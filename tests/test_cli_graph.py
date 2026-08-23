"""`corpbrain graph` CLI 어댑터 (v0.6 스펙 §3 항목3, §4.7).

정확 문자열 단언은 `tests/unit/test_graph_report.py`가 한다. 여기서는 종료 코드와 배선만
확인해, 출력 문구를 다듬을 때 어댑터 테스트가 깨지지 않게 한다
(`tests/test_cli_search.py`가 `assert "먼저" in err` 수준으로만 보는 것과 같다).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from corpbrain import cli
from corpbrain.core import graphstore
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


# --- 조회 전용 개봉 (v0.6.1 후속-1 · 스펙 §4.7) ------------------------------------


def test_graph_does_not_modify_the_database(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """조회 명령이 파일을 바꾸지 않는다 — 종전에는 개봉만으로 스키마를 되만들었다."""
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    before = graph_path_for(out_dir).read_bytes()

    assert cli.main(["graph", "--out", str(out_dir), "--stats"]) == cli.EXIT_OK

    capsys.readouterr()
    assert graph_path_for(out_dir).read_bytes() == before


def test_graph_reads_a_read_only_database(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """읽기 전용 파일에서도 조회된다 (백업 볼륨·읽기 전용 공유).

    **이 테스트는 v0.6.0 코드에서도 통과한다** — 스키마가 온전한 DB에서는
    `CREATE TABLE IF NOT EXISTS`가 실제로 쓰지 않아 sqlite가 쓰기 잠금을 잡지 않는다
    (실측). 즉 v0.6.0 회귀를 잡는 장치가 아니라, 앞으로 개봉 경로에 쓰기가 끼어드는 변경
    (PRAGMA·WAL 전환·개봉 시 마이그레이션)을 막는 **전방 가드**다.
    """
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    path = graph_path_for(out_dir)
    path.chmod(0o444)
    try:
        code = cli.main(["graph", "--out", str(out_dir), "--stats"])
    finally:
        path.chmod(0o644)

    assert code == cli.EXIT_OK
    assert "노드" in capsys.readouterr().out


def test_graph_refuses_a_database_whose_tables_are_gone(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """테이블이 사라진 DB를 «엣지 0개»라고 정상 응답하지 않는다 (스펙 §5)."""
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    conn = sqlite3.connect(graph_path_for(out_dir))
    for table in ("edges", "nodes", "doc_facts", "meta"):
        conn.execute(f"DROP TABLE {table}")
    conn.commit()
    conn.close()

    code = cli.main(["graph", "--out", str(out_dir), "--stats"])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "다시 scan" in capsys.readouterr().err


# --- 라벨은 저장된 값을 읽는다 (v0.6.1 후속-2 · 스펙 §4.4) ---------------------------


def _relabel(out_dir: Path, node_id: str, label: str) -> None:
    conn = sqlite3.connect(graph_path_for(out_dir))
    conn.execute("UPDATE nodes SET label = ? WHERE id = ?", (label, node_id))
    conn.commit()
    conn.close()


@pytest.mark.parametrize("view", ["--central", "--neighbors"])
def test_graph_labels_come_from_the_stored_node_row(
    view: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """`nodes.label`을 그대로 읽는다 — 재료에서 다시 계산하지 않는다.

    v0.6.0은 저장소 계약에 노드 조회가 없어 `doc_facts`의 제목에서 라벨을 재구성했다. 저장된
    라벨만 바꿔 두면 그 구현은 옛 제목("설계 문서")을 계속 출력하고, 저장된 값을 읽는 구현만
    바뀐 라벨을 낸다 — 두 화면이 어긋나던 상태를 이 단언이 막는다.
    """
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    _relabel(out_dir, SOURCE, "저장된 라벨")

    argv = ["graph", "--out", str(out_dir), view]
    if view == "--neighbors":
        argv.append("개발/설계.md.md")

    assert cli.main(argv) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "저장된 라벨" in out
    assert "설계 문서" not in out


def test_graph_neighbors_labels_tag_nodes_from_storage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """문서뿐 아니라 태그·엔티티 라벨도 저장된 행에서 온다."""
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    _relabel(out_dir, "tag:설계", "저장된 태그 라벨")

    assert cli.main(["graph", "--out", str(out_dir), "--neighbors", "개발/설계.md.md"]) == cli.EXIT_OK

    assert "저장된 태그 라벨" in capsys.readouterr().out


def test_neighbors_rejects_a_document_that_has_facts_but_no_node(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """존재 판정은 `nodes` 테이블로 한다 (v0.6.1 · §4.7).

    패스1과 패스2 사이에서 `scan`이 죽으면 `doc_facts`에는 재료가 있는데 노드는 없다.
    그래프가 담고 있지 않은 문서에 «이웃 없음»이라고 답하면 사용자는 고립 문서와 구분할
    수 없다 — v0.6.0은 `doc_facts` 존재로 판정해 이 경우 exit 0을 냈다.
    """
    out_dir = tmp_path / "wiki"
    out_dir.mkdir(parents=True)
    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        store.upsert_facts(DocFacts(doc_id=SOURCE, title="재료만", tags=[], entities=[]))
        # replace_graph 를 부르지 않는다 — 노드가 없는 상태.

    code = cli.main(["graph", "--out", str(out_dir), "--neighbors", SOURCE])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "그래프에 없는 문서" in capsys.readouterr().err


def test_graph_reads_from_a_read_only_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """디렉터리가 읽기 전용이어도 조회된다.

    이 항목이 겨냥한 시나리오(백업 볼륨·팀 공유 마운트)는 파일 권한보다 **디렉터리 권한**
    으로 잠기는 쪽이 흔하다. 저널 파일을 만들려 들면 여기서 실패한다.

    위 테스트와 마찬가지로 **v0.6.0 코드에서도 통과하는 전방 가드**다. v0.6.0 개봉이
    실제로 실패하는 것은 스키마가 불완전해 `CREATE TABLE`이 써야만 하는 경우이며, 그 경우는
    `test_graph_refuses_a_database_whose_tables_are_gone`가 따로 덮는다.
    """
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    out_dir.chmod(0o555)
    try:
        code = cli.main(["graph", "--out", str(out_dir), "--stats"])
    finally:
        out_dir.chmod(0o755)

    assert code == cli.EXIT_OK
    assert "노드" in capsys.readouterr().out


def test_graph_opens_the_store_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """CLI가 실제로 `read_only=True`로 여는지 배선을 고정한다 (v0.6.1 · §4.7).

    권한 기반 테스트만으로는 이 배선이 지켜지지 않는다 — 스키마가 온전한 DB에서는 쓰기
    개봉도 조용히 성공하기 때문이다(실측). 그래서 여기서만 인자를 직접 들여다본다.
    """
    out_dir = tmp_path / "wiki"
    _seed(out_dir)
    seen: list[bool] = []
    original = graphstore.SqliteGraphStore.__init__

    def spy(self: object, path: Path, *, read_only: bool = False) -> None:
        seen.append(read_only)
        original(self, path, read_only=read_only)

    monkeypatch.setattr(graphstore.SqliteGraphStore, "__init__", spy)

    assert cli.main(["graph", "--out", str(out_dir), "--stats"]) == cli.EXIT_OK

    capsys.readouterr()
    assert seen == [True]
