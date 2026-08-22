"""패키지 버전이 배포 메타데이터와 어긋나지 않는지 고정한다.

`corpbrain/__init__.py`의 `__version__`은 v0.1 이후 손으로 갱신되지 않아 `pyproject.toml`이
0.5.0일 때까지 `0.1.0`에 머물렀다. 지금은 `importlib.metadata`에서 읽으므로 구조적으로
어긋날 수 없지만, 누가 상수를 되돌리면 이 테스트가 잡는다.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import corpbrain

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _declared_version() -> str:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def test_package_version_matches_pyproject() -> None:
    declared = _declared_version()
    assert corpbrain.__version__ == declared, (
        f"패키지 버전 {corpbrain.__version__!r} != pyproject {declared!r} — "
        "버전을 범프한 뒤 재설치하지 않았다면 `uv sync`로 메타데이터를 갱신한다."
    )


def test_package_version_is_resolved() -> None:
    """설치가 깨졌을 때의 폴백 값이 그대로 새어 나가지 않는지 확인한다."""
    assert corpbrain.__version__ != corpbrain._UNKNOWN_VERSION, (
        "배포 메타데이터를 찾지 못했다 — 개발 환경에 패키지가 설치되지 않았다. "
        "`uv sync` 후 `uv run pytest`로 실행한다."
    )
