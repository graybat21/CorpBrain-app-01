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

#: 파서가 **알되 임베딩에서는 빼는** 섹션 (v0.6 §4.4).
#:
#: "## 관련 문서"를 여기에 넣지 않으면 그 섹션과 마커·불릿이 직전 "## 원문" 섹션의 내용으로
#: 흡수된다. 현재는 "## 원문"이 `_EMBEDDABLE_SECTIONS`에 없어 결과적으로 무해하지만 그것은
#: **우연**이며, 언젠가 "## 원문"을 임베딩에 포함시키면 유사도 → 관련 문서 → 임베딩 →
#: 유사도의 **피드백 루프**가 생겨 같은 입력이 같은 그래프를 내지 못한다. 동시에 갓 생성된
#: 문서와 백필된 문서의 임베딩 텍스트가 어긋나 아래 독스트링이 경계한 랭킹 불안정이 생긴다.
_NON_EMBEDDABLE_SECTIONS: tuple[str, ...] = ("## 원문", "## 관련 문서")
_ALL_SECTIONS: frozenset[str] = frozenset({*_EMBEDDABLE_SECTIONS, *_NON_EMBEDDABLE_SECTIONS})

#: 위키 본문에서 태그를 복원할 섹션 — 그래프 재료 fallback에 쓴다 (v0.6 §4.4).
_TAGS_SECTION = "## 태그·키워드"


def parse_wiki_markdown(markdown: str) -> tuple[str, str, list[str]]:
    """이미 기록된 위키 마크다운에서 (제목, 임베딩 입력 텍스트, 태그)를 뽑는다.

    재실행 시 위키 재생성은 스킵되지만 인덱스에 벡터가 없는 문서를 백필할 때 쓴다 —
    `SummaryResult`가 없으므로 저장된 파일에서 직접 복원한다(v0.4 스펙 §4.3 증분 규칙).

    섹션별로 내용을 뽑아 `summary_embedding_text()`와 같은 줄 단위 모양으로 재조립한다 —
    "## 원문"(파일 링크)·"## 관련 문서"(그래프 산출물)와 마크다운 구문(헤더·불릿 기호)은
    제외해, 신선하게 생성된 문서와 백필된 문서가 구조적으로 다른 텍스트를 임베딩해 검색
    랭킹이 흔들리지 않게 한다.

    세 번째 반환값인 태그는 v0.6의 재료 복원 fallback이 쓴다 (§4.4) — `doc_facts`에 행이
    없는 기존 위키에서 제목·태그를 되살려 태그·참조·유사도 3종이 동작하는 부분 그래프를
    만든다. 파서를 둘로 나누지 않아 마크다운 구조 지식이 이 파일 하나에 모인다.
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
    return title, text, list(sections.get(_TAGS_SECTION, []))


def _strip_front_matter(markdown: str) -> str:
    """앞의 `---...---` front-matter 블록을 제거한다(경로·시각 등 임베딩에 무의미한 메타데이터)."""
    if not markdown.startswith("---"):
        return markdown
    end = markdown.find("\n---", 3)
    if end == -1:
        return markdown
    return markdown[end + len("\n---") :]
