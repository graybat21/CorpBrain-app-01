# CorpBrain v0.4 구현 페이즈 — 의사결정 체크포인트 (조기 종료 카운터)

기존 문서(v0.4 스펙·`GRILL_LEDGER-v0.4.md`·`docs/ROADMAP.md`)가 명확히 정하지 않은 신규 결정만
누적한다.

- 임계: `CORE` ≥ 3 → STOP REASON: CORE_BUDGET · `MINOR` ≥ 10 → STOP REASON: MINOR_BUDGET
- 권위값 = 엔트리 줄 수: `grep -c '^- \[CORE\]' ...` / `grep -c '^- \[MINOR\]' ...`
- 형식(한 줄, append only): `- [CORE|MINOR] <결정> | 근거 | 관련 파일`

CORE: 0
MINOR: 1

## 엔트리 (append only)

- [MINOR] VectorStore 최소 계약(T1: upsert/delete/search/model_name)에 list_ids() 추가 | 원문/위키 삭제 시 고아 벡터를 가려내려면(§3 항목5) 저장된 doc_id 전체 열거가 필요 | corpbrain/core/vectorstore.py
