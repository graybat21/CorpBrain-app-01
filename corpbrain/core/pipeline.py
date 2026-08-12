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
from corpbrain.core.errors import PreconditionError
from corpbrain.core.extract import prepare_summary_input
from corpbrain.core.llm.ollama_client import detect
from corpbrain.core.llm.summarize import LLMParseError, summarize
from corpbrain.core.models import GeneratedWiki, ScanResult, SkippedFile, SkipReason
from corpbrain.core.output import output_path_for, write_wiki
from corpbrain.core.render import render_markdown
from corpbrain.core.rerun import should_regenerate
from corpbrain.core.scanner import scan_folder

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


def run_scan(config: ScanConfig, *, on_event: EventSink | None = None) -> ScanResult:
    """폴더를 스캔해 문서마다 위키 마크다운 1개를 생성하고 결과를 반환한다.

    Args:
        config: 실행 파라미터 (순수 값). 어댑터 타입에 의존하지 않는다.
        on_event: 진행 이벤트 콜백(선택). `None`이면 이벤트를 방출하지 않는다.

    Returns:
        생성·스킵 목록을 담은 `ScanResult`. 개별 파일 실패는 스킵으로 담고 예외로 올리지 않는다.

    Raises:
        PreconditionError: 입력 폴더 없음/접근 불가, Ollama 미탐지 등 선행 조건 실패.
    """
    root = _validated_root(config.folder)
    detect(config.ollama_url)

    findings = scan_folder(root, max_files=config.max_files)
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

    _emit(on_event, FileStarted(at=time.monotonic(), index=index, total=total,
                                path=path_str, bytes=_size_of(source_path)))

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
        source_bytes=_size_of(source_path),
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


def _size_of(source_path: Path) -> int:
    """파일 바이트 크기 — 접근 실패 시 0."""
    try:
        return source_path.stat().st_size
    except OSError:
        return 0


def _validated_root(folder: Path) -> Path:
    """입력 폴더가 실제로 접근 가능한 디렉터리인지 확인하고 정규화한다."""
    try:
        root = folder.resolve()
        if not root.is_dir():
            raise PreconditionError(f"입력 폴더가 없거나 디렉터리가 아닙니다: {folder}")
    except OSError as exc:
        raise PreconditionError(f"입력 폴더에 접근할 수 없습니다: {folder} ({exc})") from exc
    return root
