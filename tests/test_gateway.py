"""단일 외부호출 관문 검증 (FR-003 / 스펙 §4.5, 완료의 정의 6번).

실제 소켓은 열지 않는다 — 관문 내부의 opener(`gateway._OPENER`)를 monkeypatch로 스텁해
관문이 만들어 보내는 요청과 오류 변환, 그리고 목적지 감시 훅을 확인한다.
v0.5부터 관문은 리다이렉트를 따라가지 않는 전용 opener로만 나가므로(스펙 §4.4),
스텁 지점도 `urllib.request.urlopen`이 아니라 이 opener다.
"""

from __future__ import annotations

import ast
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

import pytest

from corpbrain.core import gateway
from corpbrain.core.errors import CorpBrainError

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
#: 로컬 호출도 목적지 정책을 선언해야 한다 — `allowed_hosts`는 기본값 없는 필수 인자다 (§4.4).
LOCAL_HOSTS = ("127.0.0.1", "localhost")


class _FakeResponse:
    """`urlopen`이 돌려주는 컨텍스트 매니저 응답 스텁."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class _FakeOpener:
    """`gateway._OPENER`를 대신하는 스텁 — `.open(request, timeout=...)`만 흉내낸다."""

    def __init__(self, body: bytes, error: Exception | None) -> None:
        self._body = body
        self._error = error
        self.calls: list[tuple[urllib.request.Request, float | None]] = []

    def open(
        self, request: urllib.request.Request, timeout: float | None = None
    ) -> _FakeResponse:
        self.calls.append((request, timeout))
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._body)


def _stub_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes = b"{}",
    error: Exception | None = None,
) -> list[tuple[urllib.request.Request, float | None]]:
    """관문 내부의 opener를 스텁하고 관측된 (요청, 타임아웃) 목록을 돌려준다."""
    opener = _FakeOpener(body, error)
    monkeypatch.setattr(gateway, "_OPENER", opener)
    return opener.calls


@pytest.fixture(autouse=True)
def _reset_gateway_observations() -> Any:
    """관문의 URL 기록을 테스트마다 격리한다."""
    gateway.reset_requested_urls()
    yield
    gateway.reset_requested_urls()


def test_get_request_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """본문 없는 기본 호출은 GET으로 나가고 응답 JSON이 파싱돼 돌아온다."""
    calls = _stub_urlopen(monkeypatch, body=b'{"models": [{"name": "qwen2.5"}]}')

    result = gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    assert result == {"models": [{"name": "qwen2.5"}]}
    request, _timeout = calls[0]
    assert request.full_url == OLLAMA_URL
    assert request.get_method() == "GET"
    assert request.data is None


def test_payload_is_json_encoded_and_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """payload가 주어지면 JSON 직렬화해 본문으로 보내고 Content-Type을 붙인다."""
    calls = _stub_urlopen(monkeypatch, body=b'{"response": "ok"}')

    result = gateway.request_json(
        OLLAMA_URL,
        method="POST",
        payload={"model": "qwen2.5", "stream": False},
        allowed_hosts=LOCAL_HOSTS,
    )

    assert result == {"response": "ok"}
    request, _timeout = calls[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"model": "qwen2.5", "stream": False}
    assert request.get_header("Content-type") == "application/json"


def test_timeout_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """타임아웃은 기본값(60초)과 명시값 모두 소켓 계층으로 전달된다."""
    calls = _stub_urlopen(monkeypatch)

    gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)
    gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS, timeout=1.5)

    assert [timeout for _request, timeout in calls] == [60.0, 1.5]


def test_http_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 오류 상태는 GatewayError로 감싸 올린다."""
    error = urllib.error.HTTPError(OLLAMA_URL, 500, "Server Error", {}, None)  # type: ignore[arg-type]
    _stub_urlopen(monkeypatch, error=error)

    with pytest.raises(gateway.GatewayError) as excinfo:
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    assert excinfo.value.url == OLLAMA_URL
    assert excinfo.value.__cause__ is error


def test_http_error_json_body_is_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    """서버가 `{"error": ...}` 본문을 주면 그 메시지가 GatewayError에 실려 나온다 (진단)."""
    body = io.BytesIO(b'{"error": "CUDA error: the provided PTX was compiled with an unsupported toolchain."}')
    error = urllib.error.HTTPError(OLLAMA_URL, 500, "Server Error", {}, body)  # type: ignore[arg-type]
    _stub_urlopen(monkeypatch, error=error)

    with pytest.raises(gateway.GatewayError) as excinfo:
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    message = str(excinfo.value)
    assert "500" in message
    assert "unsupported toolchain" in message


def test_http_error_plaintext_body_is_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON이 아닌 오류 본문도 앞부분이 메시지에 실린다."""
    error = urllib.error.HTTPError(
        OLLAMA_URL, 502, "Bad Gateway", {}, io.BytesIO(b"upstream boom")  # type: ignore[arg-type]
    )
    _stub_urlopen(monkeypatch, error=error)

    with pytest.raises(gateway.GatewayError) as excinfo:
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    assert "upstream boom" in str(excinfo.value)


def test_http_error_without_body_still_wraps(monkeypatch: pytest.MonkeyPatch) -> None:
    """본문이 없어도(fp=None) 상태코드 메시지로 감싸 올린다 (진단이 실패를 숨기지 않는다)."""
    error = urllib.error.HTTPError(OLLAMA_URL, 500, "Server Error", {}, None)  # type: ignore[arg-type]
    _stub_urlopen(monkeypatch, error=error)

    with pytest.raises(gateway.GatewayError) as excinfo:
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    assert "500" in str(excinfo.value)


def test_connection_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """연결 실패(Ollama 미구동 등)는 GatewayError로 감싸 올린다."""
    _stub_urlopen(monkeypatch, error=urllib.error.URLError(ConnectionRefusedError(61)))

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)


def test_timeout_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """소켓 타임아웃도 GatewayError로 감싸 올린다 (raw OSError 누출 금지)."""
    _stub_urlopen(monkeypatch, error=TimeoutError("timed out"))

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)


def test_invalid_json_response_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON이 아닌 응답 본문은 GatewayError로 감싸 올린다."""
    _stub_urlopen(monkeypatch, body=b"not json at all")

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)


def test_unserializable_payload_fails_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """직렬화 불가 payload는 소켓을 열기 전에 GatewayError로 실패한다."""
    calls = _stub_urlopen(monkeypatch)

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(
            OLLAMA_URL,
            method="POST",
            payload={"fp": object()},
            allowed_hosts=LOCAL_HOSTS,
        )

    assert calls == []


def test_gateway_error_is_a_corpbrain_error() -> None:
    """관문 예외는 코어 예외 계층에 속한다 (어댑터가 한 뿌리로 잡을 수 있다)."""
    error = gateway.GatewayError("boom", url=OLLAMA_URL)

    assert isinstance(error, CorpBrainError)
    assert error.url == OLLAMA_URL


def test_requested_urls_records_every_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """성공·실패를 가리지 않고 시도한 목적지가 순서대로 기록된다."""
    _stub_urlopen(monkeypatch, body=b"{}")
    gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)

    _stub_urlopen(monkeypatch, error=TimeoutError("timed out"))
    with pytest.raises(gateway.GatewayError):
        gateway.request_json(
            "http://localhost:11434/api/tags", allowed_hosts=LOCAL_HOSTS
        )

    assert gateway.requested_urls() == (OLLAMA_URL, "http://localhost:11434/api/tags")

    gateway.reset_requested_urls()
    assert gateway.requested_urls() == ()


def test_observation_hook_supports_localhost_only_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """완료의 정의 6번: 관문 기록만 보고 'localhost 외 연결 없음'을 단언할 수 있다."""
    _stub_urlopen(monkeypatch)

    gateway.request_json(OLLAMA_URL, allowed_hosts=LOCAL_HOSTS)
    gateway.request_json("http://localhost:11434/api/tags", allowed_hosts=LOCAL_HOSTS)

    hosts = {urlsplit(url).hostname for url in gateway.requested_urls()}
    assert hosts <= {"127.0.0.1", "localhost", "::1"}


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def test_extra_headers_are_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """v0.5 §4.3: 인증 헤더 등 provider 고유 헤더를 실어 보낼 수 있다 (공식 SDK 미사용)."""
    calls = _stub_urlopen(monkeypatch, body=b"{}")

    gateway.request_json(
        ANTHROPIC_URL,
        method="POST",
        payload={"model": "claude"},
        headers={"x-api-key": "sk-test", "anthropic-version": "2023-06-01"},
        allowed_hosts=("api.anthropic.com",),
        require_https=True,
    )

    request, _timeout = calls[0]
    assert request.get_header("X-api-key") == "sk-test"
    assert request.get_header("Anthropic-version") == "2023-06-01"
    assert request.get_header("Content-type") == "application/json"


def test_disallowed_host_is_blocked_before_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """v0.5 §4.4: allowlist 밖 호스트는 소켓을 열기 전에 차단되고 기록도 남지 않는다."""
    calls = _stub_urlopen(monkeypatch)

    with pytest.raises(gateway.NetworkGuardError):
        gateway.request_json(
            "https://evil.example.com/v1/messages", allowed_hosts=("api.anthropic.com",)
        )

    assert calls == []
    assert gateway.requested_urls() == ()


def test_allowed_host_matches_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    """호스트 비교는 대소문자를 무시한 정확 일치다."""
    _stub_urlopen(monkeypatch, body=b"{}")

    gateway.request_json(
        "https://API.Anthropic.COM/v1/models", allowed_hosts=("api.anthropic.com",)
    )

    assert gateway.requested_urls() == ("https://API.Anthropic.COM/v1/models",)


def test_subdomain_is_not_allowed_by_suffix_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """서픽스·와일드카드 매칭을 쓰지 않는다 — 하위 도메인은 허용되지 않는다."""
    _stub_urlopen(monkeypatch)

    with pytest.raises(gateway.NetworkGuardError):
        gateway.request_json(
            "https://evil.api.anthropic.com/v1/messages",
            allowed_hosts=("api.anthropic.com",),
        )


def test_require_https_rejects_plain_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """클라우드 경로는 HTTPS만 허용한다 (v0.5 §4.4)."""
    calls = _stub_urlopen(monkeypatch)

    with pytest.raises(gateway.NetworkGuardError):
        gateway.request_json(
            "http://api.anthropic.com/v1/messages",
            allowed_hosts=("api.anthropic.com",),
            require_https=True,
        )

    assert calls == []


def test_allowed_hosts_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """목적지 정책을 선언하지 않고는 관문을 부를 수 없다 (v0.5 §4.4).

    기본값을 두면 "제한 없음"이 조용한 기본 동작이 되어, 호출부가 잊거나 리팩터링이 인자를
    흘리는 순간 아무 신호 없이 가드가 사라진다. 관문은 이 프로세스의 유일한 출구이므로
    누락이 **호출 시점에 즉시 드러나야** 한다.
    """
    _stub_urlopen(monkeypatch, body=b"{}")

    with pytest.raises(TypeError):
        gateway.request_json(OLLAMA_URL)  # type: ignore[call-arg]


def test_every_gateway_call_in_the_package_declares_a_destination() -> None:
    """패키지 안의 모든 관문 호출이 `allowed_hosts`를 넘긴다 (회귀 방지 정적 검사)."""
    package_root = Path(gateway.__file__).resolve().parents[1]
    offenders: list[str] = []

    for source_path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            is_gateway_call = (
                isinstance(target, ast.Attribute) and target.attr == "request_json"
            )
            if not is_gateway_call:
                continue
            if not any(kw.arg == "allowed_hosts" for kw in node.keywords):
                offenders.append(f"{source_path.relative_to(package_root)}:{node.lineno}")

    assert offenders == [], f"목적지를 선언하지 않은 관문 호출: {offenders}"


def test_network_guard_error_is_a_gateway_error() -> None:
    """NetworkGuard 거부도 관문 예외 계층에 속한다 (어댑터가 한 뿌리로 잡는다)."""
    error = gateway.NetworkGuardError("blocked", url=ANTHROPIC_URL)

    assert isinstance(error, gateway.GatewayError)
    assert isinstance(error, CorpBrainError)


def test_redirects_are_not_followed() -> None:
    """3xx는 추적하지 않는다 — 커스텀 핸들러가 `redirect_request`를 무력화한다 (v0.5 §4.4)."""
    handler = gateway._NoRedirectHandler()

    assert (
        handler.redirect_request(
            None, None, 302, "Found", {}, "https://evil.example.com/"
        )
        is None
    )


def test_opener_has_no_redirect_handler() -> None:
    """관문 opener는 표준 리다이렉트 핸들러 대신 차단 핸들러를 쓴다."""
    handlers = [type(handler) for handler in gateway._OPENER.handlers]

    assert gateway._NoRedirectHandler in handlers


#: 관문 밖에서 import 되면 안 되는 네트워크 라이브러리 (접두사 매칭).
#: `urllib.parse`처럼 순수 문자열 처리 모듈은 허용한다.
_NETWORK_MODULES = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "urllib.error",
        "urllib.request",
        "urllib3",
    }
)


def _imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


#: **인바운드 허용 목록** — 파일 단위로, 이름 단위로 좁게 연다 (v0.9).
#:
#: 이 불변식이 지키는 것은 「나가는 연결은 전부 관문을 통과한다」이다. v0.9 GUI 서버는
#: 반대 방향이다 — **듣는 소켓**을 열고 HTTP 문법을 해석하며, 어떤 원격지에도 연결하지
#: 않는다. 그래서 이름을 열되 **모듈 전체를 면제하지 않는다**: `urllib.request`·`requests`·
#: `httpx`·`aiohttp`·`urllib3`·`ssl` 같은 **나가는** 라이브러리는 `corpbrain/gui/` 안에서도
#: 그대로 막힌다. GUI 어댑터가 관문을 우회해 외부를 호출하면 여기서 잡힌다.
#:
#: 「듣는 소켓의 바인드 주소가 127.0.0.1뿐인가」는 이 정적 검사가 아니라
#: `tests/security/test_network_invariant.py`의 `bind` 감시가 본다 (v0.9 §3 항목3) —
#: 축이 다르므로 장치도 다르다.
_INBOUND_ALLOWANCES: dict[str, frozenset[str]] = {
    "gui/api.py": frozenset({"http.cookies", "http.cookies.SimpleCookie"}),
    "gui/httpd.py": frozenset(
        {
            "http.server",
            "http.server.BaseHTTPRequestHandler",
            "http.server.ThreadingHTTPServer",
        }
    ),
}


def _is_network_module(name: str) -> bool:
    return any(
        name == blocked or name.startswith(f"{blocked}.") for blocked in _NETWORK_MODULES
    )


def test_gateway_is_the_only_module_touching_the_network() -> None:
    """AC 시나리오 2: 관문 외의 어떤 모듈도 네트워크 라이브러리를 직접 import 하지 않는다."""
    package_root = Path(gateway.__file__).resolve().parents[1]
    gateway_path = Path(gateway.__file__).resolve()

    offenders: dict[str, set[str]] = {}
    for source_path in sorted(package_root.rglob("*.py")):
        if source_path.resolve() == gateway_path:
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        relative = source_path.relative_to(package_root).as_posix()
        allowed = _INBOUND_ALLOWANCES.get(relative, frozenset())
        blocked = {
            name
            for name in _imported_module_names(tree)
            if _is_network_module(name) and name not in allowed
        }
        if blocked:
            offenders[relative] = blocked

    assert offenders == {}, f"관문을 우회하는 네트워크 import: {offenders}"


def test_inbound_allowance_does_not_open_outbound_libraries() -> None:
    """허용 목록이 「나가는」 라이브러리를 열어 주지 않는다 — 감시장치가 공허해지지 않는다.

    `test_watcher_flags_a_gateway_bypass`가 소켓 감시에 대해 하는 일과 같다: 예외를 둔
    바로 그 파일에서 관문 우회를 시도하면 여전히 잡히는지 확인한다.
    """
    outbound = {"urllib.request", "requests", "httpx", "aiohttp", "urllib3", "socket"}
    for path, allowed in _INBOUND_ALLOWANCES.items():
        leaked = {name for name in allowed if name in outbound}
        assert leaked == set(), f"{path}의 허용 목록이 나가는 라이브러리를 열었다: {leaked}"
        assert all(_is_network_module(name) for name in allowed), (
            f"{path}의 허용 목록에 막히지도 않는 이름이 있다 — 목록이 낡았다"
        )
