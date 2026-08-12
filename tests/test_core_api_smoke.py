"""코어 API 스모크 — CLI를 거치지 않고 코어를 직접 호출할 수 있는지 확인한다 (FR-002 / 스펙 §4.5)."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

from corpbrain import core


def test_core_public_api_is_importable_without_cli() -> None:
    """코어 import 경로가 `corpbrain.cli`를 끌어들이지 않는다.

    pytest는 수집 단계에서 CLI 테스트 모듈까지 import 하므로, 이 성질은 현재 프로세스의
    `sys.modules`가 아니라 별도 인터프리터에서 확인해야 한다.
    """
    assert callable(core.run_scan)

    probe = subprocess.run(
        [sys.executable, "-c", "import sys, corpbrain.core; assert 'corpbrain.cli' not in sys.modules"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr


def test_run_scan_takes_pure_config_value() -> None:
    """공개 진입점은 어댑터 타입이 아닌 순수 값(`ScanConfig`)을 받는다."""
    signature = inspect.signature(core.run_scan)
    assert list(signature.parameters) == ["config"]
    assert signature.parameters["config"].annotation == "ScanConfig"


def test_scan_config_defaults_match_spec() -> None:
    """스펙 §4.1의 CLI 기본값이 코어 기본값과 일치한다."""
    config = core.ScanConfig(folder=Path("/tmp/in"))
    assert config.out_dir == Path("./corpbrain_wiki")
    assert config.model == "qwen2.5:7b-instruct"
    assert config.max_files == 50
    assert config.max_chars == 12000
    assert config.ollama_url == "http://127.0.0.1:11434"
    assert config.force is False
