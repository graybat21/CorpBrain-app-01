# Grill Ledger — v0.9 GUI (4라운드: 구현 순서)

앞선 라운드: `GRILL_LEDGER-v0.9-gui.md`(계약 13) · `-test-harness.md`(6) ·
`-interaction.md`(7) — 셋 다 ALL_RESOLVED. 그 뒤 스펙 검토 14건이 반영됐다(커밋 `881cdb6`).

- 참조 범위: `static/docs/specs/features/corpbrain-v0.9-gui.md`(확정) · `corpbrain/core/` ·
  `tests/` · `.github/workflows/ci.yml` · `docs/plans/` 3종(관례)
- 관심 방향: **구현 순서** — 무엇을 어떤 차례로 만들고, 어디서 자르며, 각 단계의 완료를
  무엇으로 판정하는가
- 착수 근거: 이 슬라이스는 앞선 셋과 **표면의 성격이 다르다.** v0.7·v0.8은 「쪼갤 자리가
  없다」를 근거로 단일 PR이었지만(구현이 한 파일·한 명령에 몰려 있었다), v0.9는 코어 6종 ·
  서버 계층 전체 · 프론트 6화면 · 패키징 · CI 신규 단계 · 문서 4종을 동시에 건드린다.
  그 전례를 그대로 적용할 수 없으므로 절단면을 다시 정한다.
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: `docs/plans/corpbrain-v0.9-gui.md` + 필요한 하네스 + 본 원장

```
RESOLVED: 9 / TOTAL: 9
- [x] T1 | CORE  | PR 절단면 — 몇 개로 자르고 어디서 자르는가 | status:RESOLVED | decision:2 PR·수직 절단 — ① 코어+서버+대시보드 1화면(뜨는 GUI) ② 나머지 5화면+문서+릴리스. 계층 절단은 main에 호출자 없는 코드를 남겨 배제, 단일 PR은 리뷰 단위가 스펙 600줄어치가 되어 배제 | applied:docs/plans/corpbrain-v0.9-gui.md 「브랜치·PR 전략」
- [x] T2 | CORE  | 코어 변경 6종을 언제 넣는가 | status:RESOLVED | decision:순수 리팩터링(⑥)과 CLI가 공짜로 이득 보는 것(③)만 선행. 나머지 4종(①②④⑤)은 그것을 처음 부르는 커밋과 같은 커밋에 — v0.8이 SUPPORTED_EXTENSIONS 를 추출기와 같은 커밋으로 미룬 것과 같은 규율 | applied:docs/plans/corpbrain-v0.9-gui.md 「코어 변경 6종을 넣는 시점」
- [x] T3 | CORE  | 서버·프론트 진행 방식 | status:RESOLVED | decision:엄격한 수직 관통 — PR① 은 인프라 전체(인증·라우팅·SSE·패키징·프론트 골격·bind·CI)와 대시보드가 실제로 부르는 엔드포인트 2종만. 서버 계층 통째·조회까지 절충 둘 다 배제(호출자 없는 엔드포인트가 남거나 잣대가 둘로 갈린다) | applied:docs/plans/corpbrain-v0.9-gui.md 「PR ①의 범위」
- [x] T4 | CORE  | 화면 순서 (대시보드는 T3 로 PR① 확정, 남은 5개) | status:RESOLVED | decision:스캔 → 위키 → 그래프 → 검색 → 설정. 데이터 생산자(스캔)를 먼저, 그다음 링크의 도착지부터 — 죽은 버튼이 한 번도 생기지 않고 DoD 4·5·6·7 이 첫 화면에서 닫힌다 | applied:docs/plans/corpbrain-v0.9-gui.md 「PR ②의 화면 순서」
- [x] T5 | CORE  | 단계별 완료 판정 | status:RESOLVED | decision:DoD 12항목을 PR 별로 배분하고 PR 을 가로지르는 3항목(1·4·7)은 「PR① 몫 / PR② 몫」을 글자로 적는다. 기능+테스트+DoD 번호가 한 커밋, 매 커밋 green. v0.8 의 단위별 DoD 매핑 관용구 계승 | applied:docs/plans/corpbrain-v0.9-gui.md 「완료 판정」
- [x] T6 | MINOR | `bind` 감시장치 확장 시점 | status:RESOLVED | decision:corpbrain gui 가 서버를 띄우는 커밋과 같은 커밋. 먼저 세우면 측정 대상이 없어 공허하게 통과하고, v0.8 이 보안 케이스를 미룬 근거(측정 대상이 그제야 존재)는 여기서 이른 시점을 가리킨다 | applied:docs/plans/corpbrain-v0.9-gui.md 「bind 감시장치 확장 시점」
- [x] T7 | MINOR | CI wheel 빌드·기동 스모크 단계 추가 시점 | status:RESOLVED | decision:서버 기동 커밋 직후 별도 커밋(YAML 은 성격이 다르다). 이 저장소는 CI 에서 wheel 을 빌드해 본 적이 없고 -e 설치는 자산 배치 오류를 감추므로 가장 이른 시점에 넣는다 | applied:docs/plans/corpbrain-v0.9-gui.md 「CI wheel 단계 추가 시점」
- [x] T8 | MINOR | 문서 4종 갱신 시점 | status:RESOLVED | decision:PR 마다 마지막 단위에서 그 PR 몫만. 전례(마지막에 몰아서)가 성립한 것은 단일 PR 이라 머지 시점이 하나뿐이었기 때문 — PR 이 둘이면 각 머지 시점마다 문서가 맞아야 한다. DoD 11 은 PR① 로 이동 | applied:docs/plans/corpbrain-v0.9-gui.md 「문서 갱신 시점」 + T5 배분표 정정
- [x] T9 | MINOR | 수동 스모크 K 와 릴리스의 배치 | status:RESOLVED | decision:스모크는 PR② ready 조건(세션이 기계 관측 3항목, 사용자가 눈 판정 3항목 — v0.7 이 역할 분담 조항을 실제와 어긋난 채 남긴 전례를 반복하지 않는다), 릴리스는 머지 후 별도 PR③ | applied:docs/plans/corpbrain-v0.9-gui.md 「수동 스모크 K와 릴리스」
```


**STOP: ALL_RESOLVED** — 9/9 (CORE 5 · MINOR 4)
