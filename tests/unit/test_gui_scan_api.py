"""단위 테스트 — 스캔 엔드포인트의 상태 판정과 상태코드 (v0.9 §4.3.4 · §4.4 · §4.10.3).

**소켓도 스레드도 열지 않는다.** 「진행 중」이 전제인 판정(409)은 상태를 주입해 `handle()`을
부르는 것으로 재현한다 — 스펙 §3 항목5가 「이것은 스레드 경합이 아니라 상태 판정이므로 실제
동시 실행이 필요 없다」고 정한 그대로다. `sleep`·`threading.Event`·`Barrier`를 쓰지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import ScanResult
from corpbrain.gui.api import SESSION_COOKIE, GuiApp
from corpbrain.gui.scan import ScanController, ScanInProgressError, config_from_payload

PORT = 8765
AUTH = {
    "Host": f"127.0.0.1:{PORT}",
    "Cookie": f"{SESSION_COOKIE}=sess",
    "Origin": f"http://127.0.0.1:{PORT}",
}


class _StubController(ScanController):
    """상태를 **주입**하는 컨트롤러 — 진짜 스캔을 돌리지 않는다.

    `ScanController`를 상속하는 이유는 `GuiApp`이 기대하는 계약(속성 5개 + `measure`·
    `start`·`cancel`)이 그대로 유지되는지를 이 테스트가 함께 지키기 때문이다. 가짜 객체를
    새로 짜면 계약이 갈려도 테스트가 통과한다.
    """

    def __init__(self, *, running: bool = False) -> None:
        super().__init__(events=_Events(running))
        self.started: list[ScanConfig] = []
        self.cancelled = False

    def measure(self, config: ScanConfig) -> object:  # type: ignore[override]
        raise AssertionError("이 테스트는 계량을 부르지 않는다")

    def start(self, config: ScanConfig) -> None:
        if self.running:
            raise ScanInProgressError("이미 스캔이 진행 중입니다.")
        self.started.append(config)

    def cancel(self) -> None:
        self.cancelled = True


class _Events:
    """`EventStream` 중 컨트롤러가 읽는 부분만 흉내 낸다."""

    def __init__(self, running: bool) -> None:
        self.running = running

    def begin(self) -> None: ...

    def end(self) -> None: ...

    def publish(self, event: object) -> None: ...


def _app(tmp_path: Path, controller: ScanController) -> GuiApp:
    return GuiApp(
        out_dir=tmp_path / "wiki",
        token="tok",
        port=PORT,
        session_token="sess",
        events=controller.events,  # type: ignore[arg-type]
        scan=controller,
    )


def _post(app: GuiApp, path: str, payload: dict[str, object]) -> object:
    return app.handle("POST", path, AUTH, json.dumps(payload).encode("utf-8"))


def test_second_scan_while_running_is_conflict_409(tmp_path: Path) -> None:
    """DoD 5 — 진행 중에 들어온 새 스캔 요청은 **409**다."""
    controller = _StubController(running=True)
    app = _app(tmp_path, controller)

    response = _post(app, "/api/scan", {"folder": str(tmp_path)})

    assert response.status == 409
    assert response.json()["error"] == "ScanInProgress"


def test_conflict_does_not_disturb_the_running_scan(tmp_path: Path) -> None:
    """DoD 5 — 거절된 요청이 진행 중이던 스캔을 건드리지 않는다."""
    controller = _StubController(running=True)
    app = _app(tmp_path, controller)

    _post(app, "/api/scan", {"folder": str(tmp_path)})

    assert controller.started == []
    assert controller.cancelled is False
    assert controller.running is True


def test_scan_starts_when_idle(tmp_path: Path) -> None:
    controller = _StubController(running=False)
    app = _app(tmp_path, controller)

    response = _post(app, "/api/scan", {"folder": str(tmp_path)})

    assert response.status == 200
    assert [config.folder for config in controller.started] == [tmp_path]


def test_cancel_is_accepted_even_when_idle(tmp_path: Path) -> None:
    """취소는 **요청**이라 진행 중이 아니어도 오류가 아니다.

    마지막 문서가 끝나는 순간 누른 취소를 오류로 만들면, 사용자가 아무것도 잘못하지 않았는데
    오류를 본다.
    """
    controller = _StubController(running=False)
    app = _app(tmp_path, controller)

    response = _post(app, "/api/scan/cancel", {})

    assert response.status == 200
    assert controller.cancelled is True


def test_status_reports_running_and_last_result(tmp_path: Path) -> None:
    controller = _StubController(running=True)
    controller._result = ScanResult(out_dir=tmp_path / "wiki", cancelled=True)
    app = _app(tmp_path, controller)

    body = app.handle("GET", "/api/scan", AUTH).json()

    assert body["running"] is True
    assert body["result"]["cancelled"] is True
    # 종료 요약 줄의 **어휘**가 CLI와 갈리지 않는다 (§4.6.1).
    assert "  - 그래프 미반영 — 다시 스캔하면 반영됩니다." in body["result"]["summary_lines"]


def test_worker_failure_is_reported_as_domain_state(tmp_path: Path) -> None:
    """워커 스레드에서 죽은 코어 예외도 §4.3.2의 매핑 규칙을 그대로 받는다."""
    controller = _StubController(running=False)
    controller._failure = PreconditionError("Ollama 데몬이 응답하지 않습니다.")
    app = _app(tmp_path, controller)

    body = app.handle("GET", "/api/scan", AUTH).json()

    assert body["failure"]["error"] == "PreconditionError"
    assert "Ollama" in body["failure"]["message"]


def test_malformed_body_is_400_not_500(tmp_path: Path) -> None:
    """요청의 모양 문제는 프로토콜 층이다 — 「로그의 500 = 버그 신호」를 지킨다."""
    controller = _StubController(running=False)
    app = _app(tmp_path, controller)

    response = app.handle("POST", "/api/scan", AUTH, b"not json")

    assert response.status == 400
    assert response.json()["error"] == "BadRequest"


def test_missing_folder_is_400(tmp_path: Path) -> None:
    controller = _StubController(running=False)
    app = _app(tmp_path, controller)

    assert _post(app, "/api/scan", {}).status == 400


class TestConfigFromPayload:
    """§4.3.3 — GUI는 **검증하지 않는다.** 타입만 옮기고 값은 그대로 코어로 간다."""

    def test_all_scan_config_fields_are_reachable(self, tmp_path: Path) -> None:
        payload = {
            "folder": str(tmp_path),
            "out_dir": str(tmp_path / "out"),
            "model": "m", "embed_model": "e", "ollama_url": "http://127.0.0.1:1",
            "engine": "cloud", "cloud_model": "c",
            "max_files": 7, "max_chars": 8, "max_file_size": 9,
            "max_total_tokens": 10, "related_top_k": 11,
            "force": True, "force_gates": True, "similarity_threshold": 0.25,
        }
        config = config_from_payload(payload, default_out=tmp_path / "default")
        # 「CLI로 돌아가야만 되는 일」을 남기지 않는다 — 15필드가 전부 닿는다.
        assert config.max_files == 7
        assert config.force is True
        assert config.similarity_threshold == 0.25
        assert config.engine == "cloud"
        assert config.out_dir == tmp_path / "out"

    def test_invalid_values_are_passed_through_untouched(self, tmp_path: Path) -> None:
        """음수 상한을 어댑터가 막지 않는다 — 규칙이 한 곳(코어)에만 있어야 한다."""
        config = config_from_payload(
            {"folder": str(tmp_path), "max_files": -5}, default_out=tmp_path
        )
        assert config.max_files == -5

    def test_out_dir_falls_back_to_server_default(self, tmp_path: Path) -> None:
        config = config_from_payload(
            {"folder": str(tmp_path)}, default_out=tmp_path / "wiki"
        )
        assert config.out_dir == tmp_path / "wiki"


class TestMeasurementReuse:
    """§4.3.4 — 계량 재사용은 **같은 `ScanConfig`일 때로 한정**한다."""

    def test_same_config_reuses_the_held_measurement(self, tmp_path: Path) -> None:
        controller = ScanController(events=_Events(False))  # type: ignore[arg-type]
        config = ScanConfig(folder=tmp_path, out_dir=tmp_path / "wiki")
        held = controller.measure(config)

        assert controller._reusable(config) is held

    def test_changed_limit_discards_the_stale_gate_verdict(self, tmp_path: Path) -> None:
        """한도를 올렸는데 낡은 판정에 계속 막히는 상황을 막는다.

        `ScanPlan.gate`는 계량 시점 임계값으로 이미 내려진 판정이고 `run_scan`의 방어는
        「파일 수가 같은가」 하나뿐이라, 파일 수가 그대로면 낡은 판정이 그대로 쓰인다.
        """
        controller = ScanController(events=_Events(False))  # type: ignore[arg-type]
        config = ScanConfig(folder=tmp_path, out_dir=tmp_path / "wiki")
        controller.measure(config)

        raised = ScanConfig(
            folder=tmp_path, out_dir=tmp_path / "wiki", max_total_tokens=500_000
        )
        assert controller._reusable(raised) is None

    def test_changed_engine_discards_it_too(self, tmp_path: Path) -> None:
        """local → cloud 는 `gate.gpu_enforced`가 낡은 채 따라온다."""
        controller = ScanController(events=_Events(False))  # type: ignore[arg-type]
        config = ScanConfig(folder=tmp_path, out_dir=tmp_path / "wiki")
        controller.measure(config)

        assert controller._reusable(
            ScanConfig(folder=tmp_path, out_dir=tmp_path / "wiki", engine="cloud")
        ) is None
