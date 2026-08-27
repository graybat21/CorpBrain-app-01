"""단위 테스트 — 토큰·쿠키 교환과 `Origin`/`Host` 검증 (v0.9 §4.2 · DoD 2).

§3 항목2가 요구하는 **5종 + 1**을 양방향으로 고정한다: 토큰 없음 / 잘못된 토큰 /
잘못된 `Origin` / 잘못된 `Host` / `Origin` 없는 POST 가 401·403이고, **`Origin` 없는 GET은
통과**한다. 마지막 하나가 없으면 「전부 403」 구현이 테스트를 통과하면서 기동 시 여는 첫
화면을 막는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain.gui.api import SESSION_COOKIE, GuiApp, Request, Response

PORT = 8765
BOOTSTRAP = "boot-token"
SESSION = "session-token"
ORIGIN = f"http://127.0.0.1:{PORT}"
HOST = f"127.0.0.1:{PORT}"


@pytest.fixture
def app(tmp_path: Path) -> GuiApp:
    return GuiApp(
        out_dir=tmp_path / "wiki", token=BOOTSTRAP, port=PORT, session_token=SESSION
    )


def _headers(**overrides: str | None) -> dict[str, str]:
    base: dict[str, str | None] = {"Host": HOST, "Cookie": f"{SESSION_COOKIE}={SESSION}"}
    base.update(overrides)
    return {key: value for key, value in base.items() if value is not None}


def _set_cookie(response: Response) -> str | None:
    for name, value in response.headers:
        if name == "Set-Cookie":
            return value
    return None


# --- 401: 자격 (§4.2) ------------------------------------------------------------


def test_request_without_any_token_is_401(app: GuiApp) -> None:
    response = app.handle("GET", "/api/dashboard", _headers(Cookie=None))
    assert response.status == 401


def test_request_with_a_wrong_token_is_401(app: GuiApp) -> None:
    wrong_cookie = app.handle(
        "GET", "/api/dashboard", _headers(Cookie=f"{SESSION_COOKIE}=nope")
    )
    wrong_query = app.handle(
        "GET", "/api/dashboard?token=nope", _headers(Cookie=None)
    )
    assert (wrong_cookie.status, wrong_query.status) == (401, 401)


def test_refusals_do_not_explain_themselves(app: GuiApp) -> None:
    """이유를 자세히 적지 않는다 (§5) — 토큰 값이 새어 나가지 않는다."""
    body = app.handle("GET", "/api/dashboard", _headers(Cookie=None)).json()
    assert body == {"error": "Unauthorized", "message": "인증되지 않은 요청입니다."}


# --- 403: `Host` · `Origin` (§4.2) ------------------------------------------------


def test_wrong_host_is_403(app: GuiApp) -> None:
    """DNS rebinding — 공격자 도메인이 127.0.0.1로 해석되게 만든 요청을 막는다."""
    response = app.handle("GET", "/api/dashboard", _headers(Host="evil.example.com"))
    assert response.status == 403


def test_missing_host_is_403_for_every_method(app: GuiApp) -> None:
    """`Host`는 **항상 필수**다 — 메서드로 가르지 않는다."""
    for method in ("GET", "POST"):
        assert app.handle(method, "/api/dashboard", _headers(Host=None)).status == 403


def test_wrong_origin_is_403(app: GuiApp) -> None:
    response = app.handle(
        "GET", "/api/dashboard", _headers(Origin="http://evil.example.com")
    )
    assert response.status == 403


def test_post_without_origin_is_403(app: GuiApp) -> None:
    """상태를 바꾸는 메서드에서는 `Origin` 부재가 곧 거절이다."""
    assert app.handle("POST", "/api/dashboard", _headers()).status == 403


def test_get_without_origin_passes(app: GuiApp) -> None:
    """브라우저는 최상위 GET 내비게이션에 `Origin`을 붙이지 않는다.

    기동 시 여는 `http://127.0.0.1:<port>/?token=…`이 정확히 그 요청이므로, 「없음 = 403」
    으로 구현하면 서버가 **자기 자신에게 403**을 낸다.
    """
    assert app.handle("GET", "/api/dashboard", _headers()).status == 200


def test_get_with_matching_origin_passes(app: GuiApp) -> None:
    assert app.handle("GET", "/api/dashboard", _headers(Origin=ORIGIN)).status == 200


# --- 부트스트랩 → 세션 쿠키 교환 (§4.2 · T6) ---------------------------------------


def test_bootstrap_query_token_is_exchanged_for_a_session_cookie(app: GuiApp) -> None:
    response = app.handle(
        "GET", f"/api/dashboard?token={BOOTSTRAP}", _headers(Cookie=None)
    )
    assert response.status == 200
    cookie = _set_cookie(response)
    assert cookie is not None
    assert cookie.startswith(f"{SESSION_COOKIE}={SESSION};")
    # `EventSource`는 커스텀 헤더를 붙일 수 없어 쿠키라야 인증 경로가 하나로 유지된다.
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    # `http://127.0.0.1`이므로 `Secure`를 붙이면 쿠키가 아예 저장되지 않는다.
    assert "Secure" not in cookie


def test_session_cookie_value_is_not_the_bootstrap_token(app: GuiApp) -> None:
    """URL·히스토리·리퍼러에 남는 값과 쿠키 값이 같지 않다."""
    assert app.session_token != app.token


def test_cookie_requests_do_not_reissue_the_cookie(app: GuiApp) -> None:
    """이미 교환한 뒤에는 `Set-Cookie`를 매번 다시 보내지 않는다."""
    assert _set_cookie(app.handle("GET", "/api/dashboard", _headers())) is None


def test_refused_bootstrap_does_not_leak_a_cookie(app: GuiApp) -> None:
    """`Host`가 틀린 요청은 쿼리 토큰이 맞아도 쿠키를 받지 못한다."""
    response = app.handle(
        "GET", f"/api/dashboard?token={BOOTSTRAP}", _headers(Host="evil.example.com")
    )
    assert response.status == 403
    assert _set_cookie(response) is None


def test_malformed_cookie_header_is_treated_as_no_credential(app: GuiApp) -> None:
    """깨진 쿠키는 '자격 없음'으로 수렴한다 — 파싱 실패가 500이 되지 않는다."""
    response = app.handle("GET", "/api/dashboard", _headers(Cookie="=;;;"))
    assert response.status == 401


# --- SSE 경로가 같은 검증을 쓴다 (§4.2 「인증 경로를 둘로 나누지 않는다」) --------------


def test_authorize_is_reusable_by_the_streaming_path(app: GuiApp) -> None:
    assert app.authorize("GET", "/api/events", _headers()) is None
    refusal = app.authorize("GET", "/api/events", _headers(Cookie=None))
    assert refusal is not None and refusal.status == 401


def test_authorization_runs_before_routing(app: GuiApp) -> None:
    """없는 경로라도 인증이 먼저다 — 401이 라우트 존재 여부를 알려 주지 않는다."""
    assert app.handle("GET", "/api/nope", _headers(Cookie=None)).status == 401
    assert app.handle("GET", "/api/nope", _headers()).status == 404


def test_request_headers_are_case_insensitive(app: GuiApp) -> None:
    lowered = {"host": HOST, "cookie": f"{SESSION_COOKIE}={SESSION}"}
    assert app.handle("GET", "/api/dashboard", lowered).status == 200
    assert isinstance(Request(method="GET", path="/"), Request)
