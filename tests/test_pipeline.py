"""파이프라인 오케스트레이션 테스트 (FR-015 / 스펙 §4.5, §5).

Ollama HTTP는 단일 관문(`gateway.request_json`)을 스텁해 대체하며, 코어 API를
CLI 없이 직접 호출한다 (스펙 §4.5 검증).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain.core import gateway, pipeline, scanner
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import SkipReason
from corpbrain.core.pipeline import run_scan
from corpbrain.core.plan import plan_scan

#: 요약·임베딩 대상 모델이 모두 설치된 정상 `/api/tags` 응답 (v0.3·v0.4 모델 선점검 통과용).
TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
EMBEDDING_RESPONSE = {"embedding": [0.1, 0.2, 0.3]}

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
            return TAGS_RESPONSE
        if url.endswith("/api/generate"):
            return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}
        if url.endswith("/api/embeddings"):
            return EMBEDDING_RESPONSE
        raise AssertionError(f"예상치 못한 호출 대상: {url}")

    monkeypatch.setattr(gateway, "request_json", _request_json)
    return urls


def _config(root: Path, out_dir: Path, **overrides: Any) -> ScanConfig:
    # 처리 경로 검증이 목적이므로 자원 게이트는 기본 우회한다(v0.3 GPU 무조건 차단은 별도 테스트).
    overrides.setdefault("force_gates", True)
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


def test_run_scan_reuses_given_findings_without_rewalking(
    corpus: Path, tmp_path: Path, stub_ollama: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """findings를 주면 run_scan은 디렉터리를 다시 순회하지 않고 그대로 쓴다 (배너와 워크 공유).

    어댑터가 pre-scan 배너용으로 한 번 훑은 결과를 그대로 넘겨 이중 워크를 없애는 경로다.
    """
    prewalked = scanner.scan_folder(corpus, max_files=50)

    def _no_walk(*args: object, **kwargs: object) -> object:
        raise AssertionError("findings를 받고도 run_scan이 다시 순회했다")

    monkeypatch.setattr(pipeline, "scan_folder", _no_walk)

    result = run_scan(_config(corpus, tmp_path / "wiki"), findings=prewalked)

    generated = {wiki.source_path.name for wiki in result.generated}
    assert generated == {"normal.txt", "nested.md"}  # 주입한 findings를 그대로 처리


def test_run_scan_recomputes_plan_when_it_mismatches_findings(
    corpus: Path, tmp_path: Path, stub_ollama: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """findings와 파일 수가 어긋나는 plan은 신뢰하지 않고 재계산한다 (오게이팅 방지).

    어댑터가 절단된/다른 스캔의 plan을 넘겨도 게이트가 엉뚱한 집합으로 판정되지 않도록,
    run_scan이 findings와 일치하지 않는 plan을 감지해 다시 계산한다.
    """
    config = _config(corpus, tmp_path / "wiki")
    real_findings = scanner.scan_folder(corpus, max_files=None)
    empty = scanner.scan_folder(tmp_path / "does_not_exist", max_files=None)
    wrong_plan = plan_scan(config, findings=empty)  # file_count=0 → real_findings와 불일치
    assert wrong_plan.file_count != len(real_findings.targets)

    recomputed_with: list[object] = []

    def _spy(cfg: ScanConfig, *, findings: object = None) -> object:
        recomputed_with.append(findings)
        return plan_scan(cfg, findings=findings)

    monkeypatch.setattr(pipeline, "plan_scan", _spy)

    run_scan(config, findings=real_findings, plan=wrong_plan)

    assert recomputed_with, "불일치 plan인데 재계산하지 않았다"
    assert len(recomputed_with[0].targets) == len(real_findings.targets)  # 올바른 findings로 재계산


def test_run_scan_reuses_matching_plan_without_recomputing(
    corpus: Path, tmp_path: Path, stub_ollama: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """findings와 일치하는 plan은 재계산 없이 재사용한다 (효율 유지)."""
    config = _config(corpus, tmp_path / "wiki")
    real_findings = scanner.scan_folder(corpus, max_files=None)
    good_plan = plan_scan(config, findings=real_findings)

    def _no_recompute(*args: object, **kwargs: object) -> object:
        raise AssertionError("findings와 일치하는 plan인데 재계산했다")

    monkeypatch.setattr(pipeline, "plan_scan", _no_recompute)

    run_scan(config, findings=real_findings, plan=good_plan)  # 재계산 없이 통과해야 한다


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
            return TAGS_RESPONSE
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
