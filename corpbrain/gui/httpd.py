"""소켓 계층 — `ThreadingHTTPServer` 배선 (v0.9 스펙 §4.10 · §4.10.3).

이 모듈만 소켓을 안다. 요청 처리는 `api.GuiApp.handle()`이라는 **순수 함수**가 하고 여기서는
그것을 부르기만 한다 — 그래야 인증·라우팅·상태코드 단언이 소켓 없이 결정적으로 성립한다.

유일한 예외가 SSE다. 스트리밍은 응답 본문이 끝나지 않으므로 `Response.body`(항상 `bytes`)로
표현할 수 없어 여기서 직접 다룬다. 인증만은 같은 `GuiApp.authorize()`를 부르므로 경로가
둘로 갈리지 않는다 (§4.2).

**듣는 주소는 `127.0.0.1` 상수다.** 플래그로 바꿀 수 없다 (§2 「외부 노출」 비목표).
"""

from __future__ import annotations

import webbrowser
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from corpbrain.gui.api import (
    EVENTS_PATH,
    HOST,
    TOKEN_QUERY_PARAM,
    GuiApp,
    Response,
    new_token,
)
from corpbrain.gui.sse import SSE_CONTENT_TYPE, SSE_KEEPALIVE, format_sse

__all__ = ["GuiServer", "create_server", "serve"]

#: 이벤트가 없을 때 keepalive를 내는 주기(초). 값이 커지면 유휴 연결이 프록시에 끊기고,
#: 작아지면 의미 없는 프레임이 늘어난다. 브라우저 기본 유휴 한계보다 넉넉히 짧게 잡는다.
KEEPALIVE_INTERVAL = 15.0


class GuiServer(ThreadingHTTPServer):
    """`GuiApp`을 들고 있는 `ThreadingHTTPServer`.

    `daemon_threads`를 켜 두어 `Ctrl+C` 때 요청 스레드가 종료를 막지 않는다 — SSE 연결은
    정의상 끝나지 않으므로 이 설정이 없으면 서버가 내려가지 않는다.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, app: GuiApp) -> None:
        self.app = app
        super().__init__((HOST, app.port), _Handler)


class _Handler(BaseHTTPRequestHandler):
    """요청을 `GuiApp`에 넘기고 응답을 소켓에 쓴다 — 판정을 하지 않는다."""

    server_version = "CorpBrain"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def _app(self) -> GuiApp:
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # BaseHTTPRequestHandler 규약 이름이다
        raw_path, _, _ = self.path.partition("?")
        if raw_path == EVENTS_PATH:
            self._stream_events()
            return
        self._respond(self._app.handle("GET", self.path, dict(self.headers)))

    def do_POST(self) -> None:  # BaseHTTPRequestHandler 규약 이름이다
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        self._respond(self._app.handle("POST", self.path, dict(self.headers), body))

    def do_DELETE(self) -> None:  # BaseHTTPRequestHandler 규약 이름이다
        self._respond(self._app.handle("DELETE", self.path, dict(self.headers)))

    def log_message(self, format: str, *args: object) -> None:  # `format` 이름은 상위 클래스 규약이다
        """요청 로그를 내지 않는다 — 포그라운드 stdout이 진행 안내로 남아야 한다."""

    def _respond(self, response: Response) -> None:
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        for name, value in response.headers:
            self.send_header(name, value)
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    def _stream_events(self) -> None:
        """SSE — 접속 즉시 스냅샷 1건을 보내고 실시간 이벤트를 잇는다 (§4.3)."""
        refusal = self._app.authorize("GET", self.path, dict(self.headers))
        if refusal is not None:
            self._respond(refusal)
            return
        self.send_response(200)
        self.send_header("Content-Type", SSE_CONTENT_TYPE)
        self.send_header("Cache-Control", "no-store")
        # 스트림은 길이를 미리 알 수 없다 — `Content-Length` 대신 청크 없이 흘려보낸다.
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for chunk in self._frames():
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # 브라우저가 떠났다 — `EventSource`가 알아서 재연결한다

    def _frames(self) -> Iterator[str]:
        stream = self._app.events
        yield stream.current_frame()
        with stream.subscribe() as subscriber:
            while True:
                payload = subscriber.get(timeout=KEEPALIVE_INTERVAL)
                yield SSE_KEEPALIVE if payload is None else format_sse(payload)


def create_server(out_dir: Path) -> GuiServer:
    """서버를 만들고 **임의 포트**로 바인드한다 (§4.1).

    포트 0을 넘겨 OS가 빈 포트를 고르게 한 뒤, 실제로 바인드된 포트를 앱에 되돌려 준다 —
    `Origin`·`Host` 검증이 그 값에 의존하므로 서버 객체와 앱이 같은 값을 봐야 한다.
    """
    app = GuiApp(out_dir=out_dir, token=new_token(), port=0)
    server = GuiServer(app)
    app.port = server.server_address[1]
    return server


def start_url(app: GuiApp) -> str:
    """부트스트랩 토큰이 실린 첫 접속 URL."""
    return f"http://{HOST}:{app.port}/?{TOKEN_QUERY_PARAM}={app.token}"


def serve(out_dir: Path, *, open_browser: bool = True) -> None:
    """포그라운드로 서버를 띄운다. `Ctrl+C`로 종료한다 (§4.1)."""
    server = create_server(out_dir)
    url = start_url(server.app)
    print(f"CorpBrain GUI — {url}")
    print("종료하려면 Ctrl+C 를 누르세요.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
