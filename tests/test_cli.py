"""CLI 어댑터 단위 테스트 — 플래그 파싱·기본값·모델 우선순위·코어 디스패치 (FR-014 / 스펙 §4.1, §4.5).

코어 파이프라인(`run_scan`)은 FR-015에서 채워지므로 여기서는 monkeypatch로 가로채고,
"올바른 `ScanConfig`가 코어로 전달되는가"만 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain import cli, core


@pytest.fixture(autouse=True)
def _clear_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경변수 오염을 막는다 — 각 테스트가 필요할 때만 직접 설정한다."""
    monkeypatch.delenv(cli.MODEL_ENV_VAR, raising=False)


def _config_for(argv: list[str]) -> core.ScanConfig:
    """argv를 파싱해 코어에 넘길 설정 객체로 만든다."""
    args = cli.build_parser().parse_args(argv)
    return cli.build_config(args)


def test_defaults_match_spec() -> None:
    """Scenario 1: `corpbrain scan ./inbox`만 입력하면 스펙 §4.1 기본값이 채워진다."""
    config = _config_for(["scan", "./inbox"])

    assert config.folder == Path("./inbox")
    assert config.out_dir == Path("./corpbrain_wiki")
    assert config.model == "qwen2.5:7b-instruct"
    assert config.max_files == 50
    assert config.max_chars == 12000
    assert config.ollama_url == "http://127.0.0.1:11434"
    assert config.force is False


def test_defaults_come_from_core_constants() -> None:
    """기본값의 출처는 CLI 하드코딩이 아니라 코어 상수다 (스펙 §4.5)."""
    config = _config_for(["scan", "./inbox"])

    assert config.out_dir == core.DEFAULT_OUT_DIR
    assert config.model == core.DEFAULT_MODEL
    assert config.max_files == core.DEFAULT_MAX_FILES
    assert config.max_chars == core.DEFAULT_MAX_CHARS
    assert config.ollama_url == core.DEFAULT_OLLAMA_URL


def test_explicit_flags_override_defaults() -> None:
    """모든 플래그를 명시하면 그대로 설정 객체에 반영된다."""
    config = _config_for(
        [
            "scan",
            "./inbox",
            "--out",
            "/tmp/wiki",
            "--model",
            "llama3.1:8b",
            "--max",
            "7",
            "--max-chars",
            "2000",
            "--ollama-url",
            "http://127.0.0.1:9999",
            "--force",
        ]
    )

    assert config.folder == Path("./inbox")
    assert config.out_dir == Path("/tmp/wiki")
    assert config.model == "llama3.1:8b"
    assert config.max_files == 7
    assert config.max_chars == 2000
    assert config.ollama_url == "http://127.0.0.1:9999"
    assert config.force is True


def test_explicit_model_flag_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 2: 환경변수가 있어도 명시 `--model`이 이긴다."""
    monkeypatch.setenv(cli.MODEL_ENV_VAR, "envmodel")

    config = _config_for(["scan", "./inbox", "--model", "flagmodel"])

    assert config.model == "flagmodel"


def test_env_model_used_when_flag_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 2 후반: `--model` 없이 실행하면 환경변수 값이 쓰인다."""
    monkeypatch.setenv(cli.MODEL_ENV_VAR, "envmodel")

    config = _config_for(["scan", "./inbox"])

    assert config.model == "envmodel"


def test_blank_env_model_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈/공백 환경변수는 미설정으로 보고 코어 기본값으로 떨어진다."""
    monkeypatch.setenv(cli.MODEL_ENV_VAR, "   ")

    config = _config_for(["scan", "./inbox"])

    assert config.model == core.DEFAULT_MODEL


def test_main_dispatches_config_to_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main`은 만들어진 `ScanConfig`를 코어 진입점에 넘기고 성공 시 0을 반환한다."""
    received: list[core.ScanConfig] = []

    def fake_run_scan(config: core.ScanConfig, **_: object) -> core.ScanResult:
        received.append(config)
        return core.ScanResult(out_dir=config.out_dir)

    monkeypatch.setattr(core, "run_scan", fake_run_scan)
    monkeypatch.setenv(cli.MODEL_ENV_VAR, "envmodel")

    exit_code = cli.main(["scan", "./inbox", "--max", "3"])

    assert exit_code == 0
    assert received == [
        core.ScanConfig(
            folder=Path("./inbox"),
            out_dir=core.DEFAULT_OUT_DIR,
            model="envmodel",
            max_files=3,
            max_chars=core.DEFAULT_MAX_CHARS,
            ollama_url=core.DEFAULT_OLLAMA_URL,
            force=False,
        )
    ]


def test_subcommand_is_required() -> None:
    """서브커맨드 없이 호출하면 argparse가 사용법 오류로 거부한다."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_folder_argument_is_required() -> None:
    """`scan`은 위치 인자 `folder` 1개를 요구한다."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["scan"])


@pytest.mark.parametrize("unknown_flag", ["--verbose", "--dry-run", "--out-dir"])
def test_flags_outside_spec_are_rejected(unknown_flag: str) -> None:
    """스펙 §4.1에 없는 플래그는 받지 않는다."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["scan", "./inbox", unknown_flag])
