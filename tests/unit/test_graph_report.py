"""`graph` 조회 출력 빌더 (v0.6 스펙 §4.7).

정확 문자열 단언은 이 파일이 한다 — 완료의 정의 3번이 "출력의 개수가 DB 실측과 일치"를
요구하므로 느슨한 부분 매칭으로는 부족하다. CLI 테스트는 종료 코드와 배선만 본다.
"""

from __future__ import annotations

from corpbrain.core.models import EdgeType, GraphEdge, GraphStats
from corpbrain.core.report import (
    build_graph_central_lines,
    build_graph_neighbors_lines,
    build_graph_stats_lines,
)

A = "/work/인사/채용계획.docx"
B = "/work/인사/온보딩.md"
LABELS = {
    A: "2026년도 신입 채용 계획",
    B: "신입사원 온보딩 가이드",
    "tag:인사": "인사",
    "entity:인사팀": "인사팀",
}


# --- --stats -------------------------------------------------------------------


def test_stats_lines_report_counts_by_type() -> None:
    stats = GraphStats(
        documents=6,
        entities=11,
        tags=6,
        edges_by_type={
            "TAGGED_WITH": 20,
            "CONTAINS_ENTITY": 15,
            "SEMANTICALLY_SIMILAR": 5,
            "REFERENCES": 1,
        },
    )

    assert build_graph_stats_lines(stats) == [
        "노드 23개  문서 6 · 엔티티 11 · 태그 6",
        "엣지 41개  TAGGED_WITH 20 · CONTAINS_ENTITY 15 · SEMANTICALLY_SIMILAR 5 · REFERENCES 1",
    ]


def test_stats_lines_keep_the_same_shape_for_an_empty_graph() -> None:
    """빈 그래프도 줄 수가 흔들리지 않는다 — 눈으로도 스크립트로도 비교하기 쉽다."""
    lines = build_graph_stats_lines(GraphStats())

    assert lines == [
        "노드 0개  문서 0 · 엔티티 0 · 태그 0",
        "엣지 0개  TAGGED_WITH 0 · CONTAINS_ENTITY 0 · SEMANTICALLY_SIMILAR 0 · REFERENCES 0",
    ]


def test_stats_edge_order_follows_edge_type_declaration() -> None:
    lines = build_graph_stats_lines(GraphStats(edges_by_type={"REFERENCES": 1}))

    positions = [lines[1].index(kind.value) for kind in EdgeType]
    assert positions == sorted(positions)


# --- --neighbors ---------------------------------------------------------------


def test_neighbors_lines_cover_all_four_edge_kinds() -> None:
    edges = [
        GraphEdge(src=A, dst="tag:인사", type=EdgeType.TAGGED_WITH),
        GraphEdge(src=A, dst="entity:인사팀", type=EdgeType.CONTAINS_ENTITY),
        GraphEdge(src=B, dst=A, type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.8123),
        GraphEdge(src=A, dst=B, type=EdgeType.REFERENCES),
    ]

    lines = build_graph_neighbors_lines(A, edges, labels=LABELS)

    assert lines[0] == f"2026년도 신입 채용 계획  —  {A}"
    assert lines[1:] == [
        "  TAGGED_WITH                 인사",
        "  CONTAINS_ENTITY             인사팀",
        f"  SEMANTICALLY_SIMILAR  0.81  신입사원 온보딩 가이드  ({B})",
        f"  REFERENCES →                신입사원 온보딩 가이드  ({B})",
    ]
    # 종류 열이 같은 자리에서 시작해 눈으로 훑을 수 있다.
    assert {len(line) - len(line.lstrip()) for line in lines[1:]} == {2}


def test_incoming_and_outgoing_references_are_distinguished() -> None:
    """`REFERENCES`만 방향이 작성자의 의도를 담는다 (§4.1)."""
    edges = [
        GraphEdge(src=A, dst=B, type=EdgeType.REFERENCES),
        GraphEdge(src=B, dst=A, type=EdgeType.REFERENCES),
    ]

    lines = build_graph_neighbors_lines(A, edges, labels=LABELS)

    assert any("REFERENCES →" in line for line in lines)
    assert any("REFERENCES ←" in line for line in lines)


def test_symmetric_edge_is_read_from_either_end() -> None:
    """대칭 엣지는 `src < dst` 한 행만 저장되므로 반대편에서도 상대가 보여야 한다 (§4.1)."""
    edge = GraphEdge(src=B, dst=A, type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.9)

    from_a = build_graph_neighbors_lines(A, [edge], labels=LABELS)
    from_b = build_graph_neighbors_lines(B, [edge], labels=LABELS)

    assert "신입사원 온보딩 가이드" in from_a[1]
    assert "2026년도 신입 채용 계획" in from_b[1]


def test_document_neighbors_carry_their_doc_id_for_copy_paste() -> None:
    """출력의 문서 경로를 그대로 `--neighbors`에 넣을 수 있어야 한다 (§4.7 절대경로 허용)."""
    edges = [GraphEdge(src=A, dst=B, type=EdgeType.REFERENCES)]

    lines = build_graph_neighbors_lines(A, edges, labels=LABELS)

    assert f"({B})" in lines[1]


def test_attribute_neighbors_show_only_the_label() -> None:
    """태그·엔티티는 정규화 키를 노출하지 않는다 — 사람이 읽을 값만 낸다."""
    edges = [GraphEdge(src=A, dst="tag:인사", type=EdgeType.TAGGED_WITH)]

    lines = build_graph_neighbors_lines(A, edges, labels=LABELS)

    assert lines[1].endswith("인사")
    assert "tag:" not in lines[1]


def test_isolated_document_says_so_instead_of_printing_nothing() -> None:
    lines = build_graph_neighbors_lines(A, [], labels=LABELS)

    assert len(lines) == 2
    assert "연결된 문서·태그·엔티티가 없습니다" in lines[1]


# --- --central -----------------------------------------------------------------


def test_central_lines_are_degree_descending() -> None:
    lines = build_graph_central_lines([(A, 4), (B, 2)], labels=LABELS)

    assert lines == [
        f"    4  2026년도 신입 채용 계획  ({A})",
        f"    2  신입사원 온보딩 가이드  ({B})",
    ]


def test_central_lines_on_an_empty_graph_are_a_normal_answer() -> None:
    """빈 결과는 오류가 아니다 — `graph --central`은 exit 0이다 (§4.7)."""
    assert build_graph_central_lines([], labels={}) == ["그래프에 문서가 없습니다."]


def test_missing_label_falls_back_to_the_node_id() -> None:
    """표시가 실패를 가리지 않게 한다 — 라벨이 없어도 식별자는 보인다."""
    lines = build_graph_central_lines([("/work/알수없음.txt", 1)], labels={})

    assert "/work/알수없음.txt" in lines[0]
