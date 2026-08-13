"""종료 리포트·종료 코드 매핑 테스트 (FR-016 / 스펙 §4.1, §5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from corpbrain import cli
from corpbrain.core.models import GeneratedWiki, ScanResult, SkippedFile, SkipReason


def _install_result(monkeypatch: pytest.MonkeyPatch, result: ScanResult) -> None:
    monkeypatch.setattr(cli.core, "run_scan", lambda config, **_: result)


def test_partial_failure_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    result = ScanResult(
        out_dir=tmp_path / "wiki",
        generated=[GeneratedWiki(source_path=tmp_path / "a.txt", output_path=tmp_path / "wiki" / "a.txt.md")],
        skipped=[
            SkippedFile(path=tmp_path / "b.jpg", reason=SkipReason.UNSUPPORTED_EXTENSION),
            SkippedFile(path=tmp_path / "c.txt", reason=SkipReason.SUMMARY_FAILED, detail="깨진 JSON"),
        ],
    )
    _install_result(monkeypatch, result)

    code = cli.main(["scan", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert captured.out == ""  # 요약은 stdout이 아니라 stderr
    assert "처리 1건 / 스킵 2건" in captured.err
    assert "미지원 확장자: 1건" in captured.err
    assert "LLM JSON 파싱 실패: 1건" in captured.err
    assert str(result.out_dir) in captured.err


def test_precondition_failure_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def _raise(config: Any, **_: Any) -> ScanResult:
        raise cli.PreconditionError("Ollama를 찾지 못했습니다")

    monkeypatch.setattr(cli.core, "run_scan", _raise)

    code = cli.main(["scan", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert code != 0
    assert "선행 조건 실패" in captured.err
    assert "Ollama를 찾지 못했습니다" in captured.err


def test_limit_exceeded_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    result = ScanResult(out_dir=tmp_path / "wiki", limit_exceeded=True, discovered_count=73)
    _install_result(monkeypatch, result)

    code = cli.main(["scan", str(tmp_path), "--max", "50"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_LIMIT_EXCEEDED
    assert code != 0
    assert "73건" in captured.err


def test_clean_run_exits_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = ScanResult(out_dir=tmp_path / "wiki")
    _install_result(monkeypatch, result)

    assert cli.main(["scan", str(tmp_path)]) == cli.EXIT_OK
