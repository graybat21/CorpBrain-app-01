"""`corpbrain search` CLI 어댑터 테스트 (v0.4 스펙 §3 완료의 정의 6·7, §4.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from corpbrain import cli
from corpbrain.core import gateway
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for


def _seed_index(out_dir: Path, *, model: str = "nomic-embed-text") -> None:
    store = SqliteVectorStore(index_path_for(out_dir))
    store.set_model_name(model)
    store.upsert("a", [1.0, 0.0], {"title": "휴가 규정", "source_path": "/docs/a.txt"})
    store.upsert("b", [0.0, 1.0], {"title": "출장비 규정", "source_path": "/docs/b.txt"})
    store.close()


def test_search_no_index_exits_precondition_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["search", "휴가", "--out", str(tmp_path / "wiki")])

    err = capsys.readouterr().err
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "먼저" in err


def test_search_zero_results_exits_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        return {"embedding": [1.0, 0.0]}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    # top_k=0 → 결과 0건이지만 인덱스는 정상이므로 exit 0.
    code = cli.main(["search", "휴가", "--out", str(out_dir), "--top-k", "0"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "일치하는 문서가 없습니다" in out


def test_search_returns_ranked_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        assert url.endswith("/api/embeddings")
        assert payload == {"model": "nomic-embed-text", "prompt": "휴가"}
        return {"embedding": [1.0, 0.0]}

    monkeypatch.setattr(gateway, "request_json", _request_json)

    code = cli.main(["search", "휴가", "--out", str(out_dir)])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "검색 결과 2건" in out
    assert "휴가 규정" in out
    # 쿼리와 완전히 같은 방향의 벡터("a")가 먼저 나온다.
    assert out.index("휴가 규정") < out.index("출장비 규정")


def test_search_query_embedding_failure_exits_precondition_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        raise gateway.GatewayError("데몬 다운", url=url)

    monkeypatch.setattr(gateway, "request_json", _request_json)

    code = cli.main(["search", "휴가", "--out", str(out_dir)])

    assert code == cli.EXIT_PRECONDITION_FAILED


# --- v0.7: 그래프 확산 플래그 (스펙 §4.4) ---------------------------------------
#
# 이 파일은 **종료 코드와 배선만** 본다. 근거 줄의 정확 문자열은
# `tests/unit/test_search_report.py`가 단언한다 (v0.7 §3 항목12).


def _seed_graph(out_dir: Path) -> None:
    from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
    from corpbrain.core.models import EdgeType, GraphEdge, GraphNode, NodeType

    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        store.replace_graph(
            [
                GraphNode(id="a", type=NodeType.DOCUMENT, label="휴가 규정"),
                GraphNode(id="b", type=NodeType.DOCUMENT, label="출장비 규정"),
                # 벡터 인덱스에는 없고 그래프에만 있는 문서 — 확산으로만 후보가 된다.
                GraphNode(id="c", type=NodeType.DOCUMENT, label="경조사 규정"),
                GraphNode(id="tag:규정", type=NodeType.TAG, label="규정"),
            ],
            [
                GraphEdge(src="a", dst="tag:규정", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="b", dst="tag:규정", type=EdgeType.TAGGED_WITH),
                GraphEdge(src="c", dst="tag:규정", type=EdgeType.TAGGED_WITH),
            ],
        )


@pytest.fixture
def _stub_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        return {"embedding": [1.0, 0.0]}

    monkeypatch.setattr(gateway, "request_json", _request_json)


def test_search_without_a_graph_db_exits_ok_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _stub_embedding: None
) -> None:
    """§3 항목7 — 그래프 DB 부재는 exit 0 · 코사인 단독 결과 · stderr 안내 1줄."""
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)

    code = cli.main(["search", "휴가", "--out", str(out_dir)])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "검색 결과" in captured.out
    assert len([line for line in captured.err.splitlines() if line.strip()]) == 1
    assert "그래프" in captured.err


def test_search_with_a_graph_db_wires_the_expansion_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _stub_embedding: None
) -> None:
    """배선 확인 — 확산 근거 줄이 stdout에 도달한다. 문자열 단언은 리포트 단위테스트가 한다."""
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)

    code = cli.main(["search", "휴가", "--out", str(out_dir), "--top-k", "2"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "└" in captured.out
    assert captured.err == ""  # 그래프가 있으므로 안내 줄이 없다


def test_no_graph_flag_exits_ok_without_the_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _stub_embedding: None
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)

    code = cli.main(["search", "휴가", "--out", str(out_dir), "--no-graph"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert captured.err == ""
    assert "└" not in captured.out


@pytest.mark.parametrize("alpha", ["0", "1", "1.5", "-0.2"])
def test_graph_decay_outside_the_open_interval_exits_precondition_failed(
    tmp_path: Path, alpha: str, _stub_embedding: None
) -> None:
    """§3 항목8 — 코어의 `PreconditionError`가 exit 1로 매핑된다. CLI는 자체 검증을 두지 않는다."""
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)

    code = cli.main(["search", "휴가", "--out", str(out_dir), "--graph-decay", alpha])

    assert code == cli.EXIT_PRECONDITION_FAILED


@pytest.mark.parametrize("raw", ["tagged_with", "", "TAGGED_WITH,", "NOPE"])
def test_malformed_expand_edges_exits_precondition_failed(
    tmp_path: Path, raw: str, _stub_embedding: None
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)

    code = cli.main(["search", "휴가", "--out", str(out_dir), "--expand-edges", raw])

    assert code == cli.EXIT_PRECONDITION_FAILED


def test_expand_edges_accepts_edge_type_values_verbatim(
    tmp_path: Path, _stub_embedding: None
) -> None:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)

    code = cli.main(
        ["search", "휴가", "--out", str(out_dir), "--expand-edges", " TAGGED_WITH , REFERENCES "]
    )

    assert code == cli.EXIT_OK


def test_corrupt_graph_schema_exits_precondition_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], _stub_embedding: None
) -> None:
    """§3 항목9 — 손상·스키마 불일치는 exit 1 + 재생성 안내다 (부재의 exit 0과 갈라 다룬다)."""
    import sqlite3

    from corpbrain.core.graphstore import graph_path_for

    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)
    conn = sqlite3.connect(graph_path_for(out_dir))
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    code = cli.main(["search", "휴가", "--out", str(out_dir)])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "지우고" in capsys.readouterr().err
