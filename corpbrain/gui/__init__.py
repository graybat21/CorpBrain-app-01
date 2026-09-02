"""로컬 웹 GUI 어댑터 (v0.9 스펙).

`corpbrain.core`의 **공개 API만 호출하는 두 번째 어댑터**다 — v0.1 스펙 §4.5가
"이후 UI는 같은 코어를 호출하는 또 다른 어댑터로 붙는다"고 약속한 이음새를 그대로 쓴다.
코어를 수정하지 않으며, 이 패키지는 `corpbrain/core/` 밖에 있다(`tests/test_core_api_smoke.py`가
"코어를 import 해도 CLI가 딸려 오지 않음"을 단언하는 것과 같은 격리를 GUI에도 유지한다).

표준 라이브러리만 쓴다 — 신규 런타임 의존성이 0개다 (스펙 §4.2).
"""

from __future__ import annotations
