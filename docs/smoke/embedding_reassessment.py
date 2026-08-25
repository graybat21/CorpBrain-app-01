"""v0.7 임베딩 모델 재판단 — 결정적 측정 스크립트 (issue #42, 스펙 §4.4).

사용자가 로컬 Ollama에 후보 모델을 미리 pull한 뒤 이 스크립트를 실행한다.
구현 세션은 이 스크립트를 실행하지 않는다 — 실측은 사용자가 로컬에서 수행하고
원시 출력(표준출력 + 생성된 json/csv)을 구현 세션에 전달한다.

사전 준비:
    ollama serve
    ollama pull nomic-embed-text
    ollama pull bge-m3
    ollama pull qwen3-embedding:4b
    ollama pull bona/bge-m3-korean
    ollama pull hf.co/mykor/KURE-v1-gguf

사용법 (리포지토리 루트에서):
    uv run python docs/smoke/embedding_reassessment.py \
        --corpus docs/smoke/corpus \
        --out docs/smoke/embedding_reassessment_results

    --models, --ollama-url 로 후보 모델 목록·서버 주소를 바꿀 수 있다.

산출물:
    <out>.json — 모델별 top-1 적중률·문서별 적중 여부·전 쌍 코사인 값 원본
    <out>.csv  — 전 쌍 코사인 값(모델, 문서 A, 문서 B, 코사인)
    표준출력에 모델별 top-1 적중률 요약 표.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from corpbrain.core.vectorstore import cosine_similarity

DEFAULT_MODELS = [
    "nomic-embed-text",
    "bge-m3",
    "qwen3-embedding:4b",
    "bona/bge-m3-korean",
    "hf.co/mykor/KURE-v1-gguf",
]

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
EMBED_PATH = "/api/embeddings"

# docs/smoke/README.md §3.2 "참조 관계(설계 의도)"를 그대로 인코딩한 것 — 정본은 README다.
# 값은 "의도된 관련 문서" 집합(양방향으로 취급). 고립 문서는 여기 없다 — top-1 평가에서
# 자동으로 제외된다(top1_hit_rate가 GROUND_TRUTH에 있는 문서만 평가 대상으로 삼는다).
GROUND_TRUTH: dict[str, set[str]] = {
    "인사/채용계획.md": {"인사/온보딩.md", "인사/조직개편.md"},
    "인사/온보딩.md": {"인사/채용계획.md", "인사/평가제도.md", "인사/복지제도.md"},
    "인사/평가제도.md": {"인사/온보딩.md"},
    "인사/복지제도.md": {"인사/온보딩.md"},
    "인사/조직개편.md": {"인사/채용계획.md"},
    "개발/아키텍처.md": {
        "개발/README.md",
        "개발/벡터설계.md",
        "개발/그래프설계.md",
        "개발/API설계.md",
        "개발/테스트전략.md",
    },
    "개발/README.md": {"개발/아키텍처.md", "개발/벡터설계.md", "개발/테스트전략.md"},
    "개발/벡터설계.md": {"개발/아키텍처.md", "개발/README.md", "개발/그래프설계.md"},
    "개발/그래프설계.md": {"개발/아키텍처.md", "개발/벡터설계.md"},
    "개발/API설계.md": {"개발/아키텍처.md"},
    "개발/테스트전략.md": {"개발/README.md", "개발/아키텍처.md"},
    "재무/예산계획.md": {"재무/지출보고.md", "재무/투자계획.md"},
    "재무/지출보고.md": {"재무/예산계획.md", "재무/원가분석.md", "재무/투자계획.md", "재무/감사대응.md"},
    "재무/회계정책.md": {"재무/예산계획.md", "재무/감사대응.md"},
    "재무/원가분석.md": {"재무/지출보고.md", "재무/투자계획.md"},
    "재무/투자계획.md": {"재무/예산계획.md", "재무/원가분석.md", "재무/지출보고.md"},
    "재무/감사대응.md": {"재무/회계정책.md", "재무/지출보고.md"},
    "마케팅/캠페인기획.md": {
        "마케팅/소셜미디어전략.md",
        "마케팅/브랜드가이드.md",
        "마케팅/파트너십제휴.md",
        "마케팅/고객설문분석.md",
    },
    "마케팅/소셜미디어전략.md": {"마케팅/캠페인기획.md", "마케팅/브랜드가이드.md", "마케팅/고객설문분석.md"},
    "마케팅/브랜드가이드.md": {"마케팅/캠페인기획.md", "마케팅/소셜미디어전략.md", "마케팅/파트너십제휴.md"},
    "마케팅/고객설문분석.md": {"마케팅/캠페인기획.md", "마케팅/소셜미디어전략.md"},
    "마케팅/파트너십제휴.md": {"마케팅/캠페인기획.md", "마케팅/브랜드가이드.md"},
}

# GROUND_TRUTH에 없는, 다른 문서와 의도적으로 무관한 문서. top-1 평가 대상이 아니다.
ISOLATED_DOCS: set[str] = {"기타/메모.md", "법무/계약검토메모.md"}


class EmbeddingRequestError(RuntimeError):
    """Ollama 임베딩 요청이 실패했을 때."""


def embed_text(text: str, model: str, ollama_url: str, timeout: float = 120.0) -> list[float]:
    """Ollama 로컬 임베딩 API를 호출한다.

    이 스크립트는 corpbrain 코어의 단일 게이트웨이(`corpbrain.core.gateway`)를 거치지
    않는다 — 프로덕션 코드가 아니라 일회성 개발자 도구이기 때문이다(스펙 §2 비목표).
    """
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}{EMBED_PATH}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EmbeddingRequestError(f"{model} 임베딩 요청 실패: {exc}") from exc
    vector = body.get("embedding")
    if not isinstance(vector, list):
        raise EmbeddingRequestError(f"{model} 응답에 embedding 배열이 없다: {body!r}")
    return vector


def load_corpus(corpus_dir: Path) -> dict[str, str]:
    """corpus_dir 하위 `.md` 파일을 {상대경로: 본문} 으로 읽는다. 경로 구분자는 '/'로 정규화한다."""
    docs: dict[str, str] = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        rel = path.relative_to(corpus_dir).as_posix()
        docs[rel] = path.read_text(encoding="utf-8")
    return docs


def check_ground_truth_matches_corpus(doc_ids: set[str]) -> list[str]:
    """GROUND_TRUTH·ISOLATED_DOCS의 키 집합이 실제 코퍼스 파일과 정확히 일치하는지 확인한다.
    불일치 목록(사람이 읽을 문자열)을 돌려준다 — 비어 있으면 문제 없음."""
    known = set(GROUND_TRUTH) | ISOLATED_DOCS
    problems = []
    missing_on_disk = known - doc_ids
    missing_in_map = doc_ids - known
    if missing_on_disk:
        problems.append(f"GROUND_TRUTH/ISOLATED_DOCS에는 있지만 코퍼스에 없는 문서: {sorted(missing_on_disk)}")
    if missing_in_map:
        problems.append(f"코퍼스에는 있지만 GROUND_TRUTH/ISOLATED_DOCS에 없는 문서: {sorted(missing_in_map)}")
    return problems


def nearest_neighbor(doc_id: str, vectors: dict[str, list[float]]) -> str | None:
    """doc_id를 제외한 나머지 중 코사인 유사도가 가장 높은 문서 id. 후보가 없으면 None."""
    best_id: str | None = None
    best_score = float("-inf")
    for other_id, other_vec in vectors.items():
        if other_id == doc_id:
            continue
        score = cosine_similarity(vectors[doc_id], other_vec)
        if score > best_score:
            best_score = score
            best_id = other_id
    return best_id


def top1_hit_rate(vectors: dict[str, list[float]]) -> tuple[float, dict[str, bool]]:
    """GROUND_TRUTH에 있는 평가 대상 문서 중, 코사인 1위 이웃이 의도된 관련 문서 집합
    안에 있는 비율과 문서별 적중 여부를 돌려준다."""
    evaluable = [d for d in vectors if d in GROUND_TRUTH]
    hits: dict[str, bool] = {}
    for doc_id in evaluable:
        neighbor = nearest_neighbor(doc_id, vectors)
        hits[doc_id] = neighbor in GROUND_TRUTH.get(doc_id, set())
    rate = sum(hits.values()) / len(hits) if hits else 0.0
    return rate, hits


def pairwise_matrix(vectors: dict[str, list[float]]) -> list[tuple[str, str, float]]:
    """전체 문서 쌍(중복 없이)의 코사인 유사도 목록."""
    ids = sorted(vectors)
    rows: list[tuple[str, str, float]] = []
    for i, doc_a in enumerate(ids):
        for doc_b in ids[i + 1 :]:
            rows.append((doc_a, doc_b, cosine_similarity(vectors[doc_a], vectors[doc_b])))
    return rows


def run_model(model: str, docs: dict[str, str], ollama_url: str) -> dict:
    vectors = {doc_id: embed_text(text, model, ollama_url) for doc_id, text in docs.items()}
    rate, hits = top1_hit_rate(vectors)
    matrix = pairwise_matrix(vectors)
    return {
        "model": model,
        "top1_hit_rate": rate,
        "hits": hits,
        "pairwise": matrix,
    }


def write_outputs(results: list[dict], out_prefix: Path) -> None:
    json_path = out_prefix.with_suffix(".json")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = out_prefix.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model", "doc_a", "doc_b", "cosine"])
        for result in results:
            for doc_a, doc_b, score in result["pairwise"]:
                writer.writerow([result["model"], doc_a, doc_b, f"{score:.6f}"])

    print(f"\n결과 저장: {json_path}, {csv_path}\n")
    print(f"{'모델':<28} {'top-1 적중률':>14}")
    for result in results:
        hit_n = sum(result["hits"].values())
        total = len(result["hits"])
        pct = result["top1_hit_rate"]
        print(f"{result['model']:<28} {hit_n}/{total} ({pct:.2%})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=Path("docs/smoke/corpus"))
    parser.add_argument("--models", type=str, default=",".join(DEFAULT_MODELS))
    parser.add_argument("--ollama-url", type=str, default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--out", type=Path, default=Path("docs/smoke/embedding_reassessment_results"))
    args = parser.parse_args(argv)

    docs = load_corpus(args.corpus)
    if not docs:
        print(f"코퍼스에 문서가 없다: {args.corpus}", file=sys.stderr)
        return 1

    problems = check_ground_truth_matches_corpus(set(docs))
    if problems:
        for problem in problems:
            print(f"GROUND_TRUTH 불일치 — {problem}", file=sys.stderr)
        return 1

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results = []
    for model in models:
        print(f"[{model}] 임베딩 중... ({len(docs)}개 문서)", file=sys.stderr)
        try:
            results.append(run_model(model, docs, args.ollama_url))
        except EmbeddingRequestError as exc:
            print(f"[{model}] 건너뜀 — {exc}", file=sys.stderr)

    if not results:
        print("모든 모델이 실패했다.", file=sys.stderr)
        return 1

    write_outputs(results, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
