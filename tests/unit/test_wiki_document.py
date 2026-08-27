"""단위 테스트 — `parse_wiki_document()`와 위키 상세 응답 (v0.9 §3 항목8 · §4.6).

입력은 **`render.py`가 실제로 렌더한 위키**다. 손으로 쓴 마크다운을 넣으면 파서가 렌더러와
어긋나도 테스트가 통과한다 — 두 모듈이 같은 섹션 지식을 공유한다는 것이 이 파일의 요지다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from corpbrain.core.embedding_text import parse_wiki_document, parse_wiki_markdown
from corpbrain.core.models import (
    ReferenceDirection,
    RelatedDocument,
    SummaryResult,
    WikiDocument,
)
from corpbrain.core.render import (
    FRONT_MATTER_KEYS,
    SECTION_HEADERS,
    render_markdown,
    render_related_block,
    replace_related_block,
)
from corpbrain.gui.api import SESSION_COOKIE, GuiApp

SUMMARY = SummaryResult(
    title="채용 계획",
    one_line_summary="2026년 상반기 채용 계획 문서다.",
    key_points=["신입 5명", "경력 3명", "면접은 2월"],
    summary="인사팀이 상반기 채용 규모와 일정을 정리했다.",
    tags=["인사", "채용"],
    entities=["인사팀"],
)


def _rendered(source_path: str = "/원문/인사/채용계획.docx") -> str:
    return render_markdown(
        SUMMARY,
        source_path=source_path,
        model="qwen2.5:7b-instruct",
        source_bytes=1234,
        generated_at="2026-08-27T10:00:00+09:00",
        engine="cloud",
    )


class TestParseWikiDocument:
    def test_front_matter_five_keys(self) -> None:
        """front-matter 5키를 전부 낸다 — `engine`을 빼지 않는다 (§4.6)."""
        document = parse_wiki_document(_rendered())

        assert document.source_path == "/원문/인사/채용계획.docx"
        assert document.generated_at == "2026-08-27T10:00:00+09:00"
        assert document.model == "qwen2.5:7b-instruct"
        assert document.engine == "cloud"
        assert document.source_bytes == 1234
        # 렌더러가 쓰는 키 집합과 파서가 내는 필드가 어긋나지 않는다.
        assert set(FRONT_MATTER_KEYS) <= set(vars(document))

    def test_seven_sections(self) -> None:
        document = parse_wiki_document(_rendered())

        assert document.title == "채용 계획"
        assert document.one_line_summary == "2026년 상반기 채용 계획 문서다."
        assert document.key_points == ["신입 5명", "경력 3명", "면접은 2월"]
        assert document.summary == "인사팀이 상반기 채용 규모와 일정을 정리했다."
        assert document.tags == ["인사", "채용"]
        assert document.source_link == "/원문/인사/채용계획.docx"
        # 갓 렌더된 위키의 「관련 문서」는 비어 있다 (`관련 문서 없음`).
        assert document.related == []
        # 7섹션이 모두 필드로 존재한다 — 렌더러의 헤더 튜플과 대응이 어긋나지 않는다.
        assert len(SECTION_HEADERS) == 6  # `# 제목`을 뺀 `## ` 헤더 수

    def test_markers_are_not_shown(self) -> None:
        """기계 관리 마커는 화면에 보일 것이 아니다 (v0.6 §4.5)."""
        document = parse_wiki_document(_rendered())

        assert "corpbrain:related" not in json.dumps(vars(document), default=str)

    def test_related_links_keep_title_href_and_evidence(self) -> None:
        block = render_related_block(
            [
                RelatedDocument(
                    doc_id="/원문/인사/온보딩.md",
                    title="온보딩",
                    similarity=0.81,
                    shared_tags=["인사"],
                    shared_entities=["인사팀"],
                    reference=ReferenceDirection.MUTUAL,
                )
            ],
            relative_to="인사/채용계획.docx.md",
            relative_paths={"/원문/인사/온보딩.md": "인사/온보딩.md.md"},
        )
        document = parse_wiki_document(replace_related_block(_rendered(), block))

        assert len(document.related) == 1
        link = document.related[0]
        assert link.title == "온보딩"
        assert link.href == "온보딩.md.md"
        # 근거 문구는 v0.6·v0.7이 못박은 **어휘**라 그대로 옮긴다.
        assert "서로 참조함" in link.evidence
        # `doc_id`는 위키 본문에 적혀 있지 않으므로 파서가 채우지 않는다 (§4.6 · IX3).
        assert link.doc_id == ""

    def test_broken_input_yields_empty_fields_not_an_exception(self) -> None:
        """위키가 낡았거나 손으로 고쳐졌다고 상세 화면 전체가 실패하지 않는다."""
        document = parse_wiki_document("그냥 텍스트")

        assert document == WikiDocument()


class TestParseWikiMarkdownStaysAThreeTuple:
    """§3 항목8 — 기존 호출부 세 곳의 안전이 여기에 달려 있다 (§4.6)."""

    def test_returns_three_tuple(self) -> None:
        result = parse_wiki_markdown(_rendered())

        assert isinstance(result, tuple)
        assert len(result) == 3
        title, _text, tags = result
        assert title == "채용 계획"
        assert tags == ["인사", "채용"]

    def test_embedding_text_excludes_front_matter_and_generated_sections(self) -> None:
        _title, text, _tags = parse_wiki_markdown(_rendered())

        assert "source_path" not in text
        assert "file://" not in text  # 「원문」 섹션은 임베딩에서 빠진다
        assert "관련 문서" not in text  # 그래프 산출물이 임베딩으로 되먹임되지 않는다
        assert "- " not in text  # 불릿 기호가 남지 않는다


class TestWikiEndpoints:
    PORT = 8765
    AUTH: ClassVar[dict[str, str]] = {
        "Host": f"127.0.0.1:{PORT}",
        "Cookie": f"{SESSION_COOKIE}=sess",
    }

    @pytest.fixture
    def out_dir(self, tmp_path: Path) -> Path:
        out = tmp_path / "wiki"
        (out / "인사").mkdir(parents=True)
        (out / "인사" / "채용계획.docx.md").write_text(_rendered(), encoding="utf-8")
        (out / "인사" / "온보딩.md.md").write_text(
            _rendered("/원문/인사/온보딩.md"), encoding="utf-8"
        )
        return out

    def _app(self, out_dir: Path) -> GuiApp:
        return GuiApp(out_dir=out_dir, token="tok", port=self.PORT, session_token="sess")

    def test_detail_carries_five_keys_and_seven_sections(self, out_dir: Path) -> None:
        response = self._app(out_dir).handle(
            "GET", "/api/wiki/document?doc=/원문/인사/채용계획.docx", self.AUTH
        )

        assert response.status == 200
        body = response.json()
        for key in ("source_path", "generated_at", "model", "engine", "source_bytes"):
            assert key in body
        for key in ("title", "one_line_summary", "key_points", "summary", "tags",
                    "source_link", "related"):
            assert key in body
        assert body["engine"] == "cloud"

    def test_detail_of_an_unknown_document_is_a_domain_state(self, out_dir: Path) -> None:
        response = self._app(out_dir).handle(
            "GET", "/api/wiki/document?doc=/없는/문서.md", self.AUTH
        )

        # 선행 조건 실패는 **200 + 안내 문장**이다 — 4xx로 접지 않는다 (§4.3.2).
        assert response.status == 200
        assert response.json()["error"] == "PreconditionError"

    def test_detail_without_doc_is_400(self, out_dir: Path) -> None:
        response = self._app(out_dir).handle("GET", "/api/wiki/document", self.AUTH)

        assert response.status == 400

    def test_tree_falls_back_to_file_names_without_a_graph(self, out_dir: Path) -> None:
        """§4.6.2 파생 결정 — 라벨을 얻지 못하면 파일명으로 대체하고 그 사실을 알린다."""
        body = self._app(out_dir).handle("GET", "/api/wiki", self.AUTH).json()

        assert body["source"] == "files"
        assert "다시 스캔" in body["message"]
        assert {entry["doc_id"] for entry in body["documents"]} == {
            "/원문/인사/채용계획.docx",
            "/원문/인사/온보딩.md",
        }
        # 키는 `doc_id`이며 그래프 화면·검색과 같은 키다.
        assert body["documents"][0]["directory"] == "/원문/인사"

    def test_related_links_are_resolved_to_doc_ids_by_the_server(
        self, out_dir: Path
    ) -> None:
        """IX3 — 서버가 상대 링크를 풀어 대상 위키의 `source_path`를 읽는다.

        위키 본문에는 `doc_id`가 적혀 있지 않으므로 이 왕복은 사라지는 것이 아니라 프론트에서
        서버로 **옮겨진다**. 프론트가 링크를 파싱하면 경로 해석이 프론트로 넘어가고
        「프론트엔드에 마크다운 파서를 두지 않는다」와도 부딪친다.
        """
        block = render_related_block(
            [RelatedDocument(doc_id="/원문/인사/온보딩.md", title="온보딩", similarity=0.81)],
            relative_to="인사/채용계획.docx.md",
            relative_paths={"/원문/인사/온보딩.md": "인사/온보딩.md.md"},
        )
        target = out_dir / "인사" / "채용계획.docx.md"
        target.write_text(
            replace_related_block(target.read_text(encoding="utf-8"), block),
            encoding="utf-8",
        )

        body = self._app(out_dir).handle(
            "GET", "/api/wiki/document?doc=/원문/인사/채용계획.docx", self.AUTH
        ).json()

        assert body["related"] == [
            {
                "title": "온보딩",
                "doc_id": "/원문/인사/온보딩.md",
                "evidence": "유사도 0.81",
            }
        ]

    def test_unresolvable_related_link_keeps_the_title(self, out_dir: Path) -> None:
        """대상 위키가 사라졌다고 상세 전체를 실패시키지 않는다."""
        block = render_related_block(
            [RelatedDocument(doc_id="/원문/사라진.md", title="사라진 문서")],
            relative_to="인사/채용계획.docx.md",
            relative_paths={"/원문/사라진.md": "없는폴더/사라진.md.md"},
        )
        target = out_dir / "인사" / "채용계획.docx.md"
        target.write_text(
            replace_related_block(target.read_text(encoding="utf-8"), block),
            encoding="utf-8",
        )

        body = self._app(out_dir).handle(
            "GET", "/api/wiki/document?doc=/원문/인사/채용계획.docx", self.AUTH
        ).json()

        assert body["related"][0]["title"] == "사라진 문서"
        assert body["related"][0]["doc_id"] == ""

    def test_tree_on_an_empty_out_dir_is_a_domain_state(self, tmp_path: Path) -> None:
        response = self._app(tmp_path / "없음").handle("GET", "/api/wiki", self.AUTH)

        assert response.status == 200
        assert response.json()["error"] == "PreconditionError"
