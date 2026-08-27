"""통합 테스트 — 협조적 취소 (v0.9 스펙 §3 항목6·7 · §4.7).

`gateway.request_json`을 스텁한 채 코어 `run_scan()`을 직접 호출한다. **스레드도 `sleep`도
쓰지 않는다** — 취소 술어가 순수 함수라 「N번째 문서 뒤에 `True`」로 정확한 지점이 재현된다.
타이밍 의존 테스트는 CI 부하에 따라 간헐 실패하고 깨질 때마다 대기 시간이 늘어난다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.pipeline import run_scan
from corpbrain.core.report import build_summary_lines
from corpbrain.core.vectorstore import SqliteVectorStore, index_path_for

TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}

DOC_COUNT = 5


@pytest.fixture
def ok_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(
        url: str, *, method: str = "GET", payload: Any = None, **_: Any
    ) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            seed = float(sum(ord(ch) for ch in payload["prompt"]) % 97)
            return {"embedding": [seed, 1.0]}
        return {
            "response": json.dumps(
                {
                    "title": "제목",
                    "one_line_summary": "한 줄",
                    "key_points": ["a", "b", "c"],
                    "summary": "요약",
                    "tags": ["t"],
                },
                ensure_ascii=False,
            )
        }

    monkeypatch.setattr(gateway, "request_json", _request_json)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    for index in range(DOC_COUNT):
        (root / f"{index:02d}.md").write_text(f"문서 {index} 본문", encoding="utf-8")
    return root


def _config(corpus: Path, tmp_path: Path) -> ScanConfig:
    # `force_gates=True` — 이 테스트가 보는 것은 취소이지 GPU 게이트가 아니다. CI·개발
    # 머신에 GPU가 없으면 게이트가 먼저 걸려 취소 경로에 닿지도 못한다.
    return ScanConfig(folder=corpus, out_dir=tmp_path / "wiki", force_gates=True)


def _cancel_after(count: int) -> Any:
    """N개 문서를 처리한 뒤 `True`를 돌려주는 **순수 술어**를 만든다.

    코어는 파일 루프 **경계**에서 이것을 부르므로, 호출 횟수가 곧 「지금까지 시작하려던
    문서의 순번」이다.
    """
    state = {"calls": 0}

    def should_cancel() -> bool:
        state["calls"] += 1
        return state["calls"] > count

    return should_cancel


def test_cancel_stops_at_the_file_loop_boundary(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """DoD 7 — 진행 중이던 문서는 마치고, 그다음 문서는 시작하지 않는다."""
    result = run_scan(_config(corpus, tmp_path), should_cancel=_cancel_after(2))

    assert result.cancelled is True
    assert len(result.generated) == 2
    # 3번째 문서는 **시작조차 하지 않았다** — 스킵으로도 담기지 않는다.
    assert len(result.skipped) == 0


def test_cancelled_scan_returns_a_partial_result_with_files_on_disk(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """DoD 6 — 부분 `ScanResult`가 정상 반환되고 그때까지 쓰인 `.md`가 남는다."""
    result = run_scan(_config(corpus, tmp_path), should_cancel=_cancel_after(2))

    written = sorted(path.name for path in (tmp_path / "wiki").glob("*.md"))
    assert written == ["00.md.md", "01.md.md"]
    assert [wiki.output_path.name for wiki in result.generated] == written


def test_cancelled_scan_preserves_vectors_of_unvisited_documents(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """DoD 6 — 방문하지 않은 문서가 고아로 오판돼 지워지지 않는다 (§4.7).

    고아 벡터 정리는 파일 루프가 **방문한 문서만** 담은 집합으로 판정하므로, 취소로 루프가
    끊기면 아직 방문하지 않은 문서 전부가 그 판정에 걸린다. v0.6 §5가 「목록이 불완전한
    채로 «없는 문서»를 판정하지 않는다」로 세운 잣대와 같다.
    """
    config = _config(corpus, tmp_path)
    run_scan(config)  # 1회차: 전 문서 인덱싱
    store = SqliteVectorStore(index_path_for(config.out_dir))
    try:
        before = set(store.list_ids())
    finally:
        store.close()
    assert len(before) == DOC_COUNT

    run_scan(config, should_cancel=_cancel_after(2))

    store = SqliteVectorStore(index_path_for(config.out_dir))
    try:
        after = set(store.list_ids())
    finally:
        store.close()
    assert after == before


def test_cancelled_scan_skips_the_graph_stage(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """§4.7 — 취소되면 패스2·3을 건너뛰고 즉시 반환한다."""
    result = run_scan(_config(corpus, tmp_path), should_cancel=_cancel_after(2))

    assert result.graph is None


def test_cancelled_scan_reports_the_unreflected_graph(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """§4.7 — 그래프를 건너뛴 창(window)을 조용히 두지 않는다."""
    result = run_scan(_config(corpus, tmp_path), should_cancel=_cancel_after(2))

    lines = build_summary_lines(result)
    assert "  - 그래프 미반영 — 다시 스캔하면 반영됩니다." in lines


def test_next_scan_recovers_the_graph_without_resummarising(
    ok_gateway: None, corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4.7 — `doc_facts`가 패스1에서 문서마다 저장되므로 다음 `scan`이 자동 회복한다."""
    config = _config(corpus, tmp_path)
    run_scan(config, should_cancel=_cancel_after(2))

    result = run_scan(config)

    assert result.cancelled is False
    assert result.graph is not None
    assert result.graph.stats is not None
    # 전 문서가 그래프에 참여한다 — 취소된 실행이 남긴 재료 + 이번에 처리한 나머지.
    assert result.graph.stats.documents == DOC_COUNT


def test_cancel_predicate_exceptions_are_not_swallowed(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """§4.7 — 취소 술어는 **제어 입력**이라 예외를 삼키지 않는다.

    `on_event`(표시 장치)와 의도적으로 다르다 — sink는 죽어도 스캔이 계속되는 것이 옳지만,
    취소 술어를 조용히 무시하면 사용자의 중단 요청이 사라진다.
    """

    def boom() -> bool:
        raise RuntimeError("취소 판정 실패")

    with pytest.raises(RuntimeError, match="취소 판정 실패"):
        run_scan(_config(corpus, tmp_path), should_cancel=boom)


def test_event_sink_exceptions_are_still_swallowed(
    ok_gateway: None, corpus: Path, tmp_path: Path
) -> None:
    """대비 케이스 — 두 콜백의 계약이 갈린다는 것 자체를 고정한다."""

    def boom(event: Any) -> None:
        raise RuntimeError("sink 실패")

    result = run_scan(_config(corpus, tmp_path), on_event=boom)

    assert len(result.generated) == DOC_COUNT
