"""실행 진행상태(run-status) 관측용 이벤트 계약 (내부 전용).

스펙: `static/docs/specs/features/corpbrain-run-status-observability.md` §4.1.
코어는 이 이벤트를 콜백(`on_event`)으로 방출만 하고 I/O를 하지 않는다. 어댑터(CLI stderr
렌더러 등)가 `reduce`로 스냅샷을 만들고 `render_status_line`으로 표시한다.

이 모듈은 공개 API가 아니다 — `corpbrain/core/__init__.py`에 재노출하지 않는다(스펙 §2 비목표).
패키지 내부(테스트·CLI 어댑터)는 `corpbrain.core._progress`를 직접 import한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from corpbrain.core.models import GraphStats


class EventKind(StrEnum):
    """방출되는 진행 이벤트의 종류 (스펙 §4.1)."""

    RUN_STARTED = "run_started"
    MODEL_LOADING = "model_loading"
    MODEL_READY = "model_ready"
    FILE_STARTED = "file_started"
    FILE_STAGE = "file_stage"
    FILE_GENERATED = "file_generated"
    FILE_SKIPPED = "file_skipped"
    GRAPH_STARTED = "graph_started"
    RELATED_INJECTED = "related_injected"
    GRAPH_FINISHED = "graph_finished"
    RUN_FINISHED = "run_finished"


class Stage(StrEnum):
    """파일 1건 처리의 세부 단계 (스펙 §4.2)."""

    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    RENDER = "render"
    WRITE = "write"


@dataclass(frozen=True)
class ProgressEvent:
    """모든 진행 이벤트의 기반 — monotonic 타임스탬프를 공통으로 갖는다."""

    at: float

    @property
    def kind(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화 가능한 dict로 변환한다 (StrEnum은 순수 문자열로)."""
        data: dict[str, Any] = {"kind": str(self.kind)}
        for key, value in asdict(self).items():
            data[key] = str(value) if isinstance(value, StrEnum) else value
        return data


@dataclass(frozen=True)
class RunStarted(ProgressEvent):
    model: str
    total: int

    @property
    def kind(self) -> str:
        return EventKind.RUN_STARTED


@dataclass(frozen=True)
class ModelLoading(ProgressEvent):
    model: str

    @property
    def kind(self) -> str:
        return EventKind.MODEL_LOADING


@dataclass(frozen=True)
class ModelReady(ProgressEvent):
    model: str
    latency: float

    @property
    def kind(self) -> str:
        return EventKind.MODEL_READY


@dataclass(frozen=True)
class FileStarted(ProgressEvent):
    index: int
    total: int
    path: str
    bytes: int

    @property
    def kind(self) -> str:
        return EventKind.FILE_STARTED


@dataclass(frozen=True)
class FileStage(ProgressEvent):
    index: int
    total: int
    path: str
    stage: Stage

    @property
    def kind(self) -> str:
        return EventKind.FILE_STAGE


@dataclass(frozen=True)
class FileGenerated(ProgressEvent):
    index: int
    total: int
    path: str
    output_path: str
    latency: float

    @property
    def kind(self) -> str:
        return EventKind.FILE_GENERATED


@dataclass(frozen=True)
class FileSkipped(ProgressEvent):
    index: int
    total: int
    path: str
    reason: str
    detail: str = ""

    @property
    def kind(self) -> str:
        return EventKind.FILE_SKIPPED


@dataclass(frozen=True)
class GraphStarted(ProgressEvent):
    """패스2(그래프 재빌드) 진입 (v0.9 §4.7).

    진행률을 싣지 않는다 — 패스2는 쪼갤 수 없는 단일 작업이고, 없는 진행률을 지어내지
    않는다. 「쪼갤 수 있는 것만 쪼갠다」가 타입에 드러나 있다.
    """

    @property
    def kind(self) -> str:
        return EventKind.GRAPH_STARTED


@dataclass(frozen=True)
class RelatedInjected(ProgressEvent):
    """패스3에서 위키 1개의 「관련 문서」를 처리했다 (v0.9 §4.7).

    `index`·`total`·`path`는 `FileStarted`·`FileStage`·`FileGenerated`와 **같은 이름·같은
    의미**를 쓴다 — 진행 이벤트의 어휘가 갈리지 않게 한다. 기존 `FileStage`의 `Stage` enum에
    값을 더해 재사용하지 않는 이유는 그 타입이 「문서 1개를 처리하는 중」을 뜻하기 때문이다.
    의미가 달라지고 `reduce()`의 `generated` 카운트와 rate·ETA 계산이 오염된다.
    """

    index: int
    total: int
    path: str

    @property
    def kind(self) -> str:
        return EventKind.RELATED_INJECTED


@dataclass(frozen=True)
class GraphFinished(ProgressEvent):
    """패스3 종료 (v0.9 §4.7).

    `stats`는 빌드가 실패해 그래프가 이전 상태로 남은 경우 `None`이다(v0.6 §5). 그때도
    이벤트를 내 `GraphStarted`가 열어 둔 구간을 닫는다 — 열린 채 끝나면 화면이 「그래프
    빌드 중」에 멈춘 것처럼 보인다.
    """

    stats: GraphStats | None = None

    @property
    def kind(self) -> str:
        return EventKind.GRAPH_FINISHED


@dataclass(frozen=True)
class RunFinished(ProgressEvent):
    @property
    def kind(self) -> str:
        return EventKind.RUN_FINISHED


@dataclass(frozen=True)
class StatusSnapshot:
    """이벤트들을 접어 만든 '현재 상태' 값 객체 (스펙 §4.1 리치 세트)."""

    state: str = "starting"
    model: str = ""
    model_loading: bool = False
    current_file: str | None = None
    stage: str | None = None
    index: int = 0
    total: int = 0
    generated: int = 0
    skipped: int = 0
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    elapsed: float = 0.0
    rate: float = 0.0
    eta: float | None = None
    last_error: str | None = None
    last_net_latency: float | None = None
    started_at: float | None = None
    #: 그래프 단계의 세부 진행 — `None`(아직 진입 전) · `building`(패스2) · `injecting`(패스3)
    #: · `done`(패스3 종료). 파일 루프의 `stage`와 **별도 축**이다: 같은 필드에 담으면
    #: `generated` 카운트와 rate·ETA 계산이 오염된다 (v0.9 §4.7).
    graph_stage: str | None = None
    #: 패스3의 진행률. 패스2는 쪼갤 수 없어 진행률이 없으므로 `building` 동안 0으로 남는다.
    graph_index: int = 0
    graph_total: int = 0


def _with_timing(snapshot: StatusSnapshot, at: float) -> StatusSnapshot:
    """`at` 시점 기준으로 경과·처리율·ETA를 다시 계산한다 (스펙 §4.3 단순 누적 평균)."""
    if snapshot.started_at is None:
        return snapshot
    elapsed = max(0.0, at - snapshot.started_at)
    done = snapshot.generated + snapshot.skipped
    rate = (done / elapsed) if elapsed > 0 else 0.0
    remaining = max(0, snapshot.total - done)
    eta = (remaining / rate) if rate > 0 else None
    return replace(snapshot, elapsed=elapsed, rate=rate, eta=eta)


def reduce(snapshot: StatusSnapshot | None, event: ProgressEvent) -> StatusSnapshot:
    """이벤트 하나를 접어 다음 스냅샷을 만든다 (순수 함수)."""
    snap = snapshot or StatusSnapshot()
    kind = event.kind

    if kind == EventKind.RUN_STARTED:
        assert isinstance(event, RunStarted)
        snap = replace(snap, state="processing", model=event.model, total=event.total,
                       started_at=event.at)
    elif kind == EventKind.MODEL_LOADING:
        assert isinstance(event, ModelLoading)
        snap = replace(snap, model_loading=True, model=event.model or snap.model)
    elif kind == EventKind.MODEL_READY:
        assert isinstance(event, ModelReady)
        snap = replace(snap, model_loading=False, last_net_latency=event.latency)
    elif kind == EventKind.FILE_STARTED:
        assert isinstance(event, FileStarted)
        snap = replace(snap, state="processing", index=event.index, total=event.total,
                       current_file=event.path, stage=None)
    elif kind == EventKind.FILE_STAGE:
        assert isinstance(event, FileStage)
        snap = replace(snap, index=event.index, total=event.total,
                       current_file=event.path, stage=str(event.stage))
    elif kind == EventKind.FILE_GENERATED:
        assert isinstance(event, FileGenerated)
        snap = replace(snap, generated=snap.generated + 1, current_file=event.path,
                       stage=None, last_net_latency=event.latency)
    elif kind == EventKind.FILE_SKIPPED:
        assert isinstance(event, FileSkipped)
        by_reason = dict(snap.skipped_by_reason)
        by_reason[event.reason] = by_reason.get(event.reason, 0) + 1
        snap = replace(snap, skipped=snap.skipped + 1, skipped_by_reason=by_reason,
                       current_file=event.path, stage=None,
                       last_error=event.detail or snap.last_error)
    elif kind == EventKind.GRAPH_STARTED:
        # 파일 루프의 잔상(마지막 파일 이름·단계)을 지운다 — 그래프 단계는 문서 1개를
        # 처리하는 중이 아니다. `index`·`total`·`generated`는 건드리지 않는다.
        snap = replace(snap, state="graph", graph_stage="building",
                       current_file=None, stage=None)
    elif kind == EventKind.RELATED_INJECTED:
        assert isinstance(event, RelatedInjected)
        # `current_file`에 위키 경로를 실어 CLI 라이브 라인이 그대로 살아 움직인다 —
        # v0.9 §2가 「공짜 이득으로 받되 목표로 삼지 않는다」고 한 그 이득이다.
        snap = replace(snap, state="graph", graph_stage="injecting",
                       graph_index=event.index, graph_total=event.total,
                       current_file=event.path, stage=None)
    elif kind == EventKind.GRAPH_FINISHED:
        snap = replace(snap, graph_stage="done", current_file=None, stage=None)
    elif kind == EventKind.RUN_FINISHED:
        snap = replace(snap, state="done")

    return _with_timing(snap, event.at)


def _basename(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or normalized


def _fmt_mmss(seconds: float) -> str:
    total = int(max(0.0, seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def render_status_line(snapshot: StatusSnapshot) -> str:
    """스냅샷을 한 줄 문자열로 렌더한다 (문자열만 만들고 출력하지 않는다 — 스펙 §4.1)."""
    idx = f"{snapshot.index}/{snapshot.total}" if snapshot.total else str(snapshot.index)
    name = _basename(snapshot.current_file) if snapshot.current_file else "-"
    label = snapshot.stage or snapshot.state
    parts = [
        f"[{idx}] {label} {name}",
        f"model={snapshot.model or '-'}",
        f"loading={'true' if snapshot.model_loading else 'false'}",
        f"경과 {_fmt_mmss(snapshot.elapsed)}",
    ]
    if snapshot.eta is not None:
        parts.append(f"ETA {_fmt_mmss(snapshot.eta)}")
    if snapshot.rate > 0:
        parts.append(f"{snapshot.rate * 60:.1f}/min")
    parts.append(f"생성 {snapshot.generated} 스킵 {snapshot.skipped}")
    if snapshot.last_net_latency is not None:
        parts.append(f"net {snapshot.last_net_latency:.1f}s")
    return "  ".join(parts)
