"""`SqliteGraphStore` — 재료 증분 · 파생물 전체 재빌드 · 조회 (v0.6 스펙 §4.4 · §4.7 · §5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from corpbrain.core.errors import PreconditionError
from corpbrain.core.graphstore import (
    GRAPH_FILENAME,
    SCHEMA_VERSION,
    GraphStore,
    SqliteGraphStore,
    graph_path_for,
)
from corpbrain.core.models import DocFacts, EdgeType, GraphEdge, GraphNode, NodeType
from corpbrain.core.vectorstore import index_path_for


def _store(tmp_path: Path) -> SqliteGraphStore:
    return SqliteGraphStore(graph_path_for(tmp_path))


def _doc(node_id: str) -> GraphNode:
    return GraphNode(id=node_id, type=NodeType.DOCUMENT, label=node_id)


# --- 파일·스키마 ---------------------------------------------------------------


def test_graph_file_is_separate_from_vector_index(tmp_path: Path) -> None:
    """그래프 DB와 벡터 인덱스는 별도 파일이라 한쪽만 지워 재구축할 수 있다 (§4.4)."""
    assert graph_path_for(tmp_path).name == GRAPH_FILENAME
    assert graph_path_for(tmp_path) != index_path_for(tmp_path)


def test_new_store_records_schema_version(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        assert isinstance(store, GraphStore)

    conn = sqlite3.connect(graph_path_for(tmp_path))
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    conn.close()
    assert row[0] == SCHEMA_VERSION


def test_schema_version_mismatch_is_precondition_failure(tmp_path: Path) -> None:
    """자동 마이그레이션하지 않고 멈춘 뒤 삭제·재실행을 안내한다 (§5)."""
    with _store(tmp_path) as store:
        store.upsert_facts(DocFacts(doc_id="/w/a.txt", title="A"))
    conn = sqlite3.connect(graph_path_for(tmp_path))
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(PreconditionError) as excinfo:
        SqliteGraphStore(graph_path_for(tmp_path))

    message = str(excinfo.value)
    assert "스키마 버전" in message
    assert "지우고 다시 scan" in message


# --- 재료 (증분) ---------------------------------------------------------------


def test_upsert_and_get_facts_round_trip_korean(tmp_path: Path) -> None:
    facts = DocFacts(
        doc_id="/work/인사/채용계획.docx",
        title="2026년도 신입 채용 계획",
        tags=["채용", "인사"],
        entities=["인사팀", "그리팅 ATS"],
        refs=["/work/인사/온보딩.md"],
    )
    with _store(tmp_path) as store:
        store.upsert_facts(facts)

        assert store.get_facts("/work/인사/채용계획.docx") == facts


def test_get_facts_returns_none_when_absent(tmp_path: Path) -> None:
    """복원 경로가 '행이 있는가'를 이 값으로 판정한다 (§4.4)."""
    with _store(tmp_path) as store:
        assert store.get_facts("/work/없는문서.txt") is None


def test_upsert_facts_overwrites_previous_material(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.upsert_facts(DocFacts(doc_id="/w/a.txt", title="옛 제목", tags=["옛태그"]))
        store.upsert_facts(DocFacts(doc_id="/w/a.txt", title="새 제목", tags=["새태그"]))

        stored = store.get_facts("/w/a.txt")
        assert stored is not None
        assert stored.title == "새 제목"
        assert stored.tags == ["새태그"]


def test_iter_facts_is_ordered_by_doc_id(tmp_path: Path) -> None:
    """파생이 결정적이려면 입력 순서부터 고정돼야 한다 (§3 항목4)."""
    with _store(tmp_path) as store:
        for doc_id in ("/w/c.txt", "/w/a.txt", "/w/b.txt"):
            store.upsert_facts(DocFacts(doc_id=doc_id, title=doc_id))

        assert [f.doc_id for f in store.iter_facts()] == ["/w/a.txt", "/w/b.txt", "/w/c.txt"]


def test_delete_facts_removes_row_and_tolerates_missing(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.upsert_facts(DocFacts(doc_id="/w/a.txt", title="A"))
        store.delete_facts("/w/a.txt")
        store.delete_facts("/w/없음.txt")  # 없어도 조용히 통과

        assert store.get_facts("/w/a.txt") is None


# --- 파생물 (전체 재빌드) -------------------------------------------------------


def test_replace_graph_replaces_everything(tmp_path: Path) -> None:
    """임계치가 바뀌어도 옛 엣지가 남지 않는다 (§4.4 재빌드 전략)."""
    with _store(tmp_path) as store:
        store.replace_graph(
            [_doc("/w/a.txt"), _doc("/w/b.txt")],
            [
                GraphEdge(
                    src="/w/a.txt",
                    dst="/w/b.txt",
                    type=EdgeType.SEMANTICALLY_SIMILAR,
                    weight=0.80,
                )
            ],
        )
        store.replace_graph([_doc("/w/a.txt")], [])

        stats = store.stats()
        assert stats.documents == 1
        assert stats.edges == 0


def test_replace_graph_rolls_back_and_keeps_previous_graph(tmp_path: Path) -> None:
    """단일 트랜잭션이라 실패 시 이전 그래프가 그대로 보존된다 (§5)."""
    with _store(tmp_path) as store:
        good_edge = GraphEdge(src="/w/a.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH)
        store.replace_graph([_doc("/w/a.txt")], [good_edge])

        duplicate = GraphEdge(src="/w/x.txt", dst="tag:x", type=EdgeType.TAGGED_WITH)
        with pytest.raises(sqlite3.IntegrityError):
            store.replace_graph([_doc("/w/x.txt")], [duplicate, duplicate])

        stats = store.stats()
        assert stats.documents == 1
        assert stats.edges_by_type[str(EdgeType.TAGGED_WITH)] == 1
        assert store.neighbors("/w/a.txt") == [good_edge]


def test_replace_graph_does_not_touch_doc_facts(tmp_path: Path) -> None:
    """재료와 파생물의 수명은 분리돼 있다 — 재빌드가 재료를 지우지 않는다 (§4.4)."""
    with _store(tmp_path) as store:
        store.upsert_facts(DocFacts(doc_id="/w/a.txt", title="A", entities=["인사팀"]))
        store.replace_graph([], [])

        stored = store.get_facts("/w/a.txt")
        assert stored is not None
        assert stored.entities == ["인사팀"]


# --- 조회 ---------------------------------------------------------------------


def test_stats_counts_nodes_by_type_and_all_four_edge_types(tmp_path: Path) -> None:
    """엣지 4종을 0까지 포함해 담아 그래프가 비어도 출력 줄 수가 흔들리지 않는다."""
    with _store(tmp_path) as store:
        store.replace_graph(
            [
                _doc("/w/a.txt"),
                _doc("/w/b.txt"),
                GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
                GraphNode(id="entity:인사팀", type=NodeType.ENTITY, label="인사팀"),
            ],
            [
                GraphEdge(src="/w/a.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="/w/b.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(
                    src="/w/a.txt", dst="entity:인사팀", type=EdgeType.CONTAINS_ENTITY
                ),
            ],
        )

        stats = store.stats()
        assert (stats.documents, stats.entities, stats.tags) == (2, 1, 1)
        assert stats.nodes == 4
        assert stats.edges == 3
        assert stats.edges_by_type == {
            str(EdgeType.TAGGED_WITH): 2,
            str(EdgeType.CONTAINS_ENTITY): 1,
            str(EdgeType.SEMANTICALLY_SIMILAR): 0,
            str(EdgeType.REFERENCES): 0,
        }


def test_neighbors_sees_both_directions_of_a_symmetric_edge(tmp_path: Path) -> None:
    """대칭 엣지는 src<dst로 한 행만 저장하므로 조회가 양쪽을 봐야 한다 (§4.1)."""
    edge = GraphEdge(
        src="/w/a.txt", dst="/w/b.txt", type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.81
    )
    with _store(tmp_path) as store:
        store.replace_graph([_doc("/w/a.txt"), _doc("/w/b.txt")], [edge])

        assert store.neighbors("/w/a.txt") == [edge]
        assert store.neighbors("/w/b.txt") == [edge]


def test_neighbors_of_unknown_node_is_empty(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
        store.replace_graph([_doc("/w/a.txt")], [])

        assert store.neighbors("/w/없음.txt") == []


def test_degree_ranking_lists_documents_by_degree_then_id(tmp_path: Path) -> None:
    """문서만, 차수 내림차순, 동점은 노드 id 사전순 (§4.7)."""
    with _store(tmp_path) as store:
        store.replace_graph(
            [
                _doc("/w/a.txt"),
                _doc("/w/b.txt"),
                _doc("/w/c.txt"),
                GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
            ],
            [
                GraphEdge(src="/w/a.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="/w/b.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="/w/c.txt", dst="tag:인사", type=EdgeType.TAGGED_WITH),
                GraphEdge(
                    src="/w/a.txt",
                    dst="/w/c.txt",
                    type=EdgeType.SEMANTICALLY_SIMILAR,
                    weight=0.9,
                ),
            ],
        )

        # a: 2, c: 2, b: 1 — a와 c는 동점이므로 사전순. 태그 노드는 목록에 없다.
        assert store.degree_ranking() == [("/w/a.txt", 2), ("/w/c.txt", 2), ("/w/b.txt", 1)]
