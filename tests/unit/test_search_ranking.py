"""v0.7 하이브리드 검색 — 값 타입·설정 기본값과 확산 순위 계산 (스펙 §4.1·§4.2·§4.3·§4.5).

`graph.py`의 확산 계산은 순수 함수다 — 저장소도 파일도 네트워크도 없이 여기서 전부 덮인다.
`graph_decay`는 `DEFAULT_GRAPH_DECAY`를 참조하지 않고 **명시적으로 넘긴다**(스펙 T11) —
실측 후 상수 한 줄을 갈아끼워도 이 파일이 깨지지 않게 하기 위함이다.
"""

from __future__ import annotations

import pytest

from corpbrain.core import (
    DEFAULT_EXPAND_EDGES,
    DEFAULT_GRAPH_DECAY,
    EdgeType,
    GraphEdge,
    GraphExpansion,
    ReferenceDirection,
    SearchResult,
)
from corpbrain.core.errors import PreconditionError
from corpbrain.core.graph import parse_expand_edges, rank_hybrid, validate_graph_decay

# --- U1: 값 타입·설정 ---------------------------------------------------------


def test_default_expand_edges_are_the_three_non_embedding_signals() -> None:
    """기본 확산 엣지는 3종이며 `SEMANTICALLY_SIMILAR`는 빠져 있다 (스펙 §4.2).

    임베딩 코사인 그 자체인 엣지를 기본에 넣으면 같은 신호를 두 번 세게 된다.
    """
    assert DEFAULT_EXPAND_EDGES == frozenset(
        {EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY, EdgeType.REFERENCES}
    )
    assert EdgeType.SEMANTICALLY_SIMILAR not in DEFAULT_EXPAND_EDGES


def test_default_graph_decay_lies_in_the_open_interval() -> None:
    """기본값을 실측으로 갈아끼워도 유효 범위 `0 < α < 1` 안이어야 한다 (§4.1)."""
    assert 0.0 < DEFAULT_GRAPH_DECAY < 1.0


def test_search_result_expansion_defaults_to_none() -> None:
    """코사인 단독 경로(v0.4)의 결과 타입이 그대로 유지된다 — 선택 필드 하나만 늘었다 (§4.5)."""
    result = SearchResult(doc_id="/docs/a.md", score=0.5, metadata={})

    assert result.expansion is None


def test_graph_expansion_carries_labels_not_node_ids() -> None:
    """`shared_tags`·`shared_entities`는 표시 라벨을 담는다 — 렌더러가 재변환하지 않는다 (§4.5)."""
    expansion = GraphExpansion(
        seed_doc_id="/docs/seed.md",
        seed_title="온보딩",
        seed_score=0.71,
        cosine=0.38,
        shared_tags=["인사"],
        shared_entities=["인사팀"],
        reference=ReferenceDirection.MUTUAL,
    )

    assert expansion.shared_tags == ["인사"]
    assert not any(tag.startswith("tag:") for tag in expansion.shared_tags)
    assert not any(name.startswith("entity:") for name in expansion.shared_entities)


# --- U2: 확산 순위 계산 -------------------------------------------------------

ALPHA = 0.7  # 상수를 참조하지 않고 명시적으로 넘긴다 (스펙 T11)
ALL_EDGES = frozenset(EdgeType)
NO_SIMILARITY = frozenset(
    {EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY, EdgeType.REFERENCES}
)


def _hit(doc_id: str, score: float, title: str = "") -> SearchResult:
    return SearchResult(
        doc_id=doc_id,
        score=score,
        metadata={"title": title or doc_id, "source_path": doc_id},
    )


def _tagged(doc_id: str, tag: str) -> GraphEdge:
    return GraphEdge(src=doc_id, dst=f"tag:{tag}", type=EdgeType.TAGGED_WITH)


def _entity(doc_id: str, name: str) -> GraphEdge:
    return GraphEdge(src=doc_id, dst=f"entity:{name}", type=EdgeType.CONTAINS_ENTITY)


def _references(src: str, dst: str) -> GraphEdge:
    return GraphEdge(src=src, dst=dst, type=EdgeType.REFERENCES)


LABELS = {"tag:인사": "인사", "entity:인사팀": "인사팀", "/b.md": "채용계획", "/c.md": "메모"}


def test_expansion_score_is_seed_score_times_decay() -> None:
    """확산 문서의 점수는 `max(자기 코사인, 시드 점수 × α)`다 (스펙 §4.1)."""
    ranked = [_hit("/a.md", 0.90, "온보딩"), _hit("/b.md", 0.10, "채용계획")]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=1
    )

    assert [r.doc_id for r in results] == ["/a.md"]  # top_k=1 로 잘린다

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    # /b.md 는 시드(top_k=2)라 코사인 그대로다 — 확산이 시드 점수를 건드리지 않는다.
    assert [(r.doc_id, r.score) for r in results] == [("/a.md", 0.90), ("/b.md", 0.10)]


def test_document_outside_top_k_is_pulled_in_by_the_graph() -> None:
    """코사인 top-k 밖 문서가 확산으로 후보가 되고 점수는 `시드 × α`다 (§3 항목1)."""
    ranked = [_hit("/a.md", 0.90, "온보딩"), _hit("/z.md", 0.30), _hit("/b.md", 0.10, "채용계획")]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )

    assert [r.doc_id for r in results] == ["/a.md", "/b.md"]
    assert results[1].score == 0.90 * ALPHA
    # 코사인 상위였던 /z.md 가 밀려나는 것은 재순위화의 의도된 동작이다 (§4.1).
    assert results[1].expansion is not None
    assert results[1].expansion.seed_doc_id == "/a.md"
    assert results[1].expansion.seed_title == "온보딩"
    assert results[1].expansion.cosine == 0.10


def test_seed_keeps_expansion_none_even_when_it_is_also_a_neighbor() -> None:
    """경계는 «후보 진입 경로»다 — 시드는 다른 시드의 이웃이어도 근거 줄을 갖지 않는다 (§4.5)."""
    ranked = [_hit("/a.md", 0.90), _hit("/b.md", 0.80)]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )

    assert [r.expansion for r in results] == [None, None]


def test_seed_wins_an_exact_score_tie_against_an_expansion_document() -> None:
    """점수가 정확히 같으면 시드가 남는다 (§4.3 · 2026-08-26 결정).

    `/b.md` 는 코사인 top-k 밖이고 자기 코사인(0.44)이 `시드 × α`(0.50 × 0.7 = 0.35)를
    이겨 점수가 최하위 시드 `/x.md` 와 정확히 같아진다. 이때 확산 문서를 앞세우면 **코사인
    top-k 안에 정말로 들어온 문서가 감쇠로 그 자리에 온 문서에 밀려 잘려 나간다.**
    §4.1이 「코사인 하위 시드가 밀려나는 것은 의도된 동작」이라고 한 것은 확산 문서의 점수가
    더 **높을 때**이지 같을 때가 아니다.

    이전 구현은 §4.3의 관계 축(공유 태그·엔티티·참조)을 시드에도 매겨 이 동점에서 확산
    문서가 이겼다. 그 축들은 전부 「**시드와의** 공유 …」라 시드 자신에게는 적용할 대상이
    없다는 것이 정정의 근거다.
    """
    ranked = [_hit("/a.md", 0.50), _hit("/x.md", 0.44), _hit("/b.md", 0.44)]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )

    assert [r.doc_id for r in results] == ["/a.md", "/x.md"]
    assert [r.expansion for r in results] == [None, None]   # 둘 다 시드로 남았다


def test_an_expansion_document_that_enters_always_scores_above_its_own_cosine() -> None:
    """위 결정의 따름정리 — 결과에 오른 확산 문서의 점수는 늘 `시드 × α` 다 (§4.5 표 주석).

    확산 문서의 코사인은 정의상 최하위 시드의 코사인 이하이므로, 자기 코사인이 `max()`를
    이긴 문서는 잘해야 최하위 시드와 동점이고 그 동점은 이제 시드가 가져간다. 따라서 결과에
    남은 확산 문서는 «자기 코사인 < 점수» 를 만족한다. 근거 줄이 코사인을 따로 적는 이유가
    바로 이것이다 — 대괄호 숫자는 그 문서의 코사인이 아니다.
    """
    ranked = [_hit("/a.md", 0.90), _hit("/x.md", 0.50), _hit("/b.md", 0.10)]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    expanded = [r for r in results if r.expansion is not None]

    assert [r.doc_id for r in results] == ["/a.md", "/b.md"]  # 0.90 × 0.7 = 0.63 > 시드 0.50
    assert len(expanded) == 1
    assert expanded[0].expansion is not None
    assert expanded[0].expansion.cosine is not None
    assert expanded[0].expansion.cosine < expanded[0].score


def test_expansion_never_outranks_its_seed() -> None:
    """§3 항목4 — 열린 구간 `0 < α < 1`에서 확산 문서는 자기 시드를 추월하지 못한다."""
    ranked = [_hit("/a.md", 0.90), _hit("/x.md", 0.80), _hit("/b.md", 0.70)]
    edges = [_tagged("/a.md", "인사"), _tagged("/b.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=0.95, top_k=2
    )

    for result in results:
        assert result.expansion is None or result.score <= result.expansion.seed_score


def test_shared_tags_and_entities_are_labels_of_the_base_seed_relation() -> None:
    ranked = [_hit("/a.md", 0.90, "온보딩"), _hit("/x.md", 0.50), _hit("/b.md", 0.10)]
    edges = [
        _tagged("/a.md", "인사"),
        _tagged("/b.md", "인사"),
        _entity("/a.md", "인사팀"),
        _entity("/b.md", "인사팀"),
        _references("/b.md", "/a.md"),
        _references("/a.md", "/b.md"),
    ]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    expansion = next(r for r in results if r.doc_id == "/b.md").expansion

    assert expansion is not None
    assert expansion.shared_tags == ["인사"]
    assert expansion.shared_entities == ["인사팀"]
    assert expansion.reference is ReferenceDirection.MUTUAL


def test_reference_direction_is_read_from_the_expansion_document_side() -> None:
    """줄의 주인은 확산 문서다 — 확산 문서 → 시드가 `OUTGOING`이다 (§4.6)."""
    ranked = [_hit("/a.md", 0.90), _hit("/x.md", 0.50), _hit("/b.md", 0.10)]

    outgoing = rank_hybrid(
        ranked,
        [_references("/b.md", "/a.md")],
        labels=LABELS,
        expand_edges=NO_SIMILARITY,
        decay=ALPHA,
        top_k=2,
    )
    incoming = rank_hybrid(
        ranked,
        [_references("/a.md", "/b.md")],
        labels=LABELS,
        expand_edges=NO_SIMILARITY,
        decay=ALPHA,
        top_k=2,
    )

    assert outgoing[1].expansion is not None
    assert outgoing[1].expansion.reference is ReferenceDirection.OUTGOING
    assert incoming[1].expansion is not None
    assert incoming[1].expansion.reference is ReferenceDirection.INCOMING


def test_tie_break_follows_the_hierarchical_keys() -> None:
    """동점 그룹은 참조 → 공유 엔티티 수 → 공유 태그 수 → 자기 코사인 → doc_id 순 (§4.3, §3 항목5)."""
    ranked = [_hit("/seed.md", 0.90), _hit("/x.md", 0.50)]
    edges = [
        _tagged("/seed.md", "인사"),
        _entity("/seed.md", "인사팀"),
        _references("/ref.md", "/seed.md"),
        # 넷 다 시드의 태그를 공유해 점수가 `0.90 × α` 로 같다.
        _tagged("/ref.md", "인사"),
        _tagged("/ent.md", "인사"),
        _entity("/ent.md", "인사팀"),
        _tagged("/tag.md", "인사"),
        _tagged("/aaa.md", "인사"),
    ]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=5
    )

    assert [r.doc_id for r in results] == [
        "/seed.md",  # 시드 (코사인 0.90)
        "/ref.md",  # ① 참조 관계
        "/ent.md",  # ② 공유 엔티티 1개
        "/aaa.md",  # ⑤ doc_id 사전순 — 벡터가 없어 코사인은 둘 다 최하위
        "/tag.md",
    ]
    assert {r.score for r in results if r.expansion} == {0.90 * ALPHA}


def test_own_cosine_breaks_ties_before_doc_id() -> None:
    """정렬 키 4 — 벡터가 없는 확산 문서는 자기 코사인이 최하위로 취급된다 (§4.3·§5)."""
    ranked = [
        _hit("/seed.md", 0.90),
        _hit("/x1.md", 0.50),
        _hit("/x2.md", 0.40),
        _hit("/zzz.md", 0.10),
    ]
    edges = [
        _tagged("/seed.md", "인사"),
        _tagged("/zzz.md", "인사"),  # 벡터 있음 (코사인 0.10 — 0.90 × α 에 밀려 점수는 동점)
        _tagged("/aaa.md", "인사"),  # 벡터 없음
    ]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=3
    )

    # 사전순으로는 /aaa.md 가 앞이지만 코사인이 있는 /zzz.md 가 먼저다.
    assert [r.doc_id for r in results] == ["/seed.md", "/zzz.md", "/aaa.md"]
    assert {r.score for r in results if r.expansion} == {0.90 * ALPHA}
    assert next(r for r in results if r.doc_id == "/aaa.md").expansion.cosine is None


def test_base_seed_is_the_highest_scoring_adjacent_seed() -> None:
    """여러 시드의 이웃이면 가장 높은 점수를 준 시드가 근거·정렬의 기준이다 (§4.3)."""
    ranked = [_hit("/high.md", 0.90, "높은쪽"), _hit("/low.md", 0.60, "낮은쪽"), _hit("/x.md", 0.40)]
    edges = [
        _tagged("/high.md", "인사"),
        _tagged("/low.md", "인사"),
        _tagged("/b.md", "인사"),
    ]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    expansion = next(r for r in results if r.doc_id == "/b.md").expansion

    assert expansion is not None
    assert expansion.seed_doc_id == "/high.md"
    assert expansion.seed_score == 0.90


def test_base_seed_ties_break_on_seed_doc_id() -> None:
    ranked = [_hit("/b_seed.md", 0.90), _hit("/a_seed.md", 0.90), _hit("/x.md", 0.40)]
    edges = [
        _tagged("/b_seed.md", "인사"),
        _tagged("/a_seed.md", "인사"),
        _tagged("/target.md", "인사"),
    ]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=3
    )
    expansion = next(r for r in results if r.doc_id == "/target.md").expansion

    assert expansion is not None
    assert expansion.seed_doc_id == "/a_seed.md"


def test_dropping_references_from_expand_edges_removes_reference_only_documents() -> None:
    """§3 항목6 — `--expand-edges`에서 `REFERENCES`를 빼면 참조로만 이어진 문서가 사라진다."""
    ranked = [_hit("/a.md", 0.90), _hit("/x.md", 0.40)]
    edges = [_references("/a.md", "/b.md")]

    with_refs = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    without_refs = rank_hybrid(
        ranked,
        edges,
        labels=LABELS,
        expand_edges=frozenset({EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY}),
        decay=ALPHA,
        top_k=2,
    )

    assert {r.doc_id for r in with_refs} == {"/a.md", "/b.md"}
    assert {r.doc_id for r in without_refs} == {"/a.md", "/x.md"}


def test_similarity_edges_expand_only_when_enabled() -> None:
    ranked = [_hit("/a.md", 0.90), _hit("/x.md", 0.40)]
    edges = [
        GraphEdge(src="/a.md", dst="/b.md", type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.8)
    ]

    off = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    on = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=ALL_EDGES, decay=ALPHA, top_k=2
    )

    assert {r.doc_id for r in off} == {"/a.md", "/x.md"}
    assert {r.doc_id for r in on} == {"/a.md", "/b.md"}


def test_result_count_never_exceeds_top_k() -> None:
    """§3 항목3 — 확산으로 후보가 넘쳐도 반환 길이는 `top_k` 이하다."""
    ranked = [_hit("/a.md", 0.90)]
    edges = [_tagged("/a.md", "인사")] + [_tagged(f"/d{i}.md", "인사") for i in range(20)]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=5
    )

    assert len(results) == 5


def test_top_k_zero_returns_nothing() -> None:
    """v0.4의 clamp 동작을 그대로 둔다 (§5)."""
    ranked = [_hit("/a.md", 0.90)]

    assert rank_hybrid(
        ranked, [], labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=0
    ) == []
    assert rank_hybrid(
        ranked, [], labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=-3
    ) == []


def test_seed_missing_from_the_graph_keeps_its_cosine_score() -> None:
    """§5 — 패스1과 패스2 사이에서 scan이 죽어 시드가 `nodes`에 없어도 조용히 지나간다."""
    ranked = [_hit("/a.md", 0.90), _hit("/b.md", 0.50)]

    results = rank_hybrid(
        ranked, [], labels={}, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )

    assert [(r.doc_id, r.score, r.expansion) for r in results] == [
        ("/a.md", 0.90, None),
        ("/b.md", 0.50, None),
    ]


def test_expansion_without_a_vector_uses_the_graph_label_for_display() -> None:
    """벡터 인덱스에 없는 확산 문서의 표시 라벨은 그래프 `nodes.label`에서만 온다 (§4.7)."""
    ranked = [_hit("/a.md", 0.90)]
    edges = [_tagged("/a.md", "인사"), _tagged("/c.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=2
    )
    expanded = next(r for r in results if r.doc_id == "/c.md")

    assert expanded.metadata == {"title": "메모"}  # source_path 는 없다 — doc_id 로 대체된다
    assert expanded.expansion is not None
    assert expanded.expansion.cosine is None
    assert expanded.score == 0.90 * ALPHA


def test_a_document_is_never_its_own_neighbor() -> None:
    """v0.6이 자기 루프 엣지를 만들지 않으므로 추가 처리가 필요 없다 — 그래도 방어한다 (§4.2)."""
    ranked = [_hit("/a.md", 0.90)]
    edges = [_references("/a.md", "/a.md"), _tagged("/a.md", "인사")]

    results = rank_hybrid(
        ranked, edges, labels=LABELS, expand_edges=NO_SIMILARITY, decay=ALPHA, top_k=3
    )

    assert [r.doc_id for r in results] == ["/a.md"]


# --- U3: 입력 검증 ------------------------------------------------------------


@pytest.mark.parametrize("alpha", [0.01, 0.5, 0.7, 0.99])
def test_graph_decay_inside_the_open_interval_is_returned_as_is(alpha: float) -> None:
    assert validate_graph_decay(alpha) == alpha


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5, float("nan")])
def test_graph_decay_outside_the_open_interval_is_rejected(alpha: float) -> None:
    """§3 항목8 — 경계값 0.0·1.0을 포함해 범위 밖은 `PreconditionError`다. 클램프하지 않는다.

    α ≥ 1은 확산 문서가 시드를 추월하거나 전부 동점이 되고, α ≤ 0은 확산 기여가 사라져
    플래그가 무의미해진다. 조용히 다른 값으로 바꾸면 α를 스윕해 효과를 재는 측정 절차가
    «준 값과 다른 값으로 계산된 결과»를 보게 된다 (§4.1).
    """
    with pytest.raises(PreconditionError):
        validate_graph_decay(alpha)


def test_expand_edges_parses_edge_type_values_verbatim() -> None:
    """`EdgeType` StrEnum 값을 그대로 받는다 — 짧은 별칭을 새로 만들지 않는다 (§4.4)."""
    assert parse_expand_edges("TAGGED_WITH,REFERENCES") == frozenset(
        {EdgeType.TAGGED_WITH, EdgeType.REFERENCES}
    )


def test_expand_edges_trims_whitespace_and_absorbs_duplicates() -> None:
    assert parse_expand_edges(" TAGGED_WITH , REFERENCES ,TAGGED_WITH") == frozenset(
        {EdgeType.TAGGED_WITH, EdgeType.REFERENCES}
    )


@pytest.mark.parametrize(
    "raw",
    [
        "tagged_with",  # 소문자 — 어휘가 갈리지 않게 받아 주지 않는다
        "",  # 빈 목록 — 확산을 끄는 길은 --no-graph 하나여야 한다
        "   ",
        "TAGGED_WITH,",  # 빈 항목
        ",TAGGED_WITH",
        "TAGGED_WITH,NOT_AN_EDGE",
    ],
)
def test_expand_edges_rejects_malformed_input(raw: str) -> None:
    """§4.4 입력 처리 규칙 표 — 소문자·빈 목록·빈 항목·미지의 값은 exit 1이 될 예외다."""
    with pytest.raises(PreconditionError):
        parse_expand_edges(raw)
