/goal

## 1) 작업 핵심 목표 및 범위
- 목표: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md` 의 "완료의 정의"(§3) 13개 항목을 모두 구현해 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이 되게 하고, `/security-review` 를 통과한 뒤 변경을 draft PR로 올린다.
- 시작 지점: `main`(tag v0.4 완료 상태)에서 `feat/v0.5-cloud-opt-in` 브랜치를 새로 만들어 착수한다. 착수 직후 현재 미커밋(untracked) 상태인 `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md` 와 `docs/grill/GRILL_LEDGER-v0.5.md` 두 문서를 **내용 수정 없이** 브랜치의 첫 커밋으로 포함한다.
- 작업 대상: v0.5 스펙이 정의한 클라우드 옵트인 경로 전체 — 신규 `corpbrain/core/pii.py`·`corpbrain/core/consent.py`·`corpbrain/core/llm/anthropic_client.py`, 확장 대상 `corpbrain/core/gateway.py`(headers 파라미터·NetworkGuard·리다이렉트 차단)·`corpbrain/core/config.py`·`corpbrain/core/models.py`·`corpbrain/core/errors.py`·`corpbrain/core/pipeline.py`·`corpbrain/core/rerun.py`·`corpbrain/core/render.py`·`corpbrain/core/report.py`·`corpbrain/core/environment.py`·`corpbrain/core/llm/summarize.py`·`corpbrain/cli.py`, 그리고 대응 `tests/`(신규 `tests/test_pii.py`·`tests/test_consent.py`·`tests/test_anthropic_client.py` 포함, 기존 `tests/security/test_network_invariant.py` 확장). 문서 갱신은 `docs/USAGE.md` 의 v0.5 섹션 신설(기존 "이번 범위 밖 (v0.5 이후)" 대목을 v0.5 반영 상태로 갱신).
- 작업 자율성: 종료 조건에 도달하거나 목표가 완료될 때까지 사용자 확인 없이 자율 진행한다. 단 main 머지·force push·`git tag`·GitHub Release·`pyproject.toml` 버전 범프·실제 Anthropic API 호출(비-mock)은 하지 않는다.

## 2) 작업 세부 규칙
- 세부 구현 계약은 v0.5 스펙(§3 완료의 정의 · §4 인터페이스 계약 · §5 엣지 케이스)과 `docs/grill/GRILL_LEDGER-v0.5.md`(확정된 8개 결정: NetworkGuard 매칭 방식 · 인증 프리플라이트 · 타임아웃 · SkipReason 매핑 · PII 정규식 7종 · 프롬프트/tool 스키마 · 원자적 쓰기 · doctor 출력)를 정본으로 삼아 그대로 구현한다. 스펙에 없는 동작을 임의로 추가하지 않고, 비목표(§2)를 슬쩍 넣지 않는다.
- 워크플로: 스펙 "완료의 정의" 항목 단위로 TDD 사이클(Red 실패 테스트 → Green 구현 → Refactor → 항목 검증)을 돈다. 기존 코드의 불변식을 유지한다 — 코어/CLI 이음새, **단일 게이트웨이**(모든 외부 호출은 `gateway.request_json` 경유), 코어 no-I/O, 하위 호환(신규 파라미터는 선택·기본값 보존, `--engine` 미지정 시 v0.4 동작 불변).
- **병렬 개발(서브에이전트 2개 이상 활용)**: 아래 파트 A·B는 서로도, 메인 작업과도 파일이 겹치지 않는 독립 leaf 모듈이므로 **한 메시지에서 서브에이전트 2개를 동시에 띄워 병렬로 구현**한다.
  - 파트 A (서브에이전트 1): `corpbrain/core/pii.py` + `tests/test_pii.py` — 스펙 §4.5의 정규식 7종 표를 그대로 구현한 탐지·마스킹 순수 함수와 그 단위테스트. 다른 파일은 건드리지 않는다.
  - 파트 B (서브에이전트 2): `corpbrain/core/consent.py` + `tests/test_consent.py` — 스펙 §4.2의 `~/.corpbrain/config.json` 읽기/쓰기(원자적 쓰기: 임시파일 + `os.replace`), grant/revoke 코어 함수와 그 단위테스트. **CLI 배선은 하지 않는다**(`cli.py` 미수정). 다른 파일은 건드리지 않는다.
  - 파트 C (메인 에이전트, 직렬): 공유 파일 전체 — `gateway.py` 확장, `anthropic_client.py`, Summarizer 인터페이스·두 구현체, `pipeline.py`/`rerun.py`/`render.py`/`report.py`/`environment.py` 통합, `cli.py`(`--engine`·`--cloud-model`·`consent` 서브커맨드 배선), 통합·보안 테스트. 파트 A·B가 반환되면 그 산출물을 여기에 배선한다.
  - 서브에이전트에는 v0.5 스펙 경로와 해당 절(§4.5 또는 §4.2)을 명시해 전달하고, "지정된 2개 파일 외에는 생성·수정하지 말라"를 지시에 포함한다.
- 브랜치·PR: 단일 `feat/v0.5-cloud-opt-in` 브랜치에서 작업하고, 착수 직후 draft PR을 열어 커밋을 누적한다. 커밋 메시지는 저장소 관례(예: `v0.5(pii): ...`, `v0.5(gateway): ...`, `v0.5(cli): ...`)를 따른다.
- 의사결정 기록(조기 종료 카운터): 구현 중 **기존 문서(v0.5 스펙·`GRILL_LEDGER-v0.5.md`·`docs/ROADMAP.md`·상위 버전 스펙)가 명확히 정해두지 않은** 새 결정을 내려야 할 때마다 `docs/loop/DECISION_CHECKPOINT-v0.5.md` 에 한 줄로 기록하고 CORE/MINOR로 분류한 뒤 해당 카운터를 +1 한다(규격 §6). 이미 정해진 사항은 카운트하지 않는다. 결정을 메모리에만 두지 않는다.
- 명령 표준: 프로젝트는 `uv` 관리. 테스트 `uv run pytest`, 린트 `uv run ruff check .`. Anthropic·Ollama 연동 테스트는 모두 게이트웨이(`gateway.request_json`)·소켓 레벨 mock으로 스텁하며 실제 API·데몬에 접속하지 않는다.
- 보안 검토: 구현이 완료되어 두 검증 명령이 exit 0 이 된 뒤, PR을 draft에서 올리기 전 `/security-review` 를 1회 실행한다(스펙 §3 항목 13). 지적된 고위험 항목(API 키 유출·PII 마스킹 우회·allowlist 우회)은 수정하고, 수정이 새 결정을 요구하면 그 결정도 체크포인트에 카운트한다.

## 3) 종료 조건 및 종료 방법
- 종료 조건 (아래 중 하나라도 충족되는 순간 루프를 즉시 멈춘다):
  - `docs/loop/DECISION_CHECKPOINT-v0.5.md` 의 `CORE:` 카운터가 3에 도달 → STOP REASON: CORE_BUDGET
  - 같은 문서의 `MINOR:` 카운터가 10에 도달 → STOP REASON: MINOR_BUDGET
  - v0.5 스펙 "완료의 정의" 13개 항목이 모두 충족되고 `uv run ruff check .` 와 `uv run pytest` 가 exit 0 이며 `/security-review` 의 미해결 고위험 지적이 0건 → STOP REASON: ALL_DONE
  - 평가-진행 라운드(turn = /goal 평가자가 진행 상태를 한 번 점검하는 메인 에이전트 응답 사이클)가 누적 60회 도달 → STOP REASON: TURN_CAP (= or stop after 60 turns)
- 종료 방법:
  1) `docs/loop/DECISION_CHECKPOINT-v0.5.md` 마지막 줄에 `STOP REASON: <원인 코드>` 한 줄을 덧붙인다.
  2) `uv run ruff check . && uv run pytest` 를 실행해 두 명령의 exit 코드(0/비-0) 출력을 대화에 남겨 증명한다.
  3) `cat docs/loop/DECISION_CHECKPOINT-v0.5.md` 를 실행해 `CORE: N`·`MINOR: M` 카운터 줄과 `STOP REASON:` 줄이 보이는 출력을 대화에 남긴다.
  4) `git diff --name-only main` 을 실행해 변경 파일이 §1 작업 대상 범위 안에만 있음을 대화에 남긴다.
  5) `gh pr list` 를 실행해 이 루프가 연 draft PR을 대화에 남긴다(gh 사용 불가 시 `git log --oneline -10` 으로 대체).

## 4) 기타 제약조건
- 금지: 어떤 PR도 main에 merge하지 않는다. force push·`git tag`·GitHub Release 생성·자동배포 유발 금지. `pyproject.toml`/`uv.lock` 의 버전 범프 금지(릴리스는 사용자가 tag 시점에 별도로 수행). 실제 Anthropic API·비-localhost 외부 호출 금지 — 모든 네트워크는 테스트에서 mock으로만 다룬다.
- 수정 금지: `static/docs/specs/features/*.md`(v0.5 스펙 포함 — 구현을 스펙에 맞추되 스펙을 바꾸지 않는다. 단 §1이 지시한 "미커밋 파일을 그대로 커밋"은 내용 변경이 아니므로 허용), `docs/ROADMAP.md`, `docs/grill/GRILL_LEDGER-v0.5.md` 및 다른 버전 원장, `CLAUDE.md`, 다른 버전 스펙, 기존 `docs/loop/DECISION_CHECKPOINT*.md`(v0.5 것 제외).
- 활성 범위(§1 작업 대상) 밖 파일은 수정하지 않는다. 예외: `docs/loop/DECISION_CHECKPOINT-v0.5.md`, `docs/USAGE.md`(v0.5 섹션), `reports/`.
- 스펙이 비목표로 못박은 것을 구현하지 않는다: 복수 provider·임의 엔드포인트, 임베딩의 클라우드 경로, ML 기반 PII 탐지, 자동 재시도/백오프, 파일별 자동 라우팅/폴백, API 키 디스크 저장, RAG 답변 합성.

## 5) GitHub 연동 규칙
- `gh` CLI로 draft PR 생성·갱신만 한다(`gh pr create --draft`, 이후 push로 갱신). 리뷰 요청·머지·라벨/마일스톤 정책 변경은 하지 않는다.
- PR 본문에는 구현한 "완료의 정의" 항목 번호와 `DECISION_CHECKPOINT-v0.5.md` 카운터 현재값(`CORE: N`·`MINOR: M`), `/security-review` 결과 요약을 적는다.
- gh 인증이 없거나 원격 push가 거부되면 STOP하지 말고, 로컬 커밋을 유지한 채 그 사실을 대화에 남기고 구현을 계속한다(PR은 종료 방법 5)에서 재시도).

## 6) 의사결정 체크포인트 문서 규격 (`docs/loop/DECISION_CHECKPOINT-v0.5.md`)
- 멀티에이전트가 동시에 읽어도 명확하도록, 문서 상단에 grep 가능한 카운터 두 줄을 항상 유지한다:
  - `CORE: N`
  - `MINOR: M`
- 문서가 없으면 착수 시 `CORE: 0` / `MINOR: 0` 으로 생성한다(이미 시드돼 있으면 그대로 이어쓴다).
- 분류 기준:
  - CORE = 아키텍처·보안·외부 의존·데이터 모델·공개 API/CLI 계약·핵심 UX 계약에 관한 신규 결정.
  - MINOR = 네이밍·디렉터리·로그 문구·테스트 픽스처·내부 헬퍼 등 국소 결정.
- 각 결정은 한 줄로 `- [CORE|MINOR] <결정> | 근거 | 관련 파일 | 결정 주체(main|sub-A|sub-B)` 형식으로 적고, 기록 직후 해당 카운터를 +1 한다.
- **쓰기 직렬화**: 카운터 유실을 막기 위해 이 문서에 **직접 쓰는 것은 메인 에이전트만** 한다. 서브에이전트(파트 A·B)는 이 파일을 수정하지 않고, 자신이 내린 새 결정을 최종 보고에 목록으로 반환한다. 메인 에이전트가 서브에이전트 보고를 받은 직후 이를 문서에 반영하고 카운터를 갱신한다. 어느 에이전트든 **읽기**는 언제든 가능하며, 현재 카운터 값은 항상 이 문서가 정본이다.
- 이미 v0.5 스펙·`GRILL_LEDGER-v0.5.md`·`docs/ROADMAP.md`에 정해진 사항은 여기에 적지 않는다(중복·오카운트 방지).
- 이 문서는 조기 종료 판정의 **단일 근거**다 — CORE_BUDGET(≥3)·MINOR_BUDGET(≥10)은 오직 이 카운터로만 판정한다. 카운터가 임계에 닿으면 미해소 결정이 누적된 신호이므로 즉시 STOP하고 `/interview`·`/grill-it`로 되돌린다.
