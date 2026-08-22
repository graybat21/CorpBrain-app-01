"""「관련 문서」 계층적 정렬 (v0.6 스펙 §4.5 순위 규칙)."""

from __future__ import annotations

from corpbrain.core.graph import build_graph, rank_related
from corpbrain.core.models import DocFacts, ReferenceDirection

SELF = "/w/self.md"
REF = "/w/ref.md"
SIM_HIGH = "/w/a-sim-high.md"
SIM_LOW = "/w/b-sim-low.md"
ENT = "/w/c-entity.md"
TAG = "/w/d-tag.md"

#: 출력 상대경로 — tie-break(⑤)에 쓴다. 코어는 경로를 만들지 않고 호출자가 넘긴다.
PATHS = {
    SELF: "self.md.md",
    REF: "ref.md.md",
    SIM_HIGH: "a-sim-high.md.md",
    SIM_LOW: "b-sim-low.md.md",
    ENT: "c-entity.md.md",
    TAG: "d-tag.md.md",
}


def _ranked(facts: list[DocFacts], vectors=(), *, top_k: int = 5, threshold: float = 0.75):
    nodes, edges = build_graph(facts, vectors, similarity_threshold=threshold)
    return rank_related(SELF, nodes, edges, relative_paths=PATHS, top_k=top_k)


def test_hierarchical_order_reference_then_similarity_then_entity_then_tag() -> None:
    """①참조 → ②유사도 → ③공유 엔티티 → ④공유 태그 순으로 줄을 세운다."""
    axis = [1.0, 0.0, 0.0]
    near = [0.95, 0.3122498999199199, 0.0]
    mid = [0.80, 0.5999999999999999, 0.0]
    facts = [
        DocFacts(doc_id=SELF, title="본문", tags=["공통태그"], entities=["공통엔티티"], refs=[REF]),
        DocFacts(doc_id=REF, title="참조 대상"),
        DocFacts(doc_id=SIM_HIGH, title="유사 높음"),
        DocFacts(doc_id=SIM_LOW, title="유사 낮음"),
        DocFacts(doc_id=ENT, title="엔티티 공유", entities=["공통엔티티"]),
        DocFacts(doc_id=TAG, title="태그 공유", tags=["공통태그"]),
    ]
    vectors = [(SELF, axis), (SIM_HIGH, near), (SIM_LOW, mid)]

    order = [r.doc_id for r in _ranked(facts, vectors)]

    assert order == [REF, SIM_HIGH, SIM_LOW, ENT, TAG]


def test_reference_beats_higher_similarity() -> None:
    """작성자가 직접 가리킨 문서가 최우선이다 — 유사도가 더 높아도 뒤로 밀리지 않는다."""
    axis = [1.0, 0.0, 0.0]
    facts = [
        DocFacts(doc_id=SELF, title="본문", refs=[REF]),
        DocFacts(doc_id=REF, title="참조 대상"),
        DocFacts(doc_id=SIM_HIGH, title="유사 1.0"),
    ]
    vectors = [(SELF, axis), (SIM_HIGH, axis)]

    order = [r.doc_id for r in _ranked(facts, vectors)]

    assert order[0] == REF


def test_ties_break_by_output_relative_path() -> None:
    """모든 축이 같으면 출력 상대경로 사전순 — 실행마다 순서가 흔들리지 않는다 (⑤)."""
    facts = [
        DocFacts(doc_id=SELF, title="본문", tags=["공통태그"]),
        DocFacts(doc_id=TAG, title="d", tags=["공통태그"]),
        DocFacts(doc_id=ENT, title="c", tags=["공통태그"]),
    ]

    order = [r.doc_id for r in _ranked(facts)]

    # c-entity.md.md < d-tag.md.md
    assert order == [ENT, TAG]


def test_reference_direction_is_reported_for_each_case() -> None:
    facts = [
        DocFacts(doc_id=SELF, title="본문", refs=[REF, SIM_HIGH]),
        DocFacts(doc_id=REF, title="서로", refs=[SELF]),
        DocFacts(doc_id=SIM_HIGH, title="나가는쪽"),
        DocFacts(doc_id=TAG, title="들어오는쪽", refs=[SELF]),
    ]

    directions = {r.doc_id: r.reference for r in _ranked(facts)}

    assert directions[REF] is ReferenceDirection.MUTUAL
    assert directions[SIM_HIGH] is ReferenceDirection.OUTGOING
    assert directions[TAG] is ReferenceDirection.INCOMING


def test_shared_tags_and_entities_are_reported_as_labels() -> None:
    facts = [
        DocFacts(doc_id=SELF, title="본문", tags=["인사"], entities=["인사팀"]),
        DocFacts(doc_id=TAG, title="상대", tags=["인사"], entities=["인사 팀"]),
    ]

    related = _ranked(facts)

    assert len(related) == 1
    assert related[0].shared_tags == ["tag:인사"]
    assert related[0].shared_entities == ["entity:인사팀"]


def test_isolated_document_has_no_related_documents() -> None:
    """고립 문서는 「관련 문서 없음」으로 렌더된다 (§5)."""
    facts = [
        DocFacts(doc_id=SELF, title="고립", tags=["나만의태그"]),
        DocFacts(doc_id=TAG, title="남", tags=["남의태그"]),
    ]

    assert _ranked(facts) == []


def test_top_k_truncates_after_ranking() -> None:
    facts = [
        DocFacts(doc_id=SELF, title="본문", tags=["공통태그"]),
        DocFacts(doc_id=REF, title="1", tags=["공통태그"]),
        DocFacts(doc_id=ENT, title="2", tags=["공통태그"]),
        DocFacts(doc_id=TAG, title="3", tags=["공통태그"]),
    ]

    assert len(_ranked(facts, top_k=2)) == 2
    assert _ranked(facts, top_k=0) == []


def test_self_is_never_related_to_itself() -> None:
    """자기 자신을 향하는 엣지를 만들지 않으므로 목록에도 나타나지 않는다 (§4.1)."""
    axis = [1.0, 0.0, 0.0]
    facts = [DocFacts(doc_id=SELF, title="본문", tags=["t"], refs=[SELF])]

    assert [r.doc_id for r in _ranked(facts, [(SELF, axis)])] == []
