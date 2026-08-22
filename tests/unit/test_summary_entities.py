"""요약 응답의 `entities` 선택 필드 처리 (v0.6 스펙 §4.2).

`entities`는 §4.5 위키 템플릿의 어느 섹션에도 렌더되지 않는 그래프 전용 재료다. 없어도
위키는 정상 생성돼야 하고, 두 엔진이 같은 규칙을 써야 한다.
"""

from __future__ import annotations

import pytest

from corpbrain.core.llm.anthropic_client import SUMMARY_TOOL_SCHEMA
from corpbrain.core.llm.base import LLMParseError, validate_summary_fields
from corpbrain.core.llm.summarize import PROMPT_TEMPLATE


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "2026년도 신입 채용 계획",
        "one_line_summary": "상반기 신입 20명을 3개 직군으로 공채한다.",
        "key_points": ["직군 3개", "정원 20명", "상반기 진행"],
        "summary": "인사팀이 그리팅 ATS로 상반기 공채를 진행한다.",
        "tags": ["채용", "인사"],
    }
    base.update(overrides)
    return base


def test_entities_are_parsed_when_present() -> None:
    result = validate_summary_fields(_payload(entities=["인사팀", "그리팅 ATS"]))

    assert result.entities == ["인사팀", "그리팅 ATS"]


def test_missing_entities_becomes_empty_list_not_parse_error() -> None:
    """필수로 두면 로컬 모델이 빠뜨렸을 때 그 문서의 위키가 통째로 생성되지 않는다."""
    result = validate_summary_fields(_payload())

    assert result.entities == []
    assert result.title == "2026년도 신입 채용 계획"


@pytest.mark.parametrize("bad", ["인사팀", 42, None, {"a": 1}])
def test_non_list_entities_degrades_to_empty_list(bad: object) -> None:
    """타입이 어긋나도 그래프 재료만 비고 위키 생성은 막지 않는다."""
    result = validate_summary_fields(_payload(entities=bad))

    assert result.entities == []


def test_non_string_items_are_dropped_and_blanks_trimmed() -> None:
    result = validate_summary_fields(_payload(entities=["  인사팀  ", 7, "", "  ", "ATS"]))

    assert result.entities == ["인사팀", "ATS"]


def test_required_five_fields_still_raise_when_missing() -> None:
    """기존 5필드는 종전대로 필수다 — 전부 위키 템플릿에 직접 렌더되기 때문이다."""
    payload = _payload()
    del payload["tags"]

    with pytest.raises(LLMParseError):
        validate_summary_fields(payload)


def test_local_prompt_requests_entities() -> None:
    assert '"entities"' in PROMPT_TEMPLATE


def test_cloud_tool_schema_offers_entities_but_does_not_require_it() -> None:
    """엔진별로 필수 여부가 갈리면 같은 폴더가 엔진에 따라 다른 개수의 위키를 낸다."""
    schema = SUMMARY_TOOL_SCHEMA["input_schema"]

    assert "entities" in schema["properties"]
    assert "entities" not in schema["required"]
    assert schema["required"] == [
        "title",
        "one_line_summary",
        "key_points",
        "summary",
        "tags",
    ]
