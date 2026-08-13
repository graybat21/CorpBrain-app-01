# Grill Ledger — CorpBrain v0.3 (자원 게이팅 · Ollama doctor)

- 대상 스펙: `static/docs/specs/features/corpbrain-v0.3-resource-gating-and-ollama-doctor.md`
- 참조 범위(A): 위 스펙 + 그것이 건드리는 코어 이음새(`cli.py` 프리플라이트·종료코드, `core/plan.py` plan_scan·detect_hardware, `core/llm/ollama_client.py` detect, `core/gateway.py`, `core/report.py`, `core/config.py`, `core/models.py` SkipReason)
- 관심 방향(B): 스펙이 "확정"이라 적었지만 구현을 **비결정적·임의적**으로 만드는 과소명세·내부 순서 모순 지점
- 완료조건(C): 아래 토픽이 전부 RESOLVED
- OUTPUT(D): 스펙 문서(정본) + 하네스(CLAUDE.md·USAGE.md 등) + 이 원장

RESOLVED: 7 / TOTAL: 7  ·  STOP: ALL_RESOLVED

- [x] T1 | CORE  | 프리플라이트 점검 순서 & 복수 위반 시 표면화 우선순위(GPU/토큰/Ollama/모델) | status:RESOLVED | decision:환경→자원 fail-fast(폴더→Ollama→모델→GPU→토큰), 첫 위반 즉시 종료, --force-gates는 GPU·토큰만 우회, plan은 2·3 생략·네트워크0, doctor는 집계 | applied:스펙 §4.2·§5
- [x] T2 | CORE  | 모델 이름 매칭 규칙(/api/tags name ↔ --model, 태그 정규화) | status:RESOLVED | decision:태그 정규화 후 정확 일치(무태그→:latest 보정), 접두·부분 매칭 금지, 대소문자 구분 | applied:스펙 §4.3
- [x] T3 | CORE  | 게이트 판정 코어 API 형태 & 진단 모듈 배치 | status:RESOLVED | decision:models.py에 GateVerdict(gpu_ok/tokens_ok/oversized_count/임계에코) 추가·ScanPlan.gate 필드, plan_scan이 순수 계산; 신규 core/environment.py가 shutil.which+doctor 조립, 모델 매칭은 ollama_client(네트워크-순수) | applied:스펙 §4.4
- [x] T4 | CORE  | 토큰 예산(total_est_tokens) 산정 대상 — 스킵 예정 파일 포함/제외 | status:RESOLVED | decision:요약될 파일만 합산 — 미지원·file_too_large(size>max_file_size) 제외, 대용량은 oversized_count로 별도 표시 | applied:스펙 §4.2·§4.4
- [x] T5 | MINOR | doctor 출력 형식 & 미설치/미구동/모델없음 안내 문자열(설치 URL 포함 여부) | status:RESOLVED | decision:한국어 stdout 체크리스트(설치→구동→모델→GPU→임계), 실패 줄에 해결 명령(설치 URL·ollama serve·ollama pull), GPU는 경고 줄, URL·명령은 평문(네트워크 아님) | applied:스펙 §4.3
- [x] T6 | MINOR | plan/scan 리포트·배너의 게이트 판정 렌더 위치·형식 | status:RESOLVED | decision:report.py 담당 — build_plan_report_lines에 게이트 섹션, build_scan_banner_lines에 한 줄 요약, scan 차단 시 stderr에 발동 게이트+해결책(--force-gates/--max-file-size) | applied:스펙 §4.3
- [x] T7 | MINOR | BREAKING·신기능 사용법 문서화 위치(USAGE.md/릴리스 노트) | status:RESOLVED | decision:docs/USAGE.md의 v0.3 섹션 + GitHub Release(tag v0.3) 노트에 BREAKING 명시(문서 갱신은 구현 시점) | applied:스펙 §3(DoD 9)
