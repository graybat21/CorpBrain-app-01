# CorpBrain v0.2 의사결정 로그 (조기 종료 체크포인트)

대상: `docs/goals/corpbrain-v0.2-prescan-and-pdf-loop.md` / 플랜: `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`

- 권위값 = 아래 엔트리 줄 수:
  - `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_v0.2.md`
  - `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_v0.2.md`
- 임계: CORE ≥ 2 → CORE_BUDGET, MINOR ≥ 8 → MINOR_BUDGET

## 엔트리 (append only)
