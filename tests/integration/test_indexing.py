"""벡터 인덱싱 통합 테스트 (v0.4 스펙 §3 완료의 정의 1~5).

Ollama HTTP는 단일 관문을 스텁하고, `run_scan`을 코어 API로 직접 호출한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.pipeline import run_scan
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

TAGS_RESPONSE = {
    "models": [
        {"name": DEFAULT_MODEL},
        {"name": DEFAULT_EMBED_MODEL},
        {"name": "other-embed-model"},  # 임베딩 모델 혼입 거부 테스트용으로 설치된 것으로 취급
    ]
}


def _summary_json_for(document_text: str) -> dict[str, Any]:
    """요약 프롬프트(문서 본문 포함)에서 문서마다 다른 요약을 만든다.

    모든 문서가 같은 고정 SUMMARY_JSON을 쓰면 summary_embedding_text()가 문서마다 동일한
    텍스트를 만들어, 벡터가 실제로 문서별로 달라지는지 이 테스트 모음이 전혀 검증하지 못한다
    (코드리뷰 finding). 문서 본문을 제목에 그대로 반영해 문서마다 다른 요약 텍스트가 임베딩
    프롬프트로 넘어가게 한다.
    """
    return {
        "title": f"제목: {document_text}",
        "one_line_summary": "한 줄",
        "key_points": ["a", "b", "c"],
        "summary": "요약",
        "tags": ["t"],
    }


def _vector_for(path_str: str) -> list[float]:
    """임베딩 프롬프트 문자열에서 결정적으로 다른 벡터를 만든다(문서별 요약이 다르면 벡터도 달라짐)."""
    seed = sum(ord(ch) for ch in path_str) % 100
    return [float(seed), 1.0 - float(seed) / 100]


@pytest.fixture
def ok_gateway(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        calls.append(url)
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": _vector_for(payload["prompt"])}
        summary = _summary_json_for(payload["prompt"])
        return {"response": json.dumps(summary, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)
    return calls


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "a.txt").write_text("문서 A 본문", encoding="utf-8")
    (root / "b.txt").write_text("문서 B 본문", encoding="utf-8")
    return root


def _config(root: Path, out_dir: Path, **overrides: Any) -> ScanConfig:
    overrides.setdefault("force_gates", True)
    return ScanConfig(folder=root, out_dir=out_dir, **overrides)


# --- 완료의 정의 1: 임베딩 모델 프리플라이트 ------------------------------------


def test_scan_blocks_when_embed_model_missing(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": DEFAULT_MODEL}]}  # 임베딩 모델 부재
        raise AssertionError("임베딩 모델 부재 시 요약·임베딩 호출까지 가면 안 된다")

    monkeypatch.setattr(gateway, "request_json", _request_json)
    out_dir = tmp_path / "wiki"

    with pytest.raises(PreconditionError, match=DEFAULT_EMBED_MODEL):
        run_scan(_config(corpus, out_dir))

    assert not out_dir.exists()


# --- 완료의 정의 2: 정상 실행 시 문서마다 임베딩이 인덱스에 저장 ----------------


def test_generated_documents_are_indexed(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    assert len(result.generated) == 2
    assert result.embedding_failures == []
    store = SqliteVectorStore(index_path_for(out_dir))
    assert set(store.list_ids()) == {str(corpus / "a.txt"), str(corpus / "b.txt")}
    assert store.model_name == DEFAULT_EMBED_MODEL

    # 두 문서가 실제로 서로 다른 벡터로 저장됐는지 직접 확인한다(같은 텍스트가 모든 문서에
    # 임베딩되는 회귀가 나면, doc_id 집합만 보는 검증은 이를 놓친다 — 코드리뷰 finding).
    top = store.search([1.0, 1.0], top_k=2)
    assert len(top) == 2
    assert top[0].metadata != top[1].metadata


# --- 완료의 정의 3: 증분 규칙 — 위키 스킵돼도 인덱스 없으면 채움, 있으면 유지 --


def test_up_to_date_skip_keeps_existing_vector_without_reembedding(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))
    embed_calls_after_first = sum(1 for u in ok_gateway if u.endswith("/api/embeddings"))
    assert embed_calls_after_first == 2

    ok_gateway.clear()
    result = run_scan(_config(corpus, out_dir))  # 원문 안 바뀜 → 위키 스킵

    assert len(result.generated) == 0
    assert all(u.endswith("/api/embeddings") is False for u in ok_gateway)  # 재계산 없음


def test_backfill_embeds_existing_wiki_when_index_missing_entry(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    """v0.3 위키 폴더에 처음 v0.4 scan을 돌리는 경우를 흉내: 위키는 있지만 인덱스가 비어 있다."""
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    # 인덱스를 지워 "이미 위키는 있지만 벡터가 없는" 상태를 만든다.
    index_path_for(out_dir).unlink()
    ok_gateway.clear()

    result = run_scan(_config(corpus, out_dir))

    assert len(result.generated) == 0  # 위키 자체는 재생성되지 않음(mtime 안 바뀜)
    assert result.embedding_failures == []
    embed_calls = [u for u in ok_gateway if u.endswith("/api/embeddings")]
    assert len(embed_calls) == 2  # 백필로 두 문서 모두 재임베딩됨
    store = SqliteVectorStore(index_path_for(out_dir))
    assert set(store.list_ids()) == {str(corpus / "a.txt"), str(corpus / "b.txt")}


def test_force_regenerates_wiki_and_vector(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))
    ok_gateway.clear()

    result = run_scan(_config(corpus, out_dir, force=True))

    assert len(result.generated) == 2
    embed_calls = [u for u in ok_gateway if u.endswith("/api/embeddings")]
    assert len(embed_calls) == 2


# --- 완료의 정의 4: 프리플라이트 통과 후 런타임 임베딩 실패는 위키를 남기고 스킵 ---


def test_runtime_embedding_failure_keeps_wiki_and_reports_failure(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            raise gateway.GatewayError("타임아웃", url=url)
        summary = _summary_json_for(payload["prompt"])
        return {"response": json.dumps(summary, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    assert len(result.generated) == 2  # 위키는 정상 생성됨
    assert (out_dir / "a.txt.md").exists()
    assert len(result.embedding_failures) == 2  # 인덱싱만 실패로 기록
    store = SqliteVectorStore(index_path_for(out_dir))
    assert store.list_ids() == []  # 아무것도 인덱싱되지 않음


# --- 완료의 정의 5: 원문/위키 삭제 시 고아 벡터 정리 ---------------------------


def test_deleted_source_prunes_its_vector_on_rescan(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    (corpus / "b.txt").unlink()
    (out_dir / "b.txt.md").unlink()

    run_scan(_config(corpus, out_dir))

    store = SqliteVectorStore(index_path_for(out_dir))
    assert store.list_ids() == [str(corpus / "a.txt")]


def test_narrower_rescan_does_not_prune_vectors_outside_its_scope(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    """코드리뷰 finding: 하위 폴더만 좁혀 재스캔해도, 이번 스캔 범위 밖의 원문·위키가 그대로인
    문서의 벡터는 고아로 오인해 지우면 안 된다."""
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))  # corpus 전체(a.txt, b.txt) 인덱싱

    sub = corpus / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("문서 C 본문", encoding="utf-8")
    run_scan(_config(sub, out_dir))  # sub만 좁혀서 재스캔 — a.txt/b.txt는 스캔 범위 밖

    store = SqliteVectorStore(index_path_for(out_dir))
    assert str(corpus / "a.txt") in store.list_ids()
    assert str(corpus / "b.txt") in store.list_ids()
    assert str(sub / "c.txt") in store.list_ids()


# --- 임베딩 모델 혼입 방지 (코드리뷰 finding) -----------------------------------


def test_scan_rejects_reindexing_with_a_different_embed_model(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    """이미 다른 임베딩 모델로 만들어진 인덱스에 다른 모델로 재스캔하면 벡터가 섞이므로 거부한다."""
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir, embed_model=DEFAULT_EMBED_MODEL))

    with pytest.raises(PreconditionError, match="다른 임베딩 모델"):
        run_scan(_config(corpus, out_dir, embed_model="other-embed-model"))


def test_scan_reports_clean_error_on_corrupted_index_file(
    corpus: Path, tmp_path: Path, ok_gateway: list[str]
) -> None:
    """스펙 §5: 인덱스 파일이 손상되어 있으면 크래시 대신 PreconditionError로 안내한다."""
    out_dir = tmp_path / "wiki"
    out_dir.mkdir()
    index_path_for(out_dir).write_text("이 파일은 sqlite db가 아니다", encoding="utf-8")

    with pytest.raises(PreconditionError, match="인덱스"):
        run_scan(_config(corpus, out_dir))
