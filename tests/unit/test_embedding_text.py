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


def test_parse_wiki_markdown_excludes_link_and_markdown_syntax() -> None:
    """백필 경로가 '## 원문' 파일 링크나 헤더·불릿 기호 같은 마크다운 잡음을 담지 않는다."""
    summary = SummaryResult(
        title="가이드", one_line_summary="요약", key_points=["포인트A"], summary="본문", tags=["태그A"]
    )
    markdown = render_markdown(
        summary, source_path="/abs/guide.md", model="m",
        source_bytes=10, generated_at="2026-01-01T00:00:00+09:00",
    )

    _title, body = parse_wiki_markdown(markdown)

    assert "file://" not in body
    assert "## " not in body
    assert "- 포인트A" not in body and "포인트A" in body  # 불릿 기호는 빠지고 내용만 남는다


def test_backfilled_text_matches_fresh_text_shape() -> None:
    """백필된 문서와 신선하게 생성된 문서가 같은 요약에서 같은 임베딩 텍스트를 만든다(항목9 회귀 방지)."""
    summary = SummaryResult(
        title="휴가 규정",
        one_line_summary="연차는 15일이다.",
        key_points=["연차 15일", "이월 불가"],
        summary="상세 규정 문단.",
        tags=["인사", "휴가"],
    )
    fresh = summary_embedding_text(summary)

    markdown = render_markdown(
        summary, source_path="/abs/vacation.txt", model="m",
        source_bytes=10, generated_at="2026-01-01T00:00:00+09:00",
    )
    _title, backfilled = parse_wiki_markdown(markdown)

    assert fresh == backfilled
