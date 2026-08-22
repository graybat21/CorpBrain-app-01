# Grill Ledger — v0.6 지식그래프 (문서 중심 4종 엣지 · 관련 문서 상호연결)

참조 범위: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` + 해당 결정이 닿는 코어 모듈(`pipeline.py`, `render.py`, `output.py`, `rerun.py`, `vectorstore.py`, `models.py`, `cli.py`)
관심 방향: v0.6 스펙의 구현 착수 전 실행 수준 모호함 — 데이터 식별자·저장 스키마·2패스 구조·재료 확보 경로·검증 픽스처
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md`, 필요 시 `CLAUDE.md`

RESOLVED: 10 / TOTAL: 10  ·  STOP: ALL_RESOLVED

- [x] T1  | CORE  | 그래프 노드 ID 체계 (Document/Entity/Tag id 규칙 · 벡터스토어 doc_id 조인 키) | status:RESOLVED | decision:Document id=원문 절대경로(v0.4 doc_id와 동일 키로 무변환 조인), Entity id=entity:<정규화키>, Tag id=tag:<정규화키>, --neighbors 상대경로는 CLI 어댑터가 절대경로로 해석 | applied:corpbrain-v0.6-knowledge-graph.md §4.1, CLAUDE.md
- [x] T2  | CORE  | 그래프 DB 테이블 스키마와 재빌드 전략 (전체 재빌드 vs 증분 upsert) | status:RESOLVED | decision:재료(doc_facts)는 증분 upsert로 영속, 파생물(nodes·edges)은 매 실행 전체 재빌드 — 스킵 문서 엔티티 보존과 결정성을 동시 충족. 4테이블 스키마 확정 | applied:corpbrain-v0.6-knowledge-graph.md §4.4, CLAUDE.md
- [x] T3  | CORE  | 스킵된 문서(up_to_date)의 엔티티·태그 재료 확보 경로 | status:RESOLVED | decision:정상 경로는 doc_facts 보존으로 해결(T2). 행이 없는 기존 위키는 마크다운의 제목·「태그·키워드」를 파싱해 doc_facts에 1회 upsert하고 엔티티만 빈 배열 — v0.5 산출물도 3종 동작하는 부분 그래프 | applied:corpbrain-v0.6-knowledge-graph.md §4.4
- [x] T4  | CORE  | REFERENCES 매칭에 쓸 입력 텍스트 확보 방법 (--max-chars 절단·재읽기 여부) | status:RESOLVED | decision:재요약 문서는 요약 입력 텍스트 재사용(추가 I/O 0), doc_facts 복원 시에만 --max-chars까지 1회 재읽기 후 캐시. --max-chars 이후 참조 미탐지는 알려진 한계로 명시 | applied:corpbrain-v0.6-knowledge-graph.md §5
- [x] T5  | CORE  | SEMANTICALLY_SIMILAR용 벡터 접근 경로 (VectorStore Protocol 확장 여부) | status:RESOLVED | decision:VectorStore Protocol에 iter_vectors() 추가(SqliteVectorStore + _NoIndexStore 구현), 그래프 빌더는 sqlite 직접 접근 금지. 규모 가드는 기존 --max가 겸함 | applied:corpbrain-v0.6-knowledge-graph.md §4.4, CLAUDE.md
- [x] T6  | CORE  | 「관련 문서」를 기존 위키에 반영하는 방식 (텍스트 치환 vs 재렌더) | status:RESOLVED | decision:<!-- corpbrain:related:start/end --> 마커 블록 사이만 교체, 없으면 파일 끝에 추가. 재요약·스킵·v0.5복원 세 경로를 단일 코드로 처리하고 요약문에 헤딩 문자열이 있어도 본문 손실 없음 | applied:corpbrain-v0.6-knowledge-graph.md §4.5, CLAUDE.md
- [x] T7  | MINOR | 2·3패스 중간 실패 시 원자성·롤백 방침 | status:RESOLVED | decision:nodes·edges 재빌드는 단일 트랜잭션(실패 시 이전 그래프 보존), 위키 주입은 파일별 베스트 에포트. 두 경우 모두 exit 0 + 종료 요약 보고 — v0.1 §5 부분성공 원칙 계승 | applied:corpbrain-v0.6-knowledge-graph.md §5
- [x] T8  | MINOR | ScanResult 확장 필드와 종료 요약 문구 | status:RESOLVED | decision:그래프 결과 4종을 단일 GraphOutcome 객체로 묶어 ScanResult.graph 한 필드로 담음(9필드 유지). GraphStats·GraphSkipReason 신설, 종료 요약 문구 확정 | applied:corpbrain-v0.6-knowledge-graph.md §4.6
- [x] T9  | MINOR | graph 명령 인자 경로 형식 · 미존재 문서 · DB 부재 시 종료 코드 | status:RESOLVED | decision:경로는 위키 상대경로 우선 + 원문 상대경로 fallback + 절대경로 허용. DB 부재 exit 1(search 선례), 미존재 문서 exit 1(식별자 지목 실패는 빈 결과와 다름), 빈 그래프 --stats/--central은 exit 0 | applied:corpbrain-v0.6-knowledge-graph.md §4.7
- [x] T10 | MINOR | v0.6 검증용 픽스처 코퍼스 설계 (기존 sample_corpus 확장 vs 신규) | status:RESOLVED | decision:역할 분리 — 자동 테스트는 tmp_path 인라인 생성(스텁이 태그·엔티티·벡터를 결정하므로 온디스크 이점 없음), 수동 스모크용으로만 신규 온디스크 코퍼스. 기존 sample_corpus는 2026-08-22 오염 사고 이력으로 확장하지 않음 | applied:corpbrain-v0.6-knowledge-graph.md §3
