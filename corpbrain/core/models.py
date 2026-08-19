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


@dataclass
class ScanResult:
    """파이프라인 1회 실행 결과 — 부분 성공을 그대로 담는다 (스펙 §5)."""

    out_dir: Path
    generated: list[GeneratedWiki] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    #: 프리플라이트 통과 후 개별 문서의 임베딩 런타임 실패 (위키는 유지, 인덱싱만 실패) (v0.4 §4.3).
    embedding_failures: list[EmbeddingFailure] = field(default_factory=list)
    #: 스캔 대상이 상한(`ScanConfig.max_files`)을 넘어 처리를 중단했는가.
    limit_exceeded: bool = False
    #: 상한 판정에 사용된 발견 파일 수.
    discovered_count: int = 0


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

    #: GPU가 감지됐는가 (False면 GPU 게이트가 scan을 차단한다 — `--force-gates`로만 강행).
    gpu_ok: bool
    #: `total_est_tokens <= max_total_tokens` 인가 (False면 토큰 게이트가 scan을 차단, exit 3).
    tokens_ok: bool
    #: `size_bytes > max_file_size` 로 스킵될 예정인 파일 수(`file_too_large`).
    oversized_count: int
    #: 판정에 쓰인 유효 임계값 (에코).
    max_file_size: int
    max_total_tokens: int


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
