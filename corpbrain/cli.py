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
import sqlite3
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
from corpbrain.core.config import API_KEY_ENV_VAR
from corpbrain.core.errors import PreconditionError, TokenBudgetExceededError
from corpbrain.core.graphstore import graph_path_for
from corpbrain.core.report import (
    build_detail_lines,
    build_doctor_lines,
    build_graph_central_lines,
    build_graph_neighbors_lines,
    build_graph_stats_lines,
    build_plan_report_lines,
    build_scan_banner_lines,
    build_search_lines,
    build_summary_lines,
)
from corpbrain.core.rerun import read_source_path
from corpbrain.core.scanner import (
    ScanFindings,
    resolve_excluded_out_dir,
    scan_folder,
    validated_root,
)

#: `--model`을 대신 지정할 수 있는 환경변수 (스펙 §4.1).
MODEL_ENV_VAR = "CORPBRAIN_MODEL"
#: `--embed-model`을 대신 지정할 수 있는 환경변수 (v0.4 스펙 §4.1).
EMBED_MODEL_ENV_VAR = "CORPBRAIN_EMBED_MODEL"

#: `--max-file-size`는 MB 단위 입력이며 코어는 바이트로 저장한다 (v0.3 스펙 §4.1·§4.4).
BYTES_PER_MB = 1_000_000

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
        "--similarity-threshold",
        dest="similarity_threshold",
        type=float,
        default=core.DEFAULT_SIMILARITY_THRESHOLD,
        help=(
            "지식그래프의 유사도 엣지를 만드는 코사인 하한 "
            f"(기본 {core.DEFAULT_SIMILARITY_THRESHOLD}, 이 값 이상이면 연결)."
        ),
    )
    scan.add_argument(
        "--related-top-k",
        dest="related_top_k",
        type=int,
        default=core.DEFAULT_RELATED_TOP_K,
        help=f"위키 「관련 문서」 섹션에 넣을 최대 항목 수 (기본 {core.DEFAULT_RELATED_TOP_K}).",
    )
    scan.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="문서를 처리하지 않고 plan과 동일한 pre-scan 리포트만 stdout으로 낸다 (위키 0개).",
    )
    scan.add_argument(
        "--force-gates",
        dest="force_gates",
        action="store_true",
        help="차단 게이트(GPU·토큰)를 무시하고 강행한다 (file_too_large 스킵에는 영향 없음).",
    )
    scan.add_argument(
        "--max-file-size",
        dest="max_file_size_mb",
        type=int,
        default=core.DEFAULT_MAX_FILE_SIZE // BYTES_PER_MB,
        metavar="MB",
        help=(
            f"개별 파일 크기 상한(MB); 초과 파일은 file_too_large로 스킵한다 "
            f"(기본 {core.DEFAULT_MAX_FILE_SIZE // BYTES_PER_MB})."
        ),
    )
    scan.add_argument(
        "--max-total-tokens",
        dest="max_total_tokens",
        type=int,
        default=core.DEFAULT_MAX_TOTAL_TOKENS,
        metavar="N",
        help=(
            f"스캔 전체 예상 토큰 예산; 초과 시 차단한다 "
            f"(기본 {core.DEFAULT_MAX_TOTAL_TOKENS})."
        ),
    )
    scan.add_argument(
        "--embed-model",
        dest="embed_model",
        default=None,
        metavar="NAME",
        help=(
            f"인덱싱에 쓸 Ollama 임베딩 모델 (기본 {core.DEFAULT_EMBED_MODEL}). "
            f"환경변수 {EMBED_MODEL_ENV_VAR}로도 지정할 수 있다. "
            f"scan은 항상 인덱싱까지 수행하며 이 모델이 없으면 exit 1로 종료한다."
        ),
    )
    scan.add_argument(
        "--engine",
        dest="engine",
        choices=core.ENGINES,
        default=core.ENGINE_LOCAL,
        help=(
            f"요약 엔진 (기본 {core.ENGINE_LOCAL}). "
            f"{core.ENGINE_CLOUD}는 `corpbrain consent cloud --grant` 동의와 "
            f"{API_KEY_ENV_VAR} 환경변수가 모두 있어야 한다. 임베딩은 언제나 로컬이다."
        ),
    )
    scan.add_argument(
        "--cloud-model",
        dest="cloud_model",
        default=core.DEFAULT_CLOUD_MODEL,
        metavar="NAME",
        help=(
            f"--engine {core.ENGINE_CLOUD}일 때 쓸 Anthropic 모델 "
            f"(기본 {core.DEFAULT_CLOUD_MODEL})."
        ),
    )

    consent = subparsers.add_parser(
        "consent",
        help="클라우드 엔진 사용 동의를 기록·철회한다 (로컬 설정 파일에 저장).",
    )
    consent.add_argument(
        "provider",
        choices=["cloud"],
        help="동의 대상. 현재는 cloud(Anthropic API)뿐이다.",
    )
    consent_action = consent.add_mutually_exclusive_group(required=True)
    consent_action.add_argument(
        "--grant",
        action="store_true",
        help="클라우드 엔진 사용에 동의하고 그 사실을 로컬 설정 파일에 기록한다.",
    )
    consent_action.add_argument(
        "--revoke",
        action="store_true",
        help="기록된 동의를 철회한다. 이후 --engine cloud 는 다시 차단된다.",
    )

    search = subparsers.add_parser(
        "search",
        help="이미 생성된 위키 인덱스에서 자연어 쿼리와 유사한 문서를 찾는다.",
    )
    search.add_argument("query", help="검색할 자연어 쿼리.")
    search.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        default=core.DEFAULT_OUT_DIR,
        metavar="DIR",
        help=f"scan이 만든 위키·인덱스 폴더 (기본 {core.DEFAULT_OUT_DIR}).",
    )
    search.add_argument(
        "--top-k",
        dest="top_k",
        type=int,
        default=5,
        metavar="N",
        help="반환할 최대 결과 수 (기본 5).",
    )
    search.add_argument(
        "--ollama-url",
        dest="ollama_url",
        default=core.DEFAULT_OLLAMA_URL,
        metavar="URL",
        help=f"로컬 Ollama 주소 (기본 {core.DEFAULT_OLLAMA_URL}).",
    )
    # v0.7: 하이브리드가 기본 동작이고, 되돌리는 플래그를 두어 하위 호환을 확보한다 (§4.4).
    # 플래그 이름에 «hybrid»를 쓰지 않는다 — 그 단어는 업계에서 BM25 결합을 뜻한다 (§2).
    search.add_argument(
        "--no-graph",
        dest="no_graph",
        action="store_true",
        help="그래프 확산 없이 코사인 단독으로 검색한다 (v0.4 동작).",
    )
    search.add_argument(
        "--graph-decay",
        dest="graph_decay",
        type=float,
        default=core.DEFAULT_GRAPH_DECAY,
        metavar="FLOAT",
        help=(
            f"그래프 확산 감쇠 계수 α — 0 과 1 사이 (기본 {core.DEFAULT_GRAPH_DECAY}). "
            "기본값에서는 확산이 순위를 바꾸지 않는다 — docs/USAGE.md §6.3 참고."
        ),
    )
    search.add_argument(
        "--expand-edges",
        dest="expand_edges",
        default=None,
        metavar="LIST",
        help=(
            "확산에 쓸 엣지 종류를 쉼표로 나열한다 "
            f"(기본 {','.join(sorted(str(e) for e in core.DEFAULT_EXPAND_EDGES))}; "
            f"쓸 수 있는 값 {','.join(str(e) for e in core.EdgeType)})."
        ),
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
    plan.add_argument(
        "--max-file-size",
        dest="max_file_size_mb",
        type=int,
        default=core.DEFAULT_MAX_FILE_SIZE // BYTES_PER_MB,
        metavar="MB",
        help=(
            f"게이트 판정 표시용 개별 파일 크기 상한(MB) "
            f"(기본 {core.DEFAULT_MAX_FILE_SIZE // BYTES_PER_MB}). plan은 차단하지 않는다."
        ),
    )
    plan.add_argument(
        "--max-total-tokens",
        dest="max_total_tokens",
        type=int,
        default=core.DEFAULT_MAX_TOTAL_TOKENS,
        metavar="N",
        help=(
            f"게이트 판정 표시용 토큰 예산 (기본 {core.DEFAULT_MAX_TOTAL_TOKENS}). "
            f"plan은 차단하지 않는다."
        ),
    )

    graph = subparsers.add_parser(
        "graph",
        help="지식그래프를 조회한다 (v0.6 스펙 §4.7).",
        description=(
            "scan이 만들어 둔 지식그래프를 읽기만 한다. 조회 시점에 엣지를 다시 계산하지 "
            "않으므로 출력이 그래프 DB·위키와 항상 같은 값을 가리킨다. 임계치를 바꿔 보려면 "
            "`corpbrain scan --similarity-threshold ...` 를 다시 실행한다."
        ),
    )
    graph.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        default=core.DEFAULT_OUT_DIR,
        help=f"위키·그래프 DB 위치 (기본 {core.DEFAULT_OUT_DIR}).",
    )
    view = graph.add_mutually_exclusive_group(required=True)
    view.add_argument(
        "--stats", action="store_true", help="노드·엣지 종류별 개수를 낸다."
    )
    view.add_argument(
        "--neighbors",
        metavar="경로",
        help=(
            "해당 문서에 닿는 4종 엣지를 낸다. --out 기준 위키 상대경로"
            "(개발/설계.md.md)를 우선 찾고, 없으면 원문 상대경로(개발/설계.md)로 다시 "
            "시도한다. 절대경로도 받는다."
        ),
    )
    view.add_argument(
        "--central", action="store_true", help="연결 차수 내림차순 문서 목록을 낸다."
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="환경 준비 상태(Ollama 설치/구동/모델·GPU·게이트 임계)를 점검한다.",
    )
    doctor.add_argument(
        "--model",
        dest="model",
        default=None,
        metavar="NAME",
        help=(
            f"점검할 대상 모델 (기본 {core.DEFAULT_MODEL}). "
            f"환경변수 {MODEL_ENV_VAR}로도 지정할 수 있다."
        ),
    )
    doctor.add_argument(
        "--embed-model",
        dest="embed_model",
        default=None,
        metavar="NAME",
        help=(
            f"점검할 임베딩 모델 (기본 {core.DEFAULT_EMBED_MODEL}). "
            f"환경변수 {EMBED_MODEL_ENV_VAR}로도 지정할 수 있다."
        ),
    )
    doctor.add_argument(
        "--ollama-url",
        dest="ollama_url",
        default=core.DEFAULT_OLLAMA_URL,
        metavar="URL",
        help=f"로컬 Ollama 주소 (기본 {core.DEFAULT_OLLAMA_URL}).",
    )
    return parser


def build_config(args: argparse.Namespace) -> core.ScanConfig:
    """파싱 결과를 코어가 받는 순수 값 `ScanConfig`로 매핑한다 (스펙 §4.5)."""
    return core.ScanConfig(
        folder=args.folder,
        out_dir=args.out_dir,
        model=_resolve_model(args.model),
        embed_model=_resolve_embed_model(args.embed_model),
        max_files=args.max_files,
        max_chars=args.max_chars,
        ollama_url=args.ollama_url,
        force=args.force,
        max_file_size=args.max_file_size_mb * BYTES_PER_MB,
        max_total_tokens=args.max_total_tokens,
        force_gates=args.force_gates,
        engine=args.engine,
        cloud_model=args.cloud_model,
        similarity_threshold=args.similarity_threshold,
        related_top_k=args.related_top_k,
    )


def _resolve_model(flag_value: str | None) -> str:
    """모델 우선순위를 해소한다: 명시 `--model` > 환경변수 > 코어 기본값 (스펙 §4.1)."""
    if flag_value:
        return flag_value
    env_value = os.environ.get(MODEL_ENV_VAR, "").strip()
    return env_value or core.DEFAULT_MODEL


def _resolve_embed_model(flag_value: str | None) -> str:
    """임베딩 모델 우선순위를 해소한다: 명시 `--embed-model` > 환경변수 > 코어 기본값 (v0.4 §4.1)."""
    if flag_value:
        return flag_value
    env_value = os.environ.get(EMBED_MODEL_ENV_VAR, "").strip()
    return env_value or core.DEFAULT_EMBED_MODEL


def main(argv: list[str] | None = None) -> int:
    """콘솔 엔트리 포인트. 서브커맨드(`scan`/`plan`)로 분기해 종료 코드를 반환한다."""
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _run_plan(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "search":
        return _run_search(args)
    if args.command == "consent":
        return _run_consent(args)
    if args.command == "graph":
        return _run_graph(args)
    return _run_scan(args)


def _run_consent(args: argparse.Namespace) -> int:
    """`consent cloud --grant|--revoke` — 클라우드 사용 동의를 기록·철회한다 (v0.5 §4.1).

    동의는 로컬 설정 파일에만 남고 API 키는 저장하지 않는다. 쓰기 실패는 코어가
    `PreconditionError` 하위로 올리므로 기존 exit 1 매핑을 그대로 쓴다.
    """
    try:
        if args.grant:
            core.grant_cloud_consent()
            print(f"cloud 엔진(Anthropic API) 사용에 동의했습니다 — {core.consent_path()}")
            print("- 문서 내용이 외부(Anthropic)로 전송됩니다 (PII 7종은 자동 마스킹).")
            print(f"- API 키는 {API_KEY_ENV_VAR} 환경변수로 지정하세요 (파일에 저장되지 않습니다).")
        else:
            core.revoke_cloud_consent()
            print(f"cloud 엔진 사용 동의를 철회했습니다 — {core.consent_path()}")
    except PreconditionError as exc:
        _log(f"선행 조건 실패: {exc}")
        return EXIT_PRECONDITION_FAILED
    return EXIT_OK


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

    _log(
        f"스캔 시작: {config.folder} → {config.out_dir} "
        f"(엔진 {config.engine} · 모델 {config.effective_model})"
    )
    if resolve_excluded_out_dir(config.folder.resolve(), config.out_dir) is not None:
        _log(f"안내: 출력 폴더가 스캔 대상 폴더 안에 있어 자동으로 제외합니다 — {config.out_dir}")
    banner = _emit_scan_banner(config)
    findings, plan = banner if banner is not None else (None, None)

    progress = _StderrProgress(sys.stderr)
    try:
        result = core.run_scan(config, on_event=progress, findings=findings, plan=plan)
    except TokenBudgetExceededError as exc:
        _log(f"자원 게이트 차단: {exc}")
        return EXIT_LIMIT_EXCEEDED
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
        folder=args.folder,
        max_files=args.max_files,
        max_chars=args.max_chars,
        max_file_size=args.max_file_size_mb * BYTES_PER_MB,
        max_total_tokens=args.max_total_tokens,
    )
    return _emit_plan_report(config)


def _run_doctor(args: argparse.Namespace) -> int:
    """`doctor` — 환경 준비 상태를 stdout 체크리스트로 낸다 (v0.3 스펙 §4.3).

    필수 조건(Ollama 설치·구동·대상 모델)이 미충족이면 비-0(1), 준비되면 0. GPU 없음은
    경고로 표시하되 종료 코드에 영향을 주지 않는다. 전 항목을 점검(fail-fast 아님)한다.
    """
    report = core.diagnose(
        model=_resolve_model(args.model),
        embed_model=_resolve_embed_model(args.embed_model),
        ollama_url=args.ollama_url,
    )
    for line in build_doctor_lines(report):
        print(line)
    return EXIT_OK if report.ready else EXIT_PRECONDITION_FAILED


def _run_search(args: argparse.Namespace) -> int:
    """`search` — 위키 인덱스·그래프에서 쿼리와 관련된 문서를 찾아 stdout에 낸다.

    인덱스 없음·쿼리 임베딩 실패·잘못된 확산 인자·그래프 DB 손상은 exit 1, 결과 0건은
    exit 0(정상 — 빈 결과도 정상 응답). 그래프 DB **부재**도 exit 0이며, 코사인 단독으로
    검색했음을 stderr에 한 줄 알린다 (v0.7 §3 항목7 · §5).

    그래프 DB 존재 확인을 어댑터가 한 번 더 하는 이유는 코어 반환 타입이 `list[SearchResult]`
    하나로 고정돼 있어(§4.5) «그래프 없이 답했다»를 실어 보낼 자리가 없기 때문이다. 읽기만
    하는 확인이라 코어의 판정을 바꾸지 않는다.
    """
    try:
        expand_edges = (
            core.DEFAULT_EXPAND_EDGES
            if args.expand_edges is None
            # 파싱 규칙은 코어가 소유한다 — CLI는 자체 파서를 두지 않고 이것을 부른다 (§4.4 · T10).
            else core.parse_expand_edges(args.expand_edges)
        )
        results = core.search_index(
            args.out_dir,
            args.query,
            top_k=args.top_k,
            ollama_url=args.ollama_url,
            graph=not args.no_graph,
            graph_decay=args.graph_decay,
            expand_edges=expand_edges,
        )
    except PreconditionError as exc:
        _log(f"선행 조건 실패: {exc}")
        return EXIT_PRECONDITION_FAILED
    if not args.no_graph and not graph_path_for(args.out_dir).exists():
        _log(
            "그래프 DB가 없어 코사인 단독으로 검색했습니다 — "
            f"`corpbrain scan <폴더> --out {args.out_dir}` 를 실행하면 그래프 확산이 켜집니다."
        )
    for line in build_search_lines(results):
        print(line)
    return EXIT_OK


def _run_graph(args: argparse.Namespace) -> int:
    """`graph` — 지식그래프를 조회해 stdout에 낸다 (v0.6 스펙 §4.7).

    `build_config()`를 쓰지 않는다 — 그 함수는 `scan` 파서에만 있는 인자를 무조건 읽는다.
    `graph`에 필요한 것은 `--out` 하나뿐이다.

    그래프 DB 부재·손상은 exit 1(`search`가 인덱스 부재를 다루는 선례). `--neighbors`가
    지목한 문서가 그래프에 없으면 exit 1 — 자유 텍스트 쿼리와 달리 존재를 전제한 식별자
    지목이므로 매칭 실패는 빈 결과가 아니라 잘못된 지목이다. 빈 그래프 조회는 exit 0.
    """
    path = graph_path_for(args.out_dir)
    if not path.exists():
        _log(
            f"선행 조건 실패: 그래프 DB가 없습니다: {path} — "
            "먼저 `corpbrain scan <폴더> --out <경로>` 를 실행하세요."
        )
        return EXIT_PRECONDITION_FAILED
    try:
        # 조회 전용으로 연다 — 파일에 아무것도 쓰지 않는다 (v0.6.1 / 스펙 §4.7).
        store = core.SqliteGraphStore(path, read_only=True)
    except PreconditionError as exc:
        _log(f"선행 조건 실패: {exc}")
        return EXIT_PRECONDITION_FAILED

    try:
        if args.stats:
            lines = build_graph_stats_lines(store.stats())
        elif args.central:
            ranking = store.degree_ranking()
            labels = _labels_for(store, [doc_id for doc_id, _ in ranking])
            lines = build_graph_central_lines(ranking, labels=labels)
        else:
            doc_id = _resolve_graph_document(args.out_dir, args.neighbors)
            if not store.nodes_of([doc_id]):
                _log(
                    f"그래프에 없는 문서입니다: {args.neighbors} — "
                    "`corpbrain graph --central` 로 문서 목록을 확인하세요."
                )
                return EXIT_PRECONDITION_FAILED
            edges = store.neighbors(doc_id)
            ids = [doc_id]
            for edge in edges:
                ids += [edge.src, edge.dst]
            lines = build_graph_neighbors_lines(doc_id, edges, labels=_labels_for(store, ids))
    except sqlite3.Error as exc:
        # 개봉은 됐지만 조회에서 깨지는 DB(손상된 페이지 등)를 raw traceback으로 흘리지
        # 않는다 — 다른 명령과 같이 선행 조건 실패로 정리한다.
        _log(
            f"선행 조건 실패: 그래프 DB를 읽지 못했습니다: {exc} — "
            f"{path} 를 지우고 다시 scan 하세요."
        )
        return EXIT_PRECONDITION_FAILED
    finally:
        store.close()

    for line in lines:
        print(line)
    return EXIT_OK


def _labels_for(store: core.GraphStore, node_ids: list[str]) -> dict[str, str]:
    """노드 id → 표시 라벨. **저장된 `nodes.label`을 그대로 읽는다** (스펙 §4.4).

    v0.6.0은 저장소 계약에 노드 조회가 없어 재료에서 라벨을 다시 계산했다. 규칙을 한쪽만
    고치면 위키 「관련 문서」와 이 출력이 같은 노드를 다르게 표시하면서도 오류 없이 통과했다.
    """
    return {node_id: node.label for node_id, node in store.nodes_of(node_ids).items()}


def _resolve_graph_document(out_dir: Path, raw: str) -> str:
    """`--neighbors` 인자를 `doc_id`(원문 절대경로)로 해석한다 (v0.6 §4.7).

    위키 상대경로를 우선 찾고, 없으면 원문 상대경로에 위키 접미사를 붙여 다시 찾는다. 둘 다
    아니면 인자를 `doc_id`로 그대로 넘겨 그래프가 판정하게 둔다(절대경로 입력).

    경로 해석은 어댑터의 몫이다 — 코어는 경로 해석 책임을 지지 않는다(코어 no-I/O 불변식).
    """
    for wiki in (out_dir / raw, out_dir / f"{raw}{core.WIKI_SUFFIX}"):
        # `out_dir` 하위일 때만 위키로 본다. `raw`가 절대경로면 `out_dir / raw`는 그 경로
        # 자체가 되는데, 그것이 front-matter를 가진 **원문**(다른 도구의 위키, 스캔 대상에
        # 섞인 CorpBrain 위키 등)이면 그 안의 `source_path`를 읽어 엉뚱한 문서로 간다.
        if wiki.is_file() and _is_within(wiki, out_dir):
            doc_id = read_source_path(wiki)
            if doc_id:
                return doc_id
    return raw


def _is_within(path: Path, root: Path) -> bool:
    """`path`가 `root` 아래인가. 심볼릭 링크·`..`를 풀어서 판정한다."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


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


def _emit_scan_banner(
    config: core.ScanConfig,
) -> tuple[ScanFindings, core.ScanPlan] | None:
    """scan 시작 배너를 stderr로 내고, run_scan이 재사용할 (findings, plan)을 돌려준다.

    디렉터리 워크와 하드웨어 감지를 한 번만 하도록, 배너용 pre-scan이 훑은 발견 집합(절단 전)과
    그 `ScanPlan`을 함께 돌려준다 — `run_scan`이 findings로 상한을 적용하고 plan으로 게이트를
    판정하므로 `plan_scan`을 두 번 돌리지 않는다. best-effort다 — 선행 조건 실패면 배너를
    생략하고 `None`을 돌려주며, 그러면 `run_scan`이 직접 순회하며 종료 코드를 권위 있게 판정한다.
    """
    try:
        root = validated_root(config.folder)
        findings = scan_folder(root, max_files=None, out_dir=config.out_dir)
        plan = core.plan_scan(config, findings=findings)
    except PreconditionError:
        return None
    for line in build_scan_banner_lines(plan):
        _log(line)
    # 상한(`--max`) 절단은 run_scan이 게이트 판정 이후에 직접 적용한다 (v0.3 §4.2).
    return findings, plan


def _log(message: str) -> None:
    """진행 로그·요약은 stdout이 아니라 stderr로 낸다 (스펙 §4.1)."""
    print(message, file=sys.stderr)
