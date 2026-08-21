"""PII 마스킹 단위테스트 (v0.5 스펙 §4.5, 완료의 정의 6번의 단위테스트 절반).

순수 함수만 검증한다 — 파일·네트워크·전역 상태를 건드리지 않는다.
스펙의 "형태 기반 느슨한 매칭(체크섬 미검증)" 원칙을 그대로 고정한다 — 과탐은 감수하고
누락을 최소화하는 방향이므로, 과탐 케이스도 "마스킹된다"로 명시적으로 못박는다.
"""

from __future__ import annotations

import pytest

from corpbrain.core.pii import PII_PATTERNS, MaskingResult, PiiType, mask_pii

#: (원본 PII 문자열, 기대 유형) — 스펙 §4.5 표 7종 각각의 대표 양성 케이스.
POSITIVE_CASES: list[tuple[str, PiiType]] = [
    # 주민등록번호 — 하이픈 유무 모두 허용.
    ("900101-1234567", PiiType.RRN),
    ("9001011234567", PiiType.RRN),
    # 전화번호 — 휴대전화·일반전화 두 패턴을 OR로 결합.
    ("010-1234-5678", PiiType.PHONE),
    ("01012345678", PiiType.PHONE),
    ("02-123-4567", PiiType.PHONE),
    ("031-123-4567", PiiType.PHONE),
    # 이메일.
    ("hong.gildong@example.com", PiiType.EMAIL),
    ("user+tag@sub-domain.co.kr", PiiType.EMAIL),
    # 사업자등록번호 — 하이픈 포함 3-2-5 표기만.
    ("123-45-67890", PiiType.BIZ_NO),
    # 신용카드번호 — 16자리 4그룹(하이픈·공백·구분자 없음).
    ("1234-5678-9012-3456", PiiType.CARD),
    ("1234 5678 9012 3456", PiiType.CARD),
    ("1234567890123456", PiiType.CARD),
    # 계좌번호 — 하이픈 2~3개로 구분된 숫자 그룹(휴리스틱).
    ("110-234-567890", PiiType.ACCOUNT),
    ("301-0000-1234-56", PiiType.ACCOUNT),
    # IP 주소 — IPv4 형태만.
    ("192.168.0.10", PiiType.IP),
]

MIXED_TEXT = """계약 담당자 정보
주민등록번호: 900101-1234567
연락처: 010-1234-5678 (사무실 02-123-4567)
이메일: hong.gildong@example.com
사업자등록번호: 123-45-67890
카드: 1234-5678-9012-3456
계좌: 110-234-567890
서버 IP: 192.168.0.10
"""

MIXED_RAW_PII: list[str] = [
    "900101-1234567",
    "010-1234-5678",
    "02-123-4567",
    "hong.gildong@example.com",
    "123-45-67890",
    "1234-5678-9012-3456",
    "110-234-567890",
    "192.168.0.10",
]


# --- 7종 각각의 양성 케이스 -------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), POSITIVE_CASES, ids=[c[0] for c in POSITIVE_CASES])
def test_each_pii_type_is_masked(raw: str, expected: PiiType) -> None:
    """대표 양성 케이스가 기대한 유형의 플레이스홀더로 치환된다."""
    result = mask_pii(f"담당자 정보 {raw} 끝.")

    assert expected.placeholder in result.text
    assert result.counts == {expected: 1}


@pytest.mark.parametrize(("raw", "expected"), POSITIVE_CASES, ids=[c[0] for c in POSITIVE_CASES])
def test_original_pii_string_never_survives_masking(raw: str, expected: PiiType) -> None:
    """마스킹 후 원본 PII 문자열이 결과에 한 글자도 남지 않는다 (완료의 정의 6)."""
    result = mask_pii(f"담당자 정보 {raw} 끝.")

    assert raw not in result.text


# --- 혼합·무탐지·빈 문자열 --------------------------------------------------------


def test_mixed_text_masks_every_type() -> None:
    """여러 유형이 한 텍스트에 섞여도 7종 모두 각각의 플레이스홀더로 치환된다."""
    result = mask_pii(MIXED_TEXT)

    for pii_type in PiiType:
        assert pii_type.placeholder in result.text, pii_type


def test_mixed_text_leaves_no_raw_pii() -> None:
    """혼합 문서에서도 원본 PII 부분 문자열이 전부 사라진다."""
    result = mask_pii(MIXED_TEXT)

    for raw in MIXED_RAW_PII:
        assert raw not in result.text, raw


def test_mixed_text_counts_are_exact() -> None:
    """유형별 치환 개수 집계가 정확하다 (전화번호 2건 포함)."""
    result = mask_pii(MIXED_TEXT)

    assert result.counts == {
        PiiType.EMAIL: 1,
        PiiType.RRN: 1,
        PiiType.CARD: 1,
        PiiType.PHONE: 2,
        PiiType.BIZ_NO: 1,
        PiiType.ACCOUNT: 1,
        PiiType.IP: 1,
    }
    assert result.total == 8


def test_text_without_pii_is_returned_unchanged() -> None:
    """PII가 전혀 없는 텍스트는 원문 그대로 반환되고 집계는 비어 있다."""
    text = "이 문서에는 개인정보가 없습니다. 총 매출은 12% 증가했습니다."

    result = mask_pii(text)

    assert result.text == text
    assert result.counts == {}
    assert result.total == 0


def test_empty_text_is_handled() -> None:
    """빈 문자열도 예외 없이 처리된다."""
    result = mask_pii("")

    assert result.text == ""
    assert result.counts == {}
    assert result.total == 0


def test_partially_matching_document_masks_only_detected_types() -> None:
    """7종 중 일부만 포함된 문서는 탐지된 유형만 마스킹된다 (스펙 §5)."""
    result = mask_pii("문의는 support@corp.example 로 주세요. 나머지는 평범한 문장입니다.")

    assert result.counts == {PiiType.EMAIL: 1}
    assert "support@corp.example" not in result.text


def test_repeated_occurrences_are_counted_individually() -> None:
    """같은 유형이 여러 번 나오면 등장 횟수만큼 집계된다."""
    text = "a@x.com, b@y.com, c@z.com 그리고 10.0.0.1"

    result = mask_pii(text)

    assert result.counts == {PiiType.EMAIL: 3, PiiType.IP: 1}
    assert result.total == 4
    assert result.text.count(PiiType.EMAIL.placeholder) == 3


# --- 유형 판정 우선순위 (패턴 간 겹침) ---------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected", "shadowed"),
    [
        ("123-45-67890", PiiType.BIZ_NO, PiiType.ACCOUNT),
        ("010-1234-5678", PiiType.PHONE, PiiType.ACCOUNT),
        ("02-123-4567", PiiType.PHONE, PiiType.ACCOUNT),
        ("1234-5678-9012-3456", PiiType.CARD, PiiType.ACCOUNT),
    ],
)
def test_more_specific_pattern_wins_over_account_heuristic(
    raw: str, expected: PiiType, shadowed: PiiType
) -> None:
    """형태가 겹치면 더 좁은 패턴이 이긴다 — 계좌번호 휴리스틱이 삼키지 않는다."""
    result = mask_pii(raw)

    assert result.counts == {expected: 1}
    assert shadowed.placeholder not in result.text


# --- 느슨한 매칭 원칙 (체크섬 미검증 · 과탐 감수) -----------------------------------


def test_checksums_are_not_validated() -> None:
    """체크섬·Luhn 검증 없이 형태만 본다 — 무효한 번호도 마스킹된다."""
    result = mask_pii("카드 0000-0000-0000-0000 / IP 999.999.999.999")

    assert result.counts == {PiiType.CARD: 1, PiiType.IP: 1}


def test_rrn_gender_digit_outside_range_is_not_masked() -> None:
    """주민등록번호 뒷자리 첫 숫자가 1~8 밖이면 매칭되지 않는다 (스펙 표의 과탐 제한)."""
    text = "일련번호 900101-9234567 입니다."

    result = mask_pii(text)

    assert result.text == text
    assert result.counts == {}


@pytest.mark.parametrize(
    "text",
    [
        "작성일 2026-08-21",
        "작성일 2026-08-21.",
        "기간 2026-08-21~2026-09-30",
        "2026-01-01 부터",
        "마감 2025-12-31 까지",
    ],
)
def test_iso_dates_are_not_masked_as_account(text: str) -> None:
    """ISO 날짜는 계좌번호로 잡지 않는다 — 날짜는 개인정보가 아니고, 계약서·회의록의
    거의 모든 줄에 있어 요약을 뭉개고 PII 집계를 부풀린다 (코드 리뷰 후속)."""
    result = mask_pii(text)

    assert result.text == text
    assert result.counts == {}


@pytest.mark.parametrize(
    "text",
    [
        "무효 월 1234-56-78",  # 월 56은 날짜가 될 수 없다
        "무효 일 2026-08-99",  # 일 99는 날짜가 될 수 없다
        "계좌 110-234-567890",  # 첫 그룹이 4자리가 아니다
    ],
)
def test_date_shaped_but_invalid_values_are_still_masked(text: str) -> None:
    """날짜가 될 수 없는 값은 계좌번호 후보로 그대로 남긴다 (누락 최소화 원칙)."""
    assert mask_pii(text).counts == {PiiType.ACCOUNT: 1}


# --- 값·순수성 계약 ----------------------------------------------------------------


def test_result_is_a_frozen_value() -> None:
    """반환값은 불변 값 타입이다 (코어 no-I/O·순수 함수 불변식)."""
    result = mask_pii(MIXED_TEXT)

    assert isinstance(result, MaskingResult)
    with pytest.raises(AttributeError):
        result.text = "덮어쓰기"  # type: ignore[misc]


def test_masking_is_idempotent() -> None:
    """이미 마스킹된 텍스트를 다시 마스킹해도 새로 치환될 것이 없다."""
    once = mask_pii(MIXED_TEXT)
    twice = mask_pii(once.text)

    assert twice.text == once.text
    assert twice.counts == {}


def test_masking_is_deterministic() -> None:
    """같은 입력은 항상 같은 출력·같은 집계를 낸다."""
    assert mask_pii(MIXED_TEXT) == mask_pii(MIXED_TEXT)


def test_placeholder_format_matches_spec() -> None:
    """플레이스홀더는 `[REDACTED_<TYPE>]` 형태다 (스펙 §4.5)."""
    for pii_type in PiiType:
        assert pii_type.placeholder == f"[REDACTED_{pii_type.value}]"


def test_pattern_table_covers_exactly_seven_types() -> None:
    """패턴 표는 스펙 §4.5의 7종을 정확히 한 번씩 담는다."""
    covered = [pii_type for pii_type, _ in PII_PATTERNS]

    assert len(covered) == 7
    assert set(covered) == set(PiiType)


def test_every_type_has_a_korean_label() -> None:
    """진행 로그·리포트 표시에 쓸 한국어 유형명이 7종 모두에 있다 (스펙 §4.5 표의 '유형' 열)."""
    labels = {pii_type.label for pii_type in PiiType}

    assert len(labels) == 7
    assert PiiType.RRN.label == "주민등록번호"


# --- 한글 인접 PII 회귀 (2026-08-21 보안 검토 검출) ------------------------------

#: 조사·의존명사가 공백 없이 바로 붙는 한국어 문장. 유니코드 `\b`로는 경계가 성립하지 않아
#: 원문 PII가 그대로 전송본에 실렸던 케이스들이다 — 7종 전부를 조사 인접 형태로 고정한다.
HANGUL_ADJACENT_CASES = [
    ("주민등록번호900101-1234567입니다", "900101-1234567", PiiType.RRN),
    ("연락처는 010-1234-5678로 주세요", "010-1234-5678", PiiType.PHONE),
    ("담당자 010-9876-5432님께 문의", "010-9876-5432", PiiType.PHONE),
    ("메일은 hong@corp.co.kr입니다", "hong@corp.co.kr", PiiType.EMAIL),
    ("사업자등록번호 123-45-67890입니다", "123-45-67890", PiiType.BIZ_NO),
    ("카드번호 1234-5678-1234-5678입니다", "1234-5678-1234-5678", PiiType.CARD),
    ("급여계좌 110-234-567890으로 입금", "110-234-567890", PiiType.ACCOUNT),
    ("서버 192.168.0.1에서 접속했습니다", "192.168.0.1", PiiType.IP),
    ("사내 서버 10.0.0.5번에 접속", "10.0.0.5", PiiType.IP),
]


@pytest.mark.parametrize(("text", "raw", "expected"), HANGUL_ADJACENT_CASES)
def test_hangul_adjacent_pii_is_masked(text: str, raw: str, expected: PiiType) -> None:
    """조사가 바로 붙어도 마스킹된다 — 한글은 유니코드 단어 문자라 `\\b`가 성립하지 않는다."""
    result = mask_pii(text)

    assert raw not in result.text, f"원문 PII가 전송본에 남았다: {raw}"
    assert expected.placeholder in result.text
    assert result.counts.get(expected) == 1


def test_realistic_korean_paragraph_masks_all_seven_types() -> None:
    """조사가 섞인 실제 한국어 인사 문서 형태에서 7종이 모두 가려진다."""
    paragraph = (
        "담당자: 김철수 (주민등록번호 900101-1234567입니다)\n"
        "연락처는 010-9876-5432로 문의 바랍니다.\n"
        "이메일은 hong@corp.co.kr입니다.\n"
        "법인 사업자등록번호 123-45-67890이며,\n"
        "급여계좌는 110-234-567890으로 지정되어 있습니다.\n"
        "카드번호 1234-5678-1234-5678입니다.\n"
        "사내 서버 192.168.0.11에서 확인 가능합니다.\n"
    )

    result = mask_pii(paragraph)

    for raw in (
        "900101-1234567", "010-9876-5432", "hong@corp.co.kr",
        "123-45-67890", "110-234-567890", "1234-5678-1234-5678", "192.168.0.11",
    ):
        assert raw not in result.text, f"원문 PII가 전송본에 남았다: {raw}"
    assert set(result.counts) == set(PiiType)


def test_multi_label_domain_is_masked_whole() -> None:
    """`corp.co.kr`처럼 라벨이 셋 이상인 도메인이 중간에서 잘리지 않는다."""
    result = mask_pii("hong@corp.co.kr 로 보내주세요")

    assert result.text == "[REDACTED_EMAIL] 로 보내주세요"


def test_ipv4_does_not_leave_a_trailing_octet() -> None:
    """다섯 번째 옥텟이 남아 부분 노출되지 않는다."""
    result = mask_pii("주소 192.168.0.1.5 입니다")

    assert "192.168" not in result.text


# --- 문장 끝 PII 회귀 (2026-08-21 코드 리뷰 검출) --------------------------------

#: 마침표로 끝나는 문장의 이메일·IP. 오른쪽 경계에서 `.`를 막았더니 통째로 빠져나갔던
#: 케이스다 — 한글 인접 수정이 만든 회귀라 두 방향을 함께 고정한다.
SENTENCE_FINAL_CASES = [
    ("문의는 hong@corp.co.kr.", "hong@corp.co.kr", PiiType.EMAIL),
    ("e-mail: kim.min-su@corp.co.kr.", "kim.min-su@corp.co.kr", PiiType.EMAIL),
    ("서버 주소 192.168.0.1.", "192.168.0.1", PiiType.IP),
    ("IP: 10.0.0.5.", "10.0.0.5", PiiType.IP),
]


@pytest.mark.parametrize(("text", "raw", "expected"), SENTENCE_FINAL_CASES)
def test_sentence_final_pii_is_masked(text: str, raw: str, expected: PiiType) -> None:
    """마침표로 끝나도 마스킹된다 — 문장 끝은 한국어 산문에서 가장 흔한 형태다."""
    result = mask_pii(text)

    assert raw not in result.text, f"원문 PII가 전송본에 남았다: {raw}"
    assert expected.placeholder in result.text


def test_multiple_sentence_final_items_all_masked() -> None:
    """한 줄에 여러 건이 마침표로 끝나도 전부 잡는다(첫 건만 잡히지 않는다)."""
    result = mask_pii("ip 192.168.0.1, 10.0.0.2. 메일 a@b.com. c@d.com.")

    for raw in ("192.168.0.1", "10.0.0.2", "a@b.com", "c@d.com"):
        assert raw not in result.text, f"원문 PII가 전송본에 남았다: {raw}"
    assert result.counts[PiiType.IP] == 2
    assert result.counts[PiiType.EMAIL] == 2
