# Grill Ledger — v0.9 GUI (2라운드: 테스트 하네스 설계)

앞선 라운드: `GRILL_LEDGER-v0.9-gui.md`(스펙 계약 공백 13건) — ALL_RESOLVED.

- 참조 범위: `static/docs/specs/features/corpbrain-v0.9-gui.md` §3 ·
  `tests/security/test_network_invariant.py` · `tests/` 배치 관용구
- 관심 방향: GUI 서버를 무엇으로 어떻게 검증하는가 — §3 DoD가 요구하는 검증이 실제로
  성립하는 형태인가
- 착수 근거: **DoD 3번이 현재 감시장치로는 측정 불가능하다.** `watch_sockets`는
  `socket.socket.connect`·`socket.create_connection`만 패치해 **나가는 연결만** 보며,
  `bind`/`listen`은 보지 않는다. 게다가 `_fake_connect`가 `ConnectionRefusedError`를 던져
  이 fixture를 쓰는 테스트는 실제 연결 자체를 할 수 없다.
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: 스펙 §3 정정 + `CLAUDE.md` v0.9 불변식 + 본 원장

```
RESOLVED: 6 / TOTAL: 6
- [x] TH1 | CORE  | 서버 테스트가 실제 소켓을 여는가, 순수 함수를 부르는가 | status:RESOLVED | decision:요청 처리를 handle(method, path, headers, body) -> Response 순수 함수로 뽑고 http.server 핸들러는 그것을 부르기만 한다. 인증·라우팅·직렬화·상태코드는 소켓 없이 단언, 실제 소켓은 「뜨고 붙는다」만 최소 확인 | applied:스펙 §3·§4.10
- [x] TH2 | CORE  | 「듣는 소켓은 127.0.0.1뿐」을 무엇으로 단언하는가 | status:RESOLVED | decision:SocketWatcher를 bind까지 넓혀 주소를 기록·가로챈다(실제 바인드 안 함). 상수만 단언하는 방식 배제 | applied:스펙 §3 항목3, CLAUDE.md v0.9 불변식
- [x] TH3 | CORE  | watch_sockets 가 연결을 거부하는 성질과의 충돌 | status:RESOLVED | decision:기동 스모크는 fixture를 쓰지 않는다. watcher에 허용 목록 예외를 두지 않는다 — 예외는 늘어나고 불변식이 스스로 약해진다 | applied:스펙 §4.10.3, CLAUDE.md v0.9 불변식
- [x] TH4 | CORE  | SSE 무한 스트림을 테스트에서 읽고 끝내는 방법 | status:RESOLVED | decision:이벤트 시퀀스(코어 on_event)와 프레임 직렬화(format_sse 순수함수)를 나눠 각각 단언. 실제 스트림 통과·Response.body 이터레이터화 배제 | applied:스펙 §3 항목4, CLAUDE.md v0.9 불변식
- [x] TH5 | CORE  | 타이밍 의존 테스트(409·취소)를 결정적으로 만드는 법 | status:RESOLVED | decision:상태 주입 + 순수 판정. 409는 상태 판정이지 경합이 아니고, 취소는 「N번째 문서 뒤 True」 술어로 재현. sleep·Event·Barrier 전부 배제 | applied:스펙 §3 항목5·6, CLAUDE.md v0.9 불변식
- [x] TH6 | MINOR | GUI 테스트 파일 배치와 명명 | status:RESOLVED | decision:성격별 기존 자리에 분산(unit/ · 평면 test_gui*.py · security/ 기존 파일). tests/gui/·conftest.py 신설 배제 | applied:스펙 §3
```


**STOP: ALL_RESOLVED** — 6/6 (CORE 5 · MINOR 1)
