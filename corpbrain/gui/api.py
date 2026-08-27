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

from corpbrain.core.config import (
    DEFAULT_EMBED_MODEL,
    DEFAULT_GRAPH_DECAY,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
)
from corpbrain.core.configstore import default_config_path, read_section, update_section
from corpbrain.core.consent import (
    grant_cloud_consent,
    is_cloud_consent_granted,
    revoke_cloud_consent,
)
from corpbrain.core.embedding_text import parse_wiki_document
from corpbrain.core.environment import DoctorReport, diagnose
from corpbrain.core.errors import CorpBrainError
from corpbrain.core.graph import parse_expand_edges
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.models import (
    GraphStats,
    NodeType,
    ScanPlan,
    ScanResult,
    SearchResult,
    WikiDocument,
)
from corpbrain.core.pii import PiiType
from corpbrain.core.pipeline import collect_wiki_documents
from corpbrain.core.report import build_expansion_evidence, build_summary_lines
from corpbrain.core.rerun import read_source_path
from corpbrain.core.scanner import ScanFindings
from corpbrain.core.search import search_index
from corpbrain.gui.assets import AssetNotFound, content_type_for, read_asset
from corpbrain.gui.errors import (
    BadRequest,
    GraphNotBuilt,
    NothingScanned,
    WikiNotFound,
)
from corpbrain.gui.scan import (
    Measurement,
    ScanController,
    ScanInProgressError,
    config_from_payload,
)
from corpbrain.gui.sse import EventStream

__all__ = [
    "EVENTS_PATH",
    "HOST",
    "JSON_CONTENT_TYPE",
    "SESSION_COOKIE",
    "TOKEN_QUERY_PARAM",
    "BadRequest",
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
#: 진행 스트림(SSE) 경로. **`handle()`의 라우트 표에 없다** — 스트리밍은 소켓 계층이
#: 가로채 처리한다(§3 항목4: `Response.body`를 이터레이터까지 받도록 넓히지 않는다).
#: 인증은 그 계층도 `GuiApp.authorize()`를 부르므로 경로가 갈리지 않는다 (§4.2).
EVENTS_PATH = "/api/events"
#: 정적 자산 경로 접두사. 하위 디렉터리를 두지 않는다 — 경로 조립이 없으면 트래버설도 없다.
ASSETS_PREFIX = "/assets/"
#: 기동 시 여는 첫 화면.
INDEX_ASSET = "index.html"
#: `~/.corpbrain/config.json`에서 GUI가 쓰는 섹션 키 (§4.8). 클라우드 동의 섹션과
#: 나란히 두며, 새 설정 파일을 만들지 않는다 — 사용자가 어디를 봐야 하는지 헷갈리지
#: 않게 하고 코어의 기존 읽기·쓰기 관용구를 그대로 쓴다.
GUI_SECTION = "gui"

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
    - `BadRequest` → **400**. 요청 본문이 이 엔드포인트의 모양이 아니다 — 404·405와 같은
      프로토콜 층 사건이다.
    - 그 밖의 예외 → 500. 5xx가 오직 버그일 때만 나므로 **로그의 500이 그대로 버그 신호**다.

    열거하지 않는 이유는 `CorpBrainError` 계층에 `GatewayError`·`ExtractionError` 등이
    더 있고, 목록에 없는 하나가 조회 경로로 새는 순간 버그가 아닌데 500이 되기 때문이다.
    """
    if isinstance(exc, BadRequest):
        return error_response(type(exc).__name__, str(exc), status=400)
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
        events: EventStream | None = None,
        scan: ScanController | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.out_dir = out_dir
        #: 진행 상태의 단일 출처. 스캔 상태는 서버가 소유하고 브라우저 세션이 소유하지
        #: 않으므로(§4.4) 이 객체가 앱 수명과 같이 간다.
        self.events = events or EventStream()
        #: URL 쿼리에 실려 브라우저에 전달되는 **부트스트랩** 토큰 (§4.2).
        self.token = token
        #: 부트스트랩과 **교환**되는 세션 쿠키 값. 별도 비밀을 쓰므로, 프론트엔드가
        #: `history.replaceState`로 URL을 지운 뒤에는 브라우저 히스토리·리퍼러에 남은
        #: 부트스트랩 토큰이 세션 값과 같지 않다.
        self.session_token = session_token or new_token()
        self.port = port
        #: 스캔 상태의 단일 출처 (§4.4). 워커 스레드는 하나뿐이며, 진행 중에 들어온 새 스캔
        #: 요청은 409로 거절된다.
        self.scan = scan or ScanController(self.events)
        #: 설정 파일 경로. 테스트가 사용자의 실제 `~/.corpbrain/config.json`을 건드리지
        #: 않도록 주입 이음새를 코어와 같은 모양으로 둔다.
        self.config_path = config_path or default_config_path()

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
        if session is not None and _matches(session, self.session_token):
            return True
        return self._is_bootstrap(request)

    def _is_bootstrap(self, request: Request) -> bool:
        """부트스트랩 쿼리 토큰이 실려 있고 값이 맞는가."""
        supplied = request.query.get(TOKEN_QUERY_PARAM)
        return supplied is not None and _matches(supplied, self.token)

    # --- 라우팅 -----------------------------------------------------------------

    def _routes(self) -> dict[str, dict[str, Handler]]:
        """경로 → 메서드 → 핸들러. 경로는 정확히 일치할 때만 매칭한다."""
        return {
            "/api/dashboard": {"GET": self._dashboard},
            "/api/scan": {"GET": self._scan_status, "POST": self._scan_run},
            "/api/scan/plan": {"POST": self._scan_plan},
            "/api/scan/cancel": {"POST": self._scan_cancel},
            "/api/wiki": {"GET": self._wiki_tree},
            "/api/wiki/document": {"GET": self._wiki_document},
            "/api/graph": {"GET": self._graph},
            "/api/search": {"GET": self._search},
            "/api/settings": {"GET": self._settings, "POST": self._settings_update},
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
        # 인증 검사도 **이 `try` 안에서** 돈다. 밖에 두면 자격 검증이 예외를 올릴 때
        # 응답이 아예 나가지 않고 핸들러가 죽는다 — 500 보다 나쁜 결과이며, 매핑 규칙
        # (§4.3.2)이 닿지 못하는 구멍이 하나 생긴다.
        try:
            refusal = self._authorize(request)
            if refusal is not None:
                return refusal
            response = self._dispatch(request)
            if self._is_bootstrap(request):
                # 부트스트랩 토큰을 **세션 쿠키로 교환**한다 (§4.2). 쿠키는 `fetch`와
                # `EventSource`가 자동으로 함께 나르므로 인증 경로가 하나로 유지된다 —
                # `EventSource`는 커스텀 헤더를 붙일 수 없어 `Authorization` 방식은 SSE
                # 하나에서 깨진다.
                response = _with_session_cookie(response, self.session_token)
            return response
        except Exception as exc:  # noqa: BLE001 — 매핑 규칙이 종류를 가른다
            return response_for_exception(exc)

    def _dispatch(self, request: Request) -> Response:
        if request.path == "/" or request.path.startswith(ASSETS_PREFIX):
            return self._asset(request)
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

    def _asset(self, request: Request) -> Response:
        """정적 자산 — 프론트엔드는 빌드 스텝이 없어 파일이 그대로 나간다 (§4.10)."""
        if request.method != "GET":
            return error_response(
                "MethodNotAllowed",
                f"{request.method}는 이 경로에서 허용되지 않습니다 (허용: GET).",
                status=405,
                headers=(("Allow", "GET"),),
            )
        name = (
            INDEX_ASSET
            if request.path == "/"
            else request.path[len(ASSETS_PREFIX) :]
        )
        try:
            body = read_asset(name)
        except AssetNotFound:
            return error_response(
                "NotFound", f"그런 자산이 없습니다: {name}", status=404
            )
        return Response(status=200, body=body, content_type=content_type_for(name))

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

    # --- 스캔 (§4.3.4 계량 → 확인 → 실행) -----------------------------------------

    def _scan_plan(self, request: Request) -> Response:
        """1단계 계량 — `plan_scan()`을 부르고 LLM은 부르지 않는다.

        폴더를 고르는 즉시 자동으로 불리지 않는다(§4.3.4) — 이 엔드포인트는 사용자가
        「계량하기」를 눌렀을 때만 호출된다. `plan_scan()`은 `nvidia-smi` subprocess와 전체
        stat 패스를 돌리므로, 폴더를 둘러보는 동안 반복되면 탐색이 느려진다.
        """
        payload = _json_body(request)
        config = config_from_payload(payload, default_out=self.out_dir)
        return json_response(_measurement_dict(self.scan.measure(config)))

    def _scan_run(self, request: Request) -> Response:
        """2단계 실행 — 계량 결과 화면에서 눌러야 시작된다.

        진행 중이면 **409**다(§4.4). 이것은 프로토콜 층 사건이라 도메인(200)으로 접지
        않는다 — 화면이 「시작됐다」와 「이미 돌고 있다」를 같은 코드로 받으면 안 된다.
        """
        payload = _json_body(request)
        config = config_from_payload(payload, default_out=self.out_dir)
        try:
            self.scan.start(config)
        except ScanInProgressError as exc:
            return error_response("ScanInProgress", str(exc), status=409)
        return json_response(self._scan_state())

    def _scan_cancel(self, request: Request) -> Response:
        """취소 요청 — 진행 중인 문서를 마친 뒤 멈춘다 (§4.7).

        진행 중이 아니어도 오류가 아니다. 취소는 **요청**이고, 이미 끝난 스캔에 대한 요청은
        아무 일도 하지 않는 것이 옳다 — 화면과 서버 사이의 경합(마지막 문서가 끝나는 순간
        누른 취소)을 오류로 만들면 사용자가 아무것도 잘못하지 않았는데 오류를 본다.
        """
        self.scan.cancel()
        return json_response(self._scan_state())

    def _scan_status(self, request: Request) -> Response:
        """현재 스캔 상태 + 마지막 결과. 새로고침·다른 탭이 진행 중인 스캔에 다시 붙는 길이다."""
        return json_response(self._scan_state())

    def _scan_state(self) -> dict[str, Any]:
        failure = self.scan.failure
        return {
            "running": self.scan.running,
            "cancel_requested": self.scan.cancel_requested,
            "plan": (
                _measurement_dict(self.scan.measurement)
                if self.scan.measurement is not None
                else None
            ),
            "result": (
                _result_dict(self.scan.result) if self.scan.result is not None else None
            ),
            # 워커 스레드에서 죽은 예외도 같은 매핑 규칙(§4.3.2)으로 가른다. 도메인이면
            # 안내 문장이 되고, 버그면 여기서 다시 올라가 500이 된다.
            "failure": _section(_reraise(failure)) if failure is not None else None,
        }

    # --- 설정 (§4.8 · §4.9 · §4.11) --------------------------------------------------

    def _settings(self, request: Request) -> Response:
        """엔진·클라우드 동의·마스킹 유형·GUI 설정 (§4.8 · §4.9).

        **API 키를 다루지 않는다** — 키는 `ANTHROPIC_API_KEY` 환경변수로만 읽는다(§4.9).
        GUI가 키를 받으면 그 값이 HTTP 바디로 오가고 서버 프로세스가 키를 쥐게 되어 경계가
        넓어진다. 여기서 내보내는 것은 「설정되어 있는가」라는 **불리언 하나**뿐이다.
        """
        return json_response(
            {
                "config_path": str(self.config_path),
                "cloud_consent": _section(self._consent_payload),
                # 코어 `PiiType` **7종**을 그대로 낸다 — 목업이 6종이었고 라벨·플레이스홀더도
                # 어긋나 있었다 (§4.11). 프론트가 자기 목록을 갖지 않는다.
                "pii_types": [
                    {
                        "name": str(kind),
                        "label": kind.label,
                        "placeholder": kind.placeholder,
                    }
                    for kind in PiiType
                ],
                "gui": read_section(self.config_path, GUI_SECTION),
            }
        )

    def _consent_payload(self) -> dict[str, Any]:
        return {"granted": is_cloud_consent_granted(config_path=self.config_path)}

    def _settings_update(self, request: Request) -> Response:
        """동의 토글과 `gui` 섹션 저장 (§4.8).

        쓰기는 코어의 공유 헬퍼를 그대로 쓴다 — 「재읽기 → 자기 섹션만 교체 → 임시파일 후
        `rename`」. 두 어댑터가 한 파일을 쓰므로 「읽기 → 수정 → 통째로 쓰기」는 나중에 쓴
        쪽이 상대 섹션을 날리고, 동의가 조용히 철회되면 클라우드 스캔이 막히면서 원인이
        드러나지 않는다.
        """
        payload = _json_body(request)
        consent = payload.get("cloud_consent")
        if consent is not None:
            if consent:
                grant_cloud_consent(config_path=self.config_path)
            else:
                revoke_cloud_consent(config_path=self.config_path)
        gui = payload.get("gui")
        if gui is not None:
            if not isinstance(gui, dict):
                raise BadRequest("`gui`는 JSON 객체여야 합니다.")
            update_section(self.config_path, GUI_SECTION, lambda current: {**current, **gui})
        return self._settings(request)

    # --- 지식 검색 (§4.6.1) ----------------------------------------------------------

    def _search(self, request: Request) -> Response:
        """코사인 + 그래프 확산 검색 (§4.6.1).

        **검증을 자체적으로 두지 않는다** (§4.3.3). `graph_decay`의 범위와 `expand_edges`의
        문법은 코어가 판정하고, 그 실패는 `PreconditionError`라 도메인(200 + 안내 문장)으로
        나간다 — v0.7 §4.4가 「규칙이 한 곳에만 있어야 코어를 직접 부르는 후속 어댑터도 같은
        보호를 받는다」고 정한 그 후속 어댑터가 이 GUI다.
        """
        query = request.query.get("q", "").strip()
        if not query:
            raise BadRequest("검색어를 입력하세요 (`q`).")
        expand_raw = request.query.get("expand_edges", "")
        results = search_index(
            self.out_dir,
            query,
            top_k=_as_int(request.query.get("top_k"), default=5),
            ollama_url=request.query.get("ollama_url") or DEFAULT_OLLAMA_URL,
            # 문자열 `"false"`가 참이 되는 실수를 막는다 — 프론트는 `graph=false`를 보낸다.
            graph=request.query.get("graph", "true").lower() != "false",
            graph_decay=_as_float(
                request.query.get("graph_decay"), default=DEFAULT_GRAPH_DECAY
            ),
            **(
                {"expand_edges": parse_expand_edges(expand_raw)} if expand_raw else {}
            ),
        )
        return json_response({"query": query, "results": [_result_row(r) for r in results]})

    # --- 지식그래프 (§4.3.1) ---------------------------------------------------------

    def _graph(self, request: Request) -> Response:
        """전체 노드와 엣지 (§4.3.1).

        노드는 기존 계약으로 얻는다 — 엣지만 `iter_edges()`가 필요했고, 그래서 계약이
        10 → 11멤버가 됐다.

        **`degree_ranking()`은 `Document` 노드만 준다** (v0.6 §4.7 `--central`이 문서 목록이라
        그렇게 정의됐다). 스펙 §4.3.1은 그것이 「전 노드 id를 준다」고 적었으나 사실이 아니며,
        그대로 믿고 짜면 `Entity`·`Tag` 노드가 통째로 빠진 그래프가 그려진다(실측 확인).
        전 노드는 **`degree_ranking()`의 문서 ∪ 엣지 끝점**으로 얻는다 — `Entity`·`Tag`
        노드는 문서가 그것을 가리켜야만 존재하므로 반드시 어떤 엣지의 끝점이고, 엣지가 하나도
        없는 고립 문서는 `degree_ranking()`이 담는다. 두 집합의 합이 곧 전 노드다.

        계약을 더 넓히지 않는다 — 이 길이 이미 있으므로 12번째 멤버를 만들 이유가 없다.

        **규모 상한·필터·차수 추림을 두지 않는다** — 4종 노드를 제한 없이 전부 그리며,
        대규모에서 느려지는 것은 §5가 명시한 알려진 한계이자 issue #58로 분리돼 있다.
        여기서 조용히 잘라 내면 화면이 「이게 전부」라고 말하면서 아닌 것을 보여 준다.
        """
        path = graph_path_for(self.out_dir)
        if not path.exists():
            raise GraphNotBuilt(
                "아직 스캔하지 않았습니다 — 먼저 스캔하면 지식그래프가 채워집니다."
            )
        store = SqliteGraphStore(path, read_only=True)
        try:
            edges = list(store.iter_edges())
            node_ids = {node_id for node_id, _degree in store.degree_ranking()}
            for edge in edges:
                node_ids.add(edge.src)
                node_ids.add(edge.dst)
            nodes = store.nodes_of(sorted(node_ids))
            stats = store.stats()
        finally:
            store.close()
        # 차수는 **엣지에서 센다** — `degree_ranking()`은 문서만 담아 `Entity`·`Tag`가 전부
        # 0이 되고, 화면이 노드 크기를 그것으로 정하므로 허브 태그가 가장 작게 그려진다.
        # 문서의 값은 어차피 같다(둘 다 닿는 엣지 수).
        degrees: dict[str, int] = {node_id: 0 for node_id in node_ids}
        for edge in edges:
            degrees[edge.src] = degrees.get(edge.src, 0) + 1
            degrees[edge.dst] = degrees.get(edge.dst, 0) + 1
        return json_response(
            {
                "stats": _stats_dict(stats),
                "nodes": [
                    {
                        # 노드 종류는 코어 `NodeType` 값을 **그대로** 쓴다 — 프론트가 자기
                        # 리터럴을 가지면 어휘가 갈린다 (§4.11).
                        "id": node.id,
                        "type": str(node.type),
                        "label": node.label,
                        "degree": degrees.get(node.id, 0),
                    }
                    for node in sorted(nodes.values(), key=lambda node: node.id)
                ],
                "edges": [
                    {
                        # 엣지 종류도 `EdgeType` 값 그대로 — `graph --stats` 출력·DB의 type
                        # 컬럼·`--expand-edges` 플래그와 한 문자열이어야 한다 (§4.11).
                        "src": edge.src,
                        "dst": edge.dst,
                        "type": str(edge.type),
                        "weight": edge.weight,
                    }
                    for edge in edges
                ],
            }
        )

    # --- 위키 (§4.6 · §4.6.2) -------------------------------------------------------

    def _wiki_tree(self, request: Request) -> Response:
        """트리 — **제목은 그래프 `nodes.label`에서 얻는다** (§4.6.2).

        `degree_ranking()`으로 전 노드 id를 받아 `nodes_of()`로 `Document` 노드의 라벨을
        가져온다. sqlite 조회 2번이고 위키 파일을 하나도 열지 않는다. 라벨 선택 규칙은
        `build_graph()` 한 곳에만 있고 조회는 저장된 값을 읽는다(v0.6.1 결정 계승) — 같은
        문서가 화면마다 다른 제목으로 불리지 않는다.

        **그래프가 없으면 파일명으로 대체하고 그 사실을 알린다** — §4.6.2의 파생 결정이다.
        이 fallback 이 제목을 «파싱»하지 않는다는 점이 중요하다. 파일명을 쓰므로 제목 파싱
        경로는 여전히 서버 안에 하나뿐이다.
        """
        path = graph_path_for(self.out_dir)
        if path.exists():
            store = SqliteGraphStore(path, read_only=True)
            try:
                ids = [node_id for node_id, _degree in store.degree_ranking()]
                nodes = store.nodes_of(ids)
            finally:
                store.close()
            documents = [
                _tree_entry(node.id, node.label)
                for node in sorted(nodes.values(), key=lambda node: node.id)
                if node.type is NodeType.DOCUMENT
            ]
            if documents:
                return json_response({"source": "graph", "documents": documents})

        inventory = collect_wiki_documents(self.out_dir)
        if not inventory.documents:
            raise NothingScanned(
                "아직 스캔하지 않았습니다 — 먼저 스캔하면 위키 트리가 채워집니다."
            )
        return json_response(
            {
                "source": "files",
                "message": "그래프가 아직 없어 파일명을 제목 대신 씁니다 — 다시 스캔하면 채워집니다.",
                "documents": [
                    _tree_entry(doc_id, Path(doc_id).name)
                    for doc_id in sorted(inventory.documents)
                ],
            }
        )

    def _wiki_document(self, request: Request) -> Response:
        """상세 — front-matter 5키와 7섹션을 **필드로 분리해** 담는다 (§4.6).

        프론트엔드에 마크다운 파서를 두지 않으므로 마크다운 렌더 경로의 XSS 방어도
        프론트엔드 책임이 아니다.
        """
        doc_id = request.query.get("doc", "")
        if not doc_id:
            raise BadRequest("어느 문서인지 지정하세요 (`doc`).")
        inventory = collect_wiki_documents(self.out_dir)
        wiki_path = inventory.documents.get(doc_id)
        if wiki_path is None:
            raise WikiNotFound(
                f"그 문서의 위키가 `{self.out_dir}` 아래에 없습니다 — 다시 스캔해 보세요."
            )
        document = parse_wiki_document(wiki_path.read_text(encoding="utf-8"))
        return json_response(
            _wiki_dict(document, wiki_path=wiki_path, out_dir=self.out_dir)
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

        **DB가 아직 없는 것과 손상된 것을 가른다** (§5 · T11). 코어는 둘을 같은
        `PreconditionError`로 묶어 「손상되었거나 접근할 수 없습니다 … 파일을 지우고 다시
        scan 하세요」라고 안내하는데, 그것은 `graph` **CLI**의 계약(부재도 선행 조건 실패,
        exit 1)에 맞춰진 문구다. GUI에서 첫 실행 사용자가 그 문장을 보면 **만든 적도 없는
        파일을 지우라는 안내**를 받는다 — CLAUDE.md가 「사용자가 멀쩡한 DB를 지운다」로
        경계한 그 상황이다. 파일 존재 여부는 열기 전에 확인할 수 있으므로 여기서 가른다.
        """
        path = graph_path_for(self.out_dir)
        if not path.exists():
            # 첫 실행은 오류가 아니라 정상적인 빈 상태다 (§5). 화면은 이 식별자를 보고
            # 자기 빈 상태를 그리고 스캔 화면으로 보낸다. **예외로 올린다** — 본문을 손으로
            # 짜면 같은 조건이 화면마다 다른 식별자를 갖게 되고, `_section`이 §4.3.2 매핑을
            # 적용할 기회도 사라진다.
            raise GraphNotBuilt(
                "아직 스캔하지 않았습니다 — 먼저 스캔하면 지식그래프가 채워집니다."
            )
        store = SqliteGraphStore(path, read_only=True)
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


def _matches(supplied: str, expected: str) -> bool:
    """자격 하나를 상수 시간으로 비교한다.

    **UTF-8 바이트로 비교한다.** `secrets.compare_digest`는 `str`을 받으면 비-ASCII 문자에
    `TypeError`를 올리므로, 한글이 든 쿠키·쿼리 토큰 하나로 인증 경로가 예외를 던진다 —
    실측으로 `?token=한글` 요청이 `handle()` 밖으로 탈출했다. 자격이 틀린 것은 요청의
    정상적인 실패이지 버그가 아니므로 그냥 `False`로 수렴해야 한다.

    바이트로 비교해도 상수 시간 성질은 그대로다.
    """
    return secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


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


def _reraise(exc: BaseException) -> Callable[[], dict[str, Any]]:
    """`_section`이 판정할 수 있도록 보관된 예외를 다시 올리는 얇은 호출자."""

    def raise_it() -> dict[str, Any]:
        raise exc

    return raise_it


def _json_body(request: Request) -> dict[str, Any]:
    """요청 본문을 JSON 객체로 읽는다. 본문이 없으면 빈 객체로 본다."""
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadRequest(f"본문을 JSON으로 읽지 못했습니다: {exc}") from exc
    if not isinstance(payload, dict):
        raise BadRequest("본문은 JSON 객체여야 합니다.")
    return payload


def _measurement_dict(measurement: Measurement) -> dict[str, Any]:
    """계량 결과 — 파일별 테이블과 게이트 판정 (§4.3.4 1단계)."""
    return {
        "plan": _plan_dict(measurement.plan),
        "findings": _findings_dict(measurement.findings),
    }


def _plan_dict(plan: ScanPlan) -> dict[str, Any]:
    gate = plan.gate
    return {
        "file_count": plan.file_count,
        "total_est_tokens": plan.total_est_tokens,
        "est_seconds": plan.est_seconds,
        "hardware": {"gpu": plan.hardware.gpu, "label": plan.hardware.label},
        "entries": [
            {
                "path": str(entry.path),
                "ext": entry.ext,
                "size_bytes": entry.size_bytes,
                "est_tokens": entry.est_tokens,
                "importance": entry.importance,
            }
            for entry in plan.entries
        ],
        "gate": (
            None
            if gate is None
            else {
                "gpu_ok": gate.gpu_ok,
                "gpu_enforced": gate.gpu_enforced,
                "tokens_ok": gate.tokens_ok,
                "oversized_count": gate.oversized_count,
                "max_file_size": gate.max_file_size,
                "max_total_tokens": gate.max_total_tokens,
                # 게이트가 걸리면 화면이 이유와 강행 토글(`force_gates`)을 함께 보여 준다 —
                # CLI가 exit 3으로 막는 자리와 같다 (§4.3.4).
                "blocked": (gate.gpu_enforced and not gate.gpu_ok) or not gate.tokens_ok,
            }
        ),
    }


def _findings_dict(findings: ScanFindings) -> dict[str, Any]:
    return {
        "discovered_count": findings.discovered_count,
        "limit_exceeded": findings.limit_exceeded,
        "target_count": len(findings.targets),
        "skipped": [
            {"path": str(item.path), "reason": str(item.reason), "detail": item.detail}
            for item in findings.skipped
        ],
    }


def _result_dict(result: ScanResult) -> dict[str, Any]:
    """스캔 결과 — 구조화된 집계 + 종료 요약 줄.

    **줄을 함께 싣는 이유**는 §4.6.1의 원칙 그대로다. 갈라지면 안 되는 것은 「어휘」이고,
    「그래프 미반영 — 다시 스캔하면 반영됩니다」·스킵 사유 라벨 같은 문구를 프론트가 다시
    구현하면 CLI와 GUI가 같은 결과를 다른 말로 설명한다. 검색 결과와 달리 이 줄들은 이미
    **독립된 줄의 목록**이라 프론트가 정규식으로 다시 가를 일이 없다 — 그대로 출력하면 된다.
    카드가 필요로 하는 숫자는 아래 필드가 따로 낸다.
    """
    graph = result.graph
    return {
        "cancelled": result.cancelled,
        "limit_exceeded": result.limit_exceeded,
        "discovered_count": result.discovered_count,
        "generated_count": len(result.generated),
        "skipped_count": len(result.skipped),
        "embedding_failure_count": len(result.embedding_failures),
        "out_dir": str(result.out_dir),
        "graph": None if graph is None or graph.stats is None else _stats_dict(graph.stats),
        "summary_lines": build_summary_lines(result),
    }


def _tree_entry(doc_id: str, title: str) -> dict[str, Any]:
    """트리 항목 — 키는 `doc_id`이며 그래프 화면·검색과 **같은 키**를 쓴다 (§4.6.2).

    `directory`를 서버가 실어 보내는 것은 화면이 폴더별로 묶어 그리기 때문이다. 프론트가
    절대경로를 잘라 쓰게 두지 않는다 — 경로 해석은 어댑터의 책임이다.
    """
    path = Path(doc_id)
    return {
        "doc_id": doc_id,
        "title": title,
        "name": path.name,
        "directory": str(path.parent),
    }


def _wiki_dict(document: WikiDocument, *, wiki_path: Path, out_dir: Path) -> dict[str, Any]:
    return {
        # front-matter 5키 — `engine`을 빼지 않는다. 「이 문서가 외부로 나갔는가」를
        # 생성물만 보고 아는 값이라 상세 화면에서 가장 먼저 보여야 할 값에 가깝다 (§4.6).
        "source_path": document.source_path,
        "generated_at": document.generated_at,
        "model": document.model,
        "engine": document.engine,
        "source_bytes": document.source_bytes,
        # 7섹션.
        "title": document.title,
        "one_line_summary": document.one_line_summary,
        "key_points": list(document.key_points),
        "summary": document.summary,
        "tags": list(document.tags),
        # 「원문」은 링크가 아니라 **경로**로 내려간다. `file://`는 http 페이지에서 브라우저가
        # 차단하므로 화면은 경로 표시 + 복사 버튼으로 낸다 (§4.6 · IX2). 파일을 OS 기본 앱으로
        # 여는 엔드포인트는 두지 않는다 — MVP 스펙 §2의 명시적 비목표다.
        "source_link": document.source_link,
        "related": _related_dicts(document, wiki_path=wiki_path, out_dir=out_dir),
        "wiki_path": str(wiki_path),
        "wiki_relative": str(wiki_path.relative_to(out_dir)) if wiki_path.is_relative_to(out_dir) else str(wiki_path),
    }


def _related_dicts(
    document: WikiDocument, *, wiki_path: Path, out_dir: Path
) -> list[dict[str, Any]]:
    """「관련 문서」에 `doc_id`를 실어 내린다 (§4.6 · IX3).

    위키 본문에는 `doc_id`가 **적혀 있지 않다** — 적혀 있는 것은 제목·상대경로·근거 문구뿐이다.
    서버가 그 상대경로를 **이 위키 파일 기준**으로 풀어 대상 위키의 front-matter `source_path`를
    읽는다. 비용은 상세 1건당 최대 `related_top_k`개(기본 5)의 head 읽기다.

    **그래프에서 `rank_related()`로 다시 계산하지 않는다** — 동점 정렬 키가 달라져 화면 순서가
    파일에 적힌 순서와 어긋나고, 「조회 시점에 파생값을 다시 계산하지 않는다」는 v0.6 불변식과도
    부딪친다. 프론트가 링크를 파싱해 되돌리게 하지도 않는다 — 경로 해석이 프론트로 넘어가고
    「프론트엔드에 마크다운 파서를 두지 않는다」와도 부딪친다.
    """
    entries: list[dict[str, Any]] = []
    for link in document.related:
        target = (wiki_path.parent / link.href).resolve()
        doc_id = read_source_path(target) if target.is_file() else None
        entries.append(
            {
                "title": link.title,
                # 못 풀면 빈 문자열이다 — 화면은 링크 대신 제목만 보여 준다. 위키가 지워졌거나
                # 사용자가 손으로 고친 경우이며, 상세 전체를 실패시킬 이유가 아니다.
                "doc_id": doc_id or "",
                # 근거 문구는 v0.6·v0.7이 못박은 **어휘**라 그대로 싣는다 (§4.6.1).
                "evidence": link.evidence,
            }
        )
    return entries


def _as_int(raw: str | None, *, default: int) -> int:
    """쿼리 파라미터를 정수로 옮긴다 — **값의 타당성은 코어가 판정한다** (§4.3.3)."""
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise BadRequest(f"정수가 아닙니다: {raw}") from exc


def _as_float(raw: str | None, *, default: float) -> float:
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise BadRequest(f"숫자가 아닙니다: {raw}") from exc


def _result_row(result: SearchResult) -> dict[str, Any]:
    """검색 결과 1건 — 필드로 내리되 **근거 줄만** 기존 빌더의 문자열을 그대로 싣는다.

    §4.6.1의 원칙: **갈라지면 안 되는 것은 「어휘」이지 「줄 조립」이 아니다.** 카드는 점수
    배지·제목·경로를 각각 그려야 하므로 `build_search_lines()` 전체를 내리면 프론트가 정규식
    으로 다시 갈라야 하고, 출력 문구를 다듬는 순간 조용히 깨진다. 반대로 근거를 전부 구조화
    하면 참조 방향 3종 문구(「시드를 참조함」·「시드가 참조함」·「서로 참조함」)를 프론트가 다시
    구현하게 되어 v0.7이 정확 문자열까지 못박은 어휘가 둘로 갈린다.
    """
    metadata = result.metadata or {}
    expansion = result.expansion
    return {
        "doc_id": result.doc_id,
        "score": result.score,
        # 제목·경로의 출처는 시드와 확산에서 하나로 유지된다 (v0.7 §4.7).
        "title": metadata.get("title") or Path(result.doc_id).name,
        # v0.4 그대로 원문 절대경로를 적는다. `metadata`가 없는 확산 문서는 `doc_id`가 곧
        # 같은 값이다 (v0.7 §4.6).
        "source_path": metadata.get("source_path") or result.doc_id,
        "tags": list(metadata.get("tags") or []),
        "expansion": (
            None
            if expansion is None
            else {
                "seed_doc_id": expansion.seed_doc_id,
                "seed_title": expansion.seed_title,
                # v0.7 §4.6이 정확 문자열까지 못박은 계약 — 한 글자도 갈리지 않는다.
                "evidence": build_expansion_evidence(expansion, result.score),
            }
        ),
    }
