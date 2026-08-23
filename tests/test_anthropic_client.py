"""Anthropic 클라우드 백엔드 단위 테스트 (v0.5 스펙 §4.3·§4.4).

관문(`gateway.request_json`)을 스텁해 요청 조립·응답 파싱·실패 분류를 검증한다.
실제 API에는 접속하지 않는다.
"""

from __future__ import annotations

from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_CLOUD_MODEL
from corpbrain.core.errors import PreconditionError
from corpbrain.core.llm import anthropic_client as ac
from corpbrain.core.llm.base import LLMParseError

SUMMARY_INPUT = {
    "title": "제목",
    "one_line_summary": "한 줄",
    "key_points": ["가", "나", "다"],
    "summary": "요약",
    "tags": ["태그"],
}


def _tool_use(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "name": ac.SUMMARY_TOOL_NAME,
                "input": payload if payload is not None else SUMMARY_INPUT,
            }
        ],
    }


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """관문 호출을 기록하고 tool_use 응답을 돌려주는 스텁."""
    recorded: list[dict[str, Any]] = []

    def _request_json(url: str, **kwargs: Any) -> Any:
        recorded.append({"url": url, **kwargs})
        if url.endswith("/v1/models"):
            return {"data": []}
        return _tool_use()

    monkeypatch.setattr(gateway, "request_json", _request_json)
    return recorded


# --- API 키 해소 ---------------------------------------------------------------


def test_resolve_api_key_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ac.API_KEY_ENV_VAR, "  sk-test  ")

    assert ac.resolve_api_key() == "sk-test"


@pytest.mark.parametrize("value", ["", "   "])
def test_missing_api_key_is_a_precondition_failure(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """키 부재는 선행 조건 실패라 어댑터가 exit 1로 매핑한다 (§3 항목4)."""
    monkeypatch.setenv(ac.API_KEY_ENV_VAR, value)

    with pytest.raises(ac.CloudAuthError) as excinfo:
        ac.resolve_api_key()

    assert isinstance(excinfo.value, PreconditionError)


def test_api_key_is_never_placed_in_scan_config() -> None:
    """자격증명은 값 객체에 실리지 않는다 — 로그·에러에 노출되지 않게 한다 (§4.1)."""
    from corpbrain.core.config import ScanConfig

    assert not any("key" in field for field in ScanConfig.__dataclass_fields__)


# --- 요청 조립 -----------------------------------------------------------------


def test_summarize_sends_auth_headers_and_guard_params(calls: list[dict[str, Any]]) -> None:
    """인증 헤더가 관문 headers 통로로 실리고 NetworkGuard·HTTPS 강제가 함께 걸린다 (§4.3·§4.4)."""
    ac.summarize_cloud("문서 본문", DEFAULT_CLOUD_MODEL, "sk-test")

    call = calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "sk-test"
    assert call["headers"]["anthropic-version"] == ac.ANTHROPIC_VERSION
    assert call["allowed_hosts"] == (ac.ANTHROPIC_HOST,)
    assert call["require_https"] is True


def test_summarize_forces_the_summary_tool(calls: list[dict[str, Any]]) -> None:
    """5필드 스키마는 tool_choice로 강제한다 — 프롬프트 기반 JSON 강제가 아니다 (§4.3)."""
    ac.summarize_cloud("문서 본문", DEFAULT_CLOUD_MODEL, "sk-test")

    payload = calls[0]["payload"]
    assert payload["tool_choice"] == {"type": "tool", "name": ac.SUMMARY_TOOL_NAME}
    assert payload["tools"] == [ac.SUMMARY_TOOL_SCHEMA]
    assert payload["max_tokens"] == ac.MAX_TOKENS


def test_document_body_reaches_the_prompt(calls: list[dict[str, Any]]) -> None:
    """문서 본문이 실제로 프롬프트에 실린다 (템플릿 이스케이프 회귀 방지)."""
    ac.summarize_cloud("고유한문서본문표식", DEFAULT_CLOUD_MODEL, "sk-test")

    assert "고유한문서본문표식" in calls[0]["payload"]["messages"][0]["content"]


def test_tool_schema_requires_all_six_fields_without_item_bounds() -> None:
    """6필드 모두 required이되 minItems/maxItems는 두지 않는다 — 로컬과 검증 규칙 일치 (§4.3).

    `entities`는 v0.6.1에서 required로 옮겼다 — 선택으로 두면 스키마를 강제받는 모델이
    건너뛴다 (`tests/unit/test_summary_entities.py`).
    """
    schema = ac.SUMMARY_TOOL_SCHEMA["input_schema"]

    assert set(schema["required"]) == {
        "title", "one_line_summary", "key_points", "summary", "tags", "entities",
    }
    for field in ("key_points", "tags"):
        assert "minItems" not in schema["properties"][field]
        assert "maxItems" not in schema["properties"][field]


# --- PII 마스킹 ----------------------------------------------------------------


def test_pii_is_masked_before_the_request_leaves(calls: list[dict[str, Any]]) -> None:
    """전송 직전 마스킹이 걸린다 — 원문 PII는 payload에 없다 (§4.5)."""
    _summary, masked = ac.summarize_cloud(
        "연락처 010-1234-5678", DEFAULT_CLOUD_MODEL, "sk-test"
    )

    assert "010-1234-5678" not in str(calls[0]["payload"])
    assert "[REDACTED_PHONE]" in calls[0]["payload"]["messages"][0]["content"]
    assert masked.total == 1


# --- 응답 파싱 -----------------------------------------------------------------


def test_tool_use_input_becomes_summary_result(calls: list[dict[str, Any]]) -> None:
    summary, _masked = ac.summarize_cloud("본문", DEFAULT_CLOUD_MODEL, "sk-test")

    assert summary.title == "제목"
    assert summary.key_points == ["가", "나", "다"]


@pytest.mark.parametrize(
    "envelope",
    [
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "안녕"}]},
        {"content": []},
        {"content": "not-a-list"},
        "not-a-dict",
    ],
)
def test_missing_tool_use_is_a_parse_error(
    monkeypatch: pytest.MonkeyPatch, envelope: Any
) -> None:
    """도구 호출이 없는 응답은 해당 파일만 스킵되는 파싱 실패로 수렴한다 (§4.3)."""
    monkeypatch.setattr(gateway, "request_json", lambda url, **_: envelope)

    with pytest.raises(LLMParseError):
        ac.summarize_cloud("본문", DEFAULT_CLOUD_MODEL, "sk-test")


def test_schema_violation_is_a_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """필수 필드가 비면 로컬과 동일한 규칙으로 거부된다 (§4.3 검증 규칙 공유)."""
    monkeypatch.setattr(
        gateway, "request_json", lambda url, **_: _tool_use({**SUMMARY_INPUT, "title": "  "})
    )

    with pytest.raises(LLMParseError):
        ac.summarize_cloud("본문", DEFAULT_CLOUD_MODEL, "sk-test")


# --- 실패 분류 (§3 항목8) --------------------------------------------------------


def _gateway_error_with_status(status: int | None) -> gateway.GatewayError:
    """관문이 계약으로 노출하는 `status`를 그대로 실어 만든다 (`__cause__`를 흉내내지 않는다)."""
    return gateway.GatewayError(
        "실패", url="https://api.anthropic.com/v1/messages", status=status
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, ac.CloudRateLimitedError),
        (500, ac.CloudApiError),
        (503, ac.CloudApiError),
        (400, ac.CloudApiError),
        (404, ac.CloudApiError),
        (None, ac.CloudApiError),  # 타임아웃·연결오류 (상태코드 없음)
    ],
)
def test_call_failures_are_classified(
    monkeypatch: pytest.MonkeyPatch, status: int | None, expected: type[Exception]
) -> None:
    """429만 레이트리밋, 나머지는 전부 api_error로 통합한다 (§3 항목8)."""
    error = _gateway_error_with_status(status)

    def _boom(url: str, **_: Any) -> Any:
        raise error

    monkeypatch.setattr(gateway, "request_json", _boom)

    with pytest.raises(expected):
        ac.summarize_cloud("본문", DEFAULT_CLOUD_MODEL, "sk-test")


def test_rate_limited_and_api_errors_are_not_precondition_failures() -> None:
    """개별 파일 스킵 사유이므로 전체 실행을 멈추는 선행 조건 실패가 아니다 (§3 항목8)."""
    assert not issubclass(ac.CloudRateLimitedError, PreconditionError)
    assert not issubclass(ac.CloudApiError, PreconditionError)


# --- 프리플라이트 (§4.3) ---------------------------------------------------------


def test_preflight_calls_models_endpoint(calls: list[dict[str, Any]]) -> None:
    """프리플라이트는 토큰 비용이 없는 `GET /v1/models`를 쓴다."""
    ac.preflight("sk-test")

    assert calls[0]["url"] == "https://api.anthropic.com/v1/models"
    assert calls[0].get("payload") is None


def _stub_preflight_failure(
    monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    """프리플라이트가 주어진 HTTP 상태로 실패하도록 관문을 스텁한다."""
    def _boom(url: str, **_: Any) -> Any:
        raise gateway.GatewayError(f"실패 {status}", url=url, status=status)

    monkeypatch.setattr(gateway, "request_json", _boom)


@pytest.mark.parametrize("status", [401, 403])
def test_credential_rejection_is_an_auth_error(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """자격증명 거부(401·403)만 인증 실패로 분류한다 (§3 항목4)."""
    _stub_preflight_failure(monkeypatch, status)

    with pytest.raises(ac.CloudAuthError) as excinfo:
        ac.preflight("sk-bad")

    assert isinstance(excinfo.value, PreconditionError)
    assert ac.API_KEY_ENV_VAR in str(excinfo.value)  # 손댈 곳을 정확히 가리킨다


@pytest.mark.parametrize("status", [500, 502, 503, 529, 404, None])
def test_non_credential_failures_are_unavailable_not_auth(
    monkeypatch: pytest.MonkeyPatch, status: int | None
) -> None:
    """5xx·타임아웃(status=None) 등은 인증 실패로 뭉개지 않는다 — 엉뚱한 안내를 막는다."""
    _stub_preflight_failure(monkeypatch, status)

    with pytest.raises(ac.CloudUnavailableError) as excinfo:
        ac.preflight("sk-test")

    assert not isinstance(excinfo.value, ac.CloudAuthError)
    assert isinstance(excinfo.value, PreconditionError)  # 여전히 exit 1
    assert ac.API_KEY_ENV_VAR not in str(excinfo.value)  # API 키를 탓하지 않는다


def test_transient_failure_message_does_not_blame_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """일시적 5xx에 '키를 확인하라'고 안내하지 않는다 (코드 리뷰 검출 회귀)."""
    _stub_preflight_failure(monkeypatch, 503)

    with pytest.raises(ac.CloudUnavailableError) as excinfo:
        ac.preflight("sk-valid")

    message = str(excinfo.value)
    assert "네트워크" in message
    assert "API 키 문제는 아닙니다" in message


def test_both_preflight_errors_map_to_exit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """두 실패 유형 모두 선행 조건 실패라 파일을 하나도 처리하지 않는다 (신규 종료 코드 없음)."""
    for status in (401, 503):
        _stub_preflight_failure(monkeypatch, status)
        with pytest.raises(PreconditionError):
            ac.preflight("sk-test")


# --- Summarizer 프로토콜 (§4.3) ---------------------------------------------------


def test_summarizer_exposes_engine_and_model(calls: list[dict[str, Any]]) -> None:
    """파이프라인이 front-matter에 쓸 엔진·모델을 백엔드가 스스로 알고 있다."""
    summarizer = ac.AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test")

    summarizer.summarize("본문")

    assert summarizer.engine == "cloud"
    assert summarizer.model == DEFAULT_CLOUD_MODEL
    assert summarizer.last_mask is not None
