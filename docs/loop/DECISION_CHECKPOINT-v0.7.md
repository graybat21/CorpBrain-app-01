# v0.7 하이브리드 검색 — 의사결정 체크포인트

정본: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` ·
`docs/plans/corpbrain-v0.7-hybrid-search.md` ·
`docs/grill/GRILL_LEDGER-v0.7-hybrid-search*.md` 2종(16개 결정 ALL_RESOLVED).
아래에는 **위 정본에 확정돼 있지 않은** 추가 의사결정만 기록한다.

CORE: 0
MINOR: 4

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

2. **그래프 DB 부재 안내는 CLI 어댑터가 존재 확인을 한 번 더 해서 낸다.**
   §3 항목7·§5는 「그래프 DB 부재 → exit 0 + stderr 안내 1줄」을 요구하는데, §4.5가 고정한
   코어 반환 타입은 `list[SearchResult]` 하나뿐이라 «그래프 없이 답했다»를 실어 보낼 자리가
   없다. `GraphOutcome` 같은 결과 객체를 새로 만드는 것은 §4.5가 정한 «선택 필드 1개»를
   넘어서고, 반환 타입을 튜플로 바꾸면 v0.4 호출부가 깨진다. 어댑터가
   `graph_path_for(out_dir).exists()` 를 한 번 더 보는 쪽을 골랐다 — 읽기만 하는 확인이라
   코어의 판정을 바꾸지 않고, `_run_graph` 가 이미 같은 확인을 하고 있어 관용구가 늘지 않는다.
   — U6

3. **`--graph-decay`·`--expand-edges` 검증은 `--no-graph` 여부와 무관하게 무조건 한다.**
   스펙 §4.5는 조건 없이 "`graph_decay`가 `0 < α < 1` 밖이면 `PreconditionError`를 낸다"고
   적었으므로 글자 그대로 따랐다. 확산을 끌 때만 검증을 건너뛰면 규칙이 둘로 갈리고, 잘못된
   값을 준 사용자가 «받아들여졌다»고 오해한다. 잘못된 입력은 확산 여부와 무관하게 잘못된
   입력이다. — U4

4. **α 스윕 스크립트는 CLI를 껍데기째 호출하지 않고 `core.search_index()` 를 직접 부른다.**
   스펙 §4.8 6번은 "측정은 사용자와 같은 경로를 쓴다 — `--graph-decay`·`--expand-edges`
   플래그로 스윕한다"고 적었다. 그 결정이 막으려던 것은 **별도 랭킹 구현을 두어 측정값이 실제
   동작과 어긋나는 것**이고, CLI는 인자를 파싱해 같은 함수를 부르는 얇은 어댑터라 이 방식도
   같은 경로다. 대신 stdout(한국어 리포트 문구)을 파싱하지 않아도 되어, 출력 문구를 다듬는
   변경이 측정 하네스를 깨뜨리지 않는다. — U9

---

STOP REASON: ALL_DONE
