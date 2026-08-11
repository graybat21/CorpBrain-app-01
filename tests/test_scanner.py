"""재귀 스캐너·포맷 필터 단위 테스트 (FR-004 / 스펙 §4.2, §4.5)."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from corpbrain.core import config
from corpbrain.core.models import SkipReason
from corpbrain.core.scanner import (
    SUPPORTED_EXTENSIONS,
    ScanFindings,
    is_supported,
    iter_files,
    scan_folder,
)


def _make_fixture(root: Path) -> None:
    """하위폴더·지원 포맷·미지원 확장자가 섞인 픽스처 트리를 만든다.

    root/
      Notes.MD          지원 (대문자 확장자)
      a.txt             지원
      b.pdf             미지원 (비목표 포맷)
      sub/c.docx        지원 (하위폴더)
      sub/d.jpg         미지원
      sub/deep/e.md     지원 (2단계 하위폴더)
      empty_dir/        파일 없음
    """
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "empty_dir").mkdir()
    (root / "Notes.MD").write_text("notes", encoding="utf-8")
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b.pdf").write_bytes(b"%PDF-1.4")
    (root / "sub" / "c.docx").write_bytes(b"PK\x03\x04")
    (root / "sub" / "d.jpg").write_bytes(b"\xff\xd8\xff")
    (root / "sub" / "deep" / "e.md").write_text("# e", encoding="utf-8")


# --- Scenario 1: 지원 포맷만 재귀 선별 -------------------------------------------


def test_scan_folder_collects_supported_files_recursively(tmp_path: Path) -> None:
    """하위폴더 포함 모든 지원 포맷을 담고 미지원 확장자는 처리 대상에서 뺀다."""
    _make_fixture(tmp_path)

    findings = scan_folder(tmp_path)

    root = tmp_path.resolve()
    assert findings.targets == [
        root / "Notes.MD",
        root / "a.txt",
        root / "sub" / "c.docx",
        root / "sub" / "deep" / "e.md",
    ]


def test_scan_folder_returns_absolute_paths_relative_to_root(tmp_path: Path) -> None:
    """반환 경로는 절대경로이며 root 기준 상대경로를 계산할 수 있다 (FR-012 미러링 기반)."""
    _make_fixture(tmp_path)

    findings = scan_folder(tmp_path)

    root = tmp_path.resolve()
    assert all(path.is_absolute() for path in findings.targets)
    assert {path.relative_to(root) for path in findings.targets} == {
        Path("Notes.MD"),
        Path("a.txt"),
        Path("sub/c.docx"),
        Path("sub/deep/e.md"),
    }


def test_scan_folder_accepts_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """상대경로 root로 호출해도 절대경로를 돌려준다."""
    _make_fixture(tmp_path)
    monkeypatch.chdir(tmp_path.parent)

    findings = scan_folder(Path(tmp_path.name))

    assert findings.targets == scan_folder(tmp_path).targets


def test_scan_folder_on_empty_folder_returns_empty_findings(tmp_path: Path) -> None:
    """파일이 없으면 대상도 스킵도 없다."""
    findings = scan_folder(tmp_path)

    assert findings == ScanFindings(targets=[], skipped=[])


def test_iter_files_yields_every_file_in_deterministic_order(tmp_path: Path) -> None:
    """순회는 지원 여부와 무관하게 모든 파일을 같은 순서로 흘려보낸다."""
    _make_fixture(tmp_path)

    root = tmp_path.resolve()
    assert list(iter_files(tmp_path)) == [
        root / "Notes.MD",
        root / "a.txt",
        root / "b.pdf",
        root / "sub" / "c.docx",
        root / "sub" / "d.jpg",
        root / "sub" / "deep" / "e.md",
    ]


def test_iter_files_on_missing_folder_yields_nothing(tmp_path: Path) -> None:
    """없는 폴더는 예외 없이 빈 순회 — 선행 조건 검사는 FR-005 담당."""
    assert list(iter_files(tmp_path / "no_such_dir")) == []


# --- Scenario 2: 미지원 확장자 스킵 분류 -----------------------------------------


def test_scan_folder_classifies_unsupported_extensions_as_skipped(
    tmp_path: Path,
) -> None:
    """미지원 확장자는 사유 `unsupported_extension`으로 스킵 목록에 들어간다."""
    _make_fixture(tmp_path)

    findings = scan_folder(tmp_path)

    root = tmp_path.resolve()
    assert [(item.path, item.reason) for item in findings.skipped] == [
        (root / "b.pdf", SkipReason.UNSUPPORTED_EXTENSION),
        (root / "sub" / "d.jpg", SkipReason.UNSUPPORTED_EXTENSION),
    ]
    assert all(item.reason == "unsupported_extension" for item in findings.skipped)
    assert not set(findings.targets) & {item.path for item in findings.skipped}


def test_scan_folder_skips_files_without_extension(tmp_path: Path) -> None:
    """확장자가 없는 파일도 미지원으로 분류한다."""
    (tmp_path / "README").write_text("no suffix", encoding="utf-8")

    findings = scan_folder(tmp_path)

    assert findings.targets == []
    assert [item.reason for item in findings.skipped] == [
        SkipReason.UNSUPPORTED_EXTENSION
    ]


# --- 포맷 필터 ------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["doc.docx", "doc.DOCX", "note.txt", "note.Txt", "wiki.md", "wiki.MD"],
)
def test_is_supported_ignores_extension_case(name: str) -> None:
    assert is_supported(Path(name)) is True


@pytest.mark.parametrize(
    "name", ["scan.pdf", "old.doc", "photo.JPG", "README", "a.mdx"]
)
def test_is_supported_rejects_unsupported_extensions(name: str) -> None:
    assert is_supported(Path(name)) is False


def test_supported_extensions_is_the_shared_core_constant() -> None:
    """확장자 집합을 새로 만들지 않고 코어 설정(스펙 §4.2)을 re-export 한다."""
    assert SUPPORTED_EXTENSIONS is config.SUPPORTED_EXTENSIONS
    assert SUPPORTED_EXTENSIONS == {".docx", ".txt", ".md"}


# --- 경로만 다룬다 --------------------------------------------------------------


def test_scan_folder_never_opens_file_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스캔은 파일 내용을 열지 않는다 (텍스트 추출은 FR-006~008 담당)."""
    _make_fixture(tmp_path)

    def _fail_open(*args: object, **kwargs: object) -> None:
        raise AssertionError("스캐너가 파일을 열었다")

    monkeypatch.setattr(builtins, "open", _fail_open)
    monkeypatch.setattr(Path, "read_bytes", _fail_open)
    monkeypatch.setattr(Path, "read_text", _fail_open)

    findings = scan_folder(tmp_path)

    assert len(findings.targets) == 4
