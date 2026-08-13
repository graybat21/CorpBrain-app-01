# CorpBrain v0.3 마감 페이즈 — 의사결정 체크포인트 (조기 종료 카운터)

기존 문서(v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`)가 명확히 정하지 않은 신규 결정만
누적한다. 이전 구현 페이즈(`DECISION_CHECKPOINT.md`)와 분리한다.

- 임계: `CORE` ≥ 3 → STOP REASON: CORE_BUDGET · `MINOR` ≥ 10 → STOP REASON: MINOR_BUDGET
- 권위값 = 엔트리 줄 수: `grep -c '^- \[CORE\]' ...` / `grep -c '^- \[MINOR\]' ...`
- 형식(한 줄, append only): `- [CORE|MINOR] <결정> | 근거 | 관련 파일`

CORE: 0
MINOR: 0

## 엔트리 (append only)
