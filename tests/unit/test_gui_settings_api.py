"""단위 테스트 — 설정 엔드포인트 (v0.9 §4.8 · §4.9 · §4.11).

두 가지를 지킨다: **API 키를 다루지 않는다**(§4.9)와 **한 파일을 두 어댑터가 쓰므로 자기 섹션만
교체한다**(§4.8). 후자는 실제 파일을 써서 확인한다 — 「상대 섹션이 살아남는가」는 파일 내용에만
드러난다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from corpbrain.core.consent import is_cloud_consent_granted
from corpbrain.core.pii import PiiType
from corpbrain.gui.api import SESSION_COOKIE, GuiApp

PORT = 8765
AUTH: ClassVar = {
    "Host": f"127.0.0.1:{PORT}",
    "Cookie": f"{SESSION_COOKIE}=sess",
    "Origin": f"http://127.0.0.1:{PORT}",
}


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def app(tmp_path: Path, config_path: Path) -> GuiApp:
    return GuiApp(
        out_dir=tmp_path / "wiki",
        token="tok",
        port=PORT,
        session_token="sess",
        config_path=config_path,
    )


def _post(app: GuiApp, payload: dict[str, object]):
    return app.handle("POST", "/api/settings", AUTH, json.dumps(payload).encode())


def test_pii_types_are_the_core_seven(app: GuiApp) -> None:
    """§4.11 — 목업은 6종이었고 라벨·플레이스홀더도 어긋나 있었다. 코어 값을 그대로 낸다."""
    body = app.handle("GET", "/api/settings", AUTH).json()

    assert len(body["pii_types"]) == 7
    assert {kind["name"] for kind in body["pii_types"]} == {str(k) for k in PiiType}
    phone = next(k for k in body["pii_types"] if k["name"] == "PHONE")
    assert phone["label"] == "전화번호"  # 목업의 「휴대전화번호」가 아니다
    assert phone["placeholder"] == "[REDACTED_PHONE]"  # `[PII: …:001]` 형식이 아니다


def test_api_key_value_is_never_exposed(app: GuiApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """§4.9 — 키는 환경변수로만 읽고 GUI는 값을 다루지 않는다."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-비밀값")

    raw = app.handle("GET", "/api/settings", AUTH).body

    assert b"sk-ant" not in raw


def test_consent_toggle_round_trips(app: GuiApp, config_path: Path) -> None:
    assert _post(app, {"cloud_consent": True}).status == 200
    assert is_cloud_consent_granted(config_path=config_path) is True

    assert _post(app, {"cloud_consent": False}).status == 200
    assert is_cloud_consent_granted(config_path=config_path) is False


def test_gui_section_write_preserves_the_consent_section(
    app: GuiApp, config_path: Path
) -> None:
    """§4.8 — 나중에 쓴 쪽이 상대 섹션을 날리면 동의가 조용히 철회된다."""
    _post(app, {"cloud_consent": True})

    _post(app, {"gui": {"last_folder": "/원문", "engine": "cloud"}})

    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["gui"] == {"last_folder": "/원문", "engine": "cloud"}
    assert is_cloud_consent_granted(config_path=config_path) is True


def test_gui_section_updates_merge_instead_of_replacing(
    app: GuiApp, config_path: Path
) -> None:
    _post(app, {"gui": {"last_folder": "/원문"}})
    _post(app, {"gui": {"engine": "cloud"}})

    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["gui"] == {"last_folder": "/원문", "engine": "cloud"}


def test_consent_write_preserves_the_gui_section(app: GuiApp, config_path: Path) -> None:
    """반대 방향도 성립한다 — 두 어댑터가 한 파일을 쓴다는 것이 이 절의 전제다."""
    _post(app, {"gui": {"last_folder": "/원문"}})

    _post(app, {"cloud_consent": True})

    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["gui"] == {"last_folder": "/원문"}
    assert is_cloud_consent_granted(config_path=config_path) is True


def test_non_object_gui_payload_is_400(app: GuiApp) -> None:
    assert _post(app, {"gui": "문자열"}).status == 400


def test_settings_write_requires_origin(app: GuiApp) -> None:
    """상태를 바꾸는 메서드에서 `Origin`은 필수다 (§4.2)."""
    headers = {key: value for key, value in AUTH.items() if key != "Origin"}

    response = app.handle("POST", "/api/settings", headers, b"{}")

    assert response.status == 403
