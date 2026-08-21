"""프로세스의 유일한 외부 네트워크 출구 — 단일 외부호출 관문 (스펙 §4.5).

코어의 다른 모듈(`ollama`·`anthropic` 등)은 `urllib.request`·`http.client`·서드파티 HTTP
라이브러리를 직접 호출하지 않고, 반드시 이 모듈의 `request_json()`만 경유한다. 이 이음새
덕분에 NetworkGuard(목적지 allowlist·리다이렉트 차단)를 이 한 곳에만 얹으면 로컬·클라우드
경로가 함께 보호된다.

나가는 호출은 두 갈래뿐이다 — 로컬 Ollama(`--ollama-url`)와, `--engine cloud`일 때의
Anthropic API(`api.anthropic.com`). 테스트는 이 단일 지점을 monkeypatch로 스텁하고
`requested_urls()`로 감시해 '허용된 목적지 외 연결 없음'을 검증한다 (v0.5 스펙 §3 항목7).

표준 라이브러리(`urllib.request`)만 사용한다 — 서드파티 HTTP 의존성을 두지 않는다.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit  # 순수 문자열 파싱 — 네트워크 호출 없음

from corpbrain.core.errors import CorpBrainError

#: 관문이 이번 프로세스에서 시도한 URL 기록 (요청 순서). 소켓을 열기 전에 append 하므로
#: 실패한 호출도 남는다. 테스트·진단용 관찰 훅이며 정책 판단에는 쓰지 않는다.
_REQUESTED_URLS: list[str] = []


class GatewayError(CorpBrainError):
    """관문을 통한 외부 호출 실패 — 연결·HTTP 상태·JSON 직렬화/파싱 오류를 감싼다.

    Attributes:
        url: 실패한 호출의 대상 URL.
        status: HTTP 상태코드. 응답을 받지 못한 실패(연결 거부·타임아웃·DNS·직렬화·파싱)는
            `None`이다. 호출자가 상태별로 다르게 대응(401은 선행 조건 실패, 429는 파일 스킵
            등)할 수 있도록 관문이 **계약의 일부로** 노출한다 — 원인 예외(`__cause__`)의
            비공개 구조를 들여다보지 않게 하기 위함이다.
    """

    def __init__(self, message: str, *, url: str, status: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status = status


class NetworkGuardError(GatewayError):
    """NetworkGuard가 목적지를 거부했다 — 소켓을 열기 전에 차단된다 (v0.5 스펙 §4.4).

    허용 호스트(allowlist) 불일치, HTTPS 강제 위반, 리다이렉트 추적 시도가 여기에 해당한다.
    """


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """리다이렉트를 추적하지 않고 즉시 실패시킨다 (v0.5 스펙 §4.4).

    3xx 응답을 따라가면 NetworkGuard가 승인한 목적지 밖으로 요청이 새어 나갈 수 있으므로,
    따라가는 대신 원래 3xx를 그대로 오류로 올린다. 표준 핸들러의 `redirect_request`를
    `None` 반환으로 무력화하면 `urlopen`이 `HTTPError`를 그대로 전파한다.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


#: 리다이렉트를 따라가지 않고 **프록시도 타지 않는** opener — 모든 요청이 이 opener로만 나간다.
#:
#: `build_opener()`의 기본 `ProxyHandler`는 `http_proxy`/`https_proxy` 환경변수와 Windows 레지스트리
#: 프록시 설정을 자동으로 읽어들인다. 그러면 NetworkGuard가 URL **문자열**을 통과시킨 뒤 소켓은
#: 전혀 다른 목적지로 열릴 수 있고, 특히 `urllib`는 `127.0.0.1`·`localhost`를 프록시에서 자동
#: 제외하지 않는다 — 선의로 설정된 사내 프록시 하나만으로 "기본 로컬·외부 통신 0" 불변식이
#: 조용히 깨지고, 마스킹되지 않은 로컬 요약 본문이 평문 HTTP로 사외로 나갈 수 있다.
#: 빈 `ProxyHandler({})`를 명시해 프록시 설정을 아예 무시한다.
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _NoRedirectHandler
)


def _guard_destination(
    url: str,
    *,
    allowed_hosts: Sequence[str] | None,
    require_https: bool,
) -> None:
    """소켓을 열기 전에 목적지를 검사한다 — NetworkGuard (v0.5 스펙 §4.4).

    `urlsplit`으로 스킴·호스트만 뽑아 **대소문자 무시 정확 일치**로 판정한다.
    서픽스·와일드카드 매칭은 쓰지 않는다(하드코딩 단일 호스트 원칙).

    Args:
        url: 검사할 대상 URL.
        allowed_hosts: 허용 호스트 목록. `None`이면 호스트를 제한하지 않는다.
        require_https: True면 스킴이 `https`가 아닐 때 거부한다.

    Raises:
        NetworkGuardError: 스킴·호스트가 허용 범위 밖일 때.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if require_https and scheme != "https":
        raise NetworkGuardError(
            f"이 목적지는 HTTPS만 허용됩니다: {url} (스킴 {scheme or '없음'})", url=url
        )
    if allowed_hosts is None:
        return
    hostname = (parts.hostname or "").lower()
    if hostname not in {host.lower() for host in allowed_hosts}:
        allowed = ", ".join(allowed_hosts) or "(없음)"
        raise NetworkGuardError(
            f"허용되지 않은 목적지입니다: {hostname or '(호스트 없음)'} — 허용: {allowed}",
            url=url,
        )


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
    headers: Mapping[str, str] | None = None,
    timeout: float = 60.0,
    allowed_hosts: Sequence[str] | None = None,
    require_https: bool = False,
) -> Any:
    """외부에 JSON 요청을 보내고 응답 JSON을 파싱해 반환한다 — 프로세스의 유일한 출구.

    Args:
        url: 대상 URL. 코어는 이 값을 주입받아 넘기며(하드코딩하지 않는다), 테스트는
            이 인자로 관문 통과 지점을 감시한다.
        method: HTTP 메서드.
        payload: 주어지면 JSON으로 직렬화해 본문으로 보낸다. `None`이면 본문 없는 요청.
        headers: 추가 요청 헤더(선택). 인증 헤더 등 provider 고유 헤더를 싣는 통로다
            (v0.5 스펙 §4.3 — 공식 SDK 없이 raw HTTP로 호출하기 위함). 기본 헤더
            (`Accept`·`Content-Type`)와 키가 겹치면 이 값이 이긴다.
        timeout: 소켓 타임아웃(초).
        allowed_hosts: NetworkGuard 허용 호스트 목록 (v0.5 스펙 §4.4). 주어지면 소켓을
            열기 전에 목적지 호스트를 대소문자 무시 정확 일치로 검사한다.
        require_https: True면 HTTPS 스킴만 허용한다 (클라우드 경로).

    Returns:
        응답 본문을 JSON 파싱한 값.

    Raises:
        NetworkGuardError: 목적지가 allowlist 밖이거나 HTTPS 강제를 위반.
        GatewayError: 연결 실패·타임아웃·HTTP 오류 상태·JSON 직렬화/파싱 실패.
    """
    # NetworkGuard: 목적지 판정은 소켓을 열기 **전에** 끝낸다 (v0.5 스펙 §4.4).
    # 거부된 요청은 `_REQUESTED_URLS`에 남기지 않는다 — 시도조차 하지 않았기 때문이다.
    _guard_destination(url, allowed_hosts=allowed_hosts, require_https=require_https)

    _REQUESTED_URLS.append(url)

    request_headers = {"Accept": "application/json"}
    body: bytes | None = None
    if payload is not None:
        try:
            body = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise GatewayError(
                f"요청 본문을 JSON으로 직렬화하지 못했습니다: {exc}", url=url
            ) from exc
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        # 리다이렉트를 따라가지 않는 opener로만 나간다 — 승인된 목적지 밖으로 새지 않게 한다.
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = _read_error_body(exc)
        message = f"외부 호출이 HTTP {exc.code}로 실패했습니다: {url}"
        if detail:
            message = f"{message} — {detail}"
        raise GatewayError(message, url=url, status=exc.code) from exc
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
