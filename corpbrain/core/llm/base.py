"""요약 백엔드 공통 계약 — 인터페이스와 응답 검증 (v0.5 스펙 §4.3).

로컬(Ollama)과 클라우드(Anthropic) 두 백엔드가 같은 `SummaryResult`를 내도록, 응답 검증
규칙을 이 한 곳에 두고 양쪽이 함께 쓴다. 검증 규칙이 갈라지면 "엔진에 따라 위키 품질 기준이
달라지는" 상황이 생기므로 의도적으로 공유한다.

`Summarizer` 프로토콜은 파이프라인이 엔진을 값으로 고르게 하는 이음새다 — 파이프라인은
구현체가 로컬인지 클라우드인지 모른 채 `summarize(text)`만 호출한다.
"""

from __future__ import annotations

from typing import Any, Protocol

from corpbrain.core.errors import CorpBrainError
from corpbrain.core.models import SummaryResult
from corpbrain.core.pii import MaskingResult

#: 문자열 필드와 문자열 배열 필드 (스펙 §4.3의 고정 필드).
TEXT_FIELDS = ("title", "one_line_summary", "summary")
LIST_FIELDS = ("key_points", "tags")

#: 있으면 쓰고 없으면 빈 배열로 두는 배열 필드 (v0.6 §4.2).
#:
#: `entities`는 §4.5 위키 템플릿의 어느 섹션에도 렌더되지 않는 **그래프 전용 재료**다.
#: 필수로 두면 프롬프트로만 요청받는 로컬 모델이 이 필드를 빠뜨렸을 때 제목·요약·태그를
#: 모두 정상 수신했음에도 그 문서의 위키가 통째로 생성되지 않고, 같은 모델이면 재실행에서도
#: 반복된다. 재료가 없으면 그 엣지만 빠지는 것이 v0.6의 다른 «재료 부재» 처리와 일관된다.
OPTIONAL_LIST_FIELDS = ("entities",)


class LLMParseError(CorpBrainError):
    """LLM 응답을 고정 필드 JSON으로 해석하지 못함 — 해당 파일만 스킵된다."""


class Summarizer(Protocol):
    """요약 백엔드 1개의 계약 — 절단된 텍스트를 고정 필드 요약으로 바꾼다.

    구현체는 자신이 쓸 모델·엔드포인트·자격증명을 생성 시점에 이미 알고 있어야 한다.
    파이프라인은 문서 텍스트만 넘기고 백엔드 종류를 알지 못한다 (v0.5 스펙 §4.3).
    """

    #: 생성물 front-matter에 기록할 엔진 이름 (`"local"` 또는 `"cloud"`).
    engine: str
    #: 생성물 front-matter에 기록할 실제 모델 이름.
    model: str
    #: 직전 `summarize()` 호출에서 마스킹한 PII 집계 (v0.5 스펙 §4.5).
    #:
    #: 외부로 나가지 않는 백엔드(로컬 Ollama)는 마스킹할 이유가 없으므로 **항상 `None`**이다.
    #: 계약의 일부로 두는 이유는, 파이프라인이 `getattr`로 속성을 더듬으면 이름이 바뀌거나
    #: 새 백엔드가 다르게 부를 때 PII 리포트가 **아무 오류 없이 사라지기** 때문이다.
    last_mask: MaskingResult | None

    def summarize(self, text: str) -> SummaryResult:
        """절단된 문서 텍스트를 고정 필드 요약으로 변환한다.

        Raises:
            LLMParseError: 요청 실패, 응답 파싱 실패, 필수 필드 누락·타입 불일치.
        """
        ...


def validate_summary_fields(parsed: Any) -> SummaryResult:
    """모델이 낸 JSON 객체(dict)를 검증해 `SummaryResult`로 만든다.

    로컬·클라우드 두 백엔드가 공유하는 단일 검증 규칙이다 — 필수 5필드, 문자열 필드는
    공백 불허, 배열 필드는 문자열 배열만 허용한다 (v0.5 스펙 §4.3). v0.6의 `entities`는
    선택 필드로, 없거나 문자열 배열이 아니면 빈 배열로 둔다 (v0.6 §4.2).

    엔진별로 필수 여부를 달리하지 않는다 — 같은 폴더를 `--engine local`로 돌렸을 때와
    `cloud`로 돌렸을 때 생성되는 위키 개수가 달라지기 때문이다.
    """
    if not isinstance(parsed, dict):
        raise LLMParseError(f"응답 JSON이 객체가 아닙니다: {type(parsed).__name__}")

    values: dict[str, Any] = {}
    for field in TEXT_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, str) or not value.strip():
            raise LLMParseError(f"필수 문자열 필드가 없거나 비어 있습니다: {field}")
        values[field] = value.strip()

    for field in LIST_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise LLMParseError(f"필수 배열 필드가 문자열 배열이 아닙니다: {field}")
        values[field] = [item.strip() for item in value if item.strip()]

    for field in OPTIONAL_LIST_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, list):
            values[field] = []
            continue
        values[field] = [item.strip() for item in value if isinstance(item, str) and item.strip()]

    return SummaryResult(
        title=values["title"],
        one_line_summary=values["one_line_summary"],
        key_points=values["key_points"],
        summary=values["summary"],
        tags=values["tags"],
        entities=values["entities"],
    )
