# v0.7 하이브리드 검색 — 의사결정 체크포인트

정본: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` ·
`docs/plans/corpbrain-v0.7-hybrid-search.md` ·
`docs/grill/GRILL_LEDGER-v0.7-hybrid-search*.md` 2종(16개 결정 ALL_RESOLVED).
아래에는 **위 정본에 확정돼 있지 않은** 추가 의사결정만 기록한다.

CORE: 0
MINOR: 1

## CORE (아키텍처·보안·외부의존·데이터 모델)

(없음)

## MINOR (네이밍·디렉터리·로그 포맷·문구)

1. **`--expand-edges` 문자열 파서의 공개 이름은 `core.parse_expand_edges()`다.**
   스펙 §4.4는 "파싱과 검증도 코어가 맡고 CLI는 문자열을 그대로 넘긴다"고 정했지만,
   §4.5의 `search_index()` 시그니처는 `frozenset[EdgeType]`을 받는다. 두 요구를 함께
   지키려면 코어가 «문자열 → 집합» 함수를 하나 공개해야 하는데 정본에 이름이 없다.
   `graph.py`에 `validate_graph_decay()`와 나란히 두고 `corpbrain.core`에서 내보낸다 —
   둘 다 확산 파라미터의 순수 검증이고, 순위 계산과 같은 파일에 있어야 «α가 열린 구간일
   때만 성립하는 성질»이 규칙 옆에 놓인다. `validate_graph_decay()`는 호출자가
   `search_index()` 하나뿐이라 내보내지 않는다. — U3
