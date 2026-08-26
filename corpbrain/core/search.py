"""검색 — 벡터 인덱스와 지식그래프에서 쿼리와 관련된 문서를 찾는다 (v0.4 §4.1 · v0.7 §4.5).

인덱스 파일이 없으면 `IndexNotFoundError`(선행 조건 실패, exit 1). 인덱스가 있지만 결과가
0건이면 빈 리스트를 정상 반환한다(exit 0 — v0.4 스펙 §3 항목6). 쿼리 임베딩은 인덱스
메타데이터에 기록된 모델을 강제로 쓴다(v0.4 §4.3 — `search`에는 `--embed-model` 플래그가 없다).

v0.7부터 코사인 상위 `top_k` 문서를 **시드**로 삼아 그래프로 연결된 문서를 후보에 끌어올린다.
이 모듈이 하는 것은 **저장소 조회와 조립뿐**이고, 점수·정렬·근거 계산은 `graph.rank_hybrid()`가
순수 계산으로 맡는다. 추가 LLM 호출과 추가 네트워크 연결은 없다 — 쿼리 임베딩 1회는 v0.4와
같고, 그래프 조회는 소켓을 하나도 열지 않는다 (v0.7 §3 항목11).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from corpbrain.core.config import (
    DEFAULT_EXPAND_EDGES,
    DEFAULT_GRAPH_DECAY,
    DEFAULT_OLLAMA_URL,
)
from corpbrain.core.errors import PreconditionError
from corpbrain.core.graph import rank_hybrid, validate_graph_decay
from corpbrain.core.graphstore import GraphStore, SqliteGraphStore, graph_path_for
from corpbrain.core.llm.embed import EmbeddingError, embed
from corpbrain.core.models import EdgeType, GraphEdge, SearchResult
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

__all__ = ["IndexNotFoundError", "search_index"]

#: 태그·엔티티 노드를 한쪽 끝으로 갖는 엣지 — 이 노드들을 한 번 더 조회해야 «같은 태그를
#: 가진 다른 문서»에 닿는다. 문서 → Tag/Entity → 문서는 「문서 1홉」이다 (v0.7 §4.1).
_ATTRIBUTE_EDGES = (EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY)


class IndexNotFoundError(PreconditionError):
    """인덱스 파일이 없거나 비어 있음 — 먼저 `scan`을 실행해야 한다 (v0.4 스펙 §3 항목6)."""


def search_index(
    out_dir: Path,
    query: str,
    *,
    top_k: int = 5,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    graph: bool = True,
    graph_decay: float = DEFAULT_GRAPH_DECAY,
    expand_edges: frozenset[EdgeType] = DEFAULT_EXPAND_EDGES,
) -> list[SearchResult]:
    """`out_dir`의 인덱스·그래프에서 `query`와 관련된 문서 상위 `top_k`건을 돌려준다.

    Args:
        out_dir: `scan --out`으로 위키·인덱스·그래프 DB가 쌓인 폴더.
        query: 자연어 검색어.
        top_k: 시드 개수이자 최종 결과 개수 (v0.7 §4.4).
        ollama_url: `--ollama-url` 값. 이 대상 외에는 접속하지 않는다.
        graph: `False`면 그래프 확산 없이 코사인 단독 — v0.4 동작 그대로다.
        graph_decay: 확산 감쇠 계수 α. `0 < α < 1` 밖이면 `PreconditionError`다 (§4.1 · T5).
        expand_edges: 확산에 쓸 엣지 종류. 빈 집합은 받지 않는다 — 확산을 끄는 길은
            `graph=False` 하나여야 §3 항목2·7이 다루는 경로가 갈라지지 않는다 (§4.4 · T10).

    Raises:
        IndexNotFoundError: `out_dir`에 인덱스 파일이 없거나(먼저 scan 필요) 비어 있음.
        PreconditionError: α가 유효 범위 밖 · `expand_edges`가 빈 집합 · 쿼리 임베딩 실패 ·
            그래프 DB 손상·스키마 불일치(자동 복구하지 않는다, §5).
    """
    # 검증은 인덱스를 열기 전에 무조건 한다 — 잘못된 입력은 `--no-graph` 여부와 무관하게
    # 잘못된 입력이고, 규칙이 분기 없이 한 줄이어야 코어를 직접 부르는 어댑터도 같은 답을 본다.
    validate_graph_decay(graph_decay)
    if not expand_edges:
        raise PreconditionError(
            "--expand-edges 가 비어 있습니다 — 확산을 끄려면 --no-graph 를 쓰세요."
        )

    path = index_path_for(out_dir)
    if not path.exists():
        raise IndexNotFoundError(
            f"인덱스가 없습니다: {path} — 먼저 `corpbrain scan {out_dir}`을 실행하세요."
        )

    store = SqliteVectorStore(path)
    try:
        model = store.model_name
        if model is None:
            raise IndexNotFoundError(
                f"인덱스가 비어 있습니다: {path} — 먼저 `corpbrain scan {out_dir}`을 실행하세요."
            )
        try:
            query_vector = embed(query, model, ollama_url)
        except EmbeddingError as exc:
            raise PreconditionError(f"쿼리 임베딩에 실패했습니다: {exc}") from exc

        graph_path = graph_path_for(out_dir)
        if not graph or not graph_path.exists():
            # 그래프 DB 부재는 정상 응답이다 — 코사인 단독으로 답하고 exit 0 (§5). 이 경로가
            # `--no-graph`와 **같은 한 줄**이라 두 실행의 stdout이 바이트 동일하다 (§3 항목2).
            return store.search(query_vector, top_k)

        # 전 문서를 한 번에 받는다 — `SqliteVectorStore.search()`는 이미 전 행을 채점한 뒤
        # 자르기만 하므로 자르지 않는 것이 I/O도 코사인 계산도 늘리지 않는다. 저장소 계약을
        # 넓히지 않으면서 확산 문서의 코사인·제목·경로를 시드와 같은 출처에서 얻는다 (§4.7 T1).
        ranked = store.search(query_vector, top_k=len(store.list_ids()))
        seeds = ranked[: max(0, top_k)]

        # 조회 전용으로 연다 — 파일에 아무것도 쓰지 않고, 스키마가 소실된 DB를 되만들지
        # 않는다 (v0.6.1 결정 계승). 개봉 실패는 `PreconditionError`로 그대로 올라간다.
        graph_store = SqliteGraphStore(graph_path, read_only=True)
        try:
            edges, labels = _collect_expansion(graph_store, seeds, expand_edges)
        finally:
            graph_store.close()

        return rank_hybrid(
            ranked,
            edges,
            labels=labels,
            expand_edges=expand_edges,
            decay=graph_decay,
            top_k=top_k,
        )
    finally:
        store.close()


def _collect_expansion(
    store: GraphStore,
    seeds: Sequence[SearchResult],
    expand_edges: frozenset[EdgeType],
) -> tuple[list[GraphEdge], dict[str, str]]:
    """시드의 문서 1홉 이웃을 이루는 엣지와 표시 라벨을 모은다 (v0.7 §4.7).

    `GraphStore` 계약(10멤버)을 넓히지 않는다 — 시드에 `neighbors()`, 거기서 얻은 Tag·Entity
    노드에 `neighbors()`, 라벨은 `nodes_of()`. 세 멤버 모두 v0.6이 이미 가진 것이다.

    시드가 그래프 `nodes`에 없으면(패스1과 패스2 사이에서 `scan`이 죽은 경우) 이웃이 0건인
    것과 같아, 그 시드는 확산 없이 코사인 점수 그대로 남는다 — 조용히 처리하며 오류로 만들지
    않는다 (§5).
    """
    edges: list[GraphEdge] = []
    attribute_nodes: dict[str, None] = {}
    for seed in seeds:
        for edge in store.neighbors(seed.doc_id):
            if edge.type not in expand_edges:
                continue
            edges.append(edge)
            if edge.type in _ATTRIBUTE_EDGES and edge.src == seed.doc_id:
                attribute_nodes[edge.dst] = None
    for node_id in attribute_nodes:
        edges.extend(edge for edge in store.neighbors(node_id) if edge.type in expand_edges)

    wanted = {seed.doc_id for seed in seeds}
    for edge in edges:
        wanted.add(edge.src)
        wanted.add(edge.dst)
    # 라벨 선택 규칙은 `build_graph()` 한 곳에만 있고 조회는 저장된 `nodes.label`을 읽는다
    # (v0.6.1 결정 계승) — 위키 「관련 문서」와 검색 결과가 같은 노드를 다르게 표시하지 않는다.
    return edges, {node_id: node.label for node_id, node in store.nodes_of(sorted(wanted)).items()}
