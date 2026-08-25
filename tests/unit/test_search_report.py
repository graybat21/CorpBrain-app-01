"""build_search_lines 렌더 단위테스트 (v0.4 스펙 §3 항목6, 코드리뷰 finding: 빈 제목 폴백)."""

from __future__ import annotations

from corpbrain.core.models import GraphExpansion, ReferenceDirection, SearchResult
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


# --- v0.7: 확산 근거 줄 (스펙 §4.6) --------------------------------------------
#
# 정확 문자열은 이 파일이 단언한다 — `tests/test_cli_search.py`는 종료 코드와 배선만 본다
# (§3 항목12, v0.6 §3 출력 검증 관용구 계승).


def _expanded(
    doc_id: str,
    score: float,
    title: str,
    expansion: GraphExpansion,
) -> SearchResult:
    return SearchResult(
        doc_id=doc_id,
        score=score,
        metadata={"title": title, "source_path": doc_id},
        expansion=expansion,
    )


def test_seed_lines_have_no_evidence_line() -> None:
    """시드는 코사인 상위라 이유가 자명하다 — 근거 줄을 붙이지 않는다 (§4.5·§4.6)."""
    results = [
        SearchResult(
            doc_id="/docs/온보딩.md",
            score=0.710,
            metadata={"title": "온보딩", "source_path": "/docs/온보딩.md"},
        )
    ]

    assert build_search_lines(results) == [
        "검색 결과 1건",
        "  1. [0.710] 온보딩 — /docs/온보딩.md",
    ]


def test_expansion_line_matches_the_spec_example() -> None:
    """스펙 §4.6 예시 그대로 — 코사인 · 시드 · 공유 태그 · 공유 엔티티 · 참조 순서다."""
    results = [
        SearchResult(
            doc_id="/docs/인사/온보딩.md",
            score=0.710,
            metadata={"title": "온보딩", "source_path": "/docs/인사/온보딩.md"},
        ),
        _expanded(
            "/docs/인사/채용계획.docx",
            0.568,
            "채용계획",
            GraphExpansion(
                seed_doc_id="/docs/인사/온보딩.md",
                seed_title="온보딩",
                seed_score=0.710,
                cosine=0.380,
                shared_tags=["인사"],
                shared_entities=["인사팀"],
                reference=ReferenceDirection.MUTUAL,
            ),
        ),
    ]

    assert build_search_lines(results) == [
        "검색 결과 2건",
        "  1. [0.710] 온보딩 — /docs/인사/온보딩.md",
        "  2. [0.568] 채용계획 — /docs/인사/채용계획.docx",
        "       └ 코사인 0.380 · 시드 «온보딩» · 공유 태그 `인사` · 공유 엔티티 `인사팀` · 서로 참조함",
    ]


def test_cosine_item_is_omitted_when_the_document_has_no_vector() -> None:
    """벡터가 없어 `cosine`이 `None`이면 「코사인 …」 항목을 생략한다 (§4.6·§5)."""
    results = [
        _expanded(
            "/docs/a.md",
            0.497,
            "메모",
            GraphExpansion(
                seed_doc_id="/docs/seed.md",
                seed_title="온보딩",
                seed_score=0.710,
                cosine=None,
                shared_tags=["인사"],
                shared_entities=[],
                reference=ReferenceDirection.NONE,
            ),
        )
    ]

    assert build_search_lines(results)[2] == "       └ 시드 «온보딩» · 공유 태그 `인사`"


def test_cosine_item_is_omitted_when_it_equals_the_bracket_score() -> None:
    """같은 숫자를 한 줄에서 두 번 적지 않는다 — 알릴 것이 없다 (§4.6 · T2)."""
    results = [
        _expanded(
            "/docs/a.md",
            0.440,
            "채용계획",
            GraphExpansion(
                seed_doc_id="/docs/seed.md",
                seed_title="온보딩",
                seed_score=0.500,
                cosine=0.440,
                shared_tags=["인사"],
                shared_entities=[],
                reference=ReferenceDirection.NONE,
            ),
        )
    ]

    assert build_search_lines(results)[2] == "       └ 시드 «온보딩» · 공유 태그 `인사`"


def test_reference_wording_names_the_seed_explicitly() -> None:
    """근거 줄에는 문서가 둘 등장하므로 «시드»를 글자로 박는다 (§4.6 · T9).

    위키(`render.py`)의 「이 문서가 참조함」 3종은 **바뀌지 않는다** — 두 화면이 서로 다른
    기준을 말하므로 문구도 각자의 기준을 적는다.
    """
    wordings = []
    for direction in (
        ReferenceDirection.OUTGOING,
        ReferenceDirection.INCOMING,
        ReferenceDirection.MUTUAL,
        ReferenceDirection.NONE,
    ):
        results = [
            _expanded(
                "/docs/a.md",
                0.4,
                "문서",
                GraphExpansion(
                    seed_doc_id="/docs/seed.md",
                    seed_title="시드문서",
                    seed_score=0.5,
                    cosine=None,
                    shared_tags=[],
                    shared_entities=[],
                    reference=direction,
                ),
            )
        ]
        wordings.append(build_search_lines(results)[2])

    assert wordings == [
        "       └ 시드 «시드문서» · 시드를 참조함",
        "       └ 시드 «시드문서» · 시드가 참조함",
        "       └ 시드 «시드문서» · 서로 참조함",
        "       └ 시드 «시드문서»",  # 관계가 없으면 항목을 생략한다 — 시드 표기만 남는다
    ]


def test_multiple_shared_labels_are_backtick_wrapped_and_space_joined() -> None:
    """나열 관용구는 v0.6 `render.py:_evidence()`와 같은 결이다 — 조사로 잇지 않는다 (§4.6)."""
    results = [
        _expanded(
            "/docs/a.md",
            0.4,
            "문서",
            GraphExpansion(
                seed_doc_id="/docs/seed.md",
                seed_title="시드문서",
                seed_score=0.5,
                cosine=None,
                shared_tags=["인사", "채용"],
                shared_entities=["인사팀", "채용위원회"],
                reference=ReferenceDirection.NONE,
            ),
        )
    ]

    assert build_search_lines(results)[2] == (
        "       └ 시드 «시드문서» · 공유 태그 `인사` `채용` · 공유 엔티티 `인사팀` `채용위원회`"
    )
