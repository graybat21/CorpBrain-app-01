"""위키 마크다운 출력 배치 — `--out` 하위에 입력 폴더 구조를 미러링 (스펙 §4.4).

파일명 규칙(스펙 §4.4): 원본 파일명에 확장자를 **유지한 채** `.md`를 덧붙인다.
`report.docx` → `report.docx.md`. 확장자를 대체하지 않으므로 같은 폴더의 `a.txt`와 `a.md`가
동일한 출력으로 충돌하지 않는다("입력 1개당 위키 1개").
"""

from __future__ import annotations

from pathlib import Path

from corpbrain.core.render import replace_related_block

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


def inject_related_block(out_path: Path, block: str) -> bool:
    """위키의 「관련 문서」 마커 블록을 교체한다. **실제로 기록했으면** True (v0.6 §4.5).

    마커 교체를 위해 어차피 파일 전체를 읽으므로, 교체 결과를 기존 내용과 비교해 **다를 때만**
    쓴다. 재실행 시 관련 문서가 바뀌지 않은 대다수 위키는 mtime이 그대로 유지되어, 동기화
    도구가 매 실행마다 위키 전체를 변경으로 보고 다시 전송하는 일이 없다.

    Raises:
        OSError: 읽기·쓰기 실패(권한 거부·잠금 등). 호출자가 파일별 베스트 에포트로 다룬다.
    """
    original = out_path.read_text(encoding="utf-8")
    updated = replace_related_block(original, block)
    if updated == original:
        return False
    out_path.write_text(updated, encoding="utf-8")
    return True
