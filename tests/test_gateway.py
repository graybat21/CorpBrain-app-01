"""단일 외부호출 관문 검증 (FR-003 / 스펙 §4.5, 완료의 정의 6번).

실제 소켓은 열지 않는다 — `urllib.request.urlopen`을 monkeypatch로 스텁해
관문이 만들어 보내는 요청과 오류 변환, 그리고 목적지 감시 훅을 확인한다.
"""

from __future__ import annotations

import ast
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


def _stub_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes = b"{}",
    error: Exception | None = None,
) -> list[tuple[urllib.request.Request, float | None]]:
    """관문 내부의 `urlopen`을 스텁하고 관측된 (요청, 타임아웃) 목록을 돌려준다."""
    calls: list[tuple[urllib.request.Request, float | None]] = []

    def fake_urlopen(
        request: urllib.request.Request, timeout: float | None = None
    ) -> _FakeResponse:
        calls.append((request, timeout))
        if error is not None:
            raise error
        return _FakeResponse(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


@pytest.fixture(autouse=True)
def _reset_gateway_observations() -> Any:
    """관문의 URL 기록을 테스트마다 격리한다."""
    gateway.reset_requested_urls()
    yield
    gateway.reset_requested_urls()


def test_get_request_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """본문 없는 기본 호출은 GET으로 나가고 응답 JSON이 파싱돼 돌아온다."""
    calls = _stub_urlopen(monkeypatch, body=b'{"models": [{"name": "qwen2.5"}]}')

    result = gateway.request_json(OLLAMA_URL)

    assert result == {"models": [{"name": "qwen2.5"}]}
    request, _timeout = calls[0]
    assert request.full_url == OLLAMA_URL
    assert request.get_method() == "GET"
    assert request.data is None


def test_payload_is_json_encoded_and_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """payload가 주어지면 JSON 직렬화해 본문으로 보내고 Content-Type을 붙인다."""
    calls = _stub_urlopen(monkeypatch, body=b'{"response": "ok"}')

    result = gateway.request_json(
        OLLAMA_URL, method="POST", payload={"model": "qwen2.5", "stream": False}
    )

    assert result == {"response": "ok"}
    request, _timeout = calls[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"model": "qwen2.5", "stream": False}
    assert request.get_header("Content-type") == "application/json"


def test_timeout_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """타임아웃은 기본값(60초)과 명시값 모두 소켓 계층으로 전달된다."""
    calls = _stub_urlopen(monkeypatch)

    gateway.request_json(OLLAMA_URL)
    gateway.request_json(OLLAMA_URL, timeout=1.5)

    assert [timeout for _request, timeout in calls] == [60.0, 1.5]


def test_http_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 오류 상태는 GatewayError로 감싸 올린다."""
    error = urllib.error.HTTPError(OLLAMA_URL, 500, "Server Error", {}, None)  # type: ignore[arg-type]
    _stub_urlopen(monkeypatch, error=error)

    with pytest.raises(gateway.GatewayError) as excinfo:
        gateway.request_json(OLLAMA_URL)

    assert excinfo.value.url == OLLAMA_URL
    assert excinfo.value.__cause__ is error


def test_connection_failure_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """연결 실패(Ollama 미구동 등)는 GatewayError로 감싸 올린다."""
    _stub_urlopen(monkeypatch, error=urllib.error.URLError(ConnectionRefusedError(61)))

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL)


def test_timeout_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """소켓 타임아웃도 GatewayError로 감싸 올린다 (raw OSError 누출 금지)."""
    _stub_urlopen(monkeypatch, error=TimeoutError("timed out"))

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL)


def test_invalid_json_response_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON이 아닌 응답 본문은 GatewayError로 감싸 올린다."""
    _stub_urlopen(monkeypatch, body=b"not json at all")

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL)


def test_unserializable_payload_fails_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """직렬화 불가 payload는 소켓을 열기 전에 GatewayError로 실패한다."""
    calls = _stub_urlopen(monkeypatch)

    with pytest.raises(gateway.GatewayError):
        gateway.request_json(OLLAMA_URL, method="POST", payload={"fp": object()})

    assert calls == []


def test_gateway_error_is_a_corpbrain_error() -> None:
    """관문 예외는 코어 예외 계층에 속한다 (어댑터가 한 뿌리로 잡을 수 있다)."""
    error = gateway.GatewayError("boom", url=OLLAMA_URL)

    assert isinstance(error, CorpBrainError)
    assert error.url == OLLAMA_URL


def test_requested_urls_records_every_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """성공·실패를 가리지 않고 시도한 목적지가 순서대로 기록된다."""
    _stub_urlopen(monkeypatch, body=b"{}")
    gateway.request_json(OLLAMA_URL)

    _stub_urlopen(monkeypatch, error=TimeoutError("timed out"))
    with pytest.raises(gateway.GatewayError):
        gateway.request_json("http://localhost:11434/api/tags")

    assert gateway.requested_urls() == (OLLAMA_URL, "http://localhost:11434/api/tags")

    gateway.reset_requested_urls()
    assert gateway.requested_urls() == ()


def test_observation_hook_supports_localhost_only_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """완료의 정의 6번: 관문 기록만 보고 'localhost 외 연결 없음'을 단언할 수 있다."""
    _stub_urlopen(monkeypatch)

    gateway.request_json(OLLAMA_URL)
    gateway.request_json("http://localhost:11434/api/tags")

    hosts = {urlsplit(url).hostname for url in gateway.requested_urls()}
    assert hosts <= {"127.0.0.1", "localhost", "::1"}


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
        blocked = {
            name for name in _imported_module_names(tree) if _is_network_module(name)
        }
        if blocked:
            offenders[str(source_path.relative_to(package_root))] = blocked

    assert offenders == {}, f"관문을 우회하는 네트워크 import: {offenders}"
