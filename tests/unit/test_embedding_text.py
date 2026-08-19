"""임베딩 입력 텍스트 조립 단위테스트 (v0.4 스펙 §4.3)."""

from __future__ import annotations

from corpbrain.core.embedding_text import parse_wiki_markdown, summary_embedding_text
from corpbrain.core.models import SummaryResult
from corpbrain.core.render import render_markdown


def test_summary_embedding_text_joins_fields_skipping_empty() -> None:
    summary = SummaryResult(
        title="제목",
        one_line_summary="한 줄 요약",
        key_points=["포인트1", "포인트2"],
        summary="문단 요약",
        tags=["태그1", "태그2"],
    )

    text = summary_embedding_text(summary)

    assert "제목" in text
    assert "한 줄 요약" in text
    assert "포인트1" in text
    assert "문단 요약" in text
    assert "태그1" in text


def test_summary_embedding_text_omits_empty_tags() -> None:
    summary = SummaryResult(
        title="제목", one_line_summary="요약", key_points=["p"], summary="s", tags=[]
    )
    text = summary_embedding_text(summary)
    assert text.count("\n") == 3  # title, one_line, key_point, summary — tags 없음


def test_parse_wiki_markdown_strips_front_matter_and_finds_title() -> None:
    summary = SummaryResult(
        title="분기 실적 보고",
        one_line_summary="매출이 늘었다.",
        key_points=["a", "b", "c"],
        summary="상세 요약 문단.",
        tags=["실적"],
    )
    markdown = render_markdown(
        summary,
        source_path="/abs/report.docx",
        model="qwen2.5:7b-instruct",
        source_bytes=1234,
        generated_at="2026-01-01T00:00:00+09:00",
    )

    title, body = parse_wiki_markdown(markdown)

    assert title == "분기 실적 보고"
    assert "source_path" not in body  # front-matter 제거됨
    assert "매출이 늘었다." in body
    assert "상세 요약 문단." in body
