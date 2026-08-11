"""코어 공개 진입점 — CLI 없이 함수 호출만으로 end-to-end 실행 (스펙 §4.5).

파이프라인 본체(스캔→추출→요약→렌더→출력)는 FR-015에서 채운다.
"""

from __future__ import annotations

from corpbrain.core.config import ScanConfig
from corpbrain.core.models import ScanResult


def run_scan(config: ScanConfig) -> ScanResult:
    """폴더를 스캔해 문서마다 위키 마크다운 1개를 생성하고 결과를 반환한다.

    Args:
        config: 실행 파라미터 (순수 값). 어댑터 타입에 의존하지 않는다.

    Returns:
        생성·스킵 목록을 담은 `ScanResult`. 개별 파일 실패는 스킵으로 담고 예외로 올리지 않는다.

    Raises:
        PreconditionError: 입력 폴더 없음/접근 불가, Ollama 미탐지 등 선행 조건 실패.
    """
    raise NotImplementedError("파이프라인 오케스트레이션은 FR-015에서 구현한다.")
