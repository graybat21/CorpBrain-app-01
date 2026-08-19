"""자원 게이트 파이프라인·CLI 통합 테스트 (v0.3 스펙 §3 완료의 정의 1·2·3·5).

Ollama HTTP는 단일 관문을 스텁하고, GPU 감지는 `plan.detect_hardware`를 monkeypatch로
고정해 실제 하드웨어와 무관하게 게이트 동작을 검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from corpbrain import cli
from corpbrain.core import gateway
from corpbrain.core import plan as plan_module
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL, ScanConfig
from corpbrain.core.errors import GpuGateError, TokenBudgetExceededError
from corpbrain.core.models import HardwareInfo, SkipReason
from corpbrain.core.pipeline import run_scan

TAGS_RESPONSE = {"models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]}
SUMMARY_JSON = {
    "title": "제목",
    "one_line_summary": "한 줄",
    "key_points": ["a", "b", "c"],
    "summary": "요약",
    "tags": ["t"],
}


@pytest.fixture
def ok_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return TAGS_RESPONSE
        if url.endswith("/api/embeddings"):
            return {"embedding": [0.1, 0.2, 0.3]}
        return {"response": json.dumps(SUMMARY_JSON, ensure_ascii=False)}

    monkeypatch.setattr(gateway, "request_json", _request_json)


def _force_hardware(monkeypatch: pytest.MonkeyPatch, *, gpu: bool) -> None:
    label = "GPU: Test" if gpu else "CPU"
    monkeypatch.setattr(
        plan_module, "detect_hardware", lambda: HardwareInfo(gpu=gpu, label=label)
    )


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "note.txt").write_text("작은 문서 본문", encoding="utf-8")
    return root


# --- GPU 게이트 (완료의 정의 1) -------------------------------------------------


def test_gpu_gate_blocks_scan_without_force(
    corpus: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=False)

    with pytest.raises(GpuGateError):
        run_scan(ScanConfig(folder=corpus, out_dir=tmp_path / "wiki"))


def test_force_gates_bypasses_gpu_gate(
    corpus: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=False)

    result = run_scan(ScanConfig(folder=corpus, out_dir=tmp_path / "wiki", force_gates=True))

    assert [w.source_path.name for w in result.generated] == ["note.txt"]


def test_gpu_gate_exit_1_via_cli(
    corpus: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=False)

    blocked = cli.main(["scan", str(corpus), "--out", str(tmp_path / "wiki")])
    assert blocked == cli.EXIT_PRECONDITION_FAILED

    forced = cli.main(["scan", str(corpus), "--out", str(tmp_path / "w2"), "--force-gates"])
    assert forced == cli.EXIT_OK


# --- 토큰 게이트 (완료의 정의 2) ------------------------------------------------


def test_token_gate_blocks_scan(
    corpus: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=True)  # GPU는 통과, 토큰만 차단

    with pytest.raises(TokenBudgetExceededError):
        run_scan(
            ScanConfig(folder=corpus, out_dir=tmp_path / "wiki", max_total_tokens=1)
        )


def test_token_gate_counts_embedding_margin_v0_4(
    tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v0.4 §3 항목12: 임베딩 비용 가산분(원문 토큰의 10%) 때문에만 넘는 임계에서도 차단된다."""
    from corpbrain.core.plan import plan_scan

    _force_hardware(monkeypatch, gpu=True)
    root = tmp_path / "docs"
    root.mkdir()
    (root / "note.txt").write_text("가" * 2000, encoding="utf-8")

    base_plan = plan_scan(ScanConfig(folder=root))
    base_tokens = base_plan.entries[0].est_tokens
    assert base_tokens > 0

    # 임계를 순수 요약 토큰과 정확히 같게 두면, 10% 가산분 없이는 통과했을 값이다.
    with pytest.raises(TokenBudgetExceededError):
        run_scan(
            ScanConfig(folder=root, out_dir=tmp_path / "wiki", max_total_tokens=base_tokens)
        )


def test_token_gate_exit_3_via_cli(
    corpus: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=True)

    blocked = cli.main(
        ["scan", str(corpus), "--out", str(tmp_path / "wiki"), "--max-total-tokens", "1"]
    )
    assert blocked == cli.EXIT_LIMIT_EXCEEDED

    forced = cli.main(
        ["scan", str(corpus), "--out", str(tmp_path / "w2"),
         "--max-total-tokens", "1", "--force-gates"]
    )
    assert forced == cli.EXIT_OK


# --- 파일 크기 게이트 (완료의 정의 3·5) ----------------------------------------


@pytest.fixture
def mixed_sizes(tmp_path: Path) -> Path:
    root = tmp_path / "mixed"
    root.mkdir()
    (root / "small.txt").write_text("y" * 40, encoding="utf-8")
    (root / "big.txt").write_text("z" * 500, encoding="utf-8")
    return root


def test_oversized_file_skipped_others_processed(
    mixed_sizes: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 3: 대용량 파일만 file_too_large로 스킵, 나머지는 정상 생성(exit 0)."""
    _force_hardware(monkeypatch, gpu=True)

    result = run_scan(
        ScanConfig(folder=mixed_sizes, out_dir=tmp_path / "wiki", max_file_size=100)
    )

    generated = {w.source_path.name for w in result.generated}
    skipped = {s.path.name: s.reason for s in result.skipped}
    assert generated == {"small.txt"}
    assert skipped["big.txt"] == SkipReason.FILE_TOO_LARGE
    assert not (tmp_path / "wiki" / "big.txt.md").exists()


def test_oversized_exit_zero_via_cli(
    mixed_sizes: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_hardware(monkeypatch, gpu=True)

    code = cli.main(
        ["scan", str(mixed_sizes), "--out", str(tmp_path / "wiki"), "--max-file-size", "1"]
    )
    # --max-file-size 1(MB) → small/big 모두 1MB 미만이라 스킵 없음; 부분 성공 exit 0.
    assert code == cli.EXIT_OK


def test_force_gates_does_not_bypass_file_too_large(
    mixed_sizes: Path, tmp_path: Path, ok_gateway: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """완료의 정의 5: --force-gates는 차단 게이트만 무시하고 file_too_large 스킵은 유지한다."""
    _force_hardware(monkeypatch, gpu=False)  # GPU 없음 + force_gates로 강행

    result = run_scan(
        ScanConfig(
            folder=mixed_sizes,
            out_dir=tmp_path / "wiki",
            max_file_size=100,
            force_gates=True,
        )
    )

    generated = {w.source_path.name for w in result.generated}
    skipped = {s.path.name: s.reason for s in result.skipped}
    assert generated == {"small.txt"}  # 강행해도 처리됨
    assert skipped["big.txt"] == SkipReason.FILE_TOO_LARGE  # 대용량은 여전히 스킵
