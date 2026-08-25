# Grill Ledger — v0.7 임베딩 모델 재판단 스펙

참조 범위: `static/docs/specs/features/corpbrain-v0.7-embedding-model-reassessment.md`
관심 방향: 스펙 전체의 미확정 세부사항
OUTPUT: 위 스펙 문서 + 본 원장

```
RESOLVED: 5 / TOTAL: 5
- [x] T1 | CORE  | 실측(5종 모델 pull·측정) 실행 주체              | depends:-  | status:RESOLVED | decision:사용자가 로컬에서 §4.4 측정 스크립트를 실행하고 원시 결과를 구현 세션에 전달한다(구현 세션은 pull·측정을 직접 하지 않는다) | applied:spec §2·§3-2·§4.4
- [x] T2 | CORE  | 코퍼스 확장 문서(14~24개) 작성 주체              | depends:-  | status:RESOLVED | decision:구현 세션이 기존 6문서와 동일한 합성 설계 원칙으로 작성한다(실제 업무 문서 사용 안 함) | applied:spec §3-1
- [x] T3 | CORE  | 참조쌍·고립문서 설계 노트의 정확한 기록 위치     | depends:T2 | status:RESOLVED | decision:`docs/smoke/README.md`에 기존 6문서 설계 기록에 이어서 확장분도 기록 | applied:spec §3-1
- [x] T4 | MINOR | 마이그레이션 안내 문구를 어디에 넣을지(릴리스노트/USAGE.md) | depends:- | status:RESOLVED | decision:docs/USAGE.md §13.5에만 명시, 릴리스 노트 별도 문구 없음 | applied:spec §3-5
- [x] T5 | MINOR | 코퍼스 목표 정확한 문서 수·참조쌍 수             | depends:T2 | status:RESOLVED | decision:24문서·6폴더·클러스터4개(클러스터당 최소 2문서 상호참조)·고립문서2개로 확정 | applied:spec §3-1
```
