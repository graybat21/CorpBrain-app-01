"""종료 요약의 그래프 줄 (v0.6 스펙 §4.6)."""

from __future__ import annotations

from pathlib import Path

from corpbrain.core.models import (
    GraphOutcome,
    GraphSkipReason,
    GraphStats,
    InjectionFailure,
    ScanResult,
)
from corpbrain.core.report import build_summary_lines

STATS = GraphStats(
    documents=6,
    entities=11,
    tags=6,
    edges_by_type={"TAGGED_WITH": 20, "CONTAINS_ENTITY": 15, "SEMANTICALLY_SIMILAR": 5, "REFERENCES": 1},
)


def _result(graph: GraphOutcome | None) -> ScanResult:
    return ScanResult(out_dir=Path("./corpbrain_wiki"), graph=graph)


def test_no_graph_stage_adds_no_lines() -> None:
    """v0.5까지의 실행과 출력이 같다 — 그래프가 돌지 않으면 아무 줄도 늘지 않는다."""
    lines = build_summary_lines(_result(None))

    assert not any("그래프" in line for line in lines)


def test_stats_line_reports_nodes_by_type_and_edge_total() -> None:
    lines = build_summary_lines(_result(GraphOutcome(stats=STATS)))

    assert "그래프: 노드 23개(문서 6 · 엔티티 11 · 태그 6) / 엣지 41개" in lines


def test_related_updated_count_is_reported_on_its_own_axis() -> None:
    """'스킵 N건'이라고 보고해 놓고 파일 타임스탬프가 바뀌는 상황을 설명한다."""
    lines = build_summary_lines(_result(GraphOutcome(stats=STATS, related_updated_count=4)))

    assert "  - 관련 문서 갱신 4건" in lines


def test_unchanged_related_documents_are_not_reported() -> None:
    lines = build_summary_lines(_result(GraphOutcome(stats=STATS, related_updated_count=0)))

    assert not any("관련 문서 갱신" in line for line in lines)


def test_vectors_unavailable_explains_the_partial_graph() -> None:
    lines = build_summary_lines(
        _result(
            GraphOutcome(stats=STATS, similarity_skipped=GraphSkipReason.VECTORS_UNAVAILABLE)
        )
    )

    assert any("유사도 엣지 생략" in line for line in lines)


def test_facts_missing_points_at_the_force_rescan() -> None:
    lines = build_summary_lines(_result(GraphOutcome(stats=STATS, facts_missing_count=2)))

    assert any("엔티티 없는 기존 위키 2건" in line and "--force" in line for line in lines)


def test_build_failure_says_the_previous_graph_survived() -> None:
    """트랜잭션이라 이전 그래프가 남아 있다는 사실이 사용자에게 보여야 한다 (§5)."""
    lines = build_summary_lines(
        _result(
            GraphOutcome(
                similarity_skipped=GraphSkipReason.BUILD_FAILED,
                build_failure="database or disk is full",
            )
        )
    )

    assert any("그래프 갱신 실패" in line and "이전 그래프를 유지" in line for line in lines)
    # 빌드가 실패했으므로 통계 줄은 내지 않는다.
    assert not any(line.startswith("그래프: 노드") for line in lines)


def test_injection_failures_are_listed_with_path_and_reason() -> None:
    lines = build_summary_lines(
        _result(
            GraphOutcome(
                stats=STATS,
                injection_failures=[
                    InjectionFailure(path=Path("/w/개발/설계.md.md"), detail="권한 거부")
                ],
            )
        )
    )

    assert any("주입 실패" in line and "권한 거부" in line for line in lines)


def test_graph_lines_come_before_the_output_path() -> None:
    lines = build_summary_lines(_result(GraphOutcome(stats=STATS)))

    assert lines[-1].startswith("출력 경로:")
