# Grill Ledger — v0.6 지식그래프 (4라운드: 검증 계획 구체화)

앞선 라운드: `GRILL_LEDGER-v0.6.md`(실행 수준 설계) · `GRILL_LEDGER-v0.6-integration.md`(기존 코드 통합) · `GRILL_LEDGER-v0.6-spec-consistency.md`(스펙 정합성) — 모두 ALL_RESOLVED.

참조 범위: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` §3 완료의 정의 + 기존 테스트 관용구(`tests/integration/`, `tests/unit/`, `tests/security/`)
관심 방향: 완료의 정의 8개를 실제 테스트 케이스로 전개하면서 드러나는 경계 조건과 픽스처·스텁 설계
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md`, 필요 시 `CLAUDE.md`

RESOLVED: 7 / TOTAL: 7  ·  STOP: ALL_RESOLVED

- [x] W1 | CORE  | 유사도 임계치 비교 연산자(>= vs >)와 자기 자신 쌍 처리 | status:RESOLVED | decision:비교는 >=(이상), 자기 자신은 유사도 값이 아니라 doc_id 동일성으로 제외(같은 내용의 별개 파일은 엣지 유지), 대칭 엣지는 src<dst 정렬로 한 행만 저장하고 neighbors가 양쪽 조회 — --stats가 사람이 세는 관계 수와 일치 | applied:corpbrain-v0.6-knowledge-graph.md §4.1
- [x] W2 | CORE  | REFERENCES 양방향·자기참조 처리와 「관련 문서」 근거 문구 | status:RESOLVED | decision:자기 자신을 향하는 엣지는 종류 불문 생성 금지(doc_id 판정, W1과 통합). 양방향은 방향을 살려 두 행 유지. 근거 문구 3종 확정(이 문서가 참조함 / 이 문서를 참조함 / 서로 참조함) | applied:corpbrain-v0.6-knowledge-graph.md §4.1, §4.5, CLAUDE.md
- [x] W3 | CORE  | 인라인 코퍼스 설계 — 문서 구성과 5종 관계 배치 | status:RESOLVED | decision:단일 6문서 코퍼스(A~F, 하위폴더 3개)로 11가지 커버 대상을 모두 덮음 — DoD 항목1의 전체 그래프 단언이 코퍼스 하나를 요구. 경계 로직은 단위테스트가 별도 커버 | applied:corpbrain-v0.6-knowledge-graph.md §3
- [x] W4 | MINOR | 임베딩 스텁이 결정적 유사도를 만드는 방법 | status:RESOLVED | decision:짧은 직교 기저 조합 벡터(3~4차원)를 쓰고, 임계치 경계 케이스는 --similarity-threshold를 실측 코사인 값으로 지정해 부동소수 왕복 오차를 우회. 코사인 계산 자체는 test_vectorstore가 이미 커버 | applied:corpbrain-v0.6-knowledge-graph.md §3
- [x] W5 | MINOR | graph CLI 테스트의 stdout 단언 형태(정확 문자열 vs 부분 매칭) | status:RESOLVED | decision:report.py에 뷰별 빌더 3개(stats/neighbors/central) 추가, 정확 문자열 단언은 tests/unit/test_graph_report.py, CLI 테스트는 종료 코드·배선만 — 기존 6빌더 + test_*_report.py 관용구 계승 | applied:corpbrain-v0.6-knowledge-graph.md §3
- [x] W6 | MINOR | test_network_invariant.py 확장 형태 | status:RESOLVED | decision:기존 파일에 케이스 2개 추가 — 그래프까지 도는 scan의 목적지가 localhost뿐, graph 단독 실행은 소켓 0건(plan_scan 선례와 동형). 새 파일 분리 시 소켓 패치 복제 + self-check 보호 상실이라 비채택 | applied:corpbrain-v0.6-knowledge-graph.md §3 항목8
- [x] W7 | MINOR | 스모크 시나리오 문안과 온디스크 코퍼스 구성 | status:RESOLVED | decision:SMOKE.md에 실행 H 하나 추가 — 스텁이 증명 못 하는 3가지만 확인(실제 모델의 entities 충실도 / 실제 임베딩에서 0.75 임계치 타당성 / 관련 문서 납득성). 온디스크 코퍼스는 인라인과 같은 6문서 구조를 실제 한국어 문서로. 부분 그래프는 DoD 5번이 스텁으로 덮으므로 제외 | applied:corpbrain-v0.6-knowledge-graph.md §3, CLAUDE.md
