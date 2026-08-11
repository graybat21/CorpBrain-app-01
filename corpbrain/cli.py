"""CorpBrain CLI 어댑터.

인자 파싱·로그 출력·종료 코드 매핑만 담당하고, 비즈니스 로직은 코어에 둔다 (스펙 §4.5).
실제 `scan` 서브커맨드 구현은 후속 FR에서 채운다.
"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    """콘솔 엔트리 포인트. 종료 코드를 정수로 반환한다."""
    return 0
