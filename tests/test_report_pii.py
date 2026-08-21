"""PII 리포트 렌더·엔진별 모델 표시 (v0.5 스펙 §4.5·§4.1, 코드 리뷰 후속).

리포트 문자열 조립은 순수 함수라 코어만 직접 부른다 — 파일·네트워크를 건드리지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corpbrain.core.config import (
    DEFAULT_CLOUD_MODEL,
    DEFAULT_MODEL,
    ENGINE_CLOUD,
    ENGINE_LOCAL,
    ScanConfig,
)
from corpbrain.core.llm.anthropic_client import AnthropicSummarizer
from corpbrain.core.llm.summarize import OllamaSummarizer
from corpbrain.core.models import PiiMasking, ScanResult
from corpbrain.core.pii import PiiType
from corpbrain.core.report import build_summary_lines, pii_label_for


def _result_with(*maskings: PiiMasking) -> ScanResult:
    return ScanResult(out_dir=Path("wiki"), pii_maskings=list(maskings))


# --- 한국어 유형명 (§4.3 출력 언어) ------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("RRN", "주민등록번호"),
        ("PHONE", "전화번호"),
        ("EMAIL", "이메일"),
        ("BIZ_NO", "사업자등록번호"),
        ("CARD", "신용카드번호"),
        ("ACCOUNT", "계좌번호"),
        ("IP", "IP주소"),
    ],
)
def test_every_token_renders_as_a_korean_label(token: str, expected: str) -> None:
    """7종 모두 내부 토큰이 아니라 한국어 유형명으로 표시된다."""
    assert pii_label_for(token) == expected


def test_unknown_token_falls_back_to_the_raw_value() -> None:
    """알 수 없는 값이면 원시 토큰을 그대로 쓴다 — 표시가 실패를 가리지 않는다."""
    assert pii_label_for("MYSTERY") == "MYSTERY"


def test_summary_line_uses_korean_labels_not_enum_tokens() -> None:
    """요약 줄에 `RRN`·`BIZ_NO` 같은 내부 토큰이 새어 나오지 않는다."""
    result = _result_with(
        PiiMasking(path=Path("a.txt"), total=5, counts={"RRN": 4, "BIZ_NO": 1})
    )

    line = next(ln for ln in build_summary_lines(result) if "PII 마스킹" in ln)

    assert "주민등록번호 4건" in line
    assert "사업자등록번호 1건" in line
    assert "RRN" not in line
    assert "BIZ_NO" not in line


def test_summary_aggregates_across_documents_by_descending_count() -> None:
    """여러 문서의 집계를 합치고 건수 내림차순으로 낸다(결정적 출력)."""
    result = _result_with(
        PiiMasking(path=Path("a.txt"), total=2, counts={"PHONE": 1, "EMAIL": 1}),
        PiiMasking(path=Path("b.txt"), total=3, counts={"PHONE": 3}),
    )

    line = next(ln for ln in build_summary_lines(result) if "PII 마스킹" in ln)

    assert "PII 마스킹 5건 (문서 2개)" in line
    assert line.index("전화번호 4건") < line.index("이메일 1건")


def test_no_pii_line_when_nothing_was_masked() -> None:
    """로컬 엔진 등 마스킹이 없었던 실행에는 PII 줄이 아예 나오지 않는다."""
    assert not any("PII 마스킹" in ln for ln in build_summary_lines(_result_with()))


def test_labels_cover_the_whole_enum() -> None:
    """유형이 추가되면 라벨도 함께 추가되도록 7종 전체를 고정한다."""
    labels = {pii_label_for(pii_type.value) for pii_type in PiiType}

    assert len(labels) == len(list(PiiType))
    assert all(label.isascii() is False for label in labels)  # 전부 한국어


# --- 엔진별 유효 모델 (§4.1) --------------------------------------------------------


def test_effective_model_follows_the_engine() -> None:
    """실제로 호출되는 모델을 코어가 한 곳에서 판정한다."""
    local = ScanConfig(folder=Path("docs"), engine=ENGINE_LOCAL)
    cloud = ScanConfig(folder=Path("docs"), engine=ENGINE_CLOUD)

    assert local.effective_model == DEFAULT_MODEL
    assert cloud.effective_model == DEFAULT_CLOUD_MODEL


def test_effective_model_honours_explicit_cloud_model() -> None:
    """`--cloud-model`로 지정한 값이 그대로 표시 대상이 된다."""
    config = ScanConfig(
        folder=Path("docs"), engine=ENGINE_CLOUD, cloud_model="claude-sonnet-4-5"
    )

    assert config.effective_model == "claude-sonnet-4-5"


def test_cloud_run_never_reports_the_ollama_model() -> None:
    """cloud 실행이 호출되지도 않는 로컬 모델명을 표시하지 않는다 (코드 리뷰 검출)."""
    config = ScanConfig(
        folder=Path("docs"), engine=ENGINE_CLOUD, model="qwen2.5:7b-instruct"
    )

    assert config.effective_model != "qwen2.5:7b-instruct"


# --- Summarizer 프로토콜 계약 (§4.3) -------------------------------------------------


def test_both_summarizers_expose_the_masking_contract() -> None:
    """`last_mask`는 프로토콜의 일부다 — getattr로 더듬지 않아도 항상 존재한다."""
    local = OllamaSummarizer(DEFAULT_MODEL, "http://127.0.0.1:11434")
    cloud = AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test")

    assert local.last_mask is None  # 로컬은 외부로 나가지 않아 마스킹 대상이 아니다
    assert cloud.last_mask is None  # 아직 요약을 돌리지 않았다


def test_engine_names_come_from_core_constants() -> None:
    """두 백엔드 모두 엔진 이름을 코어 상수에서 가져온다(리터럴 하드코딩 금지)."""
    assert OllamaSummarizer(DEFAULT_MODEL, "http://x").engine == ENGINE_LOCAL
    assert AnthropicSummarizer(DEFAULT_CLOUD_MODEL, "sk-test").engine == ENGINE_CLOUD


# --- scan 시작 배너 (§4.1, 코드 리뷰 검출) --------------------------------------------


def _run_scan_capturing_banner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *extra: str
) -> str:
    """`scan`을 돌려 stderr 배너만 뽑는다 — 실제 파이프라인은 스텁한다."""
    from corpbrain import cli

    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.txt").write_text("본문", encoding="utf-8")
    monkeypatch.setattr(
        cli.core, "run_scan", lambda config, **_: ScanResult(out_dir=config.out_dir)
    )
    cli.main(["scan", str(folder), "--out", str(tmp_path / "wiki"), *extra])
    return ""


def test_banner_shows_the_cloud_model_when_engine_is_cloud(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """cloud 실행 배너가 호출되지도 않는 Ollama 모델명을 찍지 않는다 (코드 리뷰 검출)."""
    _run_scan_capturing_banner(
        monkeypatch, tmp_path, "--engine", "cloud", "--cloud-model", "claude-sonnet-4-5"
    )

    banner = next(
        line for line in capsys.readouterr().err.splitlines() if "스캔 시작" in line
    )
    assert "claude-sonnet-4-5" in banner
    assert DEFAULT_MODEL not in banner
    assert "엔진 cloud" in banner


def test_banner_shows_the_ollama_model_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """기본(로컬) 실행은 기존대로 Ollama 모델명을 찍는다."""
    _run_scan_capturing_banner(monkeypatch, tmp_path)

    banner = next(
        line for line in capsys.readouterr().err.splitlines() if "스캔 시작" in line
    )
    assert DEFAULT_MODEL in banner
    assert "엔진 local" in banner


# --- 파일별 PII 표시 (§4.5 "파일별로", 코드 리뷰 후속) --------------------------------


def test_detail_lines_name_each_masked_document() -> None:
    """어느 문서가 무엇을 가린 채 나갔는지 파일별로 보인다 — 감사 질문의 답이다."""
    from corpbrain.core.report import build_detail_lines

    result = _result_with(
        PiiMasking(path=Path("a.docx"), total=5, counts={"RRN": 4, "BIZ_NO": 1}),
        PiiMasking(path=Path("b.txt"), total=2, counts={"PHONE": 2}),
    )

    lines = [ln for ln in build_detail_lines(result) if "PII 마스킹" in ln]

    assert len(lines) == 2
    assert "a.docx" in lines[0] and "5건" in lines[0]
    assert "주민등록번호 4건" in lines[0]
    assert "b.txt" in lines[1] and "전화번호 2건" in lines[1]


def test_detail_lines_have_no_pii_entry_for_local_runs() -> None:
    """로컬 엔진 실행에는 파일별 PII 줄이 나오지 않는다."""
    from corpbrain.core.report import build_detail_lines

    assert not any("PII 마스킹" in ln for ln in build_detail_lines(_result_with()))


def test_detail_lines_never_leak_raw_type_tokens() -> None:
    """파일별 줄도 내부 토큰이 아니라 한국어 유형명을 쓴다."""
    from corpbrain.core.report import build_detail_lines

    result = _result_with(
        PiiMasking(path=Path("a.txt"), total=1, counts={"BIZ_NO": 1})
    )

    line = next(ln for ln in build_detail_lines(result) if "PII 마스킹" in ln)

    assert "사업자등록번호" in line
    assert "BIZ_NO" not in line
