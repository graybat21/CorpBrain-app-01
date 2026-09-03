"""최소 마크다운 렌더러 (v0.9 스펙 §4.9).

라이브러리를 쓰지 않는다 — 그러면 §4.2의 「신규 런타임 의존성 0개」가 깨진다. 위키는 코드가
소유한 **고정 템플릿**(front-matter · `#` 제목 · `##` 섹션 6~7개 · 불릿 · 링크)이므로 이
범위로 충분하고, 모르는 문법은 평문으로 흘린다.

**HTML을 반드시 이스케이프한다.** 위키 본문은 LLM이 만들고 사용자가 편집하는, 신뢰할 수
없는 입력이다. 편집을 범위에 넣은 이상 XSS 방어가 필수다 (§4.9).
"""

from __future__ import annotations

import html
import posixpath
import re
from collections.abc import Callable
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

#: `` `코드` ``
_CODE = re.compile(r"`([^`]+)`")

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


def render(markdown: str, *, base: str = "") -> str:
    """마크다운을 HTML 조각으로 만든다. **모든 텍스트를 이스케이프한다.**

    지원하는 것은 우리 템플릿이 실제로 쓰는 것뿐이다 — `#`~`######` 헤딩, `-`/`*` 불릿,
    문단, 인라인 코드, 링크. 나머지 문법은 평문으로 흘린다.

    Args:
        base: 이 마크다운이 놓인 위키의 `out_dir` 기준 상대경로. 「관련 문서」 링크가 **그
            파일 기준** 상대경로라(v0.6 §4.5) 이것이 있어야 어느 위키를 가리키는지 풀린다.
            비우면 링크 대상을 그대로 쓴다.
    """
    out: list[str] = []
    bullets: list[str] = []
    in_related = False

    def flush() -> None:
        if bullets:
            # 「관련 문서」 목록은 표시 규칙이 다르다(한 줄 유지) — 클래스로 갈라 준다.
            # 한 줄 유지는 **안쪽 상자**가 맡는다. `li` 에 `overflow` 를 걸면 목록 점(마커)이
            # 함께 잘려 사라진다 — 마커는 `li` 상자 **밖**에 그려지기 때문이다.
            css, open_i, close_i = (
                (' class="rel"', '<li><span class="rline">', "</span></li>")
                if in_related
                else ("", "<li>", "</li>")
            )
            out.append(
                f"<ul{css}>"
                + "".join(f"{open_i}{item}{close_i}" for item in bullets)
                + "</ul>"
            )
            bullets.clear()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush()
            continue
        if stripped.startswith("<!--"):
            # 기계 관리 마커는 화면에 내지 않는다 — CommonMark 주석이라 원래 보이지 않는다.
            # 다만 **어디까지가 「관련 문서」인지**는 이 마커로만 알 수 있다. 헤딩 문자열을
            # 찾아 가르지 않는 이유는 v0.6 §4.5 가 마커를 도입한 이유와 같다 — 요약 본문에
            # 같은 헤딩이 들어간 문서가 실제로 있다.
            flush()
            if stripped.startswith(RELATED_MARKER_START):
                in_related = True
            elif stripped.startswith(RELATED_MARKER_END):
                in_related = False
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet:
            item = bullet.group(1)
            bullets.append(_related_item(item, base) if in_related else _inline(item))
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
    whole = _whole_line_link(escaped)
    return whole if whole is not None else _scan_links(escaped, _body_link)


def _whole_line_link(text: str) -> str | None:
    """줄 전체가 링크 하나인 경우 — 대상을 **줄 끝까지** 읽는다.

    위키의 「원문」 줄이 그렇다(`[원본 파일 열기](file://…)`). 대상이 사용자의 파일 경로라
    괄호 짝이 맞지 않을 수 있는데(`회의록 1차).docx` · `회의록 (1차.docx`), 줄 전체가 링크
    하나라면 **마지막 `)` 가 대상의 끝임이 확실하다** — 괄호를 셀 필요가 없다. 실측에서
    이 두 이름이 각각 경로 잘림과 링크 실패를 냈다.

    `](` 가 두 번 이상 나오면 한 줄에 링크가 여럿이라는 뜻이므로 이 지름길을 쓰지 않고
    괄호를 세는 `_scan_links()` 에 맡긴다.
    """
    if not text.startswith("[") or not text.endswith(")") or text.count("](") != 1:
        return None
    opened = text.index("](")
    return _body_link(text[1:opened], text[opened + 2 : -1])


def _scan_links(text: str, make: Callable[[str, str], str | None]) -> str:
    r"""`[라벨](대상)` 을 찾아 `make(라벨, 대상)` 이 돌려주는 HTML 로 바꾼다.

    **정규식을 쓰지 않는다.** 대상에 괄호가 들어갈 수 있기 때문이다 — `[^)]+` 는 첫 `)`
    에서 끊겨 `…환경조사서_(출장형` 같은 **반토막 경로**를 만들고, 그 경로로 위키를 열면
    「그런 위키가 없습니다」가 뜬다(실측). 실제 문서명에 `(출장형)` 같은 괄호는 흔하다.
    여는 괄호를 세어 짝이 맞는 자리까지 읽으므로 중첩된 괄호도 견딘다.

    `make` 가 `None` 을 돌려주면 그 자리는 마크다운 원문 그대로 남긴다.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        start = text.find("[", index)
        if start < 0:
            out.append(text[index:])
            return "".join(out)
        close = text.find("]", start + 1)
        if close < 0 or close + 1 >= length or text[close + 1] != "(":
            out.append(text[index : start + 1])
            index = start + 1
            continue

        depth = 1
        cursor = close + 2
        while cursor < length and depth:
            if text[cursor] == "(":
                depth += 1
            elif text[cursor] == ")":
                depth -= 1
            cursor += 1
        if depth:                       # 닫는 괄호가 없다 — 링크가 아니다
            out.append(text[index : start + 1])
            index = start + 1
            continue

        made = make(text[start + 1 : close], text[close + 2 : cursor - 1])
        out.append(text[index:cursor] if made is None else text[index:start] + made)
        index = cursor
    return "".join(out)


def _body_link(label: str, target: str) -> str | None:
    """본문의 링크. `file://` 는 «폴더 열기» 버튼, 나머지는 스킴을 확인해 `<a>` 로 낸다."""
    if target.startswith(_FILE_SCHEME):
        return _source_button(label, target)
    if not _SAFE_LINK.match(target):
        # 허용되지 않은 스킴은 링크로 만들지 않고 글자로 남긴다 (`javascript:` 차단).
        return None
    return f'<a href="{target}">{label}</a>'


def _source_button(label: str, target: str) -> str:
    """위키 「원문」 섹션의 `file://` 링크를 **폴더를 여는 버튼**으로 낸다.

    두 가지를 함께 고친다.

    1. **죽은 링크였다.** 브라우저는 `http://` 페이지에서 `file://` 로 가는 링크를 오류도
       없이 조용히 무시한다. 서버가 대신 폴더를 열 수 있으므로(`POST …/reveal`) 그것을
       부르는 버튼으로 바꾼다.
    2. **경로에 공백·괄호가 있으면 링크로 인식조차 되지 않았다.** 정규식이 대상에 공백을
       허용하지 않았고, 허용한 뒤에도 첫 `)` 에서 끊겨 반토막 경로가 됐다. 지금은
       `_scan_links()` 가 괄호 짝을 세어 읽는다.

    **문구는 마크다운에 적힌 것을 그대로 쓴다** [사용자 결정 · 2026-09-02]. 이 화면이 보여
    주는 것은 위키 문서 자체이므로, 화면이 위키의 글을 고쳐 쓰지 않는다. 경로를 덧붙이지도
    않는다 — 이미 위키가 적어 둔 것 외의 글자를 화면이 지어내는 셈이 된다.

    위키 **파일 자체는 바뀌지 않는다** — 마크다운에는 종전대로 `file://` 링크가 있다.
    """
    path = target[len(_FILE_SCHEME) :]
    if _WINDOWS_DRIVE.match(path):
        # `file:///D:/...` 형태. POSIX 절대경로(`/home/...`)의 앞 슬래시는 남겨야 하므로
        # 드라이브 문자가 뒤따를 때만 하나 뗀다.
        path = path[1:]
    # 두 문자열 모두 이미 `html.escape(quote=True)` 를 거쳐 왔으므로 그대로 둔다.
    return f'<button type="button" class="reveal" data-path="{path}">{label}</button>'


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


def _related_item(text: str, base: str) -> str:
    """「관련 문서」 한 줄. 링크를 **그 위키를 여는 버튼**으로 낸다.

    `<a href="개발/설계.md.md">` 로 두면 브라우저가 서버의 그 주소로 이동해 버린다 —
    위키는 정적 파일이 아니라 API 로 받아 화면 안에서 여는 것이다. `file://` 링크를 폴더
    열기 버튼으로 바꾼 것과 같은 이유이며, 버튼이라 `javascript:` 같은 스킴이 실행될 길도
    애초에 없다.
    """
    escaped = html.escape(text, quote=True)
    escaped = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    split = _split_related(escaped)
    if split is None:
        return escaped
    label, target, tail = split
    return _wiki_button(label, target, base) + tail


def _split_related(item: str) -> tuple[str, str, str] | None:
    """「관련 문서」 한 줄을 `제목` · `대상` · `근거` 셋으로 가른다.

    이 줄의 **형식은 우리가 소유한다** — `render_related_block()` 이 언제나
    `[제목](대상)` 뒤에 근거를 ` — …` 로 덧붙인다(근거가 없으면 링크뿐이다). 그 사실을 쓰면
    일반 마크다운 파서보다 훨씬 넓게 견딜 수 있다. 제목도 대상도 **사용자의 글자**라
    괄호·대괄호가 짝이 맞지 않을 수 있기 때문이다(실측한 실패 셋):

    - 대상에 여는 괄호만 있으면(`회의록 (1차.docx`) 괄호를 세는 방식은 짝을 못 찾아 링크
      자체를 포기했다.
    - 닫는 괄호만 있으면(`회의록 1차).docx`) 그 자리에서 끊겨 **조용히 엉뚱한 경로**가 됐다.
      에러가 아니라 잘못된 링크라 더 나쁘다.
    - 제목에 `]` 가 있으면(`[대외비] 보안진단 결과`) 제목이 거기서 끊겨 링크가 깨졌다.

    그래서 이렇게 가른다. 줄은 `[` 로 시작하고, 제목과 대상의 경계는 **마지막 `](`** 이며,
    대상을 닫는 괄호는 **그 뒤가 줄 끝이거나 ` — ` 인 첫 `)`** 다. 뒤를 함께 보므로 대상
    안의 `)` 와 근거 안의 `)`(태그 이름이 `설계(안)` 인 경우)를 둘 다 넘긴다.

    형식에 맞지 않으면 `None` 을 돌려주고 호출자가 글자 그대로 남긴다 — 사람이 손으로
    고쳐 쓴 줄을 억지로 링크로 만들지 않는다.
    """
    if not item.startswith("["):
        return None
    opened = item.rfind("](")
    if opened < 0:
        return None
    rest = item[opened + 2 :]
    for index, char in enumerate(rest):
        if char != ")":
            continue
        tail = rest[index + 1 :]
        if tail and not tail.startswith(" — "):
            continue
        return item[1:opened], rest[:index], tail
    return None


def _wiki_button(label: str, target: str, base: str) -> str:
    path = html.escape(_resolve_wiki_link(base, html.unescape(target)), quote=True)
    return f'<button type="button" class="wikilink" data-path="{path}">{label}</button>'


def _resolve_wiki_link(base: str, target: str) -> str:
    """`그 위키 파일 기준` 상대경로를 `out_dir` 기준 상대경로로 되돌린다.

    예: `인사/온보딩.md.md` 안의 `../개발/설계.md.md` → `개발/설계.md.md`.
    같은 폴더의 `채용계획.docx.md` → `인사/채용계획.docx.md`.
    """
    folder = posixpath.dirname(base.replace("\\", "/"))
    joined = posixpath.join(folder, target) if folder else target
    return posixpath.normpath(joined)
