"""임베딩 — Ollama 로컬 임베딩 모델 호출 (v0.4 스펙 §4.3).

`llm/summarize.py`와 동일한 패턴을 따른다: 네트워크는
`corpbrain.core.gateway.request_json()`만 경유하고, 이 모듈은 HTTP 라이브러리를 직접
import 하지 않는다 (스펙 §4.5 단일 외부호출 관문).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크 호출 없음

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_OLLAMA_URL
from corpbrain.core.errors import CorpBrainError

#: 단일 프롬프트 임베딩 엔드포인트.
EMBED_PATH = "/api/embeddings"

#: 임베딩 1건의 소켓 타임아웃(초) — 요약보다 짧아도 충분하다(입력이 위키 요약 콘텐츠뿐).
DEFAULT_TIMEOUT = 60.0


class EmbeddingError(CorpBrainError):
    """임베딩 요청 실패 또는 응답 파싱 실패 — 해당 문서만 인덱싱 실패로 흡수된다."""


def embed(
    text: str,
    model: str = DEFAULT_EMBED_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[float]:
    """텍스트를 임베딩 벡터로 변환한다.

    Args:
        text: 임베딩할 텍스트(문서당 1개 — 청크 분할 없음, v0.4 스펙 §4.3).
        model: Ollama 임베딩 모델 이름.
        ollama_url: `--ollama-url` 값. 이 대상 외에는 접속하지 않는다.
        timeout: 요청 소켓 타임아웃(초).

    Raises:
        EmbeddingError: 요청 실패 또는 응답에 숫자 배열 `embedding` 필드가 없음.
    """
    url = _embed_url(ollama_url)
    payload = {"model": model, "prompt": text}
    try:
        envelope = gateway.request_json(url, method="POST", payload=payload, timeout=timeout)
    except gateway.GatewayError as exc:
        raise EmbeddingError(f"임베딩 요청에 실패했습니다: {url} ({exc})") from exc
    return _parse_embedding(envelope)


def _parse_embedding(envelope: Any) -> list[float]:
    if not isinstance(envelope, dict):
        raise EmbeddingError(f"임베딩 응답이 JSON 객체가 아닙니다: {type(envelope).__name__}")
    vector = envelope.get("embedding")
    if not isinstance(vector, list) or not vector or not all(
        isinstance(item, (int, float)) and not isinstance(item, bool) for item in vector
    ):
        raise EmbeddingError("임베딩 응답에 숫자 배열 `embedding` 필드가 없습니다.")
    return [float(item) for item in vector]


def _embed_url(ollama_url: str) -> str:
    """임베딩 엔드포인트 URL을 조립한다 (베이스 경로 보존 — `ollama_client._health_url`과 동일 규칙)."""
    base = ollama_url if ollama_url.endswith("/") else f"{ollama_url}/"
    return urljoin(base, EMBED_PATH.lstrip("/"))
