/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` 의 "완료의 정의"(§3) 중 **PR② 범위인 항목3과 항목8의 `graph` 단독 실행 부분**을 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, 변경을 draft PR로 올린다.
- 시작 지점: PR①(`feat/v0.6-graph-core`, PR #33)이 머지된 `main`에서 `feat/v0.6-graph-cli` 브랜치를 새로 만들어 착수한다. **PR①이 아직 머지되지 않았으면 착수하지 말고 그 사실을 보고하고 멈춘다** — PR②는 PR①의 타입(`GraphStats`·`GraphEdge`·`GraphStore`)에 의존하므로 머지 전에 열면 리뷰어가 `main`에 없는 타입을 가정한 코드를 읽게 된다.
- 작업 대상: `docs/plans/corpbrain-v0.6-knowledge-graph.md` 가 정의한 **U8~U10** 단위.
  - U8 — `corpbrain/core/report.py` 에 뷰별 빌더 3개(`build_graph_stats_lines`, `build_graph_neighbors_lines`, `build_graph_central_lines`)와 `tests/unit/test_graph_report.py`
  - U9 — `corpbrain/cli.py` 에 `graph` 서브커맨드, `tests/test_cli_graph.py`, `tests/security/test_network_invariant.py` 에 케이스 1건 추가
  - U10 — `docs/USAGE.md` 갱신, `docs/SMOKE.md` 에 실행 H 추가, v0.6 스펙의 «상태» 줄을 `확정` → `완료`로
- **PR① 범위는 이 목표에 포함하지 않는다** — 그래프 빌더·저장소·파이프라인 통합·「관련 문서」 주입은 이미 `main`에 있다. 그 코드를 고칠 이유가 생기면 고치지 말고 의사결정으로 기록한 뒤 계속 진행한다.
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 버전 범프·실제 Anthropic API 호출(비-mock)은 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 다음 세 문서를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
  - v0.6 스펙 §3 항목3·항목8 · §4.6 결과 타입 · **§4.7 CLI 계약** · §5
  - `docs/plans/corpbrain-v0.6-knowledge-graph.md` — U8~U10 · 의존 · 커밋 규율
  - `docs/grill/GRILL_LEDGER-v0.6*.md` 5종 — 30개 확정 결정
- 워크플로: U8 → U9 → U10 순서로 진행하고, 단위마다 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 단위 검증)을 돈다.
- **커밋 규율**: 모든 커밋이 green이어야 한다 — 각 단위 커밋은 자기 테스트를 함께 담는다.
- 커밋 메시지 프리픽스: `v0.6(report):` U8 / `v0.6(cli):` U9 / `v0.6(docs):` U10.
- **출력 검증 관용구를 지킨다** (§3): 정확 문자열 단언은 `tests/unit/test_graph_report.py` 가 하고, `tests/test_cli_graph.py` 는 종료 코드와 배선만 확인한다 — `tests/test_cli_search.py` 가 `assert "먼저" in err` 수준으로만 보는 것과 같다. 출력 문구를 다듬을 때 어댑터 테스트가 깨지지 않게 한다.
- `graph`는 **순수 조회 명령**이다 (§4.7). 조회 시점에 엣지를 다시 계산하지 않는다 — `--stats` 출력이 DB·위키와 어긋나 §3 항목3을 위반한다. `--similarity-threshold`·`--related-top-k` 를 `graph`에 달지 않는다.
- 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새(코어는 경로 해석 책임을 지지 않는다), 단일 게이트웨이, 코어 no-I/O, 하위 호환.
- 의사결정 기록: 위 세 정본에 확정돼 있지 않은 추가 의사결정은 `docs/loop/DECISION_CHECKPOINT-v0.6-cli.md` 에 기록한다. CORE(아키텍처·보안·외부의존·데이터 모델) 또는 MINOR(네이밍·디렉터리·로그 포맷·문구)로 분류하고, grep 가능한 카운터를 각각 별도 줄에 `CORE: N` 과 `MINOR: M` 으로 유지한다.
- 도구: `uv` 를 쓴다(`uv run pytest`, `uv run ruff check .`). 신규 외부 패키지를 `pyproject.toml` 에 추가하지 않는다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - PR①이 `main`에 머지돼 있지 않음 → STOP REASON: BLOCKED_ON_PR1
  - `docs/loop/DECISION_CHECKPOINT-v0.6-cli.md` 의 `CORE:` 카운터가 2에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 6에 도달 → STOP REASON: MINOR_BUDGET
  - PR② 범위의 완료의 정의(§3 항목3 및 항목8의 `graph` 단독 소켓 0건)가 모두 충족되고 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 25회 도달 → STOP REASON: TURN_CAP (= or stop after 25 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.6-cli.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드(0/비-0) 출력을 대화에 남겨 증명한다.
  3) `uv run corpbrain graph --out <스모크 out_dir> --stats` 를 실행해 노드·엣지 종류별 개수가 보이는 출력을 대화에 남긴다.
  4) `cat docs/loop/DECISION_CHECKPOINT-v0.6-cli.md` 를 실행해 `CORE: N`·`MINOR: M` 카운터 줄과 `STOP REASON:` 줄이 보이는 출력을 대화에 남긴다.
  5) `git diff --name-only main` 을 실행해 변경 파일이 §1 작업 대상 범위 안에만 있음을 대화에 남긴다.
  6) `gh pr list` 를 실행해 이 루프가 연 draft PR을 대화에 남긴다(gh 사용 불가 시 `git log --oneline -10` 으로 대체).

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성 금지. `pyproject.toml`/`uv.lock` 의 버전 범프 금지. 실제 Anthropic API·비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 `gateway.request_json` 스텁으로만 다룬다.
- 수정 금지: `docs/plans/corpbrain-v0.6-knowledge-graph.md`, `docs/grill/GRILL_LEDGER-v0.6*.md` 및 다른 버전 원장, `docs/ROADMAP.md`, `CLAUDE.md`, `gui_preview/`, `.github/workflows/`, 다른 버전 스펙, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.6-cli 것 제외).
- **v0.6 스펙 예외**: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` 는 **머리말의 «상태» 줄을 `확정` → `완료`로 바꾸고 «최종 갱신» 날짜를 고치는 것만** 허용한다(U10, v0.4·v0.5 선례). 그 밖의 내용 변경은 금지 — 구현을 스펙에 맞추되 스펙을 구현에 맞추지 않는다.
- PR① 범위 코드(`graph.py`·`graphstore.py`·`pipeline.py`의 그래프 단계·`render.py`의 관련 문서 렌더)를 고치지 않는다. 고쳐야 할 문제를 발견하면 의사결정으로 기록하고 PR② 범위 안에서 우회하거나, 우회가 불가능하면 그 사실을 STOP 사유로 보고한다.
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.6-cli.md`.
- 스펙이 비목표(§2)로 못박은 것을 구현하지 않는다: GUI 일체, `RELATES_TO` 엣지, LLM 기반 엔티티 동의어 병합, 엔티티→태그 엣지, 그래프 가중치를 결합한 하이브리드 검색, 별도 `graph build` 명령, 매개 중심성 등 고급 지표, 그래프 DB 스키마 마이그레이션.

## 5) `graph` 명령 계약 (스펙 §4.7 요약 — 구현 시 원문을 확인한다)
```
corpbrain graph
  --out DIR                    위키·그래프 DB 위치 (기본 ./corpbrain_wiki)
  --stats                      노드·엣지 종류별 개수
  --neighbors <상대경로>        해당 문서의 4종 엣지 이웃
  --central                    연결 차수 내림차순 문서 목록
```
- `--stats` / `--neighbors` / `--central` 은 상호배타이며 중첩 서브커맨드를 두지 않는다.
- 경로 해석: `--out` 기준 **위키 상대경로**(`개발/설계.md.md`)를 우선 매칭하고, 실패하면 **원문 상대경로**(`개발/설계.md`)로 한 번 더 시도한다. 절대경로도 허용한다. 해석은 **CLI 어댑터**가 하고 코어에 절대경로를 넘긴다.
- 오류 계약: 그래프 DB 부재 → **exit 1**(`search`의 인덱스 부재 선례). `--neighbors` 가 지목한 문서가 그래프에 없음 → **exit 1** + 안내(자유 텍스트 쿼리와 달리 존재를 전제한 식별자 지목이므로 매칭 실패는 빈 결과가 아니라 잘못된 지목이다). `--stats`·`--central` 이 빈 그래프를 만난 경우 → **exit 0**.
- `--central` 은 `Document` 노드만, 연결 차수 내림차순, 동점은 노드 id 사전순이다(`GraphStore.degree_ranking()` 이 이미 구현).
- **`cli.build_config(args)` 를 `graph` 명령에서 재사용하지 않는다.** 이 함수는
  `args.similarity_threshold`·`args.related_top_k` 를 무조건 읽는데 두 인자는 `scan` 파서에만
  있어, 그대로 부르면 `AttributeError` 가 난다. `graph` 는 `--out` 하나만 필요하므로 인자를
  직접 읽어 코어에 넘긴다. (PR #33 리뷰에서 확인된 지점)
