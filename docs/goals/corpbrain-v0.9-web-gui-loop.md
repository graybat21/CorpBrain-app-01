/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.9-web-gui.md` 의 「완료의 정의」(§3) **12개 항목을 모두 충족**하도록 로컬 웹 GUI를 구현해, `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되고 `uv run corpbrain gui --no-browser` 가 `127.0.0.1` 에 바인딩된 서버를 띄우게 한다.
- 시작 지점: 현재 작업 트리의 HEAD 상태. **이 작업 트리는 git 저장소가 아니다**(`git rev-parse --is-inside-work-tree` 가 `fatal: not a git repository` 를 낸다). 착수 시 이 명령을 한 번 실행해 확인하고, 결과에 따라 §2 의 「버전 관리 분기」를 따른다.
- 작업 대상:
  - 신규 `corpbrain/gui/` — `__init__.py` · `server.py` · `runner.py` · `workspaces.py` · `markdown.py` · `static/`
  - 기존 `corpbrain/cli.py` — `gui` 서브커맨드 추가 (코어는 건드리지 않는다)
  - 신규 테스트 — `tests/test_gui_server.py` · `tests/unit/test_gui_markdown.py` · `tests/unit/test_gui_workspaces.py`
  - 기존 테스트 1건 — `tests/security/test_network_invariant.py` 에 케이스 **추가**
  - 문서 — `docs/USAGE.md` · `docs/SMOKE.md` · `README.md`
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 `pyproject.toml` 의 `version` 범프, 신규 런타임 의존성 추가, `git tag`·릴리스 생성은 하지 않는다.

## 2) 작업 세부 규칙

### 정본 문서
세부 구현 계약은 아래 셋을 정본으로 삼아 그대로 구현한다. **스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.**
- `static/docs/specs/features/corpbrain-v0.9-web-gui.md` — §3 완료의 정의 · §4 인터페이스 계약(§4.3.1 스냅샷 수명 · §4.4.1 종료 레코드 · §4.6.1 토큰 전달 · §4.7.1 옵션 노출 · §4.8.1 정적 자산 포함) · §5 엣지 케이스
- `docs/grill/GRILL_LEDGER-v0.9-web-gui.md` — 확정 결정 8건 (전부 ALL_RESOLVED)
- `CLAUDE.md` 의 「v0.9 웹 GUI 불변식」 — 구현 중 유지할 13개 항목

### 작업 순서 — W1 → W8
**이 슬라이스에는 별도 실행 플랜 문서가 없다.** 아래 8단위를 순서대로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다. 병렬 서브에이전트를 쓰지 않는다 — W4~W7 이 `server.py` 를 똑같이 통과한다.

- **W1 서버 골격** — `corpbrain/gui/server.py` 의 `ThreadingHTTPServer`, `127.0.0.1` 고정 바인딩, 포트 자동 선택, 랜덤 토큰 생성, `corpbrain/cli.py` 에 `gui` 서브커맨드(`--port`·`--no-browser`), 브라우저 자동 오픈. → 스펙 §3 항목1
  - **`cli.main()` 의 if 체인 끝은 무조건 `_run_scan(args)` 로 떨어진다.** `gui` 분기를 그 앞에 넣지 않으면 조용히 스캔이 돈다.
- **W2 보호 계층** — 토큰 검증(커스텀 헤더), `Host` 헤더 검증, 401/403 매핑, 첫 진입만 URL 쿼리스트링 허용. → 스펙 §3 항목2 · §4.6.1
- **W3 워크스페이스 저장소** — `corpbrain/gui/workspaces.py`, `~/.corpbrain/workspaces.json` 원자적 쓰기(임시 파일 → `fsync` → `os.replace`), `last_options`(단 `force`·`force_gates` 제외), 폴더 탐색 API. → 스펙 §4.5 · §4.7
- **W4 러너** — `corpbrain/gui/runner.py`(`python -m` 진입), stdin JSON 입력, stdout JSON 라인 이벤트, §4.4.1 종료 레코드 직렬화, `<out_dir>/.corpbrain_gui_lastrun.json` 기록·복원. → 스펙 §3 항목3·5 · §4.3.1 · §4.4
  - **`GraphStats.nodes`·`edges` 는 프로퍼티라 `dataclasses.asdict()` 에 담기지 않는다.** 명시적으로 더하지 않으면 화면 총계가 조용히 빈다.
- **W5 스캔 API** — `POST/GET/DELETE /api/scan`, 자식 프로세스 기동·1초 폴링용 스냅샷(`_progress.reduce()`)·중지, 동시 스캔 409, 서버 종료 시 자식 동반 종료. → 스펙 §3 항목3·5 · §5
- **W6 조회 API** — dashboard · plan · search · wiki 트리 · graph · doctor · cloud settings. 스캔 중 **검색만 409**, 그래프·위키는 허용하고 `sqlite3.Error` 를 안내로 흡수. → 스펙 §3 항목4 · §4.7 · §5
- **W7 마크다운 렌더러와 위키 편집** — `corpbrain/gui/markdown.py`(헤딩·불릿·링크·인라인 코드·문단·front-matter 분리), **HTML 이스케이프**, 편집 저장 시 `corpbrain:related` 마커 보존 검증(없으면 400, 파일 미변경), 스캔 중 편집 저장 409. → 스펙 §3 항목8·9 · §4.9
- **W8 프론트엔드·테스트·문서** — `gui_preview/variants/minimalist` 를 `corpbrain/gui/static/` 으로 **복사**(원본은 보존), 1축 레이아웃으로 개편(상단 탭 제거 · 메뉴 3개 · 탐색 통합 화면), 시스템 폰트 스택, 토큰 헤더 주입과 `history.replaceState`, **스프링 힘 y축 부호 버그 수정**(`b.vy += …` → `-=`), `tests/security/test_network_invariant.py` 케이스 추가, `docs/SMOKE.md` 체크리스트, `docs/USAGE.md`·`README.md` 갱신. → 스펙 §3 항목6·7·10·12 · §4.8.1

### 버전 관리 분기
- `git rev-parse --is-inside-work-tree` 가 **성공하면**: `feat/v0.9-web-gui` 브랜치를 만들어 작업하고, 커밋 메시지 프리픽스는 `v0.9(gui):` W1~W7 / `v0.9(ui):` W8 프론트엔드 / `v0.9(test):` 테스트 / `v0.9(docs):` 문서 로 한다. 모든 커밋이 green 이어야 한다 — 각 단위 커밋은 자기 단위테스트를 함께 담는다.
- **실패하면**(현재 상태): 브랜치·커밋·PR 관련 규칙을 전부 건너뛰고 **파일 변경만으로 진행한다.** `git`·`gh` 명령을 종료 방법의 증명 수단으로 쓰지 않는다. 이 경우 변경 범위 증명은 `ls -R corpbrain/gui` 와 `uv run pytest -k gui -v` 로 대신한다.

### 의사결정 기록
- 위 정본 셋에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.9.md` 에 기록한다.
- 각 항목을 CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.

### 도구
- 실행은 `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`, `uv run corpbrain ...`).
- **`uv add` 를 쓰지 않는다.** 이 슬라이스는 신규 런타임 의존성이 0개다(스펙 §4.2).

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `static/docs/specs/features/corpbrain-v0.9-web-gui.md` 가 존재하지 않음 → STOP REASON: NO_SPEC (착수 전 확인)
  - `docs/loop/DECISION_CHECKPOINT-v0.9.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - 스펙 §3 의 완료의 정의를 충족하려면 **코어(`corpbrain/core/`)를 고쳐야만 한다고 판단됨** → STOP REASON: CORE_CHANGE_REQUIRED (고치지 말고 멈춰 사용자에게 알린다)
  - W1~W8 이 끝나고 완료의 정의 §3 항목 1~12 가 충족되며 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 45회 도달 → STOP REASON: TURN_CAP (= or stop after 45 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.9.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드 출력을 대화에 남겨 증명한다.
  3) `uv run pytest -k gui -v` 를 실행해 이 슬라이스 고유 항목의 통과가 보이는 출력을 대화에 남긴다 — 토큰 없는 요청 401 · 위조 `Host` 403 · 스캔 중 검색 409 · 마커 없는 편집 저장 400 · `<script>` 이스케이프 · 중지 후 자식 프로세스 종료.
  4) `grep -rnE "https?://" corpbrain/gui/static/` 를 실행해 **0 matches** 인 출력을 대화에 남긴다(스펙 §3 항목6 — 외부 URL 0건).
  5) `uv run corpbrain gui --no-browser` 를 5초 이내에 종료시키며 실행해, stderr 에 `127.0.0.1` 접속 URL 한 줄이 보이는 출력을 대화에 남긴다.
  6) `cat docs/loop/DECISION_CHECKPOINT-v0.9.md` 로 `CORE: N` · `MINOR: M` 카운터 줄과 `STOP REASON:` 줄을 남긴다.
  7) `ls -R corpbrain/gui` 로 신규 생성된 파일 목록을 남긴다.

## 4) 기타 제약조건
- **`corpbrain/core/` 아래 어떤 파일도 수정하지 않는다.** 코어 수정이 필요해 보이면 고치지 말고 STOP REASON: CORE_CHANGE_REQUIRED 로 멈춘다. 스펙 §2 가 「코어 수정」을 비목표로 못박았고, `tests/test_core_api_smoke.py` 가 `run_scan` 파라미터 목록을 정확히 일치로 단언한다.
- 수정 금지: `static/docs/specs/features/*.md` 전부(구현을 스펙에 맞추되 스펙을 구현에 맞추지 않는다), `docs/grill/GRILL_LEDGER-*.md`, `CLAUDE.md`, **`gui_preview/`**(모든 goal 루프가 「수정 금지」로 지정한 참고 자료다 — 복사만 하고 원본은 건드리지 않는다), `.github/workflows/`, `pyproject.toml`, `uv.lock`, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.9 것 제외), `docs/ROADMAP.md`.
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.9.md`.
- 금지 행동: 신규 서드파티 패키지 추가(FastAPI·Starlette·uvicorn·마크다운 라이브러리 포함), Node 툴체인·번들러 도입, 웹폰트 파일 커밋, 외부 CDN 링크, `0.0.0.0`·LAN IP 바인딩, `pyproject.toml` 버전 범프, `git tag`·릴리스 생성, force push.
- 비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다.
- **`tests/security/test_network_invariant.py` 의 `watch_sockets` 픽스처 안에서 자기 서버에 HTTP 로 접속하는 테스트를 작성하지 않는다.** 그 픽스처는 `socket.connect` 를 무조건 `ConnectionRefusedError` 로 만들므로 원리적으로 불가능하다. 서버 핸들러는 **in-process 로 직접 호출**해 테스트한다(스펙 §3 검증 방식).
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: pywebview 데스크톱 창, 원격 접속·다중 사용자·계정, 그래프 수동 편집, RAG 답변 생성, 프론트엔드 E2E·JS 단위 테스트, 워크스페이스의 코어·CLI 편입, `ProgressEvent` 공개 API 승격, React·번들러, 외부 CDN.
- 토큰을 쿠키나 `localStorage` 에 저장하지 않는다 — 쿠키는 브라우저가 다른 탭의 요청에도 자동으로 붙여 보내 토큰을 둔 목적 자체를 무효화한다(스펙 §4.6.1).
