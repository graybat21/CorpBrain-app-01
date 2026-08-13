"""텍스트 추출기 단위테스트 (FR-006 `.txt`/`.md`, FR-007 `.docx`)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from docx import Document

from corpbrain.core.extract import ExtractionError, extract_text, prepare_summary_input
from corpbrain.core.models import SkipReason

MAX_CHARS = 12000

#: 완료의 정의(스펙 §3)가 요구하는 픽스처 코퍼스 — 통합테스트(FR-018)도 같은 폴더를 쓴다.
FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "sample_corpus"

#: 권한 거부 재현은 POSIX 권한 비트가 적용되는 비-root 환경에서만 가능하다. `os.geteuid`는
#: POSIX 전용이므로 단락 평가로 Windows 수집 크래시를 피한다 (test_scanner.py와 동일 관용구).
needs_posix_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="POSIX 권한 비트가 적용되는 비-root 환경에서만 권한 거부를 재현할 수 있다",
)


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(str(path))


def test_txt_extraction_returns_plain_text(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("첫 줄\n둘째 줄\n", encoding="utf-8")

    assert extract_text(source, MAX_CHARS) == "첫 줄\n둘째 줄\n"


def test_md_is_extracted_verbatim_without_markdown_parsing(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# 제목\n\n- 항목 1\n", encoding="utf-8")

    assert extract_text(source, MAX_CHARS) == "# 제목\n\n- 항목 1\n"


def test_plaintext_reads_only_leading_max_chars(tmp_path: Path) -> None:
    source = tmp_path / "long.txt"
    source.write_text("가" * 20_000, encoding="utf-8")

    extracted = extract_text(source, MAX_CHARS)

    assert len(extracted) == MAX_CHARS
    assert extracted == "가" * MAX_CHARS


def test_empty_file_yields_empty_string(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")

    assert extract_text(source, MAX_CHARS) == ""


def test_broken_encoding_does_not_crash(tmp_path: Path) -> None:
    source = tmp_path / "broken.txt"
    source.write_bytes(b"\xff\xfe valid tail")

    extracted = extract_text(source, MAX_CHARS)

    assert "valid tail" in extracted


def test_unsupported_extension_raises_extraction_error(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")

    with pytest.raises(ExtractionError):
        extract_text(source, MAX_CHARS)


@needs_posix_permissions
def test_permission_denied_is_reported_as_extraction_error(tmp_path: Path) -> None:
    source = tmp_path / "secret.txt"
    source.write_text("내용", encoding="utf-8")
    source.chmod(0o000)

    try:
        with pytest.raises(ExtractionError) as excinfo:
            extract_text(source, MAX_CHARS)
    finally:
        source.chmod(0o600)

    assert isinstance(excinfo.value.__cause__, PermissionError)


def test_docx_paragraphs_are_joined_in_order(tmp_path: Path) -> None:
    source = tmp_path / "report.docx"
    _write_docx(source, ["첫 문단", "둘째 문단", "셋째 문단"])

    assert extract_text(source, MAX_CHARS) == "첫 문단\n둘째 문단\n셋째 문단"


def test_docx_extraction_stops_at_max_chars(tmp_path: Path) -> None:
    source = tmp_path / "big.docx"
    _write_docx(source, ["나" * 500 for _ in range(20)])

    extracted = extract_text(source, 1000)

    assert len(extracted) == 1000


def test_corrupted_docx_raises_extraction_error(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.docx"
    source.write_bytes(b"not a real docx package")

    with pytest.raises(ExtractionError):
        extract_text(source, MAX_CHARS)


def test_empty_docx_yields_empty_string(tmp_path: Path) -> None:
    source = tmp_path / "blank.docx"
    _write_docx(source, [])

    assert extract_text(source, MAX_CHARS) == ""


# --- FR-008: 길이 제한 + 빈문서·추출실패 스킵 판정 -------------------------------


def test_oversized_document_is_truncated_not_skipped(tmp_path: Path) -> None:
    source = tmp_path / "huge.txt"
    source.write_text("다" * 20_000, encoding="utf-8")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.skipped is None
    assert prepared.text is not None
    assert len(prepared.text) == MAX_CHARS


def test_whitespace_only_document_is_skipped_as_empty(tmp_path: Path) -> None:
    source = tmp_path / "blank.md"
    source.write_text("   \n\t\n", encoding="utf-8")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.text is None
    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EMPTY_DOCUMENT


def test_zero_byte_document_is_skipped_as_empty(tmp_path: Path) -> None:
    source = tmp_path / "zero.txt"
    source.write_bytes(b"")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EMPTY_DOCUMENT


def test_corrupted_docx_is_skipped_as_extraction_failed(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.docx"
    source.write_bytes(b"not a real docx package")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.text is None
    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EXTRACTION_FAILED
    assert prepared.skipped.detail


@needs_posix_permissions
def test_unreadable_document_is_skipped_as_permission_denied(tmp_path: Path) -> None:
    source = tmp_path / "locked.txt"
    source.write_text("내용", encoding="utf-8")
    source.chmod(0o000)

    try:
        prepared = prepare_summary_input(source, MAX_CHARS)
    finally:
        source.chmod(0o600)

    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.PERMISSION_DENIED


def test_normal_document_passes_through_with_text(tmp_path: Path) -> None:
    source = tmp_path / "ok.txt"
    source.write_text("정상 문서 본문", encoding="utf-8")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.skipped is None
    assert prepared.text == "정상 문서 본문"


# --- FR-017: 커밋된 픽스처 코퍼스 기반 검증 -------------------------------------


def test_fixture_txt_and_md_extract_plain_text() -> None:
    assert "샘플 텍스트 문서입니다." in extract_text(FIXTURE_CORPUS / "normal.txt", MAX_CHARS)
    assert "# 마크다운 제목" in extract_text(FIXTURE_CORPUS / "guide.md", MAX_CHARS)


def test_fixture_docx_extracts_paragraphs_in_order() -> None:
    extracted = extract_text(FIXTURE_CORPUS / "sub" / "report.docx", MAX_CHARS)

    assert extracted.splitlines()[0] == "분기 실적 보고"
    assert "신규 고객이 늘었다." in extracted


def test_fixture_oversized_document_is_truncated_to_max_chars() -> None:
    prepared = prepare_summary_input(FIXTURE_CORPUS / "oversized.txt", MAX_CHARS)

    assert prepared.skipped is None
    assert prepared.text is not None
    assert len(prepared.text) == MAX_CHARS


def test_fixture_empty_document_is_skipped() -> None:
    prepared = prepare_summary_input(FIXTURE_CORPUS / "empty.txt", MAX_CHARS)

    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EMPTY_DOCUMENT


def test_fixture_unsupported_extension_is_rejected() -> None:
    with pytest.raises(ExtractionError):
        extract_text(FIXTURE_CORPUS / "photo.jpg", MAX_CHARS)
