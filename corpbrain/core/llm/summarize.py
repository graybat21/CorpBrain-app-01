"""요약·구조화 — 고정 필드 JSON 요청과 파싱 (스펙 §4.3, §5).

모델에게 `title`/`one_line_summary`/`key_points`/`summary`/`tags` 다섯 필드를 가진 JSON을
한국어로 요청하고, 그 응답을 엄격히 검증해 `SummaryResult`로 돌려준다. 마크다운 조립은
코드가 결정적으로 수행하므로(FR-011) 모델은 문서 구조를 만들지 않는다.

입력 텍스트는 이미 `--max-chars`로 절단된 상태로 들어온다 (FR-008).
JSON 파싱·검증 실패는 해당 파일만의 실패이며, 파이프라인이 스킵으로 흡수한다 (스펙 §5).
네트워크는 `corpbrain.core.gateway.request_json()`만 경유한다 (스펙 §4.5).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크 호출 없음

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from corpbrain.core.llm.base import LLMParseError, validate_summary_fields
from corpbrain.core.models import SummaryResult

#: 단일 프롬프트 생성 엔드포인트.
GENERATE_PATH = "/api/generate"

#: 요약 1건의 소켓 타임아웃(초). 로컬 7B 모델이 12,000자를 처리할 여유를 둔다.
DEFAULT_TIMEOUT = 300.0

PROMPT_TEMPLATE = """당신은 사내 문서를 정리하는 한국어 지식 관리 도우미입니다.
아래 문서를 읽고 JSON 객체 하나만 출력하세요. 설명·코드블록·군더더기 없이 JSON만 출력합니다.

JSON 스키마:
{{
  "title": "문서를 대표하는 제목 (문자열)",
  "one_line_summary": "문서를 한 문장으로 요약 (문자열)",
  "key_points": ["핵심 포인트 3~7개 (문자열 배열)"],
  "summary": "문단 하나 분량의 요약 (문자열)",
  "tags": ["문서를 대표하는 키워드 (문자열 배열)"]
}}

규칙:
- 모든 값은 반드시 한국어로 작성합니다.
- 문서에 없는 내용을 지어내지 않습니다.
- key_points는 3개 이상 7개 이하로 작성합니다.

문서:
\"\"\"
{document}
\"\"\"
"""


def build_prompt(text: str) -> str:
    """요약 프롬프트를 만든다 (출력 언어는 항상 한국어 — 스펙 §4.3)."""
    return PROMPT_TEMPLATE.format(document=text)


def summarize(
    text: str,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> SummaryResult:
    """절단된 문서 텍스트를 고정 필드 요약으로 변환한다.

    Args:
        text: `--max-chars`까지 절단된 문서 텍스트.
        model: Ollama 모델 이름 (CLI가 주입).
        ollama_url: `--ollama-url` 값. 이 대상 외에는 접속하지 않는다.
        timeout: 요청 소켓 타임아웃(초).

    Raises:
        LLMParseError: 요청 실패, JSON 파싱 실패, 필수 필드 누락·타입 불일치.
    """
    url = _generate_url(ollama_url)
    payload = {
        "model": model,
        "prompt": build_prompt(text),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }

    try:
        envelope = gateway.request_json(url, method="POST", payload=payload, timeout=timeout)
    except gateway.GatewayError as exc:
        raise LLMParseError(f"요약 요청에 실패했습니다: {url} ({exc})") from exc

    return parse_summary(_response_text(envelope))


def parse_summary(raw: str) -> SummaryResult:
    """모델이 낸 JSON 문자열을 검증해 `SummaryResult`로 만든다.

    필드 검증 규칙 자체는 클라우드 백엔드와 공유한다 (`llm.base.validate_summary_fields`) —
    엔진에 따라 위키 품질 기준이 달라지지 않게 한다 (v0.5 스펙 §4.3).
    """
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise LLMParseError(f"응답이 유효한 JSON이 아닙니다: {raw[:200]!r}") from exc

    return validate_summary_fields(parsed)


def _response_text(envelope: Any) -> str:
    """Ollama `/api/generate` 응답 봉투에서 모델이 생성한 본문 문자열을 꺼낸다."""
    if not isinstance(envelope, dict):
        raise LLMParseError(f"Ollama 응답이 JSON 객체가 아닙니다: {type(envelope).__name__}")
    body = envelope.get("response")
    if not isinstance(body, str):
        raise LLMParseError("Ollama 응답에 문자열 `response` 필드가 없습니다.")
    return body


def _generate_url(ollama_url: str) -> str:
    """생성 엔드포인트 URL을 조립한다 (베이스 경로 보존 — `ollama_client._health_url`과 동일 규칙)."""
    base = ollama_url if ollama_url.endswith("/") else f"{ollama_url}/"
    return urljoin(base, GENERATE_PATH.lstrip("/"))
