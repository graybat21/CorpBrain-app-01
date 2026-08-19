"""코어 실행 파라미터 (순수 값 — CLI 타입에 의존하지 않는다).

기본값은 스펙 §4.1 CLI 계약에서 온다. CLI 어댑터는 인자를 파싱해 `ScanConfig`를 만들어
코어에 넘기고, 코어는 argparse 등 어댑터 타입을 알지 못한다 (스펙 §4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUT_DIR = Path("./corpbrain_wiki")
DEFAULT_MODEL = "qwen2.5:7b-instruct"
#: 임베딩 전용 모델 (v0.4 스펙 §4.1). 요약 모델과 별개로 프리플라이트에서 존재를 확인한다.
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_MAX_FILES = 50
DEFAULT_MAX_CHARS = 12000
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

#: 개별 파일 크기 상한 바이트 — 초과 파일은 `file_too_large`로 스킵한다 (v0.3 스펙 §4.4).
#: 20MB(십진) = CLI `--max-file-size 20`.
DEFAULT_MAX_FILE_SIZE = 20_000_000
#: 스캔 전체 예상 토큰 예산 — 초과 시 차단한다 (v0.3 스펙 §4.4).
DEFAULT_MAX_TOTAL_TOKENS = 200_000

#: 지원 포맷 4종 (스펙 §4.2 + v0.2 §4.1 `.pdf`). 그 외 확장자는 스킵한다.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".txt", ".md", ".pdf"})

#: 경로 길이 상한 (스펙 §5) — 초과 시 스킵한다.
MAX_PATH_LENGTH = 260


@dataclass(frozen=True)
class ScanConfig:
    """`scan` 파이프라인 1회 실행에 필요한 모든 입력."""

    folder: Path
    out_dir: Path = DEFAULT_OUT_DIR
    model: str = DEFAULT_MODEL
    #: 임베딩에 쓸 Ollama 모델 — scan 프리플라이트에서 존재를 확인한다(v0.4 §4.2 ④).
    embed_model: str = DEFAULT_EMBED_MODEL
    max_files: int = DEFAULT_MAX_FILES
    max_chars: int = DEFAULT_MAX_CHARS
    ollama_url: str = DEFAULT_OLLAMA_URL
    force: bool = False
    #: 개별 파일 크기 상한(바이트) — 초과 파일은 `file_too_large`로 스킵 (v0.3 §4.2).
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    #: 스캔 전체 예상 토큰 예산 — 초과 시 차단(exit 3) (v0.3 §4.2).
    max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS
    #: 차단 게이트(GPU·토큰)를 무시하고 강행한다 — `file_too_large` 스킵에는 영향 없음 (v0.3 §4.2).
    force_gates: bool = False
