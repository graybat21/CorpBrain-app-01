"""출력 배치 단위테스트 (FR-012 / 스펙 §4.4 파일명 규칙, §3 완료의 정의 1번)."""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain.core.output import output_path_for, write_wiki


def test_subfolder_structure_is_mirrored(tmp_path: Path) -> None:
    root = tmp_path / "inbox"
    (root / "sub").mkdir(parents=True)
    source = root / "sub" / "a.txt"
    source.write_text("본문", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    assert output_path_for(source, root, out_dir) == out_dir / "sub" / "a.txt.md"


def test_original_extension_is_kept_before_md(tmp_path: Path) -> None:
    root = tmp_path / "inbox"
    root.mkdir()
    source = root / "report.docx"
    source.write_text("x", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    assert output_path_for(source, root, out_dir) == out_dir / "report.docx.md"


def test_same_stem_different_extensions_do_not_collide(tmp_path: Path) -> None:
    """`a.txt`와 `a.md`가 한 폴더에 있어도 출력이 겹치지 않는다 (입력 1개당 위키 1개)."""
    root = tmp_path / "inbox"
    root.mkdir()
    txt = root / "a.txt"
    md = root / "a.md"
    txt.write_text("t", encoding="utf-8")
    md.write_text("m", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    assert output_path_for(txt, root, out_dir) != output_path_for(md, root, out_dir)
    assert output_path_for(txt, root, out_dir).name == "a.txt.md"
    assert output_path_for(md, root, out_dir).name == "a.md.md"


def test_relative_root_is_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "inbox"
    (root / "sub").mkdir(parents=True)
    source = (root / "sub" / "b.md").resolve()
    source.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert output_path_for(source, Path("inbox"), Path("wiki")) == Path("wiki/sub/b.md.md")


def test_source_outside_scan_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "inbox"
    root.mkdir()
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        output_path_for(outside, root, tmp_path / "wiki")


def test_write_wiki_creates_missing_directories(tmp_path: Path) -> None:
    out_path = tmp_path / "wiki" / "sub" / "deep" / "a.txt.md"

    write_wiki("# 제목\n내용", out_path)

    assert out_path.read_text(encoding="utf-8") == "# 제목\n내용"


def test_write_wiki_overwrites_existing_file(tmp_path: Path) -> None:
    out_path = tmp_path / "wiki" / "a.txt.md"
    write_wiki("이전", out_path)

    write_wiki("이후", out_path)

    assert out_path.read_text(encoding="utf-8") == "이후"
