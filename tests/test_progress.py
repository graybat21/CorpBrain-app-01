"""단위 테스트 — 진행상태 이벤트 계약(reduce·to_dict·render) (스펙 §3-2,3,4)."""

from __future__ import annotations

import json

import pytest

from corpbrain.core._progress import (
    EventKind,
    FileGenerated,
    FileSkipped,
    FileStage,
    FileStarted,
    GraphFinished,
    GraphStarted,
    ModelLoading,
    ModelReady,
    RelatedInjected,
    RunFinished,
    RunStarted,
    Stage,
    StatusSnapshot,
    reduce,
    render_status_line,
)
from corpbrain.core.models import GraphStats


def _fold(events: list) -> StatusSnapshot:
    snapshot = None
    for event in events:
        snapshot = reduce(snapshot, event)
    assert snapshot is not None
    return snapshot


def test_reduce_folds_event_stream_into_snapshot() -> None:
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="m", total=2),
            FileStarted(at=1.0, index=1, total=2, path="/x/a.txt", bytes=10),
            FileStage(at=1.0, index=1, total=2, path="/x/a.txt", stage=Stage.SUMMARIZE),
            ModelLoading(at=1.0, model="m"),
            ModelReady(at=3.0, model="m", latency=2.0),
            FileGenerated(at=4.0, index=1, total=2, path="/x/a.txt",
                          output_path="/o/a.txt.md", latency=2.0),
            FileStarted(at=4.0, index=2, total=2, path="/x/b.txt", bytes=20),
            FileSkipped(at=5.0, index=2, total=2, path="/x/b.txt", reason="empty_document"),
            RunFinished(at=6.0),
        ]
    )

    assert snapshot.state == "done"
    assert snapshot.model == "m"
    assert snapshot.total == 2
    assert snapshot.generated == 1
    assert snapshot.skipped == 1
    assert snapshot.skipped_by_reason["empty_document"] == 1
    assert snapshot.model_loading is False
    assert snapshot.last_net_latency == 2.0
    assert snapshot.elapsed == 6.0
    assert snapshot.rate == pytest.approx(2 / 6)


def test_model_loading_toggles() -> None:
    snapshot = _fold([RunStarted(at=0.0, model="m", total=1), ModelLoading(at=0.0, model="m")])
    assert snapshot.model_loading is True
    snapshot = reduce(snapshot, ModelReady(at=1.0, model="m", latency=1.0))
    assert snapshot.model_loading is False
    assert snapshot.last_net_latency == 1.0


def test_skip_detail_becomes_last_error() -> None:
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="m", total=1),
            FileSkipped(at=1.0, index=1, total=1, path="/a", reason="summary_failed",
                        detail="깨진 JSON"),
        ]
    )
    assert snapshot.last_error == "깨진 JSON"


def test_event_to_dict_is_json_serializable() -> None:
    events = [
        RunStarted(at=0.0, model="m", total=1),
        FileStage(at=1.0, index=1, total=1, path="/a", stage=Stage.RENDER),
        FileSkipped(at=2.0, index=1, total=1, path="/a", reason="empty_document", detail="빈"),
    ]
    for event in events:
        data = event.to_dict()
        assert data["kind"] == event.kind
        assert json.dumps(data, ensure_ascii=False)  # 예외 없이 직렬화

    stage_dict = FileStage(at=1.0, index=1, total=1, path="/a", stage=Stage.RENDER).to_dict()
    assert stage_dict["stage"] == "render"
    assert stage_dict["kind"] == "file_stage"
    assert isinstance(stage_dict["stage"], str)


def test_render_status_line_contains_rich_fields() -> None:
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="qwen2.5:7b", total=50),
            FileStarted(at=41.0, index=3, total=50, path="/docs/report.docx", bytes=100),
            FileStage(at=41.0, index=3, total=50, path="/docs/report.docx", stage=Stage.SUMMARIZE),
        ]
    )
    line = render_status_line(snapshot)
    for token in ["3/50", "report.docx", "summarize", "qwen2.5:7b", "loading=false", "경과 00:41"]:
        assert token in line, f"{token!r} 누락: {line!r}"
    assert "\n" not in line


def test_render_shows_loading_true_during_model_load() -> None:
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="m", total=1),
            FileStage(at=1.0, index=1, total=1, path="/a.txt", stage=Stage.SUMMARIZE),
            ModelLoading(at=1.0, model="m"),
        ]
    )
    assert "loading=true" in render_status_line(snapshot)


def test_render_uses_basename_for_windows_paths() -> None:
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="m", total=1),
            FileStage(at=1.0, index=1, total=1, path="C:\\docs\\report.docx", stage=Stage.EXTRACT),
        ]
    )
    line = render_status_line(snapshot)
    assert "report.docx" in line
    assert "C:\\docs" not in line


def test_run_finished_marks_done_and_first_event_is_run_started() -> None:
    started = reduce(None, RunStarted(at=0.0, model="m", total=0))
    assert started.state == "processing"
    finished = reduce(started, RunFinished(at=1.0))
    assert finished.state == "done"
    assert RunStarted(at=0.0, model="m", total=0).kind == EventKind.RUN_STARTED


# --- v0.9 U2: 그래프 단계 진행 이벤트 3종 (v0.9 스펙 §4.7 · DoD 7) --------------------


def test_graph_events_fold_into_their_own_axis() -> None:
    """그래프 3종이 `reduce()`를 통과해 스냅샷에 반영된다 (DoD 7).

    파일 루프의 축(`generated`·`index`·`stage`)은 건드리지 않는다 — 그것이 `FileStage`의
    `Stage` enum에 값을 더하지 않고 새 이벤트를 둔 이유다 (§4.7).
    """
    snapshot = _fold(
        [
            RunStarted(at=0.0, model="m", total=1),
            FileStarted(at=1.0, index=1, total=1, path="/x/a.txt", bytes=10),
            FileGenerated(at=2.0, index=1, total=1, path="/x/a.txt",
                          output_path="/o/a.txt.md", latency=1.0),
            GraphStarted(at=3.0),
        ]
    )
    assert snapshot.state == "graph"
    assert snapshot.graph_stage == "building"
    # 패스2는 쪼갤 수 없다 — 없는 진행률을 지어내지 않는다.
    assert (snapshot.graph_index, snapshot.graph_total) == (0, 0)
    # 파일 루프의 잔상은 지운다. 그래프 단계는 문서 1개를 처리하는 중이 아니다.
    assert snapshot.current_file is None
    assert snapshot.stage is None
    # 파일 축은 그대로다.
    assert (snapshot.generated, snapshot.index, snapshot.total) == (1, 1, 1)

    injected = reduce(
        snapshot, RelatedInjected(at=4.0, index=2, total=6, path="/o/인사/온보딩.md.md")
    )
    assert injected.graph_stage == "injecting"
    assert (injected.graph_index, injected.graph_total) == (2, 6)
    assert injected.current_file == "/o/인사/온보딩.md.md"
    assert injected.generated == 1  # 그래프 진행이 생성 카운트를 오염시키지 않는다

    stats = GraphStats(documents=6, entities=3, tags=2, edges_by_type={"TAGGED_WITH": 4})
    done = reduce(injected, GraphFinished(at=5.0, stats=stats))
    assert done.graph_stage == "done"
    assert done.current_file is None
    assert done.state == "graph"  # 실행이 끝났다는 판정은 `RunFinished`만 한다

    assert reduce(done, RunFinished(at=6.0)).state == "done"


def test_graph_events_are_json_serializable_for_sse() -> None:
    """SSE가 `to_dict()`를 그대로 싣는다 (§4.3) — 변환 계층 없이 직렬화돼야 한다."""
    started = json.loads(json.dumps(GraphStarted(at=1.0).to_dict()))
    assert started == {"kind": "graph_started", "at": 1.0}

    injected = json.loads(
        json.dumps(RelatedInjected(at=2.0, index=1, total=3, path="/o/a.md").to_dict())
    )
    assert injected == {
        "kind": "related_injected", "at": 2.0, "index": 1, "total": 3, "path": "/o/a.md",
    }

    stats = GraphStats(documents=2, entities=1, tags=1, edges_by_type={"REFERENCES": 1})
    finished = json.loads(json.dumps(GraphFinished(at=3.0, stats=stats).to_dict()))
    assert finished["kind"] == "graph_finished"
    assert finished["stats"]["documents"] == 2
    assert finished["stats"]["edges_by_type"] == {"REFERENCES": 1}

    # 빌드 실패 경로 — 그래도 구간을 닫는다 (v0.6 §5).
    assert json.loads(json.dumps(GraphFinished(at=4.0).to_dict()))["stats"] is None


def test_graph_progress_does_not_pollute_rate_and_eta() -> None:
    """`RelatedInjected`는 rate·ETA 계산의 입력(`generated`·`total`)을 바꾸지 않는다."""
    before = _fold(
        [
            RunStarted(at=0.0, model="m", total=2),
            FileGenerated(at=1.0, index=1, total=2, path="/x/a.txt",
                          output_path="/o/a.md", latency=1.0),
            FileGenerated(at=2.0, index=2, total=2, path="/x/b.txt",
                          output_path="/o/b.md", latency=1.0),
        ]
    )
    after = reduce(
        reduce(before, GraphStarted(at=2.0)),
        RelatedInjected(at=2.0, index=1, total=99, path="/o/a.md"),
    )
    assert (after.rate, after.eta, after.total) == (before.rate, before.eta, before.total)
