"""CorpBrain 코어 라이브러리 — 재사용 가능한 비즈니스 로직 (스펙 §4.5).

CLI(`corpbrain.cli`)와 후속 UI 어댑터는 모두 이 패키지의 공개 API만 호출한다.
코어는 어댑터 타입(argparse Namespace 등)에 의존하지 않는다.

모듈 배치 (후속 FR이 채우는 자리):

- `config`     실행 파라미터 `ScanConfig`와 스펙 기본값       (FR-002)
- `models`     결과 데이터 구조 `ScanResult` 등              (FR-002)
- `errors`     예외 계층                                    (FR-002)
- `pipeline`   공개 진입점 `run_scan`                        (FR-002 골격 / FR-015 구현)
- `gateway`    유일한 외부 네트워크 호출 관문                 (FR-003)
- `scanner`    재귀 스캔·포맷 필터·가드레일                   (FR-004, FR-005)
- `extract`    포맷별 텍스트 추출과 길이 제한                 (FR-006, FR-007, FR-008)
- `llm.ollama_client`  Ollama 탐지 (관문 경유)                (FR-009)
- `llm.summarize`      요약 프롬프트와 고정 필드 JSON 파싱     (FR-010)
- `render`     JSON→마크다운 결정적 렌더                      (FR-011)
- `output`     출력 경로 미러링·기록                           (FR-012)
- `rerun`      증분 재실행 정책(mtime 비교·--force)            (FR-013)
- `report`     종료 리포트 구성                               (FR-016)
"""

from __future__ import annotations

from corpbrain.core.config import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_FILES,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_OUT_DIR,
    MAX_PATH_LENGTH,
    SUPPORTED_EXTENSIONS,
    ScanConfig,
)
from corpbrain.core.errors import CorpBrainError, PreconditionError
from corpbrain.core.models import (
    GeneratedWiki,
    HardwareInfo,
    PlanEntry,
    ScanPlan,
    ScanResult,
    SkippedFile,
    SkipReason,
    SummaryResult,
)
from corpbrain.core.pipeline import run_scan

__all__ = [
    "DEFAULT_MAX_CHARS",
    "DEFAULT_MAX_FILES",
    "DEFAULT_MODEL",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_OUT_DIR",
    "MAX_PATH_LENGTH",
    "SUPPORTED_EXTENSIONS",
    "CorpBrainError",
    "GeneratedWiki",
    "HardwareInfo",
    "PlanEntry",
    "PreconditionError",
    "ScanConfig",
    "ScanPlan",
    "ScanResult",
    "SkipReason",
    "SkippedFile",
    "SummaryResult",
    "run_scan",
]
