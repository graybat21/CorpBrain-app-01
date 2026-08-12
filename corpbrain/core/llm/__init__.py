"""LLM 백엔드 어댑터 — 이번 슬라이스의 백엔드는 로컬 Ollama 하나뿐이다 (스펙 §4.3).

이 패키지의 모든 외부 호출은 `corpbrain.core.gateway`의 단일 관문만 경유한다 (스펙 §4.5).
"""

from __future__ import annotations
