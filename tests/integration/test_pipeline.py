"""통합 테스트 — 완료의 정의(스펙 §3) 1~5를 코어 API 직접 호출로 검증 (FR-018).

외부호출 단일 관문(FR-003)만 스텁해 Ollama HTTP를 대체하며, CLI를 경유하지 않고
`corpbrain.core.run_scan`을 직접 부른다 (스펙 §4.5 코어 라이브러리 이음새).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from corpbrain import cli
from corpbrain.core import _progress, gateway, run_scan
from corpbrain.core.config import ScanConfig
from corpbrain.core.render import FRONT_MATTER_KEYS, SECTION_HEADERS

FIXTURE_CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "sample_corpus"

SUMMARY_JSON = {
    "title": "통합 테스트 제목",
    "one_line_summary": "한 줄 요약입니다.",
    "key_points": ["포인트 1", "포인트 2", "포인트 3"],
    "summary": "문단 요약입니다.",
    "tags": ["태그1", "태그2"],
}

#: 완료의 정의 픽스처에서 위키가 생성돼야 하는 지원 파일 (12,000자 초과 포함, 스펙 §3-1).
EXPECTED_WIKIS = {
    "normal.txt.md",
    "guide.md.md",
    "oversized.txt.md",
    "sub/nested.txt.md",
    "sub/report.docx.md",
}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """읽기 전용 커밋 픽스처를 tmp로 복사해 mtime·출력물을 격리한다."""
    dest = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, dest)
    return dest


def _ok_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": []}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)


def _config(corpus: Path, out_dir: Path, **overrides: Any) -> ScanConfig:
    return ScanConfig(folder=corpus, out_dir=out_dir, **overrides)


def test_output_tree_mirrors_input_structure(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 1: 지원 파일마다 하위구조를 미러링한 위키가 생성된다."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    produced = {p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.md")}
    assert produced == EXPECTED_WIKIS


def test_each_wiki_has_front_matter_and_sections(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 2: 각 위키가 front-matter 4키 + 6섹션을 포함한다."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    for relative in EXPECTED_WIKIS:
        markdown = (out_dir / relative).read_text(encoding="utf-8")
        for key in FRONT_MATTER_KEYS:
            assert f"{key}:" in markdown, f"{relative}에 {key} 없음"
        for header in SECTION_HEADERS:
            assert header in markdown, f"{relative}에 {header} 없음"
        assert markdown.startswith("---\n")


def test_skip_report_lists_unsupported_and_empty(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 3: 미지원·빈 파일은 산출물이 아니라 스킵 리포트에 사유와 함께 나타난다."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    skipped = {skip.path.name: skip.reason.value for skip in result.skipped}
    assert skipped["empty.txt"] == "empty_document"
    assert skipped["photo.jpg"] == "unsupported_extension"
    assert not (out_dir / "empty.txt.md").exists()
    assert not (out_dir / "photo.jpg.md").exists()


def test_oversized_document_is_processed_not_skipped(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의: 12,000자 초과 문서는 스킵이 아니라 절단 후 정상 처리된다."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    generated = {wiki.source_path.name for wiki in result.generated}
    assert "oversized.txt" in generated


def test_limit_exceeded_stops_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 4: 51개 초과 시 처리 중단+알림."""
    _ok_gateway(monkeypatch)
    root = tmp_path / "many"
    root.mkdir()
    for index in range(51):
        (root / f"doc{index:03d}.txt").write_text("본문", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(root, out_dir, max_files=50))

    assert result.limit_exceeded is True
    assert result.discovered_count == 51
    assert result.generated == []


def test_partial_failure_exits_zero_via_cli(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 5: 개별 파일 부분 실패는 종료 코드 0."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    code = cli.main(["scan", str(corpus), "--out", str(out_dir)])

    assert code == cli.EXIT_OK


def test_precondition_failure_exits_nonzero_via_cli(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 5: Ollama 미탐지 등 선행 조건 실패는 비-0."""

    def _refused(url: str, **_: Any) -> Any:
        raise gateway.GatewayError("연결 거부", url=url)

    monkeypatch.setattr(gateway, "request_json", _refused)

    code = cli.main(["scan", str(corpus), "--out", str(tmp_path / "wiki")])

    assert code != 0
    assert code == cli.EXIT_PRECONDITION_FAILED


def test_broken_json_skips_only_that_file(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """엣지 케이스(§5): 한 파일의 JSON 파싱 실패는 그 파일만 스킵, 나머지 계속."""

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": []}
        if payload is not None and "마크다운 제목" in payload["prompt"]:
            return {"response": "이건 JSON이 아님"}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    skipped = {skip.path.name: skip.reason.value for skip in result.skipped}
    assert skipped["guide.md"] == "summary_failed"
    generated = {wiki.source_path.name for wiki in result.generated}
    assert "normal.txt" in generated
    assert not (out_dir / "guide.md.md").exists()


def test_progress_events_emitted_in_order(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스펙 완료의 정의 1: on_event로 이벤트가 순서대로 방출된다 (코어 API 직접 호출)."""
    _ok_gateway(monkeypatch)
    events: list[Any] = []

    run_scan(_config(corpus, tmp_path / "wiki"), on_event=events.append)

    kinds = [event.kind for event in events]
    assert kinds[0] == _progress.EventKind.RUN_STARTED
    assert kinds[-1] == _progress.EventKind.RUN_FINISHED
    assert kinds.count(_progress.EventKind.MODEL_LOADING) == 1
    assert kinds.count(_progress.EventKind.MODEL_READY) == 1
    assert kinds.index(_progress.EventKind.MODEL_LOADING) < kinds.index(
        _progress.EventKind.MODEL_READY
    )

    starts = [e for e in events if e.kind == _progress.EventKind.FILE_STARTED]
    assert [e.index for e in starts] == list(range(1, len(starts) + 1))
    assert {e.total for e in starts} == {len(starts)}

    outcomes = [
        e
        for e in events
        if e.kind in (_progress.EventKind.FILE_GENERATED, _progress.EventKind.FILE_SKIPPED)
    ]
    assert len(outcomes) == len(starts) == starts[0].total


def test_on_event_none_keeps_default_behavior(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스펙 완료의 정의 6: on_event 없이도 기존 동작이 그대로다 (하위 호환)."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    produced = {p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.md")}
    assert produced == EXPECTED_WIKIS


def test_sink_exception_is_isolated(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스펙 완료의 정의 8: sink 예외는 격리되어 스캔이 정상 완료된다."""
    _ok_gateway(monkeypatch)
    out_dir = tmp_path / "wiki"

    def _boom(event: Any) -> None:
        raise RuntimeError("sink broke")

    result = run_scan(_config(corpus, out_dir), on_event=_boom)

    produced = {p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.md")}
    assert produced == EXPECTED_WIKIS
    assert result.generated


def test_cli_emits_live_progress_to_stderr_only(
    corpus: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """스펙 완료의 정의 5: 라이브 라인은 stderr로만 나가고 stdout은 빈다."""
    _ok_gateway(monkeypatch)

    code = cli.main(["scan", str(corpus), "--out", str(tmp_path / "wiki")])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert captured.out == ""
    assert "summarize" in captured.err or "extract" in captured.err
    assert "loading=" in captured.err
