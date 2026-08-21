"""검색 — 벡터 인덱스에서 쿼리와 유사한 문서를 찾는다 (v0.4 스펙 §3 항목6·7, §4.1).

인덱스 파일이 없으면 `IndexNotFoundError`(선행 조건 실패, exit 1). 인덱스가 있지만 결과가
0건이면 빈 리스트를 정상 반환한다(exit 0 — 스펙 §3 항목6). 쿼리 임베딩은 인덱스 메타데이터에
기록된 모델을 강제로 쓴다(스펙 §4.3 — `search`에는 `--embed-model` 플래그가 없다).
"""

from __future__ import annotations

from pathlib import Path

from corpbrain.core.config import DEFAULT_OLLAMA_URL
from corpbrain.core.errors import PreconditionError
from corpbrain.core.llm.embed import EmbeddingError, embed
from corpbrain.core.models import SearchResult
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

__all__ = ["IndexNotFoundError", "search_index"]


class IndexNotFoundError(PreconditionError):
    """인덱스 파일이 없거나 비어 있음 — 먼저 `scan`을 실행해야 한다 (v0.4 스펙 §3 항목6)."""


def search_index(
    out_dir: Path,
    query: str,
    *,
    top_k: int = 5,
    ollama_url: str = DEFAULT_OLLAMA_URL,
) -> list[SearchResult]:
    """`out_dir`의 인덱스에서 `query`와 유사한 문서 상위 `top_k`건을 돌려준다.

    Args:
        out_dir: `scan --out`으로 위키·인덱스가 쌓인 폴더.
        query: 자연어 검색어.
        top_k: 반환할 최대 결과 수.
        ollama_url: `--ollama-url` 값. 이 대상 외에는 접속하지 않는다.

    Raises:
        IndexNotFoundError: `out_dir`에 인덱스 파일이 없거나(먼저 scan 필요) 비어 있음.
    """
    path = index_path_for(out_dir)
    if not path.exists():
        raise IndexNotFoundError(
            f"인덱스가 없습니다: {path} — 먼저 `corpbrain scan {out_dir}`을 실행하세요."
        )

    store = SqliteVectorStore(path)
    try:
        model = store.model_name
        if model is None:
            raise IndexNotFoundError(
                f"인덱스가 비어 있습니다: {path} — 먼저 `corpbrain scan {out_dir}`을 실행하세요."
            )
        try:
            query_vector = embed(query, model, ollama_url)
        except EmbeddingError as exc:
            raise PreconditionError(f"쿼리 임베딩에 실패했습니다: {exc}") from exc
        return store.search(query_vector, top_k)
    finally:
        store.close()
