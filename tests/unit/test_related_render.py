"""「관련 문서」 마커 블록 렌더와 교체 (v0.6 스펙 §4.5)."""

from __future__ import annotations

from corpbrain.core.embedding_text import parse_wiki_markdown
from corpbrain.core.models import ReferenceDirection, RelatedDocument, SummaryResult
from corpbrain.core.render import (
    RELATED_EMPTY,
    RELATED_MARKER_END,
    RELATED_MARKER_START,
    SECTION_HEADERS,
    render_markdown,
    render_related_block,
    replace_related_block,
)

PATHS = {
    "/w/인사/온보딩.md": "인사/온보딩.md.md",
    "/w/개발/설계.md": "개발/설계.md.md",
}


def _wiki(summary_text: str = "평범한 요약") -> str:
    return render_markdown(
        SummaryResult(
            title="문서 제목",
            one_line_summary="한 문장",
            key_points=["포인트"],
            summary=summary_text,
            tags=["아키텍처", "코어"],
        ),
        source_path="/w/개발/설계.md",
        model="qwen2.5:7b-instruct",
        source_bytes=100,
        generated_at="2026-08-23T10:00:00",
    )


# --- 렌더러가 빈 블록을 소유한다 -------------------------------------------------


def test_related_is_a_required_section_header() -> None:
    assert SECTION_HEADERS[-1] == "## 관련 문서"


def test_fresh_wiki_always_has_the_marker_block() -> None:
    """갓 생성된 위키에는 마커가 항상 있어 패스3이 '없으면 추가' 경로를 탈 일이 없다."""
    markdown = _wiki()

    assert RELATED_MARKER_START in markdown
    assert RELATED_MARKER_END in markdown
    assert RELATED_EMPTY in markdown


def test_all_required_sections_appear_in_order() -> None:
    markdown = _wiki()
    positions = [markdown.index(header) for header in SECTION_HEADERS]

    assert positions == sorted(positions)


# --- 근거 문구 ------------------------------------------------------------------


def test_evidence_phrases_cover_similarity_reference_tags_entities() -> None:
    block = render_related_block(
        [
            RelatedDocument(
                doc_id="/w/인사/온보딩.md",
                title="온보딩 가이드",
                similarity=0.8123,
                shared_tags=["인사"],
                shared_entities=["인사팀"],
                reference=ReferenceDirection.INCOMING,
            )
        ],
        relative_to="개발/설계.md.md",
        relative_paths=PATHS,
    )

    assert "유사도 0.81" in block
    assert "이 문서를 참조함" in block
    assert "공유 태그 `인사`" in block
    assert "공유 엔티티 `인사팀`" in block


def test_reference_direction_phrases() -> None:
    def phrase(direction: ReferenceDirection) -> str:
        return render_related_block(
            [RelatedDocument(doc_id="/w/인사/온보딩.md", title="T", reference=direction)],
            relative_to="",
            relative_paths=PATHS,
        )

    assert "이 문서가 참조함" in phrase(ReferenceDirection.OUTGOING)
    assert "이 문서를 참조함" in phrase(ReferenceDirection.INCOMING)
    assert "서로 참조함" in phrase(ReferenceDirection.MUTUAL)


def test_isolated_document_renders_the_empty_marker() -> None:
    block = render_related_block([], relative_to="a.txt.md")

    assert RELATED_EMPTY in block
    assert block.startswith(RELATED_MARKER_START)
    assert block.endswith(RELATED_MARKER_END)


# --- 링크 경로 ------------------------------------------------------------------


def test_link_is_relative_to_the_containing_wiki_file() -> None:
    """스펙 §4.5가 링크에 요구한 것은 '파일 탐색기·에디터에서 그대로 동작'이다.

    `--out` 루트 기준 문자열을 그대로 쓰면 하위 폴더 문서의 링크가 자기 폴더 아래를
    가리켜 깨진다.
    """
    block = render_related_block(
        [RelatedDocument(doc_id="/w/인사/온보딩.md", title="온보딩")],
        relative_to="개발/설계.md.md",
        relative_paths=PATHS,
    )

    assert "(../인사/온보딩.md.md)" in block


def test_link_of_top_level_document_equals_out_relative_path() -> None:
    block = render_related_block(
        [RelatedDocument(doc_id="/w/인사/온보딩.md", title="온보딩")],
        relative_to="메모.txt.md",
        relative_paths=PATHS,
    )

    assert "(인사/온보딩.md.md)" in block


# --- 교체 ----------------------------------------------------------------------


def test_replace_swaps_only_between_markers() -> None:
    original = _wiki()
    filled = render_related_block(
        [RelatedDocument(doc_id="/w/인사/온보딩.md", title="온보딩", similarity=0.9)],
        relative_to="개발/설계.md.md",
        relative_paths=PATHS,
    )

    updated = replace_related_block(original, filled)

    assert "유사도 0.90" in updated
    assert RELATED_EMPTY not in updated
    assert "## 태그·키워드" in updated
    assert "[원본 파일 열기]" in updated


def test_replace_appends_when_markers_are_absent() -> None:
    """v0.5 이하 산출물에는 마커가 없다 — 탐색하지 않고 끝에 덧붙인다."""
    legacy = "---\nsource_path: \"/w/a.txt\"\n---\n\n# 제목\n\n## 요약\n본문\n"
    block = render_related_block([], relative_to="a.txt.md")

    updated = replace_related_block(legacy, block)

    assert updated.startswith(legacy)
    assert updated.rstrip().endswith(RELATED_MARKER_END)


def test_summary_containing_the_heading_string_is_not_truncated() -> None:
    """헤딩 탐색 방식이었다면 뒤따르는 섹션이 조용히 잘려 나갔을 문서다."""
    original = _wiki("v0.6부터는 「## 관련 문서」 섹션이 추가되어 문서 간 연결을 표현한다.")
    block = render_related_block([], relative_to="개발/설계.md.md")

    updated = replace_related_block(original, block)

    assert "## 태그·키워드" in updated
    assert "아키텍처, 코어" in updated
    assert "[원본 파일 열기]" in updated
    assert updated.count(RELATED_MARKER_START) == 1


# --- 파서가 알되 임베딩에서는 뺀다 ------------------------------------------------


def test_related_block_never_reaches_the_embedding_text() -> None:
    """유사도 → 관련 문서 → 임베딩 → 유사도 피드백 루프를 구조적으로 막는다 (§4.4)."""
    filled = render_related_block(
        [RelatedDocument(doc_id="/w/인사/온보딩.md", title="온보딩 가이드", similarity=0.9)],
        relative_to="개발/설계.md.md",
        relative_paths=PATHS,
    )
    markdown = replace_related_block(_wiki(), filled)

    _title, text, _tags = parse_wiki_markdown(markdown)

    assert "온보딩 가이드" not in text
    assert "관련 문서" not in text
    assert "corpbrain:related" not in text


def test_parser_restores_tags_for_the_material_fallback() -> None:
    """`doc_facts`에 행이 없는 기존 위키에서 태그를 되살린다 (§4.4)."""
    title, _text, tags = parse_wiki_markdown(_wiki())

    assert title == "문서 제목"
    assert tags == ["아키텍처", "코어"]
