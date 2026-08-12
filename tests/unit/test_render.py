"""마크다운 렌더러 단위테스트 (FR-011 / 스펙 §4.4, §3 완료의 정의 2번)."""

from __future__ import annotations

import pytest

from corpbrain.core.models import SummaryResult
from corpbrain.core.render import FRONT_MATTER_KEYS, SECTION_HEADERS, render_markdown

SOURCE_PATH = "/Users/doctorf/inbox/보고서.docx"
GENERATED_AT = "2026-08-12T21:00:00+09:00"
MODEL = "qwen2.5:7b-instruct"
SOURCE_BYTES = 20480


@pytest.fixture
def summary() -> SummaryResult:
    return SummaryResult(
        title="2026 상반기 영업 보고",
        one_line_summary="상반기 매출이 전년 대비 12% 증가했다.",
        key_points=["매출 12% 증가", "신규 고객 34곳", "이탈률 2%p 감소"],
        summary="상반기 영업 실적을 요약한 문단이다.",
        tags=["영업", "실적", "2026"],
    )


def _render(summary: SummaryResult) -> str:
    return render_markdown(
        summary,
        source_path=SOURCE_PATH,
        model=MODEL,
        source_bytes=SOURCE_BYTES,
        generated_at=GENERATED_AT,
    )


def _front_matter(markdown: str) -> dict[str, str]:
    assert markdown.startswith("---\n")
    block = markdown.split("---\n", 2)[1]
    parsed: dict[str, str] = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def test_front_matter_contains_all_required_keys(summary: SummaryResult) -> None:
    parsed = _front_matter(_render(summary))

    assert set(FRONT_MATTER_KEYS) <= parsed.keys()
    assert parsed["source_path"] == SOURCE_PATH
    assert parsed["generated_at"] == GENERATED_AT
    assert parsed["model"] == MODEL
    assert parsed["source_bytes"] == str(SOURCE_BYTES)


def test_all_sections_render_in_spec_order(summary: SummaryResult) -> None:
    markdown = _render(summary)

    positions = [markdown.index(header) for header in SECTION_HEADERS]
    assert positions == sorted(positions)
    assert f"# {summary.title}" in markdown


def test_key_points_and_tags_are_rendered(summary: SummaryResult) -> None:
    markdown = _render(summary)

    for point in summary.key_points:
        assert f"- {point}" in markdown
    assert "영업, 실적, 2026" in markdown


def test_source_link_uses_absolute_file_url(summary: SummaryResult) -> None:
    markdown = _render(summary)

    assert f"[원본 파일 열기](file://{SOURCE_PATH})" in markdown


def test_empty_arrays_keep_section_headers() -> None:
    empty = SummaryResult(
        title="제목",
        one_line_summary="한 줄",
        key_points=[],
        summary="문단",
        tags=[],
    )

    markdown = _render(empty)

    for header in SECTION_HEADERS:
        assert header in markdown


def test_render_is_deterministic(summary: SummaryResult) -> None:
    assert _render(summary) == _render(summary)


def test_quotes_in_path_do_not_break_front_matter(summary: SummaryResult) -> None:
    markdown = render_markdown(
        summary,
        source_path='/tmp/say "hi".txt',
        model=MODEL,
        source_bytes=1,
        generated_at=GENERATED_AT,
    )

    assert 'source_path: "/tmp/say \\"hi\\".txt"' in markdown
