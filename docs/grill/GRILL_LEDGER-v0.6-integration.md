# Grill Ledger — v0.6 지식그래프 (2라운드: 기존 코드 통합 지점)

1라운드(실행 수준 설계)는 `docs/grill/GRILL_LEDGER-v0.6.md` 에 있으며 ALL_RESOLVED다.

참조 범위: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` + `corpbrain/core/pipeline.py`, `cli.py`, `render.py`, `output.py`, `rerun.py`, `embedding_text.py`, `vectorstore.py`
관심 방향: v0.6이 건드리는 기존 모듈의 변경 범위와 회귀 위험 — 자원 수명, 불필요한 쓰기, 기존 파서와의 충돌, 깨지는 테스트
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md`, 필요 시 `CLAUDE.md`

범위 안에서 검토했으나 **문제가 아닌 것으로 확인되어 토픽에서 제외한 것**:
- `--dry-run`·`plan` 경로 — `_run_scan`이 `run_scan()` 호출 전에 `_emit_plan_report()`로 빠지므로 그래프와 만나지 않는다.
- `findings`/`plan` 주입 이음새 — 둘 다 패스1 이전에 소비되고 끝나 2-패스 전환과 무관하다.
- 주입이 `rerun`을 무한 재생성으로 모는 문제 — 주입은 위키 mtime을 원문보다 늦게 만들므로 다음 실행에 정상 스킵된다.

RESOLVED: 5 / TOTAL: 5  ·  STOP: ALL_RESOLVED

- [x] U1 | CORE  | 패스2가 벡터를 읽으려면 VectorStore 수명(close 시점)을 어떻게 바꾸는가 | status:RESOLVED | decision:패스2·3을 기존 try 블록 안으로 넣어 finally: store.close()의 범위를 실행 끝까지 연장. 그래프 빌더 재개봉은 _NoIndexStore가 없앤 if indexing 분기를 되살리므로 비채택 | applied:corpbrain-v0.6-knowledge-graph.md §4.8, CLAUDE.md
- [x] U2 | CORE  | 주입 시 내용이 안 바뀐 위키까지 다시 쓰는 것을 막을 것인가 | status:RESOLVED | decision:마커 교체 결과를 기존 내용과 비교해 다를 때만 기록. 마커 탐색으로 이미 전체를 읽으므로 비교 비용 0이고, 재실행 시 대다수 위키의 mtime이 유지되어 동기화 도구 재전송이 없어짐 | applied:corpbrain-v0.6-knowledge-graph.md §4.5, CLAUDE.md
- [x] U3 | CORE  | parse_wiki_markdown이 「관련 문서」 섹션을 모르는 문제와 fallback 파서 재사용 | status:RESOLVED | decision:_ALL_SECTIONS에 "## 관련 문서" 추가(임베딩에서는 제외임을 명시)하고 반환을 (제목, 텍스트, 태그)로 확장해 T3 fallback이 같은 파서 재사용. 유사도→관련문서→임베딩 피드백 루프를 구조적으로 차단 | applied:corpbrain-v0.6-knowledge-graph.md §4.4, CLAUDE.md
- [x] U4 | MINOR | 스킵 문서 파일이 패스3에서 수정되는 것과 generated/skipped 보고의 정합 | status:RESOLVED | decision:GraphOutcome.related_updated_count를 추가해 그래프 축에 '관련 문서 갱신 N건' 한 줄로 보고. SkipReason 세분화는 요약·그래프 두 시스템 상태를 한 축에 담게 되어 비채택 | applied:corpbrain-v0.6-knowledge-graph.md §4.6
- [x] U5 | MINOR | 위키 섹션 추가로 깨지는 기존 테스트의 처리 범위 | status:RESOLVED | decision:render_markdown이 마커+'관련 문서 없음'을 렌더하고 SECTION_HEADERS에 추가 — 순회 단언 4곳은 수정 불필요. parse_wiki_markdown 3-튜플화로 언패킹 4곳만 한 줄씩 수정 | applied:corpbrain-v0.6-knowledge-graph.md §4.5, §3
