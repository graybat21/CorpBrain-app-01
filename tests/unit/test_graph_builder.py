"""그래프 빌더 — 정규화·4종 엣지·경계 조건 (v0.6 스펙 §4.1 · §4.3 · §5)."""

from __future__ import annotations

import math

from corpbrain.core.graph import (
    build_graph,
    choose_label,
    extract_references,
    normalize_key,
)
from corpbrain.core.models import DocFacts, EdgeType, NodeType

A = "/work/인사/채용계획.docx"
B = "/work/인사/온보딩.md"
C = "/work/개발/아키텍처.md"

#: 대칭 엣지는 `src < dst`로 정렬돼 저장된다. 유니코드 순서상 B < A 이므로 상수 이름의
#: 알파벳 순서와 다르다 — 기대값을 눈으로 짐작하지 않고 정렬로 만든다.
def _pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _edges(edges: list, edge_type: EdgeType) -> list[tuple[str, str]]:
    return [(e.src, e.dst) for e in edges if e.type == edge_type]


# --- 정규화 -------------------------------------------------------------------


def test_normalize_key_removes_all_whitespace_and_case() -> None:
    """한국어 문서에서 가장 흔한 분할인 내부 공백을 합친다 (§4.3)."""
    assert normalize_key("인사팀") == normalize_key("인사 팀") == normalize_key(" 인사  팀 ")
    assert normalize_key("Greeting ATS") == normalize_key("greetingats")


def test_choose_label_prefers_most_common_then_lexicographic() -> None:
    assert choose_label(["인사팀", "인사 팀", "인사팀"]) == "인사팀"
    # 동점이면 사전순 — 실행마다 라벨이 흔들리지 않게 한다.
    assert choose_label(["인사 팀", "인사팀"]) == "인사 팀"


def test_entity_variants_merge_into_one_node() -> None:
    """완료의 정의 7번: `인사팀`과 `인사 팀`이 단일 Entity 노드로 병합된다."""
    nodes, edges = build_graph(
        [
            DocFacts(doc_id=A, title="A", entities=["인사팀"]),
            DocFacts(doc_id=B, title="B", entities=["인사 팀"]),
        ],
        similarity_threshold=0.75,
    )

    entities = [n for n in nodes if n.type == NodeType.ENTITY]
    assert len(entities) == 1
    assert len(_edges(edges, EdgeType.CONTAINS_ENTITY)) == 2


# --- 참조 추출 ----------------------------------------------------------------


def test_extract_references_matches_filename_with_extension() -> None:
    text = "채용 일정은 채용계획.docx 를 참조하십시오."

    assert extract_references(text, [A, B, C], self_id=B) == [A]


def test_extract_references_skips_self_reference() -> None:
    """자기 파일명을 언급하는 문서는 흔하다 — 자기 루프는 만들지 않는다 (§4.1)."""
    text = "이 파일(온보딩.md)은 신규 입사자를 위한 안내다."

    assert extract_references(text, [A, B, C], self_id=B) == []


def test_extract_references_skips_ambiguous_duplicate_filenames() -> None:
    """동명 파일이 여럿이면 대상이 모호하므로 만들지 않는다 (§5)."""
    dup1 = "/work/인사/README.md"
    dup2 = "/work/개발/README.md"
    text = "자세한 내용은 README.md 참조."

    assert extract_references(text, [dup1, dup2, A], self_id=A) == []


def test_extract_references_ignores_extensionless_partial_match() -> None:
    text = "채용계획 문서를 보라."  # 확장자가 없다

    assert extract_references(text, [A, B], self_id=B) == []


# --- 4종 엣지 -----------------------------------------------------------------


def test_tagged_with_and_contains_entity_edges() -> None:
    nodes, edges = build_graph(
        [
            DocFacts(doc_id=A, title="A", tags=["채용", "인사"], entities=["인사팀"]),
            DocFacts(doc_id=B, title="B", tags=["인사"], entities=["인사팀"]),
        ],
        similarity_threshold=0.75,
    )

    assert sorted(_edges(edges, EdgeType.TAGGED_WITH)) == sorted(
        [(A, "tag:인사"), (A, "tag:채용"), (B, "tag:인사")]
    )
    assert sorted(_edges(edges, EdgeType.CONTAINS_ENTITY)) == sorted(
        [(A, "entity:인사팀"), (B, "entity:인사팀")]
    )
    assert {n.id for n in nodes if n.type == NodeType.TAG} == {"tag:인사", "tag:채용"}


def test_reference_edges_keep_both_directions() -> None:
    """방향이 작성자의 의도를 담으므로 병합하지 않는다 (§4.1)."""
    _nodes, edges = build_graph(
        [
            DocFacts(doc_id=A, title="A", refs=[B]),
            DocFacts(doc_id=B, title="B", refs=[A]),
        ],
        similarity_threshold=0.75,
    )

    assert sorted(_edges(edges, EdgeType.REFERENCES)) == sorted([(A, B), (B, A)])


def test_reference_to_unknown_document_is_dropped() -> None:
    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A", refs=["/work/삭제된문서.md"])],
        similarity_threshold=0.75,
    )

    assert _edges(edges, EdgeType.REFERENCES) == []


# --- 유사도 경계 --------------------------------------------------------------


def _unit(first: float) -> list[float]:
    """첫 성분이 기준축과의 코사인이 되는 단위벡터."""
    return [first, math.sqrt(max(0.0, 1.0 - first * first)), 0.0]


AXIS = [1.0, 0.0, 0.0]


def test_similarity_edge_is_inclusive_at_the_threshold() -> None:
    """`>=` 비교 — 임계치와 정확히 같은 쌍도 엣지를 만든다 (§4.1).

    벡터에서 코사인을 역산하면 부동소수 오차가 남으므로, 임계치를 **실측값**으로 준다.
    검증 대상은 "값이 무엇이냐"가 아니라 "같은 값일 때 포함하느냐"다.
    """
    from corpbrain.core.vectorstore import cosine_similarity

    vectors = [(A, AXIS), (B, _unit(0.75))]
    exact = cosine_similarity(AXIS, _unit(0.75))

    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A"), DocFacts(doc_id=B, title="B")],
        vectors,
        similarity_threshold=exact,
    )

    assert _edges(edges, EdgeType.SEMANTICALLY_SIMILAR) == [_pair(A, B)]


def test_similarity_edge_is_dropped_below_the_threshold() -> None:
    vectors = [(A, AXIS), (B, _unit(0.30))]

    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A"), DocFacts(doc_id=B, title="B")],
        vectors,
        similarity_threshold=0.75,
    )

    assert _edges(edges, EdgeType.SEMANTICALLY_SIMILAR) == []


def test_similarity_edge_is_stored_once_with_sorted_endpoints() -> None:
    """대칭 엣지는 `src < dst` 한 행만 — `--stats`가 사람이 세는 관계 수와 일치한다 (§4.1)."""
    vectors = [(B, AXIS), (A, AXIS)]  # 입력 순서를 뒤집어도 결과가 같아야 한다

    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A"), DocFacts(doc_id=B, title="B")],
        vectors,
        similarity_threshold=0.75,
    )

    similar = _edges(edges, EdgeType.SEMANTICALLY_SIMILAR)
    assert similar == [_pair(A, B)]
    assert similar[0][0] < similar[0][1]


def test_identical_content_in_separate_files_still_gets_an_edge() -> None:
    """제외 판정은 유사도 값이 아니라 `doc_id` 동일성이다 (§4.1).

    내용이 같은 별개 파일은 코사인이 1.0이어도 서로 다른 문서이므로 엣지를 가져야 한다.
    """
    vectors = [(A, AXIS), (B, AXIS)]

    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A"), DocFacts(doc_id=B, title="B")],
        vectors,
        similarity_threshold=0.75,
    )

    similar = [e for e in edges if e.type == EdgeType.SEMANTICALLY_SIMILAR]
    assert len(similar) == 1
    assert similar[0].weight == 1.0


def test_no_vectors_yields_partial_graph_without_similarity_edges() -> None:
    """벡터가 없어도 나머지 3종은 정상 생성된다 — 분기 없이 부분 그래프 (§5)."""
    _nodes, edges = build_graph(
        [
            DocFacts(doc_id=A, title="A", tags=["인사"], entities=["인사팀"], refs=[B]),
            DocFacts(doc_id=B, title="B", tags=["인사"]),
        ],
        similarity_threshold=0.75,
    )

    assert _edges(edges, EdgeType.SEMANTICALLY_SIMILAR) == []
    assert _edges(edges, EdgeType.TAGGED_WITH)
    assert _edges(edges, EdgeType.CONTAINS_ENTITY)
    assert _edges(edges, EdgeType.REFERENCES)


def test_vectors_for_unknown_documents_are_ignored() -> None:
    """위키가 사라진 문서의 고아 벡터가 유령 엣지를 만들지 않는다."""
    vectors = [(A, AXIS), ("/work/삭제됨.txt", AXIS)]

    _nodes, edges = build_graph(
        [DocFacts(doc_id=A, title="A")], vectors, similarity_threshold=0.75
    )

    assert _edges(edges, EdgeType.SEMANTICALLY_SIMILAR) == []


def test_build_graph_is_deterministic_regardless_of_input_order() -> None:
    """같은 입력이면 같은 그래프 — §3 항목4의 토대."""
    facts = [
        DocFacts(doc_id=C, title="C", tags=["설계"]),
        DocFacts(doc_id=A, title="A", tags=["인사", "채용"]),
        DocFacts(doc_id=B, title="B", tags=["인사"], refs=[A]),
    ]
    first = build_graph(facts, similarity_threshold=0.75)
    second = build_graph(list(reversed(facts)), similarity_threshold=0.75)

    assert first == second
