"""러너와 종료 레코드 단위 테스트 (v0.9 스펙 §4.3.1 · §4.4 · §4.4.1).

스캔은 **별도 프로세스**로 돈다 — 코어에 협조적 취소 이음새가 없고 `run_scan`의 파라미터
목록은 `tests/test_core_api_smoke.py`가 정확히 일치로 잠가 두었기 때문이다. 러너는 그
자식 프로세스의 진입점이며, 이벤트를 JSON 한 줄씩 stdout에 쓴다.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from corpbrain.core.models import (
    EmbeddingFailure,
    GeneratedWiki,
    GraphOutcome,
    GraphSkipReason,
    GraphStats,
    InjectionFailure,
    ScanResult,
    SkippedFile,
    SkipReason,
)
from corpbrain.gui import runner


def _result(out_dir: Path) -> ScanResult:
    """중첩 객체·`Path`·`StrEnum`을 모두 담은 결과 — 직렬화가 실제로 걸리는 모양이다."""
    return ScanResult(
        out_dir=out_dir,
        generated=[GeneratedWiki(source_path=Path("C:/docs/a.md"), output_path=out_dir / "a.md.md")],
        skipped=[
            SkippedFile(path=Path("C:/docs/b.pdf"), reason=SkipReason.EMPTY_DOCUMENT, detail="빈 문서")
        ],
        embedding_failures=[EmbeddingFailure(path=Path("C:/docs/c.md"), detail="타임아웃")],
        limit_exceeded=False,
        discovered_count=3,
        graph=GraphOutcome(
            stats=GraphStats(
                documents=2,
                entities=1,
                tags=3,
                edges_by_type={"TAGGED_WITH": 4, "REFERENCES": 1},
            ),
            similarity_skipped=GraphSkipReason.VECTORS_UNAVAILABLE,
            related_updated_count=2,
            injection_failures=[InjectionFailure(path=out_dir / "a.md.md", detail="권한 거부")],
            duplicate_sources=[Path("C:/docs/dup.md")],
        ),
    )


# --- 종료 레코드 (§4.4.1) --------------------------------------------------------


def test_record_is_json_serializable(tmp_path: Path) -> None:
    """`ScanResult`는 `Path`와 `StrEnum`을 품고 있어 `asdict()`만으로는 JSON이 되지 않는다."""
    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)

    encoded = json.dumps(record, ensure_ascii=False)

    assert json.loads(encoded) == record


def test_paths_become_absolute_strings(tmp_path: Path) -> None:
    """`Path`는 문자열이 된다 — 표기는 플랫폼의 것을 따른다(Windows는 역슬래시)."""
    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)

    assert isinstance(record["out_dir"], str)
    assert record["generated"][0]["source_path"] == str(Path("C:/docs/a.md"))
    assert record["graph"]["duplicate_sources"] == [str(Path("C:/docs/dup.md"))]


def test_enums_become_their_values(tmp_path: Path) -> None:
    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)

    assert record["skipped"][0]["reason"] == "empty_document"
    assert record["graph"]["similarity_skipped"] == "vectors_unavailable"


def test_graph_stats_totals_are_added_explicitly(tmp_path: Path) -> None:
    """`GraphStats.nodes`·`edges`는 **프로퍼티라 `asdict()`에 담기지 않는다** (§4.4.1).

    그냥 직렬화하면 화면의 총계가 조용히 빈다.
    """
    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)
    stats = record["graph"]["stats"]

    assert stats["nodes"] == 2 + 1 + 3
    assert stats["edges"] == 4 + 1


def test_record_carries_adapter_fields(tmp_path: Path) -> None:
    """`ScanResult`에 없는 어댑터 정보 넷 (§4.4.1)."""
    record = runner.build_record(_result(tmp_path), workspace_id="ws-7", exit_code=3)

    assert record["schema"] == runner.RECORD_SCHEMA
    assert record["workspace_id"] == "ws-7"
    assert record["exit_code"] == 3
    assert record["finished_at"]


def test_nothing_is_dropped_from_scan_result(tmp_path: Path) -> None:
    """필드를 골라 버리지 않는다 — 화면이 나중에 무엇을 필요로 하든 이미 있다 (§4.4.1)."""
    import dataclasses

    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)

    for field in dataclasses.fields(ScanResult):
        assert field.name in record


# --- lastrun.json (§4.3.1) -------------------------------------------------------


def test_lastrun_round_trip(tmp_path: Path) -> None:
    record = runner.build_record(_result(tmp_path), workspace_id="ws1", exit_code=0)

    runner.write_lastrun(tmp_path, record)

    assert runner.read_lastrun(tmp_path) == record
    assert runner.lastrun_path(tmp_path).name == runner.LASTRUN_FILENAME


def test_missing_lastrun_reads_as_none(tmp_path: Path) -> None:
    assert runner.read_lastrun(tmp_path) is None


def test_schema_mismatch_is_ignored_not_repaired(tmp_path: Path) -> None:
    """`schema`가 다르면 **읽지 않고 무시한다** — 표시용 사본이라 오류로 만들지 않는다 (§4.4.1).

    저장소 스키마 불일치를 오류로 다루는 v0.4·v0.6 방침과 갈리는 지점이며, **정본이 아니기
    때문에** 갈라도 된다. 다음 스캔이 덮어쓴다.
    """
    runner.write_lastrun(tmp_path, {"schema": runner.RECORD_SCHEMA + 99, "out_dir": "x"})

    assert runner.read_lastrun(tmp_path) is None


def test_corrupt_lastrun_is_ignored(tmp_path: Path) -> None:
    runner.lastrun_path(tmp_path).write_text("{ 깨진", encoding="utf-8")

    assert runner.read_lastrun(tmp_path) is None


# --- 입력 페이로드 → ScanConfig (§4.4) -------------------------------------------


def test_config_from_payload_maps_known_fields(tmp_path: Path) -> None:
    config = runner.config_from_payload(
        {
            "folder": str(tmp_path / "docs"),
            "out_dir": str(tmp_path / "wiki"),
            "model": "qwen2.5:3b-instruct",
            "max_files": 12,
            "force": True,
        }
    )

    assert config.folder == tmp_path / "docs"
    assert config.out_dir == tmp_path / "wiki"
    assert config.model == "qwen2.5:3b-instruct"
    assert config.max_files == 12
    assert config.force is True


def test_config_from_payload_uses_core_defaults_for_omitted_fields(tmp_path: Path) -> None:
    """생략된 필드는 코어 기본값을 쓴다 — 서버가 값을 지어내지 않는다 (§4.7.1)."""
    from corpbrain.core.config import DEFAULT_MAX_CHARS, DEFAULT_MODEL

    config = runner.config_from_payload(
        {"folder": str(tmp_path / "docs"), "out_dir": str(tmp_path / "wiki")}
    )

    assert config.model == DEFAULT_MODEL
    assert config.max_chars == DEFAULT_MAX_CHARS


def test_config_from_payload_rejects_unknown_fields(tmp_path: Path) -> None:
    """모르는 키를 조용히 흘리지 않는다 — 오타가 기본값으로 도는 것을 막는다."""
    with pytest.raises(ValueError, match="알 수 없는"):
        runner.config_from_payload(
            {"folder": str(tmp_path), "out_dir": str(tmp_path), "modell": "오타"}
        )


def test_config_from_payload_requires_absolute_paths(tmp_path: Path) -> None:
    """서버는 상대경로를 받지 않는다 (§4.5) — cwd 기준으로 풀려 엉뚱한 폴더를 가리킨다."""
    with pytest.raises(ValueError, match="절대경로"):
        runner.config_from_payload({"folder": "docs", "out_dir": str(tmp_path)})


# --- 러너 진입점 (§4.4) ----------------------------------------------------------


def test_runner_emits_events_then_the_final_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stdout에 **JSON 한 줄 = 이벤트 하나**, 마지막 줄이 종료 레코드다 (§4.4)."""
    from corpbrain.core._progress import RunFinished, RunStarted

    def fake_run_scan(config, *, on_event=None, **_):
        assert on_event is not None
        on_event(RunStarted(at=1.0, model="m", total=1))
        on_event(RunFinished(at=2.0))
        return _result(config.out_dir)

    monkeypatch.setattr(runner, "run_scan", fake_run_scan)
    stdout = io.StringIO()
    payload = {"folder": str(tmp_path / "docs"), "out_dir": str(tmp_path / "wiki")}

    code = runner.run(io.StringIO(json.dumps(payload)), stdout, workspace_id="ws1")

    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert code == 0
    assert lines[0]["kind"] == "run_started"
    assert lines[1]["kind"] == "run_finished"
    assert lines[-1]["schema"] == runner.RECORD_SCHEMA
    assert lines[-1]["workspace_id"] == "ws1"


def test_runner_writes_lastrun_beside_the_wiki(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "wiki"

    def fake_run_scan(config, *, on_event=None, **_):
        config.out_dir.mkdir(parents=True, exist_ok=True)
        return _result(config.out_dir)

    monkeypatch.setattr(runner, "run_scan", fake_run_scan)
    payload = {"folder": str(tmp_path / "docs"), "out_dir": str(out_dir)}

    runner.run(io.StringIO(json.dumps(payload)), io.StringIO(), workspace_id="ws1")

    assert runner.read_lastrun(out_dir) is not None


def test_runner_maps_precondition_failure_to_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """종료 코드는 CLI와 같은 매핑을 쓴다 (§4.4)."""
    from corpbrain.core.errors import PreconditionError

    def failing(config, *, on_event=None, **_):
        raise PreconditionError("Ollama가 응답하지 않습니다")

    monkeypatch.setattr(runner, "run_scan", failing)
    stdout = io.StringIO()
    payload = {"folder": str(tmp_path / "docs"), "out_dir": str(tmp_path / "wiki")}

    code = runner.run(io.StringIO(json.dumps(payload)), stdout, workspace_id="ws1")

    assert code == 1
    last = json.loads(stdout.getvalue().splitlines()[-1])
    assert last["exit_code"] == 1
    assert "Ollama" in last["error"]
