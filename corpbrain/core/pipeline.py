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
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from corpbrain.core._progress import (
    FileGenerated,
    FileSkipped,
    FileStage,
    FileStarted,
    GraphFinished,
    GraphStarted,
    ModelLoading,
    ModelReady,
    ProgressEvent,
    RelatedInjected,
    RunFinished,
    RunStarted,
    Stage,
)
from corpbrain.core.config import ENGINE_CLOUD, ScanConfig
from corpbrain.core.consent import is_cloud_consent_granted
from corpbrain.core.embedding_text import parse_wiki_markdown, summary_embedding_text
from corpbrain.core.errors import (
    GpuGateError,
    PreconditionError,
    TokenBudgetExceededError,
)
from corpbrain.core.extract import prepare_summary_input
from corpbrain.core.graph import build_graph, extract_references, rank_related
from corpbrain.core.graphstore import GraphStore, SqliteGraphStore, graph_path_for
from corpbrain.core.llm.anthropic_client import (
    AnthropicSummarizer,
    CloudApiError,
    CloudRateLimitedError,
    preflight,
    resolve_api_key,
)
from corpbrain.core.llm.base import LLMParseError, Summarizer
from corpbrain.core.llm.embed import EmbeddingError, embed
from corpbrain.core.llm.ollama_client import (
    ModelNotAvailableError,
    OllamaNotAvailableError,
    list_models,
    model_present,
)
from corpbrain.core.llm.summarize import OllamaSummarizer
from corpbrain.core.models import (
    DocFacts,
    EmbeddingFailure,
    GeneratedWiki,
    GraphEdge,
    GraphNode,
    GraphOutcome,
    GraphSkipReason,
    IndexingSkipReason,
    InjectionFailure,
    PiiMasking,
    ScanPlan,
    ScanResult,
    SearchResult,
    SkippedFile,
    SkipReason,
    SummaryResult,
)
from corpbrain.core.output import inject_related_block, output_path_for, write_wiki
from corpbrain.core.plan import plan_scan
from corpbrain.core.render import render_markdown, render_related_block
from corpbrain.core.rerun import read_source_path, should_regenerate
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
    consent_path: Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
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
        consent_path: 클라우드 동의 설정 파일 경로(선택). `consent` 모듈의 경로 주입 이음새를
            코어 진입점까지 이어 준다 — 테스트나 후속 UI 어댑터가 사용자의 실제
            `~/.corpbrain/config.json`을 건드리지 않고 격리할 수 있다. `None`(기본)이면 실제
            사용자 설정 경로를 쓴다. `engine="local"`이면 읽지 않는다.
        should_cancel: 협조적 취소를 묻는 **순수 술어**(선택, v0.9 §4.7). 파일 루프 경계에서
            호출해 `True`면 멈추며, 계약은 「진행 중인 문서를 마친 뒤 멈춘다」다. `None`(기본)
            이면 취소를 묻지 않는다.

            **`threading.Event`를 받지 않는다** — 코어에는 `threading`·`asyncio`·`signal`
            import가 하나도 없고, 순수 술어로 두면 그 성질이 유지되어 후속 어댑터가
            프로세스·비동기로 가도 변환층이 생기지 않는다. **`on_event`의 반환값으로 취소를
            표현하지도 않는다** — 표시 장치와 실행 제어를 한 콜백에 섞으면 sink 버그가 스캔을
            조용히 멈추는 실패 모드가 생긴다.

            **이 술어의 예외는 삼키지 않는다.** `_emit`이 `on_event` 예외를 흡수하는 것과
            의도적으로 다르다 — sink는 표시 장치라 죽어도 스캔이 계속되는 것이 옳지만, 취소
            술어는 제어 입력이라 조용히 무시하면 사용자의 중단 요청이 사라진다.

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
    cloud = config.engine == ENGINE_CLOUD

    # 클라우드 선행 조건(동의 → API 키 → 인증 프리플라이트)을 네트워크보다 먼저 확정한다
    # (v0.5 §4.3 · §3 항목2·4). 동의 확인은 로컬 파일 읽기라 가장 값싸므로 맨 앞에 둔다.
    api_key: str | None = None
    if cloud:
        _require_cloud_consent(consent_path)
        api_key = resolve_api_key()

    # 임베딩은 엔진과 무관하게 항상 로컬이지만(v0.5 §2 비목표), **cloud에서는 Ollama가 없어도
    # 진행한다** — 스펙 §1이 대상으로 명시한 "로컬 미가용(Ollama 미설치)" 사용자가 정작
    # 클라우드 경로에서 막히는 모순을 없앤다. 이때 위키는 정상 생성하고 벡터 인덱싱만
    # 건너뛴다(`search` 불가). 로컬 엔진에서는 요약 자체가 불가능하므로 종전대로 차단한다.
    skip_indexing: IndexingSkipReason | None = None
    try:
        available_models = list_models(config.ollama_url)
    except OllamaNotAvailableError:
        if not cloud:
            raise
        skip_indexing = IndexingSkipReason.OLLAMA_UNAVAILABLE
    else:
        if not cloud and not model_present(available_models, config.model):
            raise ModelNotAvailableError(
                f"대상 모델을 찾지 못했습니다: {config.model} — "
                f"먼저 `ollama pull {config.model}` 를 실행하세요."
            )
        if not model_present(available_models, config.embed_model):
            if not cloud:
                raise ModelNotAvailableError(
                    f"대상 모델을 찾지 못했습니다: {config.embed_model} — "
                    f"먼저 `ollama pull {config.embed_model}` 를 실행하세요."
                )
            skip_indexing = IndexingSkipReason.EMBED_MODEL_MISSING

    if api_key is not None:
        preflight(api_key)

    # 게이트 판정은 상한(`--max`) 절단 이전의 발견 집합으로 계산한다(플랜은 순수·로컬).
    # 어댑터가 배너용으로 이미 계산한 plan을 넘기면 재사용해 하드웨어 감지·stat 패스를 아끼는다.
    if findings is None:
        findings = scan_folder(root, max_files=None, out_dir=config.out_dir)
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

    summarizer = _build_summarizer(config, api_key)

    total = len(findings.targets)
    _emit(on_event, RunStarted(at=time.monotonic(), model=summarizer.model, total=total))

    if findings.limit_exceeded:
        _emit(on_event, RunFinished(at=time.monotonic()))
        return result

    run_state = _RunState()
    indexing = skip_indexing is None
    store, existing_ids = (
        _open_index(config) if indexing else (_NoIndexStore(), frozenset())
    )
    result.indexing_skip_reason = skip_indexing
    valid_ids: set[str] = set()
    doc_ids = frozenset(str(path) for path in findings.targets)
    try:
        graph = SqliteGraphStore(graph_path_for(config.out_dir))
    except BaseException:
        # 그래프 DB 개봉 실패(스키마 버전 불일치·손상·권한)는 §5가 설계한 경로다. 여기서
        # 되돌리지 않으면 이미 연 벡터 인덱스 연결이 샌다 — CLI는 곧 끝나 티가 안 나지만,
        # `run_scan()`을 반복 호출하는 후속 어댑터에서 커넥션이 누적된다.
        store.close()
        raise
    try:
        for index, source_path in enumerate(findings.targets, start=1):
            # 파일 루프 **경계**에서 묻는다 — 직전 문서는 이미 끝났고 이 문서는 아직 시작하지
            # 않았으므로, 「진행 중인 문서를 마친 뒤 멈춘다」는 계약이 그대로 성립한다.
            # 예외를 감싸지 않는 것은 의도다(위 독스트링).
            if should_cancel is not None and should_cancel():
                result.cancelled = True
                break
            _process_one(
                source_path, root, config, result,
                on_event=on_event, index=index, total=total, run_state=run_state,
                store=store, existing_ids=existing_ids, summarizer=summarizer,
                graph=graph, doc_ids=doc_ids, indexing=indexing,
            )
            out_path = output_path_for(source_path, root, config.out_dir)
            if out_path.exists():
                valid_ids.add(str(source_path))

        if not result.cancelled:
            # 고아 벡터 정리 (v0.4 스펙 §3 항목5): 이번 스캔 대상 범위(root) 안에서 위키가 없는
            # 것으로 판명된 doc_id(원문 삭제·위키 삭제 등)만 지운다. root 밖의 기존 doc_id(예:
            # 더 넓은 폴더로 이미 인덱싱된 뒤 이번엔 하위 폴더만 좁혀 스캔한 경우)는 이번 스캔과
            # 무관하므로 건드리지 않는다.
            #
            # **취소되면 이 정리를 통째로 건너뛴다** (v0.9 §4.7). `valid_ids`는 파일 루프가
            # **방문한 문서만** 담으므로, 루프가 일찍 끊기면 아직 방문하지 않은 문서 전부가
            # 「위키가 사라진 문서」로 오판돼 벡터가 지워진다(문서 50개 중 3번째에서 취소 →
            # 47건 삭제). 다음 실행이 백필하므로 영구 손실은 아니나 문서마다 임베딩 호출을
            # 다시 치르고 그 사실이 보고되지 않는다. v0.6 §5가 「위키를 하나라도 읽지 못하면
            # 재료 정리를 통째로 건너뛴다」로 세운 잣대와 같다 — **목록이 불완전한 채로
            # «없는 문서»를 판정하지 않는다.**
            try:
                for stale_id in existing_ids - valid_ids:
                    if Path(stale_id).is_relative_to(root):
                        store.delete(stale_id)
            except sqlite3.Error:
                pass  # 정리 실패는 베스트 에포트 — 이미 완료된 스캔 결과를 무효화하지 않는다.

            # 패스2·패스3 — 저장소가 열려 있는 이 블록 안에서 돈다 (v0.6 §4.8). `iter_vectors()`가
            # 유사도 계산에 필요하므로 `finally: store.close()`의 범위를 실행 끝까지 늘린다.
            #
            # **취소되면 그래프 단계도 건너뛴다** — 취소가 가장 빨리 듣는 쪽을 택한다. 안전한
            # 이유는 `doc_facts` upsert가 패스2가 아니라 **패스1의 파일 루프 안에서 문서마다**
            # 일어나기 때문이다. 완료된 문서의 재료가 엔티티까지 온전히 남아, 다음 `scan`이
            # 재요약 없이 그래프와 「관련 문서」를 자동 회복한다. 남는 대가는 다음 실행까지의
            # 창뿐이며 그것은 종료 보고가 「그래프 미반영」으로 알린다(`report.py`).
            result.graph = _run_graph_stage(
                config, store=store, graph=graph, indexing=indexing, on_event=on_event
            )
    finally:
        store.close()
        graph.close()

    _emit(on_event, RunFinished(at=time.monotonic()))
    return result


class _NoIndexStore:
    """인덱싱을 건너뛸 때 쓰는 무동작 저장소 — `VectorStore` 계약을 그대로 만족한다.

    `--engine cloud`인데 로컬 Ollama가 없어 임베딩을 계산할 수 없는 경우에만 쓴다
    (스펙 §1의 "로컬 미가용" 사용자). 파이프라인 곳곳에 `if store is not None` 분기를
    흩뿌리는 대신 무동작 구현을 끼워 넣어 처리 경로를 하나로 유지한다.
    """

    #: 아무것도 기록하지 않으므로 모델명도 없다 — `_open_index`의 혼입 검사와 무관하다.
    model_name: str | None = None

    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        """인덱싱하지 않는다."""

    def delete(self, doc_id: str) -> None:
        """지울 벡터가 없다."""

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """검색 대상이 없다 — `search` 명령은 이 저장소를 쓰지 않는다."""
        return []

    def list_ids(self) -> list[str]:
        """저장된 문서가 없다 — 고아 벡터 정리도 아무 일을 하지 않는다."""
        return []

    def iter_vectors(self) -> Iterator[tuple[str, list[float]]]:
        """낼 벡터가 없다 — 유사도 엣지 0개인 부분 그래프가 분기 없이 성립한다 (v0.6 §5)."""
        return iter(())

    def set_model_name(self, model_name: str) -> None:
        """기록할 인덱스가 없다."""

    def close(self) -> None:
        """쥔 자원이 없다."""


def _require_cloud_consent(config_path: Path | None = None) -> None:
    """클라우드 엔진 사용 동의를 확인한다 — 없으면 선행 조건 실패 (v0.5 §3 항목2).

    `config_path`는 `consent` 모듈이 마련한 경로 주입 이음새를 코어 진입점까지 이어 준다.
    이 인자가 없으면 `run_scan`을 직접 호출하는 테스트나 후속 UI 어댑터가 개발자의 실제
    `~/.corpbrain/config.json`을 읽게 되어, 수동 스모크로 동의를 한 번 켜는 순간 조용히
    다른 분기를 타게 된다.
    """
    if is_cloud_consent_granted(config_path=config_path):
        return
    raise PreconditionError(
        "cloud 엔진 사용 동의가 필요합니다 — 문서 내용이 외부(Anthropic)로 전송됩니다. "
        "먼저 `corpbrain consent cloud --grant` 를 실행하세요."
    )


def _build_summarizer(config: ScanConfig, api_key: str | None) -> Summarizer:
    """`config.engine`으로 요약 백엔드를 고른다 — 파이프라인은 이후 백엔드를 알지 못한다."""
    if config.engine == ENGINE_CLOUD:
        # 프리플라이트에서 이미 확정돼 있지만, 코어 API를 직접 호출하는 경로(어댑터 없이
        # run_scan을 부르는 UI 등)를 위해 여기서도 방어적으로 해소한다.
        return AnthropicSummarizer(config.cloud_model, api_key or resolve_api_key())
    return OllamaSummarizer(config.model, config.ollama_url)


def _enforce_gates(config: ScanConfig, plan: ScanPlan) -> None:
    """차단 게이트(GPU·토큰)를 강제한다 — 첫 위반에서 예외로 종료 (v0.3 스펙 §4.2).

    `--force-gates`면 두 차단 게이트를 모두 무시한다(단 `file_too_large` 스킵은 별개다).
    개별 파일 크기 게이트는 여기서 다루지 않고 파일 처리 단계에서 스킵으로 처리한다.

    v0.5: `engine="cloud"`면 GPU 게이트를 건너뛴다 — 클라우드 요약은 로컬 GPU를 전혀 쓰지
    않으므로 GPU 미탐지가 차단 사유가 될 수 없다 (§4.7). 토큰 게이트는 비용 보호 목적이라
    엔진과 무관하게 그대로 적용한다.
    """
    gate = plan.gate
    if config.force_gates or gate is None:
        return
    if gate.gpu_enforced and not gate.gpu_ok:
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
    (v0.4 스펙 §3 항목13·§4.2 ⑦ — search가 인덱스에 기록된 모델을 강제 사용하는 §3 항목7과
    대칭을 이루는 scan 쪽 불변식). 파일 손상·권한 문제 등 sqlite 계층 오류는 스펙 §5의
    "손상 시 에러 + --force 안내"에 맞춰 `PreconditionError`로 감싼다.
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
    summarizer: Summarizer,
    graph: GraphStore,
    doc_ids: frozenset[str],
    indexing: bool = True,
) -> None:
    """파일 1개를 처리한다 — 어떤 실패도 이 함수 밖으로 새어 나가지 않는다.

    `indexing=False`면 임베딩 호출 자체를 하지 않는다 — 로컬 Ollama가 없어 인덱싱을
    건너뛰는 경우다(v0.5 §1). 저장소만 무동작으로 바꾸면 임베딩은 그대로 호출되므로
    여기서 함께 막아야 한다.
    """
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

    if not should_regenerate(source_path, out_path, config.force, engine=summarizer.engine):
        result.skipped.append(SkippedFile(path=source_path, reason=SkipReason.UP_TO_DATE))
        # 위키는 스킵돼도, 인덱스에 이 문서 벡터가 아직 없으면 기존 위키에서 백필한다
        # (v0.4 스펙 §3 항목3 정정 — 재생성 여부가 아니라 인덱스 존재 여부가 기준).
        if indexing and path_str not in existing_ids:
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
        _emit(on_event, ModelLoading(at=time.monotonic(), model=summarizer.model))
    started = time.monotonic()
    try:
        summary = summarizer.summarize(prepared.text)
    except (LLMParseError, CloudRateLimitedError, CloudApiError) as exc:
        run_state.model_loaded = True
        # 실패해도 마스킹 기록은 남긴다 — 응답 파싱 실패·레이트리밋은 **이미 전송된 뒤**라
        # 여기서 빠뜨리면 외부로 나간 문서가 감사 기록에서 통째로 사라진다 (§4.5).
        _record_masking(source_path, summarizer, result)
        reason = _summary_failure_reason(exc)
        result.skipped.append(
            SkippedFile(path=source_path, reason=reason, detail=str(exc))
        )
        _emit(on_event, FileSkipped(at=time.monotonic(), index=index, total=total,
                                    path=path_str, reason=reason.value,
                                    detail=str(exc)))
        return
    latency = time.monotonic() - started
    if not run_state.model_loaded:
        run_state.model_loaded = True
        _emit(on_event, ModelReady(at=time.monotonic(), model=summarizer.model, latency=latency))
    _record_masking(source_path, summarizer, result)

    _emit(on_event, FileStage(at=time.monotonic(), index=index, total=total,
                              path=path_str, stage=Stage.RENDER))
    markdown = render_markdown(
        summary,
        source_path=path_str,
        model=summarizer.model,
        source_bytes=size_bytes,
        generated_at=datetime.now().astimezone().isoformat(),
        engine=summarizer.engine,
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
    # 그래프 재료를 남긴다 (v0.6 §4.4). 재요약된 문서만 기록하고, 스킵된 문서의 재료는
    # 저장소에 그대로 남아 다음 실행의 그래프에 계속 참여한다.
    _record_facts(source_path, summary, prepared.text, doc_ids=doc_ids, graph=graph)
    # 위키가 재생성됐으므로 벡터도 항상 재계산한다 (v0.4 스펙 §3 항목3).
    if indexing:
        _index_document(
            source_path, summary_embedding_text(summary), summary.title, config, result, store
        )
    _emit(on_event, FileGenerated(at=time.monotonic(), index=index, total=total,
                                  path=path_str, output_path=str(out_path), latency=latency))


def _record_facts(
    source_path: Path,
    summary: SummaryResult,
    text: str,
    *,
    doc_ids: frozenset[str],
    graph: GraphStore,
) -> None:
    """이번에 요약한 문서의 그래프 재료를 저장한다 (v0.6 §4.4).

    `REFERENCES`용 텍스트는 **이미 읽어 둔 요약 입력**을 그대로 재사용해 추가 파일 I/O를
    만들지 않는다 (§5). 저장 실패는 위키 생성 결과를 무효화하지 않는다 — 그 문서만 재료가
    없어 다음 실행에서 복원 경로로 떨어진다.
    """
    doc_id = str(source_path)
    try:
        graph.upsert_facts(
            DocFacts(
                doc_id=doc_id,
                title=summary.title,
                tags=list(summary.tags),
                entities=list(summary.entities),
                refs=extract_references(text, doc_ids, self_id=doc_id),
            )
        )
    except sqlite3.Error:
        pass  # 베스트 에포트 — 그래프 단계가 이 문서를 복원 경로로 다룬다


def _run_graph_stage(
    config: ScanConfig,
    *,
    store: VectorStore,
    graph: GraphStore,
    indexing: bool,
    on_event: EventSink | None = None,
) -> GraphOutcome:
    """패스2(그래프 빌드)와 패스3(「관련 문서」 주입) (v0.6 §4.8).

    대상은 이번 실행에서 처리한 문서가 아니라 **`--out`에 존재하는 위키 전체**다 (§4.1) —
    재실행에서 대부분의 문서가 `up_to_date`로 스킵돼도 그래프가 쪼그라들지 않는다.

    v0.9부터 이 구간이 진행 이벤트 3종을 낸다 (§4.7). 그 전에는 마지막 파일 이후
    `RunFinished`까지 아무 이벤트도 나지 않아, 대형 `--out`에서 진행 표시가 멈춘 것처럼
    보였다.
    """
    _emit(on_event, GraphStarted(at=time.monotonic()))
    inventory = collect_wiki_documents(config.out_dir)
    wikis = inventory.documents
    facts, missing = _materialize_facts(wikis, config=config, graph=graph)
    if inventory.complete:
        _prune_orphan_facts(graph, known=wikis.keys())

    nodes, edges = build_graph(
        facts, store.iter_vectors(), similarity_threshold=config.similarity_threshold
    )
    skipped = None if indexing else GraphSkipReason.VECTORS_UNAVAILABLE
    try:
        graph.replace_graph(nodes, edges)
    except sqlite3.Error as exc:
        # 단일 트랜잭션이라 이전 그래프가 그대로 남는다. 위키는 이미 생성돼 있고 LLM 비용도
        # 지불된 상태이므로 스캔 전체를 무효화하지 않는다 (§5).
        _emit(on_event, GraphFinished(at=time.monotonic(), stats=None))
        return GraphOutcome(
            similarity_skipped=GraphSkipReason.BUILD_FAILED,
            build_failure=str(exc),
            facts_missing_count=missing,
            duplicate_sources=inventory.duplicates,
        )

    relative = {
        doc_id: path.relative_to(config.out_dir).as_posix() for doc_id, path in wikis.items()
    }
    updated, failures = _inject_related(
        wikis, nodes=nodes, edges=edges, relative=relative, top_k=config.related_top_k,
        on_event=on_event,
    )
    stats = graph.stats()
    _emit(on_event, GraphFinished(at=time.monotonic(), stats=stats))
    return GraphOutcome(
        stats=stats,
        similarity_skipped=skipped,
        facts_missing_count=missing,
        related_updated_count=updated,
        injection_failures=failures,
        duplicate_sources=inventory.duplicates,
    )


@dataclass
class WikiInventory:
    """`--out` 아래 위키 목록과, 그 목록을 믿어도 되는지에 대한 판정."""

    documents: dict[str, Path] = field(default_factory=dict)
    #: 하나라도 읽지 못했으면 목록이 불완전하다 — 파괴적인 재료 정리를 건너뛰는 근거다.
    complete: bool = True
    #: 같은 원문을 가리켜 밀려난 위키들 (마지막 것만 그래프에 참여한다).
    duplicates: list[Path] = field(default_factory=list)


def collect_wiki_documents(out_dir: Path) -> WikiInventory:
    """`--out` 아래 위키를 모아 `doc_id` → 위키 경로로 만든다.

    **공개 이름이다** (v0.9). GUI의 위키 상세가 `doc_id`로 위키 파일을 찾을 때 같은 규칙을
    써야 하기 때문이다 — 중복 원문 처리와 「읽지 못한 위키는 목록을 불완전으로 표시한다」가
    어댑터마다 복제되면, 한쪽만 고쳐지는 순간 두 경로가 같은 `--out`을 다르게 본다.

    front-matter의 `source_path`가 곧 `doc_id`다 (§4.1). 그 키가 없는 `.md`(사용자가 손으로
    둔 메모 등)는 조용히 건너뛰고, **읽지 못한 위키**는 목록을 불완전으로 표시한다.
    """
    inventory = WikiInventory()
    if not out_dir.is_dir():
        return inventory
    for path in sorted(out_dir.rglob("*.md")):
        doc_id = read_source_path(path)
        if doc_id is None:
            inventory.complete = False
            continue
        if not doc_id:
            continue
        if doc_id in inventory.documents:
            # 서로 다른 스캔 루트가 같은 `--out`을 공유하면 생길 수 있다. 마지막 것이
            # 이기지만 조용히 사라지게 두지 않고 종료 요약에 알린다.
            inventory.duplicates.append(inventory.documents[doc_id])
        inventory.documents[doc_id] = path
    return inventory


def _materialize_facts(
    wikis: dict[str, Path], *, config: ScanConfig, graph: GraphStore
) -> tuple[list[DocFacts], int]:
    """저장된 재료를 모으고, 없는 문서는 위키를 파싱해 1회 복원한다 (§4.4).

    복원된 재료는 엔티티가 빈 배열이다 — 위키에 남지 않기 때문이다. 그래서 v0.5 이하
    산출물도 태그·참조·유사도 3종이 동작하는 부분 그래프에 참여한다.
    """
    facts: list[DocFacts] = []
    missing = 0
    for doc_id, wiki_path in wikis.items():
        stored = graph.get_facts(doc_id)
        if stored is not None:
            facts.append(stored)
            continue
        restored = _restore_facts(doc_id, wiki_path, config=config, known=wikis.keys())
        if restored is None:
            continue
        missing += 1
        facts.append(restored)
        try:
            graph.upsert_facts(restored)  # 파싱 비용은 문서당 1회뿐이다
        except sqlite3.Error:
            pass  # 캐시 실패는 다음 실행에서 다시 복원하면 된다
    return facts, missing


def _restore_facts(
    doc_id: str, wiki_path: Path, *, config: ScanConfig, known: Iterable[str]
) -> DocFacts | None:
    try:
        markdown = wiki_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    title, _text, tags = parse_wiki_markdown(markdown)
    return DocFacts(
        doc_id=doc_id, title=title, tags=tags, entities=[], refs=_restore_refs(doc_id, config, known)
    )


def _restore_refs(doc_id: str, config: ScanConfig, known: Iterable[str]) -> list[str]:
    """복원 경로에서만 원문을 `--max-chars`까지 1회 다시 읽어 참조를 계산한다 (§5).

    원문이 이미 없거나 접근 불가하면 빈 배열로 둔다.
    """
    prepared = prepare_summary_input(Path(doc_id), config.max_chars)
    if prepared.text is None:
        return []
    return extract_references(prepared.text, known, self_id=doc_id)


def _prune_orphan_facts(graph: GraphStore, *, known: Iterable[str]) -> None:
    """위키가 사라진 문서의 재료를 지운다 — 유령 노드를 막는다 (v0.4 고아 벡터 정리 계승).

    **위키 목록이 완전할 때만 호출한다.** 하나라도 읽지 못한 채 이 판정을 내리면, 파일이
    잠긴 일시적 조건이 `doc_facts` 삭제(엔티티 영구 소실)로 번진다.
    """
    known_ids = set(known)
    try:
        stale = [f.doc_id for f in graph.iter_facts() if f.doc_id not in known_ids]
        for doc_id in stale:
            graph.delete_facts(doc_id)
    except sqlite3.Error:
        pass  # 정리 실패는 베스트 에포트


def _inject_related(
    wikis: dict[str, Path],
    *,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    relative: dict[str, str],
    top_k: int,
    on_event: EventSink | None = None,
) -> tuple[int, list[InjectionFailure]]:
    """패스3 — 파일별 베스트 에포트로 「관련 문서」를 반영한다 (§5).

    진행률은 이 패스에만 실린다 — `--out` 아래 위키 수를 알아 쪼갤 수 있기 때문이다
    (v0.9 §4.7). 이벤트는 **내용이 바뀌지 않아 파일을 다시 쓰지 않은 위키에도** 낸다:
    진행 표시의 단위는 「처리한 위키」이지 「고쳐 쓴 위키」가 아니며, 후자만 세면 재실행에서
    대부분의 위키가 그대로일 때 진행바가 멈춘 것처럼 보인다.
    """
    updated = 0
    failures: list[InjectionFailure] = []
    total = len(wikis)
    for index, (doc_id, wiki_path) in enumerate(wikis.items(), start=1):
        block = render_related_block(
            rank_related(doc_id, nodes, edges, relative_paths=relative, top_k=top_k),
            relative_to=relative[doc_id],
            relative_paths=relative,
        )
        try:
            if inject_related_block(wiki_path, block):
                updated += 1
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(InjectionFailure(path=wiki_path, detail=str(exc)))
        _emit(on_event, RelatedInjected(at=time.monotonic(), index=index, total=total,
                                        path=str(wiki_path)))
    return updated, failures


def _summary_failure_reason(exc: Exception) -> SkipReason:
    """요약 실패를 스킵 사유로 매핑한다 — 429만 별도, 나머지 클라우드 실패는 한 사유 (v0.5 §3 항목8)."""
    if isinstance(exc, CloudRateLimitedError):
        return SkipReason.CLOUD_RATE_LIMITED
    if isinstance(exc, CloudApiError):
        return SkipReason.CLOUD_API_ERROR
    return SkipReason.SUMMARY_FAILED


def _record_masking(source_path: Path, summarizer: Summarizer, result: ScanResult) -> None:
    """직전 요약에서 마스킹된 PII 건수를 결과에 남긴다 (v0.5 §4.5).

    로컬 백엔드는 마스킹을 하지 않으므로(외부로 나가지 않는다) 남길 것이 없다.
    """
    masked = summarizer.last_mask
    if masked is None or not masked.counts:
        return
    result.pii_maskings.append(
        PiiMasking(
            path=source_path,
            total=masked.total,
            counts={pii_type.value: count for pii_type, count in masked.counts.items()},
        )
    )


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
    title, text, _tags = parse_wiki_markdown(markdown)
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
