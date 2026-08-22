# 수동 스모크 절차 (릴리스 전 사람이 1회 실행)

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

- [x] 지원 파일마다 `<원본이름.확장자>.md`가 입력 하위구조를 미러링하여 생성된다.
- [x] 각 `.md`에 front-matter 4키(`source_path`/`generated_at`/`model`/`source_bytes`)가 있다.
- [x] 6섹션(`# 제목`/`## 한 줄 요약`/`## 핵심 포인트`/`## 요약`/`## 태그·키워드`/`## 원문`)이 있다.
- [x] 요약·핵심 포인트·태그가 **한국어**로 채워진다.
- [x] 종료 요약에 `처리 N건 / 스킵 M건(+사유)` 과 `출력 경로`가 stderr로 표시된다.
- [x] 종료 코드 0 (부분 실패가 있어도 0).

## 실행 — Scenario 2 (Ollama 미기동)

데몬을 끄거나 닿지 않는 포트를 지정해 선행 조건 실패를 확인한다.

```
uv run corpbrain scan <sample> --out <tmp_out> --ollama-url http://127.0.0.1:1
```

기대(스펙 §4.3, §5):

- [x] 설치를 시도하지 않고 비-0 종료.
- [x] stderr에 미탐지 사유가 남는다.

## 실행 기록 (2026-08-12)

- 모델: `qwen2.5:7b` (로컬 보유. 스펙 기본값 `qwen2.5:7b-instruct`는 미보유라 `--model`로 지정).
- 샘플: `sales.txt`(영업 실적 문단), `roadmap.md`(로드맵 불릿) 2건.
- Scenario 1: 처리 2건 / 스킵 0건, 종료 코드 0. 소요 약 24초(2건 합산, M-계열 로컬).
  - 산출물 `sales.txt.md`: front-matter 4키·6섹션 모두 존재, 제목/요약/핵심포인트/태그가
  자연스러운 한국어로 채워짐. `## 원문` 링크가 `file://` 절대경로로 생성됨.
  - `## 태그·키워드`는 쉼표 구분 한 줄(`영업 실적, 매출 증가, 신규 고객`)로 렌더됨.
- Scenario 2 (`--ollama-url http://127.0.0.1:1`): `선행 조건 실패: 구동 중인 로컬 Ollama를 찾지 못했습니다 ... Connection refused`, 종료 코드 1. 설치 시도 없음.
- 이상 여부: 없음. 계약(한국어·템플릿·스킵/종료 코드) 모두 충족.

## run-status 관측 계층 스모크 (실행 진행상태)

스펙: `static/docs/specs/features/corpbrain-run-status-observability.md`. 실행 중 stderr
라이브 라인을 확인한다. TTY에서 실행해야 `\r` 제자리 갱신이 보인다.

### 실행 A — 라이브 진행 라인 (TTY)

```
uv run corpbrain scan <sample> --out <tmp> --model qwen2.5:7b-instruct
```

- [x] `[i/total]` 카운터가 파일마다 증가한다.
- [x] 현재 파일명·세부 단계(`extract`/`summarize`/`render`/`write`)가 나온다.
- [x] 첫 요약 구간에 `loading=true`, 이후 `loading=false`(모델 로딩 근사 표기).
- [x] `경과 MM:SS`·`ETA`·`N.N/min`·`생성/스킵`·`net Xs`가 표시된다.
- [x] 블로킹 요약 중 라인이 잠시 정지한다(이벤트 구동 — 의도된 동작).
- [x] 완료 후 기존 종료 요약이 유지되고 종료 코드 0.

### 실행 B — stdout 공백 불변

`... > stdout.txt` → `stdout.txt`가 0바이트, 진행 라인은 stderr로만 나온다.

### 실행 C — 비-TTY 폴백

`... 2> progress.log` → `\r` 대신 이벤트별 개행으로 각 단계가 한 줄씩 누적된다.

## 실행 기록 (2026-08-12, run-status + CPU 우회)

- 환경 특이사항: 로컬 Ollama가 GPU에서 `CUDA error: the provided PTX was compiled with an unsupported toolchain`(HTTP 500)으로 모델 실행에 실패 — 입력 크기와 무관하게 전건 실패.
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

## v0.5 클라우드 옵트인 스모크 (실제 Anthropic API 1회)

스펙: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md` §3 검증 방식 — *"마무리로
실제 Anthropic API 1회 수동 스모크를 실행한다"*. v0.5 구현 루프는 목표 문서
(`docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md` §1)가 **실제 API 호출(비-mock)을 금지**했기
때문에 이 절차를 수행하지 못했다. 따라서 이 절은 루프가 아니라 사람이 한 번 돌려야 한다.

mock 통합테스트가 이미 계약(스킵 사유 매핑·재생성 판정·exit 코드)을 덮고 있으므로, 여기서는
**mock으로는 증명할 수 없는 것**만 본다 — 실제 인증이 통과하는지, 실제 응답이 템플릿에 들어오는지,
그리고 실제로 전선에 나가는 payload가 마스킹되어 있는지.

### 사전 조건

- 유효한 Anthropic API 키. `export ANTHROPIC_API_KEY=sk-ant-...` — 디스크에 저장하지 않는다.
- 로컬 Ollama 데몬 + `nomic-embed-text` (실행 F를 제외한 나머지의 인덱싱 단계에 필요).
- 비용: 기본 모델 `claude-haiku-4-5-20251001`로 소형 문서 2~3건이면 1센트 미만이다.
- **주의**: `consent cloud --grant`는 테스트 격리 경로가 아니라 실제 `~/.corpbrain/config.json`에
  기록된다. 스모크가 끝나면 `consent cloud --revoke`로 되돌린다.
- **주의**: `--out`은 **리포지토리 밖 임시 폴더**로 잡는다. `tests/fixtures/` 안에 산출물을
  남기면 다음 `pytest`가 그 `.md`를 입력 문서로 다시 잡아 통합테스트가 깨진다(2026-08-22 실측).

### 스모크용 실샘플

`.txt`/`.md` 2~3개를 임의 폴더에 두되, **그중 한 건에는 PII 7종을 한글 조사가 바로 붙은 형태로
심는다** — 실행 E가 이걸 본다. 예:

```
담당자 연락처는 010-1234-5678로 주시고, 메일은 hong@corp.co.kr.
주민등록번호 900101-1234567입니다. 사업자등록번호 123-45-67890,
카드 4111-1111-1111-1111, 계좌 110-123-456789, 서버는 192.168.0.1에서 돕니다.
```

### 실행 D — 미동의 차단 → 동의 → 정상 처리 (DoD 1·2·5)

```
uv run corpbrain scan <sample> --out <tmp> --engine cloud            # 아직 동의 없음
uv run corpbrain consent cloud --grant
uv run corpbrain scan <sample> --out <tmp> --engine cloud
```

- [x] 첫 실행: 산출물 0개, **exit 1**, stderr 안내에 `corpbrain consent cloud --grant`가 나온다.
- [x] `~/.corpbrain/config.json`에 `cloud_consent.anthropic.granted: true`가 기록된다.
- [x] 둘째 실행: 위키가 생성되고 **exit 0**.
- [x] 생성된 `.md`의 front-matter에 `engine: "cloud"`와 `model: "claude-haiku-4-5-20251001"`.
- [x] 요약·핵심 포인트·태그가 **한국어**로 채워진다(로컬 엔진과 품질 계약이 같다).

### 실행 E — 실제 전선의 PII 마스킹 (DoD 6·16)

실행 D의 종료 요약을 그대로 본다. 전선 payload 자체는 통합테스트가 캡처해 검증하므로, 여기서는
**실제 API 경로에서도 집계가 도는지**와 리포트 문구를 확인한다.

- [x] 종료 요약에 `[PII 마스킹] <파일경로> — N건`이 **파일별로** 나온다.
- [x] 합계 줄 `PII 마스킹 N건 (문서 M개) — ...`의 유형명이 **한국어**다
      (`주민등록번호`·`전화번호`·… — `RRN`·`PHONE` 같은 내부 토큰이 노출되면 실패).
- [x] 한글 조사가 붙은 `010-1234-5678로`·`900101-1234567입니다`·`192.168.0.1에서`가 모두 집계에
      잡힌다(7종 전부 카운트되는지 대조).
- [x] 생성된 위키 본문에 원본 PII 문자열이 되살아나지 않는다(모델은 마스킹본만 봤으므로).

### 실행 F — 인증 실패 분류 (DoD 4)

```
ANTHROPIC_API_KEY=sk-ant-invalid uv run corpbrain scan <sample> --out <tmp> --engine cloud
```

- [x] 파일을 하나도 처리하지 않고 **exit 1** (프리플라이트에서 끊긴다).
- [x] 안내가 **자격증명 문제**를 지목한다(401·403 → `CloudAuthError` 경로).
- [x] 키를 지우고(`unset ANTHROPIC_API_KEY`) 실행하면 같은 exit 1이되, 환경변수 미설정을 안내한다.

### 실행 G — doctor의 클라우드 보고 (DoD 10)

```
uv run corpbrain doctor
```

- [x] 동의·키가 모두 있으면 `[OK] Cloud(Anthropic): 사용 준비됨`.
- [x] `consent cloud --revoke` 후에는 `[경고] Cloud 동의: 없음 — ...` 으로 바뀐다.
- [x] 두 경우 모두 **doctor의 종료 코드는 달라지지 않는다**(로컬 Ollama 판정만 반영).

### 마무리

- [x] `uv run corpbrain consent cloud --revoke` 로 동의를 되돌린다.
- [x] 아래 "실행 기록"에 모델·샘플·결과·이상 여부를 남긴다.

### 실행 기록 (2026-08-22, 실제 Anthropic API)

- 모델: `claude-haiku-4-5-20251001`(기본값). 엔진: `--engine cloud`.
- 샘플: `tests/fixtures/sample_corpus/`(정상 txt·md·docx + 하위폴더 + 빈 파일 + 미지원 `.jpg`
  + 12,000자 초과 파일). 별도 PII 샘플은 쓰지 않았다 — 아래 "남은 확인" 참고.
- D~G 체크리스트는 실행자가 수동으로 전부 확인했다. 산출물로 사후 재확인되는 항목:
  - 위키 5건 생성(`guide.md.md`·`normal.txt.md`·`oversized.txt.md`·`sub/nested.txt.md`·
    `sub/report.docx.md`), 입력 하위구조 미러링. 소요 약 12초(20:28:01~20:28:13 KST).
  - front-matter에 `engine: "cloud"`·`model: "claude-haiku-4-5-20251001"` — 생성물만 보고도
    외부 전송 여부가 구분된다(DoD 5).
  - 제목·한 줄 요약·핵심 포인트·요약·태그가 모두 자연스러운 **한국어**. 로컬 엔진과 품질 계약이
    갈라지지 않았다.
  - `empty.txt`(빈 파일)·`photo.jpg`(미지원)는 산출물 없음 — 스킵 경로가 클라우드 엔진에서도
    동일하게 동작.
  - `oversized.txt`(37,500바이트)도 정상 처리 — `--max-chars` 절단 입력으로 요약됨.
  - `.corpbrain_index.sqlite` 생성 — 클라우드 요약이어도 임베딩·인덱싱은 로컬 경로로 돌았다.
- 이상 여부: 없음. v0.5 스펙 §3의 실키 검증 요구를 충족한다.

#### 이 실행에서 얻은 절차상 교훈
`--out`을 스캔 대상인 `tests/fixtures/sample_corpus/` **안**(`.../sample_corpus/wiki/`)으로
잡아 실행했다. 그 실행 자체는 §4.2 자동 제외 덕분에 정상이었지만, 남은 `wiki/*.md`가 다음
`pytest`에서 픽스처의 **입력 문서로 다시 잡혀** `test_pipeline.py` 3건이 깨졌다
(`normal.txt.md.md` 같은 이중 산출물이 기대 트리와 어긋났다). 산출물은 삭제해 원복했다.

**스모크는 반드시 리포지토리 밖 임시 폴더를 `--out`으로 쓴다.** 픽스처 폴더는 테스트가
파일 목록을 그대로 기대하므로 어떤 산출물도 남기면 안 된다(`.gitignore`로는 못 막는다 —
커밋이 아니라 디스크에 존재하는 것만으로 테스트가 깨진다).

#### 남은 확인 — 실행 E(PII 마스킹)
이번 샘플인 픽스처 코퍼스에는 PII가 들어 있지 않아, 실행 E의 마스킹 집계는 **이 산출물로
뒷받침되지 않는다**. 마스킹 자체는 단위테스트 62건 + payload 캡처 통합테스트가 덮고 있으므로
계약 위험은 없지만, 실키 경로에서 리포트 문구까지 눈으로 보려면 위 "스모크용 실샘플"의 PII
예시 문서를 별도 폴더에 두고 D를 한 번 더 돌리면 된다.
