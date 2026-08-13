# Grill Ledger — CorpBrain v0.2 (prescan · pdf)

- 대상 스펙: `static/docs/specs/features/corpbrain-v0.2-prescan-and-pdf.md`
- 참조 범위(A): 위 스펙 + 그 스펙이 재사용을 명시한 코어 이음새(`config.ScanConfig`, `scanner.scan_folder`, `extract.py`, `_progress.py`의 run-status rate)
- 관심 방향(B): 스펙이 "확정"이라 적었지만 구현을 **비결정적·임의적**으로 만드는 과소명세·내부 모순 지점
- 완료조건(C): 아래 토픽이 전부 RESOLVED
- OUTPUT(D): 스펙 문서(정본) + 하네스(CLAUDE.md 등) + 이 원장

RESOLVED: 8 / TOTAL: 8  ·  STOP: ALL_RESOLVED

- [x] T1 | CORE  | 중요도 점수 공식 | status:RESOLVED | decision:가중 합산 휴리스틱(base_ext + depth_adj + signal_bonus − noise_penalty, clamp 0~100, 내용 무읽기) | applied:스펙 §4.2
- [x] T2 | CORE  | plan_scan I/O 경계 + 예상시간 rate 출처 | status:RESOLVED | decision:정적 기본값만(실측 rate 보정 v0.3), plan_scan은 os.stat만 허용·open/소켓/영속상태 금지·Ollama 미질의 | applied:스펙 §2·§4.2
- [x] T3 | CORE  | 처리율 기본값 + HW 감지 | status:RESOLVED | decision:nvidia-smi subprocess(성공=GPU+label 이름, 실패/타임아웃=CPU); static_rate GPU=50·CPU=10 tok/s | applied:스펙 §4.2
- [x] T4 | CORE  | est_tokens 추정식 | status:RESOLVED | decision:chars_est=min(max_chars, size_bytes*cpb[ext]); cpb txt/md=0.5·docx=0.06·pdf=0.12; tokens_est=round(chars_est/2.5) | applied:스펙 §4.2
- [x] T5 | CORE  | PDF 스킵 사유 매핑 | status:RESOLVED | decision:pypdf 예외·암호화=ExtractionError→extraction_failed(detail), 빈 텍스트=empty_document, enum·DoD 불변 | applied:스펙 §4.1·§5
- [x] T6 | MINOR | plan과 --max 정책 | status:RESOLVED | decision:plan은 scan_folder(max_files=None)로 전량 계산·표시, --max는 초과 경고 신호(중단 아님) | applied:스펙 §5
- [x] T7 | MINOR | 리포트/배너 형식·TOP N | status:RESOLVED | decision:plan stdout=중요도 TOP 20행+…외 M건+합계+HW+초과경고; scan stderr 배너=예상 파일수·시간+중요도 TOP 3 | applied:스펙 §4.3
- [x] T8 | MINOR | plan 진입점·ScanConfig 재사용 | status:RESOLVED | decision:기존 ScanConfig 재사용(model/ollama_url/force 무시), 신규 값타입 ScanPlan/PlanEntry/HardwareInfo만 models.py에 추가 | applied:스펙 §4.2
