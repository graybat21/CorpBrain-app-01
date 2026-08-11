# 구현 결정 기록 (승인 완료)

- 최종 갱신: 2026-08-12
- 근거 스펙: `static/docs/specs/features/corpbrain-mvp-local-scan-to-wiki.md`
- 원본 로그: `docs/loop/DECISION_LOG.md` (에이전틱 루프가 append-only로 기록한 원문)

이 문서는 첫 슬라이스 구현 중 스펙·이슈 명세에 정해져 있지 않아 구현자가 정했고, 사용자가
**승인한** 결정을 정본화한 것이다. 여기 적힌 항목은 이후 루프에서 "미결정"으로 다시 세지 않는다.
제품 동작 계약(파일명 규칙 등)은 스펙 본문에 직접 반영했고, 이 문서에는 구현 계층의 결정만 남긴다.

## 상태 요약

| 구분 | 건수 |
|---|---|
| 승인된 구현 결정 | 10 |
| 미결정 (다음 슬라이스 착수 전 확정 필요) | 3 |

## 승인된 결정

### 코어 경계

1. **코어 공개 표면** — `run_scan(config: ScanConfig) -> ScanResult` 단일 진입점. 코어는
   `config` / `models` / `errors` / `pipeline` + 기능 모듈(`gateway`·`scanner`·`extract`·
   `ollama`·`summarize`·`render`·`output`·`report`)로 분할한다.
   *근거:* 스펙 §4.5가 "CLI 없이 코어만으로 end-to-end 실행"을 요구하고, FR-002가 진입점 정의를
   지시하되 이름·시그니처는 미지정. 모듈 배치를 먼저 고정해 병렬 구현 시 파일 충돌을 없앴다.

2. **요약 결과 타입 이름은 `SummaryResult`** (`corpbrain/core/models.py`).
   *근거:* FR-010·FR-011 명세가 이 이름을 사용하므로 문서 표기에 맞춘다.

### 추출·스킵 판정

3. **추출 실패 신호는 예외 `ExtractionError`**, 빈 문자열은 오직 "내용 없음"만 의미한다.
   `PermissionError`는 `__cause__`에 보존해 호출자가 `permission_denied`와
   `extraction_failed`를 구분한다.
   *근거:* FR-006이 "빈 문자열/예외" 중 선택을 위임. 두 신호를 겹치면 스펙 §5의 스킵 사유
   분류가 무너진다.

4. **길이 제한·스킵 판정 지점은 `core/extract.py`의
   `prepare_summary_input(path, max_chars) -> PreparedDocument(text | skipped)`**.
   *근거:* FR-008이 "extract.py 또는 파이프라인 경계" 중 선택을 위임. 절단·빈문서·실패 판정을
   한곳에 모아 파이프라인이 분기 없이 스킵을 수집하게 한다.

### 스캔

5. **재귀 순회는 `os.walk` + 디렉터리·파일명 오름차순 정렬로 결정적 순서 고정.**
   *근거:* 스펙 §4.2는 순서를 정하지 않지만, 순서가 흔들리면 상한(50) 컷 지점과 스킵 리포트가
   실행마다 달라져 재현·테스트가 불가능하다.

6. **경로는 `root.resolve()` 기준 정규화된 절대경로로 반환한다.**
   *근거:* front-matter `source_path`가 정본 절대경로를 요구하고, 상대경로·심볼릭 링크 루트도
   허용해야 한다. **FR-012 미러링은 반드시 `path.relative_to(root.resolve())`로 계산할 것.**

### 외부호출 관문

7. **관문 감시 훅** — 모듈 레벨 URL 기록 + `requested_urls()` / `reset_requested_urls()`,
   소켓을 열기 **전에** 기록해 실패한 시도까지 남긴다. `GatewayError`는 대상 URL(`.url`)을 담는다.
   *근거:* 완료의 정의 6번은 "연결 시도"가 localhost 밖으로 나가지 않음을 봐야 하므로, 성공 응답이
   아니라 시도 시점을 기록하는 편이 검증에 정확하다.

8. **관문 우회 금지를 AST 정적 검사 테스트로 강제한다** (`tests/test_gateway.py`).
   `gateway.py` 외 `corpbrain` 전 모듈에서 socket·ssl·http·urllib.request/error·requests·
   httpx·urllib3·aiohttp import 금지. 순수 문자열 유틸인 `urllib.parse`는 허용.
   *근거:* FR-003 AC 시나리오 2가 정적 확인을 요구하나 수단은 미지정. **FR-009(Ollama 클라이언트)는
   반드시 `gateway.request_json()` 경유로 구현해야 이 테스트를 통과한다.**

### CLI 어댑터

9. **`CORPBRAIN_MODEL`이 빈 값·공백이면 미설정으로 취급**해 기본 모델로 폴백하고, 환경변수 이름은
   `corpbrain.cli.MODEL_ENV_VAR` 상수로 노출한다.
   *근거:* 스펙 §4.1은 변수 사용만 정하고 빈 값 처리를 미지정. 빈 모델명을 넘기면 요청이 무의미하게
   실패한다.

10. **argparse `dest`를 `ScanConfig` 필드명과 1:1로 맞춘다** (`--out`→`out_dir`, `--max`→`max_files`).
    *근거:* 스펙은 플래그 철자만 규정. dest를 필드명에 맞추면 `build_config`가 단순 매핑으로 남아
    CLI가 얇은 어댑터로 유지된다 (스펙 §4.5).

## 미결정 — 다음 착수 전 확정 필요

1. **사용법 오류의 종료 코드.** 현재는 argparse 기본 동작(`SystemExit 2`)에 위임했다. 스펙 §3-5는
   선행 조건 실패의 비-0만 규정하므로, FR-016(종료 리포트·종료 코드) 착수 시 성공 0 / 선행조건 실패 /
   사용법 오류를 표로 확정할 것.
2. **진행 로그를 내는 계층.** 스펙 §4.1은 "진행 로그는 stderr"만 정한다. 현재 코어(스캐너·추출기)는
   로깅하지 않고 결과 구조만 반환하며 출력은 CLI 몫으로 남겨 두었다. 코어에 `logging` 규약을
   도입할지 여부를 FR-016 착수 전 결정할 것.
3. **`gateway`·`scanner` 심볼의 `corpbrain.core` 재수출 여부.** 현재는 서브모듈 직접 import로만
   접근한다.
