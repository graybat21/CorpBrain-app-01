"""프로세스의 유일한 외부 네트워크 출구 — 단일 외부호출 관문 (스펙 §4.5).

코어의 다른 모듈(`ollama` 등)은 `urllib.request`·`http.client`·서드파티 HTTP 라이브러리를
직접 호출하지 않고, 반드시 이 모듈의 `request_json()`만 경유한다. 이 이음새 덕분에
후속 슬라이스의 클라우드 엔진·NetworkGuard·PII 마스킹 게이트를 이 한 곳에만 얹으면 된다.

이번 슬라이스에서 실제로 나가는 호출은 로컬 Ollama(`--ollama-url`) 하나뿐이며(스펙 §3-6),
테스트는 이 단일 지점을 monkeypatch로 스텁하고 `requested_urls()`로 감시해
'localhost 외 연결 없음'을 검증한다.

표준 라이브러리(`urllib.request`)만 사용한다 — 서드파티 HTTP 의존성을 두지 않는다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from corpbrain.core.errors import CorpBrainError

#: 관문이 이번 프로세스에서 시도한 URL 기록 (요청 순서). 소켓을 열기 전에 append 하므로
#: 실패한 호출도 남는다. 테스트·진단용 관찰 훅이며 정책 판단에는 쓰지 않는다.
_REQUESTED_URLS: list[str] = []


class GatewayError(CorpBrainError):
    """관문을 통한 외부 호출 실패 — 연결·HTTP 상태·JSON 직렬화/파싱 오류를 감싼다.

    Attributes:
        url: 실패한 호출의 대상 URL.
    """

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


def requested_urls() -> tuple[str, ...]:
    """관문이 시도한 URL을 요청 순서대로 돌려준다 (스냅샷).

    스펙 §3 완료의 정의 6번('`--ollama-url` 외 네트워크 연결 없음') 검증용 관찰 훅이다.
    """
    return tuple(_REQUESTED_URLS)


def reset_requested_urls() -> None:
    """`requested_urls()` 기록을 비운다 (테스트 격리용)."""
    _REQUESTED_URLS.clear()


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    timeout: float = 60.0,
) -> Any:
    """외부에 JSON 요청을 보내고 응답 JSON을 파싱해 반환한다 — 프로세스의 유일한 출구.

    Args:
        url: 대상 URL. 코어는 이 값을 주입받아 넘기며(하드코딩하지 않는다), 테스트는
            이 인자로 관문 통과 지점을 감시한다.
        method: HTTP 메서드.
        payload: 주어지면 JSON으로 직렬화해 본문으로 보낸다. `None`이면 본문 없는 요청.
        timeout: 소켓 타임아웃(초).

    Returns:
        응답 본문을 JSON 파싱한 값.

    Raises:
        GatewayError: 연결 실패·타임아웃·HTTP 오류 상태·JSON 직렬화/파싱 실패.
    """
    # --- 후속 확장 삽입 지점 (이번 슬라이스에서는 구현하지 않는다 — 스펙 §2 비목표) ---
    # NetworkGuard: 목적지 허용 판정(호스트·스킴 allowlist, 리다이렉트 추적 차단)은
    #   소켓을 열기 전인 이 지점에 들어간다.
    # PII 마스킹 게이트: 클라우드 엔진(Option A) 도입 시 `payload` 마스킹과 사용자 동의
    #   확인도 같은 지점에서 수행한다.
    # 이번 슬라이스는 로컬 Ollama 호출뿐이므로 두 게이트 모두 두지 않고, 대신 시도한
    # URL만 기록해 테스트가 목적지를 감시할 수 있게 한다.
    _REQUESTED_URLS.append(url)

    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if payload is not None:
        try:
            body = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise GatewayError(
                f"요청 본문을 JSON으로 직렬화하지 못했습니다: {exc}", url=url
            ) from exc
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = _read_error_body(exc)
        message = f"외부 호출이 HTTP {exc.code}로 실패했습니다: {url}"
        if detail:
            message = f"{message} — {detail}"
        raise GatewayError(message, url=url) from exc
    except urllib.error.URLError as exc:
        raise GatewayError(
            f"외부 호출에 연결하지 못했습니다: {url} ({exc.reason})", url=url
        ) from exc
    except OSError as exc:  # 타임아웃 등 소켓 계층 오류
        raise GatewayError(f"외부 호출이 실패했습니다: {url} ({exc})", url=url) from exc

    try:
        # bytes 응답도 그대로 받는다. 디코딩 실패(UnicodeDecodeError)·문법 오류
        # (JSONDecodeError) 모두 ValueError 하위라 한 번에 잡는다.
        return json.loads(raw)
    except ValueError as exc:
        raise GatewayError(
            f"응답을 JSON으로 파싱하지 못했습니다: {url} ({exc})", url=url
        ) from exc


def _read_error_body(exc: urllib.error.HTTPError, *, limit: int = 500) -> str:
    """HTTP 오류 응답 본문에서 서버 메시지를 뽑는다 (진단용, 최대 limit자).

    Ollama처럼 `{"error": "..."}` 형태면 그 값만, 아니면 원문 앞부분을 돌려준다.
    본문을 읽을 수 없으면(예: fp 없음) 빈 문자열을 돌려준다 — 진단이 실패를 가리지 않게 한다.
    """
    try:
        raw = exc.read()
    except Exception:  # noqa: BLE001 - 본문을 못 읽어도 상태코드 메시지는 그대로 나가야 한다
        return ""
    if not raw:
        return ""
    text = raw.decode("utf-8", "replace").strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
        text = parsed["error"]
    return " ".join(text.split())[:limit]
