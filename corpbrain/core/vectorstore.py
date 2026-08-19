"""벡터 저장소 어댑터 — 최소 계약과 sqlite3 기반 자체 구현 (v0.4 스펙 §4.3, Grill T1·T4).

`VectorStore`는 `upsert`/`delete`/`search`/`list_ids` + `model_name` 접근자로 구성된 최소
계약이다. 파이프라인·`search` 코어는 이 인터페이스에만 의존하고 구체 구현(`SqliteVectorStore`)을
직접 참조하지 않아, 후속 슬라이스가 `sqlite-vec`·`chromadb` 같은 다른 구현체로 교체할 수 있다.

`SqliteVectorStore`는 외부 의존성 없이 표준 라이브러리 `sqlite3`만 쓰고, 유사도는 순수 파이썬
코사인 계산으로 brute-force 수행한다(스캔 상한 50 규모에서 충분, v0.4 스펙 §2 비목표).
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Protocol, Self, runtime_checkable

from corpbrain.core.models import SearchResult

#: 인덱스 파일명 — `<out_dir>` 아래 숨김 파일로 둔다 (v0.4 Grill T4, 위키 `.md`와 섞여도
#: 실수로 열거나 지울 위험을 줄인다).
INDEX_FILENAME = ".corpbrain_index.sqlite"


@runtime_checkable
class VectorStore(Protocol):
    """벡터 저장소 어댑터 최소 계약 (v0.4 Grill T1)."""

    @property
    def model_name(self) -> str | None:
        """이 인덱스가 기록한 임베딩 모델명. 아직 아무것도 기록되지 않았으면 `None`."""
        ...

    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        """`doc_id`의 벡터·메타데이터를 추가하거나 덮어쓴다."""
        ...

    def delete(self, doc_id: str) -> None:
        """`doc_id`의 벡터를 지운다. 없어도 조용히 통과한다."""
        ...

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        """코사인 유사도 내림차순 상위 `top_k`건을 돌려준다."""
        ...

    def list_ids(self) -> list[str]:
        """저장된 모든 `doc_id` — 재스캔 시 고아 벡터를 가려내는 데 쓴다(v0.4 §3 항목5)."""
        ...


def index_path_for(out_dir: Path) -> Path:
    """`out_dir` 아래 인덱스 파일 경로 (v0.4 Grill T4)."""
    return out_dir / INDEX_FILENAME


class SqliteVectorStore:
    """외부 의존성 없는 `VectorStore` 기본 구현 — `sqlite3` + 순수 파이썬 코사인 유사도."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "doc_id TEXT PRIMARY KEY, vector TEXT NOT NULL, metadata TEXT NOT NULL)"
        )
        self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self._conn.commit()

    @property
    def model_name(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'model_name'"
        ).fetchone()
        return row[0] if row else None

    def set_model_name(self, model_name: str) -> None:
        """이 인덱스가 쓰는 임베딩 모델명을 기록한다(멱등). 최초 호출 시점의 값을 고정한다."""
        if self.model_name is not None:
            return
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES ('model_name', ?)", (model_name,)
        )
        self._conn.commit()

    def upsert(self, doc_id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO vectors (doc_id, vector, metadata) VALUES (?, ?, ?) "
            "ON CONFLICT(doc_id) DO UPDATE SET "
            "vector = excluded.vector, metadata = excluded.metadata",
            (doc_id, json.dumps(vector), json.dumps(metadata)),
        )
        self._conn.commit()

    def delete(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM vectors WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    def list_ids(self) -> list[str]:
        rows = self._conn.execute("SELECT doc_id FROM vectors").fetchall()
        return [row[0] for row in rows]

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        rows = self._conn.execute("SELECT doc_id, vector, metadata FROM vectors").fetchall()
        scored = [
            SearchResult(
                doc_id=doc_id,
                score=_cosine_similarity(query_vector, json.loads(vector_json)),
                metadata=json.loads(metadata_json),
            )
            for doc_id, vector_json, metadata_json in rows
        ]
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도. 길이가 다르면 짧은 쪽까지만 비교하고, 영벡터는 0.0을 돌려준다."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
