"""CorpBrain CLI 어댑터.

인자 파싱·로그 출력·종료 코드 매핑만 담당하고, 비즈니스 로직은 코어에 둔다 (스펙 §4.5).
플래그와 기본값은 스펙 §4.1 CLI 계약을 그대로 따르며, 기본값 자체는 코어
(`corpbrain.core.config`)가 소유한다 — CLI는 하드코딩하지 않는다.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from corpbrain import core

#: `--model`을 대신 지정할 수 있는 환경변수 (스펙 §4.1).
MODEL_ENV_VAR = "CORPBRAIN_MODEL"


def build_parser() -> argparse.ArgumentParser:
    """`corpbrain` 인자 파서를 만든다 (스펙 §4.1)."""
    parser = argparse.ArgumentParser(
        prog="corpbrain",
        description="로컬 문서를 스캔해 마크다운 위키로 변환한다 (100% 로컬).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan",
        help="폴더를 재귀 스캔해 문서마다 위키 마크다운 1개를 생성한다.",
    )
    scan.add_argument(
        "folder",
        type=Path,
        help="스캔할 입력 폴더.",
    )
    scan.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        default=core.DEFAULT_OUT_DIR,
        metavar="DIR",
        help=f"위키 출력 폴더 (기본 {core.DEFAULT_OUT_DIR}).",
    )
    scan.add_argument(
        "--model",
        dest="model",
        default=None,
        metavar="NAME",
        help=(
            f"요약에 쓸 Ollama 모델 (기본 {core.DEFAULT_MODEL}). "
            f"환경변수 {MODEL_ENV_VAR}로도 지정할 수 있으며, 이 플래그가 환경변수를 이긴다."
        ),
    )
    scan.add_argument(
        "--max",
        dest="max_files",
        type=int,
        default=core.DEFAULT_MAX_FILES,
        metavar="N",
        help=f"스캔 대상 상한 (기본 {core.DEFAULT_MAX_FILES}; 초과 시 중단+알림).",
    )
    scan.add_argument(
        "--max-chars",
        dest="max_chars",
        type=int,
        default=core.DEFAULT_MAX_CHARS,
        metavar="N",
        help=f"문서당 요약 입력 상한 글자 수 (기본 {core.DEFAULT_MAX_CHARS}).",
    )
    scan.add_argument(
        "--ollama-url",
        dest="ollama_url",
        default=core.DEFAULT_OLLAMA_URL,
        metavar="URL",
        help=f"로컬 Ollama 주소 (기본 {core.DEFAULT_OLLAMA_URL}).",
    )
    scan.add_argument(
        "--force",
        action="store_true",
        help="원문 mtime과 무관하게 강제 재생성한다.",
    )
    return parser


def build_config(args: argparse.Namespace) -> core.ScanConfig:
    """파싱 결과를 코어가 받는 순수 값 `ScanConfig`로 매핑한다 (스펙 §4.5)."""
    return core.ScanConfig(
        folder=args.folder,
        out_dir=args.out_dir,
        model=_resolve_model(args.model),
        max_files=args.max_files,
        max_chars=args.max_chars,
        ollama_url=args.ollama_url,
        force=args.force,
    )


def _resolve_model(flag_value: str | None) -> str:
    """모델 우선순위를 해소한다: 명시 `--model` > 환경변수 > 코어 기본값 (스펙 §4.1)."""
    if flag_value:
        return flag_value
    env_value = os.environ.get(MODEL_ENV_VAR, "").strip()
    return env_value or core.DEFAULT_MODEL


def main(argv: list[str] | None = None) -> int:
    """콘솔 엔트리 포인트. 종료 코드를 정수로 반환한다."""
    parser = build_parser()
    args = parser.parse_args(argv)
    config = build_config(args)

    core.run_scan(config)

    # FR-016에서 채움: 종료 리포트(처리/스킵/출력 경로) 출력과 종료 코드 매핑.
    return 0
