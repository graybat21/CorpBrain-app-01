"""`corpbrain graph` CLI 어댑터 (v0.6 스펙 §3 항목3, §4.7).

정확 문자열 단언은 `tests/unit/test_graph_report.py`가 한다. 여기서는 종료 코드와 배선만
확인해, 출력 문구를 다듬을 때 어댑터 테스트가 깨지지 않게 한다
(`tests/test_cli_search.py`가 `assert "먼저" in err` 수준으로만 보는 것과 같다).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain import cli
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.models import (
    DocFacts,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    SummaryResult,
)
from corpbrain.core.render import render_markdown

SOURCE = "/work/docs/개발/설계.md"


def _seed(out_dir: Path, *, with_wiki: bool = True) -> None:
    """그래프 DB와(선택적으로) 대응 위키를 만든다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        store.upsert_facts(
            DocFacts(doc_id=SOURCE, title="설계 문서", tags=["설계"], entities=["코어"])
        )
        store.replace_graph(
            [
                GraphNode(id=SOURCE, type=NodeType.DOCUMENT, label="설계 문서"),
                GraphNode(id="tag:설계", type=NodeType.TAG, label="설계"),
            ],
            [GraphEdge(src=SOURCE, dst="tag:설계", type=EdgeType.TAGGED_WITH)],
        )
    if with_wiki:
        wiki = out_dir / "개발" / "설계.md.md"
        wiki.parent.mkdir(parents=True, exist_ok=True)
        wiki.write_text(
            render_markdown(
                SummaryResult(
                    title="설계 문서",
                    one_line_summary="한 줄",
                    key_points=["a"],
                    summary="요약",
                    tags=["설계"],
                ),
                source_path=SOURCE,
                model="m",
                source_bytes=1,
                generated_at="2026-08-23T00:00:00",
            ),
            encoding="utf-8",
        )


# --- 선행 조건·오류 계약 ---------------------------------------------------------


def test_missing_graph_db_exits_precondition_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`search`가 인덱스 부재를 선행 조건 실패로 다루는 선례와 같다 (§4.7)."""
    code = cli.main(["graph", "--out", str(tmp_path / "wiki"), "--stats"])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "먼저" in capsys.readouterr().err


def test_unknown_document_exits_precondition_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """자유 텍스트 쿼리와 달리 존재를 전제한 식별자 지목이므로 빈 결과가 아니다 (§4.7)."""
    out_dir = tmp_path / "wiki"
    _seed(out_dir)

    code = cli.main(["graph", "--out", str(out_dir), "--neighbors", "없는문서.md"])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "그래프에 없는 문서" in capsys.readouterr().err


def test_schema_version_mismatch_exits_precondition_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import sqlite3

    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    conn = sqlite3.connect(graph_path_for(out_dir))
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    code = cli.main(["graph", "--out", str(out_dir), "--stats"])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "스키마 버전" in capsys.readouterr().err


def test_views_are_mutually_exclusive_and_one_is_required(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["graph", "--out", str(tmp_path), "--stats", "--central"])
    with pytest.raises(SystemExit):
        cli.main(["graph", "--out", str(tmp_path)])


def test_graph_has_no_threshold_options(tmp_path: Path) -> None:
    """`graph`는 순수 조회다 — 조회 시점에 엣지를 다시 계산하지 않는다 (§4.7)."""
    with pytest.raises(SystemExit):
        cli.main(["graph", "--out", str(tmp_path), "--stats", "--similarity-threshold", "0.9"])


# --- 정상 경로 ------------------------------------------------------------------


def test_stats_is_wired_and_exits_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "wiki"
    _seed(out_dir)

    code = cli.main(["graph", "--out", str(out_dir), "--stats"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "노드" in out
    assert "TAGGED_WITH" in out


def test_central_on_an_empty_graph_exits_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """빈 결과는 정상 응답이다 (§4.7)."""
    out_dir = tmp_path / "wiki"
    out_dir.mkdir(parents=True)
    with SqliteGraphStore(graph_path_for(out_dir)):
        pass

    code = cli.main(["graph", "--out", str(out_dir), "--central"])

    assert code == cli.EXIT_OK
    assert "문서가 없습니다" in capsys.readouterr().out


# --- 경로 해석 (§4.7) ------------------------------------------------------------


@pytest.mark.parametrize(
    "argument",
    ["개발/설계.md.md", "개발/설계.md", SOURCE],
    ids=["위키 상대경로", "원문 상대경로", "절대경로"],
)
def test_neighbors_accepts_three_path_forms(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argument: str
) -> None:
    out_dir = tmp_path / "wiki"
    _seed(out_dir)

    code = cli.main(["graph", "--out", str(out_dir), "--neighbors", argument])

    assert code == cli.EXIT_OK
    assert "설계 문서" in capsys.readouterr().out


def test_query_failure_after_open_is_a_precondition_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """리뷰 지적 ⓐ — 개봉 후 조회에서 깨지는 DB를 raw traceback으로 흘리지 않는다.

    `SqliteGraphStore.__init__`은 sqlite 오류를 감싸지만 `stats()`·`neighbors()`·
    `iter_facts()`는 감싸지 않았다. 다른 명령과 같이 exit 1로 정리한다.
    """
    import sqlite3

    from corpbrain.core import graphstore

    out_dir = tmp_path / "wiki"
    _seed(out_dir)

    def _boom(self: object) -> object:
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(graphstore.SqliteGraphStore, "stats", _boom)

    code = cli.main(["graph", "--out", str(out_dir), "--stats"])

    assert code == cli.EXIT_PRECONDITION_FAILED
    err = capsys.readouterr().err
    assert "읽지 못했습니다" in err
    assert "다시 scan" in err
