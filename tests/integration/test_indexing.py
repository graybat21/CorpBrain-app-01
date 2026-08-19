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

TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
SUMMARY_JSON = {
    "title": "제목",
    "one_line_summary": "한 줄",
    "key_points": ["a", "b", "c"],
    "summary": "요약",
    "tags": ["t"],
}


def _vector_for(path_str: str) -> list[float]:
    """경로 문자열에서 결정적으로 다른 벡터를 만든다(파일마다 실제로 다른 벡터가 저장됨을 검증)."""
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
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

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
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

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
