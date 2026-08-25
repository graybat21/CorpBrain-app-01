"""v0.6 그래프 값 타입과 설정 기본값 (v0.6 스펙 §4.1 · §4.6 · §4.7)."""

from __future__ import annotations

from pathlib import Path

from corpbrain.core import (
    DEFAULT_RELATED_TOP_K,
    DEFAULT_SIMILARITY_THRESHOLD,
    DocFacts,
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphOutcome,
    GraphSkipReason,
    GraphStats,
    InjectionFailure,
    NodeType,
    ScanConfig,
    ScanResult,
)


def test_node_type_values_match_spec_table() -> None:
    """노드 3종의 표기가 스펙 §4.1 표와 정확히 같다."""
    assert [t.value for t in NodeType] == ["Document", "Entity", "Tag"]


def test_edge_type_values_match_spec_table() -> None:
    """엣지 4종의 표기가 스펙 §4.1 표와 정확히 같다.

    이 값이 곧 `GraphStats.edges_by_type`의 키이자 `edges.type` 컬럼이므로, 표기가 갈리면
    저장소·집계·출력이 조용히 어긋난다.
    """
    assert [t.value for t in EdgeType] == [
        "TAGGED_WITH",
        "CONTAINS_ENTITY",
        "SEMANTICALLY_SIMILAR",
        "REFERENCES",
    ]


def test_graph_skip_reason_values() -> None:
    assert [r.value for r in GraphSkipReason] == ["vectors_unavailable", "build_failed"]


def test_doc_facts_defaults_are_empty_lists() -> None:
    """재료가 하나도 없는 문서도 표현할 수 있다 (엔티티 없는 v0.5 산출물 복원 경로)."""
    facts = DocFacts(doc_id="/work/a.txt", title="제목")

    assert facts.tags == []
    assert facts.entities == []
    assert facts.refs == []


def test_graph_stats_totals_are_derived_from_parts() -> None:
    stats = GraphStats(
        documents=6,
        entities=11,
        tags=6,
        edges_by_type={EdgeType.TAGGED_WITH: 14, EdgeType.SEMANTICALLY_SIMILAR: 5},
    )

    assert stats.nodes == 23
    assert stats.edges == 19


def test_graph_stats_empty_graph_totals_zero() -> None:
    stats = GraphStats()

    assert stats.nodes == 0
    assert stats.edges == 0


def test_graph_outcome_defaults_report_nothing_wrong() -> None:
    """그래프가 정상이면 생략 사유도 실패도 없다."""
    outcome = GraphOutcome()

    assert outcome.stats is None
    assert outcome.similarity_skipped is None
    assert outcome.build_failure == ""
    assert outcome.facts_missing_count == 0
    assert outcome.related_updated_count == 0
    assert outcome.injection_failures == []


def test_graph_edge_weight_is_optional() -> None:
    """가중치는 SEMANTICALLY_SIMILAR에만 쓰고 나머지 3종은 없다."""
    tagged = GraphEdge(src="/work/a.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH)
    similar = GraphEdge(
        src="/work/a.txt",
        dst="/work/b.txt",
        type=EdgeType.SEMANTICALLY_SIMILAR,
        weight=0.81,
    )

    assert tagged.weight is None
    assert similar.weight == 0.81


def test_graph_node_props_default_empty() -> None:
    node = GraphNode(id="tag:인사", type=NodeType.TAG, label="인사")

    assert node.props == {}


def test_injection_failure_shape_matches_embedding_failure() -> None:
    """v0.4 EmbeddingFailure와 같은 (경로, 사유) 모양이다."""
    failure = InjectionFailure(path=Path("/work/wiki/a.txt.md"), detail="권한 거부")

    assert failure.path == Path("/work/wiki/a.txt.md")
    assert failure.detail == "권한 거부"


def test_scan_config_graph_defaults_preserve_backward_compatibility() -> None:
    """신규 파라미터는 선택이고 기본값이 보존된다 (ROADMAP §5 하위 호환 불변식)."""
    config = ScanConfig(folder=Path("./docs"))

    assert config.similarity_threshold == DEFAULT_SIMILARITY_THRESHOLD
    assert config.related_top_k == DEFAULT_RELATED_TOP_K == 5


def test_scan_result_graph_defaults_to_none() -> None:
    """그래프 단계가 돌지 않은 실행은 `graph`가 None이다."""
    result = ScanResult(out_dir=Path("./corpbrain_wiki"))

    assert result.graph is None
