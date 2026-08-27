# Grill Ledger — v0.9 GUI (3라운드: 화면별 상호작용 계약)

앞선 라운드: `GRILL_LEDGER-v0.9-gui.md`(스펙 계약 공백 13건) ·
`GRILL_LEDGER-v0.9-gui-test-harness.md`(테스트 하네스 6건) — 둘 다 ALL_RESOLVED.

- 참조 범위: `static/docs/specs/features/corpbrain-v0.9-gui.md` §4 ·
  `corpbrain/core/render.py`(위키 링크 생성) · `corpbrain/core/report.py` ·
  `gui_preview/variants/minimalist`
- 관심 방향: 화면이 실제 데이터와 만나는 지점 — 화면 간 이동, 위키 링크, 결과 표시
- 착수 근거: **위키는 브라우저에서 열릴 것을 전제로 만들어지지 않았다.**
  `render.py:91`의 「원문」은 `file://` 링크라 http 페이지에서 브라우저가 차단하고,
  `render.py:120·144`의 「관련 문서」는 `.md.md`를 가리키는 파일시스템 상대경로다.
  프로토타입에는 `pushState`도 `location.hash`도 하나도 없고(grep 0건), `switchView()`는
  어떤 노드로 갈지 상태를 넘기지 않는다.
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: 스펙 §4 확장 + `CLAUDE.md` v0.9 불변식 + 본 원장

```
RESOLVED: 7 / TOTAL: 7
- [x] IX1 | CORE  | 화면 간 점프와 URL 상태 (라우팅 유무) | status:RESOLVED | decision:URL 해시 라우팅(#/graph?node=… · #/wiki?doc=…). 해시는 서버로 전송되지 않아 http.server 라우팅을 건드리지 않는다. pushState(SPA fallback 필요)·무라우팅 배제 | applied:스펙 §4.10.4, CLAUDE.md
- [x] IX2 | CORE  | 위키 「원문」 file:// 링크를 브라우저에서 다루는 법 | status:RESOLVED | decision:경로 표시 + 복사 버튼. OS 열기 엔드포인트(MVP §2 비목표)·원문 바이트 전송 배제. 위키 산출물은 안 바꾼다 | applied:스펙 §4.6, CLAUDE.md
- [x] IX3 | CORE  | 「관련 문서」 파일시스템 상대경로 링크 처리 | status:RESOLVED | decision:서버가 {title, doc_id, 근거} 필드로 내리고 프론트는 #/wiki?doc=<doc_id> 조립만. 프론트 링크 파싱·링크 제거 배제 | applied:스펙 §4.6, CLAUDE.md
- [x] IX4 | CORE  | 검색 결과 — build_search_lines 재사용 vs 구조화 | status:RESOLVED | decision:필드는 구조화, 확산 근거 줄만 기존 빌더 문자열 재사용. 갈라지면 안 되는 것은 어휘이지 줄 조립이 아니다 | applied:스펙 §4.6.1 신설, CLAUDE.md
- [x] IX5 | MINOR | 위키 탐색기 트리의 구성과 갱신 비용 | status:RESOLVED | decision:그래프 DB의 nodes.label 을 읽는다(sqlite 2회, 파일 0개 개봉). 키는 doc_id 로 통일. DB 부재 시 파일명 대체 + 안내 | applied:스펙 §4.6.2 신설
- [x] IX6 | MINOR | plan → scan 흐름 (사전 확인 게이트를 두는가) | status:RESOLVED | decision:계량 → 확인 → 실행 2단계. 게이트는 2단계에서 이유+강행 토글로. 폴더 선택 시 자동 계량 안 함(nvidia-smi·stat 패스). plan 결과는 run_scan 에 재사용 | applied:스펙 §4.3.4 신설
- [x] IX7 | MINOR | minimalist의 접근성 기준 계승 여부 | status:RESOLVED | decision:토큰 밖 색 금지(AA 4.5:1 유지) + 키보드 도달·포커스 링. 자동 검사(axe)는 Node 툴체인 재도입이라 배제, 수동 스모크로 | applied:스펙 §4.10.5 신설·§3 항목12, CLAUDE.md
```


**STOP: ALL_RESOLVED** — 7/7 (CORE 4 · MINOR 3)
