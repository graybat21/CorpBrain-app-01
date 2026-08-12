"""코어 예외 계층.

개별 파일의 실패는 예외가 아니라 `SkipReason`으로 결과에 담고(부분 성공 보고, 스펙 §5),
선행 조건 실패만 예외로 올려 어댑터가 비-0 종료로 매핑한다 (스펙 §3-5).
"""

from __future__ import annotations


class CorpBrainError(Exception):
    """코어가 발생시키는 모든 예외의 베이스."""


class PreconditionError(CorpBrainError):
    """선행 조건 실패 — 입력 폴더 없음/접근 불가, Ollama 미탐지 등. 비-0 종료로 이어진다."""
