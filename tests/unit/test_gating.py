"""자원 게이트 판정·모델 매칭 단위 테스트 (v0.3 스펙 §4.2·§4.3·§4.4).

순수 계량(plan_scan)이 GateVerdict를 결정적으로 계산하는지, 토큰 예산이 스킵 예정 파일을
제외하는지, 모델 이름 매칭이 태그 정규화로 오탐/오매치를 피하는지, 리포트 렌더가 게이트를
표시하는지 확인한다. 네트워크·LLM 없이 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain.core import plan as plan_module
from corpbrain.core.config import ScanConfig
from corpbrain.core.llm import ollama_client
from corpbrain.core.models import HardwareInfo, ScanPlan
from corpbrain.core.plan import plan_scan
from corpbrain.core.report import (
    build_doctor_lines,
    build_plan_report_lines,
    build_scan_banner_lines,
)


def _force_hardware(monkeypatch: pytest.MonkeyPatch, *, gpu: bool) -> None:
    label = "GPU: Test" if gpu else "CPU"
    monkeypatch.setattr(
        plan_module, "detect_hardware", lambda: HardwareInfo(gpu=gpu, label=label)
    )


# --- 모델 이름 매칭 (v0.3 §4.3) -------------------------------------------------


@pytest.mark.parametrize(
    ("available", "target", "expected"),
    [
        (["qwen2.5:7b-instruct"], "qwen2.5:7b-instruct", True),  # 정확 일치
        (["llama3:latest"], "llama3", True),  # 무태그 target → :latest 보정
        (["llama3"], "llama3:latest", True),  # 무태그 available → :latest 보정
        (["qwen2.5:7b-instruct"], "qwen2.5:7b", False),  # 접두 오매치 방지
        (["Llama3:latest"], "llama3", False),  # 대소문자 구분
        ([], "anything", False),  # 빈 목록
    ],
)
def test_model_present_normalizes_tags(
    available: list[str], target: str, expected: bool
) -> None:
    assert ollama_client.model_present(available, target) is expected


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"models": [{"name": "a"}, {"name": "b"}]}, ["a", "b"]),
        ({"models": [{"name": "a"}, {"size": 1}]}, ["a"]),  # name 없는 항목 무시
        ({"models": "oops"}, []),  # models가 리스트 아님
        ({}, []),  # models 키 없음
        (["not", "a", "dict"], []),  # 비-객체
    ],
)
def test_available_model_names_is_defensive(
    response: object, expected: list[str]
) -> None:
    assert ollama_client.available_model_names(response) == expected


# --- plan_scan GateVerdict (v0.3 §4.2·§4.4) ------------------------------------


def test_plan_scan_populates_gate_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plan_scan은 GPU·토큰 판정과 임계 에코를 담은 GateVerdict를 채운다."""
    _force_hardware(monkeypatch, gpu=True)
    (tmp_path / "a.txt").write_text("x" * 100, encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path))

    assert plan.gate is not None
    assert plan.gate.gpu_ok is True
    assert plan.gate.tokens_ok is True
    assert plan.gate.oversized_count == 0
    assert plan.gate.max_file_size == ScanConfig(folder=tmp_path).max_file_size
    assert plan.gate.max_total_tokens == ScanConfig(folder=tmp_path).max_total_tokens


def test_gpu_ok_reflects_detected_hardware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GPU 미탐지면 gate.gpu_ok=False (scan 차단 근거)."""
    _force_hardware(monkeypatch, gpu=False)
    (tmp_path / "a.txt").write_text("본문", encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path))

    assert plan.gate is not None
    assert plan.gate.gpu_ok is False


def test_token_budget_excludes_oversized_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """토큰 총합은 스킵 예정(대용량) 파일을 제외하고, oversized_count로 별도 집계한다 (§4.4)."""
    _force_hardware(monkeypatch, gpu=True)
    (tmp_path / "small.txt").write_text("y" * 40, encoding="utf-8")
    (tmp_path / "big.txt").write_text("z" * 100, encoding="utf-8")

    # max_file_size=50 → big.txt(100 bytes)만 대용량으로 제외.
    plan = plan_scan(ScanConfig(folder=tmp_path, max_file_size=50))

    # small.txt: chars=round(40*0.5)=20, tokens=round(20/2.5)=8.
    assert plan.total_est_tokens == 8
    assert plan.gate is not None
    assert plan.gate.oversized_count == 1


def test_tokens_ok_false_when_budget_exceeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """총 토큰이 예산을 넘으면 gate.tokens_ok=False (scan 차단 근거)."""
    _force_hardware(monkeypatch, gpu=True)
    (tmp_path / "a.txt").write_text("x" * 1000, encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path, max_total_tokens=1))

    assert plan.gate is not None
    assert plan.gate.tokens_ok is False


# --- 리포트 렌더 (v0.3 §4.3) ---------------------------------------------------


def test_plan_report_shows_gate_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plan 리포트에 게이트 판정 섹션(GPU·토큰·대용량)이 표시된다."""
    _force_hardware(monkeypatch, gpu=False)
    (tmp_path / "a.txt").write_text("본문", encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path))
    lines = build_plan_report_lines(plan, max_files=50)
    text = "\n".join(lines)

    assert "게이트:" in text
    assert "GPU" in text
    assert "토큰" in text


def test_scan_banner_shows_gate_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scan 배너에 한 줄 게이트 요약이 포함된다."""
    _force_hardware(monkeypatch, gpu=True)
    (tmp_path / "a.txt").write_text("본문", encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path))
    banner = "\n".join(build_scan_banner_lines(plan))

    assert "게이트" in banner


def test_plan_report_handles_missing_gate() -> None:
    """gate=None(직접 구성)이면 게이트 섹션 없이도 렌더가 깨지지 않는다 (하위 호환)."""
    plan = ScanPlan(
        entries=[], file_count=0, total_est_tokens=0, est_seconds=0,
        hardware=HardwareInfo(gpu=True, label="GPU: X"),
    )
    lines = build_plan_report_lines(plan, max_files=50)
    assert "게이트:" not in "\n".join(lines)


def test_build_doctor_lines_ready_and_not_ready() -> None:
    """doctor 렌더는 준비/미준비를 구분하고 실패 항목에 해결 명령을 낸다."""
    from corpbrain.core.environment import DoctorReport

    ready = DoctorReport(
        installed=True, running=True, model="m", model_present=True,
        available_models=["m"], hardware=HardwareInfo(gpu=True, label="GPU: X"),
        max_file_size=20_000_000, max_total_tokens=200_000,
    )
    assert "준비 완료" in "\n".join(build_doctor_lines(ready))

    missing = DoctorReport(
        installed=True, running=True, model="qwen", model_present=False,
        available_models=[], hardware=HardwareInfo(gpu=False, label="CPU"),
        max_file_size=20_000_000, max_total_tokens=200_000,
    )
    text = "\n".join(build_doctor_lines(missing))
    assert "ollama pull qwen" in text
    assert "준비 미완료" in text
