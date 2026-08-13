"""Ollama 로컬 HTTP 클라이언트 — 탐지·모델 점검 (스펙 §4.3, §5 · v0.3 §4.3).

구동 중인 인스턴스를 **탐지만** 한다. 설치·프로비저닝·모델 pull은 어떤 경우에도 시도하지
않으며(비목표), 미탐지·대상 모델 부재는 개별 파일의 부분 실패가 아니라 선행 조건 실패이므로
어댑터가 비-0 종료로 매핑한다 (스펙 §3-5, §5).

v0.3: `/api/tags` 응답의 모델 목록을 파싱해 **대상 모델 존재**를 확인한다. 부재 시 사용자에게
`ollama pull <model>`을 **안내**할 뿐 직접 실행하지 않는다 — 이 모듈은 `shutil`/`subprocess`/`os`
를 import 하지 않는다(설치 감지는 `core/environment.py`가 담당).

네트워크는 `corpbrain.core.gateway.request_json()`만 경유한다 — 이 모듈은 HTTP
라이브러리를 직접 import 하지 않는다 (스펙 §4.5 단일 외부호출 관문).
"""

from __future__ import annotations

from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크 호출 없음

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_OLLAMA_URL
from corpbrain.core.errors import PreconditionError

#: 헬스체크 겸 모델 목록 엔드포인트. 구동 중인 Ollama는 설치된 모델 목록을 JSON 객체로 돌려준다.
HEALTH_PATH = "/api/tags"

__all__ = [
    "HEALTH_PATH",
    "ModelNotAvailableError",
    "OllamaNotAvailableError",
    "available_model_names",
    "detect",
    "list_models",
    "model_present",
]


class OllamaNotAvailableError(PreconditionError):
    """Ollama 미탐지·미구동 — 선행 조건 실패이므로 상위 계층이 비-0 종료로 매핑한다."""


class ModelNotAvailableError(PreconditionError):
    """대상 모델이 설치돼 있지 않음 — 선행 조건 실패(비-0 종료).

    해결책은 `ollama pull <model>`이며, 이 모듈은 안내만 하고 직접 실행하지 않는다 (v0.3 §4.3).
    """


def _health_url(ollama_url: str) -> str:
    """헬스체크 대상 URL을 조립한다 (문자열 처리만 — 네트워크 접촉 없음).

    베이스에 경로가 붙어 있어도(리버스 프록시 뒤 등) 그 경로를 보존하도록 항상 슬래시로
    끝나는 베이스에 상대 경로를 결합한다.
    """
    base = ollama_url if ollama_url.endswith("/") else f"{ollama_url}/"
    return urljoin(base, HEALTH_PATH.lstrip("/"))


def _normalize_model(name: str) -> str:
    """모델 이름을 태그까지 정규화한다 — 태그가 없으면 Ollama 관례대로 `:latest`를 붙인다 (v0.3 §4.3)."""
    name = name.strip()
    return name if ":" in name else f"{name}:latest"


def available_model_names(response: object) -> list[str]:
    """`/api/tags` 응답에서 모델 이름 목록을 안전하게 뽑는다 (비정상 형태는 빈 목록)."""
    if not isinstance(response, dict):
        return []
    models = response.get("models")
    if not isinstance(models, list):
        return []
    return [
        item["name"]
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


def model_present(available: list[str], target: str) -> bool:
    """대상 모델이 목록에 있는지 태그 정규화 후 정확 일치로 판정한다 (대소문자 구분, v0.3 §4.3).

    무태그 이름은 `:latest`로 보정해 비교한다(`llama3` == `llama3:latest`). 접두·부분 매칭은
    쓰지 않아 `qwen2.5:7b`가 `qwen2.5:7b-instruct`에 오매치되지 않는다.
    """
    want = _normalize_model(target)
    return any(_normalize_model(name) == want for name in available)


def list_models(ollama_url: str = DEFAULT_OLLAMA_URL, *, timeout: float = 5.0) -> list[str]:
    """구동 중인 로컬 Ollama의 설치된 모델 이름 목록을 돌려준다 — 미구동·비정상은 예외.

    네트워크는 단일 관문(`gateway.request_json`)만 경유한다. 응답이 JSON 객체가 아니면
    Ollama가 아니라고 보고 미탐지로 취급한다.

    Raises:
        OllamaNotAvailableError: 연결 거부·타임아웃·HTTP 오류·JSON 파싱 실패, 또는 비-객체 응답.
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
    return available_model_names(response)


def detect(
    ollama_url: str = DEFAULT_OLLAMA_URL,
    *,
    model: str | None = None,
    timeout: float = 5.0,
) -> None:
    """구동 중인 로컬 Ollama를 탐지한다 — 정상이면 반환, 아니면 예외.

    v0.3: `model`을 주면 데몬 구동에 더해 그 모델의 설치 여부까지 확인한다(부재 시 선행 조건 실패).

    Args:
        ollama_url: `--ollama-url` 값 (기본 localhost). 이 대상 외에는 접속하지 않는다.
        model: 확인할 대상 모델. `None`이면 데몬 구동 여부만 본다(v0.2 동작 보존).
        timeout: 헬스체크 소켓 타임아웃(초). 미구동 대상에 오래 매달리지 않기 위한 값이다.

    Raises:
        OllamaNotAvailableError: 연결 거부·타임아웃·HTTP 오류 상태·JSON 파싱 실패
            (`GatewayError` 전반), 또는 응답이 JSON 객체가 아닌 비정상 형태.
            어느 경우에도 설치·프로비저닝을 시도하지 않는다.
        ModelNotAvailableError: 데몬은 살아 있으나 대상 모델이 설치돼 있지 않음.
    """
    available = list_models(ollama_url, timeout=timeout)
    if model is not None and not model_present(available, model):
        raise ModelNotAvailableError(
            f"대상 모델을 찾지 못했습니다: {model} — 먼저 `ollama pull {model}` 를 실행하세요."
        )
