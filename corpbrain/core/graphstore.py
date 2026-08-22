"""지식그래프 저장소 어댑터 — 최소 계약과 sqlite3 기반 자체 구현 (v0.6 스펙 §4.4).

v0.4 `VectorStore`와 같은 형태를 따른다: 파이프라인·`graph` CLI는 `GraphStore` 인터페이스에만
의존하고 구체 구현(`SqliteGraphStore`)을 직접 참조하지 않는다. 계약은 스펙이 명시한
사용처에서 역산한 9멤버이며, v0.4가 3메서드로 적었다가 코드리뷰에서 누락이 드러나 6메서드로
넓힌 전례를 반복하지 않기 위해 처음부터 전부 선언한다.

**재료와 파생물을 분리한다** (스펙 §4.4). `doc_facts`는 재요약된 문서만 증분 upsert해 영속하고,
`nodes`·`edges`는 매 실행 `replace_graph()`로 통째로 다시 만든다 — 임계치나 문서 집합이
바뀌어도 옛 엣지가 남지 않아 §3 항목4(결정성)를 만족한다.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol, Self, runtime_checkable

from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import (
    DocFacts,
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphStats,
    NodeType,
)

#: 그래프 파일명 — `<out_dir>` 아래 숨김 파일로 둔다. 벡터 인덱스와 **별도 파일**이라
#: 한쪽만 지워 재구축할 수 있다 (스펙 §4.4).
GRAPH_FILENAME = ".corpbrain_graph.sqlite"

#: 그래프 DB 스키마 버전 (스펙 §5). 값이 다르면 자동 마이그레이션하지 않고 선행 조건 실패로
#: 멈춘 뒤 삭제·재실행을 안내한다 — v0.4가 벡터 인덱스에 세운 방침과 동형이다.
SCHEMA_VERSION = "1"


@runtime_checkable
class GraphStore(Protocol):
    """지식그래프 저장소 어댑터 최소 계약 (스펙 §4.4)."""

    def upsert_facts(self, facts: DocFacts) -> None:
        """문서 재료를 추가하거나 덮어쓴다 — 재요약된 문서에만 호출한다."""
        ...

    def get_facts(self, doc_id: str) -> DocFacts | None:
        """저장된 재료를 돌려준다. 없으면 `None` — 위키 파싱 복원 경로의 판정에 쓴다."""
        ...

    def iter_facts(self) -> Iterator[DocFacts]:
        """저장된 모든 재료 — `nodes`·`edges` 파생의 입력이다."""
        ...

    def delete_facts(self, doc_id: str) -> None:
        """재료를 지운다. 없어도 조용히 통과한다 — 위키가 사라진 문서의 유령 노드를 막는다."""
        ...

    def replace_graph(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> None:
        """`nodes`·`edges`를 **단일 트랜잭션**으로 통째로 교체한다.

        비운 직후 중단되어 그래프가 사라지거나 절반만 채워진 그래프가 정상처럼 보이는 상태를
        원천 차단한다 (스펙 §5). 실패하면 이전 그래프가 그대로 보존된다.
        """
        ...

    def stats(self) -> GraphStats:
        """노드·엣지 종류별 개수 — `scan` 종료 요약과 `graph --stats`가 함께 쓴다."""
        ...

    def neighbors(self, node_id: str) -> list[GraphEdge]:
        """이 노드에 닿는 모든 엣지. 대칭 엣지는 한 행만 저장되므로 `src`·`dst` 양쪽을 본다."""
        ...

    def degree_ranking(self) -> list[tuple[str, int]]:
        """`Document` 노드를 연결 차수 내림차순으로 — 동점은 노드 id 사전순 (스펙 §4.7)."""
        ...

    def close(self) -> None:
        """이 저장소가 쥔 자원(연결 등)을 정리한다."""
        ...


def graph_path_for(out_dir: Path) -> Path:
    """`out_dir` 아래 그래프 DB 경로 (스펙 §4.4)."""
    return out_dir / GRAPH_FILENAME


class SqliteGraphStore:
    """외부 의존성 없는 `GraphStore` 기본 구현 — 표준 라이브러리 `sqlite3`만 쓴다."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        try:
            self._conn = sqlite3.connect(path)
            self._create_schema()
            self._check_schema_version()
        except sqlite3.Error as exc:
            self._safe_close()
            raise PreconditionError(
                f"그래프 DB를 열지 못했습니다: {path} ({exc}) — 손상되었거나 접근할 수 "
                f"없습니다. 문제를 해결하거나 파일을 지우고 다시 scan 하세요."
            ) from exc
        if is_new:
            _hide_on_windows(path)

    # --- 스키마 ---------------------------------------------------------------

    def _create_schema(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS doc_facts ("
            "doc_id TEXT PRIMARY KEY, title TEXT NOT NULL, tags_json TEXT NOT NULL, "
            "entities_json TEXT NOT NULL, refs_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS nodes ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, label TEXT NOT NULL, "
            "props_json TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS edges ("
            "src TEXT NOT NULL, dst TEXT NOT NULL, type TEXT NOT NULL, weight REAL, "
            "PRIMARY KEY (src, dst, type))"
        )
        self._conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self._conn.commit()

    def _check_schema_version(self) -> None:
        """기록된 스키마 버전을 확인한다 — 없으면 기록하고, 다르면 선행 조건 실패 (스펙 §5)."""
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
            )
            self._conn.commit()
            return
        if row[0] != SCHEMA_VERSION:
            raise PreconditionError(
                f"그래프 DB의 스키마 버전이 다릅니다: {row[0]} (이 버전: {SCHEMA_VERSION}) — "
                f"자동 마이그레이션하지 않습니다. {self._path} 를 지우고 다시 scan 하세요 "
                f"(엔티티까지 되살리려면 --force 로 재스캔하세요)."
            )

    # --- 재료 (증분) -----------------------------------------------------------

    def upsert_facts(self, facts: DocFacts) -> None:
        # 재료는 즉시 커밋한다. `replace_graph`의 트랜잭션이 롤백될 때 함께 되돌아가면,
        # 위키는 이미 생성됐는데 그 문서의 엔티티만 사라져 다음 실행에서 복원 경로로
        # 떨어진다(엔티티 없는 부분 그래프). 재료와 파생물의 수명은 분리한다.
        self._conn.execute(
            "INSERT INTO doc_facts "
            "(doc_id, title, tags_json, entities_json, refs_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(doc_id) DO UPDATE SET "
            "title = excluded.title, tags_json = excluded.tags_json, "
            "entities_json = excluded.entities_json, refs_json = excluded.refs_json, "
            "updated_at = excluded.updated_at",
            (
                facts.doc_id,
                facts.title,
                json.dumps(facts.tags, ensure_ascii=False),
                json.dumps(facts.entities, ensure_ascii=False),
                json.dumps(facts.refs, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def get_facts(self, doc_id: str) -> DocFacts | None:
        row = self._conn.execute(
            "SELECT doc_id, title, tags_json, entities_json, refs_json "
            "FROM doc_facts WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        return _row_to_facts(row) if row else None

    def iter_facts(self) -> Iterator[DocFacts]:
        rows = self._conn.execute(
            "SELECT doc_id, title, tags_json, entities_json, refs_json "
            "FROM doc_facts ORDER BY doc_id"
        ).fetchall()
        for row in rows:
            yield _row_to_facts(row)

    def delete_facts(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM doc_facts WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    # --- 파생물 (전체 재빌드) ---------------------------------------------------

    def replace_graph(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> None:
        with self._conn:  # 실패하면 통째로 롤백돼 이전 그래프가 남는다 (스펙 §5).
            self._conn.execute("DELETE FROM edges")
            self._conn.execute("DELETE FROM nodes")
            self._conn.executemany(
                "INSERT INTO nodes (id, type, label, props_json) VALUES (?, ?, ?, ?)",
                [
                    (n.id, str(n.type), n.label, json.dumps(n.props, ensure_ascii=False))
                    for n in nodes
                ],
            )
            self._conn.executemany(
                "INSERT INTO edges (src, dst, type, weight) VALUES (?, ?, ?, ?)",
                [(e.src, e.dst, str(e.type), e.weight) for e in edges],
            )

    # --- 조회 -----------------------------------------------------------------

    def stats(self) -> GraphStats:
        by_type = dict(
            self._conn.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type").fetchall()
        )
        edge_rows = dict(
            self._conn.execute("SELECT type, COUNT(*) FROM edges GROUP BY type").fetchall()
        )
        return GraphStats(
            documents=by_type.get(str(NodeType.DOCUMENT), 0),
            entities=by_type.get(str(NodeType.ENTITY), 0),
            tags=by_type.get(str(NodeType.TAG), 0),
            # 4종을 0까지 포함해 담는다 — 그래프가 비어도 출력 줄 수가 흔들리지 않는다.
            edges_by_type={str(t): edge_rows.get(str(t), 0) for t in EdgeType},
        )

    def neighbors(self, node_id: str) -> list[GraphEdge]:
        rows = self._conn.execute(
            "SELECT src, dst, type, weight FROM edges WHERE src = ? OR dst = ? "
            "ORDER BY type, src, dst",
            (node_id, node_id),
        ).fetchall()
        return [GraphEdge(src=r[0], dst=r[1], type=EdgeType(r[2]), weight=r[3]) for r in rows]

    def degree_ranking(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT n.id, ("
            "  SELECT COUNT(*) FROM edges e WHERE e.src = n.id OR e.dst = n.id"
            ") AS degree "
            "FROM nodes n WHERE n.type = ? "
            "ORDER BY degree DESC, n.id ASC",
            (str(NodeType.DOCUMENT),),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    # --- 수명 -----------------------------------------------------------------

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def _safe_close(self) -> None:
        conn = getattr(self, "_conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass  # 이미 실패 경로다 — 정리 실패가 원래 원인을 덮어쓰지 않게 둔다

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _row_to_facts(row: tuple[str, str, str, str, str]) -> DocFacts:
    return DocFacts(
        doc_id=row[0],
        title=row[1],
        tags=json.loads(row[2]),
        entities=json.loads(row[3]),
        refs=json.loads(row[4]),
    )


def _hide_on_windows(path: Path) -> None:
    """Windows에서 파일에 숨김 속성을 추가한다(베스트 에포트, 실패해도 그래프엔 영향 없음)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        FILE_ATTRIBUTE_HIDDEN = 0x2
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_HIDDEN)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001, S110 - 순수 사용성 보조 기능, 실패해도 그래프는 계속돼야 한다
        pass
