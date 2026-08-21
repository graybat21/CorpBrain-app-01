"""PII 마스킹 — 클라우드로 나가는 전송본에서 한국 특화 개인정보 7종을 치환한다 (v0.5 스펙 §4.5).

`engine=cloud`로 요약을 요청하기 직전, 프롬프트에 들어갈 원문 텍스트를 이 모듈에 통과시켜
탐지된 PII를 `[REDACTED_<TYPE>]` 플레이스홀더로 바꾼 뒤 게이트웨이로 보낸다. 마스킹은
**전송본에만** 적용되며 원본 문서·산출된 위키에는 영향을 주지 않는다 (스펙 §4.5).
`engine=local`(Ollama) 경로는 외부로 나가지 않으므로 마스킹하지 않는다.

**정밀도 원칙 (스펙 §4.5):** 체크섬·Luhn 등 검증 알고리즘 없이 형태(자릿수·구분자) 기반의
느슨한 매칭만 쓴다. 과탐(정상 숫자열을 마스킹)은 감수하되 누락(실제 PII를 놓침)을 최소화하는
방향으로 기운다 — 과탐의 비용은 요약 품질이 조금 흐려지는 것뿐이기 때문이다.

**I/O 경계:** 순수 함수만 있다. 파일·네트워크·전역 가변 상태를 쓰지 않으며, 입력 문자열을
변형하지 않고 새 값(`MaskingResult`)을 돌려준다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["PII_PATTERNS", "MaskingResult", "PiiType", "mask_pii"]


class PiiType(StrEnum):
    """마스킹 대상 PII 유형 7종 (스펙 §4.5 표).

    멤버 값이 곧 플레이스홀더의 `<TYPE>` 토큰이다 — 값을 바꾸면 전송본의 치환 문자열이 바뀐다.
    """

    RRN = "RRN"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    BIZ_NO = "BIZ_NO"
    CARD = "CARD"
    ACCOUNT = "ACCOUNT"
    IP = "IP"

    @property
    def placeholder(self) -> str:
        """치환에 쓰는 `[REDACTED_<TYPE>]` 문자열 (스펙 §4.5)."""
        return f"[REDACTED_{self.value}]"

    @property
    def label(self) -> str:
        """진행 로그·요약 리포트에 쓸 한국어 유형명 (스펙 §4.5 표의 '유형' 열)."""
        return _LABELS[self]


#: 스펙 §4.5 표의 '유형' 열 — 어댑터가 치환 건수를 사람이 읽는 문구로 렌더할 때 쓴다.
_LABELS: dict[PiiType, str] = {
    PiiType.RRN: "주민등록번호",
    PiiType.PHONE: "전화번호",
    PiiType.EMAIL: "이메일",
    PiiType.BIZ_NO: "사업자등록번호",
    PiiType.CARD: "신용카드번호",
    PiiType.ACCOUNT: "계좌번호",
    PiiType.IP: "IP주소",
}

#: ASCII 전용 경계 — 스펙 §4.5 표는 `\b`로 적혀 있으나 그대로 쓰면 한국어에서 무너진다.
#:
#: 파이썬의 `\b`·`\w`는 유니코드 인식이라 **한글 음절도 단어 문자**로 친다. 한국어는 조사가
#: 식별자에 공백 없이 바로 붙으므로(`010-1234-5678로`, `900101-1234567입니다`, `192.168.0.1에서`)
#: 숫자와 뒤따르는 한글 사이에 단어 경계가 생기지 않아 `\b`가 성립하지 않고, 패턴이 통째로
#: 빗나가 **원문 PII가 그대로 전송본에 실린다**. 이는 이 모듈이 선언한 정밀도 원칙(누락 최소화)과
#: 정반대의 실패 모드이므로, 경계 판정을 ASCII 영숫자·밑줄로만 한정해 한글 인접 PII를 잡는다.
#: (2026-08-21 보안 검토에서 검출 — `docs/loop/DECISION_CHECKPOINT-v0.5.md` 참조)
_L = r"(?<![0-9A-Za-z_])"
_R = r"(?![0-9A-Za-z_])"

#: 유형별 정규식 (스펙 §4.5 표의 '정규식(형태)' 열 + 위 ASCII 경계 보정) — 로드 시 1회 컴파일.
#:
#: **순서가 곧 우선순위다.** 계좌번호는 "하이픈으로 구분된 숫자 그룹"이라는 넓은 휴리스틱이라
#: 사업자등록번호(3-2-5)·전화번호(3-4-4)·카드번호(4-4-4-4)를 통째로 삼킨다. 더 좁은 패턴을
#: 먼저 적용해 구체적인 유형 라벨이 살아남게 하고, 계좌번호는 마지막에 남은 것만 가져간다.
#: 치환 결과인 플레이스홀더는 숫자·`@`를 포함하지 않으므로 뒤따르는 패턴에 다시 걸리지 않는다.
PII_PATTERNS: tuple[tuple[PiiType, re.Pattern[str]], ...] = (
    # 이메일 — local part가 숫자·하이픈·점을 품을 수 있어 숫자 패턴보다 먼저 통째로 가져간다.
    # 도메인 라벨 수를 제한하지 않는다(`corp.co.kr`처럼 다단 도메인이 중간에서 잘리지 않게).
    (
        PiiType.EMAIL,
        re.compile(
            r"(?<![0-9A-Za-z_.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+"
            r"(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![0-9A-Za-z_.-])"
        ),
    ),
    # 주민등록번호 — 하이픈 유무 모두 허용, 뒷자리 첫 숫자 1~8(성별·내외국인 코드)로 과탐 일부 제한.
    (PiiType.RRN, re.compile(_L + r"\d{6}-?[1-8]\d{6}" + _R)),
    # 신용카드번호 — 16자리 4그룹(국내 대다수 카드). 15자리(Amex 등)는 비목표.
    (PiiType.CARD, re.compile(_L + r"\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}" + _R)),
    # 전화번호 — 휴대전화·일반전화 두 패턴의 OR 결합. 경계가 한쪽 분기에만 붙지 않도록
    # 반드시 비캡처 그룹으로 감싼다.
    (
        PiiType.PHONE,
        re.compile(
            _L + r"(?:01[016789]-?\d{3,4}-?\d{4}|0(?:2|[3-6]\d)-?\d{3,4}-?\d{4})" + _R
        ),
    ),
    # 사업자등록번호 — 하이픈 포함 표준 표기(3-2-5)만.
    (PiiType.BIZ_NO, re.compile(_L + r"\d{3}-\d{2}-\d{5}" + _R)),
    # 계좌번호 — 은행별 표준 포맷이 없어 하이픈 2~3개 숫자 그룹 휴리스틱. 7종 중 오탐률 최고.
    (PiiType.ACCOUNT, re.compile(_L + r"\d{2,6}-\d{2,6}-\d{2,6}(?:-\d{1,6})?" + _R)),
    # IP주소 — IPv4 형태만. 옥텟 범위(0~255) 미검증. IPv6은 비목표.
    # 오른쪽 경계에 `.`도 포함해 다섯 번째 옥텟이 남는 일이 없게 한다.
    (PiiType.IP, re.compile(_L + r"(?:\d{1,3}\.){3}\d{1,3}" + r"(?![0-9A-Za-z_.])")),
)


@dataclass(frozen=True)
class MaskingResult:
    """마스킹 결과 (순수 값) — 클라우드로 보낼 전송본과 유형별 치환 건수."""

    #: 플레이스홀더로 치환된 텍스트. 탐지된 PII가 없으면 입력과 동일하다.
    text: str
    #: 유형별 치환 건수. **1건 이상 치환된 유형만** 담기며(0건 항목 없음), 삽입 순서는
    #: `PII_PATTERNS` 순서라 같은 입력에 대해 항상 같은 순서로 렌더된다.
    counts: dict[PiiType, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """유형을 가리지 않은 전체 치환 건수."""
        return sum(self.counts.values())


def mask_pii(text: str) -> MaskingResult:
    """`text`의 PII 7종을 `[REDACTED_<TYPE>]`로 치환한 전송본과 치환 건수를 돌려준다 (스펙 §4.5).

    `PII_PATTERNS` 순서대로 전역 치환을 누적 적용한다 — 넓은 패턴(계좌번호)이 좁은 패턴을
    삼키지 않도록 구체적인 유형을 먼저 적용한다. 탐지된 패턴만 치환하고 나머지는 그대로 두며,
    과탐을 이유로 전송을 차단하지 않는다 (스펙 §5).

    Args:
        text: 요약 프롬프트에 실릴 원문 텍스트 (이미 `--max-chars`로 절단된 상태).

    Returns:
        치환된 텍스트와 유형별 건수를 담은 `MaskingResult` (입력 문자열은 변형하지 않는다).
    """
    masked = text
    counts: dict[PiiType, int] = {}
    for pii_type, pattern in PII_PATTERNS:
        masked, replaced = pattern.subn(pii_type.placeholder, masked)
        if replaced:
            counts[pii_type] = replaced
    return MaskingResult(text=masked, counts=counts)
