/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.3-resource-gating-and-ollama-doctor.md` 의 "완료의 정의"(§3) 9개 항목을 모두 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, 변경을 draft PR로 올린다.
- 시작 지점: `main`(tag v0.2 완료 상태)에서 `feat/v0.3-resource-gating-doctor` 브랜치를 새로 만들어 착수.
- 작업 대상: v0.3 스펙이 정의한 자원 게이팅(GPU·파일크기·토큰 게이트, `--force-gates`·`--max-file-size`·`--max-total-tokens`)과 신규 `corpbrain doctor` 명령. 구현 파일 = `corpbrain/` 패키지(`core/config.py`·`core/models.py`·`core/plan.py`·`core/pipeline.py`·`core/report.py`·`core/llm/ollama_client.py`, 신규 `core/environment.py`, `cli.py`)와 대응 `tests/`. 문서 갱신은 `docs/USAGE.md` v0.3 섹션.
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·비-localhost 외부 호출은 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 위 v0.3 스펙(§4 인터페이스·§5 엣지케이스)과 `docs/grill/GRILL_LEDGER-v0.3.md`(확정된 7개 결정)를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
- 워크플로: 스펙 "완료의 정의" 항목 단위로 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 항목 검증)을 돈다. 기존 코드의 코어/CLI 이음새·단일 게이트웨이·코어 no-I/O·하위 호환 불변식을 유지한다(신규 파라미터는 선택·기본값 보존).
- 브랜치·PR: 단일 `feat/v0.3-resource-gating-doctor` 브랜치에서 작업하고, 착수 직후 draft PR을 열어 커밋을 누적한다. 커밋 메시지는 저장소 관례(예: `v0.3(gating): ...`, `v0.3(doctor): ...`)를 따른다.
- 의사결정 기록(조기 종료 카운터): 구현 중 **기존 문서(v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`)가 명확히 정해두지 않은** 새 결정을 내려야 할 때마다 `docs/loop/DECISION_CHECKPOINT.md` 에 한 줄로 기록하고 CORE/MINOR로 분류한 뒤 해당 카운터를 +1 한다(규격 §6). 이미 정해진 사항은 카운트하지 않는다. 결정을 메모리에만 두지 않는다.
- 명령 표준: 프로젝트는 `uv` 관리. 테스트 `uv run pytest`, 린트 `uv run ruff check .`. Ollama 연동 테스트는 게이트웨이(`gateway.request_json`)·`shutil.which` mock으로 스텁하며 실제 데몬에 접속하지 않는다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/DECISION_CHECKPOINT.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - v0.3 스펙 "완료의 정의" 9개 항목이 모두 충족되고 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 50회 도달 → STOP REASON: TURN_CAP (= or stop after 50 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드(0/비-0) 출력을 대화에 남겨 증명한다.
  3) `cat docs/loop/DECISION_CHECKPOINT.md` 를 실행해 `CORE: N`·`MINOR: M` 카운터 줄과 `STOP REASON:` 줄이 보이는 출력을 대화에 남긴다.
  4) `gh pr list` 를 실행해 이 루프가 연 draft PR을 대화에 남긴다(gh 사용 불가 시 `git log --oneline -5` 로 대체).

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성·자동배포 유발 금지. 로컬 Ollama(localhost) 외 네트워크 호출 금지(단일 게이트웨이 불변식 유지).
- 수정 금지: `static/docs/specs/features/*.md`(v0.3 스펙 포함 — 구현을 스펙에 맞추되 스펙을 바꾸지 않는다), `docs/ROADMAP.md`, `docs/grill/GRILL_LEDGER-v0.3.md`, `CLAUDE.md`, 다른 버전 스펙·원장.
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT.md`, `docs/USAGE.md`(v0.3 섹션), `reports/`.

## 5) GitHub 연동 규칙
- `gh` CLI로 draft PR 생성·갱신만 한다(`gh pr create --draft`, 이후 push로 갱신). 리뷰 요청·머지·라벨/마일스톤 정책 변경은 하지 않는다.
- PR 본문에는 구현한 "완료의 정의" 항목 번호와 `DECISION_CHECKPOINT.md` 카운터 현재값(`CORE: N`·`MINOR: M`)을 요약한다.
- gh 인증이 없거나 원격 push가 거부되면 STOP하지 말고, 로컬 커밋을 유지한 채 그 사실을 대화에 남기고 구현을 계속한다(PR은 종료 방법 4)에서 재시도).

## 6) 의사결정 체크포인트 문서 규격 (`docs/loop/DECISION_CHECKPOINT.md`)
- 멀티에이전트가 동시에 읽어도 명확하도록, 문서 상단에 grep 가능한 카운터 두 줄을 항상 유지한다:
  - `CORE: N`
  - `MINOR: M`
- 문서가 없으면 착수 시 `CORE: 0` / `MINOR: 0` 으로 생성한다(이미 시드돼 있으면 그대로 이어쓴다).
- 분류 기준:
  - CORE = 아키텍처·보안·외부 의존·데이터 모델·공개 API/CLI 계약·핵심 UX 계약에 관한 신규 결정.
  - MINOR = 네이밍·디렉터리·로그 문구·테스트 픽스처·내부 헬퍼 등 국소 결정.
- 각 결정은 한 줄로 `- [CORE|MINOR] <결정> | 근거 | 관련 파일` 형식으로 적고, 기록 직후 해당 카운터를 +1 한다.
- 이미 v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`에 정해진 사항은 여기에 적지 않는다(중복·오카운트 방지).
- 이 문서는 조기 종료 판정의 **단일 근거**다 — CORE_BUDGET(≥3)·MINOR_BUDGET(≥10)은 오직 이 카운터로만 판정한다. 카운터가 임계에 닿으면 미해소 결정이 누적된 신호이므로 즉시 STOP하고 `/interview`·`/grill-it`로 되돌린다.
