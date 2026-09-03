"""마크다운 렌더러 단위 테스트 (v0.9 스펙 §3 항목8·9 · §4.9).

위키 본문은 **LLM이 만들고 사용자가 편집하는 신뢰할 수 없는 입력**이다. 편집을 범위에
넣은 이상 XSS 방어가 필수다.
"""

from __future__ import annotations

import pytest

from corpbrain.core import render
from corpbrain.core.models import ReferenceDirection, RelatedDocument, SummaryResult
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


def test_related_links_become_buttons_that_open_the_wiki() -> None:
    """「관련 문서」 링크는 **그 위키를 여는 버튼**이 된다.

    세 가지가 함께 걸려 있었다.

    1. `<a href="개발/설계.md.md">` 로 두면 브라우저가 서버의 그 주소로 이동한다 — 위키는
       API 로 받아 화면 안에서 여는 것이지 정적 파일이 아니다.
    2. 같은 폴더의 문서는 대상이 `채용계획.docx.md` 처럼 `./` 없이 시작해 `_SAFE_LINK` 가
       거부했고, 마크다운 원문이 **글자 그대로** 화면에 남았다.
    3. 위키 파일명은 원본 이름을 그대로 이어 붙여 공백이 흔한데, 범용 링크 패턴은 대상에
       공백을 허용하지 않아 역시 글자로 남았다.

    링크 대상은 **그 위키 파일 기준** 상대경로이므로(v0.6 §4.5) `base` 로 풀어 준다.
    """
    body = f"""{md.RELATED_MARKER_START}
## 관련 문서
- [설계](../개발/설계.md.md) — 유사도 0.81
- [채용계획](채용계획.docx.md) — 공유 태그 `인사`
- [가이드](02. 환경설정 가이드.docx.md) — 이 문서가 참조함
{md.RELATED_MARKER_END}"""

    out = md.render(body, base="인사/온보딩.md.md")

    assert '<button type="button" class="wikilink" data-path="개발/설계.md.md">설계</button>' in out
    assert 'data-path="인사/채용계획.docx.md">채용계획</button>' in out
    assert 'data-path="인사/02. 환경설정 가이드.docx.md">가이드</button>' in out
    # 근거는 글자 그대로 남는다 — 백틱은 종전대로 `<code>` 가 된다.
    assert "유사도 0.81" in out and "<code>인사</code>" in out
    assert "[설계]" not in out          # 마크다운 원문이 남지 않는다


def test_related_link_rendering_is_scoped_to_the_marker_block() -> None:
    """마커 밖의 링크는 종전대로 `<a>` 다 — 「관련 문서」만 버튼이 된다."""
    out = md.render("- [바깥](https://example.test) 링크", base="a.md.md")

    assert '<a href="https://example.test">바깥</a>' in out
    assert "wikilink" not in out


def test_link_targets_survive_parentheses() -> None:
    """대상에 괄호가 있어도 경로가 반토막 나지 않는다.

    정규식 `[^)]+` 는 첫 `)` 에서 끊겨 `…환경조사서_(출장형` 을 만들고, 그 경로로 위키를
    열면 「그런 위키가 없습니다」가 뜬다 — 실사용에서 실제로 났다. `(출장형)` 같은 괄호는
    실제 문서명에 흔하다. 「관련 문서」와 「원문」 두 경로 모두에 걸린 결함이라 스캐너
    하나로 함께 고친다.
    """
    related = f"""{md.RELATED_MARKER_START}
## 관련 문서
- [보안진단 환경조사서(출장형)](../보안점검/보안약점 진단 환경조사서_(출장형)_초록소프트.docx.md) — 공유 엔티티 `인사팀`
{md.RELATED_MARKER_END}"""

    out = md.render(related, base="WEPLTO/온보딩.md.md")

    assert 'data-path="보안점검/보안약점 진단 환경조사서_(출장형)_초록소프트.docx.md"' in out
    assert ">보안진단 환경조사서(출장형)</button>" in out

    source = "[원본 파일 열기](file:///D:/문서/조사서_(출장형)_초록.docx)"
    assert 'data-path="D:/문서/조사서_(출장형)_초록.docx"' in md.render(source)


def test_related_list_is_marked_for_single_line_display() -> None:
    """「관련 문서」 목록만 한 줄 유지 규칙을 받는다 — 요약 본문의 불릿은 그대로 접힌다."""
    body = f"""## 핵심 포인트
- 본문 불릿
{md.RELATED_MARKER_START}
## 관련 문서
- [문서](문서.md.md) — 공유 태그 `인사`
{md.RELATED_MARKER_END}"""

    out = md.render(body, base="a.md.md")

    assert "<ul><li>본문 불릿</li></ul>" in out
    assert '<ul class="rel">' in out
    # 줄임은 **안쪽 상자**가 맡는다 — `li` 에 걸면 목록 점(마커)이 함께 잘린다.
    assert '<li><span class="rline">' in out


@pytest.mark.parametrize(
    ("title", "target", "expected"),
    [
        ("제목", "보고서(1)(최종)-정리.docx.md", "a/보고서(1)(최종)-정리.docx.md"),
        ("제목", "[2026] 계획-초안.docx.md", "a/[2026] 계획-초안.docx.md"),
        ("제목", "조사서_((출장형))_초록.docx.md", "a/조사서_((출장형))_초록.docx.md"),
        # 괄호 짝이 맞지 않는 이름 — 세는 방식으로는 풀 수 없다.
        ("제목", "회의록 (1차.docx.md", "a/회의록 (1차.docx.md"),
        ("제목", "회의록 1차).docx.md", "a/회의록 1차).docx.md"),
        # 제목에 대괄호 — 제목이 거기서 끊기면 안 된다.
        ("[대외비] 보안진단 결과", "보고서.docx.md", "a/보고서.docx.md"),
    ],
)
def test_related_links_survive_brackets_in_names(title: str, target: str, expected: str) -> None:
    """제목과 파일 이름에 `[]()` 가 섞여도 링크가 정확히 이어진다.

    줄의 **형식은 우리가 소유하므로**(`[제목](대상) — 근거`) 그 사실로 가른다 — 마지막
    `](` 가 경계이고, 대상을 닫는 괄호는 그 뒤가 줄 끝이거나 ` — ` 인 첫 `)` 다. 괄호를
    세는 방식은 짝이 맞지 않는 이름에서 링크를 통째로 포기하거나(`회의록 (1차.docx`),
    더 나쁘게는 **조용히 잘린 경로**를 만들었다(`회의록 1차).docx` → `회의록 1차`).
    """
    body = f"""{md.RELATED_MARKER_START}
## 관련 문서
- [{title}]({target}) — 공유 태그 `인사`
{md.RELATED_MARKER_END}"""

    out = md.render(body, base="a/b.md.md")

    assert f'data-path="{expected}"' in out
    assert f">{title}</button>" in out


def test_related_evidence_may_contain_parentheses() -> None:
    """근거의 태그 이름에 괄호가 있어도 대상이 거기까지 늘어나지 않는다."""
    body = f"""{md.RELATED_MARKER_START}
## 관련 문서
- [제목](보고서.docx.md) — 공유 태그 `설계(안)`
{md.RELATED_MARKER_END}"""

    assert 'data-path="a/보고서.docx.md"' in md.render(body, base="a/b.md.md")


@pytest.mark.parametrize(
    "path",
    ["D:/문서/회의록 1차).docx", "D:/문서/회의록 (1차.docx", "D:/문서/보고서(1)(최종).docx"],
)
def test_source_button_survives_unbalanced_parentheses(path: str) -> None:
    """「원문」 줄도 같은 결함을 안고 있었다 — 줄 전체가 링크이므로 끝까지 읽는다."""
    out = md.render(f"[원본 파일 열기](file:///{path})")

    assert f'data-path="{path}"' in out


def test_two_links_on_one_line_still_parse_separately() -> None:
    """줄 전체 지름길이 **여러 링크가 든 줄을 삼키지 않는다.**"""
    out = md.render("[a](./a.md) 와 [b](./b.md)")

    assert '<a href="./a.md">a</a>' in out and '<a href="./b.md">b</a>' in out


def test_gui_reads_exactly_what_the_core_writes() -> None:
    """**코어가 쓴 줄을 그대로 먹여 본다** — 손으로 적은 문자열이 아니라.

    GUI 파서는 「이 줄은 `[제목](대상) — 근거` 형식이다」를 전제로 가른다. 그 형식을
    소유한 것은 `corpbrain.core.render` 이므로, 두 곳이 어긋나면 화면이 **조용히** 엉뚱한
    문서를 열게 된다 — 링크가 깨지는 것보다 나쁘다.

    이 테스트가 그 연결을 **소리 나게** 만든다. 근거 구분자(` — `)나 줄 형식을 코어에서
    바꾸면 여기서 깨진다. 파서를 코어 형식에 맞춘 이상, 그 결합을 없앨 수는 없고 드러나게
    둘 수는 있다.
    """
    related = [
        RelatedDocument(
            doc_id="/원본/보안점검/조사서_(출장형)_초록.docx",
            title="[대외비] 조사서(출장형)",
            similarity=0.81,
            shared_tags=["설계(안)"],
        ),
        RelatedDocument(
            doc_id="/원본/기타/회의록 1차).docx",
            title="회의록",
            reference=ReferenceDirection.OUTGOING,
        ),
    ]
    block = render.render_related_block(
        related,
        relative_to="인사/온보딩.md.md",
        relative_paths={
            "/원본/보안점검/조사서_(출장형)_초록.docx": "보안점검/조사서_(출장형)_초록.docx.md",
            "/원본/기타/회의록 1차).docx": "기타/회의록 1차).docx.md",
        },
    )

    out = md.render(block, base="인사/온보딩.md.md")

    assert 'data-path="보안점검/조사서_(출장형)_초록.docx.md"' in out
    assert 'data-path="기타/회의록 1차).docx.md"' in out
    assert ">[대외비] 조사서(출장형)</button>" in out
    # 근거는 링크 밖에 그대로 남는다.
    assert "유사도 0.81" in out and "<code>설계(안)</code>" in out
    assert "이 문서가 참조함" in out
