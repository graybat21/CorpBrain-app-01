"""plan 서브커맨드·scan --dry-run·scan 시작 배너 어댑터 테스트 (U5 / 스펙 §4.3 · DoD 6·7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain import cli, core
from corpbrain.core import plan as plan_mod
from corpbrain.core.models import HardwareInfo


@pytest.fixture(autouse=True)
def _stub_hardware(monkeypatch: pytest.MonkeyPatch) -> None:
    """HW 감지를 CPU로 고정 — 실제 nvidia-smi에 의존하지 않게 한다."""
    monkeypatch.setattr(plan_mod, "detect_hardware", lambda: HardwareInfo(gpu=False, label="CPU"))


def _corpus(root: Path) -> None:
    (root / "report.pdf").write_bytes(b"%PDF-1.4 stub")
    (root / "note.txt").write_text("hello", encoding="utf-8")


# --- plan 서브커맨드 (stdout) ---------------------------------------------------


def test_plan_command_writes_report_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path)

    code = cli.main(["plan", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "CorpBrain pre-scan 계량" in captured.out  # 리포트가 stdout으로
    assert "합계: 2개 파일" in captured.out
    assert "감지 하드웨어: CPU" in captured.out


def test_plan_command_does_not_call_ollama(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plan은 LLM·네트워크를 쓰지 않는다 — run_scan/detect가 호출되면 실패한다 (스펙 §4.3)."""
    _corpus(tmp_path)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("plan이 스캔 파이프라인을 호출했다")

    monkeypatch.setattr(core, "run_scan", _boom)

    assert cli.main(["plan", str(tmp_path)]) == cli.EXIT_OK


def test_plan_command_warns_when_over_max(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for index in range(4):
        (tmp_path / f"doc{index}.txt").write_text("x", encoding="utf-8")

    cli.main(["plan", str(tmp_path), "--max", "2"])

    assert "경고:" in capsys.readouterr().out


def test_plan_command_missing_folder_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["plan", str(tmp_path / "no_such_dir")])

    captured = capsys.readouterr()
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert code != 0
    assert "선행 조건 실패" in captured.err
    assert captured.out == ""  # 실패 시 stdout은 비어 있다


# --- scan --dry-run (stdout, 위키 0개) ------------------------------------------


def test_scan_dry_run_reports_without_processing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _corpus(tmp_path)
    out_dir = tmp_path / "wiki"

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("--dry-run이 문서를 처리했다")

    monkeypatch.setattr(core, "run_scan", _boom)

    code = cli.main(["scan", str(tmp_path), "--out", str(out_dir), "--dry-run"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "CorpBrain pre-scan 계량" in captured.out
    assert list(out_dir.rglob("*.md")) == []  # 위키 0개 (DoD 7)


# --- scan 시작 배너 (stderr, stdout은 빔) ---------------------------------------


def test_scan_warns_when_out_dir_is_nested_inside_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--out이 스캔 대상 폴더 안에 있으면 stderr에 자동 제외 안내가 뜬다."""
    _corpus(tmp_path)
    monkeypatch.setattr(
        core, "run_scan", lambda config, **_: core.ScanResult(out_dir=config.out_dir)
    )

    code = cli.main(["scan", str(tmp_path), "--out", str(tmp_path / "wiki")])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "자동으로 제외합니다" in captured.err


def test_scan_does_not_warn_when_out_dir_is_a_sibling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _corpus(tmp_path)
    monkeypatch.setattr(
        core, "run_scan", lambda config, **_: core.ScanResult(out_dir=config.out_dir)
    )

    code = cli.main(["scan", str(tmp_path), "--out", str(tmp_path.parent / "wiki")])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "자동으로 제외합니다" not in captured.err


def test_scan_banner_goes_to_stderr_and_stdout_stays_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _corpus(tmp_path)
    monkeypatch.setattr(
        core, "run_scan", lambda config, **_: core.ScanResult(out_dir=config.out_dir)
    )

    code = cli.main(["scan", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert captured.out == ""  # stdout은 계속 빈다 (DoD 6)
    assert "pre-scan:" in captured.err  # 배너는 stderr
    assert "중요도 TOP" in captured.err
