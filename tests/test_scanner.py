"""재귀 스캐너·포맷 필터·가드레일 단위 테스트 (FR-004·FR-005 / 스펙 §4.2, §5, §4.5)."""

from __future__ import annotations

import builtins
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from stat import S_IMODE

import pytest

from corpbrain.core import config, scanner
from corpbrain.core.models import SkipReason
from corpbrain.core.scanner import (
    MAX_PATH_LENGTH,
    SUPPORTED_EXTENSIONS,
    ScanFindings,
    is_supported,
    iter_files,
    scan_folder,
)

#: 권한 거부 재현은 POSIX 권한 비트가 실제로 적용될 때만 가능하다 (root는 우회한다).
needs_posix_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="POSIX 권한 비트가 적용되는 비-root 환경에서만 권한 거부를 재현할 수 있다",
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


# === FR-005 가드레일 (스펙 §5, §3 완료의 정의 3·4번) =============================


def _make_files(root: Path, count: int, suffix: str = ".txt") -> None:
    """`count`개의 파일을 결정적 이름으로 만든다."""
    for index in range(count):
        (root / f"doc{index:03d}{suffix}").write_text("x", encoding="utf-8")


def _make_file_of_path_length(root: Path, total: int, suffix: str = ".md") -> Path:
    """경로 문자열 길이가 정확히 `total`자인 파일을 만든다.

    파일명 1개로 채우면 컴포넌트 255자 제한에 걸릴 수 있으므로, 남는 길이가 크면
    중간 디렉터리를 먼저 중첩해 흡수한다.
    """
    parent = root.resolve()
    while total - len(str(parent)) - 1 - len(suffix) > 200:
        parent = parent / ("d" * 40)
    name_length = total - len(str(parent)) - 1
    # pragma: no cover - 임시 경로가 비정상적으로 깊을 때만 도달한다.
    if name_length <= len(suffix):
        pytest.skip("임시 경로가 너무 길어 목표 길이의 경로를 만들 수 없다")
    parent.mkdir(parents=True, exist_ok=True)
    path = parent / (("n" * (name_length - len(suffix))) + suffix)
    path.write_text("edge", encoding="utf-8")
    assert len(str(path)) == total
    return path


@contextmanager
def _denied(path: Path) -> Iterator[Path]:
    """`path`(파일·디렉터리)의 권한을 잠시 0으로 만든다 — 종료 시 반드시 복구한다."""
    original = S_IMODE(path.stat().st_mode)
    path.chmod(0o000)
    try:
        yield path
    finally:
        path.chmod(original)


# --- Scenario 1: 상한(50) 초과 시 중단+알림 --------------------------------------


def test_scan_folder_stops_when_supported_files_exceed_max(tmp_path: Path) -> None:
    """상한 초과는 부분 실패가 아니라 처리 중단 — 대상을 하나도 넘기지 않는다."""
    _make_files(tmp_path, 51)

    findings = scan_folder(tmp_path, max_files=config.DEFAULT_MAX_FILES)

    assert findings.limit_exceeded is True
    assert findings.discovered_count == 51
    assert findings.targets == []


def test_scan_folder_allows_exactly_max_files(tmp_path: Path) -> None:
    """상한과 같은 수(50)는 초과가 아니므로 정상 처리한다."""
    _make_files(tmp_path, config.DEFAULT_MAX_FILES)

    findings = scan_folder(tmp_path, max_files=config.DEFAULT_MAX_FILES)

    assert findings.limit_exceeded is False
    assert findings.discovered_count == config.DEFAULT_MAX_FILES
    assert len(findings.targets) == config.DEFAULT_MAX_FILES


def test_scan_folder_without_max_files_applies_no_limit(tmp_path: Path) -> None:
    """상한 기본값은 CLI/파이프라인이 주입한다 — 스캐너는 50을 하드코딩하지 않는다."""
    _make_files(tmp_path, config.DEFAULT_MAX_FILES + 1)

    findings = scan_folder(tmp_path)

    assert findings.limit_exceeded is False
    assert len(findings.targets) == config.DEFAULT_MAX_FILES + 1
    assert findings.discovered_count == config.DEFAULT_MAX_FILES + 1


def test_scan_folder_limit_counts_only_processing_targets(tmp_path: Path) -> None:
    """스킵되는 파일은 상한 계산에 들어가지 않는다 (처리 대상 수 기준)."""
    _make_files(tmp_path, 3, suffix=".txt")
    _make_files(tmp_path, 5, suffix=".pdf")

    findings = scan_folder(tmp_path, max_files=3)

    assert findings.limit_exceeded is False
    assert findings.discovered_count == 3
    assert len(findings.skipped) == 5


def test_scan_folder_keeps_skip_report_when_limit_exceeded(tmp_path: Path) -> None:
    """상한 초과 시에도 그때까지 분류된 스킵 목록은 그대로 유지한다 (FR-016 리포트용)."""
    _make_files(tmp_path, 2, suffix=".md")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")

    findings = scan_folder(tmp_path, max_files=1)

    assert findings.limit_exceeded is True
    assert findings.targets == []
    assert [(item.path, item.reason) for item in findings.skipped] == [
        (tmp_path.resolve() / "photo.jpg", SkipReason.UNSUPPORTED_EXTENSION)
    ]


def test_scan_folder_limit_is_not_raised_as_exception(tmp_path: Path) -> None:
    """상한 초과는 예외가 아니라 반환 신호다 (알림·종료 코드는 FR-016 담당)."""
    _make_files(tmp_path, 2)

    findings = scan_folder(tmp_path, max_files=1)

    assert isinstance(findings, ScanFindings)
    assert findings.limit_exceeded is True


# --- Scenario 2: 긴 경로 / 권한 거부 / 미지원은 스킵+로그로 계속 처리 --------------


def test_scan_folder_classifies_long_paths_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """경로 길이가 상한을 넘으면 사유 `path_too_long`으로 스킵한다.

    실제 >260자 경로는 Windows 기본 MAX_PATH에서 생성할 수 없으므로, 상한을 대상 파일
    경로 길이보다 한 글자 낮춰 '초과' 상황을 결정적·크로스플랫폼으로 재현한다.
    (상한값 260 자체는 test_max_path_length_is_the_shared_core_constant가 검증한다.)
    """
    target = tmp_path / "over.md"
    target.write_text("edge", encoding="utf-8")
    monkeypatch.setattr(scanner, "MAX_PATH_LENGTH", len(str(target.resolve())) - 1)

    findings = scan_folder(tmp_path)

    assert findings.targets == []
    assert [(item.path, item.reason) for item in findings.skipped] == [
        (target.resolve(), SkipReason.PATH_TOO_LONG)
    ]


def test_long_path_check_precedes_extension_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """긴 경로면 확장자와 무관하게 `path_too_long`으로 분류한다(미지원 확장자보다 우선)."""
    target = tmp_path / "over.pdf"
    target.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(scanner, "MAX_PATH_LENGTH", len(str(target.resolve())) - 1)

    findings = scan_folder(tmp_path)

    assert [(item.path, item.reason) for item in findings.skipped] == [
        (target.resolve(), SkipReason.PATH_TOO_LONG)
    ]


def test_scan_folder_accepts_paths_at_the_length_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """경로 길이가 정확히 상한과 같으면 초과가 아니므로 처리 대상이다."""
    target = tmp_path / "boundary.md"
    target.write_text("edge", encoding="utf-8")
    monkeypatch.setattr(scanner, "MAX_PATH_LENGTH", len(str(target.resolve())))

    findings = scan_folder(tmp_path)

    assert findings.targets == [target.resolve()]
    assert findings.skipped == []


@needs_posix_permissions
def test_scan_folder_classifies_unreadable_file_as_permission_denied(
    tmp_path: Path,
) -> None:
    """읽을 수 없는 지원 포맷 파일은 사유 `permission_denied`로 스킵한다."""
    secret = tmp_path / "secret.md"
    secret.write_text("classified", encoding="utf-8")
    (tmp_path / "open.txt").write_text("ok", encoding="utf-8")

    with _denied(secret):
        findings = scan_folder(tmp_path)

    assert findings.targets == [tmp_path.resolve() / "open.txt"]
    assert [(item.path, item.reason) for item in findings.skipped] == [
        (tmp_path.resolve() / "secret.md", SkipReason.PERMISSION_DENIED)
    ]


@needs_posix_permissions
def test_unsupported_extension_check_precedes_permission_probe(
    tmp_path: Path,
) -> None:
    """미지원 확장자는 애초에 처리 대상이 아니므로 권한 프로브 전에 분류한다."""
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4")

    with _denied(secret):
        findings = scan_folder(tmp_path)

    assert [item.reason for item in findings.skipped] == [
        SkipReason.UNSUPPORTED_EXTENSION
    ]


@needs_posix_permissions
def test_scan_folder_absorbs_unreadable_directory_and_keeps_going(
    tmp_path: Path,
) -> None:
    """디렉터리 접근 거부는 크래시가 아니라 스킵 1건 — 나머지 순회는 계속된다."""
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "inside.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("ok", encoding="utf-8")

    with _denied(locked):
        findings = scan_folder(tmp_path)

    assert findings.targets == [tmp_path.resolve() / "visible.txt"]
    assert [(item.path, item.reason) for item in findings.skipped] == [
        (tmp_path.resolve() / "locked", SkipReason.PERMISSION_DENIED)
    ]
    assert findings.skipped[0].detail


def test_scan_folder_on_missing_root_reports_no_skip(tmp_path: Path) -> None:
    """입력 폴더 자체의 접근 실패는 개별 스킵이 아니라 선행 조건 실패다 (FR-015·016)."""
    findings = scan_folder(tmp_path / "no_such_dir", max_files=config.DEFAULT_MAX_FILES)

    assert findings == ScanFindings(targets=[], skipped=[])


@needs_posix_permissions
def test_scan_folder_mixes_every_skip_reason_and_still_processes_the_rest(
    tmp_path: Path,
) -> None:
    """긴 경로·권한 거부·미지원이 섞여 있어도 각 사유로 스킵되고 정상 파일은 처리된다."""
    (tmp_path / "good.md").write_text("keep", encoding="utf-8")
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4")
    secret = tmp_path / "secret.txt"
    secret.write_text("classified", encoding="utf-8")
    long_path = _make_file_of_path_length(tmp_path, MAX_PATH_LENGTH + 1)

    with _denied(secret):
        findings = scan_folder(tmp_path, max_files=config.DEFAULT_MAX_FILES)

    root = tmp_path.resolve()
    assert findings.limit_exceeded is False
    assert findings.targets == [root / "good.md"]
    assert {item.path: item.reason for item in findings.skipped} == {
        long_path: SkipReason.PATH_TOO_LONG,
        root / "report.pdf": SkipReason.UNSUPPORTED_EXTENSION,
        root / "secret.txt": SkipReason.PERMISSION_DENIED,
    }
    assert findings.discovered_count == 1


def test_max_path_length_is_the_shared_core_constant() -> None:
    """경로 길이 상한도 새로 만들지 않고 코어 설정(스펙 §5)을 그대로 쓴다."""
    assert MAX_PATH_LENGTH is config.MAX_PATH_LENGTH
    assert MAX_PATH_LENGTH == 260
