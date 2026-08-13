"""CorpBrain CLI 어댑터.

인자 파싱·로그 출력·종료 코드 매핑만 담당하고, 비즈니스 로직은 코어에 둔다 (스펙 §4.5).
플래그와 기본값은 스펙 §4.1 CLI 계약을 그대로 따르며, 기본값 자체는 코어
(`corpbrain.core.config`)가 소유한다 — CLI는 하드코딩하지 않는다.

진행상태는 코어가 방출하는 이벤트를 stderr 라이브 라인으로 렌더한다
(스펙 `corpbrain-run-status-observability.md`). 계약(`reduce`/`render_status_line`)은
코어 내부 모듈이며 어댑터가 여기서 구독한다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TextIO

from corpbrain import core
from corpbrain.core._progress import (
    ProgressEvent,
    StatusSnapshot,
    reduce,
    render_status_line,
)
from corpbrain.core.errors import PreconditionError
from corpbrain.core.report import (
    build_detail_lines,
    build_plan_report_lines,
    build_scan_banner_lines,
    build_summary_lines,
)
from corpbrain.core.scanner import (
    ScanFindings,
    enforce_limit,
    scan_folder,
    validated_root,
)

#: `--model`을 대신 지정할 수 있는 환경변수 (스펙 §4.1).
MODEL_ENV_VAR = "CORPBRAIN_MODEL"

#: 종료 코드 (스펙 §3-5, §5 — 부분 실패는 0, 선행 조건 실패는 비-0).
EXIT_OK = 0
EXIT_PRECONDITION_FAILED = 1
EXIT_LIMIT_EXCEEDED = 3


class _StderrProgress:
    """진행 이벤트를 stderr 라이브 라인으로 렌더하는 sink (스펙 §4.3).

    TTY면 `\\r`로 한 줄을 제자리 갱신하고, 비-TTY(파이프·리다이렉트)면 이벤트별 개행으로
    폴백한다. 소켓을 열지 않으므로 보안 불변식(localhost 외 연결 없음)에 영향이 없다.
    """

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._snapshot: StatusSnapshot | None = None
        self._tty = stream.isatty()

    def __call__(self, event: ProgressEvent) -> None:
        self._snapshot = reduce(self._snapshot, event)
        line = render_status_line(self._snapshot)
        if self._tty:
            self._stream.write("\r\033[K" + line)
        else:
            self._stream.write(line + "\n")
        self._stream.flush()

    def finish(self) -> None:
        """라이브 라인을 마무리한다(TTY 제자리 갱신 뒤 개행)."""
        if self._tty and self._snapshot is not None:
            self._stream.write("\n")
            self._stream.flush()


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
    scan.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="문서를 처리하지 않고 plan과 동일한 pre-scan 리포트만 stdout으로 낸다 (위키 0개).",
    )

    plan = subparsers.add_parser(
        "plan",
        help="본격 스캔 전에 폴더를 값싸게 훑어 중요도·예상 토큰·예상 소요를 리포트한다 (LLM·네트워크 0).",
    )
    plan.add_argument("folder", type=Path, help="계량할 입력 폴더.")
    plan.add_argument(
        "--max",
        dest="max_files",
        type=int,
        default=core.DEFAULT_MAX_FILES,
        metavar="N",
        help=f"scan 상한 경고 기준 (기본 {core.DEFAULT_MAX_FILES}; plan은 중단하지 않고 경고만 낸다).",
    )
    plan.add_argument(
        "--max-chars",
        dest="max_chars",
        type=int,
        default=core.DEFAULT_MAX_CHARS,
        metavar="N",
        help=f"예상 토큰 추정의 문서당 상한 글자 수 (기본 {core.DEFAULT_MAX_CHARS}).",
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
    """콘솔 엔트리 포인트. 서브커맨드(`scan`/`plan`)로 분기해 종료 코드를 반환한다."""
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _run_plan(args)
    return _run_scan(args)


def _force_utf8_output() -> None:
    """stdout/stderr를 UTF-8로 맞춘다 (스펙 §4.3 출력 언어 한국어).

    Windows 기본 콘솔 코드페이지(cp949 등)에서 한국어·기호(`…`·`—`·`·`)를 깨짐/크래시 없이
    내기 위함이다. 재구성이 불가능한 스트림(일부 캡처·리다이렉트)은 조용히 건너뛴다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            continue


def _run_scan(args: argparse.Namespace) -> int:
    """`scan` — pre-scan 배너(stderr) 후 문서를 처리한다. `--dry-run`이면 리포트만 낸다."""
    config = build_config(args)
    if args.dry_run:
        return _emit_plan_report(config)

    _log(f"스캔 시작: {config.folder} → {config.out_dir} (모델 {config.model})")
    findings = _emit_scan_banner(config)

    progress = _StderrProgress(sys.stderr)
    try:
        result = core.run_scan(config, on_event=progress, findings=findings)
    except PreconditionError as exc:
        _log(f"선행 조건 실패: {exc}")
        return EXIT_PRECONDITION_FAILED
    finally:
        progress.finish()

    for line in build_detail_lines(result):
        _log(line)
    for line in build_summary_lines(result):
        _log(line)

    return EXIT_LIMIT_EXCEEDED if result.limit_exceeded else EXIT_OK


def _run_plan(args: argparse.Namespace) -> int:
    """`plan` — pre-scan 계량 리포트를 stdout으로 낸다 (LLM·네트워크 0, 스펙 §4.3)."""
    config = core.ScanConfig(
        folder=args.folder, max_files=args.max_files, max_chars=args.max_chars
    )
    return _emit_plan_report(config)


def _emit_plan_report(config: core.ScanConfig) -> int:
    """pre-scan 리포트를 stdout으로 낸다 — 선행 조건 실패는 비-0으로 매핑한다 (스펙 §4.3·§5)."""
    try:
        plan = core.plan_scan(config)
    except PreconditionError as exc:
        _log(f"선행 조건 실패: {exc}")
        return EXIT_PRECONDITION_FAILED
    for line in build_plan_report_lines(plan, config.max_files):
        print(line)
    return EXIT_OK


def _emit_scan_banner(config: core.ScanConfig) -> ScanFindings | None:
    """scan 시작 배너를 stderr로 내고, run_scan이 재사용할 findings를 돌려준다.

    디렉터리 워크를 한 번만 하도록, 배너용 pre-scan이 훑은 결과에 `--max` 상한만 적용해
    돌려준다(본 스캔이 이를 그대로 쓴다). best-effort다 — 선행 조건 실패면 배너를 생략하고
    `None`을 돌려주며, 그러면 `run_scan`이 직접 순회하며 종료 코드를 권위 있게 판정한다.
    """
    try:
        root = validated_root(config.folder)
        findings = scan_folder(root, max_files=None)
        plan = core.plan_scan(config, findings=findings)
    except PreconditionError:
        return None
    for line in build_scan_banner_lines(plan):
        _log(line)
    return enforce_limit(findings, config.max_files)


def _log(message: str) -> None:
    """진행 로그·요약은 stdout이 아니라 stderr로 낸다 (스펙 §4.1)."""
    print(message, file=sys.stderr)
