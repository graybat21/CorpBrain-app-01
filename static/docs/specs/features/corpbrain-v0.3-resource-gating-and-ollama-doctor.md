# 스펙: CorpBrain v0.3 — 자원 게이팅 + Ollama doctor (환경·게이팅)

- 상태: 확정
- 최종 갱신: 2026-08-13

## 1. 목표
v0.2가 추정·표시만 하던 자원 정보를 v0.3에서 **강제 게이트**로 승격한다. GPU 유무·개별
파일 크기·스캔 전체 토큰 총량이 임계를 넘으면 처리를 차단하거나 해당 파일을 스킵하고,
사용자는 명시적 플래그로만 강행한다. 아울러 내부 LLM(Ollama) **연동을 진단·안내로 간편화**
한다 — Ollama 미설치/미구동/대상 모델 없음을 구분 감지해 정확한 해결 명령을 안내하고,
신규 `corpbrain doctor` 명령으로 환경 준비 상태를 종합 점검한다. 외부로 나가는 통신은 v0.2와
동일하게 로컬 Ollama 호출 외 전무하며, 자동 설치·자동 pull은 하지 않는다. [사용자 결정]

## 2. 비목표
이번 슬라이스에서 다음은 하지 않는다.
- Ollama 자동 설치·프로비저닝, 모델 자동 pull(`ollama pull` 대행). 진단·안내만 한다. [사용자 결정]
- GPU 감지 확장(AMD·Apple Silicon Metal 등). `nvidia-smi` 기반 탐지를 유지하며, 비-NVIDIA
  환경은 GPU가 있어도 CPU로 판정되어 `--force-gates`로 진행한다. [사용자 결정·파생]
- 워크로드 의존 게이트(파일 크기·토큰 총량)를 `doctor`에서 판정. `doctor`는 folder 인자가
  없는 환경 전용 점검이라 워크로드를 알 수 없다. [파생]
- 자원 임계 초과 시 자동 다운그레이드(파일 수·`--max-chars` 자동 축소 등). 차단형만 채택한다. [사용자 결정·파생]
- 클라우드/외부 LLM, PII 마스킹·NetworkGuard, 벡터DB·임베딩. 로드맵상 v0.5+. [로드맵]

## 3. 완료의 정의
아래를 모두 만족한다. 검증 방식(전반): 게이트 판정·진단 조립은 순수 코어를 단위테스트로,
파이프라인·doctor는 Ollama HTTP를 mock으로 스텁한 통합테스트로 검증하고, 마무리로 실제
모델 1회 수동 스모크를 실행한다.

1. `detect_hardware`를 mock해 GPU=False로 만든 상황에서 `scan`은 파일을 처리하지 않고
   **exit 1**(선행조건 실패)로 종료하며, 사유와 `--force-gates` 안내를 낸다. `--force-gates`를
   주면 정상 진행한다.
   - 검증: 통합테스트(하드웨어 mock) — exit 코드·처리 0건·안내 문자열·강행 동작 확인.
2. 스캔 전체 `total_est_tokens`가 `--max-total-tokens`(기본 200,000)를 초과하면 `scan`은
   pre-scan 단계에서 처리를 중단하고 **exit 3**(상한 초과) + 안내를 낸다. `--force-gates`를
   주면 진행한다.
   - 검증: 통합테스트(임계를 낮춘 픽스처) — exit 코드·중단·강행 동작 확인.
3. 개별 파일 크기가 `--max-file-size`(기본 20MB)를 초과하면 산출물 없이 스킵 리포트에
   신규 사유 `file_too_large`로 나타나고, 임계 이하 파일은 정상 생성되며 전체 종료 코드는
   **0**이다(부분 성공).
   - 검증: 통합테스트 — 초과 파일의 `.md` 부재·스킵 사유·이하 파일 생성·exit 0 확인.
4. `plan`과 `scan --dry-run`은 게이트 판정(예: "GPU 없음 → 차단됨", "총 토큰 예산 초과",
   `file_too_large`로 스킵될 파일 수)을 리포트에 **표시만** 하고 항상 **exit 0**, 위키 0개이며,
   `plan`은 네트워크 호출 0을 유지한다.
   - 검증: 단위/통합 + 보안(소켓 워처로 localhost 포함 0, `gateway.requested_urls()` 빈 상태).
5. `--force-gates`는 차단 게이트(GPU·토큰)만 무시하고 `file_too_large` 스킵에는 영향을 주지
   않는다. 대용량 파일을 포함하려면 `--max-file-size`를 올린다.
   - 검증: 통합테스트 — `--force-gates` 하에서도 초과 파일이 `file_too_large`로 스킵됨을 확인.
6. `corpbrain doctor`는 다음을 낸다: (a) Ollama 미설치(`shutil.which` None) → **exit 1** + 안내,
   (b) 데몬 미구동(`/api/tags` 실패) → **exit 1** + 안내, (c) 대상 모델 없음(모델 목록에 부재)
   → **exit 1** + `ollama pull <model>` 안내, (d) 모두 준비 → **exit 0**. GPU 없음은 경고로
   표시하되 (d) 판정에 영향을 주지 않는다.
   - 검증: 통합테스트(gateway·`shutil.which` mock) — 네 상황의 exit 코드·안내·GPU 경고 확인.
7. `scan` 프리플라이트는 대상 모델이 없으면 파일을 처리하지 않고 **exit 1** +
   `ollama pull <model>` 안내로 즉시 종료한다.
   - 검증: 통합테스트(`/api/tags` 모델 목록 스텁) — 처리 0건·exit 1·안내 확인.
8. 모든 네트워크 호출은 단일 관문(`gateway.request_json`)을 경유하고 localhost 외 연결이 0이며,
   `ollama_client`는 네트워크-순수를 유지한다(`shutil`/`subprocess`/`os` 미import — 정적 검사).
   `shutil.which`는 네트워크가 아니며 신규 진단 모듈이 담당한다.
   - 검증: 보안 테스트(소켓 워처) + 정적 import 검사.
9. 하위 호환·green: 신규 플래그 없이 기존 `scan`/`plan` 동작은 불변이되, GPU 없는 환경에서
   `scan`이 이제 차단되는 것은 **의도된 파괴적 변경**이며 `docs/USAGE.md`의 v0.3 섹션과 GitHub
   Release(tag `v0.3`) 노트에 BREAKING으로 명시한다. `ruff check .`·`pytest`가 모두 통과한다.
   - 검증: 회귀 테스트 + `ruff check .` + `pytest`.

## 4. 인터페이스 계약

### 4.1 CLI
```
corpbrain scan <folder>
  ... (v0.2 인자 유지) ...
  --force-gates            차단 게이트(GPU·토큰)를 무시하고 강행 (기본 off)
  --max-file-size MB       개별 파일 크기 상한, 초과 시 file_too_large로 스킵 (기본 20)
  --max-total-tokens N     스캔 전체 예상 토큰 예산, 초과 시 차단 (기본 200000)

corpbrain plan <folder>
  ... (v0.2 인자 유지) ...
  --max-file-size MB       표시용 임계 (기본 20)
  --max-total-tokens N     표시용 임계 (기본 200000)
  # plan은 --force-gates를 받지 않는다(차단하지 않음). 네트워크 0 유지.

corpbrain doctor
  --model NAME             점검할 대상 모델 (기본 CORPBRAIN_MODEL 또는 코어 기본값)
  --ollama-url URL         기본 http://127.0.0.1:11434
  # folder 인자 없음(환경 전용 점검).
```
- 종료 코드: `0`(정상) / `1`(선행조건 실패 — GPU 미탐지 차단, Ollama 미설치·미구동·모델 없음)
  / `3`(상한 초과 — 토큰 예산 차단, 기존 max_files와 동일). 신규 코드 없음. [제안 후 승인]
- 출력 언어: 한국어. 신규 환경변수 없음(플래그만). [사용자 결정·파생]

### 4.2 게이트 판정 규칙 [사용자 결정]
- **GPU 게이트**: `detect_hardware().gpu == False`면 규모 무관 무조건 차단(scan), exit 1.
  `--force-gates`로만 강행.
- **토큰 게이트**: `total_est_tokens > max_total_tokens`면 pre-scan 전체 차단(scan), exit 3.
  `--force-gates`로만 강행. `total_est_tokens` 산정 대상은 §4.4(스킵 예정·미지원 파일 제외).
- **파일 크기 게이트**: 개별 파일 `size_bytes > max_file_size`면 그 파일만 신규 SkipReason
  `file_too_large`로 스킵(부분 성공). `--force-gates` 영향 없음 — `--max-file-size`로 조정.
- `plan`/`scan --dry-run`은 위 판정을 표시만 하고 차단하지 않는다(exit 0).

**scan 프리플라이트 순서(fail-fast)** [사용자 결정]
검문소는 아래 순서로 돌며, 첫 위반에서 그 단계의 종료 코드로 즉시 종료한다(뒤 단계는 돌지 않음).
1. 폴더 검증(`validated_root`) — 실패 시 exit 1.
2. Ollama 데몬 구동(`detect` → `/api/tags`) — 실패 시 exit 1.
3. 대상 모델 존재(모델 목록 파싱) — 부재 시 exit 1 + `ollama pull <model>` 안내.
4. GPU 게이트 — 미탐지 시 exit 1.
5. 토큰 게이트 — `total_est_tokens > max_total_tokens` 시 exit 3.
- 환경(Ollama·모델)을 자원 게이트보다 먼저 확정한다 — 요약 자체가 불가능한 조건을 우선한다.
- `--force-gates`는 4·5만 우회한다. 1~3(폴더·Ollama·모델)은 우회 불가.
- 이 순서는 scan 전용이다. `plan`은 네트워크 0을 유지하므로 2·3을 돌지 않고, 4·5는 표시만 한다.
  `doctor`는 fail-fast가 아니라 전 항목을 점검해 집계 보고한다(§4.3).

### 4.3 Ollama 진단·연동 [사용자 결정·제안 승인]
- 범위: 진단·안내만. 자동 설치·자동 pull 없음. "기본 로컬 외부 0" 불변식 유지.
- `detect()`를 확장: 데몬 응답 여부에 더해 `/api/tags` 모델 목록을 파싱해 **대상 모델 존재**를
  확인한다. 모델 부재는 선행조건 실패(exit 1) + `ollama pull <model>` 안내.
- **모델 이름 매칭 규칙** [사용자 결정]: `/api/tags`의 각 `name`과 대상 모델을 **태그 정규화 후
  정확 일치**로 비교한다 — `:` 없는 이름은 `:latest`를 보정해 비교한다(`llama3` == `llama3:latest`).
  접두·부분 매칭은 쓰지 않는다(오매치 방지). 비교는 대소문자를 구분한다.
- **`doctor` 점검 항목·출력 형식** [제안 후 승인]: 한국어 체크리스트를 stdout에 낸다. 항목 순서 =
  Ollama 설치 → 구동 → 대상 모델 → GPU → 게이트 임계값(정보). 각 줄은 상태 마커(OK/실패/경고)와
  실패 시 해결 명령을 함께 낸다:
  - 미설치 → "Ollama 미설치 — https://ollama.com 에서 설치"
  - 미구동 → "Ollama 데몬 미구동 — `ollama serve` 실행"
  - 모델 없음 → "모델 &lt;name&gt; 없음 — `ollama pull &lt;name&gt;`"
  - GPU 없음 → 경고 줄(실패 아님), 임계값은 정보 줄(`max_file_size`·`max_total_tokens`).
  (설치 URL·명령 문자열은 평문 출력일 뿐 네트워크 호출이 아니다.)
- **게이트 판정 렌더** [제안 후 승인]: `report.py`가 담당한다. `build_plan_report_lines`는 게이트
  섹션(GPU 판정 · 총토큰/예산 · `file_too_large` 예정 파일 수)을 덧붙이고,
  `build_scan_banner_lines`는 한 줄 게이트 요약을 포함한다. scan 실제 차단 시 stderr 메시지는 발동
  게이트와 해결책(`--force-gates` 또는 `--max-file-size`)을 함께 낸다.
- `scan`/`plan` 실패 메시지는 `doctor`와 **같은 진단 코어**를 재사용해 actionable하게 낸다.

### 4.4 구조 제약 (기존 이음새 준수) [제안 후 승인]
- 신규 config 필드: `max_file_size: int`(바이트, 기본 20,000,000), `max_total_tokens: int`
  (기본 200,000), `force_gates: bool`(기본 False). 코어가 기본값을 소유한다.
- **게이트 판정 값 타입**: `models.py`에 신규 frozen dataclass `GateVerdict`를 추가한다(필드:
  `gpu_ok: bool`, `tokens_ok: bool`, `oversized_count: int`, 유효 임계값 에코). `ScanPlan`에
  `gate: GateVerdict` 필드를 더한다. `plan_scan`이 이 값을 순수·로컬로 계산하며(신규 config 필드를
  읽음), CLI는 이를 종료 코드·메시지로 매핑하는 얇은 어댑터 역할만 한다.
- **진단 코어 모듈**: 신규 `core/environment.py`가 설치 감지(`shutil.which("ollama")`, 로컬·비네트워크)와
  doctor 리포트 조립(`detect_hardware` + 모델 존재 확인 결과 합성)을 담당한다. 모델 목록 파싱·매칭은
  `ollama_client`(네트워크-순수, 단일 관문 경유)가 제공하고 `environment.py`가 이를 호출해 합성한다.
  `ollama_client`는 `shutil`/`subprocess`/`os`를 import하지 않는다.
- **토큰 예산 산정 대상**: `total_est_tokens`(토큰 게이트·표시 기준)는 실제로 요약될 파일만 합산한다 —
  미지원 확장자(기존 제외)와 `size_bytes > max_file_size`(스킵 예정) 파일을 제외한다. 곧 스킵될 파일이
  예산을 헛되이 초과시키지 않게 함이다. 대용량 파일은 표시용 집계(`oversized_count`)로 별도 노출한다.
- 게이트 판정은 순수 코어 값(`GateVerdict`)으로 산출하고, CLI는 종료 코드·메시지 매핑만 한다.
- `plan_scan`은 네트워크 0을 유지한다(v0.2 완료의 정의 3 보존). 모델 선점검은 scan·doctor에서만.

## 5. 엣지 케이스와 실패 시나리오 [사용자 결정·제안 승인]
- GPU 없음 + 소규모 워크로드: 그래도 차단(무조건). `--force-gates`로 진행.
- 비-NVIDIA GPU(Apple/AMD): CPU로 판정되어 차단. `--force-gates`로 진행(비목표로 문서화).
- 토큰 예산 초과 + `--force-gates`: 차단 해제하고 진행.
- 대용량 파일 다수: 각 파일이 `file_too_large`로 스킵되고 나머지는 처리(exit 0).
- `--force-gates` + 대용량 파일: 파일은 여전히 `file_too_large`로 스킵된다.
- Ollama 미설치 vs 미구동 vs 모델 없음: `doctor`·`scan`이 세 상황을 구분해 각기 다른 사유·
  해결 명령으로 안내한다(모두 exit 1).
- Ollama·모델 문제는 선행조건이며 `--force-gates`로 우회되지 않는다(요약 자체가 불가능).
- 복수 위반(예: Ollama 미구동 + GPU 미탐지): scan은 fail-fast 순서(§4.2)를 따라 Ollama 오류가
  먼저 표면화되고 exit 1로 종료한다. 전 항목 집계 뷰가 필요하면 `doctor`를 쓴다.
- `plan`/`--dry-run`은 어떤 게이트에도 차단되지 않으며 네트워크를 열지 않는다.

## 미결정 사항
없음
