"""마크다운 렌더러 단위 테스트 (v0.9 스펙 §3 항목8·9 · §4.9).

위키 본문은 **LLM이 만들고 사용자가 편집하는 신뢰할 수 없는 입력**이다. 편집을 범위에
넣은 이상 XSS 방어가 필수다.
"""

from __future__ import annotations

import pytest

from corpbrain.core import render
from corpbrain.core.models import SummaryResult
from corpbrain.gui import markdown as md

# --- 이스케이프 (스펙 §3 항목8) --------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        '<img src=x onerror="alert(1)">',
        "<iframe src='evil'></iframe>",
        "<svg/onload=alert(1)>",
    ],
)
def test_html_in_the_body_is_escaped(payload: str) -> None:
    """요약문에 태그가 들어와도 태그가 되지 않는다."""
    out = md.render(payload)

    assert "<script" not in out
    assert "<img" not in out
    assert "<iframe" not in out
    assert "<svg" not in out
    assert "&lt;" in out


def test_html_inside_a_heading_is_escaped() -> None:
    out = md.render("# <script>alert(1)</script>")

    assert out.startswith("<h1>")
    assert "&lt;script&gt;" in out


def test_html_inside_a_bullet_is_escaped() -> None:
    out = md.render("- <b>굵게</b>")

    assert "<li>" in out
    assert "&lt;b&gt;" in out


def test_javascript_links_are_not_rendered_as_links() -> None:
    """`javascript:` 스킴은 링크로 만들지 않는다 — 글자로 남긴다."""
    out = md.render("[클릭](javascript:alert(1))")

    assert "<a href" not in out
    assert "javascript" in out


@pytest.mark.parametrize(
    "target", ["./a.md", "../개발/설계.md.md", "#section", "/절대", "https://example.com"]
)
def test_safe_link_targets_are_rendered(target: str) -> None:
    out = md.render(f"[제목]({target})")

    assert f'<a href="{target}">제목</a>' in out


def test_quotes_in_text_cannot_break_out_of_an_attribute() -> None:
    """따옴표까지 이스케이프한다 — 속성 밖으로 탈출할 길을 남기지 않는다."""
    out = md.render('본문에 " 따옴표가 있다')

    assert '"' not in out.replace("&quot;", "")


# --- 렌더 (§4.9) -----------------------------------------------------------------


def test_headings_bullets_and_paragraphs() -> None:
    out = md.render("# 제목\n\n## 한 줄 요약\n문단이다\n\n- 하나\n- 둘\n")

    assert "<h1>제목</h1>" in out
    assert "<h2>한 줄 요약</h2>" in out
    assert "<p>문단이다</p>" in out
    assert "<ul><li>하나</li><li>둘</li></ul>" in out


def test_inline_code_is_rendered() -> None:
    assert "<code>인사</code>" in md.render("태그 `인사` 이다")


def test_markers_are_not_shown() -> None:
    """기계 관리 마커는 화면에 내지 않는다 — CommonMark 주석이라 원래 보이지 않는다."""
    out = md.render(f"{md.RELATED_MARKER_START}\n## 관련 문서\n{md.RELATED_MARKER_END}")

    assert "corpbrain:related" not in out
    assert "<h2>관련 문서</h2>" in out


def test_unknown_syntax_falls_through_as_text() -> None:
    """모르는 문법은 평문으로 흘린다 — 우리 템플릿 밖의 입력에서 실패하지 않는다."""
    out = md.render("| 표 | 헤더 |\n|---|---|")

    assert "<p>" in out


def test_source_link_becomes_a_button_that_keeps_the_wiki_wording() -> None:
    r"""「원문」의 `file://` 링크는 **폴더를 여는 버튼**이 된다.

    브라우저는 `http://` 페이지에서 `file://` 로 가는 링크를 오류도 없이 조용히 무시한다 —
    눌러도 아무 일이 없는 죽은 링크였다. 서버가 대신 폴더를 열 수 있으므로 그것을 부르는
    버튼으로 바꾼다.

    **문구는 위키에 적힌 것을 그대로 쓴다** [사용자 결정 · 2026-09-02]. 이 화면이 보여 주는
    것은 위키 문서 자체이므로, 화면이 위키의 글을 고쳐 쓰거나 없던 글자(경로 등)를 덧붙이지
    않는다.
    """
    path = r"D:\프로젝트\하와이 관광 이관문서\02. 환경설정 및 배포 가이드.docx"

    out = md.render(f"[원본 파일 열기](file://{path})")

    assert out == (
        f'<p><button type="button" class="reveal" data-path="{path}">원본 파일 열기</button></p>'
    )


def test_source_link_survives_spaces_in_the_path() -> None:
    """경로에 공백이 있어도 인식한다.

    범용 링크 패턴은 대상에 공백을 허용하지 않아(우리 템플릿의 다른 링크는 공백이 없다),
    `02. 환경설정 가이드.docx` 같은 **실제 문서명**에서 마크다운 원문이 글자 그대로 화면에
    남아 있었다.
    """
    out = md.render(r"[원본 파일 열기](file:///home/me/내 문서/보고 자료.docx)")

    assert "[원본 파일 열기](" not in out                     # 원문이 그대로 남지 않는다
    assert 'data-path="/home/me/내 문서/보고 자료.docx"' in out   # 앞 슬래시를 지키다


def test_windows_drive_keeps_no_leading_slash() -> None:
    """`file:///D:/...` 의 앞 슬래시는 뗀다 — POSIX 절대경로의 것은 남긴다."""
    assert 'data-path="D:/x/a.md"' in md.render("[원본 파일 열기](file:///D:/x/a.md)")


def test_other_links_are_still_plain_anchors() -> None:
    """`file://` 만 버튼이 된다. 「관련 문서」의 상대경로 링크는 종전 그대로다."""
    out = md.render("[설계](../개발/설계.md.md)")

    assert out == '<p><a href="../개발/설계.md.md">설계</a></p>'


# --- front-matter ---------------------------------------------------------------


def test_front_matter_is_split_off() -> None:
    document = md.split_front_matter(
        '---\nsource_path: "C:/docs/a.md"\nmodel: "m"\n---\n\n# 제목\n'
    )

    assert document.front_matter["source_path"] == "C:/docs/a.md"
    assert document.front_matter["model"] == "m"
    assert document.body.startswith("# 제목")


def test_missing_front_matter_is_all_body() -> None:
    """사용자가 편집하다 지웠을 수 있다 — 그것 때문에 화면이 실패하면 안 된다."""
    document = md.split_front_matter("# 제목만 있다\n")

    assert document.front_matter == {}
    assert document.body.startswith("# 제목만")


def test_front_matter_source_path_round_trips_a_windows_path() -> None:
    r"""`render._quote` 가 넣은 이스케이프를 되돌린다 — 그러지 않으면 경로가 달라진다.

    front-matter 의 `source_path` 는 원문 절대경로이고 그래프 노드 id 와 **같은 문자열이어야**
    한다. 따옴표만 벗기면 Windows 경로가 `D:\\프로젝트\\a.md` 로 남아, 탐색 화면에서 목록의
    문서를 고를 때 그래프 강조가 오류 없이 조용히 빗나간다.
    """
    path = r"D:\프로젝트\온보딩.md"
    rendered = render.render_markdown(
        SummaryResult(
            title="제목",
            one_line_summary="한 줄",
            key_points=["가"],
            summary="요약",
            tags=["태그"],
        ),
        source_path=path,
        model="m",
        source_bytes=1,
        generated_at="2026-09-02T00:00:00+09:00",
    )

    assert md.split_front_matter(rendered).front_matter["source_path"] == path


def test_front_matter_keeps_an_escaped_quote() -> None:
    document = md.split_front_matter('---\nsource_path: "a\\"b"\n---\n')

    assert document.front_matter["source_path"] == 'a"b'


def test_unterminated_front_matter_is_all_body() -> None:
    document = md.split_front_matter("---\nsource_path: x\n# 닫는 줄이 없다\n")

    assert document.front_matter == {}


# --- 편집 검증 (스펙 §3 항목9 · §4.9) --------------------------------------------


def test_editable_body_with_markers_passes() -> None:
    md.validate_editable(f"# 제목\n{md.RELATED_MARKER_START}\n{md.RELATED_MARKER_END}\n")


@pytest.mark.parametrize(
    "body",
    [
        "# 마커가 통째로 없다",
        "<!-- corpbrain:related:start -->\n여는 것만 있다",
        "<!-- corpbrain:related:end -->\n닫는 것만 있다",
    ],
)
def test_missing_marker_is_rejected(body: str) -> None:
    """마커가 사라지면 다음 스캔이 블록을 하나 더 추가해 섹션이 중복된다 (§4.9)."""
    with pytest.raises(md.MarkerMissingError):
        md.validate_editable(body)


def test_reversed_markers_are_rejected() -> None:
    with pytest.raises(md.MarkerMissingError):
        md.validate_editable(f"{md.RELATED_MARKER_END}\n{md.RELATED_MARKER_START}")
