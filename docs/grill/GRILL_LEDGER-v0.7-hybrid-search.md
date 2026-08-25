# Grill Ledger — v0.7 하이브리드 검색 (issue #43)

- 참조 범위: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md`(주 대상) ·
  `corpbrain-v0.6-knowledge-graph.md`(계승) · `CLAUDE.md`(불변식) ·
  `corpbrain/core/{search,graph,graphstore,report}.py`
- 관심 방향: 구현 착수 전, 스펙이 «미결정»으로 남긴 것과 **계약이 코드와 맞물리지 않는 지점**을
  결정 가능한 수준까지 확정한다.
- 완료 조건: 아래 토픽 전부 RESOLVED.
- OUTPUT: 스펙 문서(§) 갱신 + 하네스(`CLAUDE.md` 불변식) + 이 원장.

RESOLVED: 11 / TOTAL: 11

- [x] T1  | CORE  | 확산 문서의 코사인·표시 메타데이터를 어느 계약으로 얻는가 | status:RESOLVED | decision: `VectorStore` 계약도 넓히지 않는다 — `search(qv, top_k=len(list_ids()))`로 전 문서를 한 번에 받아 매핑으로 쓴다 (추가 I/O 0, 제목 출처 단일화) | applied: 스펙 §4.7 · CLAUDE.md v0.7 불변식
- [x] T2  | CORE  | 「확산 문서」의 정의 — 자기 코사인이 이긴 문서에 근거 줄을 붙이는가 | status:RESOLVED | decision: 경계는 «후보 진입 경로» — 시드는 expansion None, 확산 진입 문서는 점수 출처와 무관하게 근거 줄. 대괄호 점수 == 코사인이면 「코사인」 항목 생략 | applied: 스펙 §4.5·§4.6 · CLAUDE.md v0.7 불변식
- [x] T3  | CORE  | §4.3 정렬 키 5 「출력 상대경로」를 코어가 만들 수 없는 문제 | status:RESOLVED | decision: 정렬 키 5와 기준 시드 tie-break를 `doc_id`(원문 절대경로) 사전순으로 고정. 위키 I/O를 조회 경로에 들이지 않는다 | applied: 스펙 §4.3 · CLAUDE.md v0.7 불변식
- [x] T4  | MINOR | §4.6 결과 줄의 경로 표기 (현행 절대 source_path vs 상대) | status:RESOLVED | decision: v0.4 그대로 원문 절대경로(`metadata["source_path"]`) 유지, 스펙 예시를 고침 | applied: 스펙 §4.6
- [x] T5  | CORE  | `--graph-decay` 유효 범위 검증 (DoD 항목4를 무엇이 보장하는가) | status:RESOLVED | decision: 열린 구간 `0 < α < 1`, 범위 밖은 코어가 `PreconditionError`(exit 1). 클램프·CLI 검증 안 함 | applied: 스펙 §4.1·§4.5·DoD 8(신설, 이후 번호 +1) · CLAUDE.md v0.7 불변식
- [x] T6  | CORE  | α 실측의 수행 주체·절차 (스펙 미결정 1) | status:RESOLVED | decision: #42 §4.4 분담 계승 — 세션이 스크립트·쿼리 세트 작성, 사용자가 로컬에서 scan·스윕 실행, 세션이 기록·상수 확정 | applied: 스펙 §4.8 역할 분담 표 · 미결정 1 축소
- [x] T7  | MINOR | α 스윕 쿼리 세트의 형식·정답 라벨 커밋 위치 | status:RESOLVED | decision: `docs/smoke/graph_decay_queries.json`, 쿼리당 정답 **목록**(복수 허용). 초안은 세션, 확정은 사용자 | applied: 스펙 §4.8 2번
- [x] T8  | MINOR | 적중률 동률 시 보조 지표 (스펙 미결정 2) | status:RESOLVED | decision: top-1 → MRR → Recall@3 → α 오름차순(보수적). #42 지표 계승 | applied: 스펙 §4.8 4번 · 미결정 2 삭제
- [x] T9  | MINOR | 단방향 참조의 근거 문구 (스펙 미결정 3) | status:RESOLVED | decision: `시드를 참조함`/`시드가 참조함`/`서로 참조함` 3종. 위키 문구는 불변 | applied: 스펙 §4.6 · 미결정 3 삭제
- [x] T10 | MINOR | `--expand-edges` 빈 목록·중복 값 처리 | status:RESOLVED | decision: trim 허용·중복 흡수, 빈 목록/빈 항목/소문자는 코어가 `PreconditionError`(exit 1). 확산을 끄는 길은 `--no-graph` 하나 | applied: 스펙 §4.4
- [x] T11 | MINOR | 실측 전 `DEFAULT_GRAPH_DECAY` 잠정값과 구현·측정 순서 | status:RESOLVED | decision: 잠정값 0.7(주석 명시)로 구현 → 테스트는 `graph_decay=` 명시 → 사용자 스윕 → 상수 교체 → 릴리스 | applied: 스펙 §4.8 · CLAUDE.md v0.7 불변식
