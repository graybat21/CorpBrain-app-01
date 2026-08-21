"""`consent` 서브커맨드와 doctor의 클라우드 상태 표시 (v0.5 스펙 §4.1·§3 항목1·3·10).

설정 파일은 `Path.home()`을 tmp로 돌려 격리한다 — 실제 `~/.corpbrain`을 건드리지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from corpbrain.cli import EXIT_OK, EXIT_PRECONDITION_FAILED, main
from corpbrain.core import gateway
from corpbrain.core.config import DEFAULT_EMBED_MODEL, DEFAULT_MODEL
from corpbrain.core.consent import (
    ConsentStoreError,
    grant_cloud_consent,
    is_cloud_consent_granted,
)
from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    return home


# --- consent 서브커맨드 (§3 항목1·3) ---------------------------------------------


def test_grant_records_consent_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """항목1: `consent cloud --grant`가 동의를 기록하고 exit 0."""
    assert main(["consent", "cloud", "--grant"]) == EXIT_OK

    assert is_cloud_consent_granted() is True
    out = capsys.readouterr().out
    assert "동의" in out
    assert API_KEY_ENV_VAR in out  # 키는 환경변수로 지정하라고 안내한다


def test_revoke_clears_consent_and_exits_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """항목3: `consent cloud --revoke`가 동의를 지우고 exit 0."""
    grant_cloud_consent()

    assert main(["consent", "cloud", "--revoke"]) == EXIT_OK

    assert is_cloud_consent_granted() is False
    assert "철회" in capsys.readouterr().out


def test_grant_is_idempotent() -> None:
    """같은 동의를 두 번 줘도 실패하지 않는다."""
    assert main(["consent", "cloud", "--grant"]) == EXIT_OK
    assert main(["consent", "cloud", "--grant"]) == EXIT_OK
    assert is_cloud_consent_granted() is True


def test_grant_and_revoke_are_mutually_exclusive() -> None:
    """argparse가 두 플래그를 동시에 받지 않는다."""
    with pytest.raises(SystemExit):
        main(["consent", "cloud", "--grant", "--revoke"])


def test_action_flag_is_required() -> None:
    """--grant/--revoke 중 하나는 반드시 있어야 한다 (실수로 상태를 바꾸지 않게)."""
    with pytest.raises(SystemExit):
        main(["consent", "cloud"])


def test_consent_never_writes_the_api_key(
    monkeypatch: pytest.MonkeyPatch, _isolated_home: Path
) -> None:
    """API 키는 설정 파일에 절대 저장되지 않는다 (§4.2)."""
    monkeypatch.setenv(API_KEY_ENV_VAR, "sk-super-secret")

    main(["consent", "cloud", "--grant"])

    stored = (_isolated_home / ".corpbrain" / "config.json").read_text(encoding="utf-8")
    assert "sk-super-secret" not in stored
    assert API_KEY_ENV_VAR not in stored


def test_write_failure_maps_to_precondition_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """쓰기 실패는 기존 선행 조건 실패 매핑(exit 1)을 그대로 쓴다 — 신규 종료 코드 없음."""
    def _boom(**_: Any) -> None:
        raise ConsentStoreError("디스크 오류")

    monkeypatch.setattr("corpbrain.core.grant_cloud_consent", _boom)

    assert main(["consent", "cloud", "--grant"]) == EXIT_PRECONDITION_FAILED


# --- doctor의 클라우드 상태 (§3 항목10) -------------------------------------------


@pytest.fixture
def ready_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """doctor가 로컬 항목에서 실패하지 않도록 Ollama를 준비된 상태로 만든다."""
    monkeypatch.setattr(
        gateway,
        "request_json",
        lambda url, **_: {
            "models": [{"name": DEFAULT_MODEL}, {"name": DEFAULT_EMBED_MODEL}]
        },
    )
    monkeypatch.setattr("corpbrain.core.environment.shutil.which", lambda _name: "/usr/bin/ollama")


@pytest.mark.parametrize(
    ("consent", "has_key", "expects"),
    [
        (True, True, ["[OK] Cloud(Anthropic): 사용 준비됨"]),
        (True, False, ["[OK] Cloud 동의: 기록됨", f"[경고] {API_KEY_ENV_VAR}: 미설정"]),
        (False, True, ["[경고] Cloud 동의: 없음", f"[OK] {API_KEY_ENV_VAR}: 설정됨"]),
        (False, False, ["[경고] Cloud 동의: 없음", f"[경고] {API_KEY_ENV_VAR}: 미설정"]),
    ],
)
def test_doctor_reports_all_four_cloud_states(
    ready_ollama: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    consent: bool,
    has_key: bool,
    expects: list[str],
) -> None:
    """항목10: 동의·키 유무 4가지 조합이 각각 구분돼 보고된다."""
    if consent:
        grant_cloud_consent()
    if has_key:
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test")
    else:
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)

    main(["doctor"])

    out = capsys.readouterr().out
    for fragment in expects:
        assert fragment in out


@pytest.mark.parametrize(("consent", "has_key"), [(True, True), (False, False)])
def test_cloud_state_never_changes_doctor_exit_code(
    ready_ollama: None,
    monkeypatch: pytest.MonkeyPatch,
    consent: bool,
    has_key: bool,
) -> None:
    """항목10: 클라우드 상태는 GPU 선례처럼 종료 코드에 영향을 주지 않는다."""
    if consent:
        grant_cloud_consent()
    if has_key:
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test")
    else:
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)

    assert main(["doctor"]) == EXIT_OK


# --- scan 플래그 기본값 (§4.1 하위 호환) -------------------------------------------


def test_scan_defaults_to_local_engine() -> None:
    """`--engine` 미지정이면 v0.4까지와 동일한 로컬 동작이다."""
    from corpbrain.cli import build_config, build_parser

    args = build_parser().parse_args(["scan", "docs"])
    config = build_config(args)

    assert config.engine == "local"


def test_scan_rejects_unknown_engine() -> None:
    """엔진 값은 local/cloud 두 가지로 제한된다."""
    from corpbrain.cli import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["scan", "docs", "--engine", "openai"])
