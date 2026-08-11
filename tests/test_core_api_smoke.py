"""코어 API 스모크 — CLI를 거치지 않고 코어를 직접 호출할 수 있는지 확인한다 (FR-002 / 스펙 §4.5)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from corpbrain import core


def test_core_public_api_is_importable_without_cli() -> None:
    """코어 import 경로가 `corpbrain.cli`를 끌어들이지 않는다."""
    assert callable(core.run_scan)
    assert "corpbrain.cli" not in sys.modules


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
