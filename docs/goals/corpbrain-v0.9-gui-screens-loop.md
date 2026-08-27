/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `docs/plans/corpbrain-v0.9-gui.md` 의 **PR ② (`feat/v0.9-gui-screens`)** 작업 단위 **V1~V7** 을 구현해, 스펙 §3 완료의 정의 **12항목 전부**(PR ① 이 이미 닫은 2·3·9·11 포함)를 충족하는 **ready PR** 을 연다. 이 PR 의 몫은 **5·6·8·12 완결 + 1·4·7 의 나머지 반쪽**이며, 나머지는 PR ① 이 이미 닫아 두었으므로 회귀만 없으면 된다.
- 시작 지점: **`main` 에서 새 브랜치 `feat/v0.9-gui-screens` 를 만들어 작업한다.** 착수 전 확인 두 가지가 모두 참이어야 한다 — ① `git log --oneline -3 main` 에 PR #56(`feat/v0.9-gui-server`) 머지와 **PR #60(v0.9 스펙 문면 정정 5건 · issue #57)** 머지가 모두 보인다, ② `grep -c "PR ①에서 확정된 값은 아래와 같다" static/docs/specs/features/corpbrain-v0.9-gui.md` 가 **1 이상**이다. 둘 중 하나라도 아니면 **구현을 시작하지 말고 즉시 멈춰** 사용자에게 알린다 — 스펙이 구현의 근거이므로 `main` 에 없는 스펙을 보고 구현하면 두 PR 이 같은 문서를 서로 다른 상태로 참조한다.
- 작업 대상: 실행 플랜의 V1~V7 이 지목한 것만 —
  - 코어 변경 4종(각각 **첫 호출자와 같은 커밋**): `corpbrain/core/pipeline.py`(`run_scan(should_cancel=…)` · 취소 시 패스2·3 **및 고아 벡터 정리** 건너뛰기) · `corpbrain/core/models.py`(`ScanResult.cancelled`) · `corpbrain/core/graphstore.py`(`GraphStore.iter_edges()` + `SqliteGraphStore` + 무동작 구현) · `corpbrain/core/embedding_text.py`(`parse_wiki_document()` + `WikiDocument`, `parse_wiki_markdown()` 은 3-튜플 래퍼로 유지)
  - 서버: `corpbrain/gui/api.py` 의 라우트 표에 엔드포인트 6종 추가(플랜/스캔·취소 · 위키 트리·상세 · 그래프 · 검색 · 설정 · 디렉터리 열람) · `corpbrain/gui/` 아래 스캔 워커 스레드 1개
  - 프론트: `corpbrain/gui/static/app.js` · `style.css` · `index.html` — 화면 5개
  - 테스트: `tests/unit/test_gui_*.py` · `tests/test_gui*.py` · `tests/unit/test_embedding_text.py` · `tests/unit/test_graphstore.py` · `tests/integration/` (취소 · 벡터 보존)
  - 문서: `docs/USAGE.md` · `docs/SMOKE.md`(실행 K) · `docs/ROADMAP.md` §7
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 의 `version` 범프는 하지 않는다(그것은 PR ③ 의 몫이다).

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - `static/docs/specs/features/corpbrain-v0.9-gui.md` — §3 완료의 정의 · §4 인터페이스 계약(특히 §4.3.1 `iter_edges()` · §4.3.3 파라미터 노출 · §4.3.4 2단계 흐름 · §4.4 조회 커넥션 수명 · §4.5 디렉터리 열람 · §4.6 위키 상세 · §4.6.1 검색 응답 · §4.6.2 트리 · §4.7 코어 변경 · §4.10.4 해시 라우팅 · §4.10.5 접근성 · §4.11 프로토타입 정합) · §5 엣지 케이스
  - `docs/plans/corpbrain-v0.9-gui.md` — 코어 변경 시점(T2) · PR ② 화면 순서(T4) · 완료 판정(T5) · 문서 시점(T8) · 스모크·릴리스 분리(T9) · 작업 단위 V1~V7
  - `docs/grill/GRILL_LEDGER-v0.9-gui.md` · `-test-harness.md` · `-interaction.md` — 확정 결정 26건
- **PR ① 이 세운 관용구를 그대로 잇는다.** 새 구조를 발명하지 않는다 — 라우트는 `GuiApp._routes()` 표에 한 줄씩 더하고, 응답은 `json_response()`/`error_response()` 를, 오류는 `response_for_exception()` 의 기존 매핑(`CorpBrainError`→200 / `sqlite3.ProgrammingError`→500)을, 인증은 이미 도는 `_authorize()` 를 그대로 쓴다. 성공 응답은 `error` 키를 갖지 않고, 도메인 오류 본문은 `{"error": <예외 클래스명>, "message": <안내 문장>}` 이다.
- 워크플로: 실행 웨이브 순서 **V1 → V2 → V3 → V4 → V5 → V6 → V7** 로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다. 병렬 서브에이전트를 쓰지 않는다.
  - 이 순서에는 두 근거가 있고 **바꾸지 않는다**: ① 데이터 생산자가 스캔 하나뿐이라 V1 이후에야 나머지 넷을 실제 값으로 확인한다, ② 화면 간 링크가 방향을 가지므로(검색 → 그래프, 그래프·검색 → 위키) **도착지부터 만들면 죽은 버튼이 한 번도 생기지 않는다.**
- **커밋 규율**: 기능 + 그 기능의 테스트 + DoD 번호가 한 커밋에 들어온다. 모든 커밋이 `uv run ruff check .` · `uv run pytest` · `git status --porcelain` 청결을 통과한다. 커밋 메시지 프리픽스는 `v0.9(gui):`.
- **코어 변경은 첫 호출자와 같은 커밋에 들어온다**(T2). 각 코어 변경은 아래 표의 단위에서만 들어오며, 앞당겨 넣지 않는다 — 호출자 없는 코드를 `main` 후보에 남기지 않는다.
- 단위별 산출물과 DoD 배분:

  | 단위 | 함께 오는 코어 | 산출물 | DoD |
  |---|---|---|---|
  | V1 스캔 | ① `should_cancel`(+패스2·3·**고아 벡터 정리** 건너뛰기) · ② `ScanResult.cancelled` | 계량/실행 엔드포인트 · 워커 스레드 1개 · 409 · 취소 · **계량 재사용은 같은 `ScanConfig` 일 때만** · 2단계 흐름 · 「고급」 접기 | **5·6** · 1·4·7 나머지 |
  | V2 위키 | ⑤ `parse_wiki_document()` + `WikiDocument` | 트리(`degree_ranking()`+`nodes_of()`) · 상세 front-matter 5키/7섹션 · 「관련 문서」 `doc_id` 해석(`rerun.read_source_path()`) · 「원문」 경로 표시 + 복사 버튼 | **8** |
  | V3 그래프 | ④ `iter_edges()` + 무동작 구현 | 캔버스 · 노드 클릭 → `#/wiki?doc=` | 1 |
  | V4 검색 | 없음 | 결과 카드 · 확산 근거 줄은 `build_expansion_evidence()` 반환 문자열 **그대로** · 「지식그래프에서 보기」 | 1 |
  | V5 설정 | 없음 | consent 토글 · PII **7종**(코어 `PiiType` 값 그대로) · `gui` 섹션 저장(PR ① 의 공유 헬퍼 `configstore`) | 1 |
  | V6 문서 | — | USAGE 화면 6개·「고급」 파라미터·알려진 한계(그래프 렌더 규모) · SMOKE 실행 K 절차 · ROADMAP §7 | — |
  | V7 스모크 | — | 실행 K — **세션 3항목 직접 실행** + 사용자 3항목은 절차만 남기고 위임 | **12** |

- **취소의 계약을 정확히 지킨다**(§4.7): `should_cancel` 은 **순수 술어** `Callable[[], bool]` 이며 `threading.Event` 를 코어 시그니처에 박지 않는다. `on_event` 의 예외는 삼키고 **`should_cancel` 의 예외는 삼키지 않는다.** 취소되면 패스2·3과 **고아 벡터 정리를 함께** 건너뛰고, 부분 `ScanResult(cancelled=True)` 를 정상 반환하며, 종료 보고에 「그래프 미반영 — 다시 스캔하면 반영됩니다」를 낸다.
- **`GraphStore` 는 `iter_edges()` **하나만** 더해 11멤버가 된다.** 새 테이블·새 저장 계층을 만들지 않고 `read_only=True` 개봉에서도 동작해야 한다. 조회 엔드포인트는 **요청마다 저장소를 열고 `finally` 에서 닫으며** 커넥션을 요청 사이에 캐시하지 않는다(§4.4).
- **GUI 는 파라미터 검증을 자체적으로 두지 않는다.** 값을 그대로 코어에 넘긴다 — `validate_graph_decay()`·`parse_expand_edges()` 가 이미 코어에 있다. `ScanConfig` 15필드와 `search_index` 파라미터를 **전부** 다룰 수 있게 하되 실측 확정 상수(`similarity_threshold`·`graph_decay`)는 앞면이 아니라 「고급」 접기에 둔다.
- **테스트 배치는 성격별 축을 따른다.** 순수 함수는 `tests/unit/test_gui_*.py`, 서버↔코어 배선·상태코드는 `tests/test_gui*.py`, 코어 변경은 `tests/unit/`·`tests/integration/` 기존 자리. **`tests/gui/` 디렉터리와 `tests/conftest.py` 를 신설하지 않는다.**
- **테스트 이름 규약**(종료 방법의 `-k` 선택자가 이것을 집는다): 409 판정 케이스 이름에 `conflict`, 취소 관련 케이스 이름에 `cancel`, 위키 파서 케이스 이름에 `wiki_document` 를 포함시킨다.
- **`sleep`·`threading.Event`·`Barrier` 를 테스트에 들이지 않는다.** 409 는 「진행 중」 상태를 주입한 순수 판정으로, 취소는 「N번째 문서 뒤에 `True`」를 돌려주는 술어로 푼다. `watch_sockets` fixture 에 「허용 목록」 예외를 만들지 않는다.
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 **`docs/loop/DECISION_CHECKPOINT-v0.9-gui-screens.md`** 에 기록한다(PR ① 것과 같은 형식). CORE(아키텍처·보안·외부의존·데이터 모델) / MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
  - **엔드포인트 경로 문자열과 응답 필드 이름은 MINOR 로 센다** — 스펙 §4.3 이 「코어 호출 집합이 계약이고 경로·필드 이름은 구현이 확정한다」로 위임했고 PR ① 이 같은 잣대를 썼다.
- 도구: 실행은 `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`). 새 외부 패키지를 `pyproject.toml` 에 넣지 않는다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - 착수 전 확인 두 가지 중 하나라도 거짓(PR #56 또는 **PR #60 미머지**, 스펙에 정정 문면 없음) → STOP REASON: WRONG_BASE
  - `docs/loop/DECISION_CHECKPOINT-v0.9-gui-screens.md` 의 `CORE:` 카운터가 **4** 에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 **15** 에 도달 → STOP REASON: MINOR_BUDGET
  - **아래 9개 조건이 전부 충족되고 ready PR 이 열려 있음** → STOP REASON: ALL_DONE
    1. (DoD 5) 스캔 진행 중 두 번째 스캔 요청이 **409** 이고 진행 중이던 스캔이 영향받지 않음을, 상태를 주입한 순수 판정 테스트가 단언한다
    2. (DoD 6) 취소 요청 후 **부분 `ScanResult(cancelled=True)`** 가 정상 반환되고, 그때까지 생성된 `.md` 가 디스크에 남으며, **취소 전에 인덱싱돼 있던 문서의 벡터가 그대로 남는다**(방문하지 않은 문서가 고아로 오판돼 지워지지 않는다)
    3. (DoD 7 나머지) 취소 훅이 **파일 루프 경계에서** 멈춘다 — 진행 중이던 문서는 마치고 그다음 문서는 시작하지 않는다
    4. (DoD 8) 위키 상세 응답이 front-matter **5키**(`engine` 포함)와 **7섹션**을 필드로 분리해 담고, `parse_wiki_markdown()` 의 **3-튜플 반환이 그대로**이며, 프론트엔드 코드에 마크다운 파서가 없다
    5. (DoD 1 나머지) 엔드포인트 6종이 기대 JSON 본문과 상태코드를 내고, 그 단언이 **`handle()` 을 직접 부르는** 테스트로 성립한다
    6. (DoD 4 나머지) 스캔 워커가 실제로 SSE 스트림을 채워, 그래프 단계 이벤트가 **마지막 `FileGenerated` 와 `RunFinished` 사이**에 나타난다
    7. (DoD 12) `docs/SMOKE.md` 에 실행 K 절차가 있고, **세션 몫 3항목**(진행 표시가 그래프 단계까지 이어지는가 · 취소 버튼이 실제로 듣고 얼마나 기다리는가 · 그래프 화면이 실제 규모에서 버티는가)을 실제 코퍼스로 직접 실행해 그 결과를 `docs/SMOKE.md` 에 기록한다
    8. (DoD 10) `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이고 `git status --porcelain` 이 비어 있다
    9. (회귀 없음) `ScanResult` 가 **10필드**, `GraphStore` 가 **11멤버**이고, `pyproject.toml` 이 이번 PR 에서 **한 줄도 바뀌지 않았다**(신규 런타임 의존성 0)
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 **50회** 도달 → STOP REASON: TURN_CAP (= or stop after 50 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.9-gui-screens.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드 출력을 대화에 남긴다 **(DoD 10)**.
  3) `git status --porcelain` 을 실행해 **출력이 비어 있음**을 대화에 남긴다 **(DoD 10)**.
  4) `uv run pytest -k "conflict" -v` 를 실행해 409 케이스가 pass 로 보이는 출력을 남긴다 **(DoD 5)**.
  5) `uv run pytest -k "cancel" -v` 를 실행해 부분 `ScanResult`·`.md` 잔존·**기존 벡터 보존**·파일 루프 경계 케이스가 전부 pass 로 보이는 출력을 남긴다 **(DoD 6 · 7 나머지)**.
  6) `uv run pytest -k "wiki_document" -v` 를 실행해 5키/7섹션 파서 케이스와 **`parse_wiki_markdown()` 3-튜플 유지** 케이스가 pass 로 보이는 출력을 남긴다 **(DoD 8)**.
  7) `uv run pytest -k "gui" -v` 를 실행해 엔드포인트 6종의 본문·상태코드 케이스와 SSE 배선 케이스가 pass 로 보이는 출력을 남긴다 **(DoD 1 · 4 나머지)**.
  8) 아래 한 줄을 실행해 **`ScanResult fields: 10`** 과 **`GraphStore members: 11`**(목록에 `iter_edges` 포함)이 보이는 출력을 남긴다 **(회귀 없음)**:
     `uv run python -c "from dataclasses import fields; from corpbrain.core.models import ScanResult; from corpbrain.core.graphstore import GraphStore; print('ScanResult fields:', len(fields(ScanResult))); m=sorted(GraphStore.__protocol_attrs__); print('GraphStore members:', len(m), m)"`
  9) `git diff --name-only main | grep -c pyproject.toml` 가 **0** 을 보이는 출력을 남긴다 **(신규 런타임 의존성 0)**.
  10) `grep -c "마크다운" corpbrain/gui/static/app.js` 로 프론트에 마크다운 파서가 없음을 뒷받침하고, `grep -nE "실행 K" docs/SMOKE.md` 로 스모크 절차가 존재함을 대화에 남긴다 **(DoD 8 · 12)**.
  11) `cat docs/loop/DECISION_CHECKPOINT-v0.9-gui-screens.md` 로 `CORE: N` · `MINOR: M` 카운터 줄과 `STOP REASON:` 줄을 남긴다.
  12) `git diff --name-only main` 으로 변경 파일이 §1 작업 대상 범위 안에만 있음을 남긴다.
  13) `gh pr list` 로 이 루프가 연 PR 을 남긴다(gh 사용 불가 시 `git log --oneline -25`).
  14) **사용자 몫으로 남은 스모크 3항목**(① 진행 표시가 사람이 보기에 멈춘 것처럼 보이는가 ② 6개 화면이 minimalist 토큰대로 보이는가 ③ 클릭 가능한 요소가 전부 키보드로 닿고 포커스 링이 보이는가)을 **대화에 목록으로 제시하고, 그 판정을 기다리지 않고 멈춘다.** 눈으로만 판정되는 항목이므로 루프가 스스로 통과 선언하지 않는다.

## 4) 기타 제약조건
- 금지: 어떤 PR도 main 에 merge 하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml` 수정 금지(`version` 범프도 신규 의존성 추가도 하지 않는다).
- **스펙 문면을 수정하지 않는다.** 구현을 스펙에 맞추되 스펙을 구현에 맞추지 않는다. 스펙과 어긋나는 것을 발견하면 코드가 아니라 스펙을 먼저 고쳐야 하지만, 그 판단은 사용자에게 보고하고 멈춘다.
- 수정 금지: `static/docs/specs/features/*.md`, `docs/plans/corpbrain-v0.9-gui.md`, `docs/grill/GRILL_LEDGER-*.md`, `CLAUDE.md`, `gui_preview/`(설계문서 5종과 프로토타입 4벌 **전부 그대로 둔다**), 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.9-gui-screens 것 제외), `pyproject.toml`, `.github/workflows/ci.yml`(PR ① 이 이미 닫았다).
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.9-gui-screens.md`.
- **PR ① 이 이미 닫은 것을 다시 만들지 않는다** — `handle()` 골격 · 인증(토큰↔쿠키 교환 · `Origin`/`Host`) · `format_sse()` · 정적 자산 배치 · `corpbrain gui` 명령 · `bind` 감시장치 · CI wheel 단계. 이들은 **회귀만 없으면 되고**, 고쳐야 할 결함을 발견하면 그 사실을 체크포인트에 기록하고 최소 수정으로 고친다.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: 멀티 프로젝트 워크스페이스·좌 사이드바 프로젝트 축, PyPI 배포 메타데이터, `--host` 플래그, 브라우저 E2E 테스트와 Node 툴체인·axe-core, GUI 에서 API 키 입력, CLI 동작 변경(`Ctrl+C` 처리·플래그·출력), pywebview 데스크톱 셸, **그래프 렌더 규모 대응**(노드 상한·필터·차수 추림 — issue #58 로 이미 분리돼 있다).
- **파일을 OS 기본 앱으로 여는 엔드포인트를 두지 않는다** — `os.startfile`/`open`/`xdg-open` 브릿지는 MVP 스펙 §2 의 명시적 비목표다. 「원문」은 **경로 표시 + 복사 버튼**으로 낸다. `render.py` 의 `file://` 링크(위키 산출물)는 **한 글자도 바꾸지 않는다.**
- **위키 산출물을 바꾸지 않는다.** `render.py` 의 템플릿·문구·「관련 문서」 렌더는 그대로 두고, `rank_related()` 를 조회 시점에 다시 계산하지 않는다.
- **Zero External CDN 을 유지한다.** 폰트·스크립트·스타일·그래프 렌더를 전부 로컬 자산으로 번들한다.
- **계승한 디자인 토큰 밖의 색을 만들지 않는다.** 클릭 가능한 요소는 전부 키보드로 닿고 포커스 링이 보여야 한다.
- 외부 네트워크 호출 금지 — 자동 테스트의 네트워크는 전부 `gateway.request_json` 스텁으로만 다룬다. 예외는 **수동 스모크 실행 K 의 로컬 Ollama 호출과 127.0.0.1 접속**뿐이다.
