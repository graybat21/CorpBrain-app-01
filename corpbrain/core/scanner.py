"""재귀 파일 스캔·지원 포맷 필터와 스캔 가드레일 (스펙 §4.2·§5, FR-004·FR-005).

폴더 인자를 재귀 순회해 지원 포맷 파일만 처리 대상으로 선별하고,
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
from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import SkippedFile, SkipReason

__all__ = [
    "MAX_PATH_LENGTH",
    "SUPPORTED_EXTENSIONS",
    "ScanFindings",
    "enforce_limit",
    "is_supported",
    "iter_files",
    "resolve_excluded_out_dir",
    "safe_size",
    "scan_folder",
    "validated_root",
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
    """`config.SUPPORTED_EXTENSIONS`에 있는 확장자인지 판정한다 (대소문자 무시).

    확장자가 없는 파일은 미지원으로 본다.
    """
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def iter_files(
    root: Path,
    on_error: Callable[[OSError], None] | None = None,
    *,
    exclude_dir: Path | None = None,
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
        exclude_dir: 있으면 이 절대경로 디렉터리 전체(그 하위 포함)를 방문하지 않는다 —
            `os.walk`의 `dirnames`를 직접 가지치기해 하위로 아예 내려가지 않으므로,
            그 안의 파일이 아무리 많아도 개별 스킵 분류 없이 통째로 순회에서 빠진다.
            `scan_folder`가 `--out`이 `root` 안에 중첩된 경우 그 하위 트리를 넘길 때 쓴다
            (호출자가 이미 `resolve_excluded_out_dir`로 걸러 넘긴다).

    Yields:
        `root.resolve()` 기준 절대경로. 같은 폴더 안에서는 이름 오름차순,
        하위 폴더도 이름 오름차순으로 내려가 실행마다 순서가 같다.
    """
    base = root.resolve()
    for dirpath, dirnames, filenames in os.walk(base, onerror=on_error):
        current = Path(dirpath)
        if exclude_dir is not None:
            dirnames[:] = [name for name in dirnames if (current / name) != exclude_dir]
        dirnames.sort()
        for name in sorted(filenames):
            yield current / name


def scan_folder(
    root: Path, max_files: int | None = None, *, out_dir: Path | None = None
) -> ScanFindings:
    """`root`를 재귀 스캔해 처리 대상·스킵 목록으로 나누고 상한을 검사한다.

    스킵 판정 순서는 긴 경로 → 미지원 확장자 → 권한 거부다. 경로가 260자를 넘으면
    확장자와 무관하게 `path_too_long`으로 분류한다 (스펙 §5).

    Args:
        root: 스캔할 입력 폴더.
        max_files: 처리 대상 상한 (스펙 §4.1 `--max`, 기본값은 호출자가
            `config.DEFAULT_MAX_FILES`로 주입한다). `None`이면 상한을 검사하지 않는다.
        out_dir: `--out` 위키 출력 폴더(선택). `root` 안에 중첩돼 있으면(예: `--out`이 스캔
            대상의 하위 폴더) 그 하위 트리 전체를 스캔에서 제외한다 — 그러지 않으면 직전
            실행이 만든 위키 산출물(`.md`)이 다음 실행에서 새 입력 문서로 다시 처리되어
            인덱스가 오염되고 산출물이 중첩되어 계속 불어난다.

    Returns:
        `ScanFindings`. 지원 파일 수가 `max_files`를 **초과**하면 처리를 시작하지 않고
        `targets=[]`, `limit_exceeded=True`로 알린다 (예외를 던지지 않는다).
        경로는 절대경로이므로 호출자는 `path.relative_to(root.resolve())`로 입력
        하위구조를 그대로 계산할 수 있다 (FR-012 미러링).
    """
    base = root.resolve()
    exclude_dir = resolve_excluded_out_dir(base, out_dir)
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

    for path in iter_files(root, on_error=record_walk_error, exclude_dir=exclude_dir):
        reason = _skip_reason(path)
        if reason is None:
            targets.append(path)
        else:
            skipped.append(SkippedFile(path=path, reason=reason))

    unlimited = ScanFindings(
        targets=targets, skipped=skipped, discovered_count=len(targets)
    )
    return enforce_limit(unlimited, max_files)


def resolve_excluded_out_dir(root: Path, out_dir: Path | None) -> Path | None:
    """`out_dir`가 (이미 resolve된) `root` 안에 중첩돼 있으면 그 절대경로를 돌려준다.

    `scan_folder`가 이 값을 `iter_files`에 넘겨 하위 트리 전체를 스캔에서 제외하는 데
    쓴다. `out_dir`가 `root`와 완전히 같은 경우(둘을 동일 폴더로 지정)는 여기서 다루지
    않고 `None`을 돌려준다 — 원본 문서와 위키 산출물이 뒤섞이는 별도의(더 심각한) 오용
    사례이며, 하위 트리 가지치기만으로는 안전하게 해소할 수 없다.
    """
    if out_dir is None:
        return None
    resolved = out_dir.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        return None
    return resolved


def enforce_limit(findings: ScanFindings, max_files: int | None) -> ScanFindings:
    """상한 초과면 처리 대상을 비우고 `limit_exceeded`로 표시한다 (순수 함수, 스펙 §3-4).

    `scan_folder(max_files=None)`로 한 번 훑은 결과를 어댑터가 재사용해 상한만 다르게 적용할
    수 있도록 분리했다(pre-scan 배너와 본 스캔이 워크를 공유). `max_files`가 `None`이면 그대로.
    """
    if max_files is not None and findings.discovered_count > max_files:
        return ScanFindings(
            targets=[],
            skipped=findings.skipped,
            limit_exceeded=True,
            discovered_count=findings.discovered_count,
        )
    return findings


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


def validated_root(folder: Path) -> Path:
    """입력 폴더가 접근 가능한 디렉터리인지 확인하고 정규화한다 (스펙 §5 선행 조건).

    `scan`(pipeline)과 `plan`이 "유효 입력 폴더" 판정을 한 곳에서 공유하도록 여기 둔다 —
    두 곳이 서로 다른 규칙으로 드리프트하지 않게 한다.
    """
    try:
        root = folder.resolve()
        if not root.is_dir():
            raise PreconditionError(f"입력 폴더가 없거나 디렉터리가 아닙니다: {folder}")
    except OSError as exc:
        raise PreconditionError(f"입력 폴더에 접근할 수 없습니다: {folder} ({exc})") from exc
    return root


def safe_size(path: Path) -> int:
    """파일 바이트 크기 — `os.stat` 실패(삭제·격리·연결 끊김 등) 시 0을 돌려준다.

    `stat`은 실패할 수 있으므로(스캔 통과와 크기 조회 사이의 TOCTOU 포함) 개별 파일의 stat
    실패가 전체 실행을 중단시키지 않도록 흡수한다(스펙 §5 — 부분 실패는 전체 실패가 아니다).
    """
    try:
        return path.stat().st_size
    except OSError:
        return 0
