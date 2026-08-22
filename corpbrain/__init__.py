"""CorpBrain — 100% 로컬 구동형 AI 지식 관리 (MVP 첫 슬라이스).

비즈니스 로직은 재사용 가능한 코어(`corpbrain.core`)에 두고, CLI(`corpbrain.cli`)는
코어를 호출하는 얇은 어댑터로 유지한다 (스펙 §4.5).
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    #: 배포 메타데이터(`pyproject.toml`의 `version`)를 단일 출처로 삼는다.
    #: 상수를 손으로 적어 두면 버전 범프 때 조용히 어긋난다(실제로 0.1.0에 머물렀다).
    __version__ = _version("corpbrain")
except PackageNotFoundError:  # pragma: no cover - 설치 없이 소스 트리에서 import한 경우
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
