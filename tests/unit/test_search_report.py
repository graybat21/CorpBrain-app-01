"""build_search_lines 렌더 단위테스트 (v0.4 스펙 §3 항목6, 코드리뷰 finding: 빈 제목 폴백)."""

from __future__ import annotations

from corpbrain.core.models import SearchResult
from corpbrain.core.report import build_search_lines


def test_no_results_shows_placeholder_message() -> None:
    assert build_search_lines([]) == ["일치하는 문서가 없습니다."]


def test_results_show_rank_score_title_and_path() -> None:
    results = [
        SearchResult(doc_id="/docs/a.txt", score=0.823, metadata={"title": "휴가 규정", "source_path": "/docs/a.txt"}),
        SearchResult(doc_id="/docs/b.txt", score=0.611, metadata={"title": "출장비 규정", "source_path": "/docs/b.txt"}),
    ]

    lines = build_search_lines(results)

    assert lines[0] == "검색 결과 2건"
    assert "휴가 규정" in lines[1]
    assert "/docs/a.txt" in lines[1]


def test_missing_title_key_falls_back_to_placeholder() -> None:
    results = [SearchResult(doc_id="/docs/a.txt", score=0.5, metadata={"source_path": "/docs/a.txt"})]

    lines = build_search_lines(results)

    assert "(제목 없음)" in lines[1]


def test_empty_string_title_also_falls_back_to_placeholder() -> None:
    """metadata에 title 키는 있지만 빈 문자열인 경우(손상·수기 편집 위키 백필)도 대체 문구를 쓴다."""
    results = [SearchResult(doc_id="/docs/a.txt", score=0.5, metadata={"title": "", "source_path": "/docs/a.txt"})]

    lines = build_search_lines(results)

    assert "(제목 없음)" in lines[1]


def test_missing_source_path_falls_back_to_doc_id() -> None:
    results = [SearchResult(doc_id="/docs/a.txt", score=0.5, metadata={"title": "제목"})]

    lines = build_search_lines(results)

    assert "/docs/a.txt" in lines[1]


def test_empty_string_source_path_also_falls_back_to_doc_id() -> None:
    results = [
        SearchResult(doc_id="/docs/a.txt", score=0.5, metadata={"title": "제목", "source_path": ""})
    ]

    lines = build_search_lines(results)

    assert "/docs/a.txt" in lines[1]
