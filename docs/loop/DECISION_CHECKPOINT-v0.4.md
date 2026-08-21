# CorpBrain v0.4 구현 페이즈 — 의사결정 체크포인트 (조기 종료 카운터)

기존 문서(v0.4 스펙·`GRILL_LEDGER-v0.4.md`·`docs/ROADMAP.md`)가 명확히 정하지 않은 신규 결정만
누적한다.

- 임계: `CORE` ≥ 3 → STOP REASON: CORE_BUDGET · `MINOR` ≥ 10 → STOP REASON: MINOR_BUDGET
- 권위값 = 엔트리 줄 수: `grep -c '^- \[CORE\]' ...` / `grep -c '^- \[MINOR\]' ...`
- 형식(한 줄, append only): `- [CORE|MINOR] <결정> | 근거 | 관련 파일`

CORE: 0
MINOR: 3

## 엔트리 (append only)

- [MINOR] VectorStore 최소 계약(T1: upsert/delete/search/model_name)에 list_ids() 추가 | 원문/위키 삭제 시 고아 벡터를 가려내려면(§3 항목5) 저장된 doc_id 전체 열거가 필요 | corpbrain/core/vectorstore.py
- [MINOR] Ollama 임베딩 엔드포인트로 /api/embeddings(단일 prompt) 채택, /api/embed(배치) 미사용 | 문서당 벡터 1개·청크 없음 결정과 1:1 대응, summarize.py의 /api/generate 패턴과 형태 일관 | corpbrain/core/llm/embed.py
- [MINOR] SearchResult를 (doc_id, score, metadata: dict) 형태의 범용 값 타입으로 설계 | VectorStore가 저장 내용을 알 필요 없이 어댑터 무관하게 동작하도록, 도메인 필드(title 등)는 상위(search 렌더링)에서 dict로 해석 | corpbrain/core/models.py

STOP REASON: ALL_DONE
완료: v0.4 스펙 "완료의 정의" 12개 항목 모두 구현. `uv run ruff check .` clean, `uv run pytest` 313 passed / 6 skipped.
실제 로컬 Ollama(nomic-embed-text 설치됨)로 `corpbrain doctor` 수동 스모크 성공(전 항목 OK). `corpbrain scan`
실제 모델 스모크는 이 머신의 기존 GPU/CUDA 드라이버 결함(`docs/USAGE.md` §11에 이미 문서화된 "CUDA error ...
unsupported toolchain")으로 요약·임베딩 양쪽 다 HTTP 500을 내 완주하지 못했다 — v0.4 코드와 무관한 로컬
환경 문제이며, `embed()`가 그 500 실패를 EmbeddingError로 올바르게 흡수하는 것은 직접 확인했다.
CORE 0 / MINOR 3(예산 내), turn cap 미도달.
NEXT(사용자 확인, 루프 밖): draft PR 리뷰 → main merge → (선택) CUDA_VISIBLE_DEVICES=-1로 Ollama 재기동 후
실제 scan 스모크 재시도 → 버전 범프(0.3.0→0.4.0) → git tag v0.4.0 → GitHub Release(BREAKING 명시).
