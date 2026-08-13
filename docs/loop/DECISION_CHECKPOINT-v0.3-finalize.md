# CorpBrain v0.3 마감 페이즈 — 의사결정 체크포인트 (조기 종료 카운터)

기존 문서(v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`)가 명확히 정하지 않은 신규 결정만
누적한다. 이전 구현 페이즈(`DECISION_CHECKPOINT.md`)와 분리한다.

- 임계: `CORE` ≥ 3 → STOP REASON: CORE_BUDGET · `MINOR` ≥ 10 → STOP REASON: MINOR_BUDGET
- 권위값 = 엔트리 줄 수: `grep -c '^- \[CORE\]' ...` / `grep -c '^- \[MINOR\]' ...`
- 형식(한 줄, append only): `- [CORE|MINOR] <결정> | 근거 | 관련 파일`

CORE: 0
MINOR: 0

## 엔트리 (append only)

STOP REASON: RELEASE_READY
완료: spec-check 9/9 · ruff clean · pytest 275 passed · 버전 0.3.0 · 실모델 스모크 위키 1개 생성 · PR #27 ready(36ebdfb).
NEXT(사용자 확인, 루프 밖): main merge → git tag v0.3.0 → GitHub Release(노트 BREAKING 명시).
