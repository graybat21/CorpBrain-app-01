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
