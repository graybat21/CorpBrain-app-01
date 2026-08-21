"""SqliteVectorStore 단위테스트 (v0.4 스펙 §3 항목2·5, §4.3 어댑터 계약)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from corpbrain.core.models import SearchResult
from corpbrain.core.vectorstore import SqliteVectorStore, VectorStore, index_path_for


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


class _InMemoryVectorStore:
    """`VectorStore` 최소 계약을 만족하는 대체 구현체 (v0.4 스펙 §3 항목10 — 구조적 검증용).

    `SqliteVectorStore`가 아닌 완전히 다른 구현체도 같은 인터페이스로 교체될 수 있음을
    구조적 타이핑(`Protocol`)으로 증명한다. 파이프라인/`search`가 구체 클래스가 아니라
    이 프로토콜에만 의존한다는 계약의 실행 가능한 증거다.
    """

    def __init__(self) -> None:
        self._data: dict[str, tuple[list[float], dict[str, Any]]] = {}
        self._model_name: str | None = None

    @property
    def model_name(self) -> str | None:
        return self._model_name

    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        self._data[doc_id] = (vector, metadata)

    def delete(self, doc_id: str) -> None:
        self._data.pop(doc_id, None)

    def list_ids(self) -> list[str]:
        return list(self._data)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        return [
            SearchResult(doc_id=doc_id, score=1.0, metadata=metadata)
            for doc_id, (_vector, metadata) in list(self._data.items())[:top_k]
        ]

    def set_model_name(self, model_name: str) -> None:
        if self._model_name is None:
            self._model_name = model_name

    def close(self) -> None:
        pass


def test_alternate_implementation_satisfies_vectorstore_protocol() -> None:
    """대체 구현체가 `VectorStore` 구조적 타입을 만족한다(sqlite3 구현으로 하드코딩되지 않음)."""
    store: VectorStore = _InMemoryVectorStore()
    assert isinstance(store, VectorStore)

    store.upsert("a", [1.0], {"title": "A"})
    assert store.list_ids() == ["a"]
    assert store.search([1.0], top_k=5)[0].doc_id == "a"


def test_sqlite_vector_store_also_satisfies_the_protocol(tmp_path: Path) -> None:
    assert isinstance(SqliteVectorStore(index_path_for(tmp_path)), VectorStore)


def test_search_excludes_dimension_mismatched_vectors(tmp_path: Path) -> None:
    """차원이 다른(다른 모델·손상) 벡터는 비교하지 않고 결과에서 제외한다."""
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.upsert("same-dim", [1.0, 0.0], {"title": "match"})
    store.upsert("other-dim", [1.0, 0.0, 0.0], {"title": "mismatch"})

    results = store.search([1.0, 0.0], top_k=5)

    assert [r.doc_id for r in results] == ["same-dim"]


def test_search_clamps_negative_top_k_to_zero(tmp_path: Path) -> None:
    store = SqliteVectorStore(index_path_for(tmp_path))
    store.upsert("a", [1.0, 0.0], {})
    store.upsert("b", [0.0, 1.0], {})

    assert store.search([1.0, 0.0], top_k=-1) == []


def test_state_persists_across_store_instances(tmp_path: Path) -> None:
    path = index_path_for(tmp_path)
    first = SqliteVectorStore(path)
    first.upsert("a", [1.0, 0.0], {"title": "A"})
    first.set_model_name("nomic-embed-text")
    first.close()

    second = SqliteVectorStore(path)
    assert second.list_ids() == ["a"]
    assert second.model_name == "nomic-embed-text"
