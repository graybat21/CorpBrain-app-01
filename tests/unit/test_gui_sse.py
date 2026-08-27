"""단위 테스트 — SSE 프레임 문법과 스냅샷 판별자 (v0.9 §4.3 · DoD 4②).

**끝나지 않는 스트림을 통과시키지 않는다.** 프레임 직렬화는 순수 함수로, 팬아웃은 큐를
막히지 않게 비우는 `drain()`으로 단언한다 — `sleep`·`threading.Event`·`Barrier`가 없다.
「이벤트 시퀀스」쪽 축은 `tests/integration/test_graph_pipeline.py`가 코어 `on_event`로 본다.
"""

from __future__ import annotations

import json

from corpbrain.core._progress import (
    FileGenerated,
    GraphFinished,
    GraphStarted,
    RunFinished,
    RunStarted,
    StatusSnapshot,
    reduce,
)
from corpbrain.gui.sse import (
    SSE_KEEPALIVE,
    EventStream,
    format_sse,
    snapshot_payload,
)


def _payloads(frame: str) -> dict:
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return json.loads(frame[len("data: ") : -2])


# --- 프레임 문법 ------------------------------------------------------------------


def test_frame_is_one_data_line_terminated_by_a_blank_line() -> None:
    frame = format_sse({"kind": "run_started", "model": "m"})
    assert frame == 'data: {"kind": "run_started", "model": "m"}\n\n'


def test_frame_does_not_use_the_event_field() -> None:
    """판별자는 본문의 `kind`가 진다 — 프레임 문법이 두 갈래가 되지 않는다 (§4.3)."""
    assert "event:" not in format_sse({"kind": "snapshot"})


def test_newlines_inside_values_do_not_break_the_frame_boundary() -> None:
    """값 안의 줄바꿈은 JSON이 이스케이프하므로 `\\n\\n` 경계를 깨뜨리지 않는다."""
    frame = format_sse({"kind": "file_skipped", "detail": "첫 줄\n둘째 줄"})
    assert frame.count("\n\n") == 1
    assert _payloads(frame)["detail"] == "첫 줄\n둘째 줄"


def test_korean_is_not_escaped() -> None:
    assert "한글" in format_sse({"kind": "x", "path": "한글.md"})


def test_keepalive_is_an_sse_comment() -> None:
    """`EventSource`가 무시하는 주석이라 프론트에 판별 부담을 주지 않는다."""
    assert SSE_KEEPALIVE.startswith(":")
    assert SSE_KEEPALIVE.endswith("\n\n")


# --- 스냅샷 판별자 (§4.3) ----------------------------------------------------------


def test_every_frame_carries_a_kind() -> None:
    """스냅샷과 이벤트는 모양이 다른데 후자에만 `kind`가 있다 — 스냅샷도 감싼다."""
    snapshot = reduce(None, RunStarted(at=0.0, model="m", total=3))
    first = _payloads(format_sse(snapshot_payload(snapshot, running=True)))
    later = _payloads(format_sse(RunStarted(at=0.0, model="m", total=3).to_dict()))
    assert first["kind"] == "snapshot"
    assert later["kind"] == "run_started"


def test_snapshot_payload_carries_the_folded_counters() -> None:
    """진행바·통계·스킵 요약이 한 프레임으로 복원된다 — 리플레이가 필요 없는 이유다."""
    snapshot: StatusSnapshot | None = None
    for event in (
        RunStarted(at=0.0, model="m", total=2),
        FileGenerated(at=1.0, index=1, total=2, path="/a.txt",
                      output_path="/o/a.md", latency=1.0),
    ):
        snapshot = reduce(snapshot, event)

    payload = snapshot_payload(snapshot, running=True)
    assert payload["running"] is True
    assert payload["snapshot"]["generated"] == 1
    assert payload["snapshot"]["total"] == 2
    assert payload["snapshot"]["state"] == "processing"


def test_snapshot_is_null_before_any_scan_has_run() -> None:
    """기본 `StatusSnapshot()`을 대신 보내지 않는다 — 그 값은 `state="starting"`이라
    화면이 「곧 시작한다」로 읽는다."""
    payload = snapshot_payload(None, running=False)
    assert payload == {"kind": "snapshot", "running": False, "snapshot": None}


# --- 팬아웃 (§4.4 「스캔 상태는 서버가 소유한다」) -------------------------------------


def test_publish_folds_the_snapshot_and_fans_out_to_subscribers() -> None:
    stream = EventStream()
    with stream.subscribe() as first, stream.subscribe() as second:
        stream.begin()
        stream.publish(RunStarted(at=0.0, model="m", total=1))
        stream.publish(GraphStarted(at=1.0))

        kinds = [payload["kind"] for payload in first.drain()]
        assert kinds == ["run_started", "graph_started"]
        assert [payload["kind"] for payload in second.drain()] == kinds

    # 두 구독자가 같은 스냅샷을 본다 — 새로고침·다른 탭이 진행 중인 스캔에 다시 붙는다.
    assert stream.snapshot is not None
    assert stream.snapshot.graph_stage == "building"
    assert stream.subscriber_count == 0  # 컨텍스트를 벗어나면 해제된다


def test_the_first_frame_reflects_state_at_connect_time() -> None:
    """접속 시점의 스냅샷이 첫 프레임이다 — 그 전 이벤트를 리플레이하지 않는다."""
    stream = EventStream()
    stream.begin()
    stream.publish(RunStarted(at=0.0, model="m", total=1))
    stream.publish(GraphFinished(at=2.0, stats=None))

    payload = _payloads(stream.current_frame())
    assert payload["kind"] == "snapshot"
    assert payload["snapshot"]["graph_stage"] == "done"

    with stream.subscribe() as late:
        assert late.drain() == []  # 늦게 붙은 구독자에게 과거 이벤트가 오지 않는다


def test_end_keeps_the_last_snapshot_but_clears_running() -> None:
    stream = EventStream()
    stream.begin()
    stream.publish(RunStarted(at=0.0, model="m", total=1))
    stream.publish(RunFinished(at=1.0))
    stream.end()

    payload = _payloads(stream.current_frame())
    assert payload["running"] is False
    assert payload["snapshot"]["state"] == "done"


def test_begin_drops_the_previous_run_snapshot() -> None:
    stream = EventStream()
    stream.begin()
    stream.publish(RunStarted(at=0.0, model="m", total=9))
    stream.end()
    stream.begin()

    assert _payloads(stream.current_frame())["snapshot"] is None


def test_get_returns_none_when_nothing_arrives() -> None:
    """호출자가 `None`을 받으면 keepalive를 낸다 — 유휴 연결이 끊기지 않는다."""
    stream = EventStream()
    with stream.subscribe() as subscriber:
        assert subscriber.get(timeout=0.0) is None


def test_attach_loses_no_event_between_snapshot_and_subscription() -> None:
    """스냅샷 확보와 구독 등록 사이에 방출된 이벤트가 사라지지 않는다.

    둘을 따로 하면 그 사이의 `publish()`가 **어느 쪽에도 담기지 않는다** — 스냅샷은 그
    이전에 찍혔고 구독자는 아직 없었기 때문이며, 서버는 스냅샷을 다시 보내지 않으므로
    그 화면은 끝까지 어긋난 채로 남는다. 아래는 그 창을 «스냅샷을 손에 든 채 이벤트를
    방출」로 재현한다.
    """
    stream = EventStream()
    stream.begin()

    with stream.attach() as (snapshot, subscriber):
        # 첫 프레임을 소켓에 흘려보내는 동안 스캔이 이벤트를 낸 상황.
        stream.publish(RunStarted(at=0.0, model="m", total=1))
        assert _payloads(snapshot)["snapshot"] is None  # 스냅샷에는 없고
        assert [p["kind"] for p in subscriber.drain()] == ["run_started"]  # 큐에는 있다


def test_attach_does_not_deliver_an_event_twice() -> None:
    """반대 방향의 실수도 막는다 — 구독을 먼저 하고 스냅샷을 나중에 찍으면 이중 반영된다."""
    stream = EventStream()
    stream.begin()
    stream.publish(RunStarted(at=0.0, model="m", total=1))

    with stream.attach() as (snapshot, subscriber):
        # 이미 스냅샷에 접힌 이벤트가 큐로 또 오지 않는다.
        assert _payloads(snapshot)["snapshot"]["total"] == 1
        assert subscriber.drain() == []
