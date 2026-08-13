"""Ollama 탐지 클라이언트 검증 (FR-009 / 스펙 §4.3, §4.5, §5, 완료의 정의 5·6번).

실제 Ollama 데몬·소켓에는 절대 붙지 않는다 — 단일 외부호출 관문
(`corpbrain.core.gateway.request_json`)을 monkeypatch로 스텁해 탐지 성공/실패 변환과
호출 목적지(지정한 localhost URL 하나뿐)를 확인한다.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_OLLAMA_URL
from corpbrain.core.errors import CorpBrainError, PreconditionError
from corpbrain.core.llm import ollama_client
from corpbrain.core.llm.ollama_client import OllamaNotAvailableError, detect

#: 구동 중인 Ollama의 `/api/tags` 정상 응답 형태.
HEALTHY_RESPONSE = {"models": [{"name": "qwen2.5:7b-instruct"}]}


@pytest.fixture(autouse=True)
def _no_real_gateway_traffic() -> Any:
    """관문 기록을 격리하고, 테스트가 진짜 소켓을 열지 않았음을 사후 확인한다."""
    gateway.reset_requested_urls()
    yield
    assert gateway.requested_urls() == (), "테스트가 스텁이 아닌 실제 관문을 호출했다"


def _stub_gateway(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: Any = HEALTHY_RESPONSE,
    error: Exception | None = None,
) -> list[tuple[str, float]]:
    """관문을 스텁하고 관측된 (URL, timeout) 목록을 돌려준다."""
    calls: list[tuple[str, float]] = []

    def fake_request_json(
        url: str,
        *,
        method: str = "GET",
        payload: Any = None,
        timeout: float = 60.0,
    ) -> Any:
        assert method == "GET", "헬스체크는 GET이어야 한다"
        assert payload is None, "탐지 호출은 본문을 보내지 않는다"
        calls.append((url, timeout))
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(gateway, "request_json", fake_request_json)
    return calls


def _gateway_error(url: str) -> gateway.GatewayError:
    return gateway.GatewayError(f"외부 호출에 연결하지 못했습니다: {url}", url=url)


def test_detect_succeeds_when_health_check_responds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 시나리오 1: 헬스체크가 정상 응답하면 탐지에 성공한다."""
    ollama_url = "http://127.0.0.1:11434"
    calls = _stub_gateway(monkeypatch)

    assert detect(ollama_url) is None

    assert [url for url, _timeout in calls] == [f"{ollama_url}/api/tags"]


def test_detect_contacts_only_the_given_localhost_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 시나리오 1: 호출은 단일 관문을 경유하며 대상은 지정한 localhost URL뿐이다."""
    ollama_url = "http://localhost:11434/"
    calls = _stub_gateway(monkeypatch)

    detect(ollama_url)

    assert len(calls) == 1
    assert {urlsplit(url).hostname for url, _timeout in calls} <= {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def test_detect_defaults_to_spec_ollama_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """기본 대상은 스펙 §4.1의 `http://127.0.0.1:11434` (하드코딩이 아닌 config 상수)."""
    calls = _stub_gateway(monkeypatch)

    detect()

    assert calls[0][0] == f"{DEFAULT_OLLAMA_URL}/api/tags"


def test_detect_passes_timeout_to_the_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    """타임아웃은 기본값과 명시값 모두 관문으로 전달된다."""
    calls = _stub_gateway(monkeypatch)

    detect(DEFAULT_OLLAMA_URL)
    detect(DEFAULT_OLLAMA_URL, timeout=0.5)

    assert [timeout for _url, timeout in calls] == [5.0, 0.5]


def test_connection_failure_raises_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC 시나리오 2: 연결 실패(미구동)는 `OllamaNotAvailableError`로 올라온다."""
    url = f"{DEFAULT_OLLAMA_URL}/api/tags"
    error = _gateway_error(url)
    _stub_gateway(monkeypatch, error=error)

    with pytest.raises(OllamaNotAvailableError) as excinfo:
        detect(DEFAULT_OLLAMA_URL)

    assert excinfo.value.__cause__ is error, "원인 예외를 보존해야 한다"
    assert url in str(excinfo.value)


def test_http_error_status_raises_not_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """비정상 상태코드(관문이 GatewayError로 감싼다)도 미탐지로 취급한다."""
    url = f"{DEFAULT_OLLAMA_URL}/api/tags"
    _stub_gateway(
        monkeypatch,
        error=gateway.GatewayError(
            f"외부 호출이 HTTP 500로 실패했습니다: {url}", url=url
        ),
    )

    with pytest.raises(OllamaNotAvailableError):
        detect(DEFAULT_OLLAMA_URL)


@pytest.mark.parametrize("response", [None, [], ["qwen2.5"], "ok", 3])
def test_malformed_response_raises_not_available(
    monkeypatch: pytest.MonkeyPatch, response: Any
) -> None:
    """JSON 객체가 아닌 응답은 Ollama가 아니라고 보고 미탐지로 취급한다."""
    _stub_gateway(monkeypatch, response=response)

    with pytest.raises(OllamaNotAvailableError):
        detect(DEFAULT_OLLAMA_URL)


def test_not_available_error_is_a_precondition_failure() -> None:
    """선행 조건 실패 계층에 속해야 어댑터가 비-0 종료로 매핑한다 (스펙 §3-5)."""
    error = OllamaNotAvailableError("boom")

    assert isinstance(error, PreconditionError)
    assert isinstance(error, CorpBrainError)


def test_detect_never_attempts_installation_or_provisioning() -> None:
    """스펙 §4.3: 탐지만 한다 — 프로세스 실행·설치 경로를 정적으로도 갖지 않는다.

    v0.3에서 모델 부재 시 `ollama pull <model>`을 **안내**(문자열)하지만 직접 실행하지는
    않는다. 실행 경로(subprocess/shutil/os import)를 정적으로 갖지 않음을 아래 import 검사로
    보증한다(설치 감지 `shutil.which`는 별도 모듈 core/environment.py가 담당).
    """
    forbidden = {"subprocess", "shutil", "os", "sys", "venv", "pip"}
    tree = ast.parse(Path(ollama_client.__file__).read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported & forbidden == set()
