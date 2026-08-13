"""환경 진단 — Ollama 설치/구동/모델·GPU를 점검해 doctor 리포트를 조립한다 (v0.3 스펙 §4.3).

설치 여부는 로컬 `shutil.which`(PATH 조회, 소켓 아님)로 감지하고, 데몬 구동·모델 목록은 단일
관문을 경유하는 `ollama_client`가 제공한다. 이 모듈은 HTTP·소켓 라이브러리를 직접 import 하지
않으므로 '단일 외부호출 관문' 불변식과 충돌하지 않는다 (스펙 §4.5).

`doctor`는 fail-fast가 아니라 전 항목을 점검해 집계 리포트를 낸다 (v0.3 §4.2 — scan 프리플라이트와
대비되는 지점). 렌더(사람이 읽는 줄)와 종료 코드 매핑은 각각 report.py·CLI가 담당한다.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from corpbrain.core.config import (
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_MAX_TOTAL_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
)
from corpbrain.core.llm import ollama_client
from corpbrain.core.llm.ollama_client import OllamaNotAvailableError
from corpbrain.core.models import HardwareInfo
from corpbrain.core.plan import detect_hardware

__all__ = ["OLLAMA_BINARY", "DoctorReport", "diagnose"]

#: PATH에서 찾는 Ollama 실행 파일 이름.
OLLAMA_BINARY = "ollama"


@dataclass(frozen=True)
class DoctorReport:
    """`doctor`가 낸 환경 준비 상태 (순수 값). 렌더는 report.py가 담당한다 (v0.3 §4.3)."""

    #: PATH에 `ollama` 바이너리가 있는가 (`shutil.which`).
    installed: bool
    #: 데몬이 `/api/tags`에 정상 응답하는가.
    running: bool
    #: 점검 대상 모델 이름.
    model: str
    #: 대상 모델이 설치돼 있는가 (데몬 미구동이면 False).
    model_present: bool
    #: 데몬이 보고한 설치 모델 목록 (미구동이면 빈 목록).
    available_models: list[str]
    #: 감지 하드웨어 (GPU 없음은 경고일 뿐 준비 판정에 영향 없음).
    hardware: HardwareInfo
    #: 현재 게이트 임계값 (정보 표시).
    max_file_size: int
    max_total_tokens: int

    @property
    def ready(self) -> bool:
        """필수 조건(설치·구동·대상 모델)이 모두 충족됐는가. GPU 없음은 준비 판정과 무관."""
        return self.installed and self.running and self.model_present


def diagnose(
    *,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout: float = 5.0,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS,
) -> DoctorReport:
    """환경을 점검해 `DoctorReport`를 조립한다 (전 항목 점검, fail-fast 아님).

    설치 감지는 로컬 PATH 조회(`shutil.which`)뿐이고, 데몬·모델은 단일 관문을 경유한다.
    데몬 미구동이면 모델 목록을 알 수 없으므로 `running=False`·`model_present=False`로 둔다.
    """
    installed = shutil.which(OLLAMA_BINARY) is not None
    hardware = detect_hardware()

    running = False
    available: list[str] = []
    present = False
    try:
        available = ollama_client.list_models(ollama_url, timeout=timeout)
        running = True
        present = ollama_client.model_present(available, model)
    except OllamaNotAvailableError:
        running = False

    return DoctorReport(
        installed=installed,
        running=running,
        model=model,
        model_present=present,
        available_models=available,
        hardware=hardware,
        max_file_size=max_file_size,
        max_total_tokens=max_total_tokens,
    )
