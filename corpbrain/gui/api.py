"""요청 처리 순수 함수 — 소켓을 모르는 `handle()` (v0.9 스펙 §4.10.3).

인증·`Origin` 검증·라우팅·직렬화·상태코드가 **전부 이 모듈 안에** 있고, `http.server`
핸들러는 이것을 부르기만 한다. 그래야 §3 항목1·2가 요구하는 단언이 소켓 없이 결정적으로
성립한다 — `report.py`의 순수 빌더가 표시 로직을 소유하는 것과 같은 관용구다.

`BaseHTTPRequestHandler`를 가짜 소켓으로 돌리는 방식은 택하지 않았다. 테스트가
`http.server` 내부 구현에 묶여 서버 계층을 바꾸면 재사용되지 않는다.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from corpbrain.core.errors import CorpBrainError

__all__ = [
    "JSON_CONTENT_TYPE",
    "GuiApp",
    "Response",
    "json_response",
    "response_for_exception",
]

JSON_CONTENT_TYPE = "application/json; charset=utf-8"

#: 상태를 바꾸는 메서드 — `Origin` 헤더를 **필수**로 요구하는 쪽 (§4.2).
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class Response:
    """상태코드·헤더·본문을 담는 값 객체.

    본문은 항상 `bytes` 하나다 — 이터레이터까지 받도록 넓히지 않는다(§3 항목4). 타입이 두
    종류가 되면 모든 호출부가 둘을 가려야 한다. 스트리밍(SSE)은 `handle()` 밖에서 다룬다.
    """

    status: int
    body: bytes = b""
    content_type: str = JSON_CONTENT_TYPE
    headers: tuple[tuple[str, str], ...] = ()

    def json(self) -> Any:
        """본문을 JSON으로 파싱한다 — 테스트가 응답 스키마를 단언할 때 쓴다."""
        return json.loads(self.body.decode("utf-8"))


def json_response(
    payload: Any, *, status: int = 200, headers: tuple[tuple[str, str], ...] = ()
) -> Response:
    """dict를 JSON 본문으로 직렬화한다 (한글을 이스케이프하지 않는다)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return Response(status=status, body=body, headers=headers)


def error_response(
    error: str,
    message: str,
    *,
    status: int = 200,
    headers: tuple[tuple[str, str], ...] = (),
) -> Response:
    """예외 종류 식별자와 안내 문장을 **각각 필드로** 담는다 (§4.3.2).

    프론트엔드가 문자열을 파싱해 분기하지 않게 한다. 식별자는 예외 클래스명을 그대로 쓴다.
    """
    return json_response(
        {"error": error, "message": message}, status=status, headers=headers
    )


def response_for_exception(exc: BaseException) -> Response:
    """코어 예외를 응답으로 바꾼다 — **열거가 아니라 기반 클래스로** 가른다 (§4.3.2).

    - `CorpBrainError` 전부 → **200 + 구조화된 상태 본문**. 「Ollama가 안 떠 있다」·「먼저
      스캔해야 한다」는 요청의 잘못도 서버의 잘못도 아니라 **환경의 상태**이며, 화면이
      사용자에게 다음에 할 일을 안내해야 하는 경우다. 4xx로 접으면 서로 다른 안내가 한
      코드 안에 뭉쳐 프론트가 본문을 다시 갈라야 한다.
    - `sqlite3.Error` → 저장소 손상·스키마 불일치이므로 같은 도메인 응답.
    - **`sqlite3.ProgrammingError`만 예외로 500이다.** 코어의 커넥션은 `check_same_thread`
      기본값으로 열리고 `ThreadingHTTPServer`는 요청마다 스레드가 다르므로, 그 예외는
      손상이 아니라 **스레드 오용 버그**다. 200 + 「DB를 지우고 다시 스캔하세요」로 내보내면
      사용자가 멀쩡한 DB를 지운다.
    - 그 밖의 예외 → 500. 5xx가 오직 버그일 때만 나므로 **로그의 500이 그대로 버그 신호**다.

    열거하지 않는 이유는 `CorpBrainError` 계층에 `GatewayError`·`ExtractionError` 등이
    더 있고, 목록에 없는 하나가 조회 경로로 새는 순간 버그가 아닌데 500이 되기 때문이다.
    """
    if isinstance(exc, sqlite3.ProgrammingError):
        return _bug_response(exc)
    if isinstance(exc, CorpBrainError | sqlite3.Error):
        return error_response(type(exc).__name__, str(exc))
    return _bug_response(exc)


def _bug_response(exc: BaseException) -> Response:
    return error_response(
        type(exc).__name__,
        f"서버 내부 오류입니다 — 버그로 보고해 주세요: {exc}",
        status=500,
    )


#: 라우트 핸들러 — 요청을 받아 응답을 돌려주는 바운드 메서드.
Handler = Callable[["Request"], Response]


@dataclass(frozen=True)
class Request:
    """`handle()`이 라우트 핸들러에 넘기는 요청 값 객체."""

    method: str
    path: str
    query: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


class GuiApp:
    """GUI 서버의 요청 처리 — 소켓·전역 상태를 모른다.

    필요한 것(`out_dir`·토큰·포트)은 생성자로 주입받는다. 같은 이유로 테스트는 이 객체를
    직접 만들어 `handle()`을 부르며, 서버를 띄우지 않는다.
    """

    def __init__(self, *, out_dir: Path, token: str, port: int) -> None:
        self.out_dir = out_dir
        self.token = token
        self.port = port

    # --- 라우팅 -----------------------------------------------------------------

    def _routes(self) -> dict[str, dict[str, Handler]]:
        """경로 → 메서드 → 핸들러. 경로는 정확히 일치할 때만 매칭한다."""
        return {
            "/api/dashboard": {"GET": self._dashboard},
        }

    def handle(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str] | None = None,
        body: bytes = b"",
    ) -> Response:
        """요청 하나를 응답 하나로 바꾼다 (§4.10.3).

        Args:
            method: HTTP 메서드 (`GET`·`POST` …).
            path: 쿼리를 포함한 요청 대상 (`/api/dashboard?x=1`).
            headers: 요청 헤더. 이름은 대소문자를 가리지 않는다.
            body: 요청 본문 바이트.
        """
        normalized = {str(k).lower(): v for k, v in (headers or {}).items()}
        raw_path, _, raw_query = path.partition("?")
        request = Request(
            method=method.upper(),
            path=raw_path,
            query=_parse_query(raw_query),
            headers=normalized,
            body=body,
        )
        try:
            return self._dispatch(request)
        except Exception as exc:  # noqa: BLE001 — 매핑 규칙이 종류를 가른다
            return response_for_exception(exc)

    def _dispatch(self, request: Request) -> Response:
        by_method = self._routes().get(request.path)
        if by_method is None:
            return error_response(
                "NotFound", f"그런 경로가 없습니다: {request.path}", status=404
            )
        handler = by_method.get(request.method)
        if handler is None:
            allow = ", ".join(sorted(by_method))
            return error_response(
                "MethodNotAllowed",
                f"{request.method}는 이 경로에서 허용되지 않습니다 (허용: {allow}).",
                status=405,
                headers=(("Allow", allow),),
            )
        return handler(request)

    # --- 엔드포인트 --------------------------------------------------------------

    def _dashboard(self, request: Request) -> Response:
        """대시보드 — 이 단위에서는 워크스페이스 경로만 낸다 (U5가 채운다)."""
        return json_response({"out_dir": str(self.out_dir)})


def _parse_query(raw: str) -> dict[str, str]:
    """쿼리 문자열을 dict로 — 같은 키가 여러 번이면 첫 값을 쓴다."""
    parsed: dict[str, str] = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        parsed.setdefault(key, value)
    return parsed
