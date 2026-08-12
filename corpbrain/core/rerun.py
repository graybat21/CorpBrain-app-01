"""증분 재실행 정책 — 원문 mtime이 기존 위키보다 최신일 때만 재생성 (스펙 §4.2).

요약·렌더 이전 단계에서 평가해 변경 없는 파일에 대한 불필요한 LLM 호출을 막는다.
재생성하지 않는 파일은 실패가 아니라 `SkipReason.UP_TO_DATE`로 보고된다 (FR-015·FR-016).
"""

from __future__ import annotations

from pathlib import Path


def should_regenerate(source_path: Path, out_path: Path, force: bool = False) -> bool:
    """원문을 다시 요약·렌더해야 하는지 판단한다.

    Args:
        source_path: 원문 파일 경로.
        out_path: FR-012 미러링 규칙으로 산정한 위키 경로.
        force: `--force` — mtime과 무관하게 강제 재생성.

    Returns:
        재생성해야 하면 True, 최신 상태라 건너뛰어도 되면 False.
    """
    if force:
        return True
    if not out_path.exists():
        return True
    return source_path.stat().st_mtime > out_path.stat().st_mtime
