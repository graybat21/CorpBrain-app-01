# 실행 플랜(얇음): CorpBrain v0.2 — 입력 확장(PDF)·pre-scan 계량

- 대상 스펙(정본): `static/docs/specs/features/corpbrain-v0.2-prescan-and-pdf.md` (상태: 확정)
- 결정 근거: `docs/grill/GRILL_LEDGER.md` (T1~T8 전부 RESOLVED, 미결정 없음)
- 프로젝트 규칙: `CLAUDE.md` (스펙 주도 · 코어/CLI 이음새 · 단일 게이트웨이 · 코어 no-I/O 불변식)

이 문서는 **작업 단위·순서·파일 경계만** 정의한다. "무엇을·왜"의 상세는 스펙 §3(완료의 정의)·§4(계약)에
이미 있으므로 여기서 재작성하지 않는다. goal 프롬프트는 이 목록을 실행 대상으로 가리킨다.

## 작업 단위 (6개)

각 단위: `산출` / `파일 경계`(다른 단위와 겹치지 않게) / `스펙 참조` / `완료의 정의(DoD) 참조`.

### U1 — PDF 입력 확장  ·  트랙 P
- 산출: `.pdf` 텍스트 레이어 추출기. `_extract_pdf`가 pypdf 예외·손상·파싱 실패와 암호화
  (`reader.is_encrypted`)를 `ExtractionError`로 감싸 raise(→ `extraction_failed`, 암호화는
  `detail="암호화된 PDF"`). 텍스트 없음/공백뿐이면 빈 문자열 → 기존 `text.strip()` 검사로
  `empty_document`. `SkipReason` enum·리포트 라벨은 불변.
- 파일 경계: `corpbrain/core/extract.py`, `corpbrain/core/config.py`(`SUPPORTED_EXTENSIONS`에 `.pdf`
  추가 — **한 줄, 공유 파일**), `pyproject.toml`(런타임 의존성 `pypdf` 추가 — **공유 파일**),
  `tests/unit/test_extract.py`.
- 스펙: §4.1, §5.  ·  DoD: 1, 2.

### U2 — pre-scan 값 타입  ·  트랙 M
- 산출: `models.py`에 순수 값타입 3종 추가 — `ScanPlan{entries, file_count, total_est_tokens,
  est_seconds, hardware}`, `PlanEntry{path, ext, size_bytes, est_tokens, importance}`,
  `HardwareInfo{gpu: bool, label: str}`.
- 파일 경계: `corpbrain/core/models.py`.
- 스펙: §4.2.  ·  DoD: 4.

### U3 — pre-scan 코어 `plan_scan`  ·  트랙 M  ·  depends: U2, U1의 config 한 줄
- 산출: `plan_scan(config: ScanConfig) -> ScanPlan` 순수 함수. **I/O 경계**: `os.stat`(크기·mtime)까지만,
  파일 콘텐츠 open/read·소켓·영속상태 읽기 금지. 파일 목록은 `scanner.scan_folder(max_files=None)` 재사용.
  중요도(가중 합산 휴리스틱, 내용 무읽기, clamp 0~100), `est_tokens`(size_bytes·확장자만),
  `est_seconds`(정적 rate GPU=50/CPU=10), HW 감지(`nvidia-smi` subprocess만 — 소켓·Ollama 미질의).
  상수·공식은 스펙 §4.2 그대로.
- 파일 경계: 신규 코어 모듈 `corpbrain/core/plan.py`(HW 감지 헬퍼 포함), 신규 테스트 파일.
- 스펙: §4.2, §5.  ·  DoD: 3, 4, 5.

### U4 — 순수 리포트 렌더러  ·  트랙 M  ·  depends: U2, U3
- 산출: `ScanPlan` → 사람이 읽는 리포트 **문자열**을 만드는 순수 함수(출력은 어댑터가 담당). plan 리포트=
  중요도 내림차순 TOP 20행 + "…외 M건" + 합계(파일수/총토큰/예상초) + 감지 HW + `--max` 초과 경고.
  scan 시작 배너=예상 파일수·예상시간 + 중요도 TOP 3.
- 파일 경계: `corpbrain/core/report.py`(기존 `build_*_lines` 옆에 plan 렌더러 함수 추가), 렌더러 단위테스트.
- 스펙: §4.3.  ·  DoD: 6, 7.

### U5 — CLI 배선  ·  depends: U3, U4
- 산출: 얇은 어댑터만. 신규 `corpbrain plan <folder>`(리포트를 **stdout**), `scan --dry-run`(동일 리포트만,
  위키 0개), 일반 `scan` 시작 시 배너를 **stderr**로(스택 stdout은 계속 공백). `plan`은 기존 `ScanConfig`
  재사용하되 `folder`·`--max`·`--max-chars`만 채우고 `model`·`ollama_url`·`force`는 미사용.
- 파일 경계: `corpbrain/cli.py`, 어댑터 테스트 `tests/test_cli.py` / `tests/test_cli_report.py`.
- 스펙: §4.3.  ·  DoD: 6, 7.

### U6 — 하위호환·green (조인)  ·  depends: U1~U5
- 산출: 기존 스캔·run-status 동작 불변(`on_event` 유지) 확인. 통합테스트(텍스트 PDF 픽스처 → 위키 생성,
  게이트웨이 mock), `plan`/`--dry-run` 통합테스트(위키 0, 종료 0), 소켓 워처로 plan 실행 중 localhost
  포함 소켓 0·`gateway.requested_urls()` 빈 상태 확인. `ruff check .`·`pytest` 전부 green.
- 파일 경계: `tests/integration/**`, `tests/security/test_network_invariant.py`(또는 신규 plan 소켓 테스트).
- 스펙: §3 전반.  ·  DoD: 1, 2, 3, 7, 8.

## 실행 순서 (웨이브)

- **W1**: U2(값타입) + U1의 공유 선행(`SUPPORTED_EXTENSIONS += .pdf`, `pyproject.toml` `pypdf`). 기반부터.
- **W2 (병렬 가능)**: U1 본체(`_extract_pdf`)  ∥  U3(`plan_scan`). 두 트랙은 파일 경계가 겹치지 않는다
  (U1=`extract.py`, U3=`plan.py`). 공유 파일(`config.py`/`pyproject.toml`)은 W1에서 이미 처리됨.
- **W3**: U4(리포트 렌더러).
- **W4**: U5(CLI 배선).
- **W5**: U6(하위호환·통합·소켓 워처·green) — 조인·마감.

## 불변식 (모든 단위 공통)
- 코어=비즈니스 로직, CLI=얇은 어댑터. 리포트 문자열은 코어 순수 렌더러가 만들고 출력만 어댑터가 한다.
- 모든 외부 네트워크 호출은 단일 게이트웨이 경유. `plan`은 소켓을 열지 않는다(localhost 포함 0).
- 스펙 §2 비목표를 구현하지 않는다(xls/ppt, OCR·암호화 PDF 처리, 자원 게이팅, 실측 rate 보정, 순서변경·필터).
- 상수·공식은 스펙 §4.2 값을 그대로 쓴다("근사" 표기 유지). 임의 변경 금지.
