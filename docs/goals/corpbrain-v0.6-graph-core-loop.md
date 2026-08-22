/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` 의 "완료의 정의"(§3) 8개 항목 중 **PR① 범위인 1·2·4·5·6·7번과 8번의 `scan` 경로 부분**을 모두 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, 변경을 draft PR로 올린다.
- 시작 지점: `main`(tag v0.5.1 완료 상태)에서 `feat/v0.6-graph-core` 브랜치를 새로 만들어 착수한다.
- 작업 대상: `docs/plans/corpbrain-v0.6-knowledge-graph.md` 가 정의한 **U1~U7** 단위 — 신규 `corpbrain/core/graph.py`·`corpbrain/core/graphstore.py`, 확장 대상 `corpbrain/core/models.py`·`config.py`·`__init__.py`·`vectorstore.py`·`pipeline.py`·`render.py`·`embedding_text.py`·`report.py`·`llm/base.py`·`llm/summarize.py`·`llm/anthropic_client.py`·`corpbrain/cli.py`(`scan` 옵션 2개만), 그리고 대응 `tests/`(신규 통합테스트 + `tests/security/test_network_invariant.py` 확장 1케이스 + 기존 `tests/unit/test_embedding_text.py` 언패킹 3곳 수정).
- **PR② 범위는 이 목표에 포함하지 않는다** — `corpbrain graph` 서브커맨드, `report.py` 의 그래프 조회 빌더 3개, `tests/test_cli_graph.py`, `docs/USAGE.md`·`docs/SMOKE.md` 갱신, 완료의 정의 3번은 PR① 머지 후 별도 `/goal` 로 진행한다.
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 버전 범프·실제 Anthropic API 호출(비-mock)은 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` — §3 완료의 정의 · §4 인터페이스 계약 · §5 엣지 케이스
  - `docs/plans/corpbrain-v0.6-knowledge-graph.md` — 작업 단위 U1~U7 · 의존 · 실행 순서 · 커밋 규율
  - `docs/grill/GRILL_LEDGER-v0.6*.md` 5종 — 30개 확정 결정(전부 ALL_RESOLVED)
- 워크플로: U1 → U2 → U3 → U4 → U5 → U6 → U7 순서로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다.
- **커밋 규율**: 모든 커밋이 green이어야 한다 — 각 단위 커밋은 자기 단위테스트를 함께 담는다. 강제 결합은 U5의 `parse_wiki_markdown` 3-튜플 변경 하나뿐이며, 호출부(`pipeline._backfill_embedding`)와 `tests/unit/test_embedding_text.py:52`·`:70`·`:92` 를 같은 커밋에서 고친다.
- 커밋 메시지 프리픽스: `v0.6(core):` U1·U2·U4 / `v0.6(llm):` U3 / `v0.6(render):` U5 / `v0.6(wiring):` U6 / `v0.6(test):` U7.
- 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새, **단일 게이트웨이**(모든 외부 호출은 `gateway.request_json` 경유), 코어 no-I/O, 하위 호환(신규 파라미터는 선택·기본값 보존, `--similarity-threshold`·`--related-top-k` 미지정 시 기본값 0.75·5).
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.6.md` 에 기록한다. 각 항목을 CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
- 도구: 의존성·실행은 `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`). 신규 외부 패키지를 `pyproject.toml` 에 추가하지 않는다 — 그래프 계층은 표준 라이브러리 `sqlite3` 와 순수 파이썬 계산만 쓴다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/DECISION_CHECKPOINT-v0.6.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - PR① 범위의 완료의 정의(§3 항목 1·2·4·5·6·7 및 8번의 `scan` 경로)가 모두 충족되고 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 50회 도달 → STOP REASON: TURN_CAP (= or stop after 50 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.6.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드(0/비-0) 출력을 대화에 남겨 증명한다.
  3) `cat docs/loop/DECISION_CHECKPOINT-v0.6.md` 를 실행해 `CORE: N`·`MINOR: M` 카운터 줄과 `STOP REASON:` 줄이 보이는 출력을 대화에 남긴다.
  4) `git diff --name-only main` 을 실행해 변경 파일이 §1 작업 대상 범위 안에만 있음을 대화에 남긴다.
  5) `gh pr list` 를 실행해 이 루프가 연 draft PR을 대화에 남긴다(gh 사용 불가 시 `git log --oneline -15` 로 대체).

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml`/`uv.lock` 의 버전 범프 금지(릴리스는 사용자가 tag 시점에 별도로 수행). 실제 Anthropic API·비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다.
- 수정 금지: `static/docs/specs/features/*.md`(v0.6 스펙 포함 — 구현을 스펙에 맞추되 스펙을 바꾸지 않는다), `docs/plans/corpbrain-v0.6-knowledge-graph.md`, `docs/grill/GRILL_LEDGER-v0.6*.md` 및 다른 버전 원장, `docs/ROADMAP.md`, `CLAUDE.md`, `gui_preview/`, `.github/workflows/`, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.6 것 제외).
- PR② 범위 파일을 이번에 만들지 않는다: `corpbrain graph` 서브커맨드, `report.py` 의 그래프 조회 빌더 3개, `tests/test_cli_graph.py`, `tests/unit/test_graph_report.py`, `docs/USAGE.md`, `docs/SMOKE.md`.
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.6.md`.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: GUI 일체(FastAPI/SSE 서버·`corpbrain gui`·프론트엔드·멀티 워크스페이스), `RELATES_TO` 엣지(엔티티↔엔티티), LLM 기반 엔티티 동의어 병합, 엔티티→태그 엣지, 그래프 가중치를 결합한 하이브리드 검색, 별도 `graph build` 명령, 매개 중심성 등 고급 지표, 그래프 DB 스키마 마이그레이션.
- 기존 `tests/fixtures/sample_corpus/` 를 확장하지 않는다 — 통합테스트 코퍼스는 `tmp_path` 에 인라인 생성한다(스펙 §3).

## 5) 병렬 개발(서브에이전트) 규칙
- **기본은 순차 진행이다.** v0.6의 임계 경로(`doc_facts` 스키마 → 그래프 빌더 → 파이프라인 2-패스 → 「관련 문서」 주입 → 통합테스트)는 한 줄기이며, 병렬로 앞당겨지는 것은 작성 시간이지 검증 시간이 아니다. **이득이 없다고 판단되면 병렬을 쓰지 않는다 — 억지로 쓰지 않는다.**
- 병렬을 쓰려면 대상 단위가 다음을 **모두** 만족해야 한다(v0.5 루프가 `pii.py`·`consent.py` 에 적용해 성공한 조건과 같다):
  - 서로도, 메인 작업과도 **수정 파일이 하나도 겹치지 않는** 독립 leaf 단위일 것
  - 공유 타입(`models.py`)·재수출(`core/__init__.py`)·설정(`config.py`)을 **읽기만** 하고 수정하지 않을 것 — 즉 U1이 먼저 커밋돼 있을 것
- 이 기준을 만족하는 유일한 단위는 **U3(요약 스키마 확장 — `llm/base.py`·`llm/summarize.py`·`llm/anthropic_client.py` 와 대응 테스트)** 이다. U1 커밋 이후 U3를 서브에이전트에 맡기고 메인은 U2·U4를 진행해도 좋다.
- **U5는 병렬 대상이 아니다** — `pipeline.py` 의 `_backfill_embedding` 호출부를 건드려 U4(`_NoIndexStore.iter_vectors`)·U6과 같은 파일에서 충돌한다.
- 병렬을 쓸 경우 각 서브에이전트에게 자기 파일 목록을 명시적으로 주고, 그 밖의 파일은 읽기만 하도록 지시한다. 합류 후 `uv run ruff check . && uv run pytest` 로 green을 확인한 뒤 다음 단위로 넘어간다.
