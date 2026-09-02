# Grill Ledger — v0.9 웹 GUI

- 참조 범위: `static/docs/specs/features/corpbrain-v0.9-web-gui.md`
- 관심 방향: 구현 착수 전 미해소 결정·모순·구현자가 임의 해석하게 될 빈틈
- 시작: 2026-09-01

```
RESOLVED: 8 / TOTAL: 8  ← ALL_RESOLVED (2026-09-01)
- [x] T1 | CORE  | 스캔 옵션을 UI에 어디까지 노출하는가 | status:RESOLVED | decision:3단 노출 — 항상 보임(폴더·엔진·모델) / 「고급」 접기(나머지 9개) / 미노출(out_dir·ollama_url) | applied:스펙 §4.7.1 신설 · CLAUDE.md v0.9 불변식
- [x] T2 | CORE  | 스캔 중 차단 범위 — 검색만인가 그래프·위키도인가 | status:RESOLVED | decision:검색만 409 차단 · 그래프·위키 조회는 허용하고 sqlite3.Error 흡수 · 위키 편집 저장은 409 | applied:스펙 §5 첫 항목 자원별 표로 확장 · CLAUDE.md v0.9 불변식
- [x] T3 | CORE  | 스캔 상태 스냅샷의 수명과 이력 보관 | status:RESOLVED | decision:진행 중은 메모리 · 종료 시 <out_dir>/.corpbrain_gui_lastrun.json 에 마지막 1회 · 이력 없음 · 기동 시 복원 | applied:스펙 §4.3.1 신설 · CLAUDE.md v0.9 불변식
- [x] T4 | CORE  | 러너 종료 레코드의 스키마 (ScanResult 직렬화) | status:RESOLVED | decision:ScanResult 전체를 손실 없이 · Path→절대경로 문자열 · StrEnum→값 · GraphStats 프로퍼티는 명시적으로 더함 · schema/finished_at/exit_code/workspace_id 추가 · schema 불일치는 무시 | applied:스펙 §4.4.1 신설 · CLAUDE.md v0.9 불변식
- [x] T5 | CORE  | 토큰을 요청의 어디에 싣는가 (헤더·쿼리·쿠키) | status:RESOLVED | decision:첫 진입만 URL · 이후 커스텀 헤더 · history.replaceState로 주소창에서 제거 · 쿠키/localStorage 금지 | applied:스펙 §4.6.1 신설 · CLAUDE.md v0.9 불변식
- [x] T6 | MINOR | 워크스페이스별 스캔 설정을 저장하는가 | status:RESOLVED | decision:workspaces.json 에 last_options 저장 · force·force_gates 는 제외해 매번 꺼진 채 시작 | applied:스펙 §4.5 필드 확장
- [x] T7 | MINOR | 정적 자산 조달 — 폰트와 gui_preview 취급 | status:RESOLVED | decision:웹폰트 없이 시스템 폰트 스택 · minimalist 를 corpbrain/gui/static/ 으로 복사(정본) · gui_preview/ 는 참고 자료로 보존 · 복사 시 스프링 y축 부호 버그 수정 | applied:스펙 §4.8.1 신설
- [x] T8 | MINOR | 릴리스 번호와 ROADMAP 갱신 | status:RESOLVED | decision:로드맵·USAGE만 지금 맞추고 pyproject 0.8.0 은 v0.8 릴리스 순서(#50→#51→0.8.0)에 맡긴다 | applied:ROADMAP §3 v0.9 행 · §5 v0.9 상세로 교체(v0.7은 §5.1 과거 기록) · §7 GUI 해소 표기 · USAGE §15 GUI 제외
```
