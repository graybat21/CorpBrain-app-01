"""통합 테스트 — 스캔 워커가 실제로 SSE 스트림을 채우는 배선 (v0.9 §3 항목4 PR ② 몫).

PR ①이 이미 두 축을 닫아 두었다 — 코어 `on_event` 시퀀스(`test_graph_pipeline.py`)와
`format_sse()` 프레임 문법(`tests/unit/test_gui_sse.py`). 남은 반쪽은 **어댑터가 그 둘을
실제로 잇는가**이며, 이 파일이 그것만 본다.

**스레드를 띄우지 않는다.** `ScanController._run()`을 동기로 불러 같은 배선을 그대로 지나간다
— `start()`가 하는 일은 그 함수를 스레드에 얹는 것뿐이므로, 배선 단언에 스레드가 필요 없다.
`sleep`·`Event`·`Barrier` 없이 결정적으로 끝난다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.gui.scan import ScanController
from corpbrain.gui.sse import EventStream

TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}


@pytest.fixture
def ok_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(
        url: str, *, method: str = "GET", payload: Any = None, **_: Any
    ) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [float(len(payload["prompt"]) % 89), 1.0]}
        return {
            "response": json.dumps(
                {
                    "title": "제목",
                    "one_line_summary": "한 줄",
                    "key_points": ["a", "b", "c"],
                    "summary": "요약",
                    "tags": ["t"],
                },
                ensure_ascii=False,
            )
        }

    monkeypatch.setattr(gateway, "request_json", _request_json)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    for index in range(3):
        (root / f"{index}.md").write_text(f"문서 {index}", encoding="utf-8")
    return root


def _controller_and_config(corpus: Path, tmp_path: Path) -> tuple[ScanController, ScanConfig]:
    controller = ScanController(EventStream())
    config = ScanConfig(folder=corpus, out_dir=tmp_path / "wiki", force_gates=True)
    return controller, config


def test_worker_publishes_the_whole_event_sequence_into_the_stream(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """DoD 4 — 그래프 단계 이벤트가 마지막 `file_generated`와 `run_finished` **사이**에 온다."""
    controller, config = _controller_and_config(corpus, tmp_path)
    measurement = controller.measure(config)

    with controller.events.subscribe() as subscriber:
        controller.events.begin()
        controller._run(config, measurement)
        kinds = [payload["kind"] for payload in subscriber.drain()]

    assert kinds[0] == "run_started"
    assert kinds[-1] == "run_finished"
    last_generated = max(i for i, kind in enumerate(kinds) if kind == "file_generated")
    graph_span = [i for i, kind in enumerate(kinds) if kind.startswith("graph_") or kind == "related_injected"]
    assert graph_span, "그래프 단계 이벤트가 하나도 오지 않았다"
    assert min(graph_span) > last_generated
    assert max(graph_span) < len(kinds) - 1


def test_snapshot_tracks_the_run_so_a_late_viewer_resyncs(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """접속이 늦은 화면은 스냅샷 한 장으로 그때까지의 집계를 복원한다 (§4.3)."""
    controller, config = _controller_and_config(corpus, tmp_path)
    measurement = controller.measure(config)

    controller.events.begin()
    controller._run(config, measurement)

    snapshot = controller.events.snapshot
    assert snapshot is not None
    assert snapshot.generated == 3
    # 그래프 단계도 스냅샷에 반영된다 — 파일 루프와 **별도 축**이다.
    assert snapshot.graph_stage == "done"


def test_worker_wires_the_cancel_predicate_into_the_core(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """취소 요청이 실제로 코어의 파일 루프까지 닿는다."""
    controller, config = _controller_and_config(corpus, tmp_path)
    measurement = controller.measure(config)
    controller.cancel()

    controller.events.begin()
    controller._run(config, measurement)

    assert controller.result is not None
    assert controller.result.cancelled is True
    assert controller.result.generated == []
    # 워커는 끝나면서 취소 요청 플래그를 내린다 — 다음 스캔이 시작하자마자 멈추지 않는다.
    assert controller.cancel_requested is False


def test_worker_moves_a_core_failure_into_state_instead_of_dying(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """워커 스레드에서 죽은 예외를 아무도 보지 못하는 상태로 두지 않는다."""

    def _dead(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("연결 거부")

    monkeypatch.setattr(gateway, "request_json", _dead)
    controller, config = _controller_and_config(corpus, tmp_path)
    controller.events.begin()
    controller._run(config, controller.measure(config))

    assert controller.result is None
    assert controller.failure is not None
    # 구간은 반드시 닫힌다 — 실패해도 화면이 「진행 중」에 매달리지 않는다.
    assert controller.events.running is False
