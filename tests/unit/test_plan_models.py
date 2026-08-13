"""pre-scan 계량 값 타입 (스펙 §4.2, U2) — 필드·타입·불변성.

`plan_scan`의 결정성·점수 범위는 U3의 코어 테스트가 다루고, 여기서는 어댑터가 렌더링에
의존하는 순수 값 구조의 계약(필드 이름·타입·frozen)만 고정한다.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from corpbrain.core import HardwareInfo, PlanEntry, ScanPlan
from corpbrain.core import models as core_models


def _entry() -> PlanEntry:
    return PlanEntry(
        path=Path("root/report.pdf"),
        ext=".pdf",
        size_bytes=2048,
        est_tokens=98,
        importance=55,
    )


def test_plan_entry_fields_and_types() -> None:
    entry = _entry()
    assert entry.path == Path("root/report.pdf")
    assert entry.ext == ".pdf"
    assert entry.size_bytes == 2048
    assert entry.est_tokens == 98
    assert entry.importance == 55


def test_hardware_info_fields() -> None:
    gpu = HardwareInfo(gpu=True, label="GPU: NVIDIA GeForce RTX 4090")
    cpu = HardwareInfo(gpu=False, label="CPU")
    assert gpu.gpu is True and gpu.label.startswith("GPU:")
    assert cpu.gpu is False and cpu.label == "CPU"


def test_scan_plan_aggregates_entries_and_hardware() -> None:
    entry = _entry()
    plan = ScanPlan(
        entries=[entry],
        file_count=1,
        total_est_tokens=entry.est_tokens,
        est_seconds=2,
        hardware=HardwareInfo(gpu=False, label="CPU"),
    )
    assert plan.entries == [entry]
    assert plan.file_count == 1
    assert plan.total_est_tokens == 98
    assert plan.est_seconds == 2
    assert plan.hardware.label == "CPU"


def _instances() -> list[object]:
    return [
        _entry(),
        HardwareInfo(gpu=False, label="CPU"),
        ScanPlan(
            entries=[],
            file_count=0,
            total_est_tokens=0,
            est_seconds=0,
            hardware=HardwareInfo(gpu=False, label="CPU"),
        ),
    ]


@pytest.mark.parametrize("instance", _instances())
def test_value_types_are_frozen(instance: object) -> None:
    """어댑터가 공유 참조를 변형하지 못하도록 세 값 타입은 모두 frozen 이다."""
    field_name = dataclasses.fields(instance)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field_name, "mutated")


def test_value_types_are_reexported_from_core_package() -> None:
    """어댑터는 `corpbrain.core`의 공개 표면만 보고 렌더링한다 (스펙 §4.5)."""
    assert core_models.PlanEntry is PlanEntry
    assert core_models.HardwareInfo is HardwareInfo
    assert core_models.ScanPlan is ScanPlan
