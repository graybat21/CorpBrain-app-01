"""코어 실행 파라미터 (순수 값 — CLI 타입에 의존하지 않는다).

기본값은 스펙 §4.1 CLI 계약에서 온다. CLI 어댑터는 인자를 파싱해 `ScanConfig`를 만들어
코어에 넘기고, 코어는 argparse 등 어댑터 타입을 알지 못한다 (스펙 §4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from corpbrain.core.models import EdgeType

DEFAULT_OUT_DIR = Path("./corpbrain_wiki")
DEFAULT_MODEL = "qwen2.5:7b-instruct"
#: 임베딩 전용 모델 (v0.4 스펙 §4.1). 요약 모델과 별개로 프리플라이트에서 존재를 확인한다.
DEFAULT_EMBED_MODEL = "qwen3-embedding:4b"
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

#: 지원 포맷 (스펙 §4.2 + v0.2 §4.1 `.pdf` + v0.8 §4.1 오피스). 그 외 확장자는 스킵한다.
#:
#: **이 상수가 지원 포맷 목록의 정본이며 다른 모든 목록은 파생이다** (v0.8 §4.1).
#: `extract.EXTRACTORS`의 키 집합이 이 값과 정확히 같아야 하고, 그 정합성은
#: `tests/unit/test_extract.py`가 단언한다.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".docx", ".txt", ".md", ".pdf", ".xlsx", ".xlsm"}
)

#: 경로 길이 상한 (스펙 §5) — 초과 시 스킵한다.
MAX_PATH_LENGTH = 260

#: `SEMANTICALLY_SIMILAR` 엣지를 만드는 코사인 유사도 하한 (v0.6 스펙 §4.7).
#: 비교는 `>=`(이상)이며, 이 값과 정확히 같은 쌍도 엣지를 만든다 (§4.1).
#: v0.7 임베딩 모델 재판단(issue #42)에서 `qwen3-embedding:4b` 채택과 함께 재산정했다 —
#: 24문서 코퍼스에서 "의도된 관련 쌍"의 코사인 중앙값. 관련·무관 쌍 사이에 깨끗한 간극이
#: 없어(§4.1 "전원 실패" 케이스) 중간값 대신 이 대체 기준을 썼다. 근거는
#: `docs/SMOKE.md` 실행 I, `static/docs/specs/features/corpbrain-v0.7-embedding-model-reassessment.md`.
DEFAULT_SIMILARITY_THRESHOLD = 0.5717153219583704
#: 위키 「관련 문서」 섹션에 넣을 최대 항목 수 (v0.6 스펙 §4.7).
DEFAULT_RELATED_TOP_K = 5

#: 그래프 시드 확산의 감쇠 계수 α (v0.7 스펙 §4.1). 확산 문서의 점수는
#: `max(자기 코사인, 기준 시드 점수 × α)`이며, 열린 구간 `0 < α < 1`에서만
#: 「확산 문서는 자기 시드를 추월하지 못한다」가 성립한다.
#:
#: **실측으로 확정한 값이다** — 24문서 코퍼스·쿼리 15개로 α를 0.5~0.95 스윕한 결과에
#: 스펙 §4.8 4번 규칙(top-1 → MRR → Recall@3 → α 작은 쪽)을 적용해 나왔다.
#: 근거는 `docs/SMOKE.md` 실행 J, 원시 출력은 `docs/smoke/graph_decay_results.{json,csv}`.
#:
#: 이 코퍼스에서 **그래프 확산은 코사인 단독보다 나은 결과를 내지 못했다.** 확산이 개입할수록
#: 지표가 단조 하락해, 규칙이 고른 0.5는 「가장 좋은 개입 강도」가 아니라 **「이 코퍼스에서
#: 개입이 일어나지 않는 지점」**이다 — α=0.5에서는 확산 문서가 결과에 한 건도 들어오지 않아
#: 출력이 `--no-graph`와 같다. 원인은 요약 모델이 뽑는 엔티티가 대부분 부서명이라 선택성이
#: 없다는 것이다 — `인사팀` 하나가 23문서 중 10개를 잇는다. 자세한 내용과 우회법은
#: `docs/USAGE.md` §6.3에 있다.
#:
#: 자동 테스트는 이 상수를 참조하지 않고 `graph_decay=`를 명시적으로 넘긴다 — 코퍼스가
#: 달라져 이 한 줄을 다시 교체해도 테스트가 깨지지 않게 하기 위함이다.
DEFAULT_GRAPH_DECAY = 0.5

#: 확산에 쓸 기본 엣지 종류 3종 (v0.7 스펙 §4.2). 임베딩이 포착하지 못하는 신호만 더한다.
#: `SEMANTICALLY_SIMILAR`는 임베딩 코사인 그 자체라 같은 신호를 두 번 세게 되므로 기본에서
#: 빠져 있다 — `--expand-edges`로 켤 수 있다.
DEFAULT_EXPAND_EDGES: frozenset[EdgeType] = frozenset(
    {EdgeType.TAGGED_WITH, EdgeType.CONTAINS_ENTITY, EdgeType.REFERENCES}
)


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
    #: `SEMANTICALLY_SIMILAR` 엣지를 만드는 코사인 유사도 하한 (v0.6 §4.7). 기본값을
    #: 보존하므로 v0.5까지의 동작이 그대로다.
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    #: 위키 「관련 문서」 섹션의 최대 항목 수 (v0.6 §4.7).
    related_top_k: int = DEFAULT_RELATED_TOP_K

    @property
    def effective_model(self) -> str:
        """이번 실행이 **실제로 요약에 쓸** 모델 이름 (v0.5 §4.1).

        엔진에 따라 `model`(로컬)과 `cloud_model`(클라우드) 중 하나가 실제로 호출된다.
        어댑터가 배너·로그에 모델명을 표시할 때 둘 중 무엇인지 매번 분기하지 않도록
        코어가 한 곳에서 판정한다 — 분기를 빠뜨리면 호출되지도 않는 모델명이 찍힌다.
        """
        return self.cloud_model if self.engine == ENGINE_CLOUD else self.model
