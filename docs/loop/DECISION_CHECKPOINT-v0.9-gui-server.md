# 의사결정 체크포인트 — v0.9 GUI PR ① (`feat/v0.9-gui-server`)

정본 3종(스펙 `static/docs/specs/features/corpbrain-v0.9-gui.md` · 실행 플랜
`docs/plans/corpbrain-v0.9-gui.md` · grill 원장 3종)에 확정돼 있지 **않은** 추가 의사결정만
여기에 기록한다. 분류는 CORE(아키텍처·보안·외부의존·데이터 모델) / MINOR(네이밍·디렉터리·
로그 포맷·문구)이며, 엔드포인트 경로 문자열과 응답 필드 이름은 스펙 「미결정 사항」이 구현에
위임한 것이므로 **MINOR** 로 센다.

CORE: 1
MINOR: 5

## 기록

### M1 — 공유 설정 쓰기 헬퍼를 신규 모듈 `corpbrain/core/configstore.py`에 둔다 (MINOR · U1)

스펙 §4.8은 「그 쓰기 절차를 `gui`·`cloud_consent` 두 섹션이 공유하는 헬퍼 하나로 뽑아 쓴다」
까지만 정하고 **어디에 둘지는 정하지 않았다.** `consent.py`에 남기면 GUI 설정이 「동의」라는
이름의 모듈을 import 하게 되어 모듈명이 내용과 갈린다. 파일 경로 상수(`CONFIG_DIR_NAME`·
`CONFIG_FILENAME`·`default_config_path()`)도 함께 옮기고 `consent.py`가 재수출해, 기존
호출부(`corpbrain/core/__init__.py`·테스트 4파일)는 한 줄도 고치지 않는다.

### M2 — 공유 헬퍼가 올릴 예외 클래스를 인자(`error_type`)로 받는다 (MINOR · U1)

`update_section()`이 `ConfigStoreError`를 올리게 두면 `pytest.raises(ConsentStoreError)`로
단언하는 기존 테스트 4건이 깨진다(상위 클래스는 하위 클래스 단언을 만족시키지 못한다). 동의
경로가 v0.5부터 공표해 온 예외 종류를 그대로 유지하려고 `error_type` 기본값 인자를 둔다 —
`ConsentStoreError`는 `ConfigStoreError`의 하위이므로 계층은 하나로 유지된다.

### M3 — 도메인 응답 본문은 `{"error": <클래스명>, "message": <안내 문장>}` 두 필드다 (MINOR · U3)

스펙 §4.3.2는 「예외 종류 식별자와 사용자 안내 문장을 각각 필드로 담고 식별자는 예외
클래스명을 그대로 쓴다」까지만 정했다. 필드 이름을 `error`·`message`로 정하고, 성공 응답은
`error` 키를 갖지 않게 해 프론트가 `"error" in body` 하나로 가른다. 404·405·500도 같은 두
필드를 쓴다 — 프로토콜 층 사건과 도메인 상태는 **상태코드**로 갈리므로 본문 모양까지 두
벌로 둘 이유가 없다.

### M4 — GUI 모듈을 `corpbrain/gui/` 아래 성격별로 나눈다 (MINOR · U3)

`api.py`(소켓을 모르는 `handle()`·인증·라우팅·직렬화) · `sse.py`(프레임 직렬화) ·
`assets.py`(정적 자산 탐색) · `httpd.py`(소켓 계층). 스펙 §4.10.3이 요구한 것은 「요청 처리가
순수 함수이고 `http.server` 핸들러는 그것을 부르기만 한다」는 경계 하나이며, 파일 나눔은
그 경계를 파일 경계로도 드러낸 것이다. 정적 자산은 §4.10.1이 정한 대로
`corpbrain/gui/static/` 에 둔다.

### C1 — 관문 불변식의 정적 검사에 「인바운드 허용 목록」을 파일·이름 단위로 연다 (CORE · U4)

`tests/test_gateway.py`의 「관문 외 어떤 모듈도 네트워크 라이브러리를 직접 import 하지
않는다」는 `http.*` 전체를 막으므로, GUI 서버가 쓰는 `http.cookies`(U4)와 `http.server`(U7)를
그대로 통과시킬 수 없다. 스펙은 이 상황을 다루지 않았다 — v0.9 이전까지 이 저장소에는
**듣는 소켓**이 하나도 없었기 때문이다.

**모듈 전체를 면제하지 않고 파일별·이름별로 연다.** 이 불변식이 지키는 것은 「나가는 연결은
전부 관문을 통과한다」이고 GUI 서버는 반대 방향이므로 방향이 다른 이름만 열되,
`urllib.request`·`requests`·`httpx`·`aiohttp`·`urllib3`·`ssl` 같은 **나가는** 라이브러리는
`corpbrain/gui/` 안에서도 그대로 막힌다. 허용 목록이 나가는 라이브러리를 열지 않았음을
단언하는 케이스를 함께 둔다 — `test_watcher_flags_a_gateway_bypass`가 소켓 감시에 대해 하는
일과 같은 종류의 「감시장치가 공허하지 않음」 증명이다.

`corpbrain/gui/`를 통째로 제외하는 방식은 택하지 않았다. 그러면 GUI 어댑터가 관문을 우회해
외부를 호출해도 아무도 잡지 못한다.

### M5 — 부트스트랩 토큰과 세션 쿠키 값에 **서로 다른 비밀**을 쓴다 (MINOR · U4)

스펙 §4.2는 「부트스트랩 토큰을 첫 접속에서 `HttpOnly` 세션 쿠키로 교환한다」까지만 정하고
쿠키 값이 무엇인지는 정하지 않았다. 기동 시 `secrets.token_urlsafe(32)`로 두 값을 따로
만든다 — 프론트엔드가 `history.replaceState`로 URL을 지운 뒤, 브라우저 히스토리·리퍼러에
남은 부트스트랩 토큰이 세션 쿠키 값과 같지 않다. 쿠키 이름은 `corpbrain_session`이다.
