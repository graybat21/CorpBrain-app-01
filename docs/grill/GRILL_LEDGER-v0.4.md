# Grill Ledger — v0.4 벡터 인덱싱 + 검색

참조 범위: `static/docs/specs/features/corpbrain-v0.4-vector-index-and-search.md`, `docs/ROADMAP.md`, `corpbrain/core/*`
관심 방향: v0.4 스펙의 구현 착수 전 남은 모호함 — 아키텍처 인터페이스, 데이터 모델, 게이트 산정 범위
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.4-vector-index-and-search.md`, 필요 시 `docs/ROADMAP.md`/기존 스펙 문서

RESOLVED: 5 / TOTAL: 5

- [x] T1 | CORE  | VectorStore 어댑터 인터페이스 메서드 계약 확정 | status:RESOLVED | decision:upsert/delete/search 3메서드 + model_name 접근자로 구성된 최소 계약 | applied:corpbrain-v0.4-vector-index-and-search.md §4.3
- [x] T2 | CORE  | embedding_failed 실패의 데이터 모델·리포트 구조 확정 | status:RESOLVED | decision:신규 EmbeddingFailure 값 타입 + ScanResult.embedding_failures 리스트, SkippedFile과 분리 | applied:corpbrain-v0.4-vector-index-and-search.md §4.3
- [x] T3 | CORE  | 토큰 게이트(total_est_tokens) 산정에 임베딩 비용 포함 여부 | status:RESOLVED | decision:포함, 원문 추정 토큰×10%를 가산 | applied:corpbrain-v0.4-vector-index-and-search.md §3(item12)·§4.3
- [x] T4 | MINOR | 인덱스 파일명·경로 확정 | status:RESOLVED | decision:<out_dir>/.corpbrain_index.sqlite (숨김 파일) | applied:corpbrain-v0.4-vector-index-and-search.md §3(item6)·§4.3
- [x] T5 | MINOR | v0.3 스펙 §2 "로드맵상 v0.5+" 문구를 ROADMAP.md(v0.4)와 정정 | status:RESOLVED | decision:벡터DB·임베딩 항목을 v0.4로 분리 정정, v0.4 스펙 참조 추가 | applied:corpbrain-v0.3-resource-gating-and-ollama-doctor.md §2
