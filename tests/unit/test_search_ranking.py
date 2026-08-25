"""v0.7 하이브리드 검색 — 값 타입·설정 기본값과 확산 순위 계산 (스펙 §4.1·§4.2·§4.3·§4.5).

`graph.py`의 확산 계산은 순수 함수다 — 저장소도 파일도 네트워크도 없이 여기서 전부 덮인다.
`graph_decay`는 `DEFAULT_GRAPH_DECAY`를 참조하지 않고 **명시적으로 넘긴다**(스펙 T11) —
실측 후 상수 한 줄을 갈아끼워도 이 파일이 깨지지 않게 하기 위함이다.
"""

from __future__ import annotations

from corpbrain.core import (
    DEFAULT_EXPAND_EDGES,
    DEFAULT_GRAPH_DECAY,
    EdgeType,
    GraphExpansion,
    ReferenceDirection,
    SearchResult,
)

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
    """잠정값이라도 유효 범위 `0 < α < 1` 안이어야 코어 검증을 스스로 통과한다 (§4.1)."""
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
