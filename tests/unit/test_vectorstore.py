"""SqliteVectorStore 단위테스트 (v0.4 스펙 §3 항목2·5, §4.3 어댑터 계약)."""

from __future__ import annotations

from pathlib import Path

from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for


def test_index_path_for_is_hidden_file_under_out_dir(tmp_path: Path) -> None:
    assert index_path_for(tmp_path) == tmp_path / ".corpbrain_index.sqlite"


def test_upsert_then_search_returns_most_similar_first(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.upsert("a", [1.0, 0.0], {"title": "A"})
    store.upsert("b", [0.0, 1.0], {"title": "B"})

    results = store.search([1.0, 0.0], top_k=5)

    assert [r.doc_id for r in results] == ["a", "b"]
    assert results[0].score > results[1].score
    assert results[0].metadata == {"title": "A"}


def test_search_respects_top_k(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    for i in range(5):
        store.upsert(f"doc{i}", [float(i), 1.0], {})

    assert len(store.search([1.0, 1.0], top_k=2)) == 2


def test_upsert_is_idempotent_overwrite(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.upsert("a", [1.0, 0.0], {"title": "old"})
    store.upsert("a", [0.0, 1.0], {"title": "new"})

    assert store.list_ids() == ["a"]
    results = store.search([0.0, 1.0], top_k=1)
    assert results[0].metadata == {"title": "new"}


def test_delete_removes_doc_id(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.upsert("a", [1.0, 0.0], {})
    store.upsert("b", [0.0, 1.0], {})

    store.delete("a")

    assert store.list_ids() == ["b"]


def test_delete_missing_id_is_a_no_op(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.delete("does-not-exist")  # 예외 없이 통과
    assert store.list_ids() == []


def test_model_name_defaults_to_none_then_set_once(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    assert store.model_name is None

    store.set_model_name("nomic-embed-text")
    assert store.model_name == "nomic-embed-text"

    store.set_model_name("other-model")  # 최초 값 고정 — 조용히 무시
    assert store.model_name == "nomic-embed-text"


def test_state_persists_across_store_instances(tmp_path: Path) -> None:
    path = index_path_for(tmp_path)
    first = SqliteVectorStore(path)
    first.upsert("a", [1.0, 0.0], {"title": "A"})
    first.set_model_name("nomic-embed-text")
    first.close()

    second = SqliteVectorStore(path)
    assert second.list_ids() == ["a"]
    assert second.model_name == "nomic-embed-text"
