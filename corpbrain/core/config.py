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

#: 요약 엔진 (v0.5 스펙 §4.1). 기본은 로컬이며, 클라우드는 사용자가 명시적으로 켤 때만 쓴다.
ENGINE_LOCAL = "local"
ENGINE_CLOUD = "cloud"
ENGINES: tuple[str, ...] = (ENGINE_LOCAL, ENGINE_CLOUD)

#: `--cloud-model` 기본값 — 빠르고 저렴한 모델 (v0.5 스펙 §4.1).
DEFAULT_CLOUD_MODEL = "claude-haiku-4-5-20251001"

#: API 키를 받는 유일한 통로 — Anthropic 공식 관례와 같은 이름을 재사용한다 (v0.5 §4.1).
#:
#: 이름(설정 키)은 코어 설정이 소유한다. 리포트·CLI 같은 표시 계층이 이 문자열 하나 때문에
#: 클라우드 전송 모듈(`llm.anthropic_client`)을 import 하면, 표시 계층이 전송 계층에 묶이고
#: `core/__init__ → environment → anthropic_client → core` 순환 import가 깊어진다.
#: 값 자체는 어디에도 저장하지 않는다 — 읽기는 `anthropic_client.resolve_api_key()`뿐이다.
API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

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
    #: 요약 엔진 — `"local"`(기본, v0.4까지와 동일) 또는 `"cloud"` (v0.5 §4.1).
    #: `"cloud"`는 사용자 동의와 `ANTHROPIC_API_KEY`가 모두 있어야 하며, 임베딩은 엔진과
    #: 무관하게 항상 로컬이다 (v0.5 §2 비목표).
    engine: str = ENGINE_LOCAL
    #: `engine="cloud"`일 때 쓸 Anthropic 모델 (v0.5 §4.1). API 키는 여기 담지 않는다 —
    #: 자격증명은 `llm.anthropic_client`가 호출 시점에 환경변수에서 직접 읽는다.
    cloud_model: str = DEFAULT_CLOUD_MODEL

    @property
    def effective_model(self) -> str:
        """이번 실행이 **실제로 요약에 쓸** 모델 이름 (v0.5 §4.1).

        엔진에 따라 `model`(로컬)과 `cloud_model`(클라우드) 중 하나가 실제로 호출된다.
        어댑터가 배너·로그에 모델명을 표시할 때 둘 중 무엇인지 매번 분기하지 않도록
        코어가 한 곳에서 판정한다 — 분기를 빠뜨리면 호출되지도 않는 모델명이 찍힌다.
        """
        return self.cloud_model if self.engine == ENGINE_CLOUD else self.model
