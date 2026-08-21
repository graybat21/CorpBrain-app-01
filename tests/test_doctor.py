"""Ollama 진단(doctor)·모델 선점검·plan 게이트 표시 검증 (v0.3 스펙 §3 완료의 정의 4·6·7).

`shutil.which`·`list_models`·`detect_hardware`를 스텁해 실제 환경·데몬과 무관하게 네 가지
상태(미설치/미구동/모델없음/준비)와 종료 코드를 검증한다. Ollama HTTP는 단일 관문 스텁만 쓴다.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from corpbrain import cli
from corpbrain.core import environment, gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL
from corpbrain.core.llm import ollama_client
from corpbrain.core.llm.ollama_client import OllamaNotAvailableError
from corpbrain.core.models import HardwareInfo


def _stub_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    installed: bool,
    models: list[str] | None,
    gpu: bool = True,
) -> None:
    """설치(shutil.which)·모델목록(list_models)·GPU(detect_hardware)를 고정한다.

    `models=None`이면 데몬 미구동(list_models가 예외)을 흉내 낸다.
    """
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ollama" if installed else None)
    monkeypatch.setattr(
        environment, "detect_hardware",
        lambda: HardwareInfo(gpu=gpu, label="GPU: X" if gpu else "CPU"),
    )

    def _list_models(*_a: Any, **_k: Any) -> list[str]:
        if models is None:
            raise OllamaNotAvailableError("데몬 미구동")
        return models

    monkeypatch.setattr(ollama_client, "list_models", _list_models)


# --- diagnose 상태 4종 (완료의 정의 6) -----------------------------------------


def test_diagnose_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch, installed=False, models=None)
    report = environment.diagnose(model="m")
    assert report.installed is False
    assert report.ready is False


def test_diagnose_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch, installed=True, models=None)
    report = environment.diagnose(model="m")
    assert report.installed is True
    assert report.running is False
    assert report.ready is False


def test_diagnose_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch, installed=True, models=["other:latest"])
    report = environment.diagnose(model="qwen2.5:7b-instruct")
    assert report.running is True
    assert report.model_present is False
    assert report.ready is False


def test_diagnose_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_env(monkeypatch, installed=True, models=["qwen2.5:7b-instruct", DEFAULT_EMBED_MODEL])
    report = environment.diagnose(model="qwen2.5:7b-instruct")
    assert report.ready is True


def test_gpu_absence_does_not_affect_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """GPU 없음은 경고일 뿐 준비 판정(ready)에 영향을 주지 않는다 (완료의 정의 6)."""
    _stub_env(monkeypatch, installed=True, models=["m", DEFAULT_EMBED_MODEL], gpu=False)
    report = environment.diagnose(model="m")
    assert report.hardware.gpu is False
    assert report.ready is True


# --- 임베딩 모델 점검 (v0.4 스펙 §3 항목8) --------------------------------------


def test_diagnose_embed_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """대상 모델은 있지만 임베딩 모델이 없으면 ready는 False다 (v0.4 §3 항목8)."""
    _stub_env(monkeypatch, installed=True, models=[DEFAULT_MODEL])
    report = environment.diagnose(model=DEFAULT_MODEL, embed_model=DEFAULT_EMBED_MODEL)
    assert report.model_present is True
    assert report.embed_model_present is False
    assert report.ready is False


def test_cli_doctor_embed_model_missing_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_env(monkeypatch, installed=True, models=[DEFAULT_MODEL])
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert f"ollama pull {DEFAULT_EMBED_MODEL}" in out


# --- CLI doctor 종료 코드 (완료의 정의 6) --------------------------------------


def test_cli_doctor_ready_exit_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_env(monkeypatch, installed=True, models=[DEFAULT_MODEL, DEFAULT_EMBED_MODEL])
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "준비 완료" in out


def test_cli_doctor_not_installed_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_env(monkeypatch, installed=False, models=None)
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "미설치" in out


def test_cli_doctor_model_missing_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_env(monkeypatch, installed=True, models=["other:latest"])
    code = cli.main(["doctor", "--model", "qwen2.5:7b-instruct"])
    out = capsys.readouterr().out
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "ollama pull qwen2.5:7b-instruct" in out


# --- scan 모델 선점검 (완료의 정의 7) ------------------------------------------


def test_scan_preflight_blocks_when_model_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """대상 모델이 없으면 scan은 파일 처리 없이 exit 1 + `ollama pull` 안내로 종료한다."""
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "a.txt").write_text("본문", encoding="utf-8")

    def _request_json(url: str, *, method: str = "GET", payload: Any = None, **_: Any) -> Any:
        if url.endswith("/api/tags"):
            return {"models": [{"name": "other:latest"}]}  # 대상 모델 부재
        raise AssertionError("모델 부재 시 요약 호출까지 가면 안 된다")

    monkeypatch.setattr(gateway, "request_json", _request_json)
    out_dir = tmp_path / "wiki"

    code = cli.main(["scan", str(corpus), "--out", str(out_dir)])

    err = capsys.readouterr().err
    assert code == cli.EXIT_PRECONDITION_FAILED
    assert "ollama pull" in err
    assert not out_dir.exists()


# --- plan / dry-run 게이트 표시 (완료의 정의 4) --------------------------------


def test_plan_shows_gate_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """plan은 게이트 판정을 stdout에 표시하고 exit 0, 네트워크 관문을 거치지 않는다."""
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "a.txt").write_text("본문", encoding="utf-8")
    gateway.reset_requested_urls()

    code = cli.main(["plan", str(corpus)])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "게이트:" in out
    assert gateway.requested_urls() == ()  # plan은 네트워크 0


def test_dry_run_shows_gate_and_creates_no_wiki(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """scan --dry-run은 게이트를 표시하고 exit 0이며 위키를 만들지 않는다 (v0.2 DoD 7 보존)."""
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "a.txt").write_text("본문", encoding="utf-8")
    out_dir = tmp_path / "wiki"

    code = cli.main(["scan", str(corpus), "--out", str(out_dir), "--dry-run"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "게이트:" in out
    assert not out_dir.exists()


# --- 동의 설정 경로 이음새 (코드 리뷰 후속) ------------------------------------------


def test_diagnose_reads_the_injected_config_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`config_path`를 주면 그 파일만 본다 — 개발자의 실제 `~/.corpbrain`을 읽지 않는다."""
    from corpbrain.core.consent import grant_cloud_consent

    monkeypatch.setattr(
        Path, "home", classmethod(lambda _cls: tmp_path / "절대-없는-홈")
    )
    config = tmp_path / "config.json"
    grant_cloud_consent(config_path=config)

    report = environment.diagnose(model="m", config_path=config)

    assert report.cloud_consent is True


def test_diagnose_without_consent_file_reports_not_granted(tmp_path: Path) -> None:
    """주입한 경로에 파일이 없으면 '동의 없음'이다 (기본 상태)."""
    report = environment.diagnose(model="m", config_path=tmp_path / "none.json")

    assert report.cloud_consent is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [("sk-test", True), ("  ", False), (None, False)],
)
def test_api_key_presence_matches_scan_behaviour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    """doctor의 '키 설정됨' 판정이 scan의 실제 판정과 같은 규칙을 쓴다.

    doctor가 "설정됨"이라 했는데 scan이 "미설정"으로 막히면 사용자가 원인을 못 찾는다.
    공백만 든 값은 양쪽 모두 '미설정'이어야 한다.
    """
    from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR

    if value is None:
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(API_KEY_ENV_VAR, value)

    report = environment.diagnose(model="m", config_path=tmp_path / "none.json")

    assert report.cloud_api_key is expected


def test_cloud_state_does_not_affect_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """클라우드 준비 상태는 `ready`(종료 코드)에 영향을 주지 않는다 (v0.5 §3 항목10)."""
    from corpbrain.core.consent import grant_cloud_consent
    from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR

    config = tmp_path / "config.json"
    grant_cloud_consent(config_path=config)
    monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test")

    granted = environment.diagnose(model="m", config_path=config)
    absent = environment.diagnose(model="m", config_path=tmp_path / "none.json")

    assert granted.cloud_ready is True
    assert granted.ready == absent.ready  # 클라우드 상태와 무관하게 동일
