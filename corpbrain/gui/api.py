"""요청 처리 순수 함수 — 소켓을 모르는 `handle()` (v0.9 스펙 §4.10.3).

인증·`Origin` 검증·라우팅·직렬화·상태코드가 **전부 이 모듈 안에** 있고, `http.server`
핸들러는 이것을 부르기만 한다. 그래야 §3 항목1·2가 요구하는 단언이 소켓 없이 결정적으로
성립한다 — `report.py`의 순수 빌더가 표시 로직을 소유하는 것과 같은 관용구다.

`BaseHTTPRequestHandler`를 가짜 소켓으로 돌리는 방식은 택하지 않았다. 테스트가
`http.server` 내부 구현에 묶여 서버 계층을 바꾸면 재사용되지 않는다.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from corpbrain.core.environment import DoctorReport, diagnose
from corpbrain.core.errors import CorpBrainError
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.models import GraphStats

__all__ = [
    "HOST",
    "JSON_CONTENT_TYPE",
    "SESSION_COOKIE",
    "TOKEN_QUERY_PARAM",
    "GuiApp",
    "Response",
    "json_response",
    "new_token",
    "response_for_exception",
]

JSON_CONTENT_TYPE = "application/json; charset=utf-8"

#: 듣는 주소 — 플래그로 바꿀 수 없다 (§2 「외부 노출」 비목표 · §4.1).
HOST = "127.0.0.1"
#: 부트스트랩 토큰이 실리는 쿼리 파라미터 이름.
TOKEN_QUERY_PARAM = "token"
#: 세션 쿠키 이름.
SESSION_COOKIE = "corpbrain_session"

#: 상태를 바꾸는 메서드 — `Origin` 헤더를 **필수**로 요구하는 쪽 (§4.2).
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def new_token() -> str:
    """기동 시 1회용 토큰을 만든다 — 파일에 쓰지 않고 프로세스 수명과 같이 간다 (§4.2)."""
    return secrets.token_urlsafe(32)


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

    def __init__(
        self,
        *,
        out_dir: Path,
        token: str,
        port: int,
        session_token: str | None = None,
    ) -> None:
        self.out_dir = out_dir
        #: URL 쿼리에 실려 브라우저에 전달되는 **부트스트랩** 토큰 (§4.2).
        self.token = token
        #: 부트스트랩과 **교환**되는 세션 쿠키 값. 별도 비밀을 쓰므로, 프론트엔드가
        #: `history.replaceState`로 URL을 지운 뒤에는 브라우저 히스토리·리퍼러에 남은
        #: 부트스트랩 토큰이 세션 값과 같지 않다.
        self.session_token = session_token or new_token()
        self.port = port

    @property
    def origin(self) -> str:
        """이 서버 자신의 오리진 — `Origin` 헤더가 일치해야 하는 값."""
        return f"http://{HOST}:{self.port}"

    @property
    def expected_host(self) -> str:
        """`Host` 헤더가 정확히 일치해야 하는 값 (DNS rebinding 방어)."""
        return f"{HOST}:{self.port}"

    # --- 인증·오리진 검증 (§4.2) ---------------------------------------------------

    def authorize(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str] | None = None,
    ) -> Response | None:
        """거절할 이유가 있으면 응답을, 없으면 `None`을 돌려준다.

        SSE 스트리밍 경로도 이 함수를 부른다 — 인증 경로를 둘로 나누지 않는다 (§4.2).
        """
        return self._authorize(_make_request(method, path, headers, b""))

    def _authorize(self, request: Request) -> Response | None:
        # ① `Host`는 **항상 필수**다. `Origin`과 달리 메서드로 가르지 않는 이유는 이것이
        #    CSRF가 아니라 **DNS rebinding**을 막기 때문이다 — 공격자 도메인이 127.0.0.1로
        #    해석되게 만든 뒤 보내는 요청은 조회든 변경이든 똑같이 막혀야 한다.
        if request.headers.get("host") != self.expected_host:
            return _refused(403)

        # ② 토큰 — 같은 머신의 다른 프로세스를 가른다. 세션 쿠키 또는 부트스트랩 쿼리.
        if not self._has_valid_credential(request):
            return _refused(401)

        # ③ `Origin` — 브라우저발 CSRF를 가른다. **상태를 바꾸는 메서드에서만 필수**이고
        #    조회 GET에서는 부재를 허용한다. 브라우저가 최상위 GET 내비게이션에 이 헤더를
        #    붙이지 않으므로, 「없음 = 403」으로 구현하면 기동 시 여는 첫 화면이 서버
        #    자신에게 막힌다 (§4.2).
        origin = request.headers.get("origin")
        if origin is None:
            return _refused(403) if request.method in UNSAFE_METHODS else None
        if origin != self.origin:
            return _refused(403)
        return None

    def _has_valid_credential(self, request: Request) -> bool:
        session = _cookie_value(request.headers.get("cookie", ""), SESSION_COOKIE)
        if session is not None and secrets.compare_digest(session, self.session_token):
            return True
        return self._is_bootstrap(request)

    def _is_bootstrap(self, request: Request) -> bool:
        """부트스트랩 쿼리 토큰이 실려 있고 값이 맞는가."""
        supplied = request.query.get(TOKEN_QUERY_PARAM)
        return supplied is not None and secrets.compare_digest(supplied, self.token)

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
        request = _make_request(method, path, headers, body)
        refusal = self._authorize(request)
        if refusal is not None:
            return refusal
        try:
            response = self._dispatch(request)
        except Exception as exc:  # noqa: BLE001 — 매핑 규칙이 종류를 가른다
            response = response_for_exception(exc)
        if self._is_bootstrap(request):
            # 부트스트랩 토큰을 **세션 쿠키로 교환**한다 (§4.2). 쿠키는 `fetch`와
            # `EventSource`가 자동으로 함께 나르므로 인증 경로가 하나로 유지된다 —
            # `EventSource`는 커스텀 헤더를 붙일 수 없어 `Authorization` 방식은 SSE
            # 하나에서 깨진다.
            response = _with_session_cookie(response, self.session_token)
        return response

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
        """대시보드 — Doctor 카드와 그래프 지표 (§4.3).

        두 절(`doctor`·`graph`)은 **각각 독립적으로** 도메인 상태를 담을 수 있다. 한쪽이
        선행 조건 실패여도 다른 쪽 카드는 실제 값으로 그려져야 하기 때문이다 — 첫 실행에서
        그래프 DB가 없는 것은 정상이고(§5), 그때 Doctor 카드까지 사라지면 사용자는 「무엇을
        먼저 해야 하는가」를 볼 곳이 없다.

        절의 모양은 **성공 payload 또는 `{error, message}`** 둘 중 하나로 통일한다 —
        프론트는 `"error" in section` 하나로 가른다.
        """
        return json_response(
            {
                "out_dir": str(self.out_dir),
                "doctor": _section(self._doctor_payload),
                "graph": _section(self._graph_payload),
            }
        )

    def _doctor_payload(self) -> dict[str, Any]:
        return _doctor_dict(
            diagnose(
                model=DEFAULT_MODEL,
                embed_model=DEFAULT_EMBED_MODEL,
                ollama_url=DEFAULT_OLLAMA_URL,
            )
        )

    def _graph_payload(self) -> dict[str, Any]:
        """**요청마다 저장소를 열고 `finally`에서 닫는다** (§4.4).

        커넥션을 요청 사이에 캐시하지 않는다 — 코어의 sqlite 커넥션은 `check_same_thread`
        기본값으로 열리고 `ThreadingHTTPServer`는 요청마다 스레드가 다르므로, 캐시하면
        두 번째 요청부터 `sqlite3.ProgrammingError`(=버그, 500)가 난다.

        조회이므로 `read_only=True`로 연다 — 파일에 쓰지 않고, 스키마가 소실된 DB를
        되만들지 않는다 (v0.6.1 결정 계승).
        """
        store = SqliteGraphStore(graph_path_for(self.out_dir), read_only=True)
        try:
            return _stats_dict(store.stats())
        finally:
            store.close()


def _section(build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """한 절을 만들되, **도메인 상태는 그 절 안에 담고** 버그는 그대로 올린다.

    매핑 규칙을 여기서 다시 쓰지 않고 `response_for_exception`의 판정을 그대로 쓴다 —
    「`CorpBrainError`면 도메인, 아니면 버그」가 코드에 한 번만 적힌다 (§4.3.2).
    """
    try:
        return build()
    except Exception as exc:  # 아래에서 도메인/버그를 갈라 되올린다
        response = response_for_exception(exc)
        if response.status != 200:
            raise
        return response.json()


def _doctor_dict(report: DoctorReport) -> dict[str, Any]:
    """`DoctorReport`를 화면이 쓰는 필드로 편다.

    프론트는 이 불리언들로 배지를 그린다. `report.py`의 줄 빌더를 그대로 싣지 않는 이유는
    §4.6.1의 원칙 그대로다 — 갈라지면 안 되는 것은 「어휘」이지 「줄 조립」이 아니고, 여기서
    지킬 특수 어휘(v0.7이 정확 문자열로 못박은 근거 줄 같은 것)가 없다.
    """
    return {
        "installed": report.installed,
        "running": report.running,
        "model": report.model,
        "model_present": report.model_present,
        "embed_model": report.embed_model,
        "embed_model_present": report.embed_model_present,
        "available_models": list(report.available_models),
        "hardware": {"gpu": report.hardware.gpu, "label": report.hardware.label},
        "max_file_size": report.max_file_size,
        "max_total_tokens": report.max_total_tokens,
        "cloud_consent": report.cloud_consent,
        "cloud_api_key": report.cloud_api_key,
        "cloud_ready": report.cloud_ready,
        "ready": report.ready,
    }


def _stats_dict(stats: GraphStats) -> dict[str, Any]:
    """`GraphStats`를 화면이 쓰는 필드로 편다 — 합계는 코어의 property를 그대로 쓴다."""
    return {
        "documents": stats.documents,
        "entities": stats.entities,
        "tags": stats.tags,
        "nodes": stats.nodes,
        "edges": stats.edges,
        "edges_by_type": {str(key): value for key, value in stats.edges_by_type.items()},
    }


def _refused(status: int) -> Response:
    """거절 응답 — 이유를 자세히 적지 않는다 (§5)."""
    if status == 401:
        return error_response("Unauthorized", "인증되지 않은 요청입니다.", status=401)
    return error_response("Forbidden", "허용되지 않은 요청입니다.", status=403)


def _with_session_cookie(response: Response, session_token: str) -> Response:
    """`HttpOnly` · `SameSite=Strict` · `Secure` 없음(`http://127.0.0.1`) (§4.2)."""
    cookie = (
        f"{SESSION_COOKIE}={session_token}; Path=/; HttpOnly; SameSite=Strict"
    )
    return Response(
        status=response.status,
        body=response.body,
        content_type=response.content_type,
        headers=(*response.headers, ("Set-Cookie", cookie)),
    )


def _cookie_value(header: str, name: str) -> str | None:
    """`Cookie` 헤더에서 값 하나를 꺼낸다. 파싱 불가·부재면 `None`."""
    if not header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header)
    except Exception:  # noqa: BLE001 — 깨진 쿠키는 '자격 없음'으로 수렴한다
        return None
    morsel = jar.get(name)
    return morsel.value if morsel is not None else None


def _make_request(
    method: str, path: str, headers: Mapping[str, str] | None, body: bytes
) -> Request:
    """헤더 이름을 소문자로 정규화하고 경로에서 쿼리를 떼어낸다."""
    raw_path, _, raw_query = path.partition("?")
    return Request(
        method=method.upper(),
        path=raw_path,
        query=_parse_query(raw_query),
        headers={str(key).lower(): value for key, value in (headers or {}).items()},
        body=body,
    )


def _parse_query(raw: str) -> dict[str, str]:
    """쿼리 문자열을 dict로 — 같은 키가 여러 번이면 첫 값을 쓴다."""
    parsed: dict[str, str] = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        parsed.setdefault(key, value)
    return parsed
