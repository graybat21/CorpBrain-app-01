"""스캔 산출물에서 `entities` 채움 현황을 표로 뽑는다 (issue #40).

문서별 엔티티는 위키에 렌더되지 않고 **그래프 DB에만** 영속하므로(v0.6 스펙 §4.4),
`.corpbrain_graph.sqlite`를 읽어야 확인할 수 있다. 저장소는 조회 전용으로 연다
(`read_only=True`) — 측정이 산출물을 건드리지 않게 한다.

```bash
uv run python docs/smoke/entities_report.py <OUT_DIR>
```

`--json` 을 주면 기계가 읽는 형식으로도 낸다(원시 출력을 `docs/smoke/` 에 남길 때 쓴다).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from corpbrain.core.graphstore import GRAPH_FILENAME, SqliteGraphStore


def main() -> int:
    parser = argparse.ArgumentParser(description="entities 채움 현황 보고 (issue #40)")
    parser.add_argument("out_dir", type=Path, help="`corpbrain scan --out` 으로 준 폴더")
    parser.add_argument("--json", action="store_true", help="기계가 읽는 형식으로도 출력")
    args = parser.parse_args()

    db_path = args.out_dir / GRAPH_FILENAME
    if not db_path.exists():
        print(f"그래프 DB가 없습니다: {db_path}", file=sys.stderr)
        return 1

    store = SqliteGraphStore(db_path, read_only=True)
    try:
        facts = sorted(store.iter_facts(), key=lambda f: f.doc_id)
        stats = store.stats()
    finally:
        store.close()

    rows = [
        {
            "doc": Path(fact.doc_id).name,
            "tags": len(fact.tags),
            "entities": list(fact.entities),
        }
        for fact in facts
    ]
    filled = sum(1 for row in rows if row["entities"])
    all_tags = {tag for fact in facts for tag in fact.tags}

    width = max((len(row["doc"]) for row in rows), default=10)
    print(f"{'문서':<{width}}  tags  entities")
    print("-" * (width + 30))
    for row in rows:
        shown = row["entities"] if row["entities"] else "[]"
        print(f"{row['doc']:<{width}}  {row['tags']:>4}  {shown}")

    print()
    print(f"entities 채워진 문서: {filled}/{len(rows)}")
    print(f"고유 태그 수: {len(all_tags)}  (v0.6.0 클라우드 실측 비교값: 34)")
    print(
        f"그래프: 문서 {stats.documents} · 엔티티 {stats.entities} · 태그 {stats.tags}"
    )
    print(f"엣지: {stats.edges_by_type}")

    if args.json:
        print()
        print(
            json.dumps(
                {
                    "documents": rows,
                    "filled_documents": filled,
                    "total_documents": len(rows),
                    "unique_tags": sorted(all_tags),
                    "stats": {
                        "documents": stats.documents,
                        "entities": stats.entities,
                        "tags": stats.tags,
                        "edges_by_type": stats.edges_by_type,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
