"""단위 테스트 — 검색 엔드포인트의 응답 모양 (v0.9 §4.6.1 · IX4).

요지 하나: **갈라지면 안 되는 것은 「어휘」이지 「줄 조립」이 아니다.** 카드가 그릴 값은 필드로
내리고, v0.7이 정확 문자열까지 못박은 확산 근거 줄만 기존 빌더의 결과를 그대로 싣는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from corpbrain.core.models import (
    GraphExpansion,
    ReferenceDirection,
    SearchResult,
)
from corpbrain.core.report import build_expansion_evidence
from corpbrain.gui import api as gui_api
from corpbrain.gui.api import SESSION_COOKIE, GuiApp

PORT = 8765
AUTH: ClassVar = {"Host": f"127.0.0.1:{PORT}", "Cookie": f"{SESSION_COOKIE}=sess"}

SEED = SearchResult(
    doc_id="/원문/인사/온보딩.md",
    score=0.710,
    metadata={"title": "온보딩", "source_path": "/원문/인사/온보딩.md", "tags": ["인사"]},
)
EXPANDED = SearchResult(
    doc_id="/원문/인사/채용계획.docx",
    score=0.568,
    metadata={"title": "채용 계획", "source_path": "/원문/인사/채용계획.docx"},
    expansion=GraphExpansion(
        seed_doc_id="/원문/인사/온보딩.md",
        seed_title="온보딩",
        seed_score=0.710,
        cosine=0.380,
        shared_tags=["인사"],
        shared_entities=["인사팀"],
        reference=ReferenceDirection.MUTUAL,
    ),
)


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GuiApp:
    calls: list[dict[str, Any]] = []

    def _search_index(out_dir: Path, query: str, **kwargs: Any) -> list[SearchResult]:
        calls.append({"out_dir": out_dir, "query": query, **kwargs})
        return [SEED, EXPANDED]

    monkeypatch.setattr(gui_api, "search_index", _search_index)
    instance = GuiApp(
        out_dir=tmp_path / "wiki", token="tok", port=PORT, session_token="sess"
    )
    instance.calls = calls  # type: ignore[attr-defined]
    return instance


def test_results_are_fields_not_a_rendered_line(app: GuiApp) -> None:
    body = app.handle("GET", "/api/search?q=온보딩", AUTH).json()

    assert body["results"][0] == {
        "doc_id": "/원문/인사/온보딩.md",
        "score": 0.710,
        "title": "온보딩",
        "source_path": "/원문/인사/온보딩.md",
        "tags": ["인사"],
        "expansion": None,
    }


def test_expansion_evidence_is_the_builder_string_verbatim(app: GuiApp) -> None:
    """v0.7 §4.6이 정확 문자열까지 못박은 계약 — 한 글자도 갈리지 않는다."""
    body = app.handle("GET", "/api/search?q=온보딩", AUTH).json()

    assert body["results"][1]["expansion"]["evidence"] == build_expansion_evidence(
        EXPANDED.expansion, EXPANDED.score
    )
    # 참조 방향 문구를 프론트가 다시 구현하지 않는다는 것이 이 계약의 요점이다.
    assert "서로 참조함" in body["results"][1]["expansion"]["evidence"]


def test_seed_has_no_evidence_line(app: GuiApp) -> None:
    """근거 줄은 **확산된 문서에만** 붙는다 (v0.7 §4.6)."""
    body = app.handle("GET", "/api/search?q=온보딩", AUTH).json()

    assert body["results"][0]["expansion"] is None


class TestParameterHandling:
    """§4.3.3 — GUI는 검증을 두지 않는다. 타입만 옮기고 값은 그대로 코어로 간다."""

    def test_defaults_match_the_core_signature(self, app: GuiApp) -> None:
        app.handle("GET", "/api/search?q=온보딩", AUTH)

        call = app.calls[0]  # type: ignore[attr-defined]
        assert call["top_k"] == 5
        assert call["graph"] is True
        assert "expand_edges" not in call  # 주지 않으면 코어 기본값이 그대로 쓰인다

    def test_graph_false_is_not_a_truthy_string(self, app: GuiApp) -> None:
        app.handle("GET", "/api/search?q=온보딩&graph=false", AUTH)

        assert app.calls[0]["graph"] is False  # type: ignore[attr-defined]

    def test_out_of_range_decay_goes_to_the_core_untouched(self, app: GuiApp) -> None:
        """범위 판정은 코어가 한다 — 어댑터가 클램프하거나 막지 않는다 (v0.7 §4.4)."""
        app.handle("GET", "/api/search?q=온보딩&graph_decay=1.5", AUTH)

        assert app.calls[0]["graph_decay"] == 1.5  # type: ignore[attr-defined]

    def test_expand_edges_is_parsed_by_the_core_parser(self, app: GuiApp) -> None:
        app.handle("GET", "/api/search?q=온보딩&expand_edges=TAGGED_WITH,REFERENCES", AUTH)

        assert {str(value) for value in app.calls[0]["expand_edges"]} == {  # type: ignore[attr-defined]
            "TAGGED_WITH",
            "REFERENCES",
        }

    def test_lowercase_edge_name_is_a_domain_state(self, app: GuiApp) -> None:
        """소문자를 받아 주지 않는 것은 코어 규칙이며, GUI는 그 판정을 그대로 노출한다."""
        response = app.handle("GET", "/api/search?q=온보딩&expand_edges=tagged_with", AUTH)

        assert response.status == 200
        assert response.json()["error"] == "PreconditionError"

    def test_empty_query_is_400(self, app: GuiApp) -> None:
        assert app.handle("GET", "/api/search?q=%20", AUTH).status == 400

    def test_non_numeric_top_k_is_400(self, app: GuiApp) -> None:
        assert app.handle("GET", "/api/search?q=온보딩&top_k=많이", AUTH).status == 400
