/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` 의 "완료의 정의"(§3) 13개 항목 중 **α 실측에 의존하지 않는 1~12번**을 모두 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, 변경을 **draft PR**로 올린다.
- 시작 지점: **PR #45(#42 임베딩 모델 재판단)가 `main`에 머지된 것을 먼저 확인**하고(`git log --oneline -3` 에 보이지 않으면 즉시 멈춰 사용자에게 알린다), `main`에서 `feat/v0.7-hybrid-search` 브랜치를 새로 만들어 착수한다.
- 작업 대상: `docs/plans/corpbrain-v0.7-hybrid-search.md` 가 정의한 **U1~U9** 단위 — `corpbrain/core/models.py`·`config.py`·`__init__.py`·`graph.py`·`search.py`·`report.py`·`corpbrain/cli.py`(`search` 옵션 3개만), 대응 `tests/`(신규 `tests/unit/test_search_ranking.py`·`tests/unit/test_search_report.py`, 통합테스트, `tests/security/test_network_invariant.py` 케이스 추가, 기존 `tests/test_cli_search.py` 갱신), 그리고 `docs/USAGE.md`·`docs/smoke/README.md`·`docs/smoke/graph_decay_sweep.py`·`docs/smoke/graph_decay_queries.json`.
- **U10(α 확정)은 이 목표에 포함하지 않는다** — 사용자가 로컬에서 스캔·스윕을 실행해 원시 출력을 전달해야 닫히는 단위다. `DEFAULT_GRAPH_DECAY` 는 **잠정값 0.7 그대로 두고**, 그 값이 잠정임을 주석에 남긴다.
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 버전 범프·실제 Anthropic API 호출(비-mock)은 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` — §3 완료의 정의 · §4 인터페이스 계약 · §5 엣지 케이스
  - `docs/plans/corpbrain-v0.7-hybrid-search.md` — 작업 단위 U1~U10 · 의존 · 실행 웨이브 · 대기 구간
  - `docs/grill/GRILL_LEDGER-v0.7-hybrid-search*.md` 2종 — 16개 확정 결정(전부 ALL_RESOLVED)
- 워크플로: U1 → U2 → U3 → U5 → U4 → U6 → U7 → U8 → U9 순서로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다.
- **커밋 규율**: 모든 커밋이 green이어야 한다 — 각 단위 커밋은 자기 단위테스트를 함께 담는다.
- 커밋 메시지 프리픽스: `v0.7(core):` U1~U4 / `v0.7(report):` U5 / `v0.7(wiring):` U6 / `v0.7(test):` U7 / `v0.7(docs):` U8 / `v0.7(smoke):` U9.
- 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새, 단일 게이트웨이(모든 외부 호출은 `gateway.request_json` 경유), 코어 no-I/O, `CLAUDE.md` 의 「v0.7 하이브리드 검색 불변식」 5줄, 하위 호환(신규 플래그는 전부 기본값 보존 — 미지정 시 v0.4 대비 결과가 달라지는 것은 그래프 확산이 켜지는 것뿐이다).
- **저장소 계약을 넓히지 않는다** — `GraphStore`(10멤버)·`VectorStore` 어느 쪽에도 메서드를 더하지 않는다. 확산 문서의 코사인·제목·경로는 `store.search(query_vector, top_k=len(store.list_ids()))` 로 전 문서를 한 번에 받아 매핑으로 쓴다.
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.7.md` 에 기록한다. 각 항목을 CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
- 도구: 의존성·실행은 `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`). 신규 외부 패키지를 `pyproject.toml` 에 추가하지 않는다 — 이번 슬라이스는 기존 저장소와 순수 파이썬 계산만 쓴다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - PR #45 가 `main` 에 머지돼 있지 않음 → STOP REASON: BLOCKED_ON_42 (착수 전 확인)
  - `docs/loop/DECISION_CHECKPOINT-v0.7.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - U1~U9 가 끝나고 완료의 정의 §3 항목 1~12 가 충족되며 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이고 **draft PR이 열려 있음** → STOP REASON: ALL_DONE
  - 평가-진행 라운드가 누적 40회 도달 → STOP REASON: TURN_CAP (= or stop after 40 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.7.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드 출력을 대화에 남겨 증명한다.
  3) `cat docs/loop/DECISION_CHECKPOINT-v0.7.md` 로 카운터 줄과 `STOP REASON:` 줄을 남긴다.
  4) `git diff --name-only main` 으로 변경 파일이 §1 작업 대상 범위 안에만 있음을 남긴다.
  5) `gh pr list` 로 이 루프가 연 draft PR을 남긴다(gh 사용 불가 시 `git log --oneline -15`).
  6) 사용자에게 **다음 행동 3줄**을 남긴다: ① `docs/smoke/graph_decay_queries.json` 검토·확정 ② `corpbrain scan docs/smoke/corpus --out <임시경로>` ③ `uv run python docs/smoke/graph_decay_sweep.py --out <임시경로>` 후 원시 출력 전달.

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml`/`uv.lock` 버전 범프 금지. 실제 Anthropic API·비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다.
- **`DEFAULT_GRAPH_DECAY` 를 실측 없이 0.7 이외의 값으로 바꾸지 않는다.** 값의 근거는 사용자 스윕뿐이다(스펙 §4.8).
- **위키 산출물을 한 글자도 바꾸지 않는다** — `render.py` 의 「관련 문서」 블록·근거 문구·`rank_related` 계층 정렬은 이번 범위 밖이다(스펙 §2).
- 자동 테스트는 `DEFAULT_GRAPH_DECAY` 를 참조하지 말고 `graph_decay=` 를 명시적으로 넘긴다 — 실측 후 상수 한 줄 교체로 테스트가 깨지지 않게 한다.
- 수정 금지: `static/docs/specs/features/*.md`(v0.7 스펙 포함 — 구현을 스펙에 맞추되 스펙을 바꾸지 않는다. §0 실측 기록은 U10에서 사용자 결과와 함께 쓴다), `docs/plans/corpbrain-v0.7-hybrid-search.md`, `docs/grill/GRILL_LEDGER-*.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `gui_preview*/`, `.github/workflows/`, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.7 것 제외).
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.7.md`.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: BM25·키워드 결합, 확산 점수의 사전 계산·저장, 신규 테이블·저장소 계약 확장, 「관련 문서」 랭킹 변경, 문서 2홉 이상 확산, 정적 중심성 가산, 쿼리 문자열 ↔ 태그·엔티티 라벨 직접 매칭.
- 기존 `tests/fixtures/sample_corpus/` 를 확장하지 않는다 — 통합테스트 코퍼스는 `tmp_path` 에 인라인 생성한다(스펙 §3). `docs/smoke/corpus/` 는 **읽기만** 하고 그 폴더로 산출물을 내지 않는다(2026-08-22 오염 사고).

## 5) 병렬 개발(서브에이전트) 규칙
- **순차 진행한다. 병렬을 쓰지 않는다.** 임계 경로(`타입 → 확산 계산 → 정렬 → 조회 조립 → 리포트 → CLI 배선 → 통합테스트`)가 한 줄기이고, 떼어낼 수 있는 표면(U5 리포트)도 앞 사슬이 끝나야 출력이 맞는지 검증된다 — 병렬로 앞당겨지는 것은 작성 시간이지 검증 시간이 아니다(v0.6 플랜의 판단을 계승).
- 예외를 두지 않는다. v0.6이 병렬 후보로 인정했던 조건(«서로도 메인 작업과도 수정 파일이 하나도 겹치지 않는 독립 leaf»)을 만족하는 단위가 이번엔 없다 — U1~U6이 모두 `models.py`·`search.py`·`report.py` 를 순차로 통과한다.
