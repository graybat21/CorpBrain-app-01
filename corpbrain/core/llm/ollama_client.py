"""Ollama 로컬 HTTP 클라이언트 — 탐지 전용 (스펙 §4.3, §5).

구동 중인 인스턴스를 **탐지만** 한다. 설치·프로비저닝은 어떤 경우에도 시도하지 않으며
(스펙 §2 비목표·§4.3), 미탐지는 개별 파일의 부분 실패가 아니라 선행 조건 실패이므로
어댑터가 비-0 종료로 매핑한다 (스펙 §3-5, §5).

네트워크는 `corpbrain.core.gateway.request_json()`만 경유한다 — 이 모듈은 HTTP
라이브러리를 직접 import 하지 않는다 (스펙 §4.5 단일 외부호출 관문).

요약 요청·프롬프트·모델 존재 검사는 이 모듈의 범위가 아니다 (FR-010).
"""

from __future__ import annotations

from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크 호출 없음

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_OLLAMA_URL
from corpbrain.core.errors import PreconditionError

#: 헬스체크 엔드포인트. 구동 중인 Ollama는 설치된 모델 목록을 JSON 객체로 돌려준다.
#: 이번 슬라이스는 응답 내용을 판정에 쓰지 않고 '응답하는가'만 본다.
HEALTH_PATH = "/api/tags"


class OllamaNotAvailableError(PreconditionError):
    """Ollama 미탐지·미구동 — 선행 조건 실패이므로 상위 계층이 비-0 종료로 매핑한다."""


def _health_url(ollama_url: str) -> str:
    """헬스체크 대상 URL을 조립한다 (문자열 처리만 — 네트워크 접촉 없음).

    베이스에 경로가 붙어 있어도(리버스 프록시 뒤 등) 그 경로를 보존하도록 항상 슬래시로
    끝나는 베이스에 상대 경로를 결합한다.
    """
    base = ollama_url if ollama_url.endswith("/") else f"{ollama_url}/"
    return urljoin(base, HEALTH_PATH.lstrip("/"))


def detect(ollama_url: str = DEFAULT_OLLAMA_URL, *, timeout: float = 5.0) -> None:
    """구동 중인 로컬 Ollama를 탐지한다 — 정상이면 그대로 반환, 아니면 예외.

    Args:
        ollama_url: `--ollama-url` 값 (기본 localhost). 이 대상 외에는 접속하지 않는다.
        timeout: 헬스체크 소켓 타임아웃(초). 미구동 대상에 오래 매달리지 않기 위한 값이다.

    Raises:
        OllamaNotAvailableError: 연결 거부·타임아웃·HTTP 오류 상태·JSON 파싱 실패
            (`GatewayError` 전반), 또는 응답이 JSON 객체가 아닌 비정상 형태.
            어느 경우에도 설치·프로비저닝을 시도하지 않는다.
    """
    url = _health_url(ollama_url)
    try:
        response = gateway.request_json(url, timeout=timeout)
    except gateway.GatewayError as exc:
        raise OllamaNotAvailableError(
            f"구동 중인 로컬 Ollama를 찾지 못했습니다: {url} ({exc})"
        ) from exc

    if not isinstance(response, dict):
        raise OllamaNotAvailableError(
            f"Ollama 헬스체크 응답이 예상 형태(JSON 객체)가 아닙니다: {url} "
            f"({type(response).__name__})"
        )
