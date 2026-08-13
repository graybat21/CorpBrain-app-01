# CorpBrain v0.2 의사결정 로그 (조기 종료 체크포인트)

대상: `docs/goals/corpbrain-v0.2-prescan-and-pdf-loop.md` / 플랜: `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`

- 권위값 = 아래 엔트리 줄 수:
  - `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_v0.2.md`
  - `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_v0.2.md`
- 임계: CORE ≥ 2 → CORE_BUDGET, MINOR ≥ 8 → MINOR_BUDGET

## 엔트리 (append only)
- [MINOR] D-001 | U3 | agent:orchestrator | 2026-08-13T00:00:00+09:00 | nvidia-smi HW 감지는 `nvidia-smi --query-gpu=name --format=csv,noheader`로 이름 1줄을 얻고 타임아웃 2.0초로 호출(부재/실패/타임아웃=CPU) | 근거: 스펙 §4.2는 "짧은 타임아웃"으로만 명시해 구체 쿼리 플래그·타임아웃 값을 확정해야 함
