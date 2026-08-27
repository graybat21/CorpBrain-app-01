"""위키 마크다운 파싱 — 임베딩 입력 텍스트와 상세 화면용 구조화 값.

임베딩 입력은 위키 요약 콘텐츠에서 청크 분할 없이 문서당 1개 텍스트를 뽑는다
(v0.4 스펙 §4.3: "문서당 벡터 1개", 입력은 렌더링된 위키의 요약 콘텐츠).

**마크다운 구조 지식은 이 파일 하나에 모인다** (v0.6 §4.4 결정 계승). v0.9의 위키 상세
화면이 필요로 하는 `parse_wiki_document()`도 새 모듈로 나가지 않고 여기 있다 — 나가면
같은 헤더 목록이 두 곳에 생기고, 한쪽만 고쳐지는 순간 두 화면이 오류 없이 어긋난다.
"""

from __future__ import annotations

import re

from corpbrain.core.models import RelatedLink, SummaryResult, WikiDocument


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

    **반환은 3-튜플 그대로다** (v0.9 §4.6). 이 함수는 `parse_wiki_document()`를 부르는 얇은
    래퍼이며, 반환을 바꾸지 않는 것이 기존 호출부 세 곳(`_backfill_embedding`·그래프 재료
    복원·단위테스트)을 한 줄도 건드리지 않는 이유다.
    """
    document = parse_wiki_document(markdown)
    # **구조화된 값이 아니라 섹션 원문 줄에서 만든다.** `WikiDocument.key_points`는 화면에
    # 보여 줄 불릿만 담으므로(`- `로 시작하는 줄), 여러 줄로 이어진 핵심 포인트의 둘째 줄이
    # 빠진다. 그러면 갓 생성된 문서(`summary_embedding_text()`)와 백필된 문서의 임베딩
    # 텍스트가 어긋나 이 모듈 독스트링이 경계한 랭킹 불안정이 생긴다.
    _front, body = _split_front_matter(markdown)
    sections = _raw_sections(body)
    parts = [document.title]
    for header in _EMBEDDABLE_SECTIONS:
        parts.extend(
            _debullet(part)
            for line in sections.get(header, [])
            for part in (line.split(", ") if header == _TAGS_SECTION else [line])
        )
    text = "\n".join(part for part in parts if part)
    return document.title, text, list(document.tags)


def _debullet(line: str) -> str:
    """불릿 기호를 뗀다 — 임베딩 입력에는 마크다운 구문이 들어가지 않는다.

    `key_points` 밖의 섹션에도 적용하는 것은 **기존 동작을 그대로 보존하기 위함**이다.
    이 함수가 만드는 문자열이 바뀌면 갓 생성된 문서와 백필된 문서의 임베딩 텍스트가 어긋나
    검색 랭킹이 흔들린다.
    """
    return line[2:].strip() if line.startswith("- ") else line.strip()


#: 「관련 문서」 한 줄: `- [제목](상대경로) — 근거`. 근거는 없을 수 있다 (v0.6 §4.5).
_RELATED_LINE = re.compile(r"^-\s+\[(?P<title>.*?)\]\((?P<href>.*?)\)(?:\s+—\s+(?P<evidence>.*))?$")

#: 「원문」 링크: `[원본 파일 열기](file://<절대경로>)`.
_SOURCE_LINK = re.compile(r"^\[.*?\]\(file://(?P<path>.*)\)$")


def parse_wiki_document(markdown: str) -> WikiDocument:
    """렌더된 위키 마크다운을 front-matter 5키 + 7섹션으로 편다 (v0.9 §4.6).

    `parse_wiki_markdown()`과 **같은 섹션 지식**(`_ALL_SECTIONS`)을 쓰되 정규화하지 않는다 —
    그 함수는 임베딩 입력을 만들려고 불릿 기호를 떼고 태그를 분해하며 빈 줄을 버리므로 화면에
    보여 줄 원문이 남지 않는다.

    파싱에 실패한 부분은 **빈 값으로 둔다.** 위키가 조금 낡았거나 사용자가 손으로 고쳤다고
    해서 상세 화면 전체가 실패하지 않게 한다 — v0.6이 「재료가 없으면 그 엣지만 빠진다」로
    세운 방침과 같은 결이다.
    """
    front, body = _split_front_matter(markdown)
    sections = _raw_sections(body)
    key_points = [
        line[2:].strip()
        for line in sections.get("## 핵심 포인트", [])
        if line.startswith("- ")
    ]
    tags = [
        # 불릿 기호를 뗀다. 렌더러는 태그를 `, `로 이어 한 줄로 쓰지만, 손으로 고친 위키나
        # 다른 도구가 만든 산출물은 불릿으로 적혀 있을 수 있다 — 그대로 두면 그래프의 태그
        # 노드 라벨이 `- 인사`가 되고 화면의 태그 칩에도 그 기호가 남는다.
        stripped
        for line in sections.get(_TAGS_SECTION, [])
        for tag in _debullet(line).split(",")
        if (stripped := tag.strip())
    ]
    return WikiDocument(
        source_path=front.get("source_path", ""),
        generated_at=front.get("generated_at", ""),
        model=front.get("model", ""),
        engine=front.get("engine", ""),
        source_bytes=_as_int(front.get("source_bytes", "")),
        title=_first_title(body),
        one_line_summary="\n".join(sections.get("## 한 줄 요약", [])),
        key_points=key_points,
        summary="\n".join(sections.get("## 요약", [])),
        tags=tags,
        source_link=_source_link(sections.get("## 원문", [])),
        related=_related_links(sections.get("## 관련 문서", [])),
    )


def _split_front_matter(markdown: str) -> tuple[dict[str, str], str]:
    """front-matter를 `{키: 값}`으로 읽고 본문과 나눈다.

    값의 따옴표를 벗기지만 그 이상 해석하지 않는다 — YAML 파서를 들이지 않는다(신규 의존성 0).
    `render.py`가 쓰는 다섯 키는 전부 `"…"` 또는 숫자 한 줄이다.
    """
    if not markdown.startswith("---"):
        return {}, markdown
    end = markdown.find("\n---", 3)
    if end == -1:
        return {}, markdown
    front: dict[str, str] = {}
    for line in markdown[3:end].splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        front[key.strip()] = value.strip().strip('"')
    return front, markdown[end + len("\n---") :]


def _raw_sections(body: str) -> dict[str, list[str]]:
    """섹션 헤더로 본문을 가르되 **줄을 그대로** 담는다 (마커·빈 줄만 버린다)."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped in _ALL_SECTIONS:
            current = stripped
            # **덮어쓴다.** `setdefault`로 이어 붙이면 같은 헤더가 두 번 나오는 위키에서 두
            # 블록이 합쳐진다 — v0.6 §4.5가 「사용자가 마커를 지우면 다음 실행에 블록이 하나
            # 더 추가된다」로 실제로 일어난다고 적어 둔 상황이며, 그때 상세 화면의 「관련
            # 문서」가 전부 두 번 나온다. 옛 파서도 덮어썼다.
            sections[current] = []
            continue
        if stripped.startswith("<!-- corpbrain:"):
            continue  # 기계 관리 마커는 화면에 보일 것이 아니다 (v0.6 §4.5)
        if current is not None and stripped:
            sections[current].append(stripped)
    return sections


def _first_title(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def _as_int(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return 0


def _source_link(lines: list[str]) -> str:
    for line in lines:
        match = _SOURCE_LINK.match(line)
        if match:
            return match.group("path")
    return ""


def _related_links(lines: list[str]) -> list[RelatedLink]:
    """「관련 문서」 불릿을 그대로 옮긴다. `관련 문서 없음`이면 빈 목록이다.

    **`doc_id`는 여기서 채우지 않는다** — 위키 본문에 적혀 있지 않고, 상대 링크를 푸는 것은
    경로를 아는 어댑터의 일이다 (§4.6 · IX3).
    """
    links: list[RelatedLink] = []
    for line in lines:
        match = _RELATED_LINE.match(line)
        if match is None:
            continue
        links.append(
            RelatedLink(
                title=match.group("title"),
                href=match.group("href"),
                evidence=(match.group("evidence") or "").strip(),
            )
        )
    return links
