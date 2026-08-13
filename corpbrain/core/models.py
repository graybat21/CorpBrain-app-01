"""코어가 주고받는 데이터 구조 (순수 값).

어댑터(CLI·후속 UI)는 이 구조만 보고 결과를 렌더링한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class SkipReason(StrEnum):
    """산출물을 만들지 않고 건너뛴 사유 (스펙 §5)."""

    UNSUPPORTED_EXTENSION = "unsupported_extension"
    EMPTY_DOCUMENT = "empty_document"
    EXTRACTION_FAILED = "extraction_failed"
    PERMISSION_DENIED = "permission_denied"
    PATH_TOO_LONG = "path_too_long"
    SUMMARY_FAILED = "summary_failed"
    UP_TO_DATE = "up_to_date"


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
class ScanPlan:
    """pre-scan 계량 결과 (순수 값) — LLM·네트워크 없이 산출한다 (스펙 §4.2).

    본격 스캔 전에 폴더를 값싸게 훑어 "무엇이 중요하고 얼마나 걸릴지"를 먼저 보여 준다.
    """

    #: 파일별 계량. 중요도 정렬은 리포트 렌더러가 담당하고 여기서는 발견 순서를 유지한다.
    entries: list[PlanEntry]
    file_count: int
    total_est_tokens: int
    #: `total_est_tokens ÷ 감지 하드웨어 정적 처리율`의 근사 예상 소요초.
    est_seconds: int
    hardware: HardwareInfo
