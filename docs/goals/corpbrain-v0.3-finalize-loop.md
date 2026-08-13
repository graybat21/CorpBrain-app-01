/goal

## 1) 작업 핵심 목표 및 범위
- 목표: v0.3(자원 게이팅 + Ollama doctor)를 **릴리스 준비 완료** 상태로 마감한다 — v0.3 스펙 완료의 정의 §3의 9개 항목이 `/spec-check`로 모두 충족 확인되고, `uv run ruff check .`·`uv run pytest`가 exit 0, `pyproject.toml` 버전이 `0.3.0`, 실모델 스모크가 위키 1개 생성으로 통과, 브랜치가 push되어 PR #27이 최신 green을 반영하고 ready 상태가 된다.
- 시작 지점: `feat/v0.3-resource-gating-doctor` 브랜치 (로컬 HEAD `90d0e7e` = 코드리뷰 수정 반영·green·**미push**; 원격 `8294022`, PR #27 DRAFT).
- 작업 대상 (v0.3 마감):
  - (a) 로컬 커밋을 `feat/v0.3-resource-gating-doctor`에 push해 PR #27을 green으로 동기화.
  - (b) `/spec-check static/docs/specs/features/corpbrain-v0.3-resource-gating-and-ollama-doctor.md` 로 9개 완료의 정의를 항목별로 검증(근거를 대화에 surface).
  - (c) 미충족·미검증 항목만 보완: 코어(`corpbrain/core/**`)·CLI(`corpbrain/cli.py`)·`tests/**`·`docs/USAGE.md`(v0.3 섹션).
  - (d) 버전 범프 `0.2.0 → 0.3.0` (`pyproject.toml` + `uv.lock` 동기화).
  - (e) 실모델 스모크: 로컬 Ollama(CPU 구동)로 `corpbrain scan`을 픽스처에 1회 실행해 위키 생성 확인(필요 시 `--force-gates`).
  - (f) PR #27 ready 전환 + 본문 갱신(구현한 DoD 항목·카운터 요약).
- 작업 자율성: 종료 조건 도달 전까지 사용자 확인 없이 자율 진행. 단 **main 머지·`git tag`·GitHub Release·force push·비-localhost 외부호출·`ollama pull`은 하지 않는다** — 릴리스(merge/tag/release)는 이 루프 밖의 사용자 확인 단계다(v0.3는 BREAKING).

## 2) 작업 세부 규칙
- 정본: v0.3 스펙(§3 완료의 정의·§4 인터페이스·§5 엣지케이스) + `docs/grill/GRILL_LEDGER-v0.3.md`. 스펙에 없는 동작을 추가하지 않고 비목표(§2)를 넣지 않는다. 구현은 스펙에 맞추되 스펙을 바꾸지 않는다.
- 워크플로: ① 먼저 push로 PR #27 동기화 → ② `/spec-check`로 9개 DoD 항목별 검증(각 항목의 검증 명령·출력을 대화에 남김) → ③ 미충족 항목만 TDD(Red 실패 테스트 → Green 구현 → 재검증) → ④ 버전 범프 → ⑤ 실모델 스모크 → ⑥ 전체 green 재확인 → ⑦ PR ready. 코어/CLI 이음새·단일 게이트웨이·코어 no-I/O·하위호환 불변식 유지(신규 파라미터는 선택·기본값 보존).
- 브랜치·커밋: 단일 `feat/v0.3-resource-gating-doctor`에 누적. 메시지 관례 `v0.3(...): ...`. `main`에 직접 커밋하지 않는다.
- 의사결정 기록(조기 종료 카운터): 구현·검증 중 **기존 문서(v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`)가 명확히 정해두지 않은** 새 결정을 내릴 때마다 `docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md`에 한 줄 기록 후 해당 카운터를 +1 한다(규격 §6). 이미 정해진 사항·이전 페이즈 결정은 카운트하지 않는다. 결정을 메모리에만 두지 않는다.
- 명령 표준: `uv` 관리 — 테스트 `uv run pytest`, 린트 `uv run ruff check .`, 실행 `uv run corpbrain ...`. 단위/통합 Ollama 테스트는 게이트웨이(`gateway.request_json`)·`shutil.which` mock으로 스텁하고 실제 데몬에 접속하지 않는다(실모델 스모크만 예외).

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `grep -c '^- \[CORE\]' docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md` 결과가 3 이상 → STOP REASON: CORE_BUDGET
  - `grep -c '^- \[MINOR\]' docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md` 결과가 10 이상 → STOP REASON: MINOR_BUDGET
  - v0.3 스펙 9개 DoD가 `/spec-check`로 모두 충족 + `uv run ruff check .`·`uv run pytest` exit 0 + `pyproject.toml` 버전 `0.3.0` + 실모델 스모크 위키 1개 생성 + 브랜치 push(PR #27 반영)·ready → STOP REASON: RELEASE_READY
  - 동일한 검증 명령이 3회 연속 실패(고쳐도 계속 실패) → STOP REASON: REPEATED_FAILURE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 40회 도달 → STOP REASON: TURN_CAP (= or stop after 40 turns)
- 종료 방법 (모든 종료 공통 1~4):
  1) `docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md` 말미에 `STOP REASON: <코드>` 한 줄과, 남은 수동 단계(있으면) 한 줄을 append 한다.
  2) `uv run ruff check .` 와 `uv run pytest` 를 각각 실행해 exit 코드(0/비-0) 출력을 대화에 남겨 증명한다.
  3) `cat docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md` 와 `grep -c '^- \[CORE\]' ...`·`grep -c '^- \[MINOR\]' ...` 를 실행해 카운터·`STOP REASON` 줄이 보이는 출력을 대화에 남긴다.
  4) `grep -n '^version' pyproject.toml` 와 `gh pr view 27 --json state,isDraft,headRefOid`(gh 불가 시 `git log --oneline -6`) 를 실행해 출력을 대화에 남긴다.
  5) STOP REASON이 RELEASE_READY인 경우에만 추가로: 실모델 스모크 출력(종료 요약 + 생성된 `.md` 1개 앞부분)을 대화에 남기고, **다음 수동 단계**를 안내한다 — "PR #27 ready 확인 → main merge → `git tag v0.3.0` → GitHub Release(노트에 BREAKING: GPU 미탐지 시 scan 차단 명시)". 이 단계는 루프가 수행하지 않는다.
  6) CORE_BUDGET·MINOR_BUDGET으로 종료한 경우, 누적 결정 엔트리를 "사용자 확인 요청 목록"(결정/대안/권고)으로 정리해 대화에 출력하고 `/interview`·`/grill-it` 복귀를 권한다.

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. `git tag`·GitHub Release 생성·force push·자동배포 유발 금지. 로컬 Ollama(localhost) 외 네트워크 호출 금지(단일 게이트웨이 불변식). `ollama pull`로 새 모델 받지 않는다.
- 수정 금지: `static/docs/specs/features/**`(v0.3 스펙 포함 — 구현을 스펙에 맞추되 스펙 변경 금지), `docs/ROADMAP.md`, `docs/grill/**`, `docs/goals/**`, `CLAUDE.md`, `.claude/**`, 다른 버전 스펙·원장.
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/**`, `docs/USAGE.md`(v0.3 섹션), `reports/`.
- 실모델 스모크는 이미 로컬에 있는 `qwen2.5:7b-instruct`(Ollama CPU 구동)를 쓴다. GPU 게이트가 차단하면 `--force-gates`로 진행하되, 그 사실을 대화에 남긴다.

## 5) GitHub 연동 규칙
- `gh` CLI로 기존 draft PR #27을 push로 갱신하고 준비되면 `gh pr ready 27`로 ready 전환한다. 머지·라벨/마일스톤 변경·리뷰 요청 정책 변경은 하지 않는다.
- PR #27 본문에 충족한 완료의 정의 항목 번호와 `DECISION_CHECKPOINT-v0.3-finalize.md` 카운터 현재값(CORE/MINOR)을 요약한다.
- gh 인증 없음·원격 push 거부 시 STOP하지 말고, 로컬 커밋을 유지한 채 그 사실을 대화에 남기고 검증을 계속한다(push·ready는 종료 방법 4에서 재시도).

## 6) 조기 종료 체크포인트 문서 규격 (`docs/loop/DECISION_CHECKPOINT-v0.3-finalize.md`)
- 멀티에이전트가 동시에 읽어도 명확하도록, 이 마감 루프 전용 신규 문서를 쓴다(이전 페이즈의 `DECISION_CHECKPOINT.md`와 분리 — 카운터 혼동 방지). 없으면 착수 시 아래 형태로 생성한다:
  ```
  # CorpBrain v0.3 마감 페이즈 — 의사결정 체크포인트 (조기 종료 카운터)
  기존 문서(v0.3 스펙·GRILL_LEDGER-v0.3.md·ROADMAP.md)가 명확히 정하지 않은 신규 결정만 누적한다.
  임계: CORE ≥ 3 → CORE_BUDGET · MINOR ≥ 10 → MINOR_BUDGET
  CORE: 0
  MINOR: 0
  ## 엔트리 (append only)
  ```
- 권위값 = 엔트리 줄 수: `grep -c '^- \[CORE\]' ...` / `grep -c '^- \[MINOR\]' ...`. 상단 `CORE:`/`MINOR:` 줄은 참고용으로만 갱신한다.
- 각 결정은 한 줄 원자적 append: `- [CORE|MINOR] <결정> | 근거 | 관련 파일`. 기존 줄을 편집·삭제하지 않는다.
- 분류: CORE = 아키텍처·보안·외부 의존·데이터 모델·공개 API/CLI 계약·핵심 UX 계약 / MINOR = 네이밍·디렉터리·로그 문구·테스트 픽스처·내부 헬퍼 등 국소 결정.
- 체크포인트 시점(각 시점에 두 grep 실행, 출력을 대화에 남김): ① 착수 직후 ② 각 커밋 직전 ③ push·ready 직전. 임계 도달 시 즉시 STOP.
