"""지식그래프 빌더 — 재료(`DocFacts`)와 벡터에서 노드·엣지를 결정적으로 파생한다.

v0.6 스펙 §4.1·§4.3·§5. 이 모듈은 순수 계산만 한다 — 파일도 네트워크도 저장소도 건드리지
않으므로 추가 LLM 호출이 0이고 같은 입력이 항상 같은 그래프를 낸다(§3 항목4).

엣지 4종은 모두 **문서를 한쪽 끝으로** 갖는다. `RELATES_TO`(엔티티↔엔티티)는 비목표다(§2).
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from corpbrain.core.models import (
    DocFacts,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    ReferenceDirection,
    RelatedDocument,
)
from corpbrain.core.vectorstore import cosine_similarity

#: 노드 id 접두사 — 타입 접두사로 문서 절대경로와 충돌하지 않는다 (§4.1).
ENTITY_PREFIX = "entity:"
TAG_PREFIX = "tag:"


def normalize_key(name: str) -> str:
    """엔티티·태그를 병합할 정규화 키 (§4.3).

    유니코드 NFC + 소문자화 + **모든 공백 제거**. `인사팀`과 `인사 팀`이 한 노드로 합쳐진다 —
    한국어 문서에서 가장 흔한 분할이다. 동의어 병합(`인사팀` = `HR팀`)은 비목표다(§2).
    """
    folded = unicodedata.normalize("NFC", name).lower()
    return "".join(folded.split())


def choose_label(variants: Iterable[str]) -> str:
    """같은 키로 합쳐진 표기들 중 표시 라벨을 고른다 — 최다 등장 형태, 동점은 사전순 (§4.3)."""
    counts = Counter(v.strip() for v in variants if v.strip())
    if not counts:
        return ""
    top = max(counts.values())
    return min(name for name, count in counts.items() if count == top)


def extract_references(text: str, doc_ids: Iterable[str], *, self_id: str) -> list[str]:
    """대상 텍스트에서 다른 문서의 파일명을 찾아 `doc_id` 목록으로 돌려준다 (§5).

    **모호하면 만들지 않는다.** 확장자를 포함한 파일명이 정확히 등장할 때만 인정하고,
    같은 파일명을 가진 문서가 둘 이상이면 어느 쪽인지 정할 수 없으므로 건너뛴다.
    자기 자신을 향하는 참조도 만들지 않는다 — 자기 파일명을 본문에서 언급하는 문서
    (`README.md`가 "이 파일(README.md)은…"이라고 쓰는 경우)는 실제로 흔하고, 자기 루프는
    어느 엣지 종류에서도 정보가 없다 (§4.1).

    Args:
        text: 요약 입력으로 이미 읽어 둔 텍스트(`--max-chars`까지). 이 절단 이후에 등장하는
            참조는 잡히지 않는 것이 알려진 한계다 (§5).
        doc_ids: 스캔 대상 문서의 `doc_id`(원문 절대경로) 전체.
        self_id: 이 텍스트를 낸 문서의 `doc_id`.
    """
    by_name: dict[str, list[str]] = {}
    for doc_id in doc_ids:
        by_name.setdefault(doc_id.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], []).append(doc_id)

    found: list[str] = []
    for filename, owners in sorted(by_name.items()):
        if len(owners) != 1:
            continue  # 동명 파일이 여럿 — 대상이 모호하므로 엣지를 만들지 않는다
        target = owners[0]
        if target == self_id:
            continue
        if filename in text:
            found.append(target)
    return found


def build_graph(
    facts: Sequence[DocFacts],
    vectors: Iterable[tuple[str, list[float]]] = (),
    *,
    similarity_threshold: float,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """재료와 벡터에서 노드·엣지 전체를 파생한다 (§4.1).

    벡터가 비어 있으면 `SEMANTICALLY_SIMILAR`만 빠지고 나머지 3종은 정상 생성된다 —
    부분 그래프가 분기 없이 성립한다 (§5).
    """
    documents = {f.doc_id: f for f in facts}
    nodes: list[GraphNode] = [
        GraphNode(id=f.doc_id, type=NodeType.DOCUMENT, label=f.title or f.doc_id)
        for f in sorted(facts, key=lambda f: f.doc_id)
    ]
    edges: list[GraphEdge] = []

    nodes.extend(
        _attribute_nodes(facts, attribute="tags", prefix=TAG_PREFIX, node_type=NodeType.TAG)
    )
    nodes.extend(
        _attribute_nodes(
            facts, attribute="entities", prefix=ENTITY_PREFIX, node_type=NodeType.ENTITY
        )
    )
    edges.extend(
        _attribute_edges(facts, attribute="tags", prefix=TAG_PREFIX, edge_type=EdgeType.TAGGED_WITH)
    )
    edges.extend(
        _attribute_edges(
            facts,
            attribute="entities",
            prefix=ENTITY_PREFIX,
            edge_type=EdgeType.CONTAINS_ENTITY,
        )
    )
    edges.extend(_reference_edges(facts, known=documents.keys()))
    edges.extend(
        _similarity_edges(
            vectors, known=documents.keys(), similarity_threshold=similarity_threshold
        )
    )
    return nodes, edges


def _attribute_nodes(
    facts: Sequence[DocFacts], *, attribute: str, prefix: str, node_type: NodeType
) -> list[GraphNode]:
    """태그·엔티티 노드를 정규화 키로 병합해 만든다."""
    variants: dict[str, list[str]] = {}
    for doc in facts:
        for raw in getattr(doc, attribute):
            key = normalize_key(raw)
            if key:
                variants.setdefault(key, []).append(raw)
    return [
        GraphNode(id=f"{prefix}{key}", type=node_type, label=choose_label(names))
        for key, names in sorted(variants.items())
    ]


def _attribute_edges(
    facts: Sequence[DocFacts], *, attribute: str, prefix: str, edge_type: EdgeType
) -> list[GraphEdge]:
    seen: set[tuple[str, str]] = set()
    edges: list[GraphEdge] = []
    for doc in sorted(facts, key=lambda f: f.doc_id):
        for key in sorted({normalize_key(raw) for raw in getattr(doc, attribute)}):
            if not key:
                continue
            pair = (doc.doc_id, f"{prefix}{key}")
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(GraphEdge(src=pair[0], dst=pair[1], type=edge_type))
    return edges


def _reference_edges(facts: Sequence[DocFacts], *, known: Iterable[str]) -> list[GraphEdge]:
    """`REFERENCES`는 4종 중 유일하게 방향이 작성자의 의도를 담으므로 두 방향을 모두 남긴다."""
    known_ids = set(known)
    edges: list[GraphEdge] = []
    for doc in sorted(facts, key=lambda f: f.doc_id):
        for target in sorted(set(doc.refs)):
            if target == doc.doc_id or target not in known_ids:
                continue
            edges.append(GraphEdge(src=doc.doc_id, dst=target, type=EdgeType.REFERENCES))
    return edges


def _similarity_edges(
    vectors: Iterable[tuple[str, list[float]]],
    *,
    known: Iterable[str],
    similarity_threshold: float,
) -> list[GraphEdge]:
    """전 쌍 코사인 — `>=` 비교, 자기 자신 제외, `src < dst` 한 행만 (§4.1)."""
    known_ids = set(known)
    usable: Mapping[str, list[float]] = {
        doc_id: vector for doc_id, vector in vectors if doc_id in known_ids
    }
    ordered = sorted(usable)
    edges: list[GraphEdge] = []
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            # `i < j` 조합이라 같은 쌍을 두 방향으로 계산하지 않는다. 자기 자신은 이 조합에서
            # 애초에 나오지 않으며, 제외 판정은 유사도 값이 아니라 doc_id 동일성이다 —
            # 내용이 같은 별개 파일은 코사인이 1.0이어도 정상적으로 엣지를 가져야 한다.
            if len(usable[left]) != len(usable[right]):
                continue  # 다른 차원으로 저장된 벡터는 비교가 무의미하다
            score = cosine_similarity(usable[left], usable[right])
            if score >= similarity_threshold:
                edges.append(
                    GraphEdge(
                        src=left,
                        dst=right,
                        type=EdgeType.SEMANTICALLY_SIMILAR,
                        weight=score,
                    )
                )
    return edges


def rank_related(
    doc_id: str,
    nodes: Sequence[GraphNode],
    edges: Sequence[GraphEdge],
    *,
    relative_paths: Mapping[str, str],
    top_k: int,
) -> list[RelatedDocument]:
    """한 문서의 「관련 문서」를 계층적 정렬로 상위 `top_k`개 고른다 (§4.5).

    가중합을 쓰지 않는다 — 가중치를 임의로 정해야 하고 부동소수 비교가 생긴다. 대신 축을
    우선순위대로 훑는다:

    1. `REFERENCES` 관계가 있는 문서 (방향 무관 — 작성자가 직접 가리켰다)
    2. 유사도 내림차순
    3. 공유 엔티티 수 내림차순
    4. 공유 태그 수 내림차순
    5. 동점은 **출력 상대경로 사전순** (tie-break, 실행마다 순서가 흔들리지 않게 한다)

    Args:
        relative_paths: `doc_id` → `--out` 기준 위키 상대경로. 5번 tie-break에 쓴다.
            코어는 경로를 만들지 않으므로 호출자가 넘긴다.
    """
    labels = {n.id: n.label for n in nodes}
    attributes = _attributes_by_document(edges)
    similarity, outgoing, incoming = _relations_of(doc_id, edges)

    mine = attributes.get(doc_id, ({}, {}))
    candidates = set(similarity) | outgoing | incoming
    candidates |= _documents_sharing_attributes(doc_id, attributes, mine)
    candidates.discard(doc_id)

    related = [
        RelatedDocument(
            doc_id=other,
            title=labels.get(other, other),
            similarity=similarity.get(other),
            shared_tags=sorted(
                labels.get(node_id, node_id)
                for node_id in mine[0].keys() & attributes.get(other, ({}, {}))[0].keys()
            ),
            shared_entities=sorted(
                labels.get(node_id, node_id)
                for node_id in mine[1].keys() & attributes.get(other, ({}, {}))[1].keys()
            ),
            reference=_direction(other, outgoing, incoming),
        )
        for other in candidates
    ]
    related.sort(key=lambda r: _rank_key(r, relative_paths))
    return related[: max(0, top_k)]


def _rank_key(
    related: RelatedDocument, relative_paths: Mapping[str, str]
) -> tuple[int, float, int, int, str]:
    return (
        0 if related.reference is not ReferenceDirection.NONE else 1,
        -related.similarity if related.similarity is not None else float("inf"),
        -len(related.shared_entities),
        -len(related.shared_tags),
        relative_paths.get(related.doc_id, related.doc_id),
    )


def _direction(
    other: str, outgoing: set[str], incoming: set[str]
) -> ReferenceDirection:
    if other in outgoing and other in incoming:
        return ReferenceDirection.MUTUAL
    if other in outgoing:
        return ReferenceDirection.OUTGOING
    if other in incoming:
        return ReferenceDirection.INCOMING
    return ReferenceDirection.NONE


def _attributes_by_document(
    edges: Sequence[GraphEdge],
) -> dict[str, tuple[dict[str, None], dict[str, None]]]:
    """문서별 (태그 노드 집합, 엔티티 노드 집합). 삽입 순서를 보존하는 dict를 집합처럼 쓴다."""
    table: dict[str, tuple[dict[str, None], dict[str, None]]] = {}
    for edge in edges:
        if edge.type is EdgeType.TAGGED_WITH:
            table.setdefault(edge.src, ({}, {}))[0][edge.dst] = None
        elif edge.type is EdgeType.CONTAINS_ENTITY:
            table.setdefault(edge.src, ({}, {}))[1][edge.dst] = None
    return table


def _relations_of(
    doc_id: str, edges: Sequence[GraphEdge]
) -> tuple[dict[str, float], set[str], set[str]]:
    similarity: dict[str, float] = {}
    outgoing: set[str] = set()
    incoming: set[str] = set()
    for edge in edges:
        if edge.type is EdgeType.SEMANTICALLY_SIMILAR and edge.weight is not None:
            # 대칭 엣지는 한 행만 저장되므로 양쪽 끝을 모두 본다 (§4.1).
            if edge.src == doc_id:
                similarity[edge.dst] = edge.weight
            elif edge.dst == doc_id:
                similarity[edge.src] = edge.weight
        elif edge.type is EdgeType.REFERENCES:
            if edge.src == doc_id:
                outgoing.add(edge.dst)
            elif edge.dst == doc_id:
                incoming.add(edge.src)
    return similarity, outgoing, incoming


def _documents_sharing_attributes(
    doc_id: str,
    attributes: Mapping[str, tuple[dict[str, None], dict[str, None]]],
    mine: tuple[dict[str, None], dict[str, None]],
) -> set[str]:
    return {
        other
        for other, (tags, entities) in attributes.items()
        if other != doc_id and (tags.keys() & mine[0].keys() or entities.keys() & mine[1].keys())
    }


def label_index(facts: Sequence[DocFacts]) -> dict[str, str]:
    """노드 id → 표시 라벨 (v0.6 §4.3).

    `GraphStore` 계약(§4.4)에는 노드 조회가 없다 — `neighbors()`는 엣지만, `degree_ranking()`은
    `(id, 차수)`만 돌려준다. 라벨은 `nodes` 테이블에 있지만 계약을 통해 닿을 수 없으므로,
    조회 어댑터가 `iter_facts()`로 얻은 재료에서 `build_graph()`와 **같은 규칙으로** 다시
    만든다. 규칙을 공유하므로 위키 「관련 문서」에 찍힌 라벨과 `graph` 출력이 어긋나지 않는다.
    """
    labels = {f.doc_id: (f.title or f.doc_id) for f in facts}
    for attribute, prefix, node_type in (
        ("tags", TAG_PREFIX, NodeType.TAG),
        ("entities", ENTITY_PREFIX, NodeType.ENTITY),
    ):
        for node in _attribute_nodes(facts, attribute=attribute, prefix=prefix, node_type=node_type):
            labels[node.id] = node.label
    return labels
