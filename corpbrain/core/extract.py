"""텍스트 추출 — 지원 포맷 3종의 확장자 디스패치 (스펙 §4.2).

- `.txt` / `.md`: 원문을 특별 파싱 없이 평문으로 읽는다 (FR-006).
- `.docx`: 문단 텍스트를 순서대로 이어 붙인다 (FR-007).

공통 규칙: 파일을 통째로 메모리에 올리지 않고 앞부분 `max_chars`까지만 읽는다.
개별 파일의 추출 실패는 `ExtractionError`로 올리고, 호출자(FR-008/FR-015)가 스킵으로
흡수해 나머지 파일 처리를 계속한다 — 전체 실패로 위장하지 않는다 (스펙 §5).
`PermissionError`로 인한 실패는 `ExtractionError.__cause__`에 원인이 보존되므로,
호출자가 `permission_denied`와 `extraction_failed`를 구분할 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from corpbrain.core.errors import CorpBrainError
from corpbrain.core.models import SkippedFile, SkipReason

PLAINTEXT_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md"})
DOCX_EXTENSION = ".docx"


class ExtractionError(CorpBrainError):
    """텍스트 추출 실패 — 해당 파일만 스킵되고 나머지 처리는 계속된다."""


@dataclass(frozen=True)
class PreparedDocument:
    """요약 입력 준비 결과 — `text`(정상)와 `skipped`(스킵) 중 정확히 하나만 채워진다."""

    text: str | None = None
    skipped: SkippedFile | None = None


def prepare_summary_input(path: Path, max_chars: int) -> PreparedDocument:
    """추출 → 길이 제한 → 빈 문서·실패 판정을 한 규칙으로 묶는다 (FR-008 / 스펙 §4.2·§5).

    12,000자(기본) 초과 문서는 오류가 아니라 앞부분만 사용해 정상 처리된다.
    빈 문서·추출 실패·권한 거부는 스킵 사유와 함께 반환되고, 호출자는 나머지 파일 처리를 계속한다.
    """
    try:
        text = extract_text(path, max_chars)
    except ExtractionError as exc:
        reason = (
            SkipReason.PERMISSION_DENIED
            if isinstance(exc.__cause__, PermissionError)
            else SkipReason.EXTRACTION_FAILED
        )
        return PreparedDocument(skipped=SkippedFile(path=path, reason=reason, detail=str(exc)))

    # 방어적 절단 — 추출기가 앞부분만 읽더라도 요약 입력은 반드시 max_chars 이하다.
    text = text[:max_chars]
    if not text.strip():
        return PreparedDocument(skipped=SkippedFile(path=path, reason=SkipReason.EMPTY_DOCUMENT))
    return PreparedDocument(text=text)


def extract_text(path: Path, max_chars: int) -> str:
    """`path`의 앞부분 텍스트를 최대 `max_chars`자까지 추출한다.

    Args:
        path: 입력 파일 경로.
        max_chars: 요약 입력으로 쓸 상한 (스펙 §4.2, 기본 12,000).

    Returns:
        추출된 평문. 내용이 없으면 빈 문자열 (호출자가 `empty_document`로 스킵).

    Raises:
        ExtractionError: 지원하지 않는 확장자이거나 읽기·파싱에 실패한 경우.
    """
    suffix = path.suffix.lower()
    if suffix in PLAINTEXT_EXTENSIONS:
        return _extract_plaintext(path, max_chars)
    if suffix == DOCX_EXTENSION:
        return _extract_docx(path, max_chars)
    raise ExtractionError(f"지원하지 않는 확장자입니다: {path.suffix}")


def _extract_plaintext(path: Path, max_chars: int) -> str:
    """`.txt`/`.md`를 UTF-8로 읽되 디코딩 오류는 대체 문자로 흡수한다."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.read(max_chars)
    except OSError as exc:
        raise ExtractionError(f"파일을 읽지 못했습니다: {path}") from exc


def _extract_docx(path: Path, max_chars: int) -> str:
    """`.docx` 문단을 순서대로 잇되 `max_chars`에 도달하면 누적을 멈춘다."""
    try:
        document = Document(str(path))
    except (PackageNotFoundError, OSError, ValueError, KeyError) as exc:
        raise ExtractionError(f"docx를 열지 못했습니다: {path}") from exc

    parts: list[str] = []
    accumulated = 0
    try:
        for paragraph in document.paragraphs:
            text = paragraph.text
            if not text:
                continue
            parts.append(text)
            accumulated += len(text) + 1
            if accumulated >= max_chars:
                break
    except (OSError, ValueError, KeyError) as exc:
        raise ExtractionError(f"docx 문단을 읽지 못했습니다: {path}") from exc

    return "\n".join(parts)[:max_chars]
