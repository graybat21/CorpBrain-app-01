"""통합 테스트 — v0.2 .pdf가 파이프라인을 타는지 코어 API 직접 호출로 검증 (U6 / DoD 1·2).

외부호출 단일 관문만 스텁하고 `run_scan`을 직접 부른다 (스펙 §4.5). PDF 픽스처는 외부 의존성
없이 즉석 생성한다(텍스트 PDF는 최소 바이트, 암호화·빈 PDF는 pypdf PdfWriter). 헬퍼는
tests/unit/test_extract.py의 것과 동일한 관용구다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader, PdfWriter

from corpbrain.core import gateway, run_scan
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.render import FRONT_MATTER_KEYS, SECTION_HEADERS

#: 요약·임베딩 대상 모델이 모두 설치된 정상 `/api/tags` 응답 (v0.3·v0.4 모델 선점검 통과용).
TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}

SUMMARY_JSON = {
    "title": "PDF 통합 제목",
    "one_line_summary": "한 줄 요약.",
    "key_points": ["p1", "p2", "p3"],
    "summary": "문단 요약.",
    "tags": ["t1", "t2"],
}


def _write_text_pdf(path: Path, text: str) -> None:
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
    writer = PdfWriter()
    writer.append(PdfReader(str(source_pdf)))
    writer.encrypt("secret")
    with path.open("wb") as stream:
        writer.write(stream)


def _write_blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as stream:
        writer.write(stream)


def _ok_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)


def _pdf_corpus(root: Path) -> None:
    _write_text_pdf(root / "report.pdf", "CorpBrain PDF text layer sample.")
    _write_encrypted_pdf(root / "locked.pdf", root / "report.pdf")
    _write_blank_pdf(root / "scanned.pdf")


def test_text_pdf_generates_wiki(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DoD 1: 텍스트 레이어 PDF는 스캔 대상에 포함되어 <원본이름.pdf>.md가 생성된다."""
    _ok_gateway(monkeypatch)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_text_pdf(corpus / "report.pdf", "CorpBrain PDF text layer sample.")
    out_dir = tmp_path / "wiki"

    result = run_scan(ScanConfig(folder=corpus, out_dir=out_dir, force_gates=True))

    wiki = out_dir / "report.pdf.md"
    assert wiki.exists()
    assert {w.source_path.name for w in result.generated} == {"report.pdf"}
    markdown = wiki.read_text(encoding="utf-8")
    for key in FRONT_MATTER_KEYS:
        assert f"{key}:" in markdown
    for header in SECTION_HEADERS:
        assert header in markdown


def test_encrypted_and_textless_pdf_are_skipped_with_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DoD 2: 암호화 PDF는 extraction_failed, 텍스트 없는 PDF는 empty_document로 스킵된다."""
    _ok_gateway(monkeypatch)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _pdf_corpus(corpus)
    out_dir = tmp_path / "wiki"

    result = run_scan(ScanConfig(folder=corpus, out_dir=out_dir, force_gates=True))

    skipped = {skip.path.name: skip for skip in result.skipped}
    assert skipped["locked.pdf"].reason.value == "extraction_failed"
    assert "암호화" in skipped["locked.pdf"].detail
    assert skipped["scanned.pdf"].reason.value == "empty_document"
    assert not (out_dir / "locked.pdf.md").exists()
    assert not (out_dir / "scanned.pdf.md").exists()
    # 정상 텍스트 PDF는 계속 생성된다(부분 성공).
    assert (out_dir / "report.pdf.md").exists()
