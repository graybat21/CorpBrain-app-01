"""코어가 주고받는 데이터 구조 (순수 값).

어댑터(CLI·후속 UI)는 이 구조만 보고 결과를 렌더링한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class SkipReason(StrEnum):
    """산출물을 만들지 않고 건너뛴 사유 (스펙 §5)."""

    UNSUPPORTED_EXTENSION = "unsupported_extension"
    EMPTY_DOCUMENT = "empty_document"
    EXTRACTION_FAILED = "extraction_failed"
    PERMISSION_DENIED = "permission_denied"
    PATH_TOO_LONG = "path_too_long"
    SUMMARY_FAILED = "summary_failed"
    UP_TO_DATE = "up_to_date"
    #: 개별 파일 크기가 `max_file_size`를 초과해 스킵 (v0.3 스펙 §4.2 파일 크기 게이트).
    FILE_TOO_LARGE = "file_too_large"
    #: 클라우드 요약이 레이트리밋(429)에 걸림 — 재시도 없이 스킵 (v0.5 스펙 §3 항목8).
    CLOUD_RATE_LIMITED = "cloud_rate_limited"
    #: 429 외 모든 클라우드 호출 실패(5xx·타임아웃·연결오류·400/404 등) (v0.5 §3 항목8).
    CLOUD_API_ERROR = "cloud_api_error"


class IndexingSkipReason(StrEnum):
    """`--engine cloud`에서 벡터 인덱싱을 건너뛴 사유 (v0.5 스펙 §4.8).

    두 사유는 해결 방법이 다르다 — 하나는 데몬을 띄워야 하고 하나는 모델을 받아야 한다.
    단일 bool로 뭉개면 안내가 엉뚱한 곳을 가리킨다.
    """

    #: Ollama 데몬이 응답하지 않음 → `ollama serve`.
    OLLAMA_UNAVAILABLE = "ollama_unavailable"
    #: 데몬은 살아 있으나 임베딩 모델이 설치되지 않음 → `ollama pull <embed-model>`.
    EMBED_MODEL_MISSING = "embed_model_missing"


@dataclass(frozen=True)
class SkippedFile:
    """스킵된 입력 파일 1건과 그 사유."""

    path: Path
    reason: SkipReason
    detail: str = ""


@dataclass(frozen=True)
class GeneratedWiki:
    """생성된 위키 마크다운 1건 (입력 파일 1개 → 출력 1개)."""

    source_path: Path
    output_path: Path


@dataclass(frozen=True)
class EmbeddingFailure:
    """프리플라이트 통과 후 특정 문서의 임베딩 호출이 런타임에 실패한 1건 (v0.4 스펙 §4.3).

    `SkippedFile`과 의미가 다르다 — 위키 `.md`는 이미 정상 생성돼 있고 인덱싱만 실패했다.
    """

    path: Path
    detail: str = ""


@dataclass(frozen=True)
class PiiMasking:
    """클라우드로 보내기 전 문서 1건에서 마스킹한 PII 집계 (v0.5 스펙 §4.5).

    `EmbeddingFailure`와 같은 성격의 파일별 부가 기록이다 — 위키는 정상 생성되며,
    이 값은 "무엇이 얼마나 가려져 나갔는지"를 리포트에 표시하는 데만 쓴다.
    """

    path: Path
    #: 마스킹된 총 건수.
    total: int
    #: 유형 이름(`PiiType` 값 문자열) → 치환 건수. 1건 이상인 유형만 담는다.
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """벡터 검색 결과 1건 (v0.4 스펙 §4.3) — `VectorStore.search()`가 돌려준다."""

    doc_id: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SummaryResult:
    """LLM이 반환한 고정 필드 요약 (스펙 §4.3)."""

    title: str
    one_line_summary: str
    key_points: list[str]
    summary: str
    tags: list[str]
    #: 문서에 등장하는 인물·부서·시스템·프로젝트명 (v0.6 §4.2). **선택 필드**다 — 응답에
    #: 없으면 빈 배열이 된다. 위키 템플릿의 어느 섹션에도 렌더되지 않는 그래프 전용 재료라
    #: 위키 생성의 선행 조건으로 삼지 않는다.
    entities: list[str] = field(default_factory=list)


class NodeType(StrEnum):
    """지식그래프 노드 종류 (v0.6 스펙 §4.1)."""

    DOCUMENT = "Document"
    ENTITY = "Entity"
    TAG = "Tag"


class EdgeType(StrEnum):
    """지식그래프 엣지 종류 4종 (v0.6 스펙 §4.1).

    이 값이 곧 `GraphStats.edges_by_type`의 키이고 `edges` 테이블의 `type` 컬럼이다 —
    표기가 코드·저장소·출력에서 갈리지 않도록 한 곳에서 소유한다.
    """

    TAGGED_WITH = "TAGGED_WITH"
    CONTAINS_ENTITY = "CONTAINS_ENTITY"
    SEMANTICALLY_SIMILAR = "SEMANTICALLY_SIMILAR"
    REFERENCES = "REFERENCES"


class GraphSkipReason(StrEnum):
    """그래프의 일부 또는 전부를 만들지 못한 사유 (v0.6 스펙 §5)."""

    #: 벡터 인덱스가 없거나 비어 있어 유사도 엣지만 생략 (부분 그래프).
    VECTORS_UNAVAILABLE = "vectors_unavailable"
    #: 재빌드 트랜잭션이 실패해 이전 그래프를 그대로 보존.
    BUILD_FAILED = "build_failed"


@dataclass(frozen=True)
class DocFacts:
    """문서 하나에서 추출한 그래프 재료 (v0.6 스펙 §4.4 `doc_facts`).

    엣지는 `SummaryResult`가 아니라 이 값에서 파생한다 — 스킵된 문서는 이번 실행에
    `SummaryResult`가 없지만 이 재료는 저장소에 남아 그래프에 계속 참여한다.

    저장 테이블의 `updated_at` 컬럼은 여기에 담지 않는다. 저장소가 소유하는 운영 컬럼이고
    v0.6의 어떤 규칙도 이 값을 읽지 않는다.
    """

    doc_id: str
    title: str
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)


class ReferenceDirection(StrEnum):
    """두 문서 사이 `REFERENCES` 관계의 방향 — 「관련 문서」 근거 문구가 여기서 갈린다 (§4.5)."""

    NONE = "none"
    #: 이 문서가 상대를 참조함.
    OUTGOING = "outgoing"
    #: 상대가 이 문서를 참조함.
    INCOMING = "incoming"
    #: 서로 참조함.
    MUTUAL = "mutual"


@dataclass(frozen=True)
class RelatedDocument:
    """「관련 문서」 한 줄에 필요한 값 — 대상 문서와 관련 근거 (v0.6 스펙 §4.5)."""

    doc_id: str
    title: str
    similarity: float | None = None
    shared_tags: list[str] = field(default_factory=list)
    shared_entities: list[str] = field(default_factory=list)
    reference: ReferenceDirection = ReferenceDirection.NONE


@dataclass(frozen=True)
class GraphNode:
    """그래프 노드 1개 (v0.6 스펙 §4.1 노드 ID 체계)."""

    id: str
    type: NodeType
    label: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """그래프 엣지 1개. `weight`는 `SEMANTICALLY_SIMILAR`의 코사인 유사도에만 쓴다."""

    src: str
    dst: str
    type: EdgeType
    weight: float | None = None


@dataclass(frozen=True)
class GraphStats:
    """`scan` 종료 요약과 `graph --stats`가 함께 쓰는 집계 (v0.6 스펙 §4.6)."""

    documents: int = 0
    entities: int = 0
    tags: int = 0
    edges_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def nodes(self) -> int:
        """노드 총수 — 종류별 합."""
        return self.documents + self.entities + self.tags

    @property
    def edges(self) -> int:
        """엣지 총수 — 종류별 합."""
        return sum(self.edges_by_type.values())


@dataclass(frozen=True)
class InjectionFailure:
    """「관련 문서」 주입에 실패한 위키 — v0.4 `EmbeddingFailure`와 같은 모양이다."""

    path: Path
    detail: str


@dataclass(frozen=True)
class GraphOutcome:
    """그래프 단계의 결과 넷을 한데 담는다 (v0.6 스펙 §4.6).

    평면 필드로 흩뿌리지 않아 `ScanResult`가 버전마다 부풀지 않고, 후속 어댑터가 그래프
    영역만 통째로 소비할 수 있다.
    """

    stats: GraphStats | None = None
    #: 유사도 엣지를 생략한 사유. `None`이면 4종 모두 정상 생성.
    similarity_skipped: GraphSkipReason | None = None
    #: 재빌드 트랜잭션 실패 사유 원문. 빈 문자열이면 실패 없음.
    build_failure: str = ""
    #: 재료가 없어 위키 파싱으로 복원한 문서 수 (엔티티가 빈 배열이 된다).
    facts_missing_count: int = 0
    #: 「관련 문서」 블록이 실제로 달라져 다시 기록한 위키 수 — 생성/스킵과 별개 축이다.
    related_updated_count: int = 0
    injection_failures: list[InjectionFailure] = field(default_factory=list)
    #: 같은 원문(`source_path`)을 가리켜 밀려난 위키들. 서로 다른 스캔 루트가 같은 `--out`을
    #: 공유하면 생길 수 있다 — 마지막 것만 그래프에 참여하므로 조용히 두지 않고 알린다.
    duplicate_sources: list[Path] = field(default_factory=list)


@dataclass
class ScanResult:
    """파이프라인 1회 실행 결과 — 부분 성공을 그대로 담는다 (스펙 §5)."""

    out_dir: Path
    generated: list[GeneratedWiki] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    #: 프리플라이트 통과 후 개별 문서의 임베딩 런타임 실패 (위키는 유지, 인덱싱만 실패) (v0.4 §4.3).
    embedding_failures: list[EmbeddingFailure] = field(default_factory=list)
    #: 클라우드로 보내기 전 마스킹한 PII 집계 (파일별). `engine="local"`이면 항상 빈 목록이다 (v0.5 §4.5).
    pii_maskings: list[PiiMasking] = field(default_factory=list)
    #: 벡터 인덱싱을 건너뛴 **사유** (`--engine cloud` 전용, v0.5 §4.8). `None`이면 정상 인덱싱.
    #: 사유를 구분해 두는 이유는 해결 방법이 다르기 때문이다 — 데몬을 띄우는 것과
    #: 모델을 받는 것은 서로 다른 조치이므로 안내가 갈라져야 한다.
    indexing_skip_reason: IndexingSkipReason | None = None
    #: 스캔 대상이 상한(`ScanConfig.max_files`)을 넘어 처리를 중단했는가.
    limit_exceeded: bool = False
    #: 상한 판정에 사용된 발견 파일 수.
    discovered_count: int = 0
    #: v0.6 그래프 단계의 결과. `None`이면 그래프 단계가 돌지 않았다.
    graph: GraphOutcome | None = None

    @property
    def indexing_skipped(self) -> bool:
        """벡터 인덱싱을 건너뛰었는가 — 사유가 있으면 건너뛴 것이다 (v0.5 §4.8)."""
        return self.indexing_skip_reason is not None


@dataclass(frozen=True)
class PlanEntry:
    """pre-scan 계량의 파일 1건 (스펙 §4.2).

    파일 **내용을 읽지 않고** 경로·확장자·크기(stat)만으로 산출한다.
    """

    path: Path
    ext: str
    size_bytes: int
    #: `size_bytes`와 확장자만으로 결정적으로 근사한 예상 토큰 수.
    est_tokens: int
    #: 경로·이름·확장자·트리 깊이만으로 매긴 0~100 결정적 중요도 점수.
    importance: int


@dataclass(frozen=True)
class HardwareInfo:
    """예상 처리율 판정에 쓰는 감지 하드웨어 (스펙 §4.2).

    NVIDIA GPU 감지 성공 시 `gpu=True`와 이름 라벨, 그 외에는 `gpu=False`·`"CPU"`.
    """

    gpu: bool
    label: str


@dataclass(frozen=True)
class GateVerdict:
    """자원 게이트 판정 (순수 값) — plan_scan이 로컬로 계산한다 (v0.3 스펙 §4.2·§4.4).

    `plan`/`doctor`는 이 값을 표시하고, `scan`은 이 값으로 차단 여부를 정한다. 임계값을
    에코해 두어 리포트가 별도 조회 없이 "무엇 대비 초과인지"를 보여줄 수 있다.
    """

    #: GPU가 감지됐는가.
    gpu_ok: bool
    #: `total_est_tokens <= max_total_tokens` 인가 (False면 토큰 게이트가 scan을 차단, exit 3).
    tokens_ok: bool
    #: `size_bytes > max_file_size` 로 스킵될 예정인 파일 수(`file_too_large`).
    oversized_count: int
    #: 판정에 쓰인 유효 임계값 (에코).
    max_file_size: int
    max_total_tokens: int
    #: GPU 게이트가 **이번 실행에서 실제로 차단력을 갖는가** (v0.5 §4.7).
    #:
    #: `--engine cloud`는 로컬 GPU를 쓰지 않으므로 GPU 미탐지가 차단 사유가 되지 않는다.
    #: 판정을 여기 한 번만 담아 `_enforce_gates`와 리포트 렌더러가 같은 값을 본다 —
    #: 따로 계산하면 "차단됨"이라고 표시해 놓고 그냥 진행하는 불일치가 생긴다.
    gpu_enforced: bool = True


@dataclass(frozen=True)
class ScanPlan:
    """pre-scan 계량 결과 (순수 값) — LLM·네트워크 없이 산출한다 (스펙 §4.2).

    본격 스캔 전에 폴더를 값싸게 훑어 "무엇이 중요하고 얼마나 걸릴지"를 먼저 보여 준다.
    """

    #: 파일별 계량. 중요도 정렬은 리포트 렌더러가 담당하고 여기서는 발견 순서를 유지한다.
    entries: list[PlanEntry]
    file_count: int
    #: 요약될 파일(미지원·`file_too_large` 제외)의 예상 토큰 합계 (v0.3 §4.4).
    total_est_tokens: int
    #: `total_est_tokens ÷ 감지 하드웨어 정적 처리율`의 근사 예상 소요초.
    est_seconds: int
    hardware: HardwareInfo
    #: 자원 게이트 판정 (v0.3). plan_scan이 항상 채운다. 직접 구성 시 생략하면 미평가(None).
    gate: GateVerdict | None = None
