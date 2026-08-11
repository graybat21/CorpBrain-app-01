"""텍스트 추출기 단위테스트 (FR-006 `.txt`/`.md`, FR-007 `.docx`)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from docx import Document

from corpbrain.core.extract import ExtractionError, extract_text, prepare_summary_input
from corpbrain.core.models import SkipReason

MAX_CHARS = 12000


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


@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한 거부를 재현할 수 없다")
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


@pytest.mark.skipif(os.geteuid() == 0, reason="root는 권한 거부를 재현할 수 없다")
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
