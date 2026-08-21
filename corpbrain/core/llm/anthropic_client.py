"""Anthropic Messages API 클라이언트 — 클라우드 요약 백엔드 (v0.5 스펙 §4.3·§4.4).

공식 SDK(`anthropic` 패키지)를 쓰지 않는다. SDK는 내부적으로 자체 HTTP 커넥션을 열어
`corpbrain.core.gateway`의 단일 관문을 우회하며, 그러면 NetworkGuard·PII 마스킹 게이트가
클라우드 경로를 보호하지 못한다. 대신 관문의 `headers` 통로로 인증 헤더를 실어 raw HTTP로
Messages API를 직접 호출한다 — 이 모듈은 HTTP 라이브러리를 직접 import 하지 않는다.

고정 5필드 JSON은 tool use(function calling)로 스키마를 강제한다 — Ollama의 프롬프트 기반
`format: "json"`보다 스키마 준수가 구조적으로 보장된다. 검증 규칙 자체는 로컬 백엔드와
공유한다(`llm.base.validate_summary_fields`) — 엔진에 따라 위키 품질 기준이 달라지지 않게 한다.

**API 키는 이 모듈이 호출 시점에 환경변수에서 직접 읽는다.** `ScanConfig` 같은 값 객체에
싣지 않는다 — 값 객체는 로그·에러 메시지에 그대로 찍힐 수 있어 자격증명의 수명과 노출면을
최소화하기 위함이다 (v0.5 스펙 §4.1 "환경변수로만 받는다").
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크 호출 없음

from corpbrain.core import gateway
from corpbrain.core.errors import CorpBrainError, PreconditionError
from corpbrain.core.llm.base import LLMParseError, validate_summary_fields
from corpbrain.core.models import SummaryResult
from corpbrain.core.pii import MaskingResult, mask_pii

#: NetworkGuard allowlist — 하드코딩 단일 호스트이며 CLI로 override할 수 없다 (v0.5 §4.4).
ANTHROPIC_HOST = "api.anthropic.com"
ANTHROPIC_BASE_URL = f"https://{ANTHROPIC_HOST}"
MESSAGES_PATH = "/v1/messages"
MODELS_PATH = "/v1/models"

#: Anthropic API 버전 헤더 (Messages API 안정 버전).
ANTHROPIC_VERSION = "2023-06-01"

#: API 키를 받는 유일한 통로 — Anthropic 공식 관례와 같은 이름을 재사용한다 (v0.5 §4.1).
API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

#: 요약 1건의 소켓 타임아웃(초). 같은 성격의 로컬 요약(`summarize.DEFAULT_TIMEOUT`)과 같은 값.
DEFAULT_TIMEOUT = 300.0
#: 인증 프리플라이트(`GET /v1/models`)는 가벼운 호출이라 관문 기본 타임아웃을 쓴다.
PREFLIGHT_TIMEOUT = 60.0

#: 요약 출력 상한. `--max-chars` 12,000자 입력 대비 5필드 요약에 충분한 여유 (v0.5 §4.3).
MAX_TOKENS = 2048

#: 스키마를 강제하는 도구 이름 (v0.5 §4.3).
SUMMARY_TOOL_NAME = "emit_summary"

#: tool use 입력 스키마 — 5필드 모두 required. `minItems`/`maxItems`는 두지 않는다.
#: (로컬 `parse_summary`와 동일하게 "비어있지 않은 문자열 배열"만 검증해 규칙을 일치시킨다.)
SUMMARY_TOOL_SCHEMA: dict[str, Any] = {
    "name": SUMMARY_TOOL_NAME,
    "description": "문서 요약 결과를 고정 5필드로 제출한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "문서를 대표하는 제목"},
            "one_line_summary": {"type": "string", "description": "문서를 한 문장으로 요약"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "핵심 포인트 3~7개",
            },
            "summary": {"type": "string", "description": "문단 하나 분량의 요약"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "문서를 대표하는 키워드",
            },
        },
        "required": ["title", "one_line_summary", "key_points", "summary", "tags"],
    },
}

__all__ = [
    "ANTHROPIC_HOST",
    "API_KEY_ENV_VAR",
    "AnthropicSummarizer",
    "CloudApiError",
    "CloudAuthError",
    "CloudRateLimitedError",
    "preflight",
    "resolve_api_key",
    "summarize_cloud",
]


class CloudAuthError(PreconditionError):
    """API 키 부재 또는 인증 실패(401) — 선행 조건 실패라 파일을 하나도 처리하지 않는다.

    v0.5 스펙 §3 항목4: 프리플라이트에서 걸러 exit 1로 즉시 종료한다.
    """


class CloudRateLimitedError(CorpBrainError):
    """레이트리밋(429) — 재시도 없이 해당 파일만 스킵한다 (v0.5 §3 항목8)."""


class CloudApiError(CorpBrainError):
    """429 외 모든 클라우드 호출 실패 — 재시도 없이 해당 파일만 스킵한다.

    5xx·타임아웃·연결오류뿐 아니라 400·404(잘못된 모델명 등 요청 자체 결함)도 여기로
    수렴한다 (v0.5 §3 항목8 매핑 규칙 — 신규 스킵 사유는 두 종류뿐이다).
    """


def resolve_api_key() -> str:
    """환경변수에서 API 키를 읽는다 — 이 모듈이 자격증명을 만지는 유일한 지점.

    Raises:
        CloudAuthError: 환경변수가 없거나 비어 있음 (선행 조건 실패).
    """
    key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    if not key:
        raise CloudAuthError(
            f"{API_KEY_ENV_VAR} 환경변수가 설정되어 있지 않습니다 — "
            f"cloud 엔진을 쓰려면 Anthropic API 키를 이 환경변수로 지정하세요."
        )
    return key


def _auth_headers(api_key: str) -> dict[str, str]:
    """Anthropic 인증 헤더를 만든다 (관문의 `headers` 통로로 실린다)."""
    return {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}


def _endpoint(path: str) -> str:
    """API 엔드포인트 URL을 조립한다 (문자열 처리만 — 네트워크 접촉 없음)."""
    return urljoin(f"{ANTHROPIC_BASE_URL}/", path.lstrip("/"))


def _request(
    path: str,
    api_key: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    """관문을 통해 Anthropic API를 호출한다 — NetworkGuard·HTTPS 강제를 항상 건다."""
    return gateway.request_json(
        _endpoint(path),
        method=method,
        payload=payload,
        headers=_auth_headers(api_key),
        timeout=timeout,
        allowed_hosts=(ANTHROPIC_HOST,),
        require_https=True,
    )


def preflight(api_key: str, *, timeout: float = PREFLIGHT_TIMEOUT) -> None:
    """파일 루프 진입 전에 API 키 유효성과 연결성을 1회 확인한다 (v0.5 §4.3).

    `GET /v1/models`는 토큰 비용이 없다. 기존 v0.3의 Ollama 모델 존재 확인과 같은 자리 —
    "환경/인증을 자원 처리보다 먼저 확정한다"는 fail-fast 관례를 따른다.

    Raises:
        CloudAuthError: 인증 실패(401) 또는 그 밖의 연결·응답 실패. 어느 쪽이든 파일을
            하나도 처리하지 않고 종료해야 하는 선행 조건 실패다.
    """
    try:
        _request(MODELS_PATH, api_key, timeout=timeout)
    except gateway.GatewayError as exc:
        raise CloudAuthError(
            f"Anthropic API 프리플라이트에 실패했습니다: {exc} — "
            f"{API_KEY_ENV_VAR} 값과 네트워크 연결을 확인하세요."
        ) from exc


def summarize_cloud(
    text: str,
    model: str,
    api_key: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[SummaryResult, MaskingResult]:
    """절단된 문서 텍스트를 클라우드에서 고정 필드 요약으로 변환한다.

    전송 직전 PII 7종을 마스킹한다 (v0.5 §4.5) — 원문 PII는 관문 밖으로 나가지 않는다.

    Args:
        text: `--max-chars`까지 절단된 문서 텍스트.
        model: `--cloud-model` 값.
        api_key: `resolve_api_key()`가 돌려준 키.
        timeout: 요청 소켓 타임아웃(초).

    Returns:
        (요약 결과, PII 마스킹 결과). 마스킹 결과는 리포트에 치환 건수를 표시하는 데 쓴다.

    Raises:
        CloudRateLimitedError: 레이트리밋(429).
        CloudApiError: 그 밖의 호출 실패(5xx·타임아웃·연결오류·400/404 등).
        LLMParseError: 응답이 tool use 스키마를 어겨 5필드를 얻지 못함.
    """
    masked = mask_pii(text)
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "tools": [SUMMARY_TOOL_SCHEMA],
        "tool_choice": {"type": "tool", "name": SUMMARY_TOOL_NAME},
        "messages": [{"role": "user", "content": build_prompt(masked.text)}],
    }

    try:
        envelope = _request(
            MESSAGES_PATH, api_key, method="POST", payload=payload, timeout=timeout
        )
    except gateway.GatewayError as exc:
        raise _classify_call_failure(exc) from exc

    return validate_summary_fields(_tool_input(envelope)), masked


def build_prompt(document: str) -> str:
    """요약 프롬프트를 만든다 — 로컬과 같은 지침을 쓰되 JSON 포맷 강제 문구는 뺀다.

    스키마 강제는 `tool_choice`가 담당하므로 "JSON만 출력하라" 류의 문구가 필요 없다
    (v0.5 §4.3). 한국어 출력·5필드 의미·환각 금지 등 provider 무관한 제품 규칙은 그대로 둔다.
    """
    return PROMPT_TEMPLATE.format(tool_name=SUMMARY_TOOL_NAME, document=document)


PROMPT_TEMPLATE = """당신은 사내 문서를 정리하는 한국어 지식 관리 도우미입니다.
아래 문서를 읽고 {tool_name} 도구를 호출해 요약 결과를 제출하세요.

규칙:
- 모든 값은 반드시 한국어로 작성합니다.
- 문서에 없는 내용을 지어내지 않습니다.
- key_points는 3개 이상 7개 이하로 작성합니다.
- 문서에 [REDACTED_...] 표시가 있으면 개인정보가 가려진 자리입니다. 그 값을 추측하지 마세요.

문서:
\"\"\"
{document}
\"\"\"
"""


def _classify_call_failure(exc: gateway.GatewayError) -> CorpBrainError:
    """관문 실패를 v0.5 §3 항목8의 두 스킵 사유로 매핑한다 — 429만 레이트리밋."""
    if _is_rate_limited(exc):
        return CloudRateLimitedError(f"Anthropic API 레이트리밋(429): {exc}")
    return CloudApiError(f"Anthropic API 호출에 실패했습니다: {exc}")


def _is_rate_limited(exc: gateway.GatewayError) -> bool:
    """관문이 감싼 원인 예외에서 HTTP 429를 판별한다 (상태코드는 원인에만 남아 있다)."""
    cause = exc.__cause__
    return getattr(cause, "code", None) == 429


def _tool_input(envelope: Any) -> Any:
    """Messages 응답에서 강제된 도구 호출의 입력(5필드 객체)을 꺼낸다."""
    if not isinstance(envelope, dict):
        raise LLMParseError(
            f"Anthropic 응답이 JSON 객체가 아닙니다: {type(envelope).__name__}"
        )
    content = envelope.get("content")
    if not isinstance(content, list):
        raise LLMParseError("Anthropic 응답에 content 배열이 없습니다.")
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == SUMMARY_TOOL_NAME
        ):
            return block.get("input")
    raise LLMParseError(
        f"Anthropic 응답에 {SUMMARY_TOOL_NAME} 도구 호출이 없습니다 "
        f"(stop_reason={envelope.get('stop_reason')!r})."
    )


class AnthropicSummarizer:
    """클라우드 요약 백엔드 — `llm.base.Summarizer` 프로토콜 구현 (v0.5 §4.3)."""

    engine = "cloud"

    def __init__(self, model: str, api_key: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout = timeout
        #: 직전 요약에서 마스킹된 PII 건수 (리포트 집계용).
        self.last_mask: MaskingResult | None = None

    def summarize(self, text: str) -> SummaryResult:
        """문서 텍스트를 클라우드에서 요약한다 (전송 직전 PII 마스킹)."""
        summary, masked = summarize_cloud(
            text, self.model, self._api_key, timeout=self._timeout
        )
        self.last_mask = masked
        return summary
