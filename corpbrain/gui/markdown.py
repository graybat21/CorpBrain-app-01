"""최소 마크다운 렌더러 (v0.9 스펙 §4.9).

라이브러리를 쓰지 않는다 — 그러면 §4.2의 「신규 런타임 의존성 0개」가 깨진다. 위키는 코드가
소유한 **고정 템플릿**(front-matter · `#` 제목 · `##` 섹션 6~7개 · 불릿 · 링크)이므로 이
범위로 충분하고, 모르는 문법은 평문으로 흘린다.

**HTML을 반드시 이스케이프한다.** 위키 본문은 LLM이 만들고 사용자가 편집하는, 신뢰할 수
없는 입력이다. 편집을 범위에 넣은 이상 XSS 방어가 필수다 (§4.9).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

__all__ = [
    "RELATED_MARKER_END",
    "RELATED_MARKER_START",
    "Document",
    "MarkerMissingError",
    "render",
    "split_front_matter",
    "validate_editable",
]

#: 「관련 문서」 블록을 감싸는 기계 관리 마커 (v0.6 §4.5).
RELATED_MARKER_START = "<!-- corpbrain:related:start -->"
RELATED_MARKER_END = "<!-- corpbrain:related:end -->"

#: `[텍스트](대상)` — 대상에 공백과 괄호가 없다고 본다(우리 템플릿이 그렇게 쓴다).
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
#: `` `코드` ``
_CODE = re.compile(r"`([^`]+)`")

#: `file://` 링크는 «폴더 열기» 버튼이 된다 — `_source_link()` 참조.
#: 대상에 **공백을 허용한다** — 실제 문서명에는 공백이 흔한데 범용 `_LINK` 는 허용하지
#: 않아 마크다운 원문이 글자 그대로 화면에 남았다.
_FILE_LINK = re.compile(r"\[([^\]]+)\]\((file://[^)]+)\)")
_FILE_SCHEME = "file://"
#: `file:///D:/...` 처럼 드라이브 문자 앞에 슬래시가 하나 더 붙은 형태.
_WINDOWS_DRIVE = re.compile(r"^/[A-Za-z]:")

#: 링크 대상으로 허용하는 스킴. **`javascript:` 를 막는 것이 목적이다.**
_SAFE_LINK = re.compile(r"^(?:[.#/]|https?://|file://|mailto:)", re.IGNORECASE)


class MarkerMissingError(ValueError):
    """편집 본문에 「관련 문서」 마커가 없다 — 저장을 거절한다 (§4.9)."""


@dataclass(frozen=True)
class Document:
    """front-matter 와 본문을 가른 결과."""

    front_matter: dict[str, str]
    body: str


def split_front_matter(text: str) -> Document:
    """`---` 로 둘러싸인 front-matter 를 갈라낸다.

    없으면 전부 본문으로 본다 — 사용자가 편집하다 지웠을 수 있고, 그것 때문에 화면이 통째로
    실패하면 안 된다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return Document(front_matter={}, body=text)
    try:
        end = lines.index("---", 1)
    except ValueError:
        return Document(front_matter={}, body=text)

    front: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if not sep:
            continue
        raw = value.strip()
        if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
            front[key.strip()] = _unquote(raw[1:-1])
        else:
            front[key.strip()] = raw
    return Document(front_matter=front, body="\n".join(lines[end + 1 :]).lstrip("\n"))


def _unquote(value: str) -> str:
    r"""`render._quote` 가 넣은 이스케이프를 되돌린다 — 이 함수가 그 짝이다.

    front-matter 의 `source_path` 는 **원문 절대경로**이고, 렌더러가 백슬래시와 큰따옴표를
    이스케이프해 적는다. 따옴표만 벗기면 Windows 경로가 `D:\\프로젝트\\a.md` 처럼 백슬래시
    두 개로 남아, 그래프 노드 id(원문 절대경로 그대로)와 **문자열이 달라진다** — 목록에서
    고른 문서의 강조가 오류 없이 조용히 빗나간다. POSIX 경로에는 백슬래시가 없어 이 결함이
    드러나지 않았다.
    """
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value) and value[index + 1] in '\\"':
            out.append(value[index + 1])
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def render(markdown: str) -> str:
    """마크다운을 HTML 조각으로 만든다. **모든 텍스트를 이스케이프한다.**

    지원하는 것은 우리 템플릿이 실제로 쓰는 것뿐이다 — `#`~`######` 헤딩, `-`/`*` 불릿,
    문단, 인라인 코드, 링크. 나머지 문법은 평문으로 흘린다.
    """
    out: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if bullets:
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in bullets) + "</ul>")
            bullets.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush()
            continue
        if stripped.startswith("<!--"):
            # 기계 관리 마커는 화면에 내지 않는다 — CommonMark 주석이라 원래 보이지 않는다.
            flush()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet:
            bullets.append(_inline(bullet.group(1)))
            continue

        flush()
        out.append(f"<p>{_inline(stripped)}</p>")

    flush()
    return "".join(out)


def _inline(text: str) -> str:
    """인라인 문법을 처리한다 — **이스케이프가 먼저다.**

    순서가 중요하다. 이스케이프를 나중에 하면 우리가 만든 태그까지 문자열로 바뀌고, 먼저
    하면 사용자 입력의 `<script>` 가 태그가 될 길이 사라진다.
    """
    escaped = html.escape(text, quote=True)
    escaped = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    # `file://` 를 **먼저** 잡는다 — 대상에 공백이 있어도 매칭되어야 한다.
    escaped = _FILE_LINK.sub(_source_link, escaped)
    return _LINK.sub(_link, escaped)


def _source_link(match: re.Match[str]) -> str:
    """위키 「원문」 섹션의 `file://` 링크를 **폴더를 여는 버튼**으로 낸다.

    두 가지를 함께 고친다.

    1. **죽은 링크였다.** 브라우저는 `http://` 페이지에서 `file://` 로 가는 링크를 오류도
       없이 조용히 무시한다. 서버가 대신 폴더를 열 수 있으므로(`POST …/reveal`) 그것을
       부르는 버튼으로 바꾼다.
    2. **경로에 공백이 있으면 링크로 인식조차 되지 않았다.** 범용 `_LINK` 는 대상에 공백을
       허용하지 않아(우리 템플릿의 다른 링크는 공백이 없다), `02. 환경설정 가이드.docx`
       같은 실제 문서명에서 마크다운 원문이 글자 그대로 화면에 남았다. 그래서 이 패턴을
       따로 두고 **먼저** 적용한다.

    **문구는 마크다운에 적힌 것을 그대로 쓴다** [사용자 결정 · 2026-09-02]. 이 화면이 보여
    주는 것은 위키 문서 자체이므로, 화면이 위키의 글을 고쳐 쓰지 않는다. 경로를 덧붙이지도
    않는다 — 이미 위키가 적어 둔 것 외의 글자를 화면이 지어내는 셈이 된다.

    위키 **파일 자체는 바뀌지 않는다** — 마크다운에는 종전대로 `file://` 링크가 있다.
    """
    label, target = match.group(1), match.group(2)
    path = target[len(_FILE_SCHEME) :]
    if _WINDOWS_DRIVE.match(path):
        # `file:///D:/...` 형태. POSIX 절대경로(`/home/...`)의 앞 슬래시는 남겨야 하므로
        # 드라이브 문자가 뒤따를 때만 하나 뗀다.
        path = path[1:]
    # 두 문자열 모두 이미 `html.escape(quote=True)` 를 거쳐 왔으므로 그대로 둔다.
    return f'<button type="button" class="reveal" data-path="{path}">{label}</button>'


def _link(match: re.Match[str]) -> str:
    """`[텍스트](대상)`. 대상 스킴을 확인한다 — `javascript:` 를 막는다."""
    label, target = match.group(1), match.group(2)
    if not _SAFE_LINK.match(target):
        # 허용되지 않은 스킴은 링크로 만들지 않고 글자로 남긴다.
        return match.group(0)
    return f'<a href="{target}">{label}</a>'


def validate_editable(text: str) -> None:
    """편집 저장 전 검사 — 마커 블록이 보존됐는가 (§4.9).

    마커가 사라지면 다음 스캔이 「관련 문서」 블록을 하나 더 추가해 섹션이 중복된다.
    v0.6이 헤딩 문자열 탐색 대신 마커를 쓰기로 한 결정이 여기서도 값을 한다.

    Raises:
        MarkerMissingError: 여는 마커나 닫는 마커가 없거나, 순서가 뒤집혔다.
    """
    start = text.find(RELATED_MARKER_START)
    end = text.find(RELATED_MARKER_END)
    if start < 0 or end < 0 or end < start:
        raise MarkerMissingError(
            "「관련 문서」 마커를 지우면 저장할 수 없습니다 — "
            f"{RELATED_MARKER_START} 와 {RELATED_MARKER_END} 를 그대로 두세요."
        )
