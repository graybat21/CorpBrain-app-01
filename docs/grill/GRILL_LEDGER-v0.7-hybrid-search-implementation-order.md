# Grill Ledger — v0.7 하이브리드 검색 (2라운드: 구현 순서와 작업 분할)

앞선 라운드: `GRILL_LEDGER-v0.7-hybrid-search.md`(스펙 계약 공백 11건) — ALL_RESOLVED.

- 참조 범위: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` ·
  `docs/plans/corpbrain-v0.6-knowledge-graph.md`(작업 단위 관용구) · `docs/ROADMAP.md` §2·§5 ·
  v0.6 커밋·PR 이력 · PR #45(#42) 상태
- 관심 방향: 무엇부터 만들고 어디서 커밋·PR을 끊을지, #42 의존과 α 실측 대기를 어디에 놓을지
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: `docs/plans/corpbrain-v0.7-hybrid-search.md` + 필요 시 `docs/goals/*-loop.md` · `CLAUDE.md`

## 기존 관용구로 이미 정해져 있어 토픽에서 제외한 것

- **브랜치 명명** — `ROADMAP.md` §2의 `feat/*` 단기 브랜치 → PR → `main`. 버전은 tag.
- **커밋 프리픽스** — v0.5·v0.6이 쓴 `v0.7(core)`/`(wiring)`/`(test)`/`(docs)` 형식을 계승.
- **커밋 단위 green** — v0.6 X3에서 「모든 커밋이 green, 각 단위가 자기 단위테스트를 함께
  담는다」로 확정. 그대로 따른다.
- **계획 문서 형식** — v0.2·v0.6 플랜의 «U1~Un + `depends:` + 실행 웨이브 + 불변식» 형식.
- **`.xls`/`.ppt` 추출** — `ROADMAP.md` §5가 "완전히 독립적이라 순서 제약 없이 병렬"로
  이미 정했다. 이 라운드의 대상이 아니다.

RESOLVED: 5 / TOTAL: 5  ·  STOP: ALL_RESOLVED

- [x] Y1 | CORE  | #42(PR #45) 미머지 상태에서의 착수 경계 | status:RESOLVED | decision: #45 머지 후 `main`에서 분기해 착수. 대기 중엔 계획 문서만 쓰고 코드는 손대지 않는다 | applied: docs/plans/corpbrain-v0.7-hybrid-search.md 「착수 전제」
- [x] Y2 | CORE  | PR·브랜치 분할 단위 (단일 PR vs 다단계) | status:RESOLVED | decision: 단일 PR `feat/v0.7-hybrid-search`, 병렬 없음. 코어만 머지하면 호출자 없는 죽은 코드가 남는다 | applied: docs/plans/… 「브랜치·PR 전략」
- [x] Y3 | CORE  | 작업 단위 U1~Un과 실행 웨이브 | status:RESOLVED | decision: 계층 분해 10단위(U1~U10) · 6웨이브. 순수 계산은 `graph.py`, 저장소 조회·조립만 `search.py` | applied: docs/plans/… 「작업 단위」
- [x] Y4 | CORE  | α 실측 대기 구간을 PR·커밋 경계 어디에 놓나 | status:RESOLVED | decision: U9 완료 시 draft PR → 스윕 결과 도착 후 U10 커밋 → ready → 머지. 잠정값이 main에 들어가는 순간이 없다 | applied: docs/plans/… 「α 실측 대기 구간」
- [x] Y5 | MINOR | 계획 문서·goal 루프 문서를 무엇까지 남기나 | status:RESOLVED | decision: plan(정본) + goal 1개. goal의 1차 종료 조건은 「U9 green + draft PR」, U10은 후속 지시 | applied: docs/goals/corpbrain-v0.7-hybrid-search-loop.md 신규
