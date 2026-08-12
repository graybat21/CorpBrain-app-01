# 스펙: CorpBrain 실행 진행상태(run-status) 관측 계층

- 상태: 완료
- 최종 갱신: 2026-08-12

## 1. 목표
`corpbrain scan`은 실행이 끝난 뒤에야 결과가 보여, 실행·대기 중에는 모델 로딩 상태·현재
처리 파일·진척도를 알 수 없다. 이 슬라이스는 스캔 실행의 진행상태를 실행 중에 관측 가능하게
한다. 코어 파이프라인이 구조화된 진행 이벤트를 방출하고, CLI 어댑터가 이를 stderr 라이브
라인으로 렌더한다. 코어는 I/O를 하지 않고 콜백만 호출한다(스펙
`corpbrain-mvp-local-scan-to-wiki.md` §4.5 이음새의 연장). [사용자 결정]

## 2. 비목표
이번 슬라이스에서 다음은 하지 않는다.
- 파일 sink(`status.json`/`events.jsonl`), localhost HTTP/SSE 서버, pywebview 연동,
  React 코드. [사용자 결정]
- 이벤트 계약(`ProgressEvent`/`StatusSnapshot`)의 공개 API 노출. 계약은 코어 내부
  전용으로 두고 `corpbrain/core/__init__.py`에 재노출하지 않는다. [사용자 결정]
- 부모 MVP 스펙의 처리 규칙·종료 코드·출력 템플릿 변경. [파생]

## 3. 완료의 정의
1. 기록용 sink를 넘겨 `run_scan(config, on_event=rec)`를 픽스처 코퍼스에 실행하면 이벤트가
   순서대로 방출된다: `run_started` → (첫 파일에서 `model_loading`→`model_ready`) →
   파일마다 `file_started`(index/total/bytes)·`file_stage`(해당 스테이지)·
   (`file_generated`|`file_skipped`) → `run_finished`.
   - 검증: 통합테스트에서 코어 API를 직접 호출(게이트웨이는 기존 `_ok_gateway`로 스텁),
     기록된 이벤트 순서·`index/total`·생성/스킵/종료 이벤트를 단언.
2. 각 `ProgressEvent.to_dict()`가 JSON 직렬화 가능하며 필수 키를 포함한다.
   - 검증: 단위테스트에서 `json.dumps(event.to_dict())` 성공 및 키 존재 확인.
3. `reduce(snapshot, event)`가 이벤트열을 정확한 `StatusSnapshot`으로 접는다.
   - 검증: 단위테스트에서 이벤트열 입력 → 기대 스냅샷 필드 비교.
4. `render_status_line(snapshot)`이 리치 세트 필드를 한 줄로 렌더한다.
   - 검증: 단위테스트에서 스냅샷 입력 → 기대 문자열 조각(index/total, stage, model,
     loading, elapsed, eta, rate 등) 포함 확인.
5. CLI 실행 시 라이브 라인은 stderr로만 나가고 stdout은 비며, 종료 코드는 기존 매핑을
   유지한다.
   - 검증: 어댑터 테스트에서 `capsys`로 `captured.out == ""` 및 stderr에 진행 라인 존재,
     종료 코드(`EXIT_OK`/`EXIT_PRECONDITION_FAILED`/`EXIT_LIMIT_EXCEEDED`) 확인.
6. `on_event=None`(기본값)에서 기존 전체 테스트 스위트가 통과한다(하위 호환).
   - 검증: 전체 `pytest` 실행 통과.
7. 보안 불변식(localhost 외 소켓 없음)이 그대로 성립한다.
   - 검증: `tests/security/test_network_invariant.py` 통과 — stderr sink는 소켓을 열지 않음.
8. sink가 예외를 던져도 스캔은 완료되고 결과·종료 코드가 정상이다.
   - 검증: 예외를 던지는 sink를 주입한 테스트에서 `ScanResult`가 정상 반환되고 종료 코드가
     격리 전과 동일함을 확인.

검증 방식(전반): 계약(이벤트·스냅샷·렌더러)은 단위테스트, 방출은 통합테스트(코어 API 직접
호출), 어댑터는 `capsys` 테스트, 마무리로 실제 Ollama 1회 수동 스모크로 라이브 라인·모델
로딩 표기를 육안 확인한다. [제안 후 승인]

## 4. 인터페이스 계약

### 4.1 코어 이벤트 계약 (내부 전용) [제안 후 승인]
- 위치: `corpbrain/core/_progress.py`. `corpbrain/core/__init__.py`에 재노출하지 않는다.
  패키지 내부(테스트·CLI 어댑터)는 `corpbrain.core._progress`를 직접 import한다.
- `ProgressEvent`: 타입이 있는 이벤트 합집합. 종류 — `run_started`, `model_loading`,
  `model_ready`, `file_started`, `file_stage`, `file_generated`, `file_skipped`,
  `run_finished`. 각 이벤트는 JSON 직렬화 가능한 `to_dict() -> dict` 를 갖는다.
  [사용자 결정: 종류 · 제안 후 승인: to_dict]
- `StatusSnapshot`: 현재 상태 값 객체. 필드 — `state`, `model`, `model_loading`,
  `current_file`, `stage`, `index`, `total`, `generated`, `skipped`(사유별 집계 포함),
  `elapsed`, `rate`, `eta`, `last_error`, `last_net_latency`. [사용자 결정]
- `reduce(snapshot, event) -> StatusSnapshot`: 순수 함수. 이벤트 하나를 접어 다음 스냅샷을
  만든다. [제안 후 승인]
- `render_status_line(snapshot) -> str`: 순수 함수. 문자열만 만들고 출력하지 않는다(§4.5 —
  코어는 로직, 어댑터는 입출력). [제안 후 승인]

### 4.2 방출 (코어 파이프라인) [제안 후 승인, 방출 지점은 사용자 결정 반영]
- `run_scan(config, *, on_event: Callable[[ProgressEvent], None] | None = None)`.
  `on_event`는 `ScanConfig`가 아닌 `run_scan`의 키워드 인자다(ScanConfig는 순수·직렬화
  가능 값으로 유지). 기본값 `None`이면 기존 동작과 동일하다.
- 방출 지점: `run_started`(모델·total 등 초기 상태) → `detect()` 전후 → 스캔 결과로 `total`
  확정 → 파일마다 `file_started`(index/total/bytes)·스테이지 경계마다
  `file_stage`(extract/summarize/render/write)·성공 시 `file_generated`·스킵 시
  `file_skipped` → 종료 시 `run_finished`.
- 모델 로딩 감지: 근사 표기. 첫 `summarize()` 호출 직전 `model_loading`(loading=true),
  반환 시 `model_ready`(이후 false). 추가 네트워크 호출은 없다. [사용자 결정]
- `last_net_latency`: `summarize()` 호출 구간의 wall-clock으로 측정한다. 게이트웨이는
  변경하지 않는다. [제안 후 승인]

### 4.3 CLI stderr 라이브 렌더러 (이번 슬라이스 유일 sink) [사용자 결정]
- `cli.py::main`이 sink를 만들어 `run_scan(config, on_event=sink)`로 넘긴다. sink는
  `reduce`로 스냅샷을 갱신하고 `render_status_line`으로 만든 문자열을 stderr에 쓴다.
- 표시: 단일 `\r` 라인 제자리 갱신, 이벤트 구동만(배경 티커 스레드 없음). 블로킹
  `summarize()` 동안에는 라인이 고정된다.
- 비-TTY(파이프·리다이렉트): `\r` 대신 이벤트별 개행으로 폴백한다.
- 의존성: 없음(순수 stderr — `rich` 미도입). stdout은 계속 비운다.
- 종료 요약: 기존 `report.build_detail_lines`/`build_summary_lines` 출력은 유지한다.
- ETA·처리율 산식: 단순 누적 평균 — `rate = done / elapsed_total`,
  `ETA = remaining / rate`. [사용자 결정]

## 5. 엣지 케이스와 실패 시나리오 [사용자 결정·제안 승인]
- sink 예외: 코어가 `on_event` 호출을 격리(삼킴)한다. 관측 실패가 실제 문서 처리를 깨지
  않는다(부모 스펙 §5 "부분 실패를 전체 실패로 위장하지 않는다"). [사용자 결정]
- 종료 코드·stdout 불변: 라이브 출력은 종료 코드 매핑을 바꾸지 않으며, stdout은 비운다.
  [사용자 결정]
- 보안 불변식: stderr sink는 소켓을 열지 않는다. localhost 외 연결 없음이 유지된다.
  [제안 후 승인]
- 하위 호환: `on_event=None`이면 이벤트를 방출하지 않고 기존 동작 그대로다. [제안 후 승인]
- 블로킹 구간 정지: 이벤트 구동 방식이므로 `summarize()` 반환 전까지 경과·라인이 고정된다.
  이는 의도된 동작이다. [사용자 결정]
- ETA 편향: 단순 누적 평균은 초반 빠른 스킵·모델 로딩 지연으로 낙관 편향될 수 있다. 알려진
  한계로 수용한다. [사용자 결정]

## 미결정 사항
없음
