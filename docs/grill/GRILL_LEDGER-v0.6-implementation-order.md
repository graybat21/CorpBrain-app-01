# Grill Ledger — v0.6 지식그래프 (5라운드: 구현 순서와 작업 분할)

앞선 라운드: `GRILL_LEDGER-v0.6.md`(실행 수준 설계) · `-integration.md`(기존 코드 통합) · `-spec-consistency.md`(스펙 정합성) · `-verification.md`(검증 계획) — 모두 ALL_RESOLVED.

참조 범위: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` + `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`(작업 단위 관용구) + `docs/ROADMAP.md` §2·§5 + v0.4·v0.5 커밋 이력
관심 방향: 무엇부터 만들고 어디서 커밋·PR을 끊을지, 중간 상태를 어떻게 유지할지
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: v0.6 실행 계획 문서 + 필요 시 `CLAUDE.md`

## 기존 관용구로 이미 정해져 있어 토픽에서 제외한 것

- **작업 단위 문서 형식** — `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`가 «U1~U6 + 트랙 + `depends:` + 실행 웨이브 + 불변식» 형식을 세웠다. 그대로 따른다.
- **커밋 프리픽스** — v0.5가 `v0.5(core)`/`(wiring)`/`(test)`/`(docs)`/`(security)`로 단계를 표기했다. `v0.6(...)`으로 계승한다.

RESOLVED: 4 / TOTAL: 4  ·  STOP: ALL_RESOLVED

- [x] X1 | CORE  | PR·브랜치 분할 단위 (단일 PR vs 다단계) | status:RESOLVED | decision:순차 2-PR(①코어+통합+위키 ②CLI+문서), 둘 다 머지 후 v0.6.0 tag. 병렬 개발 없음 — 텍스트 충돌이 아니라 의미 충돌(edges_by_type 키 표기 등)이 위험이고 임계 경로가 한 줄기라 실익이 작음 | applied:docs/plans/corpbrain-v0.6-knowledge-graph.md
- [x] X2 | CORE  | 작업 단위 분해(U1~Un)와 실행 웨이브 | status:RESOLVED | decision:계층별 10단위(PR① U1~U7, PR② U8~U10) — v0.2 플랜의 값타입→코어→렌더러→배선→조인 계승. 수직 슬라이스는 graph.py·정렬규칙·근거문구·코퍼스를 각 4회 고쳐 쓰고 첫 슬라이스가 인프라 70%를 삼켜 비채택 | applied:docs/plans/corpbrain-v0.6-knowledge-graph.md
- [x] X3 | MINOR | 커밋 단위 green 요구 수준(bisect 가능성) | status:RESOLVED | decision:모든 커밋이 green — 각 단위가 자기 단위테스트를 함께 담는다. 계층 분해 덕에 사실상 공짜이고 git bisect가 동작. 강제 결합은 U5의 parse_wiki_markdown 3-튜플(호출부+테스트 3곳 동시 수정) 하나뿐 | applied:docs/plans/corpbrain-v0.6-knowledge-graph.md
- [x] X4 | MINOR | 계획 문서를 남길 위치(docs/plans vs docs/goals) | status:RESOLVED | decision:v0.1·v0.2 방식으로 둘 다 — docs/plans/는 사람이 읽는 정본(작업 단위·근거), docs/goals/*-loop.md는 에이전트 실행 지시(종료 조건·자율 범위·금지 행위). grill 결정이 스펙에 다 있어 goal 프롬프트는 v0.5보다 짧아짐 | applied:docs/plans/corpbrain-v0.6-knowledge-graph.md
