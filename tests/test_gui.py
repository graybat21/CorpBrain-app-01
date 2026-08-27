"""GUI 서버 ↔ 코어 배선과 상태코드 (v0.9 §4.3 · DoD 1).

CLI 어댑터 테스트와 같은 잣대다 — 이 파일은 **배선과 상태코드**만 본다. 정확 문자열·순수
판정은 `tests/unit/test_gui_*.py`가 단언한다 (§3 「검증 방식」).
"""

from __future__ import annotations

import io
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import environment
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.llm import ollama_client
from corpbrain.core.models import EdgeType, GraphEdge, GraphNode, HardwareInfo, NodeType
from corpbrain.gui.api import SESSION_COOKIE, GuiApp
from corpbrain.gui.httpd import _Handler

PORT = 8765
AUTH = {"Host": f"127.0.0.1:{PORT}", "Cookie": f"{SESSION_COOKIE}=sess"}


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "wiki"


@pytest.fixture
def app(out_dir: Path) -> GuiApp:
    return GuiApp(out_dir=out_dir, token="tok", port=PORT, session_token="sess")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경 점검을 고정한다 — 어댑터 테스트는 데몬 상태와 무관해야 한다."""
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/ollama")
    monkeypatch.setattr(
        environment, "detect_hardware", lambda: HardwareInfo(gpu=True, label="GPU: X")
    )
    monkeypatch.setattr(
        ollama_client, "list_models", lambda *_a, **_k: ["qwen2.5:7b-instruct"]
    )


def _seed_graph(out_dir: Path) -> None:
    """그래프 DB를 실제 코어 저장소로 채운다 — 스텁이 아니라 배선을 본다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteGraphStore(graph_path_for(out_dir))
    try:
        store.replace_graph(
            [
                GraphNode(id="/docs/a.md", type=NodeType.DOCUMENT, label="A"),
                GraphNode(id="/docs/b.md", type=NodeType.DOCUMENT, label="B"),
                GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
            ],
            [
                GraphEdge(src="/docs/a.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="/docs/b.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
            ],
        )
    finally:
        store.close()


def test_dashboard_reports_doctor_and_graph(app: GuiApp, out_dir: Path) -> None:
    _seed_graph(out_dir)

    body = app.handle("GET", "/api/dashboard", AUTH).json()

    assert body["out_dir"] == str(out_dir)
    assert body["doctor"]["installed"] is True
    assert body["doctor"]["hardware"] == {"gpu": True, "label": "GPU: X"}
    assert body["graph"]["documents"] == 2
    assert body["graph"]["tags"] == 1
    assert body["graph"]["nodes"] == 3
    assert body["graph"]["edges_by_type"]["TAGGED_WITH"] == 2


def test_dashboard_survives_a_missing_graph_db(app: GuiApp) -> None:
    """첫 실행 — 그래프 DB가 없어도 **Doctor 카드는 실제 값으로** 그려진다 (§5).

    선행 조건 실패는 상태코드가 아니라 그 절 안의 구조화된 상태 본문으로 나온다 (§4.3.2).
    """
    response = app.handle("GET", "/api/dashboard", AUTH)

    assert response.status == 200
    body = response.json()
    assert body["doctor"]["installed"] is True  # 다른 절은 살아 있다
    assert body["graph"]["error"] == "GraphNotBuilt"


def test_absent_graph_db_is_not_reported_as_corruption(app: GuiApp) -> None:
    """스캔한 적 없는 사용자에게 「파일을 지우라」고 안내하지 않는다 (§5 · T11).

    코어는 부재와 손상을 같은 `PreconditionError`로 묶어 「손상되었거나 접근할 수 없습니다
    … 파일을 지우고 다시 scan 하세요」라고 안내한다. 그것은 `graph` CLI의 계약(부재도
    exit 1)에 맞춘 문구이고, GUI 첫 실행에서 그대로 내보내면 **만든 적도 없는 파일을
    지우라는 안내**가 된다 — CLAUDE.md가 「사용자가 멀쩡한 DB를 지운다」로 경계한 상황이다.
    """
    graph = app.handle("GET", "/api/dashboard", AUTH).json()["graph"]

    assert "지우" not in graph["message"]
    assert "손상" not in graph["message"]
    assert "먼저 스캔" in graph["message"]


def test_corrupted_graph_db_is_still_reported_as_such(app: GuiApp, out_dir: Path) -> None:
    """부재를 갈라 냈다고 **손상까지 조용해지지는 않는다** — 두 상태는 안내가 달라야 한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    graph_path_for(out_dir).write_bytes(b"not a sqlite file")  # 손상 흉내

    graph = app.handle("GET", "/api/dashboard", AUTH).json()["graph"]

    assert graph["error"] == "PreconditionError"
    assert "손상" in graph["message"]


def test_dashboard_opens_and_closes_the_store_per_request(
    app: GuiApp, out_dir: Path
) -> None:
    """요청마다 저장소를 열고 닫는다 (§4.4) — 커넥션을 요청 사이에 캐시하지 않는다.

    `ThreadingHTTPServer`는 요청마다 스레드가 다르고 코어의 sqlite 커넥션은
    `check_same_thread` 기본값으로 열린다. 캐시하면 **두 번째 요청부터**
    `sqlite3.ProgrammingError`(=버그, 500)가 난다. 스레드를 갈아 가며 두 번 부르면 그
    실패 모드가 그대로 재현되므로, 통과 자체가 「캐시하지 않았다」의 증거다.

    타이밍 의존이 아니다 — 두 호출은 순차이고 동기화 장치를 쓰지 않는다.
    """
    _seed_graph(out_dir)

    def _call() -> int:
        return app.handle("GET", "/api/dashboard", AUTH).status

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(_call).result()
    with ThreadPoolExecutor(max_workers=1) as pool:
        second = pool.submit(_call).result()

    assert (first, second) == (200, 200)


def test_dashboard_passes_core_defaults_to_diagnose(
    app: GuiApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUI는 값을 그대로 코어에 넘긴다 — 자체 기본값을 만들지 않는다 (§4.3.3)."""
    seen: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return environment.DoctorReport(
            installed=True, running=True, model=kwargs["model"], model_present=True,
            embed_model=kwargs["embed_model"], embed_model_present=True,
            available_models=[], hardware=HardwareInfo(gpu=False, label="CPU"),
            max_file_size=1, max_total_tokens=2,
        )

    monkeypatch.setattr("corpbrain.gui.api.diagnose", _spy)
    body = app.handle("GET", "/api/dashboard", AUTH).json()

    from corpbrain.core.config import (
        DEFAULT_EMBED_MODEL,
        DEFAULT_MODEL,
        DEFAULT_OLLAMA_URL,
    )

    assert seen["model"] == DEFAULT_MODEL
    assert seen["embed_model"] == DEFAULT_EMBED_MODEL
    assert seen["ollama_url"] == DEFAULT_OLLAMA_URL
    assert body["doctor"]["model"] == DEFAULT_MODEL


# --- 소켓 계층의 헤더 해석 (PR ① 자기 검토에서 발견) --------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 0), ("", 0), ("12", 12), ("abc", 0), ("-5", 0), ("1e3", 0), (" 7 ", 7)],
)
def test_content_length_never_raises_or_goes_negative(raw: str | None, expected: int) -> None:
    """`Content-Length` 해석이 요청 하나로 핸들러를 죽이지 않는다.

    `int()`를 그대로 쓰면 `Content-Length: abc` 가 `ValueError` 로 응답 없이 연결을 끊는다.
    음수는 `rfile.read(-1)` 이 EOF 까지 읽어 요청 스레드가 매달린다. 둘 다 요청의 잘못이지
    서버의 버그가 아니므로 본문을 빈 바이트로 보고 라우팅까지 보낸다.
    """
    from corpbrain.gui.httpd import _content_length

    assert _content_length(raw) == expected


def test_disconnect_errors_are_quiet_but_real_ones_are_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """상대가 떠나서 난 예외만 조용하다 — 「로그의 500이 버그 신호」를 지킨다 (§4.3.2).

    포그라운드로 떠 있는 서버라 브라우저가 탭을 닫을 때마다 트레이스백이 사용자 터미널을
    덮으면 안 된다. 그렇다고 전부 삼키면 진짜 버그가 보이지 않는다.
    """
    from corpbrain.gui.httpd import create_server

    server = create_server(tmp_path / "wiki")
    try:
        try:
            raise BrokenPipeError("client gone")
        except BrokenPipeError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert capsys.readouterr().err == ""

        try:
            raise ValueError("진짜 버그")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 1))
        assert "진짜 버그" in capsys.readouterr().err
    finally:
        server.server_close()


# --- keep-alive 프레이밍 (코드리뷰에서 실측으로 발견) --------------------------------


class _FakeHandler:
    """`_body()`만 떼어 시험하기 위한 최소 스텁 — 소켓을 열지 않는다."""

    def __init__(self, headers: dict[str, str], raw: bytes) -> None:
        self.headers = headers
        self.rfile = io.BytesIO(raw)
        self.close_connection = False

    _body = _Handler._body  # type: ignore[assignment]


def test_declared_body_is_drained_so_keep_alive_stays_aligned() -> None:
    """본문을 쓰지 않는 메서드도 선언된 바이트를 읽어야 한다.

    읽지 않으면 keep-alive 연결에 남아 **다음 요청의 요청줄로 파싱된다** — 실측에서 본문을
    실은 `DELETE` 뒤의 정상 요청이 깨졌다. `protocol_version = "HTTP/1.1"` 이라 연결이
    재사용되므로 이 구멍이 실재한다.
    """
    handler = _FakeHandler({"Content-Length": "7"}, b'{"a":1}GET / HTTP/1.1')

    assert handler._body() == b'{"a":1}'
    assert handler.rfile.read() == b"GET / HTTP/1.1"  # 다음 요청이 온전히 남는다
    assert handler.close_connection is False


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "abc"},
        {"Content-Length": "-5"},
        {"Transfer-Encoding": "chunked"},
    ],
)
def test_untrustworthy_framing_closes_the_connection(headers: dict[str, str]) -> None:
    """어디까지가 이 요청인지 모르면 응답 하나를 내고 연결을 끊는다.

    이어 쓰면 남은 바이트가 다음 요청으로 오독된다. 요청의 잘못이지 서버의 버그가 아니므로
    예외를 올리지 않고 정직하게 끊는다.
    """
    handler = _FakeHandler(headers, b"leftover bytes")

    assert handler._body() == b""
    assert handler.close_connection is True
