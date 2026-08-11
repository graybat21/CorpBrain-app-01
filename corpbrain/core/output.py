"""위키 마크다운 출력 배치 — `--out` 하위에 입력 폴더 구조를 미러링 (스펙 §4.4).

파일명 규칙(스펙 §4.4): 원본 파일명에 확장자를 **유지한 채** `.md`를 덧붙인다.
`report.docx` → `report.docx.md`. 확장자를 대체하지 않으므로 같은 폴더의 `a.txt`와 `a.md`가
동일한 출력으로 충돌하지 않는다("입력 1개당 위키 1개").
"""

from __future__ import annotations

from pathlib import Path

WIKI_SUFFIX = ".md"


def output_path_for(source_path: Path, scan_root: Path, out_dir: Path) -> Path:
    """원문 경로를 `out_dir` 아래 미러링된 위키 경로로 변환한다.

    Raises:
        ValueError: `source_path`가 `scan_root` 아래에 있지 않은 경우.
    """
    relative = source_path.resolve().relative_to(scan_root.resolve())
    return out_dir / relative.parent / f"{source_path.name}{WIKI_SUFFIX}"


def write_wiki(markdown: str, out_path: Path) -> None:
    """마크다운을 UTF-8로 기록한다. 필요한 하위 디렉터리는 만들어 준다."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
