"""단위 테스트 — 요청 처리 순수 함수의 라우팅·상태코드·예외 매핑 (v0.9 §4.10.3 · §4.3.2).

소켓을 열지 않는다. `GuiApp`을 직접 만들어 `handle()`을 부르므로 단언이 결정적이다 —
`report.py`의 순수 빌더를 단위테스트가 정확 문자열로 단언하는 것과 같은 잣대다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from corpbrain.core.errors import (
    CorpBrainError,
    GpuGateError,
    PreconditionError,
    TokenBudgetExceededError,
)
from corpbrain.gui.api import SESSION_COOKIE, GuiApp, Response, response_for_exception

PORT = 8765

#: 인증을 통과하는 최소 헤더. 인증 자체는 `test_gui_auth.py`가 단언한다 — 이 파일은
#: 라우팅·상태코드·예외 매핑만 본다.
AUTH = {
    "Host": f"127.0.0.1:{PORT}",
    "Cookie": f"{SESSION_COOKIE}=sess",
    "Origin": f"http://127.0.0.1:{PORT}",
}


@pytest.fixture
def app(tmp_path: Path) -> GuiApp:
    return GuiApp(
        out_dir=tmp_path / "wiki", token="tok", port=PORT, session_token="sess"
    )


def test_unknown_path_is_404(app: GuiApp) -> None:
    response = app.handle("GET", "/api/nope", AUTH)
    assert response.status == 404
    assert response.json()["error"] == "NotFound"


def test_unknown_method_on_known_path_is_405_with_allow(app: GuiApp) -> None:
    response = app.handle("POST", "/api/dashboard", AUTH)
    assert response.status == 405
    assert response.json()["error"] == "MethodNotAllowed"
    assert dict(response.headers)["Allow"] == "GET"


def test_query_string_is_split_off_before_routing(app: GuiApp) -> None:
    """`?token=…`이 붙어도 같은 라우트로 간다 — 부트스트랩 URL이 그 모양이다."""
    assert app.handle("GET", "/api/dashboard?token=tok&x=1", AUTH).status == 200


def test_method_is_case_insensitive(app: GuiApp) -> None:
    assert app.handle("get", "/api/dashboard", AUTH).status == 200


# --- 예외 매핑 (§4.3.2) ----------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        CorpBrainError("기반 클래스 자체"),
        PreconditionError("먼저 스캔하세요"),
        GpuGateError("GPU가 없습니다"),
        TokenBudgetExceededError("예산 초과"),
    ],
)
def test_corpbrain_errors_are_domain_responses(exc: CorpBrainError) -> None:
    """열거가 아니라 기반 클래스로 가른다 — 계층에 새 예외가 늘어도 규칙이 따라온다."""
    response = response_for_exception(exc)
    assert response.status == 200
    body = response.json()
    assert body["error"] == type(exc).__name__
    assert body["message"] == str(exc)


def test_sqlite_error_is_a_domain_response() -> None:
    """손상·스키마 불일치는 환경의 상태다 — 화면이 다음에 할 일을 안내해야 한다."""
    response = response_for_exception(sqlite3.DatabaseError("file is not a database"))
    assert response.status == 200
    assert response.json()["error"] == "DatabaseError"


def test_sqlite_programming_error_is_a_bug_not_a_domain_state() -> None:
    """스레드를 넘겨 커넥션을 쓴 버그가 200으로 숨으면 사용자가 멀쩡한 DB를 지운다."""
    response = response_for_exception(
        sqlite3.ProgrammingError("SQLite objects created in a thread can only be used…")
    )
    assert response.status == 500


def test_unknown_exception_is_500() -> None:
    """5xx가 오직 버그일 때만 나므로 로그의 500이 그대로 버그 신호가 된다."""
    assert response_for_exception(ValueError("이건 버그다")).status == 500


def test_handler_exceptions_are_mapped_not_leaked(app: GuiApp, monkeypatch) -> None:
    """라우트 핸들러가 올린 예외도 같은 규칙을 탄다 — 핸들러마다 try를 두지 않는다."""

    def _boom(_request: object) -> Response:
        raise PreconditionError("Ollama가 응답하지 않습니다")

    monkeypatch.setattr(app, "_routes", lambda: {"/api/dashboard": {"GET": _boom}})
    response = app.handle("GET", "/api/dashboard", AUTH)
    assert response.status == 200
    assert response.json()["error"] == "PreconditionError"
