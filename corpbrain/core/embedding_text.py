"""임베딩 입력 텍스트 조립 — 위키 요약 콘텐츠에서 청크 분할 없이 문서당 1개 텍스트를 뽑는다
(v0.4 스펙 §4.3: "문서당 벡터 1개", 입력은 렌더링된 위키의 요약 콘텐츠).
"""

from __future__ import annotations

from corpbrain.core.models import SummaryResult


def summary_embedding_text(summary: SummaryResult) -> str:
    """신선하게 생성된 `SummaryResult`에서 임베딩 입력 텍스트를 만든다."""
    parts = [
        summary.title,
        summary.one_line_summary,
        *summary.key_points,
        summary.summary,
        *summary.tags,
    ]
    return "\n".join(part for part in parts if part)


#: `render.py`의 고정 섹션 헤더 순서(`SECTION_HEADERS`)와 동일해야 파싱이 어긋나지 않는다.
#: "## 원문"은 파일 링크뿐이라 임베딩에서 제외한다.
_EMBEDDABLE_SECTIONS: tuple[str, ...] = ("## 한 줄 요약", "## 핵심 포인트", "## 요약", "## 태그·키워드")
_ALL_SECTIONS: frozenset[str] = frozenset({*_EMBEDDABLE_SECTIONS, "## 원문"})


def parse_wiki_markdown(markdown: str) -> tuple[str, str]:
    """이미 기록된 위키 마크다운에서 (제목, 임베딩 입력 텍스트)를 뽑는다.

    재실행 시 위키 재생성은 스킵되지만 인덱스에 벡터가 없는 문서를 백필할 때 쓴다 —
    `SummaryResult`가 없으므로 저장된 파일에서 직접 복원한다(v0.4 스펙 §4.3 증분 규칙).

    섹션별로 내용을 뽑아 `summary_embedding_text()`와 같은 줄 단위 모양으로 재조립한다 —
    "## 원문"(파일 링크)과 마크다운 구문(헤더·불릿 기호)은 제외해, 신선하게 생성된 문서와
    백필된 문서가 구조적으로 다른 텍스트를 임베딩해 검색 랭킹이 흔들리지 않게 한다.
    """
    body = _strip_front_matter(markdown).strip()
    title = ""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if not title and stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            continue
        if stripped in _ALL_SECTIONS:
            current = stripped
            sections[current] = []
            continue
        if current is not None and stripped:
            for part in stripped.split(", ") if current == "## 태그·키워드" else [stripped]:
                text = part[2:].strip() if part.startswith("- ") else part.strip()
                if text:
                    sections[current].append(text)

    parts = [title]
    for header in _EMBEDDABLE_SECTIONS:
        parts.extend(sections.get(header, []))
    text = "\n".join(part for part in parts if part)
    return title, text


def _strip_front_matter(markdown: str) -> str:
    """앞의 `---...---` front-matter 블록을 제거한다(경로·시각 등 임베딩에 무의미한 메타데이터)."""
    if not markdown.startswith("---"):
        return markdown
    end = markdown.find("\n---", 3)
    if end == -1:
        return markdown
    return markdown[end + len("\n---") :]
