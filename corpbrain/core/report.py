"""종료 요약 구성 — `ScanResult`를 사람이 읽는 줄 목록으로 바꾼다 (스펙 §4.1, §5).

문자열을 만들기만 하고 출력하지 않는다. 어디에 쓸지(stderr·UI 패널)는 어댑터가 정한다
(스펙 §4.5 — 코어는 로직, 어댑터는 입출력).
"""

from __future__ import annotations

from corpbrain.core.models import ScanResult, SkipReason

#: 스킵 사유의 한국어 표기 (스펙 §5의 사유 목록).
SKIP_REASON_LABELS: dict[SkipReason, str] = {
    SkipReason.UNSUPPORTED_EXTENSION: "미지원 확장자",
    SkipReason.EMPTY_DOCUMENT: "빈 문서",
    SkipReason.EXTRACTION_FAILED: "텍스트 추출 실패",
    SkipReason.PERMISSION_DENIED: "권한 거부",
    SkipReason.PATH_TOO_LONG: "경로 길이 초과(>260자)",
    SkipReason.SUMMARY_FAILED: "LLM JSON 파싱 실패",
    SkipReason.UP_TO_DATE: "최신 상태(재생성 불필요)",
}


def label_for(reason: SkipReason) -> str:
    """스킵 사유의 표시 문구. 알 수 없는 값이면 원시 값을 그대로 쓴다."""
    return SKIP_REASON_LABELS.get(reason, str(reason))


def build_detail_lines(result: ScanResult) -> list[str]:
    """파일 단위 결과 줄 — 생성물과 스킵 사유를 발견 순서대로 나열한다."""
    lines = [f"[생성] {wiki.source_path} → {wiki.output_path}" for wiki in result.generated]
    lines += [
        f"[스킵] {skip.path} — {label_for(skip.reason)}"
        + (f" ({skip.detail})" if skip.detail else "")
        for skip in result.skipped
    ]
    return lines


def build_summary_lines(result: ScanResult) -> list[str]:
    """종료 요약 — 처리 N건 / 스킵 M건(+사유별 집계) / 출력 경로 (스펙 §4.1)."""
    if result.limit_exceeded:
        return [
            f"스캔 대상이 상한을 초과했습니다: {result.discovered_count}건 발견 — 처리를 중단했습니다.",
            "--max 값을 올리거나 입력 폴더를 좁혀서 다시 실행하세요.",
        ]

    counts: dict[SkipReason, int] = {}
    for skip in result.skipped:
        counts[skip.reason] = counts.get(skip.reason, 0) + 1

    lines = [f"처리 {len(result.generated)}건 / 스킵 {len(result.skipped)}건"]
    lines += [
        f"  - {label_for(reason)}: {count}건"
        for reason, count in sorted(counts.items(), key=lambda item: item[0].value)
    ]
    lines.append(f"출력 경로: {result.out_dir}")
    return lines
