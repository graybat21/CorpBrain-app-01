/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.8-xlsx-pptx-extraction.md` 의 「완료의 정의」(§3) **12개 항목을 모두 충족**하도록 `.xlsx`·`.xlsm`·`.pptx` 텍스트 추출을 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, **ready PR**을 연다.
- 시작 지점: **브랜치 `feat/v0.8-xlsx-pptx-extraction` 에서 이어서 작업한다.** 이 브랜치에는 스펙·grill 원장·실행 플랜 커밋 3개가 이미 올라가 있고 코드는 아직 없다. `git log --oneline -3` 에 `v0.8(plan)` 이 보이지 않으면 즉시 멈춰 사용자에게 알린다.
- 작업 대상: `docs/plans/corpbrain-v0.8-xlsx-pptx-extraction.md` 가 정의한 **U1~U7** 단위 — `pyproject.toml`·`uv.lock`·`corpbrain/core/extract.py`·`config.py`·`plan.py`·`scanner.py`(docstring), 대응 `tests/`(`tests/unit/test_extract.py`·`tests/unit/test_plan.py`·`tests/test_scanner.py`·신규 통합테스트·`tests/security/test_network_invariant.py` 케이스 추가), 그리고 `docs/USAGE.md`·`docs/ROADMAP.md`·`README.md`.
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 버전 범프는 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - `static/docs/specs/features/corpbrain-v0.8-xlsx-pptx-extraction.md` — §3 완료의 정의 · §4 인터페이스 계약(§4.3.1 암호화 판정 포함) · §5 엣지 케이스
  - `docs/plans/corpbrain-v0.8-xlsx-pptx-extraction.md` — 작업 단위 U1~U7 · 의존 · 실행 웨이브 · 머지 조건
  - `docs/grill/GRILL_LEDGER-v0.8-xlsx-pptx-extraction.md` — 확정 결정 7건(전부 ALL_RESOLVED)
- 워크플로: **U1 → U2 → U3 → U4 → U5 → U6 → U7 순서로 진행**하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다. 병렬 서브에이전트를 쓰지 않는다 — U4·U5 가 `extract.py`·`config.py`·`plan.py` 세 파일을 똑같이 통과한다.
- **U1 은 「확인」 단위다.** 착수 전제 3건을 확인하고 **그 결과를 스펙에 되적는 것**이 산출물이다.
  1) `uv add openpyxl python-pptx` 가 성공하는가 (두 패키지가 `uv.lock`·uv 캐시에 없어 네트워크가 필요하다). 실패하면 즉시 종료한다.
  2) `read_only=True` 워크시트에서 **행 숨김 정보를 얻을 수 있는가** — 얻으면 시트·행 모두 제외하고, 못 얻으면 시트만 제외하며 스펙 §3 항목2 에서 「숨긴 행」 단언을 뺀다. `read_only=False` 로 바꾸는 선택지는 택하지 않는다.
  3) `python-pptx` 가 `.pptm` 을 실제로 거부하는가 — 결과를 스펙 §2 에 기록한다. **거부하지 않더라도 지원 범위를 넓히지 않는다**(범위는 사용자 결정이다).
- **커밋 규율**: 모든 커밋이 green 이어야 한다 — 각 단위 커밋은 자기 단위테스트를 함께 담는다. `SUPPORTED_EXTENSIONS` 추가는 U1 이 아니라 **U4·U5 에서 해당 추출기와 같은 커밋**에 넣는다(U2 가 세우는 「매핑 키 집합 == `SUPPORTED_EXTENSIONS`」 단언이 4종 → 6종 → 7종 세 상태에서 각각 통과해야 한다).
- 커밋 메시지 프리픽스: `v0.8(deps):` U1 / `v0.8(core):` U2~U5 / `v0.8(test):` U6 / `v0.8(docs):` U7.
- 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새, 단일 게이트웨이, 코어 no-I/O, `CLAUDE.md` 의 「v0.8 오피스 포맷 추출 불변식」 3줄, 하위 호환(신규 확장자 추가는 기존 4종의 동작을 바꾸지 않는다).
- **새 `SkipReason` 값을 만들지 않는다.** 실패는 기존 `extraction_failed` / `empty_document` 두 값에 매핑하고 세부는 `detail` 문자열로 가른다.
- **추출 실패 원인 판정에 예외 메시지 문자열 매칭을 쓰지 않는다.** 암호화 판정은 스펙 §4.3.1 의 OLE 시그니처 8바이트로만 한다.
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.8.md` 에 기록한다. 각 항목을 CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
- 도구: 의존성·실행은 `uv` 를 쓴다(`uv add`, `uv run pytest`, `uv run ruff check .`). U1 에서 추가하는 두 패키지 외에 신규 외부 패키지를 `pyproject.toml` 에 넣지 않는다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `git log --oneline -3` 에 `v0.8(plan)` 커밋이 보이지 않음 → STOP REASON: WRONG_BRANCH (착수 전 확인)
  - `uv add openpyxl python-pptx` 가 네트워크·해결 실패로 성공하지 못함 → STOP REASON: BLOCKED_ON_DEPS
  - `docs/loop/DECISION_CHECKPOINT-v0.8.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - U1~U7 이 끝나고 완료의 정의 §3 항목 1~12 가 충족되며 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이고 **ready PR이 열려 있음** → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 30회 도달 → STOP REASON: TURN_CAP (= or stop after 30 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.8.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드 출력을 대화에 남겨 증명한다.
  3) `uv run pytest -k "xlsx or pptx or dispatch or ole" -v` 를 실행해 이 슬라이스 고유 항목(완료의 정의 3·5·7 — 수식 캐시 없는 xlsx 의 `empty_document`, OLE 시그니처와 손상의 서로 다른 detail, 매핑 키 집합 7종 일치)의 통과가 보이는 출력을 대화에 남긴다.
  4) `cat docs/loop/DECISION_CHECKPOINT-v0.8.md` 로 `CORE: N` · `MINOR: M` 카운터 줄과 `STOP REASON:` 줄을 남긴다.
  5) `git diff --name-only main` 으로 변경 파일이 §1 작업 대상 범위 안에만 있음을 남긴다.
  6) `gh pr list` 로 이 루프가 연 PR 을 남긴다(gh 사용 불가 시 `git log --oneline -15`).
  7) 사용자에게 **U1 확인 결과 3줄**을 남긴다: ① 의존성 설치 성공 여부 ② `read_only` 행 숨김 판별 가능 여부와 그에 따른 스펙 §4.2 확정 행 ③ `.pptm` 거부 여부.

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml` 의 `version` 범프 금지(의존성 추가는 U1 의 정상 작업이다). 비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다(예외: U1 의 `uv add` 패키지 설치).
- **스펙 파일은 U1 의 확인 결과 기록에 한해서만 수정한다** — §4.2 의 숨긴 행 조건부 표와 §2 의 `.pptm` 추정 문장 두 곳이다. 그 외 스펙 문면을 고치지 않는다. 구현을 스펙에 맞추되 스펙을 구현에 맞추지 않는다.
- 수정 금지: `docs/plans/corpbrain-v0.8-xlsx-pptx-extraction.md`, `docs/grill/GRILL_LEDGER-*.md`, `CLAUDE.md`, 다른 버전의 스펙 문서, `gui_preview*/`, `.github/workflows/`, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.8 것 제외).
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.8.md`.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: `.xls`(BIFF)·`.ppt`(OLE)·`.xltx`/`.xltm`/`.pptm` 지원, OCR·이미지 텍스트·암호 해제, 확장자별 파일 크기 임계치, 수동 스모크 절차.
- **`CHARS_PER_BYTE` 세 값(`.xlsx`/`.xlsm` 0.06 · `.pptx` 0.03)을 실측 없이 다른 값으로 바꾸지 않는다.** 잠정값임을 주석에 남기고, 실측은 issue #48 로 분리돼 있다.
- 기존 `tests/fixtures/sample_corpus/` 를 확장하지 않는다 — 테스트 코퍼스는 `tmp_path` 에 인라인 생성한다(스펙 §3). `docs/smoke/corpus/` 는 읽지도 쓰지도 않는다.
- 픽스처 생성 헬퍼는 `tests/conftest.py` 나 공유 모듈을 신설하지 말고 단위·통합 테스트 파일에 각각 둔다(스펙 §3 「헬퍼 배치」).
