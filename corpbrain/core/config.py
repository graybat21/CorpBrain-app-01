"""코어 실행 파라미터 (순수 값 — CLI 타입에 의존하지 않는다).

기본값은 스펙 §4.1 CLI 계약에서 온다. CLI 어댑터는 인자를 파싱해 `ScanConfig`를 만들어
코어에 넘기고, 코어는 argparse 등 어댑터 타입을 알지 못한다 (스펙 §4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUT_DIR = Path("./corpbrain_wiki")
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_MAX_FILES = 50
DEFAULT_MAX_CHARS = 12000
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

#: 지원 포맷 3종 (스펙 §4.2). 그 외 확장자는 스킵한다.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".txt", ".md"})

#: 경로 길이 상한 (스펙 §5) — 초과 시 스킵한다.
MAX_PATH_LENGTH = 260


@dataclass(frozen=True)
class ScanConfig:
    """`scan` 파이프라인 1회 실행에 필요한 모든 입력."""

    folder: Path
    out_dir: Path = DEFAULT_OUT_DIR
    model: str = DEFAULT_MODEL
    max_files: int = DEFAULT_MAX_FILES
    max_chars: int = DEFAULT_MAX_CHARS
    ollama_url: str = DEFAULT_OLLAMA_URL
    force: bool = False
