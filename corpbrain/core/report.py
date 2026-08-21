"""종료 요약·pre-scan 리포트 구성 — 코어 값을 사람이 읽는 줄 목록으로 바꾼다 (스펙 §4.1·§4.3·§5).

문자열을 만들기만 하고 출력하지 않는다. 어디에 쓸지(stdout·stderr·UI 패널)는 어댑터가 정한다
(스펙 §4.5 — 코어는 로직, 어댑터는 입출력).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR
from corpbrain.core.models import (
    IndexingSkipReason,
    PlanEntry,
    ScanPlan,
    ScanResult,
    SearchResult,
    SkipReason,
)
from corpbrain.core.pii import PiiType

if TYPE_CHECKING:
    from corpbrain.core.environment import DoctorReport

#: plan 리포트가 표시하는 중요도 상위 행 수 (스펙 §4.3, 튜닝 가능).
PLAN_REPORT_TOP_N = 20
#: scan 시작 배너가 표시하는 중요도 상위 파일 수 (스펙 §4.3, 튜닝 가능).
SCAN_BANNER_TOP_N = 3

#: 스킵 사유의 한국어 표기 (스펙 §5의 사유 목록).
SKIP_REASON_LABELS: dict[SkipReason, str] = {
    SkipReason.UNSUPPORTED_EXTENSION: "미지원 확장자",
    SkipReason.EMPTY_DOCUMENT: "빈 문서",
    SkipReason.EXTRACTION_FAILED: "텍스트 추출 실패",
    SkipReason.PERMISSION_DENIED: "권한 거부",
    SkipReason.PATH_TOO_LONG: "경로 길이 초과(>260자)",
    SkipReason.SUMMARY_FAILED: "LLM JSON 파싱 실패",
    SkipReason.UP_TO_DATE: "최신 상태(재생성 불필요)",
    SkipReason.FILE_TOO_LARGE: "파일 크기 초과",
    SkipReason.CLOUD_RATE_LIMITED: "클라우드 레이트리밋(429)",
    SkipReason.CLOUD_API_ERROR: "클라우드 호출 실패",
}

#: 인덱싱 생략 사유별 안내 — **해결 조치까지 함께** 낸다 (v0.5 §4.8).
#: 데몬을 띄우는 것과 모델을 받는 것은 다른 일이므로 문구가 갈라져야 한다.
INDEXING_SKIP_LABELS: dict[IndexingSkipReason, str] = {
    IndexingSkipReason.OLLAMA_UNAVAILABLE: (
        "로컬 Ollama 데몬이 응답하지 않아 벡터 인덱스를 만들지 않았습니다 "
        "(`ollama serve` 실행 후 --force 로 재스캔하면 채워집니다)."
    ),
    IndexingSkipReason.EMBED_MODEL_MISSING: (
        "임베딩 모델이 설치돼 있지 않아 벡터 인덱스를 만들지 않았습니다 "
        "(`ollama pull <embed-model>` 후 --force 로 재스캔하면 채워집니다)."
    ),
}


def label_for(reason: SkipReason) -> str:
    """스킵 사유의 표시 문구. 알 수 없는 값이면 원시 값을 그대로 쓴다."""
    return SKIP_REASON_LABELS.get(reason, str(reason))


def build_detail_lines(result: ScanResult) -> list[str]:
    """파일 단위 결과 줄 — 생성물·스킵·인덱싱 실패 사유를 발견 순서대로 나열한다."""
    lines = [f"[생성] {wiki.source_path} → {wiki.output_path}" for wiki in result.generated]
    lines += [
        f"[스킵] {skip.path} — {label_for(skip.reason)}"
        + (f" ({skip.detail})" if skip.detail else "")
        for skip in result.skipped
    ]
    lines += [
        f"[인덱싱 실패] {failure.path}"
        + (f" — {failure.detail}" if failure.detail else "")
        for failure in result.embedding_failures
    ]
    # 어느 문서가 무엇을 가린 채 외부로 나갔는지 — 감사(audit) 질문에 답하는 줄이다.
    # 스펙 §4.5가 치환 건수를 "파일별로" 표시하라고 요구한다 (로컬 엔진이면 항상 비어 있다).
    lines += [
        f"[PII 마스킹] {masking.path} — {masking.total}건"
        + (f" ({_breakdown(masking.counts)})" if masking.counts else "")
        for masking in result.pii_maskings
    ]
    return lines


def _breakdown(counts: dict[str, int]) -> str:
    """유형별 건수를 한국어 라벨로, 건수 내림차순으로 조립한다 (결정적 출력)."""
    ordered = sorted(
        ((pii_label_for(name), count) for name, count in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    return ", ".join(f"{label} {count}건" for label, count in ordered)


def build_summary_lines(result: ScanResult) -> list[str]:
    """종료 요약 — 처리 N건 / 스킵 M건(+사유별 집계) / 인덱싱 실패 K건 / 출력 경로 (스펙 §4.1, v0.4 §4.3)."""
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
    # 위키는 생성됐지만 인덱싱만 실패한 문서 — 스킵과 구분되는 별도 집계 (v0.4 §4.3).
    if result.embedding_failures:
        lines.append(f"인덱싱 실패 {len(result.embedding_failures)}건 (위키는 생성됨)")
    # 클라우드로 나가기 전 가려진 개인정보 집계 (v0.5 §4.5). 로컬 엔진이면 항상 비어 있다.
    lines.extend(_pii_summary_lines(result))
    if result.indexing_skip_reason is not None:
        # 위키는 정상이지만 `search`가 이 문서들을 찾지 못한다 — 조용히 넘어가면 안 된다.
        # 사유마다 해결 조치가 다르므로 안내도 갈라진다 (v0.5 §4.8).
        lines.append(
            f"인덱싱 생략 — {INDEXING_SKIP_LABELS[result.indexing_skip_reason]} "
            "위키는 정상 생성됐지만 `corpbrain search`로는 찾을 수 없습니다."
        )
    lines.append(f"출력 경로: {result.out_dir}")
    return lines


def pii_label_for(name: str) -> str:
    """PII 유형 토큰(`RRN` 등)을 한국어 유형명으로 바꾼다 (스펙 §4.5 표의 '유형' 열).

    출력 언어는 항상 한국어이므로(스펙 §4.3) 리포트에 내부 토큰을 그대로 노출하지 않는다.
    알 수 없는 값이면 원시 토큰을 그대로 쓴다 — 표시가 실패를 가리지 않게 한다.
    """
    try:
        return PiiType(name).label
    except ValueError:
        return name


def _pii_summary_lines(result: ScanResult) -> list[str]:
    """마스킹된 PII를 문서 수·총 건수·유형별로 요약한다 (v0.5 §4.5).

    유형은 건수 내림차순으로, 같은 건수면 한국어 유형명 순으로 낸다(결정적 출력).
    """
    if not result.pii_maskings:
        return []
    per_type: dict[str, int] = {}
    for masking in result.pii_maskings:
        for name, count in masking.counts.items():
            per_type[name] = per_type.get(name, 0) + count
    total = sum(masking.total for masking in result.pii_maskings)
    return [
        f"PII 마스킹 {total}건 (문서 {len(result.pii_maskings)}개) — {_breakdown(per_type)}",
    ]


def build_search_lines(results: list[SearchResult]) -> list[str]:
    """`search`가 stdout에 낼 결과 줄 — 점수 내림차순 제목·경로 (v0.4 스펙 §3 항목6)."""
    if not results:
        return ["일치하는 문서가 없습니다."]
    lines = [f"검색 결과 {len(results)}건"]
    lines += [
        f"  {rank}. [{result.score:.3f}] "
        # 키가 없을 때뿐 아니라 빈 문자열(제목 없는 손상·수기 편집 위키)일 때도 대체 문구를 쓴다.
        f"{result.metadata.get('title') or '(제목 없음)'} — "
        f"{result.metadata.get('source_path') or result.doc_id}"
        for rank, result in enumerate(results, start=1)
    ]
    return lines


# --- v0.2 U4: pre-scan 계량 리포트·배너 (스펙 §4.3) ------------------------------


def _ranked_entries(plan: ScanPlan) -> list[PlanEntry]:
    """중요도 내림차순 정렬 — 동점은 발견(스캔) 순서를 유지한다(안정 정렬)."""
    return sorted(plan.entries, key=lambda entry: entry.importance, reverse=True)


def _format_seconds(seconds: int) -> str:
    """예상 소요초를 사람이 읽는 근사 표기로 바꾼다."""
    if seconds < 60:
        return f"{seconds}초"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}분 {remainder}초" if remainder else f"{minutes}분"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}시간 {minutes}분"


def build_plan_report_lines(plan: ScanPlan, max_files: int) -> list[str]:
    """`plan` 서브커맨드가 stdout에 낼 사람이 읽는 리포트 (스펙 §4.3).

    중요도 내림차순 TOP N행 + "…외 M건" + 합계(파일수/총토큰/예상초) + 감지 하드웨어를 담고,
    발견 수가 `max_files`(--max)를 초과하면 경고 한 줄을 덧붙인다(스펙 §5 — plan은 중단하지
    않으므로 경고 신호일 뿐이다).
    """
    ranked = _ranked_entries(plan)
    shown = ranked[:PLAN_REPORT_TOP_N]

    lines = [f"CorpBrain pre-scan 계량 — 중요도 상위 {len(shown)}개 (근사)"]
    lines += [
        f"  [{entry.importance:3d}] {entry.path.name}  ({entry.ext}, ~{entry.est_tokens} tok)"
        for entry in shown
    ]
    remaining = plan.file_count - len(shown)
    if remaining > 0:
        lines.append(f"  …외 {remaining}건")

    lines.append("")
    lines.append(
        f"합계: {plan.file_count}개 파일 · 예상 토큰 {plan.total_est_tokens:,} · "
        f"예상 소요 약 {_format_seconds(plan.est_seconds)}"
    )
    lines.append(f"감지 하드웨어: {plan.hardware.label}")
    lines += _gate_report_lines(plan)
    if plan.file_count > max_files:
        lines.append(
            f"경고: 발견 {plan.file_count}건이 --max({max_files})를 초과합니다 — "
            f"이 폴더로 scan하면 상한 초과로 중단됩니다."
        )
    return lines


def _gate_report_lines(plan: ScanPlan) -> list[str]:
    """자원 게이트 판정을 사람이 읽는 줄로 렌더한다 (v0.3 스펙 §4.3, 표시만 — 차단 아님)."""
    gate = plan.gate
    if gate is None:
        return []
    if gate.gpu_ok:
        gpu = "OK (GPU 감지)"
    elif gate.gpu_enforced:
        gpu = "차단 (GPU 미탐지 — scan은 --force-gates 필요)"
    else:
        # 클라우드 요약은 로컬 GPU를 쓰지 않아 차단 사유가 아니다 (§4.7).
        # "차단"이라고 표시해 놓고 그냥 진행하면 사용자가 불필요한 --force-gates를 붙이게 되고,
        # 그러면 cloud에도 유지돼야 할 토큰(비용) 게이트까지 함께 꺼진다.
        gpu = "미탐지 (cloud 엔진이라 차단하지 않음)"
    tokens = (
        "OK"
        if gate.tokens_ok
        else f"차단 (예산 {gate.max_total_tokens:,} 초과 — --force-gates 또는 --max-total-tokens)"
    )
    lines = [
        "게이트:",
        f"  - GPU: {gpu}",
        f"  - 토큰: {plan.total_est_tokens:,} / 예산 {gate.max_total_tokens:,} — {tokens}",
    ]
    if gate.oversized_count > 0:
        lines.append(
            f"  - 대용량 스킵 예정: {gate.oversized_count}건 "
            f"(>{gate.max_file_size:,} bytes, file_too_large)"
        )
    return lines


def build_scan_banner_lines(plan: ScanPlan) -> list[str]:
    """`scan` 시작 시 stderr에 낼 요약 배너 — 예상 파일수·예상시간 + 중요도 TOP 3 + 게이트 (스펙 §4.3)."""
    top = _ranked_entries(plan)[:SCAN_BANNER_TOP_N]
    top_names = ", ".join(entry.path.name for entry in top) if top else "(없음)"
    lines = [
        f"pre-scan: {plan.file_count}개 파일 · 예상 소요 약 {_format_seconds(plan.est_seconds)} (근사)",
        f"중요도 TOP {len(top)}: {top_names}",
    ]
    gate = plan.gate
    if gate is not None:
        if gate.gpu_ok:
            gpu = "GPU"
        else:
            gpu = "CPU(차단)" if gate.gpu_enforced else "CPU(cloud — 차단 안 함)"
        tok = "OK" if gate.tokens_ok else "예산초과"
        summary = (
            f"게이트: {gpu} · 토큰 {plan.total_est_tokens:,}/{gate.max_total_tokens:,} {tok}"
        )
        if gate.oversized_count > 0:
            summary += f" · 대용량 {gate.oversized_count}건"
        lines.append(summary)
    return lines


def _cloud_doctor_lines(report: DoctorReport) -> list[str]:
    """클라우드 옵트인 상태 줄 — GPU와 같은 경고성 표시다 (v0.5 §4.1·§3 항목10).

    동의·API 키는 옵트인이라 없는 것이 기본 상태이므로 [실패]가 아닌 [경고]로 내고,
    `report.ready`(종료 코드)에는 영향을 주지 않는다.
    """
    if report.cloud_ready:
        return ["  [OK] Cloud(Anthropic): 사용 준비됨"]
    lines: list[str] = []
    if report.cloud_consent:
        lines.append("  [OK] Cloud 동의: 기록됨")
    else:
        lines.append(
            "  [경고] Cloud 동의: 없음 — `corpbrain consent cloud --grant` 로 동의"
        )
    if report.cloud_api_key:
        lines.append(f"  [OK] {API_KEY_ENV_VAR}: 설정됨")
    else:
        lines.append(f"  [경고] {API_KEY_ENV_VAR}: 미설정 — 환경변수로 설정 필요")
    return lines


def build_doctor_lines(report: DoctorReport) -> list[str]:
    """`doctor`가 stdout에 낼 한국어 체크리스트 — 실패 항목에 해결 명령을 함께 낸다 (v0.4 §4.3).

    순서 = Ollama 설치 → 구동 → 대상 모델 → 임베딩 모델 → GPU → 게이트 임계값(정보) → 종합.
    GPU 없음은 경고일 뿐 종합 판정(`ready`)에 영향을 주지 않는다. 안내 문자열·URL은 평문 출력이다.
    """
    lines = ["CorpBrain doctor — 환경 점검"]

    if report.installed:
        lines.append("  [OK] Ollama 설치됨")
    else:
        lines.append("  [실패] Ollama 미설치 — https://ollama.com 에서 설치")

    if report.running:
        lines.append("  [OK] Ollama 데몬 구동 중")
    else:
        lines.append("  [실패] Ollama 데몬 미구동 — `ollama serve` 실행")

    if report.model_present:
        lines.append(f"  [OK] 모델 설치됨: {report.model}")
    else:
        lines.append(f"  [실패] 모델 없음: {report.model} — `ollama pull {report.model}`")

    if report.embed_model_present:
        lines.append(f"  [OK] 임베딩 모델 설치됨: {report.embed_model}")
    else:
        lines.append(
            f"  [실패] 임베딩 모델 없음: {report.embed_model} — "
            f"`ollama pull {report.embed_model}`"
        )

    if report.hardware.gpu:
        lines.append(f"  [OK] {report.hardware.label}")
    else:
        lines.append(f"  [경고] {report.hardware.label} — scan은 GPU 없이 --force-gates 필요")

    lines.extend(_cloud_doctor_lines(report))

    lines.append(
        f"  [정보] 게이트 임계: 파일 {report.max_file_size:,} bytes · "
        f"총토큰 {report.max_total_tokens:,}"
    )

    if report.ready:
        lines.append("준비 완료 — scan을 실행할 수 있습니다.")
    else:
        lines.append("준비 미완료 — 위 [실패] 항목을 해결한 뒤 다시 확인하세요.")
    return lines
