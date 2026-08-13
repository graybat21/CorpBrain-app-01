"""코어 예외 계층.

개별 파일의 실패는 예외가 아니라 `SkipReason`으로 결과에 담고(부분 성공 보고, 스펙 §5),
선행 조건 실패만 예외로 올려 어댑터가 비-0 종료로 매핑한다 (스펙 §3-5).
"""

from __future__ import annotations


class CorpBrainError(Exception):
    """코어가 발생시키는 모든 예외의 베이스."""


class PreconditionError(CorpBrainError):
    """선행 조건 실패 — 입력 폴더 없음/접근 불가, Ollama 미탐지 등. 비-0 종료로 이어진다."""


class GpuGateError(PreconditionError):
    """GPU 미탐지로 자원 게이트가 scan을 차단 — 선행 조건 실패(exit 1) (v0.3 스펙 §4.2).

    `--force-gates`로만 강행한다. 기존 종료 코드 서열을 재사용한다(Ollama 미탐지와 동일 exit 1).
    """


class TokenBudgetExceededError(CorpBrainError):
    """스캔 전체 예상 토큰이 예산을 초과해 차단 — 상한 초과(exit 3) (v0.3 스펙 §4.2).

    선행 조건 실패가 아니라 `max_files` 상한 초과와 같은 성격이라 `PreconditionError`가 아니며,
    어댑터가 `EXIT_LIMIT_EXCEEDED`(3)로 매핑한다. `--force-gates`로만 강행한다.
    """
