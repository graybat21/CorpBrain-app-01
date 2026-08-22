"""CorpBrain — 100% 로컬 구동형 AI 지식 관리 (MVP 첫 슬라이스).

비즈니스 로직은 재사용 가능한 코어(`corpbrain.core`)에 두고, CLI(`corpbrain.cli`)는
코어를 호출하는 얇은 어댑터로 유지한다 (스펙 §4.5).
"""

__all__ = ["__version__"]

#: 설치가 깨졌을 때만 나가는 값 — 실제 버전으로 오인되지 않도록 명백히 비정상인 형태로 둔다.
_UNKNOWN_VERSION = "0.0.0+unknown"


def __getattr__(name: str) -> str:
    """`__version__`을 처음 읽을 때만 해석한다 (PEP 562).

    버전은 배포 메타데이터(`pyproject.toml`의 `version`)를 단일 출처로 삼는다 — 상수를 손으로
    적어 두면 범프 때 조용히 어긋난다(실제로 `0.1.0`에 머물렀다). 다만 `importlib.metadata`
    import만으로 CLI 기동이 20~50ms 늘어나는데, 이 값을 읽는 코드는 아직 없다. 그래서 모듈
    최상단이 아니라 이 접근자 안에서 import 하고, 결과는 모듈 전역에 캐시한다.
    """
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _version

    try:
        resolved = _version("corpbrain")
    except PackageNotFoundError:
        resolved = _UNKNOWN_VERSION

    globals()["__version__"] = resolved  # 다음 접근부터는 __getattr__를 타지 않는다.
    return resolved
