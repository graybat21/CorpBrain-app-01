"""요약 응답의 `entities` 처리 (v0.6 스펙 §4.2, v0.6.1 정정).

`entities`는 §4.5 위키 템플릿의 어느 섹션에도 렌더되지 않는 그래프 전용 재료다. **검증**은
두 엔진이 공유하며 없어도 위키는 정상 생성된다. **요청**은 갈린다 — 스키마를 강제할 수 있는
클라우드는 `required`로 확실히 받아 오고, 프롬프트로만 요청할 수 있는 로컬은 그러지 못한다.
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


def test_cloud_tool_schema_requires_entities() -> None:
    """클라우드는 `required`로 확실히 받아 온다 (v0.6.1 · §4.2).

    v0.6.0은 선택으로 뒀는데, 스모크에서 문서 6개 중 5개가 `entities: []`로 왔다 —
    `tool_use`로 스키마를 강제받는 모델은 required는 채우고 선택 필드는 건너뛴다.
    """
    schema = SUMMARY_TOOL_SCHEMA["input_schema"]

    assert "entities" in schema["properties"]
    assert "entities" in schema["required"]


def test_cloud_required_does_not_change_how_many_wikis_are_produced() -> None:
    """엔진이 갈려도 위키 개수는 같다 — v0.6.0이 «선택»의 근거로 든 부작용이 없음을 고정한다.

    ① 클라우드는 `tool_choice`가 스키마를 강제하므로 **누락 자체가 불가능**하고,
    ② 로컬은 종전대로 누락을 허용해(검증은 두 엔진 공유) 문서가 실패하지 않는다.
    둘 중 하나라도 깨지면 같은 폴더가 엔진에 따라 다른 개수의 위키를 낸다.
    """
    assert validate_summary_fields(_payload()).entities == []  # 로컬 누락 → 위키는 정상
