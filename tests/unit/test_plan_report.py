"""pre-scan 리포트·배너 순수 렌더러 단위테스트 (U4 / 스펙 §4.3)."""

from __future__ import annotations

from pathlib import Path

from corpbrain.core.models import HardwareInfo, PlanEntry, ScanPlan
from corpbrain.core.report import (
    PLAN_REPORT_TOP_N,
    build_plan_report_lines,
    build_scan_banner_lines,
)

CPU = HardwareInfo(gpu=False, label="CPU")
GPU = HardwareInfo(gpu=True, label="GPU: NVIDIA GeForce RTX 4090")


def _entry(name: str, importance: int, est_tokens: int = 10, ext: str = ".txt") -> PlanEntry:
    return PlanEntry(
        path=Path(name), ext=ext, size_bytes=100, est_tokens=est_tokens, importance=importance
    )


def _plan(
    entries: list[PlanEntry], hardware: HardwareInfo = CPU, est_seconds: int = 0
) -> ScanPlan:
    return ScanPlan(
        entries=entries,
        file_count=len(entries),
        total_est_tokens=sum(entry.est_tokens for entry in entries),
        est_seconds=est_seconds,
        hardware=hardware,
    )


def _rows(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith("  [")]


# --- plan 리포트 (stdout) -------------------------------------------------------


def test_plan_report_ranks_by_importance_desc() -> None:
    plan = _plan([_entry("low.txt", 10), _entry("high.pdf", 90), _entry("mid.md", 50)])

    rows = _rows(build_plan_report_lines(plan, max_files=50))

    assert [line.split("] ")[1].split("  ")[0] for line in rows] == [
        "high.pdf",
        "mid.md",
        "low.txt",
    ]


def test_plan_report_truncates_to_top_n_and_shows_remainder() -> None:
    entries = [_entry(f"f{index:02d}.txt", importance=index) for index in range(25)]
    lines = build_plan_report_lines(_plan(entries), max_files=50)

    assert len(_rows(lines)) == PLAN_REPORT_TOP_N
    assert any(line == f"  …외 {25 - PLAN_REPORT_TOP_N}건" for line in lines)


def test_plan_report_summary_reports_counts_tokens_and_time() -> None:
    entries = [_entry("a.txt", 40, est_tokens=600), _entry("b.pdf", 60, est_tokens=650)]
    lines = build_plan_report_lines(_plan(entries, est_seconds=125), max_files=50)

    summary = next(line for line in lines if line.startswith("합계:"))
    assert "2개 파일" in summary
    assert "1,250" in summary  # 총 토큰 (천단위 콤마)
    assert "2분 5초" in summary  # 125초 근사


def test_plan_report_includes_hardware_label() -> None:
    lines = build_plan_report_lines(_plan([_entry("a.txt", 40)], hardware=GPU), max_files=50)

    assert any("감지 하드웨어: GPU: NVIDIA GeForce RTX 4090" in line for line in lines)


def test_plan_report_warns_when_discovered_exceeds_max() -> None:
    entries = [_entry(f"f{i}.txt", 40) for i in range(5)]
    lines = build_plan_report_lines(_plan(entries), max_files=3)

    assert any(line.startswith("경고:") and "--max(3)" in line for line in lines)


def test_plan_report_has_no_warning_within_max() -> None:
    entries = [_entry(f"f{i}.txt", 40) for i in range(3)]
    lines = build_plan_report_lines(_plan(entries), max_files=50)

    assert not any(line.startswith("경고:") for line in lines)


def test_plan_report_handles_empty_plan() -> None:
    lines = build_plan_report_lines(_plan([]), max_files=50)

    assert _rows(lines) == []
    assert any("0개 파일" in line for line in lines)


# --- scan 시작 배너 (stderr) ----------------------------------------------------


def test_scan_banner_shows_top3_names_in_importance_order() -> None:
    entries = [
        _entry("d.txt", 10),
        _entry("a.pdf", 95),
        _entry("b.md", 70),
        _entry("c.docx", 40),
    ]
    lines = build_scan_banner_lines(_plan(entries, est_seconds=30))

    assert "4개 파일" in lines[0]
    assert "30초" in lines[0]
    assert lines[1] == "중요도 TOP 3: a.pdf, b.md, c.docx"


def test_scan_banner_handles_fewer_than_three_files() -> None:
    lines = build_scan_banner_lines(_plan([_entry("only.txt", 40)]))

    assert lines[1] == "중요도 TOP 1: only.txt"


def test_scan_banner_handles_empty_plan() -> None:
    lines = build_scan_banner_lines(_plan([]))

    assert "0개 파일" in lines[0]
    assert lines[1] == "중요도 TOP 0: (없음)"
