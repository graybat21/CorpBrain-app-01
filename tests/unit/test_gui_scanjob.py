"""스캔 작업 관리 단위 테스트 (v0.9 스펙 §4.3 · §5).

스캔은 별도 프로세스로 돌고 중지는 프로세스 종료다. 여기서는 **진짜 자식 프로세스**를
띄운다 — 이벤트가 JSON 라인으로 실제로 건너오는지, 중지가 정말 멈추는지는 모의 객체로는
증명되지 않는다.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from corpbrain.core._progress import FileStage, RunFinished, RunStarted, Stage
from corpbrain.gui import scanjob

FAKE_RUNNER_SOURCE = """
import json, sys, time
payload = json.loads(sys.stdin.read())
for i in (1, 2):
    print(json.dumps({'kind': 'file_generated', 'at': float(i),
        'index': i, 'total': 2, 'path': f'doc{i}.md',
        'output_path': 'o.md', 'latency': 0.1}), flush=True)
print(json.dumps({'kind': 'run_finished', 'at': 3.0}), flush=True)
time.sleep(float(payload.get('max_chars', 0)) / 1000.0)
print(json.dumps({'schema': 1, 'workspace_id': sys.argv[1],
    'exit_code': 0, 'finished_at': 'now',
    'out_dir': payload['out_dir']}), flush=True)
"""


def _wait(predicate, timeout: float = 20.0) -> bool:
    """조건이 참이 될 때까지 짧게 기다린다 — 자식 프로세스는 즉시 끝나지 않는다."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


# --- 이벤트 역변환 --------------------------------------------------------------


def test_events_round_trip_through_json() -> None:
    """`kind`가 인스턴스 프로퍼티라 클래스 훑기로는 되돌릴 수 없다 — 명시 매핑을 쓴다."""
    for event in [
        RunStarted(at=1.0, model="m", total=3),
        FileStage(at=2.0, index=1, total=3, path="a.md", stage=Stage.SUMMARIZE),
        RunFinished(at=3.0),
    ]:
        restored = scanjob._event_from(json.loads(json.dumps(event.to_dict())))

        assert restored == event


def test_unknown_event_kind_is_dropped_quietly() -> None:
    """관측이 처리를 깨지 않는다 — 모르는 줄은 버린다."""
    assert scanjob._event_from({"kind": "no_such_event", "at": 1.0}) is None


def test_file_stage_with_a_bad_stage_is_dropped() -> None:
    assert (
        scanjob._event_from(
            {"kind": "file_stage", "at": 1.0, "index": 1, "total": 1, "path": "a", "stage": "없음"}
        )
        is None
    )


# --- 자식 프로세스 왕복 ----------------------------------------------------------


@pytest.fixture
def fake_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`corpbrain.gui.runner`를 대신할 가짜 모듈을 만들고 그것을 띄우게 한다.

    실제 러너를 쓰면 Ollama가 필요하다. 프로토콜(JSON 라인 → 종료 레코드)만 흉내 낸다.
    """
    module = tmp_path / "fake_runner.py"
    module.write_text(
        FAKE_RUNNER_SOURCE,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        scanjob, "_runner_command", lambda ws: [sys.executable, str(module), ws]
    )
    return module


def _payload(tmp_path: Path, **over: object) -> dict[str, object]:
    payload = {"folder": str(tmp_path / "docs"), "out_dir": str(tmp_path / "wiki")}
    payload.update(over)
    return payload


def test_start_streams_events_and_finishes(tmp_path: Path, fake_runner: Path) -> None:
    manager = scanjob.ScanJobManager()

    manager.start(workspace_id="ws1", payload=_payload(tmp_path))

    assert _wait(lambda: (manager.status() or {}).get("phase") == scanjob.PHASE_DONE)
    status = manager.status()
    assert status is not None
    assert status["running"] is False
    assert status["record"]["workspace_id"] == "ws1"
    assert [entry["path"] for entry in status["log"]] == ["doc1.md", "doc2.md"]
    assert status["snapshot"]["generated"] == 2


def test_status_is_none_before_any_run() -> None:
    assert scanjob.ScanJobManager().status() is None


def test_second_start_while_running_is_rejected(tmp_path: Path, fake_runner: Path) -> None:
    """동시 스캔은 전체에서 1개만 — 서버가 409로 매핑한다 (§5)."""
    manager = scanjob.ScanJobManager()
    manager.start(workspace_id="ws1", payload=_payload(tmp_path, max_chars=3000))

    try:
        with pytest.raises(scanjob.ScanAlreadyRunningError):
            manager.start(workspace_id="ws2", payload=_payload(tmp_path))
    finally:
        manager.stop()


def test_stop_actually_terminates_the_child(tmp_path: Path, fake_runner: Path) -> None:
    """중지 요청 후 자식 프로세스가 실제로 종료된다 (스펙 §3 항목5)."""
    manager = scanjob.ScanJobManager()
    manager.start(workspace_id="ws1", payload=_payload(tmp_path, max_chars=30000))
    assert _wait(lambda: manager.running)

    stopped = manager.stop()

    assert stopped is True
    assert manager.running is False
    assert manager._process is not None
    assert manager._process.poll() is not None  # 정말 죽었다


def test_stop_without_a_running_scan_is_false() -> None:
    assert scanjob.ScanJobManager().stop() is False


def test_graph_phase_is_shown_between_run_finished_and_the_record(
    tmp_path: Path, fake_runner: Path
) -> None:
    """코어는 그래프 단계에 이벤트를 내지 않는다 — 서버가 표시를 바꿔 준다 (§5).

    `run_finished` 뒤 종료 레코드가 오기까지의 구간에서 진행바가 멈춘 것처럼 보이면 안 된다.
    """
    manager = scanjob.ScanJobManager()
    manager.start(workspace_id="ws1", payload=_payload(tmp_path, max_chars=2000))

    assert _wait(lambda: (manager.status() or {}).get("phase") == scanjob.PHASE_GRAPH, 10.0)

    manager.stop()


def test_shutdown_kills_the_child(tmp_path: Path, fake_runner: Path) -> None:
    """서버가 내려가면 자식도 함께 종료한다 — 고아가 인덱스 락을 쥔 채 남으면 안 된다 (§5)."""
    manager = scanjob.ScanJobManager()
    manager.start(workspace_id="ws1", payload=_payload(tmp_path, max_chars=30000))
    assert _wait(lambda: manager.running)

    manager.shutdown()

    assert manager.running is False


# --- 인코딩과 실패 진단 (한글 경로에서 스캔이 통째로 실패하던 버그) ----------------


def test_child_env_pins_utf8() -> None:
    """자식이 cp949로 한글을 내보내면 부모의 UTF-8 디코딩이 깨져 결과를 통째로 잃는다.

    러너도 자기 스트림을 재구성하지만, 그 코드가 돌기 **전에** 죽는 경우의 트레이스백까지
    읽으려면 인터프리터 수준에서 정해 두어야 한다.
    """
    assert scanjob._child_env()["PYTHONIOENCODING"] == "utf-8"


def test_runner_forces_utf8_streams() -> None:
    """러너가 자기 stdout을 UTF-8로 맞춘다 — 프로세스 사이 프로토콜을 위한 조치다."""
    from corpbrain.gui import runner as gui_runner

    assert callable(gui_runner.force_utf8_streams)


DYING_RUNNER = r"""
import sys
sys.stderr.write("진짜 원인: 무언가 잘못됐다\n")
sys.exit(7)
"""

NOISY_RUNNER = r"""
import sys, json
sys.stdout.buffer.write(b"\xff\xfe not utf-8\n")
sys.stdout.buffer.flush()
print(json.dumps({"schema": 1, "workspace_id": "ws1", "exit_code": 0,
    "finished_at": "now", "out_dir": "."}), flush=True)
"""


def test_child_dying_without_a_record_reports_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """결과 없이 죽으면 **왜 그런지** 말해 준다.

    stderr를 버리면 화면에는 원인 없는 실패만 남는다. 실제로 「스캔 프로세스가 결과 없이
    종료했습니다」만 보이고 인코딩 문제라는 사실이 사라진 적이 있다.
    """
    module = tmp_path / "dying_runner.py"
    module.write_text(DYING_RUNNER, encoding="utf-8")
    monkeypatch.setattr(
        scanjob, "_runner_command", lambda ws: [sys.executable, str(module), ws]
    )
    manager = scanjob.ScanJobManager()

    manager.start(workspace_id="ws1", payload=_payload(tmp_path))

    assert _wait(lambda: not manager.running)
    status = manager.status()
    assert status is not None
    assert "종료 코드 7" in status["error"]
    assert "진짜 원인" in status["error"]


def test_undecodable_output_does_not_kill_the_pump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """깨진 바이트 한 줄이 펌프 스레드를 죽여 작업이 영영 「진행 중」으로 남지 않는다."""
    module = tmp_path / "noisy_runner.py"
    module.write_text(NOISY_RUNNER, encoding="utf-8")
    monkeypatch.setattr(
        scanjob, "_runner_command", lambda ws: [sys.executable, str(module), ws]
    )
    manager = scanjob.ScanJobManager()

    manager.start(workspace_id="ws1", payload=_payload(tmp_path))

    assert _wait(lambda: not manager.running)
    status = manager.status()
    assert status is not None
    assert status["record"] is not None  # 깨진 줄 뒤의 레코드를 정상 수신했다
