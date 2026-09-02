"""GUI 어댑터 테스트 — 서버 골격·바인딩·포트 선택·토큰 (v0.9 스펙 §3 항목1 · §4.1 · §4.2).

`tests/test_cli.py`의 관용구를 계승한다 — 파싱과 실행을 분리해 검증하고, 코어는
monkeypatch로 가로채 "올바른 값이 넘어가는가"만 본다.

**서버 핸들러는 in-process로 직접 호출해 테스트한다** (스펙 §3 검증 방식).
`tests/security/test_network_invariant.py`의 `watch_sockets` 픽스처는 `socket.connect`를
무조건 `ConnectionRefusedError`로 만들므로, 그 픽스처 안에서 HTTP 클라이언트로 자기 서버에
접속하는 테스트는 원리적으로 불가능하다.
"""

from __future__ import annotations

import io
import socket
from pathlib import Path

import pytest

from corpbrain import cli
from corpbrain.gui import server as gui_server
from corpbrain.gui import workspaces as ws

# --- CLI 배선 (스펙 §4.1) ------------------------------------------------------


def test_gui_subcommand_defaults() -> None:
    """`corpbrain gui`만 입력하면 스펙 §4.1 기본값이 채워진다."""
    args = cli.build_parser().parse_args(["gui"])

    assert args.command == "gui"
    assert args.port == gui_server.DEFAULT_PORT
    assert args.no_browser is False


def test_gui_subcommand_flags() -> None:
    """`--port`·`--no-browser`가 파싱된다."""
    args = cli.build_parser().parse_args(["gui", "--port", "9100", "--no-browser"])

    assert args.port == 9100
    assert args.no_browser is True


def test_gui_command_does_not_fall_through_to_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main()`의 if 체인 끝은 무조건 `_run_scan`이다 — `gui` 분기가 그 앞에 있어야 한다.

    분기를 빠뜨리면 `corpbrain gui`가 조용히 스캔을 돌린다. 이 테스트가 그것을 막는다.
    """
    called: list[str] = []
    monkeypatch.setattr(cli, "_run_gui", lambda args: called.append("gui") or 0)
    monkeypatch.setattr(
        cli, "_run_scan", lambda args: called.append("scan") or 0
    )

    exit_code = cli.main(["gui", "--no-browser"])

    assert called == ["gui"]
    assert exit_code == 0


# --- 바인딩과 포트 (스펙 §3 항목1 · §5) ---------------------------------------


def test_server_binds_to_loopback_only() -> None:
    """서버는 `127.0.0.1`에만 바인딩한다 — 플래그로 바꿀 수 없다 (스펙 §4.1)."""
    state = gui_server.GuiState()
    httpd = gui_server.create_server(state, port=0)
    try:
        assert httpd.server_address[0] == gui_server.HOST == "127.0.0.1"
    finally:
        httpd.server_close()


def test_port_auto_selects_next_free() -> None:
    """요청한 포트가 사용 중이면 다음 빈 포트를 잡는다 — 기동 실패로 만들지 않는다 (§5)."""
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind((gui_server.HOST, 0))
    occupied.listen(1)
    taken_port = occupied.getsockname()[1]
    try:
        state = gui_server.GuiState()
        httpd = gui_server.create_server(state, port=taken_port)
        try:
            assert httpd.server_address[1] != taken_port
            assert taken_port < httpd.server_address[1] <= taken_port + gui_server.PORT_ATTEMPTS
        finally:
            httpd.server_close()
    finally:
        occupied.close()


def test_port_exhaustion_raises_precondition_error() -> None:
    """빈 포트를 하나도 못 잡으면 선행 조건 실패다 (CLI가 exit 1로 매핑한다).

    낮은 포트 번호로는 이 상황을 만들 수 없다 — Windows는 Unix와 달리 특권 포트 바인딩을
    막지 않아 포트 1도 그냥 열린다. 실제로 점유된 포트를 쓴다.
    """
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind((gui_server.HOST, 0))
    occupied.listen(1)
    taken_port = occupied.getsockname()[1]
    try:
        with pytest.raises(gui_server.PortUnavailableError):
            gui_server.create_server(gui_server.GuiState(), port=taken_port, attempts=0)
    finally:
        occupied.close()


# --- 토큰 (스펙 §4.6) ----------------------------------------------------------


def test_token_is_random_and_url_safe() -> None:
    """기동할 때마다 새 토큰을 만든다. URL에 그대로 실을 수 있어야 한다 (§4.6.1)."""
    a = gui_server.GuiState().token
    b = gui_server.GuiState().token

    assert a != b
    assert len(a) >= 32
    assert all(ch.isalnum() or ch in "-_" for ch in a)


def test_entry_url_carries_token() -> None:
    """기동 안내 URL은 첫 진입용 토큰을 쿼리스트링으로 싣는다 (§4.6.1)."""
    state = gui_server.GuiState()

    url = gui_server.entry_url(state, port=8765)

    assert url.startswith("http://127.0.0.1:8765/?")
    assert state.token in url


# --- W2 보호 계층 (스펙 §3 항목2 · §4.6) ---------------------------------------


@pytest.fixture
def state() -> gui_server.GuiState:
    return gui_server.GuiState()


def _auth(state: gui_server.GuiState, **over: object) -> gui_server.AuthFailure | None:
    """`authorize()` 호출을 짧게 쓴다 — 기본은 «정상 통과»이고 테스트가 한 축씩 흔든다."""
    kwargs: dict[str, object] = {
        "path": "/api/workspaces",
        "host": f"127.0.0.1:{gui_server.DEFAULT_PORT}",
        "header_token": state.token,
        "query_token": None,
        "state": state,
        "port": gui_server.DEFAULT_PORT,
    }
    kwargs.update(over)
    return gui_server.authorize(**kwargs)  # type: ignore[arg-type]


def test_baseline_request_is_authorized(state: gui_server.GuiState) -> None:
    """헤더 토큰과 Host가 모두 맞으면 통과한다 — 아래 테스트들의 기준선이다."""
    assert _auth(state) is None


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.com",
        "evil.example.com:8765",
        "127.0.0.1.evil.com:8765",
        "127.0.0.1:9999",
        None,
    ],
)
def test_foreign_host_header_is_rejected(state: gui_server.GuiState, host: str | None) -> None:
    """`Host`가 허용 목록 밖이면 403 — DNS rebinding을 막는다 (§4.6).

    포트가 다른 `127.0.0.1:9999`도 거절한다. rebinding 공격은 이름을 우리 것으로 맞추므로
    호스트 문자열만 보면 통과할 수 있다.
    """
    failure = _auth(state, host=host)

    assert failure is not None
    assert failure.status == 403


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765"])
def test_loopback_host_header_is_accepted(state: gui_server.GuiState, host: str) -> None:
    assert _auth(state, host=host) is None


def test_api_without_token_is_unauthorized(state: gui_server.GuiState) -> None:
    """토큰 없는 `/api/*` 요청은 401 (스펙 §3 항목2)."""
    failure = _auth(state, header_token=None)

    assert failure is not None
    assert failure.status == 401


def test_api_with_wrong_token_is_unauthorized(state: gui_server.GuiState) -> None:
    failure = _auth(state, header_token="not-the-token")

    assert failure is not None
    assert failure.status == 401


def test_api_does_not_accept_the_token_from_the_query_string(
    state: gui_server.GuiState,
) -> None:
    """쿼리스트링 토큰은 **첫 진입에서만** 유효하다 (§4.6.1).

    API가 쿼리 토큰을 받아 주면 토큰이 서버 접근 로그와 `Referer` 헤더에 계속 남는다.
    """
    failure = _auth(state, header_token=None, query_token=state.token)

    assert failure is not None
    assert failure.status == 401


def test_shell_and_static_do_not_require_a_token(state: gui_server.GuiState) -> None:
    """페이지 껍데기와 정적 자산은 토큰 없이 받는다.

    브라우저는 `<link>`·`<script>` 요청에 커스텀 헤더를 붙일 수 없다. 이 경로들은 데이터를
    담지 않으며, 데이터를 주는 `/api/*`가 토큰으로 막혀 있으므로 안전하다.
    """
    assert _auth(state, path="/", header_token=None) is None
    assert _auth(state, path="/static/app.js", header_token=None) is None


def test_host_is_checked_even_for_the_shell(state: gui_server.GuiState) -> None:
    """토큰이 면제되는 경로에서도 `Host` 검증은 살아 있다."""
    failure = _auth(state, path="/", header_token=None, host="evil.example.com")

    assert failure is not None
    assert failure.status == 403


# --- 핸들러 배선 (in-process 호출) ---------------------------------------------


def test_handler_returns_401_for_api_without_token(state: gui_server.GuiState) -> None:
    """`authorize()`의 판정이 실제 응답으로 이어지는지 본다.

    HTTP 클라이언트로 자기 서버에 접속하지 않고 핸들러를 in-process로 돌린다 (스펙 §3).
    """
    response = _make_request(state, "GET", "/api/workspaces")

    assert response.startswith((b"HTTP/1.0 401", b"HTTP/1.1 401"))


def test_handler_returns_403_for_foreign_host(state: gui_server.GuiState) -> None:
    response = _make_request(state, "GET", "/", host="evil.example.com")

    assert b" 403 " in response.split(b"\r\n")[0]


def test_handler_serves_the_shell(state: gui_server.GuiState) -> None:
    response = _make_request(state, "GET", "/")

    assert b" 200 " in response.split(b"\r\n")[0]
    assert b"text/html" in response


def _make_request(
    state: gui_server.GuiState,
    method: str,
    path: str,
    *,
    host: str | None = f"127.0.0.1:{gui_server.DEFAULT_PORT}",
    token: str | None = None,
) -> bytes:
    """핸들러를 소켓 없이 한 번 돌리고 응답 바이트를 돌려준다."""
    lines = [f"{method} {path} HTTP/1.1"]
    if host is not None:
        lines.append(f"Host: {host}")
    if token is not None:
        lines.append(f"{gui_server.TOKEN_HEADER}: {token}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")

    conn = _FakeConn(raw)
    handler_cls = gui_server.make_handler(state, port=gui_server.DEFAULT_PORT)
    handler_cls(conn, ("127.0.0.1", 51234), _FakeServer())
    return bytes(conn.sent)


class _FakeConn:
    """`socketserver.StreamRequestHandler`가 기대하는 최소 소켓 흉내."""

    def __init__(self, raw: bytes) -> None:
        self._rfile = io.BytesIO(raw)
        self.sent = bytearray()

    def makefile(self, mode: str = "rb", bufsize: int = -1) -> io.BytesIO:
        return self._rfile

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def settimeout(self, _timeout: float | None) -> None:
        return

    def shutdown(self, _how: int) -> None:
        return

    def close(self) -> None:
        return


class _FakeServer:
    server_address = ("127.0.0.1", gui_server.DEFAULT_PORT)


# --- W5 스캔 API (§4.7 · §5) ----------------------------------------------------


@pytest.fixture
def wired(tmp_path: Path) -> tuple[gui_server.GuiState, str]:
    """레지스트리를 tmp_path에 두고 워크스페이스 하나를 등록한 상태."""
    registry = tmp_path / "workspaces.json"
    (tmp_path / "docs").mkdir()
    entry = ws.add(registry, name="테스트", source_dir=tmp_path / "docs", out_dir=tmp_path / "wiki")
    state = gui_server.GuiState(registry_path=registry)
    return state, entry.id


def _route(state, method: str, path: str, body=None, query=None):
    return gui_server.route(
        method=method, path=path, query=query or {}, body=body or {}, state=state
    )


def test_scan_status_before_any_run(wired) -> None:
    state, _ = wired

    status, payload = _route(state, "GET", "/api/scan")

    assert status == 200
    assert payload["running"] is False


def test_scan_start_rejects_unknown_workspace(wired) -> None:
    state, _ = wired

    status, payload = _route(state, "POST", "/api/scan", {"workspace_id": "없음"})

    assert status == 404
    assert "워크스페이스" in payload["error"]


def test_scan_start_rejects_unknown_option(wired) -> None:
    """오타 난 옵션이 조용히 기본값으로 돌지 않는다 — 자식을 띄우기 전에 거른다."""
    state, workspace_id = wired

    status, payload = _route(
        state, "POST", "/api/scan", {"workspace_id": workspace_id, "options": {"modell": "오타"}}
    )

    assert status == 400
    assert "알 수 없는" in payload["error"]


def test_scan_start_is_accepted_and_saves_options(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, workspace_id = wired
    started: list[dict] = []
    monkeypatch.setattr(
        state.jobs, "start", lambda **kw: started.append(kw)
    )

    status, payload = _route(
        state,
        "POST",
        "/api/scan",
        {"workspace_id": workspace_id, "options": {"model": "m", "force": True}},
    )

    assert status == 202
    assert payload["started"] is True
    assert started[0]["payload"]["model"] == "m"
    # `force`는 저장되지 않는다 (grill T6) — 하지만 이번 실행에는 전달된다.
    assert started[0]["payload"]["force"] is True
    assert ws.load(state.registry_path)[0].last_options == {"model": "m"}


def test_scan_start_while_running_is_409(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    """동시 스캔은 전체에서 1개만 (§5)."""
    state, workspace_id = wired

    def busy(**_kw):
        raise gui_server.scanjob.ScanAlreadyRunningError("이미 스캔이 실행 중입니다.")

    monkeypatch.setattr(state.jobs, "start", busy)

    status, payload = _route(state, "POST", "/api/scan", {"workspace_id": workspace_id})

    assert status == 409
    assert "실행 중" in payload["error"]


def test_scan_stop_reports_whether_it_stopped(wired) -> None:
    state, _ = wired

    status, payload = _route(state, "DELETE", "/api/scan")

    assert status == 200
    assert payload["stopped"] is False


def test_unknown_api_path_is_404(wired) -> None:
    state, _ = wired

    status, _payload = _route(state, "GET", "/api/nope")

    assert status == 404


# --- W6 조회 API (§4.7 · §5) ----------------------------------------------------


def test_workspaces_crud_round_trip(wired) -> None:
    state, workspace_id = wired

    status, payload = _route(state, "GET", "/api/workspaces")
    assert status == 200
    assert [w["id"] for w in payload["workspaces"]] == [workspace_id]

    status, _ = _route(state, "DELETE", f"/api/workspaces/{workspace_id}")
    assert status == 200
    assert _route(state, "GET", "/api/workspaces")[1]["workspaces"] == []


def test_add_workspace_requires_all_three_fields(wired) -> None:
    state, _ = wired

    status, payload = _route(state, "POST", "/api/workspaces", {"name": "이름만"})

    assert status == 400
    assert "source_dir" in payload["error"]


def test_add_workspace_stores_absolute_paths(wired, tmp_path: Path) -> None:
    state, _ = wired

    status, payload = _route(
        state,
        "POST",
        "/api/workspaces",
        {"name": "새것", "source_dir": str(tmp_path / "docs"), "out_dir": str(tmp_path / "w2")},
    )

    assert status == 201
    assert Path(payload["source_dir"]).is_absolute()


def test_removing_an_unknown_workspace_is_404(wired) -> None:
    state, _ = wired

    status, _payload = _route(state, "DELETE", "/api/workspaces/없는id")

    assert status == 404


def test_fs_list_returns_subdirectories(wired, tmp_path: Path) -> None:
    state, _ = wired
    (tmp_path / "docs" / "인사").mkdir(parents=True)

    status, payload = _route(
        state, "GET", "/api/fs/list", query={"path": [str(tmp_path / "docs")]}
    )

    assert status == 200
    assert [e["name"] for e in payload["entries"]] == ["인사"]


def test_fs_list_on_a_file_is_400(wired, tmp_path: Path) -> None:
    state, _ = wired
    target = tmp_path / "메모.txt"
    target.write_text("파일", encoding="utf-8")

    status, _payload = _route(state, "GET", "/api/fs/list", query={"path": [str(target)]})

    assert status == 400


def test_dashboard_on_an_empty_workspace(wired) -> None:
    """아직 스캔한 적이 없어도 정상 응답이다 — 비어 있음은 오류가 아니다."""
    state, workspace_id = wired

    status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/dashboard")

    assert status == 200
    assert payload == {"wiki_count": 0, "last_run": None, "graph": None}


def test_scoped_endpoint_for_unknown_workspace_is_404(wired) -> None:
    state, _ = wired

    status, _payload = _route(state, "GET", "/api/workspaces/없는id/dashboard")

    assert status == 404


def test_search_is_blocked_while_a_scan_runs(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    """스캔 중 검색은 409 (스펙 §3 항목4 · §5).

    벡터 인덱스는 스캔이 쓰기 락을 실행 내내 점유하는데 `search`는 조회인데도 인덱스를
    쓰기로 열어 구조적으로 반드시 실패한다.
    """
    state, workspace_id = wired
    monkeypatch.setattr(type(state.jobs), "running", property(lambda self: True))

    status, payload = _route(
        state, "GET", f"/api/workspaces/{workspace_id}/search", query={"q": ["휴가"]}
    )

    assert status == 409
    assert "스캔" in payload["error"]


def test_search_without_a_query_is_400(wired) -> None:
    state, workspace_id = wired

    status, _payload = _route(
        state, "GET", f"/api/workspaces/{workspace_id}/search", query={"q": ["   "]}
    )

    assert status == 400


def test_search_precondition_failure_becomes_400_not_a_traceback(wired) -> None:
    """인덱스가 없으면 코어가 선행 조건 실패를 올린다 — 트레이스백으로 새지 않는다."""
    state, workspace_id = wired

    status, payload = _route(
        state, "GET", f"/api/workspaces/{workspace_id}/search", query={"q": ["휴가"]}
    )

    assert status == 400
    assert payload["error"]


def test_sqlite_errors_become_503_not_500(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스캔이 저장소를 잡고 있을 때의 충돌을 안내로 바꾼다 (§5).

    현재 코어도 CLI도 `sqlite3.Error`를 잡지 않아 웹에서는 500이 된다.
    """
    import sqlite3

    state, workspace_id = wired

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(gui_server, "_dashboard", boom)

    status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/dashboard")

    assert status == 503
    assert "잠시 후" in payload["error"]


def test_graph_payload_is_empty_without_a_graph_db(wired) -> None:
    """그래프 DB 부재는 정상 응답이다 — 코어의 «부재는 exit 0» 방침을 따른다 (§5)."""
    state, workspace_id = wired

    status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/graph")

    assert status == 200
    assert payload == {"nodes": [], "edges": []}


def test_cloud_settings_always_carry_the_three_notices(wired) -> None:
    """동의 다이얼로그의 고지 3줄은 API가 소유한다 (§4.10).

    코어의 `grant_cloud_consent()`는 아무 고지도 하지 않고 파일만 쓴다. 화면이 문구를
    스스로 지어내면 CLI와 갈린다.
    """
    state, _ = wired

    status, payload = _route(state, "GET", "/api/settings/cloud")

    assert status == 200
    assert len(payload["notices"]) == 3
    assert any("외부" in line for line in payload["notices"])
    assert any("마스킹" in line for line in payload["notices"])
    assert any("저장되지 않" in line for line in payload["notices"])


def test_cloud_consent_can_be_granted_and_revoked(
    wired, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state, _ = wired
    config = tmp_path / "config.json"
    monkeypatch.setattr(gui_server.core, "grant_cloud_consent", lambda: config.touch())
    monkeypatch.setattr(gui_server.core, "revoke_cloud_consent", lambda: config.unlink())
    monkeypatch.setattr(gui_server.core, "is_cloud_consent_granted", lambda: config.exists())

    assert _route(state, "PUT", "/api/settings/cloud", {"granted": True})[1]["granted"] is True
    assert _route(state, "PUT", "/api/settings/cloud", {"granted": False})[1]["granted"] is False


# --- W7 위키 조회·편집 (§3 항목9 · §4.9) ----------------------------------------


WIKI_BODY = (
    '---\nsource_path: "C:/docs/a.md"\n---\n\n# 제목\n\n## 한 줄 요약\n요약이다\n\n'
    "<!-- corpbrain:related:start -->\n## 관련 문서\n관련 문서 없음\n"
    "<!-- corpbrain:related:end -->\n"
)


@pytest.fixture
def with_wiki(wired, tmp_path: Path):
    state, workspace_id = wired
    out_dir = tmp_path / "wiki" / "인사"
    out_dir.mkdir(parents=True)
    (out_dir / "온보딩.md.md").write_text(WIKI_BODY, encoding="utf-8")
    return state, workspace_id, tmp_path / "wiki"


def test_wiki_tree_lists_generated_pages(with_wiki) -> None:
    state, workspace_id, _ = with_wiki

    status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/wiki")

    assert status == 200
    assert [e["path"] for e in payload["entries"]] == ["인사/온보딩.md.md"]


def test_wiki_page_returns_html_and_raw(with_wiki) -> None:
    state, workspace_id, _ = with_wiki

    status, payload = _route(
        state, "GET", f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md"
    )

    assert status == 200
    assert "<h1>제목</h1>" in payload["html"]
    assert payload["front_matter"]["source_path"] == "C:/docs/a.md"
    assert payload["raw"] == WIKI_BODY
    assert "corpbrain:related" not in payload["html"]


def test_wiki_page_outside_out_dir_is_rejected(with_wiki) -> None:
    """`..`로 출력 폴더 밖을 읽어 가는 통로를 막는다."""
    state, workspace_id, _ = with_wiki

    status, payload = _route(
        state, "GET", f"/api/workspaces/{workspace_id}/wiki/../../secret.txt"
    )

    assert status == 400
    assert "밖" in payload["error"]


def test_missing_wiki_page_is_404(with_wiki) -> None:
    state, workspace_id, _ = with_wiki

    status, _payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/wiki/없음.md.md")

    assert status == 404


def test_saving_a_wiki_writes_it(with_wiki) -> None:
    state, workspace_id, out_dir = with_wiki
    edited = WIKI_BODY.replace("요약이다", "사람이 고친 요약")

    status, payload = _route(
        state, "PUT", f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md", {"raw": edited}
    )

    assert status == 200
    assert payload["saved"] is True
    assert "사람이 고친 요약" in (out_dir / "인사/온보딩.md.md").read_text(encoding="utf-8")


def test_reveal_opens_the_folder_of_a_document(with_wiki, monkeypatch) -> None:
    """「바로가기」는 원본이 있는 폴더를 연다.

    브라우저는 `http://` 페이지에서 `file://` 링크를 조용히 무시하므로 서버가 대신 연다.
    """
    state, workspace_id, out_dir = with_wiki
    opened: list[Path] = []
    monkeypatch.setattr(gui_server, "_open_in_file_manager", opened.append)
    target = out_dir / "인사/온보딩.md.md"

    status, payload = _route(
        state, "POST", f"/api/workspaces/{workspace_id}/reveal", {"path": str(target)}
    )

    assert status == 200
    assert payload["selected"] is True
    assert opened == [target.resolve()]


def test_windows_explorer_gets_quotes_around_the_path_only(monkeypatch, tmp_path) -> None:
    r"""Windows 는 **명령줄 문자열**로 부르고 따옴표를 경로에만 두른다.

    인자 목록으로 주면 파이썬이 공백이 든 인자를 통째로 감싸
    `explorer "/select,D:\...\02. 가이드.docx"` 가 되는데, 탐색기는 그것을 위치로 읽지 못하고
    **오류 없이 기본 폴더(문서)를 연다** — 「폴더는 열렸는데 엉뚱한 폴더」가 된다.

    이 테스트는 어느 OS 에서 돌려도 Windows 분기를 지난다. 개발·CI 가 POSIX 여도 이 결함이
    다시 새지 않게 한다.
    """
    target = tmp_path / "하와이 관광 이관문서" / "02. 환경설정 및 배포 가이드.docx"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    launched: list[object] = []
    monkeypatch.setattr(gui_server.sys, "platform", "win32")
    monkeypatch.setattr(
        gui_server.subprocess, "Popen", lambda command, **_kwargs: launched.append(command)
    )

    gui_server._open_in_file_manager(target)

    assert launched == [f'explorer /select,"{target}"']


def test_reveal_refuses_a_path_outside_the_workspace(with_wiki, monkeypatch, tmp_path) -> None:
    """워크스페이스 밖은 열지 않는다 — 토큰을 쥔 쪽이 아무 폴더나 열 수 있으면 안 된다."""
    state, workspace_id, _out_dir = with_wiki
    opened: list[Path] = []
    monkeypatch.setattr(gui_server, "_open_in_file_manager", opened.append)
    outsider = tmp_path / "밖" / "비밀.txt"
    outsider.parent.mkdir(parents=True, exist_ok=True)
    outsider.write_text("x", encoding="utf-8")

    status, _payload = _route(
        state, "POST", f"/api/workspaces/{workspace_id}/reveal", {"path": str(outsider)}
    )

    assert status == 400
    assert opened == []


def test_reveal_refuses_a_relative_path(with_wiki, monkeypatch) -> None:
    """상대경로는 서버 프로세스의 cwd 기준으로 풀려 엉뚱한 폴더를 가리킨다 (§4.5)."""
    state, workspace_id, _out_dir = with_wiki
    monkeypatch.setattr(gui_server, "_open_in_file_manager", lambda _target: None)

    status, _payload = _route(
        state, "POST", f"/api/workspaces/{workspace_id}/reveal", {"path": "./inbox"}
    )

    assert status == 400


def test_saving_a_wiki_returns_the_rendered_page(with_wiki) -> None:
    """저장 응답이 **방금 쓴 내용의 렌더 결과**를 함께 준다.

    그러지 않으면 화면이 편집기를 닫고도 낡은 본문을 보여 주어, 새로고침하기 전까지
    저장이 안 된 것처럼 보인다. 화면이 스스로 렌더하게 하면 마크다운 렌더러가 두 벌이
    되고 그중 한쪽만 이스케이프를 빠뜨리는 순간 §4.9 의 XSS 방어가 무너지므로, 렌더는
    서버 한 곳에 두고 결과만 돌려준다.
    """
    state, workspace_id, _out_dir = with_wiki
    edited = WIKI_BODY.replace("요약이다", "사람이 고친 요약").replace("# 제목", "# 고친 제목")

    _status, payload = _route(
        state, "PUT", f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md", {"raw": edited}
    )

    assert "사람이 고친 요약" in payload["html"]
    assert payload["title"] == "고친 제목"   # 제목을 고쳤으면 목록·머리글도 따라온다
    assert payload["raw"] == edited


def test_saving_without_markers_is_400_and_does_not_write(with_wiki) -> None:
    """마커가 사라지면 다음 스캔이 블록을 하나 더 추가해 섹션이 중복된다 (스펙 §3 항목9)."""
    state, workspace_id, out_dir = with_wiki
    target = out_dir / "인사/온보딩.md.md"
    before = target.read_text(encoding="utf-8")

    status, payload = _route(
        state,
        "PUT",
        f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md",
        {"raw": "# 마커를 지웠다"},
    )

    assert status == 400
    assert "마커" in payload["error"]
    assert target.read_text(encoding="utf-8") == before  # 파일이 그대로다


def test_saving_while_a_scan_runs_is_409(
    with_wiki, monkeypatch: pytest.MonkeyPatch
) -> None:
    """패스3의 마커 블록 갱신과 충돌해 한쪽이 덮인다 (§5)."""
    state, workspace_id, _ = with_wiki
    monkeypatch.setattr(type(state.jobs), "running", property(lambda self: True))

    status, payload = _route(
        state, "PUT", f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md", {"raw": WIKI_BODY}
    )

    assert status == 409
    assert "스캔" in payload["error"]


def test_saving_an_empty_body_is_400(with_wiki) -> None:
    state, workspace_id, _ = with_wiki

    status, _payload = _route(
        state, "PUT", f"/api/workspaces/{workspace_id}/wiki/인사/온보딩.md.md", {"raw": "   "}
    )

    assert status == 400


# --- W8 정적 자산 (스펙 §3 항목6·7 · §4.8.1) ------------------------------------


EXPECTED_STATIC = {"index.html", "app.css", "app.js"}


def test_static_file_set_matches_expectation() -> None:
    """제공하는 정적 파일 목록이 기대 집합과 정확히 일치한다 (스펙 §3 항목7)."""
    actual = {p.name for p in gui_server.STATIC_DIR.iterdir() if p.is_file()}

    assert actual == EXPECTED_STATIC


#: 겉모습만 URL 인 문자열 — **가져오지 않는다.** `createElementNS` 에 넘기는 XML 네임스페이스
#: 식별자이며 브라우저가 이 주소로 요청을 보내는 일이 없다. 이름표일 뿐이라 CDN 금지의
#: 대상이 아니다. 목록을 늘릴 때는 «정말 요청이 나가지 않는가» 를 먼저 확인한다.
_NOT_A_RESOURCE = frozenset({"http://www.w3.org/2000/svg"})


def test_static_assets_reference_no_external_urls() -> None:
    """외부 URL 참조가 0건이다 — CDN 제로 원칙을 테스트로 고정한다 (스펙 §3 항목6).

    `127.0.0.1`·`localhost`는 표시용 텍스트로만 허용한다.
    """
    import re

    offenders: dict[str, list[str]] = {}
    for path in sorted(gui_server.STATIC_DIR.iterdir()):
        if not path.is_file():
            continue
        hits = [
            hit
            for hit in re.findall(r"https?://[^\s\"'()]+|//cdn[^\s\"'()]*", path.read_text("utf-8"))
            if "127.0.0.1" not in hit and "localhost" not in hit and hit not in _NOT_A_RESOURCE
        ]
        if hits:
            offenders[path.name] = hits

    assert offenders == {}, f"외부 URL 참조: {offenders}"


def test_static_assets_use_only_system_fonts() -> None:
    """웹폰트를 로드하지 않는다 (§4.8.1) — `@font-face`·`@import` 가 없어야 한다."""
    css = (gui_server.STATIC_DIR / "app.css").read_text("utf-8")

    assert "@font-face" not in css
    assert "@import" not in css


def test_shell_is_served_from_static(state: gui_server.GuiState) -> None:
    response = _make_request(state, "GET", "/")

    assert b" 200 " in response.split(b"\r\n")[0]
    assert b"text/html" in response
    assert b"CorpBrain" in response


def test_static_asset_is_served(state: gui_server.GuiState) -> None:
    response = _make_request(state, "GET", "/static/app.css")

    assert b" 200 " in response.split(b"\r\n")[0]
    assert b"text/css" in response


def test_static_traversal_is_rejected(state: gui_server.GuiState) -> None:
    """`..`로 정적 폴더 밖을 읽어 가는 통로를 막는다."""
    response = _make_request(state, "GET", "/static/../../../cli.py")

    assert b" 200 " not in response.split(b"\r\n")[0]


def test_hidden_attribute_is_honoured_by_the_stylesheet() -> None:
    """`hidden` 속성이 클래스 규칙에 지지 않는다.

    브라우저 기본 규칙은 `[hidden]{display:none}` 인데 클래스가 `display` 를 지정하면 그쪽이
    이긴다. 실제로 `.modal{display:flex}` 때문에 폴더 선택 모달이 첫 화면부터 떠 화면 전체를
    덮고 클릭을 전부 먹은 적이 있다. JS 는 `el.hidden` 으로만 여닫으므로 이 규칙이 계약이다.
    """
    import re

    raw = (gui_server.STATIC_DIR / "app.css").read_text("utf-8")
    # **주석을 먼저 걷어낸다.** 이 규칙을 설명하는 주석 안에 `[hidden]{display:none}` 이라는
    # 예시 문자열이 들어 있어, 그냥 찾으면 실제 규칙이 아니라 설명을 읽는다.
    css = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)

    match = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
    assert match, "app.css 에 [hidden] 규칙이 없다"
    body = match.group(1).replace(" ", "")
    assert "display:none!important" in body


def test_every_hidden_element_has_a_matching_class_rule_or_none() -> None:
    """`hidden` 으로 여닫는 요소가 `display` 를 지정하는 클래스를 쓰는지 확인한다.

    쓰더라도 위 `[hidden]` 규칙이 이기므로 문제는 없지만, 목록을 뽑아 두면 나중에 그 규칙을
    지웠을 때 무엇이 깨지는지 바로 보인다.
    """
    import re

    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")

    hidden_ids = re.findall(r'id="([A-Za-z][\w-]*)"[^>]*\shidden', html)
    assert {"picker", "toast", "editor", "paneGraph", "scanRun", "scanDone"} <= set(hidden_ids)


# --- 모델 해소 (설정 화면의 「모델 없음」 오보) ---------------------------------


def test_env_var_names_match_the_cli() -> None:
    """GUI 가 `cli` 를 import 하면 순환이라 상수를 복제했다 — 값이 갈리지 않게 묶어 둔다.

    갈리면 CLI 로 스캔하다 GUI 로 옮겨 온 사용자가 같은 환경변수를 두고도 다른 모델을 본다.
    """
    assert gui_server.MODEL_ENV_VAR == cli.MODEL_ENV_VAR
    assert gui_server.EMBED_MODEL_ENV_VAR == cli.EMBED_MODEL_ENV_VAR


def test_model_resolution_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """명시값 > 환경변수 > 코어 기본값 — CLI 의 `_resolve_model()` 과 같은 규칙."""
    monkeypatch.setenv(gui_server.MODEL_ENV_VAR, "env-model")

    assert gui_server.resolve_model("explicit") == "explicit"
    assert gui_server.resolve_model(None) == "env-model"
    assert gui_server.resolve_model("   ") == "env-model"

    monkeypatch.delenv(gui_server.MODEL_ENV_VAR)
    assert gui_server.resolve_model(None) == gui_server.core.DEFAULT_MODEL


def _stub_report(**over: object):
    """`DoctorReport` 대역 — 기본은 «전부 정상»이고 테스트가 한 축씩 흔든다.

    필드를 하나 늘릴 때마다 테스트마다 스텁을 고치지 않도록 한 곳에 모은다.
    """
    from corpbrain.core.models import HardwareInfo

    values = {
        "installed": True,
        "running": True,
        "model": "m",
        "model_present": True,
        "embed_model": "e",
        "embed_model_present": True,
        "available_models": [],
        "hardware": HardwareInfo(gpu=True, label="GPU"),
        "max_file_size": 1,
        "max_total_tokens": 1,
        "cloud_consent": True,
        "cloud_api_key": True,
    }
    values.update(over)
    values["cloud_ready"] = values["cloud_consent"] and values["cloud_api_key"]
    values["ready"] = (
        values["installed"]
        and values["running"]
        and values["model_present"]
        and values["embed_model_present"]
    )
    return type("_Report", (), values)()


def test_doctor_checks_the_workspace_models_not_the_defaults(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """설정 화면이 **실제로 쓸 모델**을 점검한다.

    인자 없이 `diagnose()` 를 부르면 코어 기본값만 확인해, 다른 모델을 받아 둔 사용자에게
    「모델 없음」이라고 잘못 알린다 — 모델이 없는 게 아니라 점검이 엉뚱한 것을 본 것이다.
    """
    state, workspace_id = wired
    ws.save_options(
        state.registry_path,
        workspace_id,
        {"model": "qwen2.5:3b-instruct", "embed_model": "nomic-embed-text"},
    )
    seen: dict[str, str] = {}

    def fake_diagnose(**kwargs: str):
        seen.update(kwargs)
        return _stub_report()

    monkeypatch.setattr(gui_server.core, "diagnose", fake_diagnose)
    monkeypatch.setattr(gui_server, "build_doctor_lines", lambda report: ["ok"])

    status, payload = _route(
        state, "GET", "/api/doctor", query={"workspace_id": [workspace_id]}
    )

    assert status == 200
    assert seen["model"] == "qwen2.5:3b-instruct"
    assert seen["embed_model"] == "nomic-embed-text"
    # 화면이 «무엇을 점검했는가»를 함께 보여 준다.
    assert payload["model"] == "qwen2.5:3b-instruct"
    assert payload["embed_model"] == "nomic-embed-text"


def test_scan_uses_the_same_model_resolution_as_doctor(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """점검과 실행이 같은 모델을 써야 한다.

    갈리면 「점검은 통과했는데 스캔은 다른 모델로 돌아 실패」가 된다.
    """
    state, workspace_id = wired
    monkeypatch.setenv(gui_server.MODEL_ENV_VAR, "env-model")
    monkeypatch.setenv(gui_server.EMBED_MODEL_ENV_VAR, "env-embed")
    started: list[dict] = []
    monkeypatch.setattr(state.jobs, "start", lambda **kw: started.append(kw))

    status, _payload = _route(state, "POST", "/api/scan", {"workspace_id": workspace_id})

    assert status == 202
    assert started[0]["payload"]["model"] == "env-model"
    assert started[0]["payload"]["embed_model"] == "env-embed"


def test_scan_falls_back_to_saved_workspace_options(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """화면 입력칸이 비어 있으면 **워크스페이스에 저장된 모델**을 쓴다.

    이것이 없으면 저장해 둔 모델이 무시되고 코어 기본값으로 돌아, 받은 적 없는 모델을
    찾지 못했다며 실패한다. doctor 는 `last_options` 를 보는데 스캔은 보지 않아 둘이
    갈렸던 실제 결함이다.
    """
    state, workspace_id = wired
    ws.save_options(
        state.registry_path,
        workspace_id,
        {"model": "qwen2.5:3b-instruct", "embed_model": "nomic-embed-text"},
    )
    started: list[dict] = []
    monkeypatch.setattr(state.jobs, "start", lambda **kw: started.append(kw))

    # 옵션을 하나도 보내지 않는다 — 화면 입력칸이 비어 있는 상황이다.
    status, _payload = _route(state, "POST", "/api/scan", {"workspace_id": workspace_id})

    assert status == 202
    assert started[0]["payload"]["model"] == "qwen2.5:3b-instruct"
    assert started[0]["payload"]["embed_model"] == "nomic-embed-text"


def test_request_options_override_the_saved_ones(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """저장값은 기본값일 뿐이다 — 이번 실행에 입력한 값이 이긴다."""
    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "saved", "max_files": 10})
    started: list[dict] = []
    monkeypatch.setattr(state.jobs, "start", lambda **kw: started.append(kw))

    _route(
        state,
        "POST",
        "/api/scan",
        {"workspace_id": workspace_id, "options": {"model": "typed"}},
    )

    assert started[0]["payload"]["model"] == "typed"
    assert started[0]["payload"]["max_files"] == 10  # 건드리지 않은 저장값은 살아 있다


def test_doctor_and_scan_agree_on_the_model(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """점검과 실행이 **같은 모델**을 본다 — 갈리면 「점검은 통과했는데 스캔은 실패」가 된다."""
    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "qwen2.5:3b-instruct"})
    seen: dict[str, str] = {}

    def fake_diagnose(**kwargs: str):
        seen.update(kwargs)
        return _stub_report()

    monkeypatch.setattr(gui_server.core, "diagnose", fake_diagnose)
    monkeypatch.setattr(gui_server, "build_doctor_lines", lambda report: [])
    started: list[dict] = []
    monkeypatch.setattr(state.jobs, "start", lambda **kw: started.append(kw))

    _route(state, "GET", "/api/doctor", query={"workspace_id": [workspace_id]})
    _route(state, "POST", "/api/scan", {"workspace_id": workspace_id})

    assert seen["model"] == started[0]["payload"]["model"] == "qwen2.5:3b-instruct"


# --- 메서드 디스패치 (PUT 이 501 로 튀던 버그) -----------------------------------


def test_handler_accepts_every_method_the_router_uses() -> None:
    """`route()` 가 다루는 메서드를 핸들러가 **전부** 받는다.

    `BaseHTTPRequestHandler` 는 `do_<METHOD>` 가 없으면 **501 Not Implemented** 를 낸다.
    실제로 `do_PUT` 이 없어 모델 저장·위키 저장·클라우드 동의 세 경로가 통째로 막혀 있었다.

    `route()` 를 직접 부르는 테스트는 이 층을 지나지 않아 잡지 못한다 — 그래서 소스에서
    메서드를 뽑아 대조한다.
    """
    import inspect
    import re

    routed = set(re.findall(r'method == "([A-Z]+)"', inspect.getsource(gui_server)))
    handler = gui_server.make_handler(gui_server.GuiState())
    implemented = {name[len("do_") :] for name in dir(handler) if name.startswith("do_")}

    assert routed <= implemented, f"핸들러에 없는 메서드: {sorted(routed - implemented)}"


def test_put_reaches_the_router_instead_of_501(state: gui_server.GuiState) -> None:
    """PUT 요청이 501 이 아니라 실제 라우팅까지 간다."""
    response = _make_request(state, "PUT", "/api/settings/cloud", token=state.token)

    assert b" 501 " not in response.split(b"\r\n")[0]


# --- 퍼센트 인코딩 (한글·공백 경로가 그대로 파일명이 되던 버그) --------------------


def test_percent_encoded_path_is_decoded_before_routing(with_wiki) -> None:
    """브라우저는 한글·공백이 든 경로를 인코딩해 보낸다 — 서버가 되돌려야 한다.

    되돌리지 않으면 `%ED%95%98...` 라는 문자열 그대로를 파일명으로 찾아
    「그런 위키가 없습니다: %ED%95%98…」이 된다.
    """
    from urllib.parse import quote

    state, workspace_id, _ = with_wiki
    encoded = quote("인사/온보딩.md.md")
    assert "%" in encoded  # 실제로 인코딩됐다

    response = _make_request(
        state,
        "GET",
        f"/api/workspaces/{workspace_id}/wiki/{encoded}",
        token=state.token,
    )

    assert b" 200 " in response.split(b"\r\n")[0]
    assert "제목".encode() in response


def test_path_with_spaces_is_decoded(wired, tmp_path: Path) -> None:
    """공백도 `%20` 으로 온다 — 폴더 이름에 공백이 있는 실사용 경로다."""
    from urllib.parse import quote

    state, workspace_id = wired
    folder = tmp_path / "wiki" / "하와이 관광 이관문서"
    folder.mkdir(parents=True)
    (folder / "03. API 명세서.docx.md").write_text(WIKI_BODY, encoding="utf-8")

    response = _make_request(
        state,
        "GET",
        f"/api/workspaces/{workspace_id}/wiki/{quote('하와이 관광 이관문서/03. API 명세서.docx.md')}",
        token=state.token,
    )

    assert b" 200 " in response.split(b"\r\n")[0]


def test_encoded_traversal_is_still_rejected(with_wiki) -> None:
    """디코딩이 `..` 를 만들어 내도 출력 폴더를 벗어나지 못한다.

    경로 확인이 **디코딩된 값으로** 이뤄지므로 인코딩으로 검사를 우회할 수 없다.
    """
    state, workspace_id, _ = with_wiki

    response = _make_request(
        state,
        "GET",
        f"/api/workspaces/{workspace_id}/wiki/%2e%2e%2f%2e%2e%2fsecret.txt",
        token=state.token,
    )

    assert b" 200 " not in response.split(b"\r\n")[0]


def test_encoded_static_traversal_is_still_rejected(state: gui_server.GuiState) -> None:
    response = _make_request(state, "GET", "/static/%2e%2e%2f%2e%2e%2fcli.py")

    assert b" 200 " not in response.split(b"\r\n")[0]


# --- 설치된 모델 목록 (드롭다운 데이터) -----------------------------------------


def test_models_endpoint_lists_installed_models(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """화면이 자유 입력 대신 고르게 하려면 설치 목록이 필요하다."""
    state, _ = wired
    monkeypatch.setattr(
        "corpbrain.core.llm.ollama_client.list_models",
        lambda *a, **k: ["qwen2.5:3b-instruct", "qwen3-embedding:4b"],
    )

    status, payload = _route(state, "GET", "/api/models")

    assert status == 200
    assert payload["available"] is True
    assert payload["models"] == ["qwen2.5:3b-instruct", "qwen3-embedding:4b"]


def test_models_endpoint_is_not_an_error_when_ollama_is_down(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ollama 가 꺼져 있어도 오류로 만들지 않는다.

    목록이 비면 화면이 직접 입력으로 떨어지면 되고, 데몬이 없다는 사실은 바로 옆 환경
    점검이 이미 말해 준다. 여기서 400을 내면 설정 화면이 통째로 실패한다.
    """
    from corpbrain.core.llm.ollama_client import OllamaNotAvailableError

    state, _ = wired

    def down(*_a: object, **_k: object) -> list[str]:
        raise OllamaNotAvailableError("데몬이 응답하지 않습니다")

    monkeypatch.setattr("corpbrain.core.llm.ollama_client.list_models", down)

    status, payload = _route(state, "GET", "/api/models")

    assert status == 200
    assert payload["available"] is False
    assert payload["models"] == []


def test_saving_options_is_a_partial_update(wired) -> None:
    """보낸 키만 바꾸고 나머지는 남긴다.

    통째로 교체하면 설정 화면에서 「모델 저장」을 누를 때 모델 두 개만 보내므로
    `engine`·임계치 같은 다른 저장값이 함께 지워진다. 드롭다운이 채워지기 전에 눌렀다면
    설정이 통째로 날아간다 — 실제로 겪은 일이다.
    """
    state, workspace_id = wired
    ws.save_options(
        state.registry_path,
        workspace_id,
        {"model": "old", "engine": "local", "max_files": 30},
    )

    status, payload = _route(
        state, "PUT", f"/api/workspaces/{workspace_id}/options", {"model": "new"}
    )

    assert status == 200
    assert payload["last_options"] == {"model": "new", "engine": "local", "max_files": 30}


def test_saving_empty_options_keeps_what_is_there(wired) -> None:
    """빈 본문으로 저장해도 기존 설정이 사라지지 않는다."""
    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "keep-me"})

    _route(state, "PUT", f"/api/workspaces/{workspace_id}/options", {})

    assert ws.load(state.registry_path)[0].last_options == {"model": "keep-me"}


# --- 실행 단위 옵션 vs 인덱스 속성 -----------------------------------------------


def test_scan_form_does_not_offer_a_per_run_embedding_model() -> None:
    """임베딩 모델은 **인덱스 전체의 속성**이지 한 번 실행의 옵션이 아니다.

    스캔마다 바꾸면 벡터의 좌표계가 섞이므로 코어가 막는다 — 그 자리에 선택지를 두면
    「고르면 반드시 실패하는」 항목이 된다. 설정 화면에만 둔다.
    """
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    scan_section = html.split('id="v-scan"')[1].split('id="v-dash"')[0]

    assert 'data-opt="embed_model"' not in scan_section


def test_settings_still_offers_the_embedding_model() -> None:
    """대신 설정 화면에는 반드시 있어야 한다 — 없으면 바꿀 길이 사라진다."""
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    settings = html.split('id="v-settings"')[1]

    assert 'id="defEmbed"' in settings
    # 바꾸면 다시 만들어야 한다는 안내가 함께 있어야 한다. 문구가 아니라 **자리**를
    # 단언한다 — 쉬운 말로 다듬을 때마다 테스트가 깨지면 안 된다.
    assert 'id="embedWarning"' in settings


def test_changing_the_embedding_model_is_still_possible_through_options(
    wired,
) -> None:
    """설정에서 저장한 임베딩 모델이 스캔까지 전달된다."""
    state, workspace_id = wired

    _route(
        state,
        "PUT",
        f"/api/workspaces/{workspace_id}/options",
        {"embed_model": "qwen3-embedding:4b"},
    )

    assert ws.load(state.registry_path)[0].last_options["embed_model"] == "qwen3-embedding:4b"


# --- 환경 점검 화면 (OK 와 실패가 한눈에 갈리게) ---------------------------------


def test_doctor_returns_structured_checks(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    """화면이 상태 칩을 그리려면 구조가 필요하다 — CLI 문자열을 파싱하지 않는다.

    문자열을 파싱하면 문구를 다듬을 때마다 화면이 조용히 깨진다.
    """
    state, _ = wired
    monkeypatch.setattr(
        gui_server.core,
        "diagnose",
        lambda **_k: _stub_report(
            model="qwen2.5:3b-instruct",
            embed_model="qwen3-embedding:4b",
            embed_model_present=False,
            hardware=__import__("corpbrain.core.models", fromlist=["x"]).HardwareInfo(
                gpu=False, label="CPU"
            ),
            cloud_consent=False,
            cloud_api_key=False,
        ),
    )
    monkeypatch.setattr(gui_server, "build_doctor_lines", lambda report: [])

    _status, payload = _route(state, "GET", "/api/doctor")
    by_label = {c["label"]: c for c in payload["checks"]}

    assert by_label["요약 모델"]["status"] == "ok"
    assert by_label["임베딩 모델"]["status"] == "fail"
    assert "ollama pull qwen3-embedding:4b" in by_label["임베딩 모델"]["action"]


def test_only_required_checks_are_blocking(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    """GPU 없음과 클라우드 미설정은 **경고**다 — 스캔을 막지 않는다 (v0.5 §3 항목10).

    이 둘을 실패로 칠하면 로컬만 쓰는 사용자에게 늘 빨간 화면이 보인다.
    """
    state, _ = wired
    monkeypatch.setattr(
        gui_server.core,
        "diagnose",
        lambda **_k: _stub_report(
            hardware=__import__("corpbrain.core.models", fromlist=["x"]).HardwareInfo(
                gpu=False, label="CPU"
            ),
            cloud_consent=False,
            cloud_api_key=False,
        ),
    )
    monkeypatch.setattr(gui_server, "build_doctor_lines", lambda report: [])

    _status, payload = _route(state, "GET", "/api/doctor")

    assert [c["label"] for c in payload["checks"] if c["blocking"]] == []
    warned = {c["label"] for c in payload["checks"] if c["status"] == "warn"}
    assert warned == {"GPU 가속", "클라우드 엔진"}


def test_cloud_check_says_which_half_is_missing(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    """「사용 불가」로 뭉개지 않고 동의·API 키 중 무엇이 빠졌는지 말해 준다."""
    state, _ = wired
    monkeypatch.setattr(
        gui_server.core,
        "diagnose",
        lambda **_k: _stub_report(cloud_consent=True, cloud_api_key=False),
    )
    monkeypatch.setattr(gui_server, "build_doctor_lines", lambda report: [])

    _status, payload = _route(state, "GET", "/api/doctor")
    cloud = next(c for c in payload["checks"] if c["label"] == "클라우드 엔진")

    assert "동의 없음" not in cloud["detail"]
    assert "ANTHROPIC_API_KEY" in cloud["detail"]


def test_models_endpoint_reports_what_will_actually_be_used(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`resolved` 는 «지금 실제로 쓰일 모델»이다.

    화면이 「기본값 사용」 같은 항목을 두더라도 그것이 **어떤 모델인지 글자로** 적을 수
    있어야 한다 — 이름 없는 기본값은 사용자가 확인할 방법이 없다.
    """
    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "qwen2.5:3b-instruct"})
    monkeypatch.setattr(
        "corpbrain.core.llm.ollama_client.list_models", lambda *a, **k: ["qwen2.5:3b-instruct"]
    )

    _status, payload = _route(
        state, "GET", "/api/models", query={"workspace_id": [workspace_id]}
    )

    assert payload["resolved"]["model"] == "qwen2.5:3b-instruct"
    # 저장하지 않은 쪽은 코어 기본값으로 해소된다 — 그 값도 이름으로 나온다.
    assert payload["resolved"]["embed_model"] == gui_server.core.DEFAULT_EMBED_MODEL


def test_models_endpoint_resolves_even_when_ollama_is_down(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """데몬이 꺼져 있어도 «무엇이 쓰일지»는 답할 수 있다 — 그건 설정이지 조회가 아니다."""
    from corpbrain.core.llm.ollama_client import OllamaNotAvailableError

    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "저장된모델"})

    def down(*_a: object, **_k: object) -> list[str]:
        raise OllamaNotAvailableError("데몬 없음")

    monkeypatch.setattr("corpbrain.core.llm.ollama_client.list_models", down)

    _status, payload = _route(
        state, "GET", "/api/models", query={"workspace_id": [workspace_id]}
    )

    assert payload["available"] is False
    assert payload["resolved"]["model"] == "저장된모델"


def test_settings_dropdowns_have_no_nameless_default_option() -> None:
    """설정 화면 드롭다운에 「코어 기본값 사용」 같은 이름 없는 항목을 두지 않는다.

    무엇이 골라지는지 알 수 없고, 그 값은 어차피 바로 아래 목록에 이미 들어 있다.
    빈 항목이 의미를 갖는 곳은 스캔 화면(=덮어쓰지 않는다)뿐이다.
    """
    import re

    raw = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    # **주석을 먼저 걷어낸다.** 이 규칙을 설명하는 주석에 「코어 기본값 사용」이 예시로
    # 들어 있어, 그냥 찾으면 실제 코드가 아니라 설명을 읽는다.
    js = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.MULTILINE)

    assert "코어 기본값 사용" not in js


# --- 엔진과 모델의 관계 (아무 효과 없는 컨트롤을 두지 않는다) ---------------------


def test_scan_form_has_no_summary_model_control() -> None:
    """스캔 화면에서 요약 모델을 고르지 않는다.

    엔진에 따라 실제로 쓰이는 필드가 다르다(`model` vs `cloud_model`). Ollama 모델만
    나열하는 드롭다운은 **클라우드를 고른 순간 아무 효과가 없는 컨트롤**이 된다.
    모델은 설정 화면 한 곳에서만 정한다.
    """
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    scan = html.split('id="v-scan"')[1].split('id="v-dash"')[0]
    assert 'id="model"' not in scan
    # 대신 «무엇이 쓰일지»를 보여 주는 자리가 있어야 한다.
    assert 'id="effectiveModel"' in scan


def test_models_endpoint_reports_the_cloud_model_too(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """클라우드 엔진이 쓸 모델도 함께 알려 준다 — 화면이 엔진에 맞는 이름을 적으려면 필요하다."""
    state, workspace_id = wired
    monkeypatch.setattr("corpbrain.core.llm.ollama_client.list_models", lambda *a, **k: [])

    _status, payload = _route(
        state, "GET", "/api/models", query={"workspace_id": [workspace_id]}
    )

    assert payload["resolved"]["cloud_model"] == gui_server.core.DEFAULT_CLOUD_MODEL


def test_scan_uses_the_workspace_model_without_any_form_input(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    """폼에서 모델을 없앴으므로 저장된 값만으로 스캔이 성립해야 한다."""
    state, workspace_id = wired
    ws.save_options(state.registry_path, workspace_id, {"model": "qwen2.5:7b-instruct"})
    started: list[dict] = []
    monkeypatch.setattr(state.jobs, "start", lambda **kw: started.append(kw))

    _route(state, "POST", "/api/scan", {"workspace_id": workspace_id, "options": {"engine": "local"}})

    assert started[0]["payload"]["model"] == "qwen2.5:7b-instruct"


def test_settings_copy_does_not_promise_an_empty_choice() -> None:
    """드롭다운은 비울 수 없다 — 「비우면 …」이라고 말하면 거짓말이 된다.

    자유 입력이던 시절의 문구가 남아 있으면 사용자는 있지도 않은 선택지를 찾는다.
    """
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    settings = html.split('id="v-settings"')[1]

    assert "비우면" not in settings


def test_scan_screen_offers_a_way_to_change_the_model() -> None:
    """「설정에서 바꾸세요」라고 말하는 대신 데려다준다."""
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    scan = html.split('id="v-scan"')[1].split('id="v-dash"')[0]

    assert 'id="goSettings"' in scan


def test_graph_pane_states_its_scope() -> None:
    """그래프가 **워크스페이스 전체**임을 화면이 말한다.

    「본문」 탭 바로 옆에 있어 «지금 고른 문서의 그래프»로 읽히기 쉽다. 실제로는 검색과
    무관한 전체 그림이라, 사용자가 「이전 그래프가 남았다」고 오해한 적이 있다.
    """
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")

    assert 'class="graph-note"' in html
    assert "검색 결과와는 무관" in html


def test_switching_workspace_discards_everything_from_the_previous_one() -> None:
    """워크스페이스를 바꾸면 이전 것의 흔적을 **모두** 버린다.

    그림만 버리던 때는 탐색 화면에 이전 워크스페이스의 본문·편집 중이던 원고가 그대로
    남아 새 워크스페이스의 내용처럼 보였다. 편집기가 열린 채 남는 것이 특히 위험하다 —
    그 상태로 저장하면 **새** 워크스페이스의 같은 경로를 향한다.

    전환 지점이 셋(열기·추가·활성 삭제)이라 각자 지우면 하나가 빠진다. `useWorkspace()`
    한 곳으로 모았음을 여기서 고정한다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    reset = js.split("function useWorkspace(ws) {")[1].split("\n  }")[0]

    assert "graphData = { nodes: [], edges: [] }" in reset   # 그래프
    assert "openPage = null" in reset                        # 열어 둔 위키(편집 대상)
    assert "focusedDocId = null" in reset                    # 그래프 강조
    assert 'clear($("#docBody"))' in reset                   # 본문
    assert 'clear($("#results"))' in reset                   # 문서 목록·검색 결과
    assert 'setPane("body")' in reset                        # 열려 있던 편집기
    # 전환 지점 셋이 모두 이 함수를 지난다.
    assert js.count("useWorkspace(") == 4                     # 정의 1 + 호출 3


# --- 탐색 기본 화면 (검색 전에도 둘러볼 수 있게) ---------------------------------


def test_wiki_tree_carries_document_titles(with_wiki) -> None:
    """목록이 «둘러보기»로 쓰이려면 제목이 필요하다.

    파일 이름(`온보딩.md.md`)만 늘어놓으면 무엇이 들었는지 알 수 없다.
    """
    state, workspace_id, _ = with_wiki

    _status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/wiki")

    assert payload["entries"][0]["title"] == "제목"
    assert payload["entries"][0]["name"] == "온보딩.md.md"


def test_wiki_title_falls_back_to_the_file_name(wired, tmp_path: Path) -> None:
    """제목 줄이 없거나 읽지 못해도 목록이 실패하지 않는다."""
    state, workspace_id = wired
    out = tmp_path / "wiki"
    out.mkdir()
    (out / "제목없음.md.md").write_text("본문만 있다\n", encoding="utf-8")

    _status, payload = _route(state, "GET", f"/api/workspaces/{workspace_id}/wiki")

    assert payload["entries"][0]["title"] == "제목없음.md.md"


def test_explore_shows_the_document_list_before_searching() -> None:
    """검색 전 화면이 비어 있지 않다 — 빈 화면은 막다른 길이다.

    검색어를 모르면 아무것도 못 하고, 위키 목록은 이미 받아 두고 쓰지 않고 있었다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "function renderWikiList()" in js
    # 검색어를 비우면 목록으로 돌아온다.
    assert "renderWikiList(); drawGraph(); return;" in js


def test_every_edge_kind_has_an_explanation_on_the_dashboard() -> None:
    """엣지 종류 4가지에 모두 설명이 붙는다 — 종류가 늘면 여기서 걸린다.

    이름(`TAGGED_WITH` 등)은 저장소의 `type` 컬럼·`corpbrain graph` 출력·`--expand-edges`
    플래그가 함께 쓰는 문자열이라 화면에서도 그대로 두고, 뜻만 `?` 로 옆에 단다.

    설명에는 **문서끼리 직접 잇는 선인지**를 적는다. 넷 중 둘만 그러하므로, 그 사실이 없으면
    「엣지 71개」인데 그래프 그림에는 선이 두 개뿐인 것이 설명되지 않는다.
    """
    from corpbrain.core.models import EdgeType

    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    kinds = js.split("var EDGE_HELP = {")[1].split("\n  };")[0]

    for kind in EdgeType:
        assert f"{kind.value}:" in kinds
    assert kinds.count("그래프에") == len(EdgeType)
    # 키보드로도 볼 수 있어야 한다 — 마우스 호버만으로는 닿지 않는 사용자가 있다.
    assert 'tabindex: "0"' in js
    assert "focus-visible::after" in (gui_server.STATIC_DIR / "app.css").read_text("utf-8")


def test_help_tips_do_not_rely_on_hover_alone() -> None:
    """「?」 도움말은 **호버에만 의존하지 않는다** (ui-ux-pro-max · Hover vs Tap · High).

    터치 기기에는 호버가 없고, 마우스를 오래 얹기 어려운 사용자도 있다. 클릭·Enter·Space 로
    여닫고 Esc 로 닫는다. 함께 지킨 것:

    - **겨냥할 자리 44px 급** (터치 목표 · Critical) — 보이는 원은 15px 그대로 두고
      `::before` 로 사방을 넓힌다. 글자 줄의 높이를 밀지 않는다.
    - **대비 4.5:1** (Critical) — 글리프가 `--ink-3`(3.0:1) 이면 미달이라 `--ink-2` 를 쓴다.
    - **고정 폭 상자에 글을 가두지 않는다** (Text Reflow · Critical).
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    css = (gui_server.STATIC_DIR / "app.css").read_text("utf-8")
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")

    assert '.qm[aria-expanded="true"]::after' in css      # 눌러서 연 상태
    assert 'qm.setAttribute("aria-expanded"' in js
    assert 'if (event.key === "Escape") return closeTips(null);' in js
    assert '.qm::before{content:"";position:absolute;inset:-9px' in css
    assert "max-width:min(260px,68vw)" in css
    # 정적 `?` 도 같은 계약을 갖는다.
    assert html.count('class="qm" role="button" tabindex="0" aria-expanded="false"') == 8


def test_help_icon_is_the_same_drawing_everywhere() -> None:
    """정적 `?` 와 화면이 만들어 내는 `?` 가 **같은 그림**이다.

    글자 `?` 를 원 안에 넣으면 글꼴 지표 때문에 위로 쏠려 찌그러져 보인다. 인라인 SVG 로
    바꿨고(도안은 Feather Icons 의 `help-circle`, MIT), 두 벌이 갈리지 않도록 여기서 묶는다.
    이 저장소는 아이콘 라이브러리를 들이지 않는다 — 「의존성 0 · 외부 CDN 0」 이 v0.9 의
    불변식이라 인라인 SVG 가 이 프로젝트의 관용구다(접기 화살표도 같은 방식이다).
    """
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    path = "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"

    assert html.count(path) == 8
    assert path in js
    # SVG 는 다른 네임스페이스다 — `createElement` 로 만들면 그려지지 않는다.
    assert "createElementNS(SVG_NS" in js


def test_browse_list_is_a_collapsible_folder_tree() -> None:
    """둘러보기 목록은 폴더 트리다 — 평면 목록은 줄마다 같은 접두사를 반복했다.

    접힘 상태는 **변수**에 둔다. DOM 에만 두면 다른 화면에 갔다 오는 순간 전부 펼쳐진다.
    들여쓰기 폭은 CSS 가 소유하고 JS 는 깊이만 넘긴다 — 크기 값이 JS 로 새면 한쪽만
    바뀌어 어긋난다(워크스페이스 줄에서 이미 겪었다).
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    css = (gui_server.STATIC_DIR / "app.css").read_text("utf-8")

    assert "function buildTree(entries)" in js
    assert "var collapsedDirs = {}" in js
    assert 'style: "--depth:" + depth' in js
    assert "calc(12px + var(--depth,0) * 18px)" in css   # 폴더 줄
    assert "calc(20px + var(--depth,0) * 18px)" in css   # 문서 줄은 8px 더 들어간다
    # 검색 결과는 평면 그대로다 — 폴더로 묶으면 관련도 순서가 깨진다.
    ranked = js.split("function renderResults(data) {")[1].split("\n  }")[0]
    assert "--depth" not in ranked
    assert "buildTree" not in ranked


def test_workspace_row_controls_share_one_box() -> None:
    """「활성」 표시와 「열기」·「제거」 버튼이 **같은 상자**를 쓴다.

    크기를 JS 의 인라인 style 에 적어 두면 한쪽만 바뀌어 줄이 들쭉날쭉해진다. CSS 한
    규칙이 셋을 함께 잡게 한다 — 파이썬 테스트가 보지 않는 층이라 여기서 고정한다.

    테두리는 **투명하다**. 보이는 테두리는 누를 수 있는 것으로 읽혀 버튼과 헷갈리고,
    아예 빼면 폭 1px 만큼 작아져 줄이 어긋난다.
    """
    css = (gui_server.STATIC_DIR / "app.css").read_text("utf-8")
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert ".wsrow .btn,.wsrow .ws-active{padding:3px 9px;font-size:12px}" in css
    assert "border:1px solid transparent" in css     # 자리만 차지하고 보이지 않는다
    assert "padding:3px 9px" not in js               # 크기를 JS 가 따로 적지 않는다


def test_selection_survives_a_list_redraw() -> None:
    """선택 표시는 목록을 다시 그려도 남는다.

    표시를 DOM 에만 두면 다른 화면에 갔다 오거나(`show("explore")` → `loadWikiTree()`)
    검색을 다시 하는 순간 사라진다 — 본문은 열려 있는데 왼쪽에는 아무것도 골라져 있지
    않은 어긋난 상태가 된다. 그래서 «지금 열어 둔 문서»를 변수로 들고 그릴 때마다 다시
    표시한다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    # 항목마다 식별자를 심어 두고 — 목록은 위키 상대경로, 검색 결과는 원문 절대경로 —
    assert '"data-wiki": entry.path' in js
    assert '"data-doc": item.doc_id' in js
    # 표시는 언제나 그 식별자와 변수를 맞춰 다시 만든다. 두 목록이 같은 함수를 쓴다.
    assert "function markSelection()" in js
    assert js.count("markSelection();") >= 4


def test_clearing_the_query_keeps_the_open_document() -> None:
    """검색어를 비우는 것은 목록으로 돌아가는 것이지 열어 둔 문서를 닫는 것이 아니다."""
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    empty_query = js.split("var q = $(\"#q\").value.trim();")[1].split("\n")[:4]

    assert "focusedDocId = null" not in "".join(empty_query)


def test_explore_panes_are_mutually_exclusive() -> None:
    """본문·편집기·그래프는 한 번에 하나만 보인다 (스펙 §4.8 — 한 화면에서 «전환»한다).

    세 곳이 각자 `hidden` 을 만지고 있어, 그래프를 보는 중에 문서를 클릭하면 본문이 함께
    열렸다. 캔버스는 자기 픽셀 크기를 **그릴 때** 정하므로 상자만 줄고 그림은 그대로 남아
    잘려 보인다 — 고른 문서의 노란 강조가 잘려 나간 쪽에 있으면 강조가 안 되는 것처럼
    보인다. 전환을 `setPane()` 한 곳으로 모아 막는다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "function setPane(name)" in js
    # 어느 경로도 그래프를 끄지 않은 채 본문만 켜지 않는다.
    assert '$("#paneBody").hidden = false' not in js


def test_graph_redraws_when_its_box_changes_size() -> None:
    """상자 크기가 바뀌면 캔버스를 다시 그린다 — 창 크기 변경만으로는 부족하다."""
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "ResizeObserver" in js


def test_graph_is_radial_and_clickable() -> None:
    """그래프는 **방사형**이고 점을 누르면 그 문서가 열린다.

    다각형 한 겹으로 늘어놓던 배치는 어느 문서가 중심인지 그림이 말해 주지 않았고, 지름을
    가로지르는 직선이 막대처럼 보였다. 가운데·안쪽 고리·바깥 고리로 나누고 선을 곡선으로
    그린다.

    중심 선택도 이웃 판정도 **서버가 준 값**(연결 수·엣지)을 읽기만 한다 — 화면이 중심성을
    다시 계산하지 않는다는 불변식(§4.11)을 지킨다.

    클릭은 **목록에서 고른 것과 같은 경로**를 탄다(`openWikiByPath`). 그림과 목록이 서로 다른
    문서를 가리키는 상태를 만들지 않는다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "placeRing(inner, rInner)" in js and "placeRing(outer, rOuter)" in js
    assert "quadraticCurveTo" in js                      # 곡선 연결
    assert "function openGraphNode(docId)" in js
    assert "openWikiByPath(match.path" in js             # 목록 클릭과 같은 경로
    # 클릭 판정 좌표는 **그린 그대로** 담는다 — 그림과 어긋날 수 없다.
    assert "graphHits.push({ id: node.id" in js


def test_scan_options_are_restored_into_the_form() -> None:
    """저장된 실행 옵션이 스캔 폼에 되돌아온다 (스펙 §4.5).

    서버는 `last_options` 를 밑에 깔고 요청이 덮으므로, **입력칸이 비어 있어도 저장된 값이
    그대로 쓰인다.** 채워 두지 않으면 자리 표시로 보이는 기본값과 실제로 도는 값이 어긋나고
    사용자가 알 길이 없다.

    `force`·`force_gates` 는 예외다 — 저장하지 않으며 언제나 꺼진 채로 시작한다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")
    fill = js.split("function fillOptions() {")[1].split("\n  }")[0]

    assert "fillOptions();" in js.split("function loadPlan() {")[1][:120]
    assert 'if (input.type === "checkbox") { input.checked = false; return; }' in fill
    assert "adv.open" in fill          # 저장된 고급 값이 있으면 접기를 펴 둔다


def test_volatile_options_are_never_saved() -> None:
    """「이번 한 번만」인 옵션은 저장되지 않는다 — 조용히 유지되면 놀란다 (§4.5)."""
    assert ws.VOLATILE_OPTIONS == {"force", "force_gates"}


def test_every_advanced_field_is_a_real_config_key() -> None:
    """화면의 고급 항목이 모두 `ScanConfig` 의 실제 필드다.

    러너는 모르는 키를 `ValueError` 로 거절하고 서버가 그것을 400 으로 바꾼다. 화면에만 있는
    항목이 섞이면 **그 칸을 채운 순간 스캔이 시작조차 되지 않는다.**
    """
    import dataclasses
    import re

    from corpbrain.core.config import ScanConfig

    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    fields = {field.name for field in dataclasses.fields(ScanConfig)}

    keys = set(re.findall(r'data-opt="([^"]+)"', html))
    assert keys, "고급 설정 항목을 하나도 찾지 못했다"
    assert keys <= fields, f"`ScanConfig` 에 없는 키: {sorted(keys - fields)}"


def test_graph_zooms_without_recomputing_the_layout() -> None:
    """휠로 확대·축소하고 끌어서 옮긴다. **배치는 그대로 두고 그리기만 변환한다.**

    확대 배율로 좌표를 다시 계산하면 확대할 때마다 문서 자리가 미세하게 달라지고, 되돌려도
    처음 그림이 정확히 돌아오지 않는다. 클릭 판정은 화면 좌표를 그림 좌표로 되돌려 맞춘다 —
    `graphHits` 는 확대 전 좌표를 담고 있으므로 이 환산이 없으면 확대한 뒤 엉뚱한 점이 눌린다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "ctx.scale(graphView.scale, graphView.scale)" in js
    assert "{ passive: false }" in js            # 페이지가 함께 스크롤되지 않게 한다
    assert "MIN_SCALE = 0.4, MAX_SCALE = 4" in js
    # 클릭 판정을 그림 좌표로 되돌린다.
    assert "- graphView.ox) / graphView.scale" in js
    # 끌어서 옮긴 것은 클릭이 아니다 — 이동을 마칠 때마다 문서가 열리면 안 된다.
    assert "if (dragged) { dragged = false; return; }" in js
    # 조작 방법을 화면이 알려 준다.
    html = (gui_server.STATIC_DIR / "index.html").read_text("utf-8")
    assert "휠로 확대·축소" in html


def test_graph_labels_fold_when_the_circle_gets_small() -> None:
    """노드 간격이 글자 높이보다 좁아지면 라벨을 접고 고른 문서만 남긴다.

    라벨을 노드 바로 위에 중앙 정렬로 놓던 종전 방식은 원이 작아질수록 이웃 글자와
    겹쳤다. 이제 원 **바깥**으로 밀어 좌·우 정렬하고, 그래도 좁으면 접는다.
    """
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "var showLabels = gap >=" in js
    assert "function ellipsize(" in js


# --- 검색 데이터 재생성 (겁주는 문구 대신 실제 동작) -----------------------------


def _seed_index(out_dir: Path, model: str) -> None:
    from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

    out_dir.mkdir(parents=True, exist_ok=True)
    with SqliteVectorStore(index_path_for(out_dir)) as store:
        store.set_model_name(model)


def test_saving_the_same_embedding_model_needs_no_rebuild(wired, tmp_path: Path) -> None:
    state, workspace_id = wired
    _seed_index(tmp_path / "wiki", "nomic-embed-text")

    _status, payload = _route(
        state,
        "PUT",
        f"/api/workspaces/{workspace_id}/options",
        {"embed_model": "nomic-embed-text"},
    )

    assert payload["index"]["rebuild_required"] is False


def test_changing_the_embedding_model_reports_a_rebuild(wired, tmp_path: Path) -> None:
    """미리 겁주는 문구 대신 **실제로 그 일이 벌어진 시점**에 알린다.

    코어의 안내는 `--force` 같은 CLI 문구라 화면에 그대로 내보내면 쓸모가 없다.
    """
    state, workspace_id = wired
    _seed_index(tmp_path / "wiki", "nomic-embed-text")

    _status, payload = _route(
        state,
        "PUT",
        f"/api/workspaces/{workspace_id}/options",
        {"embed_model": "qwen3-embedding:4b"},
    )

    assert payload["index"]["rebuild_required"] is True
    assert payload["index"]["model"] == "nomic-embed-text"   # 이전 모델을 이름으로 알려 준다


def test_deleting_the_index_leaves_wiki_and_graph_alone(wired, tmp_path: Path) -> None:
    """지워지는 것은 벡터뿐이다 — 위키는 그대로라 다음 스캔에서 요약이 스킵된다."""
    from corpbrain.core.vectorstore import index_path_for

    state, workspace_id = wired
    out = tmp_path / "wiki"
    _seed_index(out, "nomic-embed-text")
    (out / "문서.md.md").write_text(WIKI_BODY, encoding="utf-8")

    status, payload = _route(state, "DELETE", f"/api/workspaces/{workspace_id}/index")

    assert status == 200
    assert payload["removed"] is True
    assert not index_path_for(out).exists()
    assert (out / "문서.md.md").exists()


def test_deleting_the_index_does_not_hit_the_workspace_delete_route(
    wired, tmp_path: Path
) -> None:
    """`DELETE .../{id}/index` 가 **워크스페이스 삭제**로 새지 않는다.

    하위 경로를 거르지 않으면 마지막 조각(`index`)을 워크스페이스 id로 읽어
    「그런 워크스페이스가 없습니다」로 답한다 — 실제로 그랬다.
    """
    state, workspace_id = wired
    _seed_index(tmp_path / "wiki", "nomic-embed-text")

    status, _payload = _route(state, "DELETE", f"/api/workspaces/{workspace_id}/index")

    assert status == 200
    assert len(ws.load(state.registry_path)) == 1   # 워크스페이스는 살아 있다


def test_doctor_block_does_not_repeat_the_model_names() -> None:
    """항목 줄에 모델 이름이 이미 나오므로 아래에 다시 적지 않는다."""
    js = (gui_server.STATIC_DIR / "app.js").read_text("utf-8")

    assert "점검한 모델:" not in js
