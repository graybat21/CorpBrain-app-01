"""v0.7 하이브리드 검색 — 감쇠 계수 α 스윕 측정 스크립트 (issue #43, 스펙 §4.8).

사용자가 로컬에서 코퍼스를 `scan` 해 인덱스·그래프 DB를 만든 뒤 이 스크립트를 실행한다.
구현 세션은 이 스크립트를 실행하지 않는다 — 실행 환경(모델 가중치·하드웨어)이 사용자 쪽에
있고, #42가 확정한 `qwen3-embedding:4b` 수치와 같은 환경에서 나온 값이어야 α가 그 임베딩
위에서 유효하기 때문이다(스펙 §1 선행 조건 · §4.8 역할 분담).

사전 준비:
    ollama serve
    corpbrain scan docs/smoke/corpus --out "$OUT" --force-gates

사용법 (리포지토리 루트에서):
    uv run python docs/smoke/graph_decay_sweep.py --out "$OUT"

    --alphas, --top-k, --expand-edges, --corpus, --queries, --results 로 조건을 바꿀 수 있다.

산출물:
    <results>.json — α별 지표와 쿼리별 상세(1순위 문서·적중 여부·RR·Recall@3)
    <results>.csv  — α, 쿼리, 1순위 문서, 적중 여부, RR, Recall@3
    표준출력에 α별 지표 요약 표와 §4.8 4번 규칙이 고른 α.

**측정은 사용자와 같은 경로를 쓴다.** 별도 랭킹 구현을 두지 않고 `corpbrain.core.search_index()`
를 `graph_decay`·`expand_edges`만 바꿔 가며 반복 호출한다 — CLI(`corpbrain search`)는 인자를
파싱해 같은 함수를 부르는 얇은 어댑터이므로, 여기서 잰 값과 실제 CLI 동작이 어긋날 수 없다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from corpbrain.core.config import DEFAULT_EXPAND_EDGES, DEFAULT_OLLAMA_URL
from corpbrain.core.errors import CorpBrainError
from corpbrain.core.graph import parse_expand_edges
from corpbrain.core.models import EdgeType, SearchResult
from corpbrain.core.search import search_index
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

#: 스펙 §4.8 3번이 정한 스윕 범위. 0.05 간격.
DEFAULT_ALPHAS = [round(0.5 + 0.05 * step, 2) for step in range(10)]

#: Recall 을 재는 상위 구간 — §4.8 4번의 3번째 동률 지표다.
RECALL_AT = 3

DEFAULT_CORPUS = Path("docs/smoke/corpus")
DEFAULT_QUERIES = Path("docs/smoke/graph_decay_queries.json")
DEFAULT_RESULTS = Path("docs/smoke/graph_decay_results")

#: 코사인 단독 기준선 행의 라벨. α 후보와 같은 표에 놓아 «그래프가 도움이 되긴 하는가»를
#: 먼저 보게 한다 — 확산이 기준선보다 나쁘면 값을 고르는 것 자체가 무의미하다.
BASELINE = "no-graph"


@dataclass(frozen=True)
class Labeled:
    """쿼리 1건과 사람이 라벨링한 정답 문서들 (`doc_id` = 원문 절대경로)."""

    query: str
    relevant: frozenset[str]
    #: 리포트에 그대로 싣는, 코퍼스 루트 기준 상대경로 원본.
    relative: tuple[str, ...]


def load_queries(queries_path: Path, corpus_dir: Path) -> list[Labeled]:
    """쿼리 세트를 읽어 정답 경로를 `doc_id`(원문 절대경로)로 바꾼다.

    `scan` 은 스캔 루트를 `resolve()` 한 뒤 순회하므로 저장된 `doc_id` 는 절대경로다.
    여기서 같은 규칙으로 만들어야 «정답인데 못 맞혔다»가 경로 표기 차이로 생기지 않는다.
    """
    raw = json.loads(queries_path.read_text(encoding="utf-8"))
    labeled: list[Labeled] = []
    for entry in raw:
        relative = tuple(entry["relevant"])
        labeled.append(
            Labeled(
                query=entry["query"],
                relevant=frozenset(str((corpus_dir / rel).resolve()) for rel in relative),
                relative=relative,
            )
        )
    return labeled


def check_queries_against_index(labeled: list[Labeled], out_dir: Path) -> list[str]:
    """정답 문서가 실제로 인덱싱돼 있는지 확인한다. 문제 목록(사람이 읽을 문자열)을 돌려준다.

    비어 있지 않으면 스윕을 시작하지 않는다 — 인덱스에 없는 문서를 정답으로 두면 어떤 α도
    그 쿼리를 맞힐 수 없어, 「α가 나쁘다」와 「라벨이 틀렸다」가 구분되지 않는다.
    """
    store = SqliteVectorStore(index_path_for(out_dir))
    try:
        known = set(store.list_ids())
    finally:
        store.close()
    problems: list[str] = []
    for item in labeled:
        missing = sorted(item.relevant - known)
        if missing:
            problems.append(f"«{item.query}» 의 정답이 인덱스에 없다: {missing}")
    return problems


def score_query(results: list[SearchResult], relevant: frozenset[str]) -> dict[str, float | str]:
    """한 쿼리의 지표 — top-1 적중 · RR · Recall@3 (스펙 §4.8 4번)."""
    ids = [result.doc_id for result in results]
    hit = bool(ids) and ids[0] in relevant
    rank = next((i for i, doc_id in enumerate(ids, start=1) if doc_id in relevant), 0)
    found = len(relevant & set(ids[:RECALL_AT]))
    return {
        "top1_doc": ids[0] if ids else "",
        "top1_hit": hit,
        "reciprocal_rank": 1.0 / rank if rank else 0.0,
        f"recall_at_{RECALL_AT}": found / len(relevant) if relevant else 0.0,
    }


def run_setting(
    label: str,
    labeled: list[Labeled],
    *,
    out_dir: Path,
    top_k: int,
    ollama_url: str,
    expand_edges: frozenset[EdgeType],
    graph: bool,
    graph_decay: float,
) -> dict:
    rows = []
    for item in labeled:
        results = search_index(
            out_dir,
            item.query,
            top_k=top_k,
            ollama_url=ollama_url,
            graph=graph,
            graph_decay=graph_decay,
            expand_edges=expand_edges,
        )
        rows.append(
            {
                "query": item.query,
                "relevant": list(item.relative),
                "expanded": [r.doc_id for r in results if r.expansion is not None],
                **score_query(results, item.relevant),
            }
        )
    total = len(rows) or 1
    return {
        "setting": label,
        "graph_decay": None if not graph else graph_decay,
        "top1_hit_rate": sum(bool(row["top1_hit"]) for row in rows) / total,
        "mrr": sum(float(row["reciprocal_rank"]) for row in rows) / total,
        f"recall_at_{RECALL_AT}": sum(float(row[f"recall_at_{RECALL_AT}"]) for row in rows) / total,
        "queries": rows,
    }


def selection_key(result: dict) -> tuple[float, float, float, float]:
    """스펙 §4.8 4번의 동률 처리 순서 — top-1 → MRR → Recall@3 → α가 작은 쪽.

    마지막 키를 두는 이유는 임의 선택을 남기지 않기 위해서다. α가 작을수록 그래프 개입이
    적어 v0.4 동작에 가깝고 되돌릴 일이 적다.
    """
    return (
        -result["top1_hit_rate"],
        -result["mrr"],
        -result[f"recall_at_{RECALL_AT}"],
        float(result["graph_decay"]),
    )


def write_outputs(results: list[dict], baseline: dict, out_prefix: Path) -> None:
    payload = {"baseline": baseline, "sweep": results}
    json_path = out_prefix.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out_prefix.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["setting", "query", "top1_doc", "top1_hit", "reciprocal_rank", f"recall_at_{RECALL_AT}"]
        )
        for result in [baseline, *results]:
            for row in result["queries"]:
                writer.writerow(
                    [
                        result["setting"],
                        row["query"],
                        row["top1_doc"],
                        row["top1_hit"],
                        f"{float(row['reciprocal_rank']):.4f}",
                        f"{float(row[f'recall_at_{RECALL_AT}']):.4f}",
                    ]
                )

    print(f"\n결과 저장: {json_path}, {csv_path}\n")
    header = f"{'설정':<12} {'top-1 적중률':>14} {'MRR':>8} {f'Recall@{RECALL_AT}':>12}"
    print(header)
    for result in [baseline, *results]:
        print(
            f"{result['setting']:<12} {result['top1_hit_rate']:>13.2%} "
            f"{result['mrr']:>8.4f} {result[f'recall_at_{RECALL_AT}']:>12.4f}"
        )

    best = min(results, key=selection_key)
    print(f"\n§4.8 4번 규칙이 고른 α: {best['graph_decay']}")
    # 앞 세 키는 «클수록 좋은» 지표를 음수로 담고 있으므로, 기준선 쪽이 더 작거나 같으면
    # 확산이 코사인 단독을 이기지 못한 것이다. 그때는 값을 고르는 것 자체가 무의미하다.
    if selection_key(baseline | {"graph_decay": 0.0})[:3] <= selection_key(best)[:3]:
        print(
            "⚠️  그래프 확산이 코사인 단독(no-graph)보다 낫지 않다 — 값을 고르기 전에 "
            "왜 그런지부터 본다(쿼리 세트·그래프 재료·임베딩 모델)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, required=True, help="scan --out 으로 만든 폴더.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--ollama-url", type=str, default=DEFAULT_OLLAMA_URL)
    parser.add_argument(
        "--alphas",
        type=str,
        default=",".join(str(alpha) for alpha in DEFAULT_ALPHAS),
        help="스윕할 α 목록(쉼표 구분). 기본은 스펙 §4.8 3번의 0.5~0.95를 0.05 간격으로.",
    )
    parser.add_argument(
        "--expand-edges",
        type=str,
        default=None,
        help="확산에 쓸 엣지 종류(쉼표 구분). 생략하면 코어 기본 3종.",
    )
    args = parser.parse_args(argv)

    labeled = load_queries(args.queries, args.corpus)
    if not labeled:
        print(f"쿼리 세트가 비어 있다: {args.queries}", file=sys.stderr)
        return 1

    try:
        expand_edges = (
            parse_expand_edges(args.expand_edges) if args.expand_edges else DEFAULT_EXPAND_EDGES
        )
    except CorpBrainError as exc:
        print(f"--expand-edges 오류: {exc}", file=sys.stderr)
        return 1

    problems = check_queries_against_index(labeled, args.out)
    if problems:
        for problem in problems:
            print(f"쿼리 세트 불일치 — {problem}", file=sys.stderr)
        print(
            "정답 경로가 코퍼스와 맞는지, `scan` 이 그 문서를 실제로 인덱싱했는지 확인한다.",
            file=sys.stderr,
        )
        return 1

    common = {
        "out_dir": args.out,
        "top_k": args.top_k,
        "ollama_url": args.ollama_url,
        "expand_edges": expand_edges,
    }
    print(f"[{BASELINE}] 코사인 단독 기준선 측정 중... (쿼리 {len(labeled)}개)", file=sys.stderr)
    # α는 쓰이지 않지만 코어가 값 자체를 무조건 검증하므로(§4.5) 유효 범위의 값을 넘긴다.
    baseline = run_setting(BASELINE, labeled, graph=False, graph_decay=0.5, **common)

    results = []
    for raw in args.alphas.split(","):
        alpha = float(raw.strip())
        print(f"[α={alpha}] 측정 중... (쿼리 {len(labeled)}개)", file=sys.stderr)
        try:
            results.append(
                run_setting(f"α={alpha}", labeled, graph=True, graph_decay=alpha, **common)
            )
        except CorpBrainError as exc:
            print(f"[α={alpha}] 건너뜀 — {exc}", file=sys.stderr)

    if not results:
        print("모든 α가 실패했다.", file=sys.stderr)
        return 1

    write_outputs(results, baseline, args.results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
