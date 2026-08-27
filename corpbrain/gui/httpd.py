"""소켓 계층 — `ThreadingHTTPServer` 배선 (v0.9 스펙 §4.10 · §4.10.3).

이 모듈만 소켓을 안다. 요청 처리는 `api.GuiApp.handle()`이라는 **순수 함수**가 하고 여기서는
그것을 부르기만 한다 — 그래야 인증·라우팅·상태코드 단언이 소켓 없이 결정적으로 성립한다.

유일한 예외가 SSE다. 스트리밍은 응답 본문이 끝나지 않으므로 `Response.body`(항상 `bytes`)로
표현할 수 없어 여기서 직접 다룬다. 인증만은 같은 `GuiApp.authorize()`를 부르므로 경로가
둘로 갈리지 않는다 (§4.2).

**듣는 주소는 `127.0.0.1` 상수다.** 플래그로 바꿀 수 없다 (§2 「외부 노출」 비목표).
"""

from __future__ import annotations

import sys
import webbrowser
from collections.abc import Iterator
from contextlib import closing
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

    def handle_error(self, request: object, client_address: object) -> None:
        """연결이 끊겨서 난 예외는 조용히 넘기고, **나머지는 그대로 출력한다**.

        브라우저가 응답 도중 탭을 닫으면 `BrokenPipeError`가 나는데, 기본 구현은 그때마다
        트레이스백을 stderr에 찍는다 — 포그라운드로 떠 있는 서버라 사용자 터미널이 그 노이즈로
        덮인다. `log_message`를 죽여 둔 것과 같은 이유다.

        전부를 삼키지는 않는다. 「로그의 500이 그대로 버그 신호」(§4.3.2)가 성립하려면 진짜
        예외는 보여야 하고, 여기서 조용해지는 것은 **상대가 떠나서 난 것**뿐이다.
        """
        exc = sys.exc_info()[1]
        if isinstance(exc, BrokenPipeError | ConnectionResetError | TimeoutError):
            return
        super().handle_error(request, client_address)


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
        self._handle("GET")

    def do_POST(self) -> None:  # BaseHTTPRequestHandler 규약 이름이다
        self._handle("POST")

    def do_DELETE(self) -> None:  # BaseHTTPRequestHandler 규약 이름이다
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        """본문을 **반드시 배출한 뒤** 요청을 앱에 넘긴다.

        메서드가 본문을 쓰지 않더라도 읽어야 한다. `Content-Length`가 선언된 바이트를 읽지
        않으면 keep-alive 연결에 그대로 남아 **다음 요청의 요청줄로 파싱된다** — 실측에서
        본문을 실은 `DELETE` 뒤의 정상 요청이 깨졌다. `protocol_version = "HTTP/1.1"`이라
        연결이 재사용되므로 이 구멍이 실재한다.
        """
        self._respond(self._app.handle(method, self.path, dict(self.headers), self._body()))

    def _body(self) -> bytes:
        """선언된 길이만큼 본문을 읽는다. 프레이밍을 믿을 수 없으면 연결을 닫는다.

        길이를 해석하지 못했거나(`Content-Length: abc`) 청크 전송이면 **어디까지가 이
        요청인지 알 수 없다.** 그때 연결을 이어 쓰면 남은 바이트가 다음 요청으로 오독되므로,
        응답 하나를 정직하게 내고 연결을 끊는다 — 요청의 잘못이지 서버의 버그가 아니다.
        """
        raw = self.headers.get("Content-Length")
        if self.headers.get("Transfer-Encoding", "").strip().lower() == "chunked":
            self.close_connection = True
            return b""
        length = _content_length(raw)
        if raw is not None and length == 0 and raw.strip() not in {"", "0"}:
            self.close_connection = True
            return b""
        return self.rfile.read(length) if length else b""

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
        # `closing`으로 감싸 **구독 해제를 GC에 맡기지 않는다.** 브라우저가 떠나면 아래
        # `except`가 함수를 벗어나는데, 제너레이터가 즉시 닫히지 않으면 그 안의
        # `stream.subscribe()` 컨텍스트가 살아 있어 구독자(큐 하나)가 프로세스 수명 내내
        # 남는다. CPython 참조 계수가 대개 곧바로 닫아 주지만 그것은 구현 세부다.
        with closing(self._frames()) as frames:
            try:
                for chunk in frames:
                    self.wfile.write(chunk.encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return  # 브라우저가 떠났다 — `EventSource`가 알아서 재연결한다

    def _frames(self) -> Iterator[str]:
        # `attach()`로 **스냅샷과 구독을 한 번에** 잡는다. 스냅샷을 먼저 흘려보낸 뒤 구독하면
        # 그 사이에 방출된 이벤트가 어느 쪽에도 담기지 않아 영구히 사라진다 — 첫 프레임이
        # 소켓에 flush 되기를 기다리는 동안이 그 창이다.
        with self._app.events.attach() as (snapshot, subscriber):
            yield snapshot
            while True:
                payload = subscriber.get(timeout=KEEPALIVE_INTERVAL)
                yield SSE_KEEPALIVE if payload is None else format_sse(payload)


def _content_length(raw: str | None) -> int:
    """`Content-Length` 헤더를 길이로 바꾼다 — 해석할 수 없으면 0이다.

    `int()`를 그대로 쓰면 `Content-Length: abc` 하나가 `ValueError`로 핸들러를 죽인다(응답
    없이 연결이 끊긴다). 잘못된 헤더는 요청의 잘못이지 서버의 버그가 아니므로, 본문을 빈
    바이트로 보고 라우팅까지 보내 정상적인 4xx가 나가게 한다.

    음수도 0으로 접는다 — `rfile.read(-1)`은 EOF까지 읽어 요청 스레드가 매달린다.
    """
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


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
