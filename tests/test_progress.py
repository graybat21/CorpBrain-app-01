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
    ModelLoading,
    ModelReady,
    RunFinished,
    RunStarted,
    Stage,
    StatusSnapshot,
    reduce,
    render_status_line,
)


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
