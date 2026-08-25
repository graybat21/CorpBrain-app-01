"""v0.7 하이브리드 검색 — 코어 API 통합 (스펙 §3 · §4.5 · §4.7 · §5).

코퍼스는 `tmp_path`에 **인라인 생성**하고 `gateway.request_json`을 스텁해 쿼리 임베딩을
고정한다(v0.6 관용구 계승). 벡터·그래프는 파일 내용이 아니라 이 파일이 직접 심으므로
"이 문서 쌍이 왜 붙어 있는가"가 코드에 그대로 드러난다.

`graph_decay`는 `DEFAULT_GRAPH_DECAY`를 참조하지 않고 명시적으로 넘긴다 (스펙 T11).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.errors import PreconditionError
from corpbrain.core.graphstore import SqliteGraphStore, graph_path_for
from corpbrain.core.models import EdgeType, GraphEdge, GraphNode, NodeType, SearchResult
from corpbrain.core.search import search_index
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

ALPHA = 0.7
NO_SIMILARITY = frozenset(
    {EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY, EdgeType.REFERENCES}
)

# 쿼리 벡터는 `[1, 0]` 이다 — 코사인은 각 문서 벡터의 x 성분 비율로 결정된다.
QUERY_VECTOR = [1.0, 0.0]

#: 인사 3문서 + 무관 2문서. 코사인만으로는 `채용계획`이 top-2 밖이지만 `온보딩`과 태그·
#: 엔티티·참조를 공유해 확산으로 끌려 올라온다.
ONBOARDING = "/corpus/인사/온보딩.md"
HIRING = "/corpus/인사/채용계획.md"
WELFARE = "/corpus/인사/복지제도.md"
MEMO = "/corpus/기타/메모.md"
ARCH = "/corpus/개발/아키텍처.md"
#: 온보딩이 **참조로만** 가리키는 문서 — `--expand-edges`에서 `REFERENCES`를 빼면 사라진다.
NOTICE = "/corpus/기타/공지.md"
#: 온보딩과 **유사도 엣지로만** 이어진 문서 — 기본 확산에는 나타나지 않는다.
LEGAL = "/corpus/법무/계약검토메모.md"

VECTORS: dict[str, list[float]] = {
    ONBOARDING: [0.90, 0.4359],  # 코사인 ≈ 0.900
    MEMO: [0.60, 0.8000],  # ≈ 0.600
    ARCH: [0.50, 0.8660],  # ≈ 0.500
    HIRING: [0.20, 0.9798],  # ≈ 0.200
    # 복지제도는 벡터가 없다 — 개별 문서 임베딩 실패 경로(§5)를 겸한다.
}

TITLES = {
    ONBOARDING: "온보딩",
    HIRING: "채용계획",
    WELFARE: "복지제도",
    MEMO: "메모",
    ARCH: "아키텍처",
    NOTICE: "공지",
    LEGAL: "계약검토메모",
}


def _seed_index(out_dir: Path) -> None:
    store = SqliteVectorStore(index_path_for(out_dir))
    store.set_model_name("qwen3-embedding:4b")
    for doc_id, vector in VECTORS.items():
        store.upsert(doc_id, vector, {"title": TITLES[doc_id], "source_path": doc_id})
    store.close()


def _seed_graph(out_dir: Path) -> None:
    nodes = [
        *(
            GraphNode(id=doc_id, type=NodeType.DOCUMENT, label=title)
            for doc_id, title in sorted(TITLES.items())
        ),
        GraphNode(id="tag:인사", type=NodeType.TAG, label="인사"),
        GraphNode(id="tag:개발", type=NodeType.TAG, label="개발"),
        GraphNode(id="entity:인사팀", type=NodeType.ENTITY, label="인사팀"),
    ]
    edges = [
        GraphEdge(src=ONBOARDING, dst="tag:인사", type=EdgeType.TAGGED_WITH),
        GraphEdge(src=HIRING, dst="tag:인사", type=EdgeType.TAGGED_WITH),
        GraphEdge(src=WELFARE, dst="tag:인사", type=EdgeType.TAGGED_WITH),
        GraphEdge(src=ARCH, dst="tag:개발", type=EdgeType.TAGGED_WITH),
        GraphEdge(src=ONBOARDING, dst="entity:인사팀", type=EdgeType.CONTAINS_ENTITY),
        GraphEdge(src=HIRING, dst="entity:인사팀", type=EdgeType.CONTAINS_ENTITY),
        GraphEdge(src=HIRING, dst=ONBOARDING, type=EdgeType.REFERENCES),
        GraphEdge(src=ONBOARDING, dst=HIRING, type=EdgeType.REFERENCES),
        GraphEdge(src=ONBOARDING, dst=NOTICE, type=EdgeType.REFERENCES),
        GraphEdge(
            src=ARCH, dst=MEMO, type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.81
        ),
        GraphEdge(
            src=LEGAL, dst=ONBOARDING, type=EdgeType.SEMANTICALLY_SIMILAR, weight=0.77
        ),
    ]
    with SqliteGraphStore(graph_path_for(out_dir)) as store:
        store.replace_graph(nodes, edges)


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out_dir = tmp_path / "wiki"
    _seed_index(out_dir)
    _seed_graph(out_dir)

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        assert url.endswith("/api/embeddings")
        return {"embedding": QUERY_VECTOR}

    monkeypatch.setattr(gateway, "request_json", _request_json)
    return out_dir


def _ids(results: list[SearchResult]) -> list[str]:
    return [result.doc_id for result in results]


# --- §3 항목1: 코사인 top-k 밖 문서가 하이브리드에서 기대 순위에 나타난다 -----------


def test_graph_expansion_pulls_a_document_past_the_cosine_cut(corpus: Path) -> None:
    cosine_only = search_index(corpus, "인사", top_k=2, graph=False)
    hybrid = search_index(corpus, "인사", top_k=2, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)

    assert _ids(cosine_only) == [ONBOARDING, MEMO]
    # 온보딩(0.900) × 0.7 = 0.630 > 메모의 0.600 — 코사인 4위이던 채용계획이 2위가 된다.
    assert _ids(hybrid) == [ONBOARDING, HIRING]
    assert hybrid[1].score == pytest.approx(0.900 * ALPHA, abs=1e-3)


def test_expansion_evidence_names_the_seed_and_the_shared_signals(corpus: Path) -> None:
    hybrid = search_index(corpus, "인사", top_k=2, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)
    expansion = hybrid[1].expansion

    assert hybrid[0].expansion is None  # 시드는 근거 줄을 갖지 않는다 (§4.5)
    assert expansion is not None
    assert expansion.seed_doc_id == ONBOARDING
    assert expansion.seed_title == "온보딩"
    assert expansion.shared_tags == ["인사"]
    assert expansion.shared_entities == ["인사팀"]
    assert expansion.reference.value == "mutual"
    assert expansion.cosine == pytest.approx(0.200, abs=1e-3)


def test_expansion_document_without_a_vector_uses_the_graph_label(corpus: Path) -> None:
    """§5 — 개별 문서 임베딩 실패. 점수는 `시드 × α`가 되고 표시 라벨은 그래프가 준다."""
    hybrid = search_index(corpus, "인사", top_k=4, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)
    welfare = next(result for result in hybrid if result.doc_id == WELFARE)

    assert welfare.expansion is not None
    assert welfare.expansion.cosine is None
    assert welfare.metadata == {"title": "복지제도"}
    assert welfare.score == pytest.approx(0.900 * ALPHA, abs=1e-3)


def test_result_count_never_exceeds_top_k(corpus: Path) -> None:
    """§3 항목3 — 확산 후보가 넘쳐도 반환 길이는 `top_k` 이하다."""
    assert len(search_index(corpus, "인사", top_k=1, graph_decay=ALPHA)) == 1
    assert len(search_index(corpus, "인사", top_k=3, graph_decay=ALPHA)) == 3


def test_expansion_never_outranks_its_seed(corpus: Path) -> None:
    """§3 항목4 — `expansion is None or score <= seed_score`."""
    for top_k in (1, 2, 3, 5):
        for result in search_index(corpus, "인사", top_k=top_k, graph_decay=0.95):
            assert result.expansion is None or result.score <= result.expansion.seed_score


def test_dropping_references_removes_reference_only_documents(corpus: Path) -> None:
    """§3 항목6 — `--expand-edges`에서 `REFERENCES`를 빼면 참조로만 이어진 문서가 사라진다."""
    with_refs = search_index(
        corpus, "인사", top_k=4, graph_decay=ALPHA, expand_edges=NO_SIMILARITY
    )
    without_refs = search_index(
        corpus,
        "인사",
        top_k=4,
        graph_decay=ALPHA,
        expand_edges=frozenset({EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY}),
    )

    assert NOTICE in _ids(with_refs)
    assert NOTICE not in _ids(without_refs)
    # 태그로 이어진 복지제도는 양쪽 모두에 남는다 — 사라지는 것은 참조로만 이어진 쪽이다.
    assert WELFARE in _ids(with_refs)
    assert WELFARE in _ids(without_refs)


def test_similarity_edges_expand_only_when_asked(corpus: Path) -> None:
    """`SEMANTICALLY_SIMILAR`는 기본에서 빠져 있고 `--expand-edges`로만 켜진다 (§4.2).

    임베딩 코사인 그 자체인 엣지를 기본에 넣으면 같은 신호를 두 번 세게 되고, #42가 실측한
    임베딩 모델 종속성이 순위에서 증폭된다.
    """
    default = search_index(corpus, "인사", top_k=2, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)
    similarity_only = search_index(
        corpus,
        "인사",
        top_k=2,
        graph_decay=ALPHA,
        expand_edges=frozenset({EdgeType.SEMANTICALLY_SIMILAR}),
    )

    assert LEGAL not in _ids(default)
    assert _ids(similarity_only) == [ONBOARDING, LEGAL]


# --- §3 항목7·9: 그래프 DB 부재와 손상 -----------------------------------------


def test_missing_graph_db_falls_back_to_cosine_only(corpus: Path) -> None:
    """§5 — 부재는 정상 응답이다. 코사인 단독 결과를 그대로 돌려준다."""
    graph_path_for(corpus).unlink()

    results = search_index(corpus, "인사", top_k=2, graph_decay=ALPHA)

    assert _ids(results) == [ONBOARDING, MEMO]
    assert [result.expansion for result in results] == [None, None]


def test_no_graph_matches_the_deleted_graph_db_result(corpus: Path) -> None:
    """§3 항목2 — `--no-graph` 경로와 그래프 DB를 지운 경로가 같은 값을 낸다."""
    without_flag = search_index(corpus, "인사", top_k=3, graph=False)
    graph_path_for(corpus).unlink()
    deleted = search_index(corpus, "인사", top_k=3)

    assert without_flag == deleted


def test_corrupt_schema_version_is_a_precondition_failure(corpus: Path) -> None:
    """§3 항목9 — 자동 복구하지 않고 멈춘 뒤 재생성을 안내한다 (§5)."""
    import sqlite3

    conn = sqlite3.connect(graph_path_for(corpus))
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(PreconditionError, match="스키마 버전"):
        search_index(corpus, "인사", top_k=2, graph_decay=ALPHA)


def test_search_does_not_write_to_the_graph_db(corpus: Path) -> None:
    """조회 경로는 파일에 쓰지 않는다 — `read_only=True`로 연다 (§4.7, v0.6.1 계승)."""
    path = graph_path_for(corpus)
    before = path.stat().st_mtime_ns, path.read_bytes()

    search_index(corpus, "인사", top_k=2, graph_decay=ALPHA)

    assert (path.stat().st_mtime_ns, path.read_bytes()) == before


# --- §3 항목8: 입력 검증이 코어 API에서 난다 -------------------------------------


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.5, 2.0])
def test_graph_decay_outside_the_open_interval_raises(corpus: Path, alpha: float) -> None:
    with pytest.raises(PreconditionError, match="graph-decay"):
        search_index(corpus, "인사", top_k=2, graph_decay=alpha)


def test_empty_expand_edges_raises(corpus: Path) -> None:
    """빈 목록을 «확산 안 함»으로 받아 주지 않는다 — 끄는 길은 `--no-graph` 하나다 (§4.4)."""
    with pytest.raises(PreconditionError, match="expand-edges"):
        search_index(corpus, "인사", top_k=2, graph_decay=ALPHA, expand_edges=frozenset())


# --- §3 항목10: 결정성 ----------------------------------------------------------


def test_two_runs_return_identical_results(corpus: Path) -> None:
    first = search_index(corpus, "인사", top_k=3, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)
    second = search_index(corpus, "인사", top_k=3, graph_decay=ALPHA, expand_edges=NO_SIMILARITY)

    assert first == second
