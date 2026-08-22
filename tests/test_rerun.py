"""재실행 정책 단위테스트 (FR-013 / 스펙 §4.2)."""

from __future__ import annotations

import os
from pathlib import Path

from corpbrain.core.models import SummaryResult
from corpbrain.core.render import render_markdown
from corpbrain.core.rerun import read_source_path, should_regenerate


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


def test_read_source_path_round_trips_a_quoted_filename(tmp_path: Path) -> None:
    """파일명에 큰따옴표가 있어도 `doc_id`를 그대로 되찾는다 (v0.6 §4.1).

    `[^"]*`로 두면 이스케이프된 `\\"`에서 값이 잘려 `None`이 되고, 그 위키가 그래프에서
    조용히 빠진 뒤 고아 정리가 재료까지 지운다(엔티티 소실).
    """
    for source in ('/work/say "hi".txt', "/work/back\\slash.txt", "/work/평범.txt"):
        wiki = tmp_path / "w.md"
        wiki.write_text(
            render_markdown(
                SummaryResult(
                    title="T",
                    one_line_summary="o",
                    key_points=["a"],
                    summary="s",
                    tags=["t"],
                ),
                source_path=source,
                model="m",
                source_bytes=1,
                generated_at="2026-08-23T00:00:00",
            ),
            encoding="utf-8",
        )

        assert read_source_path(wiki) == source


def test_read_source_path_returns_empty_when_absent(tmp_path: Path) -> None:
    wiki = tmp_path / "w.md"
    wiki.write_text("# 제목만 있는 파일\n", encoding="utf-8")

    assert read_source_path(wiki) == ""
