"""재귀 파일 스캔·지원 포맷 필터와 스캔 가드레일 (스펙 §4.2·§5, FR-004·FR-005).

폴더 인자를 재귀 순회해 지원 포맷(`.docx`/`.txt`/`.md`) 파일만 처리 대상으로 선별하고,
미지원 확장자·긴 경로(>260자)·권한 거부 파일은 사유와 함께 스킵 목록에 담는다. 파일
**내용은 열지 않고** 경로만 다룬다 (텍스트 추출은 FR-006~008 담당).

가드레일 두 종류는 성격이 다르다 (스펙 §5):

- **스킵**: 개별 파일만 제외하고 순회는 계속한다 (부분 성공 보고).
- **상한 초과**: 지원 파일 수가 `max_files`를 넘으면 처리를 아예 시작하지 않고
  (`targets`는 빈 리스트) `limit_exceeded` 신호로 알린다 — 예외를 던지지 않는다.

CLI 없이 코어 함수 호출만으로 동작한다 (스펙 §4.5).

이 모듈의 범위 밖:

- 빈 문서·텍스트 추출 실패 스킵 → FR-008
- 출력 경로 미러링(`root` 기준 상대경로 사용) → FR-012
- 상한 초과·스킵의 사용자 알림 문구와 종료 코드 → FR-016
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from corpbrain.core.config import MAX_PATH_LENGTH, SUPPORTED_EXTENSIONS
from corpbrain.core.models import SkippedFile, SkipReason

__all__ = [
    "MAX_PATH_LENGTH",
    "SUPPORTED_EXTENSIONS",
    "ScanFindings",
    "is_supported",
    "iter_files",
    "scan_folder",
]

#: 디렉터리 자체를 열지 못해 하위를 순회하지 못했음을 스킵 리포트에 남기는 설명.
DIRECTORY_DENIED_DETAIL = "디렉터리에 접근하지 못해 하위를 순회하지 않았습니다"


@dataclass(frozen=True)
class ScanFindings:
    """재귀 스캔 결과 — 처리 대상, 스킵 목록, 상한 초과 신호."""

    #: 지원 포맷 파일의 절대경로. 발견 순서를 그대로 유지한다.
    #: 상한을 초과하면 처리를 시작하지 않으므로 빈 리스트다.
    targets: list[Path] = field(default_factory=list)
    #: 스캔 단계에서 제외된 항목 (`unsupported_extension` / `path_too_long` /
    #: `permission_denied`). 상한을 초과해도 그때까지 분류된 목록을 그대로 유지한다.
    skipped: list[SkippedFile] = field(default_factory=list)
    #: 지원 파일 수가 `max_files`를 초과해 처리를 중단했는가 (스펙 §3-4).
    limit_exceeded: bool = False
    #: 상한 판정에 쓰인 지원 파일 발견 수. 상한 초과 여부와 무관하게 항상 채운다.
    discovered_count: int = 0


def is_supported(path: Path) -> bool:
    """지원 포맷(`.docx`/`.txt`/`.md`) 인지 확장자로 판정한다 (대소문자 무시).

    확장자가 없는 파일은 미지원으로 본다.
    """
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def iter_files(
    root: Path, on_error: Callable[[OSError], None] | None = None
) -> Iterator[Path]:
    """`root` 아래의 모든 파일 경로를 재귀적으로 yield 한다.

    지원 여부와 무관하게 발견한 모든 파일을 흘려보내며, 경로만 다루므로 파일을 열지
    않는다. 디렉터리 자체는 yield 하지 않는다.

    Args:
        root: 순회를 시작할 폴더. 존재하지 않으면 아무것도 yield 하지 않는다
            (입력 폴더 없음은 선행 조건 실패로 파이프라인이 다룬다).
        on_error: 디렉터리를 열지 못했을 때(권한 거부 등) 그 `OSError`를 받는 콜백.
            생략하면 해당 디렉터리를 조용히 건너뛴다. 어느 쪽이든 순회는 계속되며
            예외가 호출자에게 전파되지 않는다.

    Yields:
        `root.resolve()` 기준 절대경로. 같은 폴더 안에서는 이름 오름차순,
        하위 폴더도 이름 오름차순으로 내려가 실행마다 순서가 같다.
    """
    base = root.resolve()
    for dirpath, dirnames, filenames in os.walk(base, onerror=on_error):
        dirnames.sort()
        current = Path(dirpath)
        for name in sorted(filenames):
            yield current / name


def scan_folder(root: Path, max_files: int | None = None) -> ScanFindings:
    """`root`를 재귀 스캔해 처리 대상·스킵 목록으로 나누고 상한을 검사한다.

    스킵 판정 순서는 긴 경로 → 미지원 확장자 → 권한 거부다. 경로가 260자를 넘으면
    확장자와 무관하게 `path_too_long`으로 분류한다 (스펙 §5).

    Args:
        root: 스캔할 입력 폴더.
        max_files: 처리 대상 상한 (스펙 §4.1 `--max`, 기본값은 호출자가
            `config.DEFAULT_MAX_FILES`로 주입한다). `None`이면 상한을 검사하지 않는다.

    Returns:
        `ScanFindings`. 지원 파일 수가 `max_files`를 **초과**하면 처리를 시작하지 않고
        `targets=[]`, `limit_exceeded=True`로 알린다 (예외를 던지지 않는다).
        경로는 절대경로이므로 호출자는 `path.relative_to(root.resolve())`로 입력
        하위구조를 그대로 계산할 수 있다 (FR-012 미러링).
    """
    base = root.resolve()
    targets: list[Path] = []
    skipped: list[SkippedFile] = []

    def record_walk_error(error: OSError) -> None:
        """디렉터리 접근 실패를 스킵 1건으로 흡수한다 — 크래시하지 않는다."""
        failed = Path(error.filename) if error.filename else base
        if failed == base:
            # 입력 폴더 자체의 없음·접근 불가는 개별 스킵이 아니라 선행 조건 실패다.
            return
        skipped.append(
            SkippedFile(
                path=failed,
                reason=SkipReason.PERMISSION_DENIED,
                detail=DIRECTORY_DENIED_DETAIL,
            )
        )

    for path in iter_files(root, on_error=record_walk_error):
        reason = _skip_reason(path)
        if reason is None:
            targets.append(path)
        else:
            skipped.append(SkippedFile(path=path, reason=reason))

    discovered_count = len(targets)
    if max_files is not None and discovered_count > max_files:
        return ScanFindings(
            targets=[],
            skipped=skipped,
            limit_exceeded=True,
            discovered_count=discovered_count,
        )
    return ScanFindings(
        targets=targets, skipped=skipped, discovered_count=discovered_count
    )


def _skip_reason(path: Path) -> SkipReason | None:
    """스캔 단계에서 이 파일을 제외할 사유. 처리 대상이면 `None` (스펙 §5)."""
    if len(str(path)) > MAX_PATH_LENGTH:
        return SkipReason.PATH_TOO_LONG
    if not is_supported(path):
        return SkipReason.UNSUPPORTED_EXTENSION
    if not _is_readable(path):
        return SkipReason.PERMISSION_DENIED
    return None


def _is_readable(path: Path) -> bool:
    """읽기 권한 여부만 확인한다 — 파일을 열지 않는다 (내용 접근은 FR-006~008)."""
    try:
        return os.access(path, os.R_OK)
    except OSError:
        return False
