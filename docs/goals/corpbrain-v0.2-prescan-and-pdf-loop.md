/goal

## 1) 작업 핵심 목표 및 범위
- 목표: CorpBrain v0.2(입력 확장 PDF · pre-scan 계량)를 구현해, 스펙 §3 완료의 정의 1~8을 검증하는 자동 테스트를 포함한 전체 스위트가 `uv run pytest -q` exit 0 이고 `uv run ruff check .` exit 0 인 상태를 만든다.
- 시작 지점: `main`(커밋 `1b12605`), v0.2 구현 미착수. 새 브랜치 `feat/v0.2-prescan-and-pdf`에서 진행한다.
- 작업 대상: `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`의 작업 단위 U1~U6을 웨이브 W1~W5 순서로 구현한다. 각 단위의 파일 경계·스펙 참조·DoD 참조를 그대로 따른다.
- 근거 문서(착수 전 반드시 Read, 수정 금지): 정본 스펙 `static/docs/specs/features/corpbrain-v0.2-prescan-and-pdf.md`, 실행 플랜 `docs/plans/corpbrain-v0.2-prescan-and-pdf.md`, 결정 근거 `docs/grill/GRILL_LEDGER.md`, 프로젝트 규칙 `CLAUDE.md`.
- 작업 자율성: 종료 조건 도달 전까지 사용자 확인·승인을 위해 멈추지 않고 자율 진행한다. W2의 병렬 단위(U1 ∥ U3)는 서브에이전트로 팬아웃해도 된다.

## 2) 작업 세부 규칙
### 2.1 개발 환경
- `uv`로 Python 3.12 환경을 쓴다. 검증·실행은 `uv run` 접두어(`uv run pytest -q`, `uv run ruff check .`, `uv run corpbrain ...`). 환경이 없으면 `uv venv --python 3.12` → `uv pip install -e ".[dev]"`.
- 스펙 §1의 "외부 통신 0" 제약은 **제품 런타임**에만 적용된다. 개발 툴체인·의존성 설치(uv/PyPI, `pypdf` 설치)는 대상이 아니며 허용된다.

### 2.2 웨이브 사이클 (각 웨이브마다)
1) 해당 단위의 플랜 항목과 참조된 스펙 섹션을 Read 한다.
2) 테스트 가능한 단위는 테스트 먼저(Red)→구현(Green). 상수·공식은 스펙 §4.2 값을 그대로 쓴다.
3) `uv run pytest -q`·`uv run ruff check .` 둘 다 exit 0 을 확인한다.
4) 의사결정 카운터 체크포인트(§2.4)를 실행한다.
5) 커밋한다. 제목 `v0.2(U<n>): <한 줄 요약>`. `main`에 직접 커밋하지 않는다.
- 구현은 확정 스펙에 **엄격히** 맞춘다. 스펙 §2의 비목표를 슬쩍 넣지 않는다. 코어=비즈니스 로직·CLI=얇은 어댑터, 모든 외부 네트워크 호출은 단일 게이트웨이 경유 이음새를 유지한다.

### 2.3 서브에이전트 팬아웃 (W2: U1 ∥ U3)
- 팬아웃 전 오케스트레이터가 워커별 담당 파일 경계를 명시한다(U1=`corpbrain/core/extract.py`, U3=`corpbrain/core/plan.py`+테스트). 워커는 담당 파일 밖과 공유 파일(`corpbrain/core/config.py`·`pyproject.toml`)을 수정하지 않는다 — 공유 선행(`.pdf` 등록·`pypdf` 추가)은 W1에서 이미 처리된다.
- 워커는 `git commit`/`git push`/브랜치 조작을 하지 않는다. 커밋은 웨이브 종료 후 오케스트레이터가 일괄 수행한다. 워커는 결정을 §2.4 방식으로 즉시 기록하고 최종 보고에도 동일 내용을 복사한다.

### 2.4 의사결정 로그 (`docs/loop/DECISION_LOG_v0.2.md`)
- 스펙·플랜·grill 원장에 정해지지 않았는데 진행하려면 내려야 하는 결정만 기록한다.
  - CORE: 코어 API 계약·모듈 경계, 신규 런타임 의존성, 외부·네트워크 경계, 출력 계약(리포트/배너 형식·값타입 필드) 해석 변경, 스펙 문구가 모호해 한쪽으로 해석하는 경우.
  - MINOR: 내부 네이밍, 파일·함수 분할, 로그·예외 메시지, 테스트 픽스처, 타입힌트·포맷.
  - 카운트 제외(사전 승인): grill이 확정한 T1~T8, `pypdf` 도입(스펙 §4.1 확정), 브랜치·커밋·PR 절차, uv 환경, 이 /goal이 지정한 사항.
- 형식(동시 쓰기 안전 — 원자적 append 한 줄, Edit 금지): `- [CORE] D-00N | U<n> | agent:<이름> | <ISO8601> | <결정 한 줄> | 근거: <왜>`. 파일이 없으면 `# CorpBrain v0.2 의사결정 로그` + `## 엔트리 (append only)` 헤더로 생성한다.
- 카운트(권위값 = 엔트리 줄 수): `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_v0.2.md` / `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_v0.2.md`.
- 체크포인트(각 웨이브 착수 직전·팬아웃 취합 직후·각 커밋 직전): 위 두 grep을 실행해 출력을 대화에 남기고 §3 임계 도달 여부를 확인한다. 도달하면 즉시 종료 절차로 넘어간다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_v0.2.md` 결과가 2 이상 → STOP REASON: CORE_BUDGET
  - `grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_v0.2.md` 결과가 8 이상 → STOP REASON: MINOR_BUDGET
  - W5까지 모든 웨이브를 마치고 아래 종료 방법 2~4 검증이 모두 통과 → STOP REASON: ALL_UNITS_DONE
  - 동일한 검증 명령이 3회 연속 실패(고쳐도 계속 실패) → STOP REASON: REPEATED_FAILURE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 40회 도달 → STOP REASON: TURN_CAP (= or stop after 40 turns)
- 종료 방법 (조기·정상 종료 모두 1~4 수행):
  1) `docs/loop/DECISION_LOG_v0.2.md` 말미에 `STOP REASON: <코드>` 한 줄과 완료 단위 목록·`NEXT: U<n>`(다음 착수 지점) 한 줄을 append 한다.
  2) `uv run pytest -q` 를 실행해 출력을 대화에 남긴다(ALL_UNITS_DONE으로 종료할 때는 exit 0 이어야 한다).
  3) `uv run ruff check .` 를 실행해 출력을 대화에 남긴다.
  4) `grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_v0.2.md`·`grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_v0.2.md`·`git log --oneline main..HEAD`·`git status --porcelain` 을 실행해 출력을 대화에 남긴다.
  5) STOP REASON이 ALL_UNITS_DONE인 경우에만 추가로: `uv run corpbrain plan <픽스처 폴더>` 를 실행해 stdout 리포트(중요도 랭킹·합계·감지 HW)를 대화에 남기고(LLM 불필요), `git push -u origin feat/v0.2-prescan-and-pdf` 후 draft PR을 만들어 `gh pr list` 출력을 남긴다.
  6) CORE_BUDGET·MINOR_BUDGET으로 종료한 경우, 누적 결정 엔트리를 "사용자 확인 요청 목록"(결정 내용/대안/권고안)으로 정리해 대화에 출력한다.

## 4) 기타 제약조건
- `main`에 직접 커밋·머지하지 않는다. PR은 draft로만 만든다. force push 금지.
- 수정 금지: `static/docs/specs/**`, `docs/plans/**`, `docs/grill/**`, `docs/goals/**`, `CLAUDE.md`, `.claude/**`.
- 스펙 §2 비목표를 구현하지 않는다: xls(`openpyxl`)/ppt(`python-pptx`) 추출, 스캔이미지·OCR·암호화 PDF 처리, 전체 자원 게이팅, 클라우드/외부 LLM, 중요도 기반 처리순서 변경·필터링, 실측 rate 기반 예상시간 보정.
- 제품 코드는 단일 게이트웨이 외 어떤 네트워크 호출·텔레메트리도 하지 않는다. `plan`은 소켓을 열지 않는다(localhost 포함 0 — DoD 3).
- 신규 런타임 의존성은 `pypdf`만 허용(스펙 §4.1 확정, CORE 카운트 제외). 그 외 신규 의존성 추가는 CORE 결정으로 기록한다.
- 중요도·토큰·시간 추정의 상수·공식은 스펙 §4.2 값을 그대로 쓴다. 임의 튜닝 금지("근사" 표기 유지).
- 활성 웨이브의 구현 범위 밖 파일은 수정하지 않는다. 단 `docs/loop/**`는 예외다.
