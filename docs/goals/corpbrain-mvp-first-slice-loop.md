/goal

## 1) 작업 핵심 목표 및 범위
- 목표: CorpBrain MVP 첫 슬라이스(FR-001~FR-020)를 구현해, 확정 스펙 §3 "완료의 정의" 6개 항목을 검증하는 자동 테스트를 포함한 전체 테스트가 `uv run pytest -q` exit 0으로 통과하는 상태를 만든다.
- 시작 지점: `main` (커밋 `90f418d`), 구현 코드 미착수 상태. 작업은 새 브랜치 `feat/mvp-first-slice`에서 진행한다.
- 작업 대상: GitHub 이슈 #1~#20 (= `docs/issues/FR-001.md` ~ `FR-020.md`, FR-0NN = 이슈 #NN) 전부. 실행 순서는 `docs/implementation-plan.md`의 웨이브 W1~W11을 그대로 따른다.
- 근거 문서 (착수 전 반드시 Read, 수정 금지):
  - 스펙: `static/docs/specs/features/corpbrain-mvp-local-scan-to-wiki.md` (정본, 상태: 확정)
  - 태스크 명세: `docs/issues/FR-0NN.md` (담당 웨이브 착수 시 해당 파일 전문)
  - 실행 순서: `docs/implementation-plan.md`
  - 프로젝트 규칙: `CLAUDE.md` (스펙 주도 워크플로우 · 구조 이음새)
- 작업 자율성: 종료 조건에 도달하기 전까지 사용자 확인·승인을 위해 멈추지 않고 자율적으로 진행한다. 웨이브 내부의 병렬 태스크는 서브에이전트로 팬아웃해도 된다.

## 2) 작업 세부 규칙

### 2.1 개발 환경
- 이 머신에는 Python 3.12가 설치되어 있지 않고 `uv` 0.9.x가 있다. 다음으로 환경을 구성한다: `uv python install 3.12` → `uv venv --python 3.12` → `uv pip install -e ".[dev]"`.
- 모든 검증·실행 명령은 `uv run` 접두어를 사용한다 (`uv run pytest -q`, `uv run ruff check .`, `uv run corpbrain ...`).
- 스펙 §1의 "외부 통신 0" 제약은 **CorpBrain 제품 런타임**에 적용된다. 개발 툴체인·의존성 설치(uv, PyPI, Python 배포판 다운로드)는 이 제약의 대상이 아니며 허용된다.

### 2.2 웨이브 사이클
각 웨이브마다 아래 순서를 지킨다.
1) 해당 이슈 명세 `docs/issues/FR-0NN.md`와 참조된 스펙 섹션을 Read 한다.
2) 테스트가 가능한 태스크는 테스트를 먼저 쓰고(Red) 구현한다(Green). 스캐폴딩성 태스크(FR-001·002)는 예외.
3) `uv run pytest -q`와 `uv run ruff check .`를 실행해 둘 다 exit 0을 확인한다 (테스트가 아직 없는 초기 웨이브는 ruff만).
4) 의사결정 카운터 체크포인트(§2.4)를 실행한다.
5) 커밋한다. 커밋 제목은 `FR-0NN: <한 줄 요약>`, 본문에 `Refs #NN`을 넣는다. `Closes`는 쓰지 않는다.
- 구현은 확정 스펙에 **엄격히** 맞춘다. 스펙에 없는 동작을 임의로 추가하지 않고, 스펙 §2의 비목표를 슬쩍 넣지 않는다.
- 스펙 §4.5의 두 이음새를 항상 유지한다: ① 비즈니스 로직은 코어 라이브러리, CLI는 얇은 어댑터 ② 모든 외부 네트워크 호출은 단일 관문 함수 경유.

### 2.3 서브에이전트 팬아웃 규칙 (동시 작업 충돌 방지)
- 팬아웃 대상 웨이브: W3(FR-003·004·006·007·014, 5-way), W4(FR-005·008·009, 3-way), W7(FR-012·017, 2-way), W8(FR-013·015, 2-way), W11(FR-019·020, 2-way).
- 팬아웃 전에 오케스트레이터가 워커별 **담당 파일 경계**를 명시한다. 워커는 자기 담당 파일 밖을 수정하지 않는다.
- 워커는 `git commit` / `git push` / 브랜치 조작을 하지 않는다. 커밋은 웨이브 종료 후 오케스트레이터가 일괄 수행한다.
- 워커는 `pyproject.toml` 같은 공유 파일을 직접 편집하지 않는다. 의존성 추가·설정 변경이 필요하면 최종 보고에 요청 사항으로 적고, 오케스트레이터가 취합해 한 번에 반영한다.
- 워커는 의사결정을 §2.4의 append 방식으로 즉시 기록하고, **최종 보고에도 동일 내용을 그대로 복사**해 오케스트레이터가 교차 확인할 수 있게 한다.

### 2.4 의사결정 로그 = 체크포인트 문서 (`docs/loop/DECISION_LOG.md`)
- 이 파일이 조기 종료 판정의 **단일 권위 소스**다. 멀티에이전트 작업에서도 이 파일만 보면 누적 결정 수를 확인할 수 있어야 한다. 파일이 없으면 §2.5 템플릿으로 먼저 생성한다.
- **기록 대상:** 스펙·이슈 명세·실행계획 세 문서에 명확히 정해져 있지 않은데, 진행하려면 내려야 하는 모든 결정.
  - **CORE** (핵심): 아키텍처·모듈 경계·코어 API 계약, 신규 런타임 의존성 추가, 외부 인터페이스·네트워크 경계, 출력 계약(마크다운 템플릿·front-matter 키·LLM JSON 필드) 해석 변경, 스펙 문구가 모호해 한쪽으로 해석해야 하는 경우, 에러 처리·종료 코드 정책의 신규 규정.
  - **MINOR** (부수): 내부 네이밍, 파일·함수 분할, 로그·예외 메시지 문구, 테스트 픽스처 구성, 타입힌트·포맷팅 스타일, 헬퍼 위치.
  - **카운트 제외 (사전 승인됨):** 이슈 명세가 예시로 이미 언급한 선택(`ruff`, `pytest`, `python-docx`, `argparse`), 브랜치·커밋·PR 절차, uv 개발환경 구성, 이 `/goal` 문서가 이미 지정한 사항.
- **엔트리 형식** — 한 결정 = 한 줄, grep 가능한 고정 접두어:
  ```
  - [CORE] D-001 | FR-009 | agent:<이름> | <ISO8601> | <결정 한 줄> | 근거: <왜 이렇게 정했는가>
  - [MINOR] D-002 | FR-006 | agent:<이름> | <ISO8601> | <결정 한 줄> | 근거: <왜>
  ```
- **기록 방법 (동시 쓰기 안전):** 반드시 단일 명령의 원자적 append로 쓴다.
  ```
  cat >> docs/loop/DECISION_LOG.md <<'EOF'
  - [MINOR] D-00N | FR-0NN | agent:worker-a | 2026-08-12T10:00:00+09:00 | ... | 근거: ...
  EOF
  ```
  기존 줄을 편집·재정렬·삭제하지 않는다. 이 파일에 Edit 도구를 쓰지 않는다(경합 위험). D 번호가 겹쳐도 무시한다 — 판정은 번호가 아니라 줄 수로 한다.
- **카운터 줄:** 파일 상단 `## 카운터` 블록의 `CORE: N` / `MINOR: M` 두 줄은 **오케스트레이터만** 갱신한다. 권위 있는 값은 언제나 엔트리 줄 수이며 다음으로 계산한다.
  ```
  grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md
  grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md
  ```
- **체크포인트 시점 (이때마다 위 두 grep을 실행하고 출력을 대화에 남긴다):**
  1. 각 웨이브 착수 직전
  2. 서브에이전트 팬아웃 결과를 취합한 직후
  3. 각 커밋 직전
  세 시점 모두에서 §3의 임계값 도달 여부를 확인하고, 도달했으면 진행 중인 작업을 멈추고 즉시 종료 절차로 넘어간다. 팬아웃 중 임계값에 도달하면 남은 워커를 새로 띄우지 않고, 이미 도는 워커의 결과만 회수한 뒤 종료한다.

### 2.5 DECISION_LOG 템플릿 (파일이 없을 때 이 형태로 생성)
```markdown
# CorpBrain MVP 첫 슬라이스 — 의사결정 로그 (조기 종료 체크포인트)

## 카운터
CORE: 0
MINOR: 0

<!-- 위 두 줄은 오케스트레이터만 갱신. 권위 값은 아래 엔트리 줄 수:
     grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md
     grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md -->

## 엔트리 (append only)
```

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md` 결과가 3 이상 → STOP REASON: CORE_BUDGET
  - `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md` 결과가 10 이상 → STOP REASON: MINOR_BUDGET
  - W11까지 모든 웨이브를 마치고 §3 종료 방법 2~5의 검증이 모두 통과 → STOP REASON: ALL_WAVES_DONE
  - 동일한 검증 명령이 3회 연속 실패(고쳐도 계속 실패) → STOP REASON: REPEATED_FAILURE
  - 평가-진행 라운드(turn = `/goal` 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 60회 도달 → STOP REASON: TURN_CAP (= or stop after 60 turns)
- 종료 방법 (조기 종료·정상 종료 모두 1~5를 수행한다):
  1) `docs/loop/DECISION_LOG.md` 말미에 `STOP REASON: <원인 코드>` 한 줄과, 완료한 웨이브·이슈 목록 및 `NEXT: W<n>/FR-0NN` (다음 착수 지점) 한 줄을 append 한다.
  2) `uv run pytest -q` 를 실행해 출력을 대화에 남긴다 (실패해도 출력을 그대로 남긴다. ALL_WAVES_DONE으로 종료할 때는 exit 0이어야 한다).
  3) `uv run ruff check .` 를 실행해 출력을 대화에 남긴다.
  4) `grep -n '^CORE:\|^MINOR:\|^STOP REASON:\|^NEXT:' docs/loop/DECISION_LOG.md` 와 `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md`, `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md` 를 실행해, 카운터 줄과 실제 엔트리 수가 일치하는 출력을 대화에 남긴다.
  5) `git log --oneline main..HEAD` 와 `git status --porcelain` 을 실행해 출력을 대화에 남긴다.
  6) STOP REASON이 ALL_WAVES_DONE인 경우에만 추가로 수행한다:
     - 실모델 스모크: `uv run corpbrain scan <픽스처 폴더> --out <임시 폴더> --model qwen2.5:7b` 를 실행하고, 종료 요약과 생성된 `.md` 1개의 앞부분을 대화에 남긴다.
     - `git push -u origin feat/mvp-first-slice` 후 draft PR을 생성하고 `gh pr list` 출력을 대화에 남긴다.
  7) CORE_BUDGET 또는 MINOR_BUDGET으로 종료한 경우, 누적된 결정 엔트리를 "사용자 확인 요청 목록"으로 정리해 대화에 출력한다 (각 항목: 결정 내용 / 대안 / 권고안).

## 4) 기타 제약조건
- `main`에 직접 커밋하지 않고, 어떤 PR도 `main`에 merge하지 않는다. PR은 draft로만 만든다. force push 금지.
- 수정 금지: `static/docs/specs/features/corpbrain-mvp-local-scan-to-wiki.md`, `docs/issues/**`, `docs/implementation-plan.md`, `docs/goals/**`, `CLAUDE.md`, `.claude/**`.
- GitHub 이슈를 close하지 않는다 (커밋 메시지에 `Closes #N` 금지, `Refs #N`만 사용).
- 스펙 §2 비목표를 구현하지 않는다: PDF·doc 파서, UI(pywebview·React), 클라우드 LLM 경로, PII 마스킹·NetworkGuard, 벡터DB·임베딩, 실시간 Watcher, Rename/Undo, Ollama 설치·프로비저닝.
- 제품 코드는 `--ollama-url`(기본 `http://127.0.0.1:11434`) 외 어떤 네트워크 호출도 하지 않으며 텔레메트리를 넣지 않는다. 네트워크 호출은 단일 관문 모듈에서만 한다.
- 신규 런타임 의존성 추가는 CORE 결정으로 기록한다 (이슈 명세에 명시된 `python-docx`, 개발 의존성 `pytest`·`ruff`는 제외).
- `ollama pull` 로 새 모델을 받지 않는다. 실모델 스모크는 이미 로컬에 있는 `qwen2.5:7b`를 `--model`로 지정해 사용한다 (스펙 기본값 `qwen2.5:7b-instruct`는 코드의 기본값으로 그대로 두고 변경하지 않는다).
- 활성 웨이브의 구현 범위 밖 파일은 수정하지 않는다. 단 `docs/loop/**` 는 예외다.

## 5) 진행 보고 형식
- 각 웨이브를 마칠 때 대화에 3줄 요약을 남긴다: `W<n> 완료: FR-0NN, ...` / `pytest: <결과>, ruff: <결과>` / `CORE: N, MINOR: M`.
- 서브에이전트 팬아웃 시에는 워커별 담당 파일 경계를 먼저 대화에 명시하고, 취합 후 워커별 결과(성공/실패, 기록한 결정 수)를 한 줄씩 남긴다.
