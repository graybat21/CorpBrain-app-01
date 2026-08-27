"""단위 테스트 — 지식그래프 엔드포인트와 `iter_edges()` (v0.9 §4.3.1).

`iter_edges()`가 **`replace_graph()`의 읽기 대칭항**이라는 것이 이 파일의 요지다 — 쓴 것을
그대로 돌려받고, 대칭 엣지가 한 행으로 저장된다는 저장 규칙이 조회 어댑터로 새지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.models import EdgeType, GraphEdge, GraphNode, NodeType
from corpbrain.gui.api import SESSION_COOKIE, GuiApp

PORT = 8765
AUTH: ClassVar = {"Host": f"127.0.0.1:{PORT}", "Cookie": f"{SESSION_COOKIE}=sess"}

NODES = [
    GraphNode(id="/원문/a.md", type=NodeType.DOCUMENT, label="문서 A"),
    GraphNode(id="/원문/b.md", type=NodeType.DOCUMENT, label="문서 B"),
    GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
    GraphNode(id="entity:인사팀", type=NodeType.ENTITY, label="인사팀"),
]
EDGES = [
    GraphEdge(src="/원문/a.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
    GraphEdge(src="/원문/b.md", dst="tag:인사", type=EdgeType.TAGGED_WITH),
    GraphEdge(src="/원문/a.md", dst="entity:인사팀", type=EdgeType.CONTAINS_ENTITY),
    GraphEdge(src="/원문/a.md", dst="/원문/b.md", type=EdgeType.REFERENCES),
    GraphEdge(
        src="/원문/a.md", dst="/원문/b.md", type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.81
    ),
]


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    out = tmp_path / "wiki"
    out.mkdir()
    store = SqliteGraphStore(graph_path_for(out))
    try:
        store.replace_graph(NODES, EDGES)
    finally:
        store.close()
    return out


class TestIterEdges:
    def test_returns_everything_replace_graph_wrote(self, out_dir: Path) -> None:
        store = SqliteGraphStore(graph_path_for(out_dir), read_only=True)
        try:
            edges = list(store.iter_edges())
        finally:
            store.close()

        assert {(e.src, e.dst, e.type) for e in edges} == {
            (e.src, e.dst, e.type) for e in EDGES
        }

    def test_keeps_the_similarity_weight(self, out_dir: Path) -> None:
        store = SqliteGraphStore(graph_path_for(out_dir), read_only=True)
        try:
            weights = {e.type: e.weight for e in store.iter_edges()}
        finally:
            store.close()

        assert weights[EdgeType.SEMANTICALLY_SIMILAR] == pytest.approx(0.81)
        assert weights[EdgeType.REFERENCES] is None

    def test_order_is_deterministic(self, out_dir: Path) -> None:
        """같은 그래프를 두 번 열면 같은 순서다 — 노드 배치가 이유 없이 달라지지 않는다."""
        store = SqliteGraphStore(graph_path_for(out_dir), read_only=True)
        try:
            first = [(e.src, e.dst, e.type) for e in store.iter_edges()]
            second = [(e.src, e.dst, e.type) for e in store.iter_edges()]
        finally:
            store.close()

        assert first == second

    def test_works_on_a_read_only_open(self, out_dir: Path) -> None:
        """조회 경로는 파일에 쓰지 않는다 (v0.6.1 결정 계승)."""
        before = graph_path_for(out_dir).stat().st_mtime_ns
        store = SqliteGraphStore(graph_path_for(out_dir), read_only=True)
        try:
            list(store.iter_edges())
        finally:
            store.close()

        assert graph_path_for(out_dir).stat().st_mtime_ns == before


class TestGraphEndpoint:
    def _app(self, out_dir: Path) -> GuiApp:
        return GuiApp(out_dir=out_dir, token="tok", port=PORT, session_token="sess")

    def test_returns_all_nodes_and_edges(self, out_dir: Path) -> None:
        body = self._app(out_dir).handle("GET", "/api/graph", AUTH).json()

        assert {node["id"] for node in body["nodes"]} == {node.id for node in NODES}
        assert len(body["edges"]) == len(EDGES)
        assert body["stats"]["nodes"] == len(NODES)

    def test_type_names_are_core_enum_values(self, out_dir: Path) -> None:
        """§4.11 — 프론트가 자기 리터럴을 갖지 않도록 코어 값을 그대로 내려보낸다."""
        body = self._app(out_dir).handle("GET", "/api/graph", AUTH).json()

        assert {node["type"] for node in body["nodes"]} <= {
            "Document", "Entity", "Tag"
        }
        assert {edge["type"] for edge in body["edges"]} == {
            "TAGGED_WITH", "CONTAINS_ENTITY", "REFERENCES", "SEMANTICALLY_SIMILAR"
        }

    def test_nodes_carry_degree_for_sizing(self, out_dir: Path) -> None:
        body = self._app(out_dir).handle("GET", "/api/graph", AUTH).json()

        degrees = {node["id"]: node["degree"] for node in body["nodes"]}
        assert degrees["/원문/a.md"] == 4  # 태그 · 엔티티 · 참조 · 유사도

    def test_entity_and_tag_nodes_get_a_real_degree(self, out_dir: Path) -> None:
        """`degree_ranking()`은 문서만 담는다 — 그대로 쓰면 허브 태그가 가장 작게 그려진다."""
        body = self._app(out_dir).handle("GET", "/api/graph", AUTH).json()

        degrees = {node["id"]: node["degree"] for node in body["nodes"]}
        assert degrees["tag:인사"] == 2  # 문서 둘이 이 태그를 공유한다
        assert degrees["entity:인사팀"] == 1

    def test_no_cap_or_pruning_is_applied(self, out_dir: Path) -> None:
        """§5 — 4종 노드를 제한 없이 전부 그린다. 조용히 잘라 내지 않는다."""
        body = self._app(out_dir).handle("GET", "/api/graph", AUTH).json()

        assert len(body["nodes"]) == body["stats"]["nodes"]
        assert len(body["edges"]) == body["stats"]["edges"]

    def test_missing_graph_is_a_domain_state(self, tmp_path: Path) -> None:
        response = self._app(tmp_path / "없음").handle("GET", "/api/graph", AUTH)

        assert response.status == 200
        assert response.json()["error"] == "PreconditionError"
