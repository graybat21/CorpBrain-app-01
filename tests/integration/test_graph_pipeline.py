"""v0.6 지식그래프 — 완료의 정의 1·2·4·5·6·7 (스펙 §3).

코퍼스는 `tmp_path`에 인라인 생성한다 (§3 픽스처 구성). 통합테스트에서 태그·엔티티·벡터는
파일 내용이 아니라 `gateway.request_json` 스텁이 결정하므로, 4종 엣지 중 실제 파일 텍스트에
의존하는 것은 `REFERENCES`뿐이다 — 스텁 값과 기대 엣지가 이 파일에 나란히 놓인다.
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from docx import Document

from corpbrain.core import ScanConfig, run_scan
from corpbrain.core import gateway as gateway_module
from corpbrain.core.graphstore import graph_path_for
from corpbrain.core.models import GraphSkipReason
from corpbrain.core.render import (
    RELATED_EMPTY,
    RELATED_MARKER_END,
    RELATED_MARKER_START,
)
from corpbrain.core.report import build_summary_lines
from corpbrain.core.vectorstore import cosine_similarity

# --- 코퍼스 (스펙 §3 표) --------------------------------------------------------

FILES = {
    "인사/채용계획.docx": "2026년 신입 채용 계획. 입사 후 절차는 온보딩.md 를 참조한다.",
    "인사/온보딩.md": "신규 입사자 안내. 채용 일정은 채용계획.docx 를 참조한다.",
    "개발/아키텍처.md": "코어와 어댑터를 분리한다. 저장소 규약은 README.md 에 있다.",
    "개발/벡터설계.md": "임베딩과 벡터 인덱스 설계.",
    "개발/README.md": "이 파일(README.md)은 개발 폴더의 개요를 담는다.",
    "기타/메모.txt": "개인적으로 남기는 짧은 메모.",
}

#: 스텁이 문서마다 돌려줄 요약 필드. `개발/README.md`는 `entities` 키 자체를 뺀다 —
#: 선택 필드이므로 위키는 정상 생성되고 CONTAINS_ENTITY 엣지만 없어야 한다 (§4.2).
SUMMARIES: dict[str, dict[str, Any]] = {
    "인사/채용계획.docx": {"tags": ["인사", "채용"], "entities": ["인사팀"]},
    "인사/온보딩.md": {"tags": ["인사", "온보딩"], "entities": ["인사 팀"]},
    "개발/아키텍처.md": {"tags": ["설계", "아키텍처"], "entities": ["코어"]},
    "개발/벡터설계.md": {"tags": ["설계", "벡터"], "entities": ["코어"]},
    "개발/README.md": {"tags": ["안내"]},
    "기타/메모.txt": {"tags": ["메모"], "entities": ["개인"]},
}


def _orthogonal_pair(cosine: float, base: list[float]) -> list[float]:
    """`base`와 정확히 `cosine`을 이루는 단위벡터 (base[1] == 0 을 전제)."""
    lift = math.sqrt(max(0.0, 1.0 - cosine * cosine))
    return [cosine * base[0], lift, cosine * base[2], 0.0]


AXIS = [1.0, 0.0, 0.0, 0.0]
C_AXIS = [0.30, 0.0, math.sqrt(1.0 - 0.09), 0.0]

#: 짧은 직교 기저 조합 — 코사인만 의도대로 나오면 되고 짧을수록 테스트가 읽힌다 (§3).
VECTORS: dict[str, list[float]] = {
    "인사/채용계획.docx": AXIS,
    "인사/온보딩.md": _orthogonal_pair(0.81, AXIS),
    "개발/아키텍처.md": C_AXIS,
    "개발/벡터설계.md": _orthogonal_pair(0.75, C_AXIS),
    "개발/README.md": [0.0, 0.0, 0.0, 1.0],
    "기타/메모.txt": [0.0, 0.0, 0.0, -1.0],
}

#: 「개발/아키텍처.md」와 「개발/벡터설계.md」의 실측 코사인. 임계치를 **이 값 그대로** 주어
#: 부동소수 왕복 없이 `>=` 경계(같은 값을 포함하는가)를 검증한다 (§3).
THRESHOLD = cosine_similarity(VECTORS["개발/아키텍처.md"], VECTORS["개발/벡터설계.md"])


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    for relative, text in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".docx":
            document = Document()
            document.add_paragraph(text)
            document.save(path)
        else:
            path.write_text(text, encoding="utf-8")
    return root


def _which(prompt: str) -> str:
    """프롬프트가 어느 문서의 것인지 가린다.

    임베딩 호출은 원문이 아니라 **요약 텍스트**를 받는다. 그래서 스텁 요약에 상대경로를
    심어 두고 그것을 먼저 맞춘다. 요약 호출은 원문을 받으므로 내용 앞부분으로 맞춘다 —
    파일명으로 맞추면 서로를 참조하는 문서(A 본문에 B의 파일명)에서 오판한다.
    """
    for relative in FILES:
        if relative in prompt:
            return relative
    for relative, text in FILES.items():
        if text[:12] in prompt:
            return relative
    raise AssertionError(f"어느 문서인지 판별하지 못했습니다: {prompt[:80]!r}")


def _stub(*, with_vectors: bool = True):
    def request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen2.5:7b-instruct"}, {"name": "nomic-embed-text"}]}
        prompt = (payload or {}).get("prompt", "")
        if url.endswith("/api/embeddings"):
            assert with_vectors, "벡터 없는 시나리오에서는 임베딩을 호출하지 않는다"
            return {"embedding": VECTORS[_which(prompt)]}
        relative = _which(prompt)
        fields = SUMMARIES[relative]
        return {
            "response": json.dumps(
                {
                    "title": Path(relative).stem,
                    "one_line_summary": f"{relative} 한 줄 요약",
                    "key_points": ["포인트1", "포인트2", "포인트3"],
                    "summary": f"{relative} 문단 요약",
                    **fields,
                },
                ensure_ascii=False,
            )
        }

    return request_json


def _config(corpus: Path, out_dir: Path, **overrides: Any) -> ScanConfig:
    params: dict[str, Any] = {
        "folder": corpus,
        "out_dir": out_dir,
        "force_gates": True,
        "similarity_threshold": THRESHOLD,
    }
    params.update(overrides)
    return ScanConfig(**params)


def _edges(out_dir: Path) -> set[tuple[str, str, str]]:
    conn = sqlite3.connect(graph_path_for(out_dir))
    rows = conn.execute("SELECT type, src, dst FROM edges").fetchall()
    conn.close()
    return {(row[0], _short(row[1]), _short(row[2])) for row in rows}


def _nodes(out_dir: Path) -> set[tuple[str, str]]:
    conn = sqlite3.connect(graph_path_for(out_dir))
    rows = conn.execute("SELECT type, id FROM nodes").fetchall()
    conn.close()
    return {(row[0], _short(row[1])) for row in rows}


def _short(node_id: str) -> str:
    """절대경로 노드 id를 코퍼스 상대경로로 줄여 기대값을 읽을 수 있게 한다."""
    for relative in FILES:
        if node_id.endswith(relative):
            return relative
    return node_id


def _sim(left: str, right: str) -> tuple[str, str, str]:
    """대칭 엣지의 기대 튜플. 저장 순서(`src < dst`)를 눈으로 짐작하지 않고 정렬로 만든다 —
    한글 파일명의 유니코드 순서는 직관과 자주 어긋난다(`벡터설계` < `아키텍처`)."""
    low, high = sorted((left, right))
    return ("SEMANTICALLY_SIMILAR", low, high)


def _without_generated_at(wiki: Path) -> str:
    """`--force` 재실행 비교용 — 매 실행 달라지는 front-matter 시각 한 줄만 뺀다."""
    return "\n".join(
        line for line in wiki.read_text(encoding="utf-8").splitlines()
        if not line.startswith("generated_at:")
    )


def _related_block(wiki: Path) -> str:
    body = wiki.read_text(encoding="utf-8")
    return body.split(RELATED_MARKER_START)[1].split(RELATED_MARKER_END)[0].strip()


# --- 완료의 정의 1: 노드·엣지 튜플 집합이 기대와 정확히 일치 -----------------------


def test_graph_tuples_match_expected_set_exactly(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    assert _nodes(out_dir) == {
        *(("Document", relative) for relative in FILES),
        ("Tag", "tag:인사"),
        ("Tag", "tag:채용"),
        ("Tag", "tag:온보딩"),
        ("Tag", "tag:설계"),
        ("Tag", "tag:아키텍처"),
        ("Tag", "tag:벡터"),
        ("Tag", "tag:안내"),
        ("Tag", "tag:메모"),
        ("Entity", "entity:인사팀"),
        ("Entity", "entity:코어"),
        ("Entity", "entity:개인"),
    }
    assert _edges(out_dir) == {
        # TAGGED_WITH — 문서 6개의 태그 전부
        ("TAGGED_WITH", "인사/채용계획.docx", "tag:인사"),
        ("TAGGED_WITH", "인사/채용계획.docx", "tag:채용"),
        ("TAGGED_WITH", "인사/온보딩.md", "tag:인사"),
        ("TAGGED_WITH", "인사/온보딩.md", "tag:온보딩"),
        ("TAGGED_WITH", "개발/아키텍처.md", "tag:설계"),
        ("TAGGED_WITH", "개발/아키텍처.md", "tag:아키텍처"),
        ("TAGGED_WITH", "개발/벡터설계.md", "tag:설계"),
        ("TAGGED_WITH", "개발/벡터설계.md", "tag:벡터"),
        ("TAGGED_WITH", "개발/README.md", "tag:안내"),
        ("TAGGED_WITH", "기타/메모.txt", "tag:메모"),
        # CONTAINS_ENTITY — README는 entities 키가 없어 엣지도 없다 (§4.2)
        ("CONTAINS_ENTITY", "인사/채용계획.docx", "entity:인사팀"),
        ("CONTAINS_ENTITY", "인사/온보딩.md", "entity:인사팀"),
        ("CONTAINS_ENTITY", "개발/아키텍처.md", "entity:코어"),
        ("CONTAINS_ENTITY", "개발/벡터설계.md", "entity:코어"),
        ("CONTAINS_ENTITY", "기타/메모.txt", "entity:개인"),
        # SEMANTICALLY_SIMILAR — 0.81 쌍과 **정확히 임계치**인 쌍. 0.30 쌍은 제외된다
        _sim("인사/채용계획.docx", "인사/온보딩.md"),
        _sim("개발/아키텍처.md", "개발/벡터설계.md"),
        # REFERENCES — 양방향은 두 행, README의 자기참조는 없다 (§4.1)
        ("REFERENCES", "인사/채용계획.docx", "인사/온보딩.md"),
        ("REFERENCES", "인사/온보딩.md", "인사/채용계획.docx"),
        ("REFERENCES", "개발/아키텍처.md", "개발/README.md"),
    }


def test_entity_variants_merge_end_to_end(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 7 — `인사팀`과 `인사 팀`이 단일 Entity 노드가 된다."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    entities = {node_id for kind, node_id in _nodes(out_dir) if kind == "Entity"}
    assert "entity:인사팀" in entities
    assert len([e for e in entities if "인사" in e]) == 1


# --- 완료의 정의 2: 모든 위키에 「관련 문서」 섹션 ---------------------------------


def test_every_wiki_has_a_related_section(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    wikis = sorted(out_dir.rglob("*.md"))
    assert len(wikis) == len(FILES)
    for wiki in wikis:
        body = wiki.read_text(encoding="utf-8")
        assert RELATED_MARKER_START in body
        assert "## 관련 문서" in body


def test_isolated_document_renders_no_related_documents(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    assert _related_block(out_dir / "기타/메모.txt.md") == f"## 관련 문서\n{RELATED_EMPTY}"


def test_related_order_follows_the_hierarchical_rule(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """참조가 유사도보다 앞선다 (§4.5 ①→②)."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir, related_top_k=5))

    block = _related_block(out_dir / "개발/아키텍처.md.md")
    lines = [line for line in block.splitlines() if line.startswith("- ")]
    assert "README.md.md" in lines[0]
    assert "이 문서가 참조함" in lines[0]


def test_related_top_k_truncates(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir, related_top_k=1))

    block = _related_block(out_dir / "개발/아키텍처.md.md")
    assert len([line for line in block.splitlines() if line.startswith("- ")]) == 1


# --- 완료의 정의 4: 결정성 -------------------------------------------------------


def test_second_run_changes_nothing(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """두 번째 실행은 재요약도 재기록도 하지 않아 `generated_at`까지 바이트 동일하다."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))
    first_files = {p: p.read_bytes() for p in sorted(out_dir.rglob("*.md"))}
    first_edges = _edges(out_dir)

    result = run_scan(_config(corpus, out_dir))

    assert {p: p.read_bytes() for p in sorted(out_dir.rglob("*.md"))} == first_files
    assert _edges(out_dir) == first_edges
    assert result.graph is not None
    assert result.graph.related_updated_count == 0


def test_forced_rerun_produces_the_same_graph_and_bodies(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 4의 나머지 절반 — `--force` 2회 실행 비교.

    `--force`는 mtime과 무관하게 재요약하므로 `generated_at`이 달라진다. 스펙이 그 필드만
    제외하라고 한 이유다. 그 한 줄을 빼면 본문도 그래프도 바이트 동일해야 한다 — 같은
    입력에서 같은 요약·같은 벡터·같은 엣지가 나오기 때문이다.
    """
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir, force=True))
    first_nodes, first_edges = _nodes(out_dir), _edges(out_dir)
    first_bodies = {
        p.relative_to(out_dir): _without_generated_at(p) for p in sorted(out_dir.rglob("*.md"))
    }

    run_scan(_config(corpus, out_dir, force=True))

    assert _nodes(out_dir) == first_nodes
    assert _edges(out_dir) == first_edges
    assert {
        p.relative_to(out_dir): _without_generated_at(p) for p in sorted(out_dir.rglob("*.md"))
    } == first_bodies


def test_forced_rerun_actually_resummarizes(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """위 테스트가 «아무것도 안 해서» 통과하지 않음을 보인다 — `--force`는 실제로 재요약한다."""
    calls: list[str] = []
    stub = _stub()

    def counting(url: str, **kwargs: Any) -> Any:
        if not url.endswith("/api/tags") and not url.endswith("/api/embeddings"):
            calls.append(url)
        return stub(url, **kwargs)

    monkeypatch.setattr(gateway_module, "request_json", counting)
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir, force=True))
    first = len(calls)
    run_scan(_config(corpus, out_dir, force=True))

    assert first == len(FILES)
    assert len(calls) == first * 2  # 두 번째 실행도 전부 재요약했다


# --- 완료의 정의 5: 벡터 없음 → 부분 그래프 ---------------------------------------


def test_missing_vectors_yield_a_partial_graph(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """유사도 엣지만 빠지고 나머지 3종은 정상, 종료 코드 0과 생략 사유 한 줄."""
    def request_json(url: str, **kwargs: Any) -> Any:
        if url.endswith("/api/tags"):
            from corpbrain.core.llm.ollama_client import OllamaNotAvailableError

            raise OllamaNotAvailableError("데몬이 응답하지 않습니다")
        return _stub(with_vectors=False)(url, **kwargs)

    monkeypatch.setattr(gateway_module, "request_json", request_json)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(
        "corpbrain.core.pipeline.preflight", lambda api_key, **_: None
    )
    monkeypatch.setattr(
        "corpbrain.core.pipeline._require_cloud_consent", lambda path=None: None
    )
    monkeypatch.setattr(
        "corpbrain.core.pipeline._build_summarizer", _local_summarizer_factory()
    )
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir, engine="cloud"))

    assert result.graph is not None
    assert result.graph.similarity_skipped is GraphSkipReason.VECTORS_UNAVAILABLE
    kinds = {kind for kind, _src, _dst in _edges(out_dir)}
    assert "SEMANTICALLY_SIMILAR" not in kinds
    assert kinds == {"TAGGED_WITH", "CONTAINS_ENTITY", "REFERENCES"}
    assert any("유사도 엣지 생략" in line for line in build_summary_lines(result))


def _local_summarizer_factory():
    """cloud 경로에서도 스텁 응답을 그대로 쓰도록 로컬 요약기를 돌려준다."""
    from corpbrain.core.llm.summarize import OllamaSummarizer

    def factory(config: ScanConfig, api_key: str | None) -> Any:
        return OllamaSummarizer(config.model, config.ollama_url)

    return factory


# --- 완료의 정의 6: 엔티티 없는 기존 위키 ----------------------------------------


def test_legacy_wiki_is_restored_without_resummarizing(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.5 산출물이 있는 out_dir — 재요약 0회, 안내 문구, 종료 코드 0 (§5)."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    # 그래프 DB만 지운다 = 재료가 사라진 v0.5 상태와 같다.
    graph_path_for(out_dir).unlink()

    summarize_calls: list[str] = []
    stub = _stub()

    def counting(url: str, **kwargs: Any) -> Any:
        if not url.endswith("/api/tags") and not url.endswith("/api/embeddings"):
            summarize_calls.append(url)
        return stub(url, **kwargs)

    monkeypatch.setattr(gateway_module, "request_json", counting)

    result = run_scan(_config(corpus, out_dir))

    assert summarize_calls == []  # 재요약 0회
    assert result.graph is not None
    assert result.graph.facts_missing_count == len(FILES)
    kinds = {kind for kind, _src, _dst in _edges(out_dir)}
    assert "CONTAINS_ENTITY" not in kinds  # 엔티티는 위키에 남지 않는다
    assert {"TAGGED_WITH", "SEMANTICALLY_SIMILAR", "REFERENCES"} <= kinds
    assert any("--force" in line for line in build_summary_lines(result))


# --- 리뷰 지적 ⓐ·ⓑ — 파괴적 정리의 전제와 중복 원문 -------------------------------


def test_unreadable_wiki_suspends_orphan_pruning(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """위키 하나를 읽지 못하면 재료 정리를 통째로 건너뛴다.

    파일이 잠긴 일시적 조건이 `doc_facts` 삭제(엔티티 영구 소실)로 번지면 안 된다. 목록이
    불완전한 채로 "위키 없는 문서"를 판정할 수 없다.
    """
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    from corpbrain.core import pipeline as pipeline_module
    from corpbrain.core.graphstore import SqliteGraphStore

    target = out_dir / "기타/메모.txt.md"
    real = pipeline_module.read_source_path

    def _unreadable(path: Path) -> str | None:
        return None if path == target else real(path)

    monkeypatch.setattr(pipeline_module, "read_source_path", _unreadable)

    run_scan(_config(corpus, out_dir))

    # 읽히지 않은 문서의 재료가 살아 있다 — 정리가 유예됐다.
    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        surviving = {facts.doc_id for facts in store.iter_facts()}
    assert any(doc_id.endswith("기타/메모.txt") for doc_id in surviving)


def test_orphan_facts_are_pruned_when_the_inventory_is_complete(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """목록이 완전하면 위키가 사라진 문서의 재료는 지운다 (유령 노드 방지)."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    (out_dir / "기타/메모.txt.md").unlink()
    (corpus / "기타/메모.txt").unlink()

    run_scan(_config(corpus, out_dir))

    from corpbrain.core.graphstore import SqliteGraphStore

    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        surviving = {facts.doc_id for facts in store.iter_facts()}
    assert not any(doc_id.endswith("기타/메모.txt") for doc_id in surviving)


def test_duplicate_source_path_is_reported_not_swallowed(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """서로 다른 스캔 루트가 같은 `--out`을 공유하면 생길 수 있다 — 조용히 두지 않는다."""
    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    original = out_dir / "기타/메모.txt.md"
    twin = out_dir / "기타/메모-사본.txt.md"
    twin.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

    result = run_scan(_config(corpus, out_dir))

    assert result.graph is not None
    assert len(result.graph.duplicate_sources) == 1
    assert any("같은 원문을 가리키는 위키" in line for line in build_summary_lines(result))


# --- 리뷰 지적 ① — CLI 출력이 DB 실측과 일치하는가 (완료의 정의 3) ------------------


def test_cli_stats_numbers_match_the_database(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """완료의 정의 3: `graph --stats` 출력의 개수가 **DB 실측과 일치**한다.

    빌더 단위테스트는 손으로 만든 `GraphStats`를, 저장소 단위테스트는 `stats()` 자체를
    검증한다. 그 둘의 **결합**은 여기서만 단언된다 — 빌더가 태그 수를 엔티티 자리에 넣어도
    양쪽 단위테스트는 통과한다.
    """
    from corpbrain import cli
    from corpbrain.core.graphstore import SqliteGraphStore

    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        stats = store.stats()

    assert cli.main(["graph", "--out", str(out_dir), "--stats"]) == 0
    out = capsys.readouterr().out

    assert f"노드 {stats.nodes}개" in out
    assert f"문서 {stats.documents} · 엔티티 {stats.entities} · 태그 {stats.tags}" in out
    assert f"엣지 {stats.edges}개" in out
    for kind, count in stats.edges_by_type.items():
        assert f"{kind} {count}" in out


def test_cli_neighbors_matches_the_graph_after_a_real_scan(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """손으로 seed한 저장소가 아니라 실제 scan 결과를 조회한다."""
    from corpbrain import cli

    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    assert cli.main(["graph", "--out", str(out_dir), "--neighbors", "개발/아키텍처.md.md"]) == 0
    out = capsys.readouterr().out

    # 아키텍처 → README 단방향 참조와 벡터설계와의 유사도(정확히 임계치)가 함께 보인다.
    assert "REFERENCES →" in out
    assert "SEMANTICALLY_SIMILAR" in out
    assert "README" in out
    # 자기 자신은 결코 이웃으로 나오지 않는다 — 머리줄 뒤로는 자기 `doc_id`가 없다.
    # (문자열 수를 세면 안 된다: "아키텍처"는 제목·경로·태그로도 등장한다.)
    focus = str(corpus / "개발/아키텍처.md")
    header, *neighbors = out.splitlines()
    assert focus in header
    assert all(focus not in line for line in neighbors)


def test_cli_neighbors_rejects_an_absolute_source_path_outside_out_dir(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """리뷰 지적 ③ — `out_dir` 밖의 원문을 위키로 오인해 front-matter를 읽지 않는다.

    원문이 front-matter를 가진 마크다운이면(다른 도구의 위키, 스캔 대상에 섞인 CorpBrain
    위키) 그 안의 `source_path`를 읽어 **엉뚱한 문서**를 보여줄 수 있었다.
    """
    from corpbrain import cli

    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    decoy = tmp_path / "decoy.md"
    decoy.write_text('---\nsource_path: "/엉뚱한/원본.txt"\n---\n\n# 미끼\n', encoding="utf-8")

    code = cli.main(["graph", "--out", str(out_dir), "--neighbors", str(decoy)])

    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "그래프에 없는 문서" in capsys.readouterr().err


def test_cli_central_matches_the_graph_after_a_real_scan(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """`--central`도 손으로 seed한 저장소가 아니라 실제 scan 결과를 조회한다."""
    from corpbrain import cli
    from corpbrain.core.graphstore import SqliteGraphStore

    monkeypatch.setattr(gateway_module, "request_json", _stub())
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        ranking = store.degree_ranking()

    assert cli.main(["graph", "--out", str(out_dir), "--central"]) == 0
    out = capsys.readouterr().out.splitlines()

    assert len(out) == len(ranking) == len(FILES)
    # 출력 순서가 저장소의 순서(차수 내림차순, 동점은 id 사전순)와 같다.
    for line, (doc_id, degree) in zip(out, ranking, strict=True):
        assert doc_id in line
        assert line.split()[0] == str(degree)
    # 고립 문서는 차수가 가장 낮아 맨 끝이다.
    assert "메모.txt" in out[-1]
