"""벡터 저장소 어댑터 — 최소 계약과 sqlite3 기반 자체 구현 (v0.4 스펙 §4.3, Grill T1·T4).

`VectorStore`는 `upsert`/`delete`/`search`/`list_ids`/`set_model_name`/`close` + `model_name`
접근자로 구성된 최소 계약이다(코드 리뷰: 파이프라인·`search`가 실제로 호출하는 멤버 전부를
Protocol이 선언해야 대체 구현체가 진짜로 교체 가능하다). 파이프라인·`search` 코어는 이
인터페이스에만 의존하고 구체 구현(`SqliteVectorStore`)을 직접 참조하지 않아, 후속 슬라이스가
`sqlite-vec`·`chromadb` 같은 다른 구현체로 교체할 수 있다.

`SqliteVectorStore`는 외부 의존성 없이 표준 라이브러리 `sqlite3`만 쓰고, 유사도는 순수 파이썬
코사인 계산으로 brute-force 수행한다(스캔 상한 50 규모에서 충분, v0.4 스펙 §2 비목표).
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections.abc import Iterator
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

    def iter_vectors(self) -> Iterator[tuple[str, list[float]]]:
        """저장된 모든 `(doc_id, 벡터)` — 그래프의 유사도 엣지 계산에 쓴다 (v0.6 §4.4).

        그래프 빌더가 sqlite를 직접 열지 않고 이 인터페이스로만 벡터에 접근하게 해, v0.4가
        세운 저장소 어댑터 이음새를 유지한다 — 후속 저장소 교체가 그래프까지 자동으로 따라온다.
        """
        ...

    def set_model_name(self, model_name: str) -> None:
        """이 인덱스가 쓰는 임베딩 모델명을 기록한다. 이미 기록돼 있으면 조용히 무시한다(멱등)."""
        ...

    def close(self) -> None:
        """이 저장소가 쥔 자원(연결 등)을 정리한다."""
        ...


def index_path_for(out_dir: Path) -> Path:
    """`out_dir` 아래 인덱스 파일 경로 (v0.4 Grill T4)."""
    return out_dir / INDEX_FILENAME


class SqliteVectorStore:
    """외부 의존성 없는 `VectorStore` 기본 구현 — `sqlite3` + 순수 파이썬 코사인 유사도."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "doc_id TEXT PRIMARY KEY, vector TEXT NOT NULL, metadata TEXT NOT NULL)"
        )
        self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self._conn.commit()
        if is_new:
            _hide_on_windows(path)

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
        # 커밋은 close()에서 한 번에 한다 — 스캔 1회에 파일마다 매번 fsync급 커밋을 하지
        # 않기 위함이다(성능). 같은 연결 안에서는 커밋 전에도 자신의 쓰기가 그대로 보인다.
        self._conn.execute(
            "INSERT INTO vectors (doc_id, vector, metadata) VALUES (?, ?, ?) "
            "ON CONFLICT(doc_id) DO UPDATE SET "
            "vector = excluded.vector, metadata = excluded.metadata",
            (doc_id, json.dumps(vector), json.dumps(metadata)),
        )

    def delete(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM vectors WHERE doc_id = ?", (doc_id,))

    def list_ids(self) -> list[str]:
        rows = self._conn.execute("SELECT doc_id FROM vectors").fetchall()
        return [row[0] for row in rows]

    def iter_vectors(self) -> Iterator[tuple[str, list[float]]]:
        # `doc_id` 순으로 낸다 — 전 쌍 계산이 항상 같은 순서를 보게 해 §3 항목4(결정성)를 돕는다.
        rows = self._conn.execute(
            "SELECT doc_id, vector FROM vectors ORDER BY doc_id"
        ).fetchall()
        for doc_id, vector_json in rows:
            yield doc_id, json.loads(vector_json)

    def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]:
        top_k = max(0, top_k)  # 음수 --top-k가 슬라이스를 뒤집지 않도록 방어한다.
        rows = self._conn.execute("SELECT doc_id, vector, metadata FROM vectors").fetchall()
        scored: list[SearchResult] = []
        for doc_id, vector_json, metadata_json in rows:
            vector = json.loads(vector_json)
            if len(vector) != len(query_vector):
                # 다른 임베딩 모델·차원으로 저장된(손상되었거나 과거 버그로 섞인) 벡터는
                # 비교 자체가 무의미하므로 조용히 잘라 비교하지 않고 결과에서 제외한다.
                continue
            scored.append(
                SearchResult(
                    doc_id=doc_id,
                    score=cosine_similarity(query_vector, vector),
                    metadata=json.loads(metadata_json),
                )
            )
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도. 호출자가 이미 길이를 맞춘 뒤 불러야 한다(`strict=True`로 보증).

    영벡터는 0.0을 돌려준다.

    v0.6 그래프 빌더가 전 쌍 유사도를 계산할 때도 같은 함수를 쓴다 — `search` 랭킹과
    그래프 엣지가 다른 계산식을 쓰면 같은 문서 쌍이 두 화면에서 다른 값을 갖는다.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _hide_on_windows(path: Path) -> None:
    """Windows에서 파일에 숨김 속성을 추가한다(베스트 에포트, 실패해도 인덱싱엔 영향 없음).

    점(`.`) 접두는 Unix 계열 셸·Finder 관례일 뿐 Windows 탐색기에서는 파일을 숨기지
    않는다 — `INDEX_FILENAME`을 숨김 파일로 두려는 의도(Grill T4)를 이 프로젝트가 실제로
    도는 플랫폼(Windows)에서도 이행하기 위해 `FILE_ATTRIBUTE_HIDDEN`을 함께 건다.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        FILE_ATTRIBUTE_HIDDEN = 0x2
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001, S110 - 순수 사용성 보조 기능, 실패해도 인덱싱은 계속돼야 한다
        pass
