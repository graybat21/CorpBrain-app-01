"""재귀 파일 스캔과 지원 포맷 필터 (스펙 §4.2, FR-004).

폴더 인자를 재귀 순회해 지원 포맷(`.docx`/`.txt`/`.md`) 파일만 처리 대상으로 선별하고,
그 외 확장자는 사유와 함께 스킵 목록에 담는다. 파일 **내용은 열지 않고** 경로만 다룬다
(텍스트 추출은 FR-006~008 담당).

CLI 없이 코어 함수 호출만으로 동작한다 (스펙 §4.5).

이 모듈의 범위 밖:

- 스캔 상한(기본 50) 초과 중단, 경로 길이(>260) 스킵, 권한 거부 처리 → FR-005
- 빈 문서·텍스트 추출 실패 스킵 → FR-008
- 출력 경로 미러링(`root` 기준 상대경로 사용) → FR-012
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from corpbrain.core.config import SUPPORTED_EXTENSIONS
from corpbrain.core.models import SkippedFile, SkipReason

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "ScanFindings",
    "is_supported",
    "iter_files",
    "scan_folder",
]


@dataclass(frozen=True)
class ScanFindings:
    """재귀 스캔 결과 — 처리 대상과 미지원 스킵 목록."""

    #: 지원 포맷 파일의 절대경로. 발견 순서를 그대로 유지한다.
    targets: list[Path] = field(default_factory=list)
    #: 미지원 확장자로 제외된 파일 (사유 `unsupported_extension`).
    skipped: list[SkippedFile] = field(default_factory=list)


def is_supported(path: Path) -> bool:
    """지원 포맷(`.docx`/`.txt`/`.md`) 인지 확장자로 판정한다 (대소문자 무시).

    확장자가 없는 파일은 미지원으로 본다.
    """
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def iter_files(root: Path) -> Iterator[Path]:
    """`root` 아래의 모든 파일 경로를 재귀적으로 yield 한다.

    지원 여부와 무관하게 발견한 모든 파일을 흘려보내며, 경로만 다루므로 파일을 열지
    않는다. 디렉터리 자체는 yield 하지 않는다.

    Args:
        root: 순회를 시작할 폴더. 존재하지 않으면 아무것도 yield 하지 않는다
            (입력 폴더 없음은 FR-005의 선행 조건 검사에서 다룬다).

    Yields:
        `root.resolve()` 기준 절대경로. 같은 폴더 안에서는 이름 오름차순,
        하위 폴더도 이름 오름차순으로 내려가 실행마다 순서가 같다.
    """
    base = root.resolve()
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        current = Path(dirpath)
        for name in sorted(filenames):
            yield current / name


def scan_folder(root: Path) -> ScanFindings:
    """`root`를 재귀 스캔해 지원 포맷 파일과 미지원 스킵 목록으로 나눈다.

    Args:
        root: 스캔할 입력 폴더.

    Returns:
        `targets`(지원 포맷 절대경로)와 `skipped`(사유 `unsupported_extension`)를 담은
        `ScanFindings`. 절대경로이므로 호출자는 `path.relative_to(root.resolve())`로
        입력 하위구조를 그대로 계산할 수 있다 (FR-012 미러링).
    """
    targets: list[Path] = []
    skipped: list[SkippedFile] = []
    for path in iter_files(root):
        if is_supported(path):
            targets.append(path)
        else:
            skipped.append(
                SkippedFile(path=path, reason=SkipReason.UNSUPPORTED_EXTENSION)
            )
    return ScanFindings(targets=targets, skipped=skipped)
