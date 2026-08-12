"""파이프라인 오케스트레이션 테스트 (FR-015 / 스펙 §4.5, §5).

Ollama HTTP는 단일 관문(`gateway.request_json`)을 스텁해 대체하며, 코어 API를
CLI 없이 직접 호출한다 (스펙 §4.5 검증).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway
from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import SkipReason
from corpbrain.core.pipeline import run_scan

SUMMARY_JSON = {
    "title": "문서 제목",
    "one_line_summary": "한 줄 요약입니다.",
    "key_points": ["포인트 1", "포인트 2", "포인트 3"],
    "summary": "문단 요약입니다.",
    "tags": ["태그1", "태그2"],
}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "inbox"
    (root / "sub").mkdir(parents=True)
    (root / "normal.txt").write_text("정상 문서 본문입니다.", encoding="utf-8")
    (root / "sub" / "nested.md").write_text("# 하위 문서\n본문", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "photo.jpg").write_bytes(b"not an image")
    return root


@pytest.fixture
def stub_ollama(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """관문을 스텁해 헬스체크와 요약 응답을 돌려주고, 접속 대상 URL을 기록한다."""
    urls: list[str] = []

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        urls.append(url)
        if url.endswith("/api/tags"):
            return {"models": []}
        if url.endswith("/api/generate"):
            return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}
        raise AssertionError(f"예상치 못한 호출 대상: {url}")

    monkeypatch.setattr(gateway, "request_json", _request_json)
    return urls


def _config(root: Path, out_dir: Path, **overrides: Any) -> ScanConfig:
    return ScanConfig(folder=root, out_dir=out_dir, **overrides)


def test_mixed_folder_is_partially_processed(
    corpus: Path, tmp_path: Path, stub_ollama: list[str]
) -> None:
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    generated = {wiki.output_path.relative_to(out_dir).as_posix() for wiki in result.generated}
    assert generated == {"normal.txt.md", "sub/nested.md.md"}
    assert (out_dir / "normal.txt.md").exists()
    assert (out_dir / "sub" / "nested.md.md").exists()

    reasons = {skip.path.name: skip.reason for skip in result.skipped}
    assert reasons["empty.txt"] == SkipReason.EMPTY_DOCUMENT
    assert reasons["photo.jpg"] == SkipReason.UNSUPPORTED_EXTENSION
    assert not (out_dir / "empty.txt.md").exists()
    assert not (out_dir / "photo.jpg.md").exists()


def test_generated_wiki_contains_required_sections(
    corpus: Path, tmp_path: Path, stub_ollama: list[str]
) -> None:
    out_dir = tmp_path / "wiki"

    run_scan(_config(corpus, out_dir))

    markdown = (out_dir / "normal.txt.md").read_text(encoding="utf-8")
    for marker in ("source_path:", "generated_at:", "model:", "source_bytes:"):
        assert marker in markdown
    for header in ("# 문서 제목", "## 한 줄 요약", "## 핵심 포인트", "## 요약", "## 태그·키워드", "## 원문"):
        assert header in markdown
    assert f"file://{corpus / 'normal.txt'}" in markdown


def test_single_llm_failure_does_not_fail_the_run(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": []}
        if "하위 문서" in payload["prompt"]:
            return {"response": "JSON이 아닌 응답"}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(corpus, out_dir))

    assert [wiki.source_path.name for wiki in result.generated] == ["normal.txt"]
    failed = {skip.path.name: skip for skip in result.skipped}
    assert failed["nested.md"].reason == SkipReason.SUMMARY_FAILED
    assert failed["nested.md"].detail


def test_only_localhost_is_contacted(corpus: Path, tmp_path: Path, stub_ollama: list[str]) -> None:
    run_scan(_config(corpus, tmp_path / "wiki"))

    assert stub_ollama
    assert all(url.startswith("http://127.0.0.1:11434/") for url in stub_ollama)


def test_rerun_skips_up_to_date_files(
    corpus: Path, tmp_path: Path, stub_ollama: list[str]
) -> None:
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    result = run_scan(_config(corpus, out_dir))

    assert result.generated == []
    up_to_date = {skip.path.name for skip in result.skipped if skip.reason == SkipReason.UP_TO_DATE}
    assert up_to_date == {"normal.txt", "nested.md"}


def test_force_regenerates_even_when_up_to_date(
    corpus: Path, tmp_path: Path, stub_ollama: list[str]
) -> None:
    out_dir = tmp_path / "wiki"
    run_scan(_config(corpus, out_dir))

    result = run_scan(_config(corpus, out_dir, force=True))

    assert len(result.generated) == 2


def test_limit_exceeded_stops_processing(tmp_path: Path, stub_ollama: list[str]) -> None:
    root = tmp_path / "many"
    root.mkdir()
    for index in range(51):
        (root / f"doc{index:03d}.txt").write_text("본문", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    result = run_scan(_config(root, out_dir, max_files=50))

    assert result.limit_exceeded is True
    assert result.discovered_count == 51
    assert result.generated == []
    assert not out_dir.exists()


def test_missing_folder_is_precondition_failure(tmp_path: Path, stub_ollama: list[str]) -> None:
    with pytest.raises(PreconditionError):
        run_scan(_config(tmp_path / "없는폴더", tmp_path / "wiki"))


def test_ollama_not_detected_is_precondition_failure(
    corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _refused(url: str, **_: Any) -> Any:
        raise gateway.GatewayError("연결 거부", url=url)

    monkeypatch.setattr(gateway, "request_json", _refused)

    with pytest.raises(PreconditionError):
        run_scan(_config(corpus, tmp_path / "wiki"))
