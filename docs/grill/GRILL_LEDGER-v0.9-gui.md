# Grill Ledger — v0.9 GUI (로컬 서버 + 브라우저 프론트엔드)

- 참조 범위: `static/docs/specs/features/corpbrain-v0.9-gui.md` (+ 근거 확인용으로 `corpbrain/core/`, 기존 v0.4~v0.8 스펙)
- 관심 방향: 구현 착수 전 남은 결정 — 코어 계약 변경 · 서버 계약 · 저장소 접근 · 화면이 노출할 파라미터
- 완료 조건: 아래 토픽 전부 RESOLVED
- OUTPUT: `static/docs/specs/features/corpbrain-v0.9-gui.md` + `CLAUDE.md` 불변식 + 본 원장

```
RESOLVED: 13 / TOTAL: 13
- [x] T1  | CORE  | 취소 훅의 형태와 시그니처 | status:RESOLVED | decision:`should_cancel: Callable[[], bool] | None = None` — 순수 술어. threading.Event·on_event 반환값 모두 배제. 술어 예외는 삼키지 않는다 | applied:스펙 §4.7, CLAUDE.md 「v0.9 GUI 불변식」 신설
- [x] T2  | CORE  | 취소 시 그래프 단계(패스2·3)를 수행하는가 | status:RESOLVED | decision:건너뛰고 즉시 반환. doc_facts가 패스1에서 이미 저장되므로 다음 scan이 재요약 없이 자동 회복한다(실측 확인). 그 창을 「그래프 미반영」으로 보고 | applied:스펙 §4.7, CLAUDE.md v0.9 불변식
- [x] T3  | CORE  | 취소 사실을 ScanResult에 담는가 | status:RESOLVED | decision:`ScanResult.cancelled: bool = False` 최상위 필드(9→10). GraphOutcome 안에 숨기지 않는다. v0.6 「9필드 유지」의 근거는 그래프 지표에 한정되므로 위반이 아니다 | applied:스펙 §4.7, CLAUDE.md v0.9 불변식
- [x] T4  | CORE  | 그래프 단계 진행 이벤트의 종류와 진행률 표현 | status:RESOLVED | decision:3종 신설(GraphStarted / RelatedInjected(index,total,path) / GraphFinished(stats)). 진행률은 패스3에만. Stage enum 재사용 배제 | applied:스펙 §4.7, CLAUDE.md v0.9 불변식
- [x] T5  | CORE  | SSE 재접속 시 놓친 이벤트 처리 | status:RESOLVED | decision:접속 즉시 StatusSnapshot 1회 송신 후 실시간 이벤트. 버퍼·리플레이 배제. 로그 줄은 복원되지 않는 알려진 한계 | applied:스펙 §4.3, CLAUDE.md v0.9 불변식
- [x] T6  | CORE  | 토큰을 후속 요청에 싣는 방식 (EventSource 제약) | status:RESOLVED | decision:쿼리 토큰을 첫 접속에서 HttpOnly·SameSite=Strict 쿠키로 교환하고 URL에서 지운다. Authorization 헤더·쿼리 반복·경로 이원화 모두 배제 | applied:스펙 §4.2, CLAUDE.md v0.9 불변식
- [x] T7  | CORE  | 전체 그래프 조회 — GraphStore 10멤버를 넓히는가 | status:RESOLVED | decision:iter_edges() 1개 추가로 11멤버. 노드는 기존 degree_ranking()+nodes_of()로 충분. N+1+중복제거를 조회 어댑터에 두지 않는다 | applied:스펙 §4.3·§4.3.1 신설, CLAUDE.md v0.9 불변식
- [x] T8  | CORE  | 코어 예외 → HTTP 상태코드 매핑 규칙 | status:RESOLVED | decision:상태코드는 프로토콜 층만(401/403/409/404/405). 도메인 예외는 200+구조화 본문, 버그만 500. CLI exit 코드 미탑재 | applied:스펙 §4.3.2 신설, CLAUDE.md v0.9 불변식
- [x] T9  | CORE  | GUI가 노출하는 스캔·검색 파라미터의 범위 | status:RESOLVED | decision:전부 노출하되 앞면/고급 접기로 이원화. 실측 확정 상수는 고급으로. 검증은 코어가 소유 | applied:스펙 §4.3.3 신설, CLAUDE.md v0.9 불변식
- [x] T10 | MINOR | 정적 자산의 wheel 포함 방식 | status:RESOLVED | decision:corpbrain/gui/static/ (패키지 안) + importlib.resources. force-include 배제 — 개발/wheel 설치 경로가 갈리지 않게 | applied:스펙 §4.10.1 신설
- [x] T11 | MINOR | 첫 실행(위키 폴더 부재) 화면 처리 | status:RESOLVED | decision:화면별 빈 상태 + 스캔 유도. 탭 잠금·강제 이동 배제. §4.3.2 규칙이 그대로 적용되는 경우로 다룬다 | applied:스펙 §5
- [x] T12 | MINOR | gui_preview/ 목업 자산의 처분 | status:RESOLVED | decision:전부 그대로 둔다. 위상은 스펙이 가른다(정본=corpbrain/gui/, gui_preview=토큰 참조원+설계 이력). 어긋남은 수용하는 대가로 기록 | applied:스펙 §4.10.2 신설
- [x] T13 | MINOR | ~/.corpbrain/config.json 동시 쓰기 (GUI ↔ CLI) | status:RESOLVED | decision:직전 재읽기 + 자기 섹션만 교체 + 임시파일 rename. 양쪽 섹션에 적용. 파일 락·파일 분리 배제. 잔여 레이스는 알려진 한계 | applied:스펙 §4.8, CLAUDE.md v0.9 불변식
```


**STOP: ALL_RESOLVED** — 13/13 (CORE 9 · MINOR 4)
