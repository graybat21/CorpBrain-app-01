"""지식그래프 빌더 — 재료(`DocFacts`)와 벡터에서 노드·엣지를 결정적으로 파생한다.

v0.6 스펙 §4.1·§4.3·§5. 이 모듈은 순수 계산만 한다 — 파일도 네트워크도 저장소도 건드리지
않으므로 추가 LLM 호출이 0이고 같은 입력이 항상 같은 그래프를 낸다(§3 항목4).

엣지 4종은 모두 **문서를 한쪽 끝으로** 갖는다. `RELATES_TO`(엔티티↔엔티티)는 비목표다(§2).
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence

from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import (
    DocFacts,
    EdgeType,
    GraphEdge,
    GraphExpansion,
    GraphNode,
    NodeType,
    ReferenceDirection,
    RelatedDocument,
    SearchResult,
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
    """태그·엔티티 노드를 정규화 키로 병합해 만든다.

    여기서 고른 라벨이 `nodes.label`에 그대로 저장되고, `graph` 조회 명령은 그 값을
    `GraphStore.nodes_of()`로 읽는다 (§4.4). 라벨 선택 규칙은 이 함수 하나에만 있다 —
    v0.6.0은 계약에 노드 조회가 없어 조회 어댑터가 같은 규칙을 재구현하고 있었다.
    """
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


# --- v0.7: 하이브리드 검색의 입력 검증 (스펙 §4.1·§4.4·§4.5) --------------------


def validate_graph_decay(decay: float) -> float:
    """감쇠 계수 α가 열린 구간 `0 < α < 1` 안인지 확인하고 그대로 돌려준다 (v0.7 §4.1 · T5).

    검증을 CLI 파서가 아니라 **코어에 두는** 이유는 두 가지다 — 규칙이 한 곳에만 있어야
    코어를 직접 부르는 후속 어댑터(GUI 등)도 같은 보호를 받고, 「확산 문서는 자기 시드를
    추월하지 못한다」(§3 항목4)를 보장하는 성질이 순위 계산과 같은 파일에 놓인다.

    **클램프하지 않는다.** α를 스윕해 효과를 재는 §4.8 측정 절차에서, 조용히 다른 값으로
    바뀐 α는 결과를 설명 불가능하게 만든다.

    Raises:
        PreconditionError: `0 < α < 1` 밖(경계값 0.0·1.0 포함)이거나 NaN.
    """
    if not 0.0 < decay < 1.0:
        raise PreconditionError(
            f"--graph-decay 는 0 과 1 사이여야 합니다 (양 끝 제외): {decay} — "
            f"1 이상이면 확산 문서가 시드를 추월하고, 0 이하면 확산 기여가 사라집니다."
        )
    return decay


def parse_expand_edges(raw: str) -> frozenset[EdgeType]:
    """`--expand-edges` 문자열을 엣지 종류 집합으로 파싱한다 (v0.7 §4.4 · T10).

    파싱도 코어가 맡고 CLI는 문자열을 그대로 넘긴다 — `validate_graph_decay`와 같은 이유다.
    `EdgeType` StrEnum 값을 **그대로** 받고 짧은 별칭을 새로 만들지 않는다. `graph --stats`
    출력·DB의 `type` 컬럼·이 플래그가 한 문자열이어야 어휘가 갈리지 않는다.

    쉼표 주변 공백은 다듬고 중복은 `frozenset`이 흡수한다. 빈 목록은 받아 주지 않는다 —
    확산을 끄는 길은 `--no-graph` 하나여야 §3 항목2·7이 다루는 경로가 갈라지지 않는다.

    Raises:
        PreconditionError: 빈 목록·빈 항목·소문자·목록에 없는 값.
    """
    known = [str(edge_type) for edge_type in EdgeType]
    items = [item.strip() for item in raw.split(",")]
    if not raw.strip():
        raise PreconditionError(
            f"--expand-edges 가 비어 있습니다 — 확산을 끄려면 --no-graph 를 쓰세요. "
            f"쓸 수 있는 값: {', '.join(known)}"
        )
    unknown = [item for item in items if item not in known]
    if unknown:
        raise PreconditionError(
            f"--expand-edges 에 쓸 수 없는 값이 있습니다: {unknown} — "
            f"쓸 수 있는 값: {', '.join(known)} (대소문자를 그대로 씁니다)"
        )
    return frozenset(EdgeType(item) for item in items)


# --- v0.7: 하이브리드 검색의 확산 순위 계산 (스펙 §4.1·§4.3·§4.5) --------------


def rank_hybrid(
    ranked: Sequence[SearchResult],
    edges: Sequence[GraphEdge],
    *,
    labels: Mapping[str, str],
    expand_edges: Collection[EdgeType],
    decay: float,
    top_k: int,
) -> list[SearchResult]:
    """코사인 순위에 그래프 시드 확산을 얹어 재순위화한다 (v0.7 §4.1).

    `rank_related`와 같은 자리에 둔 이유는 **순위 규칙을 계승하기 때문**이다 — 동점 처리는
    v0.6의 계층 정렬 키를 그대로 쓰고 새 상수를 도입하지 않는다(§4.3). 이 함수도 순수
    계산이라 저장소를 열지 않는다. 조회·조립은 `search.py`가 한다.

    Args:
        ranked: 코사인 내림차순 **전 문서**. 앞 `top_k`개가 시드이고, 나머지는 확산 문서의
            자기 코사인·표시 메타데이터를 얻는 데 쓴다. 저장소 계약을 넓히지 않기 위해
            `search(query_vector, top_k=len(list_ids()))`로 한 번에 받아 넘긴다 (§4.7 T1).
        edges: 시드와 그 태그·엔티티 노드의 이웃 엣지를 모은 것. 중복은 여기서 흡수한다.
        labels: 노드 id → 표시 라벨. 저장된 `nodes.label`을 그대로 읽은 값이다.
        expand_edges: 확산에 쓸 엣지 종류. 후보 생성과 근거 계산 **양쪽에** 적용된다 —
            켜지 않은 종류는 조회하지도 않았으므로 근거로도 적지 않는다.
        decay: 감쇠 계수 α. 호출자가 `0 < α < 1`을 이미 검증한 뒤 넘긴다 (§4.5).
        top_k: 시드 개수이자 최종 결과 개수 (§4.4).
    """
    top_k = max(0, top_k)  # 음수 --top-k가 슬라이스를 뒤집지 않도록 방어한다 (v0.4 계승).
    seeds = list(ranked[:top_k])
    if not seeds:
        return []

    by_id = {result.doc_id: result for result in ranked}
    seed_ids = {result.doc_id for result in seeds}
    usable = [edge for edge in edges if edge.type in expand_edges]

    attributes = _attributes_by_document(usable)
    holders = _documents_by_attribute(usable)
    refs = {(edge.src, edge.dst) for edge in usable if edge.type is EdgeType.REFERENCES}
    similar = _similar_documents(usable)

    #: 확산 문서 → 기준 시드. 「가장 높은 점수를 준 시드」이고 동점은 시드 `doc_id` 사전순이다.
    base: dict[str, SearchResult] = {}
    for seed in seeds:
        for candidate in _neighbors_of(seed.doc_id, attributes, holders, refs, similar):
            if candidate in seed_ids:
                continue  # 코사인 top-k로 이미 들어온 문서 — 진입 경로가 시드다 (§4.5)
            current = base.get(candidate)
            if current is None or (-seed.score, seed.doc_id) < (
                -current.score,
                current.doc_id,
            ):
                base[candidate] = seed

    results = list(seeds)
    results += [
        _expanded_result(
            candidate,
            seed,
            by_id=by_id,
            attributes=attributes,
            refs=refs,
            labels=labels,
            decay=decay,
        )
        for candidate, seed in sorted(base.items())
    ]
    results.sort(key=_hybrid_rank_key)
    return results[:top_k]


def _expanded_result(
    doc_id: str,
    seed: SearchResult,
    *,
    by_id: Mapping[str, SearchResult],
    attributes: Mapping[str, tuple[dict[str, None], dict[str, None]]],
    refs: set[tuple[str, str]],
    labels: Mapping[str, str],
    decay: float,
) -> SearchResult:
    """확산 문서 1건의 점수·근거·표시 메타데이터를 조립한다 (§4.1·§4.5)."""
    own = by_id.get(doc_id)
    cosine = own.score if own is not None else None
    score = max(cosine, seed.score * decay) if cosine is not None else seed.score * decay

    mine = attributes.get(doc_id, ({}, {}))
    theirs = attributes.get(seed.doc_id, ({}, {}))
    outgoing = {seed.doc_id} if (doc_id, seed.doc_id) in refs else set()
    incoming = {seed.doc_id} if (seed.doc_id, doc_id) in refs else set()

    if own is not None:
        metadata = own.metadata
    else:
        # 벡터가 없는 확산 문서 — 이 경로에서만 그래프 라벨을 표시에 쓴다 (§4.7).
        metadata = {"title": labels[doc_id]} if doc_id in labels else {}

    return SearchResult(
        doc_id=doc_id,
        score=score,
        metadata=metadata,
        expansion=GraphExpansion(
            seed_doc_id=seed.doc_id,
            seed_title=seed.metadata.get("title") or labels.get(seed.doc_id) or seed.doc_id,
            seed_score=seed.score,
            cosine=cosine,
            shared_tags=sorted(
                labels.get(node_id, node_id) for node_id in mine[0].keys() & theirs[0].keys()
            ),
            shared_entities=sorted(
                labels.get(node_id, node_id) for node_id in mine[1].keys() & theirs[1].keys()
            ),
            reference=_direction(seed.doc_id, outgoing, incoming),
        ),
    )


def _hybrid_rank_key(result: SearchResult) -> tuple[float, int, int, int, float, str]:
    """1차 키는 점수 내림차순, 동점은 v0.6 `rank_related`의 계층 정렬 키를 계승한다 (§4.3).

    마지막 키가 **`doc_id`(원문 절대경로) 사전순**인 것이 `rank_related`(출력 상대경로)와
    다르다 — 조회 시점의 코어는 스캔 루트를 모르고 경로 해석 책임도 지지 않는다. 상대경로를
    얻으려면 검색 1회마다 위키 전체를 열어야 하는데, 동점 처리 하나를 위해 조회 명령의 비용
    성격을 바꾸는 일이다. 같은 스캔 루트의 문서들은 공통 접두사 뒤를 비교하므로 결과가 같다.
    """
    expansion = result.expansion
    if expansion is None:
        # 시드는 진입 경로가 코사인이라 시드와의 관계 자체가 없다 — 관계 축을 전부 0으로 둔다.
        return (-result.score, 1, 0, 0, -result.score, result.doc_id)
    return (
        -result.score,
        0 if expansion.reference is not ReferenceDirection.NONE else 1,
        -len(expansion.shared_entities),
        -len(expansion.shared_tags),
        -expansion.cosine if expansion.cosine is not None else float("inf"),
        result.doc_id,
    )


def _documents_by_attribute(edges: Sequence[GraphEdge]) -> dict[str, dict[str, None]]:
    """태그·엔티티 노드 → 그 노드를 가진 문서들. 삽입 순서를 보존하는 dict를 집합처럼 쓴다."""
    table: dict[str, dict[str, None]] = {}
    for edge in edges:
        if edge.type in (EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY):
            table.setdefault(edge.dst, {})[edge.src] = None
    return table


def _similar_documents(edges: Sequence[GraphEdge]) -> dict[str, dict[str, None]]:
    """유사도 엣지의 이웃 문서. 대칭 엣지는 한 행만 저장되므로 양쪽 끝을 모두 본다 (v0.6 §4.1)."""
    table: dict[str, dict[str, None]] = {}
    for edge in edges:
        if edge.type is EdgeType.SEMANTICALLY_SIMILAR:
            table.setdefault(edge.src, {})[edge.dst] = None
            table.setdefault(edge.dst, {})[edge.src] = None
    return table


def _neighbors_of(
    doc_id: str,
    attributes: Mapping[str, tuple[dict[str, None], dict[str, None]]],
    holders: Mapping[str, dict[str, None]],
    refs: set[tuple[str, str]],
    similar: Mapping[str, dict[str, None]],
) -> list[str]:
    """이 시드의 **문서 1홉** 이웃. 태그·엔티티 노드 경유는 홉으로 세지 않는다 (§4.1).

    확산 방향은 따지지 않는다 — `REFERENCES`가 방향 있는 엣지라도 어느 방향이든 이웃으로
    본다. 방향은 근거 문구에만 반영한다 (§4.2).
    """
    found: dict[str, None] = {}
    tags, entities = attributes.get(doc_id, ({}, {}))
    for node_id in list(tags) + list(entities):
        for other in holders.get(node_id, {}):
            found[other] = None
    for src, dst in refs:
        if src == doc_id:
            found[dst] = None
        elif dst == doc_id:
            found[src] = None
    for other in similar.get(doc_id, {}):
        found[other] = None
    found.pop(doc_id, None)  # 자기 자신은 이웃이 아니다 (§4.2)
    return sorted(found)
