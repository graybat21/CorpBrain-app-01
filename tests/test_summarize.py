"""요약 요청·JSON 파싱 단위테스트 (FR-010 / 스펙 §4.3, §5).

실제 네트워크는 쓰지 않는다 — 단일 관문 `gateway.request_json`을 스텁한다.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.llm.summarize import (
    LLMParseError,
    build_prompt,
    parse_summary,
    summarize,
)
from corpbrain.core.models import SummaryResult

VALID_PAYLOAD = {
    "title": "분기 실적 보고",
    "one_line_summary": "매출이 전년 대비 12% 늘었다.",
    "key_points": ["매출 12% 증가", "신규 고객 34곳", "이탈률 감소"],
    "summary": "상반기 실적을 요약한 문단이다.",
    "tags": ["실적", "영업"],
}


@pytest.fixture
def stub_gateway(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """관문 호출을 가로채 요청을 기록하고 지정한 본문을 돌려준다."""
    calls: list[dict[str, Any]] = []

    def _fake_request_json(url: str, **kwargs: Any) -> Any:
        calls.append({"url": url, **kwargs})
        return {"response": _fake_request_json.body}  # type: ignore[attr-defined]

    _fake_request_json.body = json.dumps(VALID_PAYLOAD, ensure_ascii=False)  # type: ignore[attr-defined]
    monkeypatch.setattr(gateway, "request_json", _fake_request_json)
    return calls


def test_valid_json_becomes_summary_result(stub_gateway: list[dict[str, Any]]) -> None:
    result = summarize("문서 본문", model="qwen2.5:7b-instruct", ollama_url="http://127.0.0.1:11434")

    assert isinstance(result, SummaryResult)
    assert result.title == "분기 실적 보고"
    assert result.key_points == VALID_PAYLOAD["key_points"]
    assert result.tags == VALID_PAYLOAD["tags"]


def test_request_targets_generate_endpoint_on_given_url(stub_gateway: list[dict[str, Any]]) -> None:
    summarize("문서 본문", model="m", ollama_url="http://127.0.0.1:11434")

    assert len(stub_gateway) == 1
    call = stub_gateway[0]
    assert call["url"] == "http://127.0.0.1:11434/api/generate"
    assert call["method"] == "POST"
    assert call["payload"]["model"] == "m"
    assert call["payload"]["stream"] is False
    assert call["payload"]["format"] == "json"


def test_prompt_requests_korean_fixed_fields() -> None:
    prompt = build_prompt("문서 본문")

    assert "한국어" in prompt
    for field in ("title", "one_line_summary", "key_points", "summary", "tags"):
        assert field in prompt
    assert "문서 본문" in prompt


def test_broken_json_raises_parse_error(
    stub_gateway: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken(url: str, **kwargs: Any) -> Any:
        return {"response": "이건 JSON이 아닙니다"}

    monkeypatch.setattr(gateway, "request_json", _broken)

    with pytest.raises(LLMParseError):
        summarize("문서 본문", model="m", ollama_url="http://127.0.0.1:11434")


def test_gateway_failure_raises_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(url: str, **kwargs: Any) -> Any:
        raise gateway.GatewayError("연결 거부", url=url)

    monkeypatch.setattr(gateway, "request_json", _fail)

    with pytest.raises(LLMParseError):
        summarize("문서 본문", model="m", ollama_url="http://127.0.0.1:11434")


@pytest.mark.parametrize(
    "mutation",
    [
        {"title": None},
        {"title": ""},
        {"one_line_summary": 3},
        {"summary": None},
        {"key_points": "배열이 아님"},
        {"key_points": [1, 2, 3]},
        {"tags": None},
    ],
)
def test_missing_or_wrong_typed_fields_raise_parse_error(mutation: dict[str, Any]) -> None:
    payload = {**VALID_PAYLOAD, **mutation}

    with pytest.raises(LLMParseError):
        parse_summary(json.dumps(payload, ensure_ascii=False))


def test_dropped_field_raises_parse_error() -> None:
    payload = {key: value for key, value in VALID_PAYLOAD.items() if key != "tags"}

    with pytest.raises(LLMParseError):
        parse_summary(json.dumps(payload, ensure_ascii=False))


def test_non_object_json_raises_parse_error() -> None:
    with pytest.raises(LLMParseError):
        parse_summary("[1, 2, 3]")


def test_envelope_without_response_field_raises_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gateway, "request_json", lambda url, **kwargs: {"error": "boom"})

    with pytest.raises(LLMParseError):
        summarize("문서 본문", model="m", ollama_url="http://127.0.0.1:11434")


def test_empty_array_fields_are_allowed_but_trimmed() -> None:
    payload = {**VALID_PAYLOAD, "tags": ["  실적  ", "  "]}

    result = parse_summary(json.dumps(payload, ensure_ascii=False))

    assert result.tags == ["실적"]
