"""pre-scan 계량 — LLM·네트워크 없이 폴더를 값싸게 훑어 중요도·예상치를 산출한다 (스펙 §4.2).

본격 `scan` 전에 "무엇이 중요하고 얼마나 걸릴지"를 먼저 보여 주기 위한 순수 계량이다.

**I/O 경계 (스펙 §4.2 · 완료의 정의 3·5):** 파일 메타데이터(`os.stat` 크기)까지만 읽는다.
파일 콘텐츠 open·read, 네트워크 소켓, 영속 상태(캐시·rate 파일) 읽기는 하지 않는다. 하드웨어
감지도 로컬 `nvidia-smi` subprocess만 쓰며 Ollama에 질의하지 않는다(localhost 소켓도 0).

상수·공식은 스펙 §4.2 값을 그대로 쓴다 — "근사"이며 튜닝 가능한 상수다. 파일 목록은
`scanner.scan_folder`를 재사용하고, 리포트 렌더·CLI 출력은 어댑터/렌더러 계층이 담당한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.models import HardwareInfo, PlanEntry, ScanPlan
from corpbrain.core.scanner import scan_folder

__all__ = ["detect_hardware", "plan_scan"]

# --- 중요도 휴리스틱 (스펙 §4.2 · 결정적, 파일 내용 무읽기) ------------------------
#: 확장자 기본 점수. plan 대상은 지원 4종뿐이다.
BASE_EXT_SCORE: dict[str, int] = {".pdf": 40, ".docx": 40, ".md": 30, ".txt": 25}
#: 신호 키워드 (부분일치·소문자). 매칭된 서로 다른 개수 × 8, 최대 30 가산.
SIGNAL_KEYWORDS: tuple[str, ...] = (
    "계약", "보고서", "report", "spec", "제안", "계획", "최종", "final", "정책",
)
#: 잡음 키워드 (부분일치·소문자). 매칭된 서로 다른 개수 × 10, 최대 30 감산.
NOISE_KEYWORDS: tuple[str, ...] = (
    "temp", "tmp", "backup", "사본", "copy", "old", "임시", "draft", "archive", "~$",
)
SIGNAL_WEIGHT = 8
NOISE_WEIGHT = 10
BONUS_CAP = 30

# --- 예상 토큰 (스펙 §4.2 · size_bytes와 확장자만, 내용 무읽기, 근사) --------------
#: 확장자별 bytes→chars 근사 비율 (한글 편중 UTF-8·zip 압축/마크업 오버헤드 가정).
CHARS_PER_BYTE: dict[str, float] = {".txt": 0.5, ".md": 0.5, ".docx": 0.06, ".pdf": 0.12}
#: chars→tokens 근사 비율 (한/영 혼합).
CHARS_PER_TOKEN = 2.5

# --- 예상 시간: 정적 처리율 tok/s (스펙 §4.2 · 근사, 실측 보정은 v0.3 비목표) -------
GPU_RATE = 50
CPU_RATE = 10

#: nvidia-smi 호출의 짧은 타임아웃(초). 로컬 프로세스만 — 소켓·Ollama 미질의.
NVIDIA_SMI_TIMEOUT = 2.0


def plan_scan(config: ScanConfig) -> ScanPlan:
    """`config.folder`를 훑어 파일별 계량과 합계를 담은 `ScanPlan`을 돌려준다 (순수 값).

    `scan_folder(max_files=None)`로 **전 파일**을 계량한다 — `--max`는 처리 중단이 아니라
    리포트 경고 신호로만 쓰이므로(스펙 §5) 여기서 절단하지 않는다. 파일 콘텐츠는 열지 않고
    `os.stat` 크기와 경로·확장자만 사용한다.

    입력 폴더가 없거나 접근 불가면 `scan`과 동일하게 `PreconditionError`를 올린다(스펙 §5).
    """
    root = _validated_root(config.folder)
    findings = scan_folder(root, max_files=None)
    hardware = detect_hardware()

    entries: list[PlanEntry] = []
    for path in findings.targets:
        ext = path.suffix.lower()
        size_bytes = path.stat().st_size
        rel_path = path.relative_to(root)
        entries.append(
            PlanEntry(
                path=path,
                ext=ext,
                size_bytes=size_bytes,
                est_tokens=_estimate_tokens(size_bytes, ext, config.max_chars),
                importance=_importance(rel_path, ext),
            )
        )

    total_est_tokens = sum(entry.est_tokens for entry in entries)
    rate = GPU_RATE if hardware.gpu else CPU_RATE
    return ScanPlan(
        entries=entries,
        file_count=len(entries),
        total_est_tokens=total_est_tokens,
        est_seconds=round(total_est_tokens / rate),
        hardware=hardware,
    )


def _validated_root(folder: Path) -> Path:
    """입력 폴더가 접근 가능한 디렉터리인지 확인하고 정규화한다 (scan과 동일한 선행 조건, 스펙 §5)."""
    try:
        root = folder.resolve()
        if not root.is_dir():
            raise PreconditionError(f"입력 폴더가 없거나 디렉터리가 아닙니다: {folder}")
    except OSError as exc:
        raise PreconditionError(f"입력 폴더에 접근할 수 없습니다: {folder} ({exc})") from exc
    return root


def _importance(rel_path: Path, ext: str) -> int:
    """경로·이름·확장자·트리 깊이만으로 0~100 결정적 점수를 매긴다 (스펙 §4.2, 내용 무읽기)."""
    haystack = str(rel_path).lower()  # 루트 기준 상대경로: 폴더명 + 파일명·확장자
    depth = len(rel_path.parts) - 1  # 루트 직속 = 0

    base = BASE_EXT_SCORE.get(ext, 0)
    depth_adj = max(-20, 15 - 5 * depth)
    signal_bonus = min(BONUS_CAP, SIGNAL_WEIGHT * _match_count(haystack, SIGNAL_KEYWORDS))
    noise_penalty = min(BONUS_CAP, NOISE_WEIGHT * _match_count(haystack, NOISE_KEYWORDS))

    score = round(base + depth_adj + signal_bonus - noise_penalty)
    return max(0, min(100, score))


def _match_count(haystack: str, keywords: tuple[str, ...]) -> int:
    """`haystack`에 부분일치하는 서로 다른 키워드 수."""
    return sum(1 for keyword in keywords if keyword in haystack)


def _estimate_tokens(size_bytes: int, ext: str, max_chars: int) -> int:
    """`size_bytes`와 확장자만으로 예상 토큰을 결정적 근사한다 (스펙 §4.2, 내용 무읽기)."""
    chars_est = min(max_chars, round(size_bytes * CHARS_PER_BYTE.get(ext, 0.5)))
    return round(chars_est / CHARS_PER_TOKEN)


def detect_hardware() -> HardwareInfo:
    """로컬 `nvidia-smi` subprocess로만 GPU를 판정한다 — 소켓·네트워크 0, Ollama 미질의 (스펙 §4.2).

    성공 시 nvidia-smi가 보고한 GPU 이름 1줄을 라벨에 담는다. 부재·실패·타임아웃, 그리고
    NVIDIA 외 GPU(AMD/Apple)는 CPU로 근사한다. 새 런타임 의존성을 추가하지 않는다.
    """
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=NVIDIA_SMI_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return HardwareInfo(gpu=False, label="CPU")

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return HardwareInfo(gpu=False, label="CPU")
    return HardwareInfo(gpu=True, label=f"GPU: {lines[0]}")
