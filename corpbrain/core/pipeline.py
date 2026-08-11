"""코어 공개 진입점 — 스캔→추출→요약→렌더→출력 조립 (스펙 §4.5, §5).

CLI 없이 `run_scan(config)` 호출만으로 end-to-end 실행된다.
개별 파일의 실패는 예외로 올리지 않고 `ScanResult.skipped`에 사유와 함께 담아
나머지 파일 처리를 계속한다(부분 성공). 선행 조건 실패(입력 폴더 없음, Ollama 미탐지)만
`PreconditionError`로 올려 어댑터가 비-0 종료로 매핑한다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from corpbrain.core.config import ScanConfig
from corpbrain.core.errors import PreconditionError
from corpbrain.core.extract import prepare_summary_input
from corpbrain.core.llm.ollama_client import detect
from corpbrain.core.llm.summarize import LLMParseError, summarize
from corpbrain.core.models import GeneratedWiki, ScanResult, SkippedFile, SkipReason
from corpbrain.core.output import output_path_for, write_wiki
from corpbrain.core.render import render_markdown
from corpbrain.core.rerun import should_regenerate
from corpbrain.core.scanner import scan_folder


def run_scan(config: ScanConfig) -> ScanResult:
    """폴더를 스캔해 문서마다 위키 마크다운 1개를 생성하고 결과를 반환한다.

    Args:
        config: 실행 파라미터 (순수 값). 어댑터 타입에 의존하지 않는다.

    Returns:
        생성·스킵 목록을 담은 `ScanResult`. 개별 파일 실패는 스킵으로 담고 예외로 올리지 않는다.

    Raises:
        PreconditionError: 입력 폴더 없음/접근 불가, Ollama 미탐지 등 선행 조건 실패.
    """
    root = _validated_root(config.folder)
    detect(config.ollama_url)

    findings = scan_folder(root, max_files=config.max_files)
    result = ScanResult(
        out_dir=config.out_dir,
        skipped=list(findings.skipped),
        limit_exceeded=findings.limit_exceeded,
        discovered_count=findings.discovered_count,
    )
    if findings.limit_exceeded:
        return result

    for source_path in findings.targets:
        _process_one(source_path, root, config, result)
    return result


def _process_one(
    source_path: Path, root: Path, config: ScanConfig, result: ScanResult
) -> None:
    """파일 1개를 처리한다 — 어떤 실패도 이 함수 밖으로 새어 나가지 않는다."""
    out_path = output_path_for(source_path, root, config.out_dir)

    if not should_regenerate(source_path, out_path, config.force):
        result.skipped.append(SkippedFile(path=source_path, reason=SkipReason.UP_TO_DATE))
        return

    prepared = prepare_summary_input(source_path, config.max_chars)
    if prepared.skipped is not None or prepared.text is None:
        result.skipped.append(
            prepared.skipped
            or SkippedFile(path=source_path, reason=SkipReason.EXTRACTION_FAILED)
        )
        return

    try:
        summary = summarize(prepared.text, config.model, config.ollama_url)
    except LLMParseError as exc:
        result.skipped.append(
            SkippedFile(
                path=source_path,
                reason=SkipReason.SUMMARY_FAILED,
                detail=str(exc),
            )
        )
        return

    try:
        source_bytes = source_path.stat().st_size
    except OSError:
        source_bytes = 0

    markdown = render_markdown(
        summary,
        source_path=str(source_path),
        model=config.model,
        source_bytes=source_bytes,
        generated_at=datetime.now().astimezone().isoformat(),
    )

    try:
        write_wiki(markdown, out_path)
    except OSError as exc:
        reason = (
            SkipReason.PERMISSION_DENIED
            if isinstance(exc, PermissionError)
            else SkipReason.EXTRACTION_FAILED
        )
        result.skipped.append(
            SkippedFile(path=source_path, reason=reason, detail=f"위키 기록 실패: {exc}")
        )
        return

    result.generated.append(GeneratedWiki(source_path=source_path, output_path=out_path))


def _validated_root(folder: Path) -> Path:
    """입력 폴더가 실제로 접근 가능한 디렉터리인지 확인하고 정규화한다."""
    try:
        root = folder.resolve()
        if not root.is_dir():
            raise PreconditionError(f"입력 폴더가 없거나 디렉터리가 아닙니다: {folder}")
    except OSError as exc:
        raise PreconditionError(f"입력 폴더에 접근할 수 없습니다: {folder} ({exc})") from exc
    return root
