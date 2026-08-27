# Grill Ledger — v0.8 `.xlsx`/`.xlsm`/`.pptx` 텍스트 추출

- 참조 범위: `static/docs/specs/features/corpbrain-v0.8-xlsx-pptx-extraction.md` +
  `corpbrain/core/{extract,config,plan,scanner}.py` · `tests/`
- 관심 방향: 구현 착수(`docs/plans/` 작업 계획) 전에 남은 결정 모호함
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: v0.8 스펙 · `CLAUDE.md` · 본 원장

RESOLVED: 7 / TOTAL: 7

- [x] T1 | CORE  | 내용이 없는 시트·슬라이드에도 경계 줄을 내는가 (완료의 정의 3과 충돌) | status:RESOLVED | decision:내용이 있을 때만 낸다 — 빈 판정 책임을 호출자 한 곳에 유지하고 완료의 정의 3을 성립시킨다 | applied:spec §4.2·§3(2·3), CLAUDE.md 「v0.8 오피스 포맷 추출 불변식」 신설
- [x] T2 | CORE  | 셀 값의 문자열화 규칙 — 날짜·숫자·`None`·빈 행 | status:RESOLVED | decision:타입별 최소 규칙 4줄(날짜 YYYY-MM-DD · 정수값 float 소수점 제거 · bool · None=빈 문자열) + 빈 행 건너뜀 + 행 끝 탭 제거. number_format 해석 안 함 | applied:spec §4.2 표 추가
- [x] T3 | CORE  | `read_only=True` 와 「숨긴 행 제외」가 양립하지 않을 때의 처리 | status:RESOLVED | decision:구현 첫 단계에서 확인 — 가능하면 시트·행 모두 제외, 불가하면 시트만 제외하고 DoD 2에서 행 단언 제외. read_only 포기는 택하지 않는다 | applied:spec §4.2 조건부 표 · §3 항목2
- [x] T4 | CORE  | 암호화를 손상과 구분해 판정할 수단 (완료의 정의 5의 detail 단언) | status:RESOLVED | decision:열기 실패 시에만 앞 8바이트 OLE 시그니처 확인 — detail 은 '암호화되었거나 구형 이진 포맷' 으로 두 원인을 함께 적는다. 예외 메시지 매칭 금지 | applied:spec §4.3 표 · §4.3.1 신설 · §3 항목5(픽스처 방법 포함)
- [x] T5 | MINOR | 확장자 디스패치 구조 — if-체인 유지 vs 매핑 전환 | status:RESOLVED | decision:dict 매핑으로 전환하고 '매핑 키 집합 == SUPPORTED_EXTENSIONS' 를 단위테스트로 단언 | applied:spec §4.2 · §3 항목7
- [x] T6 | MINOR | 테스트 픽스처 헬퍼 배치 — 복제 vs 공유 | status:RESOLVED | decision:.pdf 선례대로 단위·통합에 각각 복제. conftest.py·공유 헬퍼 모듈 신설 안 함 | applied:spec §3 픽스처 구성
- [x] T7 | MINOR | PPTX 노트 접근 관용구 (`has_notes_slide` 가드 여부) | status:RESOLVED | decision:has_notes_slide 로 가드한 뒤에만 접근 — 읽기 연산이 객체를 만드는 부작용을 피한다. 노트가 공백뿐이면 [노트] 줄도 내지 않는다 | applied:spec §4.2 PPTX

STOP: ALL_RESOLVED
