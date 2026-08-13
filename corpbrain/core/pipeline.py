"""코어 공개 진입점 — 스캔→추출→요약→렌더→출력 조립 (스펙 §4.5, §5).

CLI 없이 `run_scan(config)` 호출만으로 end-to-end 실행된다.
개별 파일의 실패는 예외로 올리지 않고 `ScanResult.skipped`에 사유와 함께 담아
나머지 파일 처리를 계속한다(부분 성공). 선행 조건 실패(입력 폴더 없음, Ollama 미탐지)만
`PreconditionError`로 올려 어댑터가 비-0 종료로 매핑한다.

진행상태 관측: `on_event` 콜백을 주면 처리 단계마다 구조화된 `ProgressEvent`를 방출한다
(스펙 `corpbrain-run-status-observability.md`). 콜백은 순수 관측용이며, 코어는 콜백을 호출만
하고 디스크·stderr I/O를 하지 않는다. 콜백 예외는 격리해 실제 처리를 깨지 않는다.
`on_event=None`(기본)이면 이벤트를 방출하지 않고 기존 동작과 동일하다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from corpbrain.core._progress import (
    FileGenerated,
    FileSkipped,
    FileStage,
    FileStarted,
    ModelLoading,
    ModelReady,
    ProgressEvent,
    RunFinished,
    RunStarted,
    Stage,
)
from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import GpuGateError, TokenBudgetExceededError
from corpbrain.core.extract import prepare_summary_input
from corpbrain.core.llm.ollama_client import detect
from corpbrain.core.llm.summarize import LLMParseError, summarize
from corpbrain.core.models import (
    GeneratedWiki,
    ScanPlan,
    ScanResult,
    SkippedFile,
    SkipReason,
)
from corpbrain.core.output import output_path_for, write_wiki
from corpbrain.core.plan import plan_scan
from corpbrain.core.render import render_markdown
from corpbrain.core.rerun import should_regenerate
from corpbrain.core.scanner import (
    ScanFindings,
    enforce_limit,
    safe_size,
    scan_folder,
    validated_root,
)

#: 진행 이벤트 sink 타입 — 어댑터가 주입한다.
EventSink = Callable[[ProgressEvent], None]


@dataclass
class _RunState:
    """실행 1회 동안 유지되는 관측 보조 상태 (모델 로딩 근사 표기용)."""

    model_loaded: bool = False


def _emit(on_event: EventSink | None, event: ProgressEvent) -> None:
    """이벤트를 방출한다 — sink 예외는 격리해 실제 처리를 깨지 않는다 (스펙 §5)."""
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception:  # noqa: BLE001
        # 관측 실패가 실제 문서 처리를 중단시키지 않는다 (스펙 §5).
        return


def run_scan(
    config: ScanConfig,
    *,
    on_event: EventSink | None = None,
    findings: ScanFindings | None = None,
) -> ScanResult:
    """폴더를 스캔해 문서마다 위키 마크다운 1개를 생성하고 결과를 반환한다.

    Args:
        config: 실행 파라미터 (순수 값). 어댑터 타입에 의존하지 않는다.
        on_event: 진행 이벤트 콜백(선택). `None`이면 이벤트를 방출하지 않는다.
        findings: 이미 계산된 스캔 결과(선택). 주면 재귀 순회를 생략하고 그대로 쓴다 —
            어댑터가 pre-scan 배너와 본 스캔의 디렉터리 워크를 한 번으로 공유할 때 쓴다.
            `None`(기본)이면 기존대로 직접 순회한다.

    Returns:
        생성·스킵 목록을 담은 `ScanResult`. 개별 파일 실패는 스킵으로 담고 예외로 올리지 않는다.

    Raises:
        PreconditionError: 입력 폴더 없음/접근 불가, Ollama 미탐지·모델 부재, GPU 게이트 등 선행 조건 실패.
        TokenBudgetExceededError: 스캔 전체 예상 토큰이 예산을 초과 (상한 초과, exit 3).
    """
    # 프리플라이트 (fail-fast, v0.3 스펙 §4.2): 폴더 → Ollama 구동 → 대상 모델 → GPU → 토큰.
    # 환경(요약 가능 여부)을 자원 게이트보다 먼저 확정하고, 첫 위반에서 즉시 예외로 종료한다.
    root = validated_root(config.folder)
    detect(config.ollama_url, model=config.model)

    # 게이트 판정은 상한(`--max`) 절단 이전의 발견 집합으로 계산한다(플랜은 순수·로컬).
    if findings is None:
        findings = scan_folder(root, max_files=None)
    plan = plan_scan(config, findings=findings)
    _enforce_gates(config, plan)

    findings = enforce_limit(findings, config.max_files)
    result = ScanResult(
        out_dir=config.out_dir,
        skipped=list(findings.skipped),
        limit_exceeded=findings.limit_exceeded,
        discovered_count=findings.discovered_count,
    )

    total = len(findings.targets)
    _emit(on_event, RunStarted(at=time.monotonic(), model=config.model, total=total))

    if findings.limit_exceeded:
        _emit(on_event, RunFinished(at=time.monotonic()))
        return result

    run_state = _RunState()
    for index, source_path in enumerate(findings.targets, start=1):
        _process_one(
            source_path, root, config, result,
            on_event=on_event, index=index, total=total, run_state=run_state,
        )

    _emit(on_event, RunFinished(at=time.monotonic()))
    return result


def _enforce_gates(config: ScanConfig, plan: ScanPlan) -> None:
    """차단 게이트(GPU·토큰)를 강제한다 — 첫 위반에서 예외로 종료 (v0.3 스펙 §4.2).

    `--force-gates`면 두 차단 게이트를 모두 무시한다(단 `file_too_large` 스킵은 별개다).
    개별 파일 크기 게이트는 여기서 다루지 않고 파일 처리 단계에서 스킵으로 처리한다.
    """
    gate = plan.gate
    if config.force_gates or gate is None:
        return
    if not gate.gpu_ok:
        raise GpuGateError(
            "GPU를 감지하지 못했습니다 — CPU로 강행하려면 --force-gates 를 쓰세요 "
            f"(감지: {plan.hardware.label})."
        )
    if not gate.tokens_ok:
        raise TokenBudgetExceededError(
            f"스캔 전체 예상 토큰 {plan.total_est_tokens:,}이(가) 예산 "
            f"{gate.max_total_tokens:,}을(를) 초과했습니다 — "
            "--force-gates 로 강행하거나 --max-total-tokens 를 올리세요."
        )


def _process_one(
    source_path: Path,
    root: Path,
    config: ScanConfig,
    result: ScanResult,
    *,
    on_event: EventSink | None,
    index: int,
    total: int,
    run_state: _RunState,
) -> None:
    """파일 1개를 처리한다 — 어떤 실패도 이 함수 밖으로 새어 나가지 않는다."""
    out_path = output_path_for(source_path, root, config.out_dir)
    path_str = str(source_path)
    size_bytes = safe_size(source_path)

    _emit(on_event, FileStarted(at=time.monotonic(), index=index, total=total,
                                path=path_str, bytes=size_bytes))

    # 파일 크기 게이트 (v0.3 §4.2): 개별 파일만 스킵, 나머지는 계속 (부분 성공).
    # `--force-gates`와 무관하다 — 포함하려면 `--max-file-size`를 올린다.
    if size_bytes > config.max_file_size:
        detail = f"{size_bytes:,} bytes > 상한 {config.max_file_size:,} bytes"
        result.skipped.append(
            SkippedFile(path=source_path, reason=SkipReason.FILE_TOO_LARGE, detail=detail)
        )
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=SkipReason.FILE_TOO_LARGE.value,
                                    detail=detail))
        return

    if not should_regenerate(source_path, out_path, config.force):
        result.skipped.append(SkippedFile(path=source_path, reason=SkipReason.UP_TO_DATE))
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=SkipReason.UP_TO_DATE.value))
        return

    _emit(on_event, FileStage(at=time.monotonic(), index=index, total=total,
                              path=path_str, stage=Stage.EXTRACT))
    prepared = prepare_summary_input(source_path, config.max_chars)
    if prepared.skipped is not None or prepared.text is None:
        skip = prepared.skipped or SkippedFile(
            path=source_path, reason=SkipReason.EXTRACTION_FAILED
        )
        result.skipped.append(skip)
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=skip.reason.value, detail=skip.detail))
        return

    _emit(on_event, FileStage(at=time.monotonic(), index=index, total=total,
                              path=path_str, stage=Stage.SUMMARIZE))
    if not run_state.model_loaded:
        _emit(on_event, ModelLoading(at=time.monotonic(), model=config.model))
    started = time.monotonic()
    try:
        summary = summarize(prepared.text, config.model, config.ollama_url)
    except LLMParseError as exc:
        run_state.model_loaded = True
        result.skipped.append(
            SkippedFile(path=source_path, reason=SkipReason.SUMMARY_FAILED, detail=str(exc))
        )
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=SkipReason.SUMMARY_FAILED.value,
                                    detail=str(exc)))
        return
    latency = time.monotonic() - started
    if not run_state.model_loaded:
        run_state.model_loaded = True
        _emit(on_event, ModelReady(at=time.monotonic(), model=config.model, latency=latency))

    _emit(on_event, FileStage(at=time.monotonic(), index=index, total=total,
                              path=path_str, stage=Stage.RENDER))
    markdown = render_markdown(
        summary,
        source_path=path_str,
        model=config.model,
        source_bytes=safe_size(source_path),
        generated_at=datetime.now().astimezone().isoformat(),
    )

    _emit(on_event, FileStage(at=time.monotonic(), index=index, total=total,
                              path=path_str, stage=Stage.WRITE))
    try:
        write_wiki(markdown, out_path)
    except OSError as exc:
        reason = (
            SkipReason.PERMISSION_DENIED
            if isinstance(exc, PermissionError)
            else SkipReason.EXTRACTION_FAILED
        )
        detail = f"위키 기록 실패: {exc}"
        result.skipped.append(SkippedFile(path=source_path, reason=reason, detail=detail))
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=reason.value, detail=detail))
        return

    result.generated.append(GeneratedWiki(source_path=source_path, output_path=out_path))
    _emit(on_event, FileGenerated(at=time.monotonic(), index=index, total=total,
                                  path=path_str, output_path=str(out_path), latency=latency))
