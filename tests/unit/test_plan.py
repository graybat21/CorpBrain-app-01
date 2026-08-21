"""pre-scan 계량 코어 단위테스트 (U3 / 스펙 §4.2 · 완료의 정의 3·4·5)."""

from __future__ import annotations

import builtins
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from corpbrain.core import plan as plan_mod
from corpbrain.core import scanner
from corpbrain.core.config import ScanConfig
from corpbrain.core.models import HardwareInfo, ScanPlan
from corpbrain.core.plan import detect_hardware, plan_scan

CPU = HardwareInfo(gpu=False, label="CPU")
GPU = HardwareInfo(gpu=True, label="GPU: TestGPU")


@pytest.fixture(autouse=True)
def _stub_hardware(monkeypatch: pytest.MonkeyPatch) -> None:
    """plan_scan의 HW 감지를 CPU로 고정한다 — 실제 nvidia-smi에 의존하지 않는 결정성."""
    monkeypatch.setattr(plan_mod, "detect_hardware", lambda: CPU)


def _config(folder: Path, max_chars: int = 12000, max_files: int = 50) -> ScanConfig:
    return ScanConfig(folder=folder, max_chars=max_chars, max_files=max_files)


# --- 중요도 휴리스틱 (스펙 §4.2) -------------------------------------------------


def test_importance_combines_ext_depth_and_signal() -> None:
    # report.pdf(root): base 40 + depth 15 + signal("report") 8 = 63
    assert plan_mod._importance(Path("report.pdf"), ".pdf") == 63


def test_importance_base_scores_differ_by_extension() -> None:
    # 같은 이름·깊이에서 확장자 기본 점수 차이만 반영 (pdf/docx 40 > md 30 > txt 25)
    assert plan_mod._importance(Path("a.pdf"), ".pdf") == 55  # 40+15
    assert plan_mod._importance(Path("a.docx"), ".docx") == 55
    assert plan_mod._importance(Path("a.md"), ".md") == 45  # 30+15
    assert plan_mod._importance(Path("a.txt"), ".txt") == 40  # 25+15


def test_importance_depth_penalty_has_floor() -> None:
    # 깊이 8: depth_adj = max(-20, 15-40) = -20 → 40 - 20 = 20
    deep = Path("a/b/c/d/e/f/g/h/x.pdf")
    assert plan_mod._importance(deep, ".pdf") == 20


def test_importance_noise_penalty_is_capped_and_clamped_to_zero() -> None:
    # temp/tmp/backup/old 4개 잡음 → 40이지만 30으로 상한; txt(25)+depth(0)-30 = -5 → 0
    path = Path("temp/tmp/backup/old.txt")
    assert plan_mod._importance(path, ".txt") == 0


def test_importance_signal_bonus_is_capped_at_30() -> None:
    # 신호 5종 매칭이어도 가산은 30까지 (계약/보고서/report/spec/제안)
    path = Path("계약_보고서_report_spec_제안.pdf")
    # base 40 + depth 15 + 30 = 85
    assert plan_mod._importance(path, ".pdf") == 85


def test_importance_uses_folder_names_in_path() -> None:
    # 신호 키워드가 폴더명에 있어도 매칭한다 (루트 기준 상대경로 전체)
    in_folder = plan_mod._importance(Path("보고서/a.txt"), ".txt")
    plain = plan_mod._importance(Path("plain/a.txt"), ".txt")
    assert in_folder - plain == 8  # signal 1개 차이


# --- 예상 토큰 (스펙 §4.2) -------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "ext", "expected"),
    [
        (1000, ".txt", 200),  # chars=500, tokens=200
        (1000, ".md", 200),
        (1000, ".docx", 24),  # chars=60, tokens=24
        (1000, ".pdf", 48),  # chars=120, tokens=48
    ],
)
def test_estimate_tokens_per_extension(size: int, ext: str, expected: int) -> None:
    assert plan_mod._estimate_tokens(size, ext, 12000) == expected


def test_estimate_tokens_caps_chars_at_max_chars() -> None:
    # 큰 파일도 chars_est는 max_chars(12000)로 상한 → tokens=round(12000/2.5)=4800
    assert plan_mod._estimate_tokens(10_000_000, ".txt", 12000) == 4800


# --- plan_scan 집계·결정성 (스펙 §4.2·§5, 완료의 정의 4·5) -----------------------


def _make_corpus(root: Path) -> None:
    (root / "sub").mkdir()
    (root / "report.pdf").write_bytes(b"%PDF-1.4 stub bytes")
    (root / "note.txt").write_text("hello", encoding="utf-8")
    (root / "sub" / "guide.md").write_text("# guide", encoding="utf-8")
    (root / "photo.jpg").write_bytes(b"\xff\xd8\xff")  # 미지원 → 제외


def test_plan_scan_returns_scan_plan_with_supported_files_only(tmp_path: Path) -> None:
    _make_corpus(tmp_path)

    plan = plan_scan(_config(tmp_path))

    assert isinstance(plan, ScanPlan)
    assert plan.file_count == 3  # jpg 제외
    assert {entry.path.name for entry in plan.entries} == {"report.pdf", "note.txt", "guide.md"}
    assert all(0 <= entry.importance <= 100 for entry in plan.entries)
    assert plan.total_est_tokens == sum(entry.est_tokens for entry in plan.entries)
    assert plan.hardware == CPU


def test_plan_scan_entry_fields_come_from_stat_and_path(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("abcdef", encoding="utf-8")

    plan = plan_scan(_config(tmp_path))
    entry = plan.entries[0]

    assert entry.path == (tmp_path.resolve() / "note.txt")
    assert entry.ext == ".txt"
    assert entry.size_bytes == 6
    assert entry.est_tokens == plan_mod._estimate_tokens(6, ".txt", 12000)


def test_plan_scan_est_seconds_uses_hardware_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "big.txt").write_text("x" * 5000, encoding="utf-8")

    cpu_plan = plan_scan(_config(tmp_path))
    monkeypatch.setattr(plan_mod, "detect_hardware", lambda: GPU)
    gpu_plan = plan_scan(_config(tmp_path))

    assert cpu_plan.est_seconds == round(cpu_plan.total_est_tokens / plan_mod.CPU_RATE)
    assert gpu_plan.est_seconds == round(gpu_plan.total_est_tokens / plan_mod.GPU_RATE)
    assert gpu_plan.est_seconds < cpu_plan.est_seconds  # GPU가 더 빠름


def test_plan_scan_counts_all_files_ignoring_max(tmp_path: Path) -> None:
    """plan은 scan_folder(max_files=None)로 전 파일을 계량한다 — --max는 절단하지 않는다 (스펙 §5)."""
    for index in range(5):
        (tmp_path / f"doc{index}.txt").write_text("x", encoding="utf-8")

    plan = plan_scan(_config(tmp_path, max_files=2))

    assert plan.file_count == 5


def test_plan_scan_excludes_nested_out_dir(tmp_path: Path) -> None:
    """out_dir이 folder 안에 중첩돼 있으면 그 안의 위키 산출물(.md)은 계량 대상에서 빠진다."""
    (tmp_path / "note.txt").write_text("본문", encoding="utf-8")
    out_dir = tmp_path / "wiki"
    out_dir.mkdir()
    (out_dir / "note.txt.md").write_text("# 제목", encoding="utf-8")

    plan = plan_scan(ScanConfig(folder=tmp_path, out_dir=out_dir))

    assert plan.file_count == 1
    assert {entry.path.name for entry in plan.entries} == {"note.txt"}


def test_plan_scan_is_deterministic(tmp_path: Path) -> None:
    _make_corpus(tmp_path)

    assert plan_scan(_config(tmp_path)) == plan_scan(_config(tmp_path))


def test_importance_is_independent_of_file_content(tmp_path: Path) -> None:
    """같은 경로·이름이면 내용이 달라도 중요도가 동일하다 (완료의 정의 5)."""
    target = tmp_path / "report.pdf"
    target.write_bytes(b"first content")
    before = plan_scan(_config(tmp_path)).entries[0].importance

    target.write_bytes(b"completely different and longer content here")
    after = plan_scan(_config(tmp_path)).entries[0].importance

    assert before == after


def test_plan_scan_never_opens_file_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """계량은 os.stat만 쓰고 파일 콘텐츠를 열지 않는다 (완료의 정의 5)."""
    _make_corpus(tmp_path)

    def _fail_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("plan_scan이 파일을 열었다")

    monkeypatch.setattr(builtins, "open", _fail_open)
    monkeypatch.setattr(Path, "read_bytes", _fail_open)
    monkeypatch.setattr(Path, "read_text", _fail_open)

    plan = plan_scan(_config(tmp_path))

    assert plan.file_count == 3


def test_plan_scan_absorbs_unstattable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스캔 통과 후 stat이 실패(삭제·격리·연결끊김)해도 크래시하지 않고 size 0으로 흡수한다.

    scan_folder가 파일을 통과시킨 뒤 stat 시점에 사라지는 TOCTOU를 흉내낸다 — 개별 파일의
    stat 실패가 전체 plan을 죽이면 스펙 §5(부분 실패 ≠ 전체 실패)를 어긴다.
    """
    (tmp_path / "vanishing.txt").write_text("x", encoding="utf-8")
    (tmp_path / "stable.txt").write_text("hello", encoding="utf-8")
    real_stat = Path.stat

    def flaky_stat(self: Path, *args: object, **kwargs: object) -> object:
        if self.name == "vanishing.txt":
            raise OSError("stat 실패 (사라진 파일)")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    plan = plan_scan(_config(tmp_path))  # 예외 없이 완료되어야 한다

    sizes = {entry.path.name: entry.size_bytes for entry in plan.entries}
    assert sizes["vanishing.txt"] == 0
    assert sizes["stable.txt"] == 5


def test_plan_scan_reuses_given_findings_without_walking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """findings를 주면 plan_scan은 다시 순회하지 않고 그대로 계량한다 (배너와 워크 공유)."""
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    prewalked = scanner.scan_folder(tmp_path, max_files=None)

    def _no_walk(*args: object, **kwargs: object) -> object:
        raise AssertionError("findings를 받고도 plan_scan이 순회했다")

    monkeypatch.setattr(plan_mod, "scan_folder", _no_walk)

    plan = plan_scan(_config(tmp_path), findings=prewalked)

    assert plan.file_count == 1


# --- 하드웨어 감지 (스펙 §4.2, nvidia-smi subprocess만) --------------------------


def test_detect_hardware_reports_gpu_name_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(stdout="NVIDIA GeForce RTX 4090\n")

    monkeypatch.setattr(plan_mod.subprocess, "run", _run)

    info = detect_hardware()

    assert info == HardwareInfo(gpu=True, label="GPU: NVIDIA GeForce RTX 4090")


@pytest.mark.parametrize(
    "boom",
    [
        FileNotFoundError("nvidia-smi 없음"),
        subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=2.0),
        subprocess.CalledProcessError(returncode=1, cmd="nvidia-smi"),
    ],
)
def test_detect_hardware_falls_back_to_cpu(
    monkeypatch: pytest.MonkeyPatch, boom: Exception
) -> None:
    def _run(*args: object, **kwargs: object) -> SimpleNamespace:
        raise boom

    monkeypatch.setattr(plan_mod.subprocess, "run", _run)

    assert detect_hardware() == HardwareInfo(gpu=False, label="CPU")


def test_detect_hardware_treats_empty_output_as_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        plan_mod.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="  \n")
    )

    assert detect_hardware() == HardwareInfo(gpu=False, label="CPU")
