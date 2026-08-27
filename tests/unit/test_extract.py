"""텍스트 추출기 단위테스트 (FR-006 `.txt`/`.md`, FR-007 `.docx`, v0.2 U1 `.pdf`)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfReader, PdfWriter

from corpbrain.core.config import SUPPORTED_EXTENSIONS
from corpbrain.core.extract import (
    EXTRACTORS,
    ExtractionError,
    _open_failure_detail,
    extract_text,
    prepare_summary_input,
)
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


def _write_text_pdf(path: Path, text: str) -> None:
    """추출 가능한 텍스트 레이어가 있는 최소 단일 페이지 PDF를 만든다 (외부 의존성 없음).

    한글은 base14 폰트로 추출되지 않으므로 텍스트는 ASCII만 사용한다. 바이트 오프셋을 계산해
    올바른 xref를 써서 pypdf의 xref 재구성 경고 없이 읽히게 한다.
    """
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("ascii") + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    path.write_bytes(bytes(out))


def _write_encrypted_pdf(path: Path, source_pdf: Path) -> None:
    """`source_pdf`를 사용자 암호로 암호화해 저장한다 (추출 시 암호화로 스킵되어야 한다)."""
    writer = PdfWriter()
    writer.append(PdfReader(str(source_pdf)))
    writer.encrypt("secret")
    with path.open("wb") as stream:
        writer.write(stream)


def _write_blank_pdf(path: Path) -> None:
    """텍스트 레이어가 없는 PDF(스캔 이미지 PDF 근사) — 추출 결과가 빈 문자열이어야 한다."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as stream:
        writer.write(stream)


#: OLE 복합문서(CFBF) 매직 넘버 — 암호화된 OOXML 파일과 구형 `.xls`/`.ppt`가 공유한다.
OLE_SIGNATURE_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def test_ole_signature_yields_encrypted_or_legacy_detail(tmp_path: Path) -> None:
    """OLE 시그니처로 시작하는 파일은 「암호화되었거나 구형 이진 포맷」 detail을 받는다 (스펙 §4.3.1).

    암호화된 `.xlsx`/`.pptx`는 zip이 아니라 OLE 복합문서로 감싸져 라이브러리가 「zip을 열지
    못했다」는 예외만 던진다 — 손상된 파일과 예외 종류가 같아 구분되지 않는다. 판정은 예외
    메시지 문자열이 아니라 파일 시그니처로 한다.
    """
    source = tmp_path / "locked.xlsx"
    source.write_bytes(OLE_SIGNATURE_BYTES + b"\x00" * 32)

    detail = _open_failure_detail(source)

    assert "암호화되었거나 구형 이진 포맷" in detail
    assert str(source) in detail


def test_non_ole_file_yields_plain_open_failure_detail(tmp_path: Path) -> None:
    """OLE 시그니처가 아니면 손상·파싱 실패 문구를 그대로 쓴다 — 두 원인이 다른 detail을 받는다."""
    source = tmp_path / "broken.xlsx"
    source.write_bytes(b"PK\x03\x04not-a-real-zip")

    detail = _open_failure_detail(source)

    assert "암호화되었거나 구형 이진 포맷" not in detail
    assert str(source) in detail


def test_ole_detail_names_the_actual_extension(tmp_path: Path) -> None:
    """문구의 포맷 이름은 실제 확장자에서 온다 — `.xlsm`이 「xlsx」로 보고되지 않는다."""
    source = tmp_path / "macro.xlsm"
    source.write_bytes(OLE_SIGNATURE_BYTES)

    assert "xlsm" in _open_failure_detail(source)


def test_ole_probe_survives_an_unreadable_file(tmp_path: Path) -> None:
    """시그니처를 읽지 못해도(파일 소실·권한) 예외 없이 기본 문구로 떨어진다.

    이 헬퍼는 **이미 실패한 경로**에서만 불린다. 여기서 새 예외를 올리면 원래의 추출 실패가
    다른 예외로 뒤덮여 스킵 사유가 바뀐다.
    """
    missing = tmp_path / "gone.xlsx"

    detail = _open_failure_detail(missing)

    assert "암호화되었거나 구형 이진 포맷" not in detail


def test_dispatch_table_keys_match_supported_extensions() -> None:
    """확장자 디스패치 매핑의 키 집합이 `SUPPORTED_EXTENSIONS`와 정확히 같다 (스펙 §3 항목7).

    지원 포맷 목록이 `config.SUPPORTED_EXTENSIONS`와 `extract.py`에 따로 정의돼 있어 둘이
    어긋나도 아무도 검증하지 않던 구멍을 닫는다 — 지금까지의 유일한 방어는 `test_scanner.py`의
    리터럴 단언뿐이었고, 그것은 상수 쪽만 본다. 한쪽에만 확장자를 더하면 스캐너가 통과시킨
    파일을 추출기가 「지원하지 않는 확장자」로 되던지거나(추출 실패로 위장된 미지원), 추출기는
    아는데 스캐너가 걸러 영원히 불리지 않는 죽은 코드가 된다.
    """
    assert set(EXTRACTORS) == set(SUPPORTED_EXTENSIONS)


def test_dispatch_table_maps_every_extension_to_a_callable() -> None:
    """매핑 값은 모두 호출 가능해야 한다 — 키만 맞고 값이 비면 위 단언이 공허해진다."""
    assert all(callable(extractor) for extractor in EXTRACTORS.values())


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
    source = tmp_path / "sheet.xlsx"  # xls는 v0.2 비목표 — 여전히 미지원
    source.write_bytes(b"PK\x03\x04")

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


# --- v0.2 U1: .pdf 텍스트 레이어 추출 (스펙 §4.1·§5) -----------------------------


def test_pdf_text_layer_is_extracted(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    _write_text_pdf(source, "CorpBrain PDF text layer sample.")

    assert "CorpBrain PDF text layer sample." in extract_text(source, MAX_CHARS)


def test_pdf_extraction_stops_at_max_chars(tmp_path: Path) -> None:
    source = tmp_path / "long.pdf"
    _write_text_pdf(source, "CorpBrain " * 60)  # 추출 결과가 50자보다 충분히 길다

    assert len(extract_text(source, 50)) == 50


def test_encrypted_pdf_raises_extraction_error(tmp_path: Path) -> None:
    plain = tmp_path / "plain.pdf"
    _write_text_pdf(plain, "secret contents")
    locked = tmp_path / "locked.pdf"
    _write_encrypted_pdf(locked, plain)

    with pytest.raises(ExtractionError, match="암호화"):
        extract_text(locked, MAX_CHARS)


def test_encrypted_pdf_is_skipped_as_extraction_failed(tmp_path: Path) -> None:
    plain = tmp_path / "plain.pdf"
    _write_text_pdf(plain, "secret contents")
    locked = tmp_path / "locked.pdf"
    _write_encrypted_pdf(locked, plain)

    prepared = prepare_summary_input(locked, MAX_CHARS)

    assert prepared.text is None
    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EXTRACTION_FAILED
    assert "암호화" in prepared.skipped.detail


def test_pdf_without_text_layer_yields_empty_string(tmp_path: Path) -> None:
    source = tmp_path / "scanned.pdf"
    _write_blank_pdf(source)

    assert extract_text(source, MAX_CHARS) == ""


def test_pdf_without_text_layer_is_skipped_as_empty(tmp_path: Path) -> None:
    source = tmp_path / "scanned.pdf"
    _write_blank_pdf(source)

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.text is None
    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EMPTY_DOCUMENT


def test_corrupted_pdf_is_skipped_as_extraction_failed(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.pdf"
    source.write_bytes(b"%PDF-1.4 this is not a real pdf body")

    prepared = prepare_summary_input(source, MAX_CHARS)

    assert prepared.text is None
    assert prepared.skipped is not None
    assert prepared.skipped.reason == SkipReason.EXTRACTION_FAILED
    assert prepared.skipped.detail


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
