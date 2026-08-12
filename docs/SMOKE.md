# 수동 스모크 절차 — 실제 Ollama 모델 1회 (FR-020)

릴리즈 전 최종 수동 확인 단계다(자동 CI 게이트 아님). mock이 아닌 실제 로컬 Ollama로
파이프라인을 1회 돌려 산출물 품질과 계약(한국어 출력·템플릿·스킵/종료 코드)을 확인한다.

## 사전 조건
- 로컬 Ollama 데몬 기동 (`ollama serve` 또는 앱 실행).
- 모델 준비. 스펙 기본값은 `qwen2.5:7b-instruct`. 없으면 `ollama pull qwen2.5:7b-instruct`,
  또는 이미 받아 둔 다른 모델을 `--model`로 지정한다(설치·pull은 CorpBrain이 하지 않는다).
- 개발 환경: `uv venv --python 3.12 && uv sync && uv pip install -e .`

## 스모크용 실샘플
소형 실샘플(정상 `.txt`/`.md`/`.docx` 소수)을 임의 폴더에 둔다. 예시로 이 저장소는
`tests/fixtures/sample_corpus/`(정상 txt·md·docx + 하위폴더·빈 파일·미지원·초과 파일)를
갖고 있으나, 순수 정상 문서만으로 스모크하려면 별도 폴더에 `.txt`/`.md` 2~3개를 만든다.

## 실행 — Scenario 1 (정상)
```
uv run corpbrain scan <sample> --out <tmp_out> --model qwen2.5:7b-instruct
```
기대(스펙 §3-1·2, §4.1, §4.3, §4.4):
- [ ] 지원 파일마다 `<원본이름.확장자>.md`가 입력 하위구조를 미러링하여 생성된다.
- [ ] 각 `.md`에 front-matter 4키(`source_path`/`generated_at`/`model`/`source_bytes`)가 있다.
- [ ] 6섹션(`# 제목`/`## 한 줄 요약`/`## 핵심 포인트`/`## 요약`/`## 태그·키워드`/`## 원문`)이 있다.
- [ ] 요약·핵심 포인트·태그가 **한국어**로 채워진다.
- [ ] 종료 요약에 `처리 N건 / 스킵 M건(+사유)` 과 `출력 경로`가 stderr로 표시된다.
- [ ] 종료 코드 0 (부분 실패가 있어도 0).

## 실행 — Scenario 2 (Ollama 미기동)
데몬을 끄거나 닿지 않는 포트를 지정해 선행 조건 실패를 확인한다.
```
uv run corpbrain scan <sample> --out <tmp_out> --ollama-url http://127.0.0.1:1
```
기대(스펙 §4.3, §5):
- [ ] 설치를 시도하지 않고 비-0 종료.
- [ ] stderr에 미탐지 사유가 남는다.

## 실행 기록 (2026-08-12)
- 모델: `qwen2.5:7b` (로컬 보유. 스펙 기본값 `qwen2.5:7b-instruct`는 미보유라 `--model`로 지정).
- 샘플: `sales.txt`(영업 실적 문단), `roadmap.md`(로드맵 불릿) 2건.
- Scenario 1: 처리 2건 / 스킵 0건, 종료 코드 0. 소요 약 24초(2건 합산, M-계열 로컬).
  - 산출물 `sales.txt.md`: front-matter 4키·6섹션 모두 존재, 제목/요약/핵심포인트/태그가
    자연스러운 한국어로 채워짐. `## 원문` 링크가 `file://` 절대경로로 생성됨.
  - `## 태그·키워드`는 쉼표 구분 한 줄(`영업 실적, 매출 증가, 신규 고객`)로 렌더됨.
- Scenario 2 (`--ollama-url http://127.0.0.1:1`): `선행 조건 실패: 구동 중인 로컬 Ollama를
  찾지 못했습니다 ... Connection refused`, 종료 코드 1. 설치 시도 없음.
- 이상 여부: 없음. 계약(한국어·템플릿·스킵/종료 코드) 모두 충족.

## run-status 관측 계층 스모크 (실행 진행상태)
스펙: `static/docs/specs/features/corpbrain-run-status-observability.md`. 실행 중 stderr
라이브 라인을 확인한다. TTY에서 실행해야 `\r` 제자리 갱신이 보인다.

### 실행 A — 라이브 진행 라인 (TTY)
```
uv run corpbrain scan <sample> --out <tmp> --model qwen2.5:7b-instruct
```
- [ ] `[i/total]` 카운터가 파일마다 증가한다.
- [ ] 현재 파일명·세부 단계(`extract`/`summarize`/`render`/`write`)가 나온다.
- [ ] 첫 요약 구간에 `loading=true`, 이후 `loading=false`(모델 로딩 근사 표기).
- [ ] `경과 MM:SS`·`ETA`·`N.N/min`·`생성/스킵`·`net Xs`가 표시된다.
- [ ] 블로킹 요약 중 라인이 잠시 정지한다(이벤트 구동 — 의도된 동작).
- [ ] 완료 후 기존 종료 요약이 유지되고 종료 코드 0.

### 실행 B — stdout 공백 불변
`... > stdout.txt` → `stdout.txt`가 0바이트, 진행 라인은 stderr로만 나온다.

### 실행 C — 비-TTY 폴백
`... 2> progress.log` → `\r` 대신 이벤트별 개행으로 각 단계가 한 줄씩 누적된다.

## 실행 기록 (2026-08-12, run-status + CPU 우회)
- 환경 특이사항: 로컬 Ollama가 GPU에서 `CUDA error: the provided PTX was compiled with an
  unsupported toolchain`(HTTP 500)으로 모델 실행에 실패 — 입력 크기와 무관하게 전건 실패.
  원인은 NVIDIA 드라이버 ↔ Ollama CUDA 런타임 버전 불일치(환경 문제, CorpBrain 무관).
  CorpBrain은 스펙 §5대로 각 파일을 `summary_failed`로 스킵+로그하고 크래시 없이 종료 코드 0.
- 우회: Ollama 서버를 `CUDA_VISIBLE_DEVICES=-1`(+`OLLAMA_LLM_LIBRARY=cpu`)로 재시작해 CPU
  추론으로 전환. **주의: 이 env는 해당 서버 프로세스 한정 — 트레이 앱 재시작·재부팅 시 GPU
  모드로 복귀해 500이 재발한다. 근본 해결은 NVIDIA 드라이버 업데이트.**
- 모델: `qwen2.5:7b-instruct`(CPU). 샘플: `sales.txt`, `roadmap.md` 2건.
- 결과: 처리 2건 / 스킵 0건, 종료 코드 0, stdout 0바이트. 요약당 CPU 소요 약 52~62초.
  - 산출물 `roadmap.md.md`: front-matter 4키·6섹션 모두 존재, 제목/요약/핵심포인트/태그가
    자연스러운 한국어로 채워짐, `## 원문` `file://` 링크 생성. (A/B/C 항목 모두 충족)
  - 라이브 라인: index/total·stage·`loading` 전환·경과/ETA/rate·net 지연 모두 정상 표시.
- 관문 개선(별건): `gateway.py`가 HTTP 오류 본문을 버리던 문제를 고쳐, 이후 500 시 서버
  메시지(`{"error": ...}`)가 종료 로그에 함께 표시된다(테스트 3건 추가).
- 이상 여부: 없음(환경 CUDA 이슈 제외). run-status 계약·CPU 경로 모두 충족.
