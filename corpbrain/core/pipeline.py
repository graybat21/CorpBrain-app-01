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

import sqlite3
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
from corpbrain.core.embedding_text import parse_wiki_markdown, summary_embedding_text
from corpbrain.core.errors import (
    GpuGateError,
    PreconditionError,
    TokenBudgetExceededError,
)
from corpbrain.core.extract import prepare_summary_input
from corpbrain.core.llm.embed import EmbeddingError, embed
from corpbrain.core.llm.ollama_client import (
    ModelNotAvailableError,
    list_models,
    model_present,
)
from corpbrain.core.llm.summarize import LLMParseError, summarize
from corpbrain.core.models import (
    EmbeddingFailure,
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
from corpbrain.core.vectorstore import SqliteVectorStore, VectorStore, index_path_for

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
    plan: ScanPlan | None = None,
) -> ScanResult:
    """폴더를 스캔해 문서마다 위키 마크다운 1개를 생성하고 결과를 반환한다.

    Args:
        config: 실행 파라미터 (순수 값). 어댑터 타입에 의존하지 않는다.
        on_event: 진행 이벤트 콜백(선택). `None`이면 이벤트를 방출하지 않는다.
        findings: 이미 계산된 스캔 결과(선택). 주면 재귀 순회를 생략하고 그대로 쓴다 —
            어댑터가 pre-scan 배너와 본 스캔의 디렉터리 워크를 한 번으로 공유할 때 쓴다.
            **반드시 상한(`--max`) 절단 이전의 발견 집합이어야 한다** — 자원 게이트를 이 위에서
            판정하고 절단은 run_scan이 직접 적용하므로, 이미 절단된(`targets=[]`) findings를 주면
            토큰·대용량 게이트가 빈 집합으로 계산돼 발동하지 않는다. `None`(기본)이면 직접 순회한다.
        plan: 이미 계산된 `ScanPlan`(선택). 주면 게이트 판정에 재사용해 `plan_scan`(→ 하드웨어
            감지·stat 패스)을 두 번 돌지 않는다. 위 `findings`·같은 `config`로 계산된 것이어야
            한다 — findings와 파일 수가 어긋나면(절단·다른 스캔) 신뢰하지 않고 재계산해 오게이팅을
            막는다. `None`이면 `findings`로 새로 계산한다.

    Returns:
        생성·스킵 목록을 담은 `ScanResult`. 개별 파일 실패는 스킵으로 담고 예외로 올리지 않는다.

    Raises:
        PreconditionError: 입력 폴더 없음/접근 불가, Ollama 미탐지·모델 부재, GPU 게이트 등 선행 조건 실패.
        TokenBudgetExceededError: 스캔 전체 예상 토큰이 예산을 초과 (상한 초과, exit 3).
    """
    # 프리플라이트 (fail-fast, v0.4 스펙 §4.2): 폴더 → Ollama 구동 → 대상 모델 →
    # 임베딩 모델 → GPU → 토큰. 환경(요약·임베딩 가능 여부)을 자원 게이트보다 먼저
    # 확정하고, 첫 위반에서 즉시 예외로 종료한다. ①~④는 --force-gates로 우회 불가.
    # 모델 목록은 한 번만 조회해 두 모델(요약·임베딩)을 함께 확인한다(왕복 절반으로 줄임).
    root = validated_root(config.folder)
    available_models = list_models(config.ollama_url)
    if not model_present(available_models, config.model):
        raise ModelNotAvailableError(
            f"대상 모델을 찾지 못했습니다: {config.model} — "
            f"먼저 `ollama pull {config.model}` 를 실행하세요."
        )
    if not model_present(available_models, config.embed_model):
        raise ModelNotAvailableError(
            f"대상 모델을 찾지 못했습니다: {config.embed_model} — "
            f"먼저 `ollama pull {config.embed_model}` 를 실행하세요."
        )

    # 게이트 판정은 상한(`--max`) 절단 이전의 발견 집합으로 계산한다(플랜은 순수·로컬).
    # 어댑터가 배너용으로 이미 계산한 plan을 넘기면 재사용해 하드웨어 감지·stat 패스를 아끼는다.
    if findings is None:
        findings = scan_folder(root, max_files=None)
    if plan is None or plan.file_count != len(findings.targets):
        # 넘어온 plan이 이 findings와 불일치(절단·다른 스캔)면 신뢰하지 않고 재계산해
        # 오게이팅(막아야 할 스캔이 통과하거나 그 반대)을 막는다.
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
    store, existing_ids = _open_index(config)
    valid_ids: set[str] = set()
    try:
        for index, source_path in enumerate(findings.targets, start=1):
            _process_one(
                source_path, root, config, result,
                on_event=on_event, index=index, total=total, run_state=run_state,
                store=store, existing_ids=existing_ids,
            )
            out_path = output_path_for(source_path, root, config.out_dir)
            if out_path.exists():
                valid_ids.add(str(source_path))

        # 고아 벡터 정리 (v0.4 스펙 §3 항목5): 이번 스캔 대상 범위(root) 안에서 위키가 없는
        # 것으로 판명된 doc_id(원문 삭제·위키 삭제 등)만 지운다. root 밖의 기존 doc_id(예:
        # 더 넓은 폴더로 이미 인덱싱된 뒤 이번엔 하위 폴더만 좁혀 스캔한 경우)는 이번 스캔과
        # 무관하므로 건드리지 않는다.
        try:
            for stale_id in existing_ids - valid_ids:
                if Path(stale_id).is_relative_to(root):
                    store.delete(stale_id)
        except sqlite3.Error:
            pass  # 정리 실패는 베스트 에포트 — 이미 완료된 스캔 결과를 무효화하지 않는다.
    finally:
        store.close()

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


def _open_index(config: ScanConfig) -> tuple[VectorStore, frozenset[str]]:
    """이번 실행의 벡터 인덱스를 연다 — 실패는 선행 조건 실패로 명확히 안내한다.

    인덱스가 이미 다른 임베딩 모델로 만들어져 있으면 모델 혼입을 막기 위해 즉시 거부한다
    (v0.4 스펙 §4.3 "search가 인덱스에 기록된 모델을 강제 사용"의 자매 불변식 — scan 쪽도
    한 인덱스에는 항상 한 모델만 쓰게 강제한다). 파일 손상·권한 문제 등 sqlite 계층 오류는
    스펙 §5의 "손상 시 에러 + --force 안내"에 맞춰 `PreconditionError`로 감싼다.
    """
    index_path = index_path_for(config.out_dir)
    store: VectorStore | None = None
    try:
        store = SqliteVectorStore(index_path)
        existing_model = store.model_name
        if existing_model is not None and existing_model != config.embed_model:
            raise PreconditionError(
                f"인덱스가 다른 임베딩 모델로 생성되어 있습니다: {existing_model} "
                f"(요청: {config.embed_model}) — --embed-model {existing_model} 로 맞추거나, "
                f"{index_path} 를 지우고 --force로 다시 생성하세요."
            )
        store.set_model_name(config.embed_model)
        existing_ids = frozenset(store.list_ids())
    except sqlite3.Error as exc:
        if store is not None:
            store.close()
        raise PreconditionError(
            f"인덱스 파일을 열지 못했습니다: {index_path} ({exc}) — 손상되었거나 접근할 수 "
            f"없습니다. 문제를 해결하거나 파일을 지우고 --force로 다시 생성하세요."
        ) from exc
    except PreconditionError:
        if store is not None:
            store.close()
        raise
    return store, existing_ids


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
    store: VectorStore,
    existing_ids: frozenset[str],
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
        # 위키는 스킵돼도, 인덱스에 이 문서 벡터가 아직 없으면 기존 위키에서 백필한다
        # (v0.4 스펙 §3 항목3 정정 — 재생성 여부가 아니라 인덱스 존재 여부가 기준).
        if path_str not in existing_ids:
            _backfill_embedding(source_path, out_path, config, result, store)
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
        source_bytes=size_bytes,
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
    # 위키가 재생성됐으므로 벡터도 항상 재계산한다 (v0.4 스펙 §3 항목3).
    _index_document(
        source_path, summary_embedding_text(summary), summary.title, config, result, store
    )
    _emit(on_event, FileGenerated(at=time.monotonic(), index=index, total=total,
                                  path=path_str, output_path=str(out_path), latency=latency))


def _backfill_embedding(
    source_path: Path,
    out_path: Path,
    config: ScanConfig,
    result: ScanResult,
    store: VectorStore,
) -> None:
    """위키가 스킵된 문서 중 인덱스에 아직 없는 것을 기존 위키 파일에서 임베딩해 채운다."""
    try:
        markdown = out_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result.embedding_failures.append(
            EmbeddingFailure(path=source_path, detail=f"기존 위키를 읽지 못했습니다: {exc}")
        )
        return
    title, text = parse_wiki_markdown(markdown)
    _index_document(source_path, text, title, config, result, store)


def _index_document(
    source_path: Path,
    text: str,
    title: str,
    config: ScanConfig,
    result: ScanResult,
    store: VectorStore,
) -> None:
    """텍스트를 임베딩해 벡터 저장소에 넣는다. 실패는 해당 문서만 인덱싱 실패로 흡수한다
    (v0.4 스펙 §3 항목4 — 위키는 이미 기록돼 있으므로 그대로 유지된다).

    임베딩 실패 시 그 문서의 기존(이제는 내용과 어긋났을 수 있는) 벡터를 지운다 — 오래된
    벡터를 남겨 검색이 낡은 내용을 신뢰하는 것처럼 보이는 것보다, 그 문서가 검색에서 아예
    빠지는 편이 안전하다. 벡터 저장소 계층 오류(디스크·잠금 등)도 같은 방식으로 흡수해
    개별 파일 실패가 나머지 처리를 멈추지 않게 한다.
    """
    doc_id = str(source_path)
    try:
        vector = embed(text, config.embed_model, config.ollama_url)
    except EmbeddingError as exc:
        result.embedding_failures.append(EmbeddingFailure(path=source_path, detail=str(exc)))
        _delete_stale_vector(store, doc_id)
        return
    try:
        store.upsert(doc_id, vector, {"title": title, "source_path": doc_id})
    except sqlite3.Error as exc:
        result.embedding_failures.append(EmbeddingFailure(path=source_path, detail=str(exc)))


def _delete_stale_vector(store: VectorStore, doc_id: str) -> None:
    """재임베딩 실패 시 남아 있을 수 있는 오래된 벡터를 지운다 (베스트 에포트)."""
    try:
        store.delete(doc_id)
    except sqlite3.Error:
        pass
