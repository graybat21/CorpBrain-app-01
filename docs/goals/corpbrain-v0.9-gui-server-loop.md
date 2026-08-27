/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `docs/plans/corpbrain-v0.9-gui.md` 의 **PR ① (`feat/v0.9-gui-server`)** 작업 단위 **U1~U11** 을 구현해, 그 문서의 「PR ①이 머지 가능한 상태의 정의」 5개 조건과 스펙 §3 완료의 정의 **2·3·9·10·11** 을 모두 충족하는 **ready PR** 을 연다.
- 시작 지점: **`main`(`78b1aee` — PR #55 머지, 스펙·grill 원장·실행 플랜 포함)에서 새 브랜치 `feat/v0.9-gui-server` 를 만들어 작업한다.** 착수 전 `git log --oneline -1` 에 `Merge pull request #55` 가, `ls static/docs/specs/features/corpbrain-v0.9-gui.md docs/plans/corpbrain-v0.9-gui.md` 가 두 파일을 보이지 않으면 즉시 멈춰 사용자에게 알린다. **코드는 아직 한 줄도 없다.**
- 작업 대상: 실행 플랜의 U1~U11 이 지목한 것만 —
  - 코어 선행분: `corpbrain/core/report.py`(`_expansion_evidence` → `build_expansion_evidence()` 공개 승격) · `corpbrain/core/consent.py`(쓰기 절차를 섹션 인자를 받는 공유 헬퍼로 추출) · `corpbrain/core/_progress.py`(그래프 이벤트 3종 + `EventKind` 3값 + `reduce()` 확장) · `corpbrain/core/pipeline.py`(`_run_graph_stage` 가 그 이벤트를 방출)
  - 신규: `corpbrain/gui/`(`handle()` 순수 함수 · `Response` 값 객체 · 라우팅 · 인증 · SSE · 서버 기동) · `corpbrain/gui/static/`(HTML·CSS·JS)
  - 어댑터: `corpbrain/cli.py`(`gui` 서브커맨드 추가)
  - 테스트: `tests/unit/test_gui_*.py` · `tests/test_gui*.py` · `tests/test_progress.py` · `tests/security/test_network_invariant.py`(`SocketWatcher` 에 `bind` pass-through 기록 + DoD 3 케이스)
  - CI·문서: `.github/workflows/ci.yml`(wheel 빌드 + 기동 스모크 단계) · `README.md` · `docs/USAGE.md`(`corpbrain gui` 절 신설)
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 의 `version` 범프는 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - `static/docs/specs/features/corpbrain-v0.9-gui.md` — §3 완료의 정의 · §4 인터페이스 계약 · §5 엣지 케이스
  - `docs/plans/corpbrain-v0.9-gui.md` — PR 절단(T1) · 코어 변경 시점(T2) · PR ① 범위(T3) · 완료 판정(T5) · `bind` 감시장치 시점(T6) · CI wheel 시점(T7) · 문서 시점(T8) · 작업 단위 U1~U11 · 실행 웨이브
  - `docs/grill/GRILL_LEDGER-v0.9-gui.md` · `-test-harness.md` · `-interaction.md` — 확정 결정 26건
- 워크플로: 실행 웨이브 순서 **U1 → U2 → U3 → U4 → U5 → U6 → U7 → U8 → U9 → U10 → U11** 로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다. 병렬 서브에이전트를 쓰지 않는다 — U3~U6 이 `handle()` 한 함수를 똑같이 통과한다.
- **U1~U6 은 소켓을 하나도 열지 않는다.** 서버 로직이 순수 함수로 다 자란 뒤 U7 에서 처음으로 소켓이 열리고, **그 커밋에서 바로** `SocketWatcher` 의 `bind` 기록과 DoD 3 케이스가 붙는다(T6).
- **커밋 규율**: 기능 + 그 기능의 테스트 + DoD 번호가 한 커밋에 들어온다. 모든 커밋이 `uv run ruff check .` · `uv run pytest` · `git status --porcelain` 청결을 통과한다. **U1 은 동작이 한 글자도 바뀌지 않는 순수 리팩터링이며 기존 테스트가 그대로 통과하는 것이 판정이다.**
- **코어 변경은 첫 호출자와 같은 커밋에 들어온다**(T2). 이번 PR 에 들어오는 코어 변경은 ⑥(U1 — CLI 가 이미 쓴다)과 ③(U2 — CLI stderr 라이브 라인이 이미 `_progress` 를 소비한다) **둘뿐**이다. ④ `iter_edges()` · ⑤ `parse_wiki_document()` · ① `should_cancel` · ② `ScanResult.cancelled` 는 **PR ② 의 것이므로 이번에 손대지 않는다.**
- 커밋 메시지 프리픽스는 `v0.9(gui):` 로 통일한다.
- 단위별 산출물과 DoD 배분:

  | 단위 | 산출물 | DoD |
  |---|---|---|
  | U1 | `build_expansion_evidence()` 공개 승격 · `consent` 쓰기 공유 헬퍼 (동작 불변) | 10 |
  | U2 | `GraphStarted` · `RelatedInjected(index,total,path)` · `GraphFinished(stats)` + `reduce()` 확장 + `_run_graph_stage` 방출 | 4① · 7 |
  | U3 | `handle(method,path,headers,body) -> Response` 골격 · 라우팅 · 404/405 · 예외 매핑(`CorpBrainError`→200 / `sqlite3.ProgrammingError`→500) | 1(부분) |
  | U4 | 부트스트랩 쿼리 토큰 → `HttpOnly`·`SameSite=Strict` 쿠키 교환 · `Host` 항상 필수 · `Origin` 메서드별 | **2** |
  | U5 | 대시보드 엔드포인트 — `diagnose()` · `SqliteGraphStore.stats()`, 요청마다 저장소 개폐 | 1(PR① 몫) |
  | U6 | `format_sse()` 순수 함수 · 접속 즉시 `{"kind":"snapshot",…}` 1건 · 이후 실시간 이벤트 | 4② |
  | U7 | `corpbrain/gui/static/` · `importlib.resources` · `corpbrain gui` 명령 · `ThreadingHTTPServer`(127.0.0.1·임의 포트) · `SocketWatcher` bind pass-through | **3** |
  | U8 | `ci.yml` 에 `uv build` + wheel 설치 + `corpbrain gui --no-browser` 기동 스모크 (별도 커밋) | **9** |
  | U9 | 프론트 골격 — 해시 라우팅 · 디자인 토큰 · 레이아웃(사이드바 264 / 헤더 114) · 빈 상태 5개 · 키보드 도달·포커스 링 | — |
  | U10 | 대시보드 화면 — Doctor 카드 · 그래프 지표 · 첫 실행 빈 상태 | — |
  | U11 | README(명령 5종 · 사전준비 2종 · GPU 게이트 · 클라우드 옵트인) · USAGE `corpbrain gui` 절 | **11** |

- 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새(GUI 서버는 CLI 와 **동급의 얇은 어댑터**이며 비즈니스 로직을 두지 않는다), 단일 게이트웨이, 코어 no-I/O, `CLAUDE.md` 의 「v0.9 GUI 불변식」 전 항목.
- **신규 런타임 의존성 0.** `pyproject.toml` 의 `dependencies` 에 아무것도 더하지 않는다. 서버는 표준 라이브러리 `http.server`(`ThreadingHTTPServer`)로 쓰고, 프론트는 빌드 스텝 없는 바닐라 JS/CSS 로 쓴다. Node 툴체인·Playwright·axe-core·마크다운 라이브러리를 도입하지 않는다.
- **`_progress` 는 밑줄 모듈인 채로 둔다.** GUI 도 CLI 와 같은 방식으로 직접 import 하며 공개 API 로 승격하지 않는다.
- **테스트 배치는 성격별 축을 따른다.** 순수 함수(`handle()`·`format_sse()`)는 `tests/unit/test_gui_*.py`, 서버↔코어 배선·상태코드는 `tests/test_gui*.py`, `bind` 불변식은 기존 `tests/security/test_network_invariant.py`. **`tests/gui/` 디렉터리와 `tests/conftest.py` 를 신설하지 않는다.**
- **`sleep`·`threading.Event`·`Barrier` 를 테스트에 들이지 않는다.** 「진행 중」이 전제인 판정은 상태를 주입한 순수 판정으로 푼다. 끝나지 않는 SSE 스트림을 테스트에서 통과시키지 않는다 — 「이벤트 시퀀스」와 「프레임 직렬화」를 나눠 각각 순수하게 검증한다.
- **`watch_sockets` fixture 에 「허용 목록」 예외를 만들지 않는다.** 실제 연결이 필요한 기동 스모크는 이 fixture 를 쓰지 않는 쪽으로 푼다. `bind` 패치는 **주소를 기록한 뒤 원래 `bind` 에 그대로 넘긴다**(pass-through) — 가로채면 `listen()` 이 `0.0.0.0` 임의 포트로 자동 바인드해 테스트가 오히려 전 인터페이스에 소켓을 연다.
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.9-gui-server.md` 에 기록한다. 각 항목을 CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
  - **엔드포인트의 경로 문자열과 응답 필드 이름은 MINOR 로 분류한다** — 스펙 「미결정 사항」이 명시적으로 구현에 위임한 것이며, 계약은 §4.3 이 요구하는 **코어 호출 집합**이다. 이것을 CORE 로 세면 착수 즉시 예산이 소진된다.
- 도구: 실행은 `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`, `uv build`). 새 외부 패키지를 `pyproject.toml` 에 넣지 않는다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - 착수 전 확인에서 `main` 의 스펙·플랜 문서 2종이 보이지 않음 → STOP REASON: WRONG_BASE
  - `docs/loop/DECISION_CHECKPOINT-v0.9-gui-server.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 12에 도달 → STOP REASON: MINOR_BUDGET
  - **아래 10개 조건이 전부 충족되고 ready PR 이 열려 있음** → STOP REASON: ALL_DONE
    1. (ready-1) `corpbrain gui --no-browser` 가 임의 포트로 뜨고, stdout 에 토큰이 실린 `http://127.0.0.1:<port>/?token=…` URL 이 나오며, 그 URL 로 받은 대시보드가 **실제** `diagnose()`·`stats()` 값을 담는다
    2. (ready-2) 인증이 스펙 §4.2 대로 동작한다 — 부트스트랩 쿼리 토큰 → `HttpOnly`·`SameSite=Strict` 세션 쿠키 교환, `Host` 는 항상 필수, `Origin` 은 상태 변경 메서드에서만 필수
    3. (ready-3) 스캔을 아직 시작할 수 없어도 **SSE 엔드포인트가 붙고** 접속 즉시 `{"kind":"snapshot",…}` 프레임 1건을 보낸다
    4. (ready-4) 미구현 화면 5개(스캔·위키·그래프·검색·설정)가 빈 화면이 아니라 스펙 §5 의 「먼저 스캔하세요」 빈 상태를 그린다
    5. (ready-5) `uv run ruff check .` · `uv run pytest` · 작업 트리 청결 검사가 전부 통과한다
    6. (DoD 2) 헤더를 달리한 요청 5종(토큰 없음 / 잘못된 토큰 / 잘못된 `Origin` / 잘못된 `Host` / **`Origin` 없는 POST**)이 401·403 이고, **`Origin` 없는 GET 은 통과**한다
    7. (DoD 3) 서버가 여는 듣는 소켓의 `bind` 주소가 `127.0.0.1` 뿐임을 `tests/security/test_network_invariant.py` 가 pass-through 감시로 단언한다
    8. (DoD 9) `uv build` 로 만든 wheel 에 정적 자산(HTML·CSS·JS)이 들어가고, 그 wheel 을 설치한 깨끗한 환경에서 `corpbrain gui --no-browser` 가 기동한다. `ci.yml` 에 그 단계가 있다
    9. (DoD 10) `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이고 `git status --porcelain` 이 비어 있다
    10. (DoD 11) `README.md` 에 명령 5종(`plan`·`doctor`·`search`·`graph`·`gui`)과 필수 사전준비 2종(요약 모델 pull · **임베딩 모델 `qwen3-embedding:4b` pull**)이 나타난다
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 40회 도달 → STOP REASON: TURN_CAP (= or stop after 40 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.9-gui-server.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드 출력을 대화에 남겨 증명한다 **(ready-5 · DoD 10)**.
  3) `git status --porcelain` 을 실행해 **출력이 비어 있음**을 대화에 남긴다 **(ready-5 · DoD 10)**.
  4) `uv run pytest -k "gui" -v` 를 실행해 인증 5종 + `Origin` 없는 GET 통과 케이스, `handle()` 라우팅·상태코드, `format_sse()` 프레임 문법, 접속 즉시 스냅샷 케이스가 pass 로 보이는 출력을 대화에 남긴다 **(DoD 2 · ready-3)**.
  5) `uv run pytest tests/security/test_network_invariant.py -v` 를 실행해 `bind` 주소 단언 케이스가 pass 로 보이는 출력을 대화에 남긴다 **(DoD 3)**.
  6) `uv build` 를 실행한 뒤 `unzip -l dist/*.whl | grep -c "corpbrain/gui/static/"` 가 **0보다 큰 수**를 보이는 출력을 대화에 남긴다 **(DoD 9 전반부)**.
  7) 깨끗한 임시 venv 에 그 wheel 을 설치하고 `corpbrain gui --no-browser` 를 백그라운드로 띄워 **stdout 에 `http://127.0.0.1:` 과 `token=` 이 함께 보이는 줄**을 대화에 남긴 뒤 프로세스를 종료한다 **(DoD 9 후반부 · ready-1)**. 이어 그 서버에 `curl` 로 ① 토큰 없는 요청이 401, ② 토큰을 실은 대시보드 요청이 200 + 실제 값 JSON, ③ SSE 첫 프레임에 `"kind": "snapshot"` 이 보이는 출력을 남긴다 **(ready-1 · ready-2 · ready-3)**. 확인이 끝나면 서버와 임시 venv, `dist/` 를 정리해 작업 트리를 다시 깨끗하게 만든다.
  8) 미구현 화면 5개가 빈 상태를 갖는지 두 줄로 남긴다 **(ready-4)**:
     `sed -n '/^const PENDING_VIEWS/,/^};/p' corpbrain/gui/static/app.js | grep -c "다음 슬라이스"` 가 **5**,
     `grep -c "먼저 스캔" corpbrain/gui/static/app.js` 가 **1 이상**(다섯 화면이 공유하는 한 템플릿).
     초판은 「`grep -c "먼저 스캔"` 이 5 이상」이었으나 그것은 같은 문구를 다섯 번 복제한
     구현을 전제한 명령이다. 조건(「미구현 화면 5개가 §5의 빈 상태를 그린다」)은 그대로 두고,
     한 템플릿을 다섯 화면이 공유하는 실제 구현을 그대로 측정하도록 명령만 고친다.
  9) `grep -nE "corpbrain (plan|doctor|search|graph|gui)|qwen3-embedding" README.md` 를 실행해 명령 5종과 임베딩 모델 pull 이 모두 보이는 출력을 대화에 남긴다 **(DoD 11)**.
  10) `cat docs/loop/DECISION_CHECKPOINT-v0.9-gui-server.md` 로 `CORE: N` · `MINOR: M` 카운터 줄과 `STOP REASON:` 줄을 남긴다.
  11) `git diff --name-only main` 으로 변경 파일이 §1 작업 대상 범위 안에만 있음을 남긴다.
  12) `gh pr list` 로 이 루프가 연 PR 을 남긴다(gh 사용 불가 시 `git log --oneline -20`).

## 4) 기타 제약조건
- 금지: 어떤 PR도 main 에 merge 하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml` 의 `version` 범프 금지(그것은 PR ③ 의 몫이다).
- **PR ② 의 범위를 이번에 구현하지 않는다** — 스캔·위키·그래프·검색·설정 5화면과 그 엔드포인트, 그리고 함께 오는 코어 변경 4종(`should_cancel` · `ScanResult.cancelled` · `GraphStore.iter_edges()` · `parse_wiki_document()`/`WikiDocument`)을 만들지 않는다. **아무 화면도 부르지 않는 엔드포인트를 `main` 후보에 남기지 않는다**는 것이 이 절단의 근거다.
- **스펙 문면을 수정하지 않는다.** 구현을 스펙에 맞추되 스펙을 구현에 맞추지 않는다. 스펙과 어긋나는 것을 발견하면 코드가 아니라 스펙을 먼저 고쳐야 하지만, 그 판단은 사용자에게 보고하고 멈춘다.
- 수정 금지: `static/docs/specs/features/*.md`, `docs/plans/corpbrain-v0.9-gui.md`, `docs/grill/GRILL_LEDGER-*.md`, `CLAUDE.md`, `gui_preview/`(설계문서 5종과 프로토타입 4벌 **전부 그대로 둔다** — 삭제·이동·수정하지 않는다), 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.9 것 제외), `docs/SMOKE.md`·`docs/ROADMAP.md`(PR ② 의 몫).
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.9-gui-server.md`.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: 멀티 프로젝트 워크스페이스·좌 사이드바 프로젝트 축, PyPI 배포 메타데이터, `--host` 플래그, 브라우저 E2E 테스트와 Node 툴체인, GUI 에서 API 키 입력, CLI 동작 변경(`Ctrl+C` 처리·플래그·출력), pywebview 데스크톱 셸·설치 관리자·앱 아이콘, 그래프 렌더 규모 대응(상한·필터·차수 추림).
- **파일을 OS 기본 앱으로 여는 엔드포인트를 두지 않는다** — `os.startfile`/`open`/`xdg-open` 브릿지는 MVP 스펙 §2 의 명시적 비목표다. `render.py` 의 `file://` 링크(위키 산출물)도 바꾸지 않는다.
- **Zero External CDN 을 유지한다.** 폰트·스크립트·스타일을 전부 로컬 자산으로 번들한다.
- **계승한 디자인 토큰 밖의 색을 만들지 않는다.** `gui_preview/variants/minimalist` 의 팔레트·`--text-secondary`·`--text-muted` 를 그대로 쓴다(대비비 실패에서 한 번 재서 올린 값이다). 클릭 가능한 요소는 전부 키보드로 닿고 포커스 링이 보여야 한다.
- 외부 네트워크 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다. 예외는 종료 방법 7)의 **로컬 127.0.0.1 `curl`** 뿐이다.
