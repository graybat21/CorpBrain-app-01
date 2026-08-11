"""재실행 정책 단위테스트 (FR-013 / 스펙 §4.2)."""

from __future__ import annotations

import os
from pathlib import Path

from corpbrain.core.rerun import should_regenerate


def _make_pair(tmp_path: Path, *, source_mtime: float, wiki_mtime: float | None) -> tuple[Path, Path]:
    source = tmp_path / "a.txt"
    source.write_text("본문", encoding="utf-8")
    os.utime(source, (source_mtime, source_mtime))

    out_path = tmp_path / "wiki" / "a.txt.md"
    if wiki_mtime is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("# 위키", encoding="utf-8")
        os.utime(out_path, (wiki_mtime, wiki_mtime))
    return source, out_path


def test_missing_wiki_is_generated(tmp_path: Path) -> None:
    source, out_path = _make_pair(tmp_path, source_mtime=1000, wiki_mtime=None)

    assert should_regenerate(source, out_path) is True


def test_newer_source_is_regenerated(tmp_path: Path) -> None:
    source, out_path = _make_pair(tmp_path, source_mtime=2000, wiki_mtime=1000)

    assert should_regenerate(source, out_path) is True


def test_older_source_is_skipped(tmp_path: Path) -> None:
    source, out_path = _make_pair(tmp_path, source_mtime=1000, wiki_mtime=2000)

    assert should_regenerate(source, out_path) is False


def test_equal_mtime_is_skipped(tmp_path: Path) -> None:
    """'최신일 때만' 재생성 — 같은 시각은 최신이 아니다."""
    source, out_path = _make_pair(tmp_path, source_mtime=1500, wiki_mtime=1500)

    assert should_regenerate(source, out_path) is False


def test_force_regenerates_regardless_of_mtime(tmp_path: Path) -> None:
    source, out_path = _make_pair(tmp_path, source_mtime=1000, wiki_mtime=2000)

    assert should_regenerate(source, out_path, force=True) is True


def test_force_with_missing_wiki(tmp_path: Path) -> None:
    source, out_path = _make_pair(tmp_path, source_mtime=1000, wiki_mtime=None)

    assert should_regenerate(source, out_path, force=True) is True
