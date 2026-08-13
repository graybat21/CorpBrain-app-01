# 스펙: CorpBrain v0.2 — 입력 확장(PDF)·pre-scan 계량

- 상태: 확정
- 최종 갱신: 2026-08-13
- 로드맵 맥락: docs/ROADMAP.md (v0.2 "입력·계량")

## 1. 목표
본격 스캔 전에 폴더를 값싸게 훑어 사용자가 "무엇이 중요하고 얼마나 걸릴지"를 먼저 보게 하고,
입력 포맷을 PDF까지 넓힌다. 두 축: (a) `.pdf`(텍스트 레이어) 추출 추가, (b) LLM·네트워크 없이
즉시 도는 pre-scan 계량 — 파일별 중요도 점수(트리·이름·확장자 휴리스틱), 크기 기반 예상 토큰,
감지 하드웨어 기준 예상 소요시간. 기본 로컬·단일 게이트웨이·코어 no-I/O 불변식을 유지한다.
[사용자 결정]

## 2. 비목표
- xls(`openpyxl`)/ppt(`python-pptx`) 추출 — 후속 버전. [사용자 결정]
- 스캔 이미지 PDF·OCR·암호화 PDF. [사용자 결정]
- 전체 자원 게이팅(임계 초과 시 기능 강제 제한)은 v0.3 — v0.2는 **추정 표시만** 한다. [사용자 결정]
- 클라우드/외부 LLM. [사용자 결정]
- 중요도 점수를 활용한 처리 순서 변경·필터링 — v0.2는 **표시만**. [제안 후 승인]
- 실측 rate 기반 예상시간 보정(과거 실행의 tokens/sec 영속화·재사용) — v0.3. v0.2는 정적 기본값만 쓴다. [사용자 결정]

## 3. 완료의 정의
1. 텍스트 레이어 `.pdf`가 스캔 대상에 포함되어 `<원본이름.pdf>.md`가 생성된다.
   - 검증: 통합테스트 — 텍스트 PDF 픽스처로 위키 생성 확인(게이트웨이 mock).
2. 텍스트가 없는/암호화/추출 실패 PDF는 산출물 없이 스킵+사유 로그.
   - 검증: 통합/단위테스트 — 해당 픽스처 → `empty_document` 또는 `extraction_failed` 스킵.
3. `plan_scan(config)`가 LLM·네트워크 호출 0으로 `ScanPlan`을 반환한다.
   - 검증: 보안 소켓 워처로 plan 실행 중 localhost 포함 소켓 연결 0, `gateway.requested_urls()` 빈 상태.
4. `ScanPlan`은 파일별 {경로·확장자·크기·예상토큰·중요도점수(0~100)}와 합계(파일수·총예상토큰·
   예상초)·감지 하드웨어를 담는다.
   - 검증: 단위테스트 — 필드·타입·점수 범위, 동일 입력 결정성.
5. 중요도 점수는 트리 깊이·폴더명·파일명·확장자만 사용하고 파일 내용을 읽지 않는다.
   - 검증: 단위테스트 — 내용을 바꿔도 경로·이름 동일이면 점수 동일; 계산 경로에 파일 open 없음.
6. `corpbrain plan <folder>`는 리포트를 stdout으로 내고, `scan`은 시작 시 요약 배너를 stderr로 낸다.
   - 검증: 어댑터 테스트(capsys) — plan은 stdout에 랭킹·예상치, scan은 stderr 배너 + stdout 공백.
7. `scan --dry-run`은 문서 처리 없이 plan과 동일 리포트만 낸다(위키 0개 생성).
   - 검증: 통합테스트 — `--dry-run` 시 out 디렉터리에 `.md` 0개, 종료 코드 0.
8. 하위 호환·green: 기존 스캔·run-status 동작 불변(`on_event` 유지), `ruff check .`·`pytest` 통과.
   - 검증: 전체 테스트 스위트 통과.

## 4. 인터페이스 계약
### 4.1 포맷 확장
- `extract.py`(또는 `extract/` 하위)에 `.pdf` 추출기를 기존 확장자별 패턴대로 추가. 백엔드 `pypdf`.
  텍스트 레이어만 연결하고 이미지/OCR은 하지 않는다. `SUPPORTED_EXTENSIONS`에 `.pdf` 추가. [사용자 결정]
- PDF 스킵 사유 매핑 — 기존 `prepare_summary_input`의 예외→`SkipReason` 기계장치를 그대로 재사용한다.
  [사용자 결정 · 2026-08-13 확정]
  - `_extract_pdf`는 pypdf 예외(손상·파싱 실패)와 **암호화**(`reader.is_encrypted`)를 `ExtractionError`로
    감싸 raise → `extraction_failed`(암호화는 `detail="암호화된 PDF"`).
  - 텍스트 레이어가 없거나 공백뿐이면(스캔 이미지 PDF 등) 추출 결과가 빈 문자열 → 기존 `text.strip()`
    검사로 `empty_document`.
  - `SkipReason` enum·리포트 라벨·완료의 정의 2(두 사유) 계약은 변경하지 않는다.
- 의존성: `pyproject.toml`에 `pypdf` 추가(런타임). [제안 후 승인]

### 4.2 코어 pre-scan
- `plan_scan(config: ScanConfig) -> ScanPlan` — 순수 함수(부수효과 없음). **I/O 경계**: 파일
  메타데이터 조회(`os.stat` — 크기·mtime)까지만 허용하고, **파일 콘텐츠 open·read·네트워크 소켓·
  영속 상태(캐시·rate 파일) 읽기는 하지 않는다.** 하드웨어 감지도 Ollama에 질의하지 않는다
  (localhost 소켓도 0 — 완료의 정의 3). 파일 목록은 `scanner.scan_folder` 재사용.
  [사용자 결정 · 2026-08-13 I/O 경계 확정]
- `ScanPlan`(순수 값): `entries: list[PlanEntry]`, `file_count`, `total_est_tokens`,
  `est_seconds`, `hardware: HardwareInfo`. `PlanEntry`: `path`, `ext`, `size_bytes`,
  `est_tokens`, `importance`. `HardwareInfo`: `gpu: bool`, `label`. 이 세 값 타입은 `models.py`에
  추가한다. `plan`은 별도 설정을 두지 않고 기존 `ScanConfig`를 재사용하며(위 시그니처 그대로), CLI
  `plan`은 `folder`·`--max`·`--max-chars`만 채우고 `model`·`ollama_url`·`force`는 plan에 무의미하므로
  사용하지 않는다. [제안 후 승인 · 2026-08-13 확정]
- 중요도(2a): **가중 합산 휴리스틱**으로 0~100 결정적 점수. 파일 **내용을 열지 않고**
  경로 문자열(루트 기준 상대경로의 폴더명 + 파일명·확장자를 소문자화)과 트리 깊이만 사용한다.
  LLM 없음. 아래 상수로 고정한다 — 동일 경로·이름이면 내용이 달라도 동일 점수(완료의 정의 5).
  [사용자 결정 · 2026-08-13 확정]
  - `base_ext`: `.pdf`/`.docx`=40, `.md`=30, `.txt`=25 (plan 대상은 지원 4종뿐).
  - `depth_adj = max(-20, 15 - 5 * depth)`, `depth = len(rel_path.parts) - 1` (루트 직속=0).
  - `signal_bonus = min(30, 8 * 매칭된 서로 다른 신호 키워드 수)`. 신호(부분일치, 소문자):
    계약, 보고서, report, spec, 제안, 계획, 최종, final, 정책.
  - `noise_penalty = min(30, 10 * 매칭된 서로 다른 잡음 키워드 수)`. 잡음(부분일치, 소문자):
    temp, tmp, backup, 사본, copy, old, 임시, draft, archive, `~$`.
  - `importance = clamp(0, 100, round(base_ext + depth_adj + signal_bonus - noise_penalty))`.
- 예상 토큰(5): 파일 **내용을 읽지 않고** `size_bytes`(stat)와 확장자만으로 결정적 근사한다.
  [제안 후 승인 · 2026-08-13 확정]
  - `chars_est = min(max_chars, round(size_bytes * cpb[ext]))`. `cpb`: `.txt`/`.md`=0.5,
    `.docx`=0.06, `.pdf`=0.12 (한글 편중 UTF-8·zip 압축/마크업 오버헤드 가정).
  - `tokens_est = round(chars_est / 2.5)` (한/영 혼합 근사 비율). 상수는 "근사"라 튜닝 가능.
  - `total_est_tokens = Σ tokens_est`.
- 예상 시간(1): `total_est_tokens ÷ 처리율`. 처리율은 감지 하드웨어(GPU/CPU) 기준 **정적 기본값만**
  사용한다(값은 T3/§4.2에서 확정). 실측 rate 기반 보정은 v0.2 비목표(§2)이며 v0.3으로 미룬다.
  값은 "근사"로 표기한다. [사용자 결정 · 2026-08-13 확정]
- 하드웨어 감지: **`nvidia-smi` subprocess** 실행 성공 여부만으로 판정한다(로컬 프로세스 — 소켓·
  네트워크 0, Ollama 미질의; 짧은 타임아웃으로 호출). 성공 시 `HardwareInfo(gpu=True,
  label="GPU: <nvidia-smi가 보고한 이름 1줄>")`, 실패·부재·타임아웃 시 `HardwareInfo(gpu=False,
  label="CPU")`. NVIDIA 외 GPU(AMD/Apple)는 CPU로 근사한다. 새 런타임 의존성 추가 없음.
  [사용자 결정 · 2026-08-13 확정]
- 처리율 정적 기본값(근사 — 튜닝 가능한 상수): GPU=50 tok/s, CPU=10 tok/s.
  `est_seconds = round(total_est_tokens ÷ (gpu ? 50 : 10))`. [제안 후 승인 · 2026-08-13]

### 4.3 CLI
- 신규 `corpbrain plan <folder>` 서브커맨드 — `plan_scan` 결과를 사람이 읽는 리포트로 **stdout**에
  출력(중요도 랭킹 + 파일수/총토큰/예상시간 + 감지 하드웨어). 리포트는 중요도 **내림차순 TOP 20행**
  + "…외 M건" + 합계로 절단하고, 발견 수가 `--max` 초과 시 경고를 포함한다(§5). 표시 상수(20)는
  튜닝 가능. [제안 후 승인 · 2026-08-13 확정]
- `corpbrain scan --dry-run` — `plan`과 동일 리포트만 내고 처리하지 않는다. [사용자 결정]
- `corpbrain scan`(일반) — 시작 시 요약 배너(예상 파일수·예상시간·중요도 **TOP 3** 파일명)를
  **stderr**로 내고 기존 처리를 진행. stdout은 계속 빈다. [사용자 결정 · 2026-08-13 TOP 3 확정]
- 리포트 문자열은 코어의 순수 렌더러가 만들고 출력만 어댑터가 한다(§4.5 이음새). [제안 후 승인]

## 5. 엣지 케이스와 실패 시나리오
- 텍스트 없는/암호화 PDF: 스킵+로그(중단 없음) — 암호화·손상·파싱 실패=`extraction_failed`,
  빈 텍스트(스캔 이미지 등)=`empty_document`(§4.1 매핑). [사용자 결정]
- 빈 폴더/접근 불가: `plan`도 `scan`과 동일하게 선행 조건 실패는 비-0, 부분 실패는 0. [제안 후 승인]
- 예상치 부정확: 로컬 LLM 편차로 예상 시간은 낙관/비관 편향 가능 — "근사"로 표기해 수용. [사용자 결정]
- 큰 폴더: `plan`은 내용을 읽지 않아 파일 수에 선형이며 즉시 반환한다. `plan`은
  `scan_folder(max_files=None)`로 **전 파일을 계산·표시**하고, `--max`는 처리 중단이 아니라
  "이 폴더로 `scan`하면 상한(N) 초과로 중단됨"을 알리는 **경고 신호**로만 쓴다(plan은 처리하지
  않으므로 중단 개념이 없다; 표시 행 수 절단은 §4.3 리포트 형식에서 다룬다).
  [제안 후 승인 · 2026-08-13 확정]
- 단일 게이트웨이·기본 로컬 불변식: `plan`은 소켓을 열지 않는다(완료의 정의 3). [사용자 결정]

## 미결정 사항
없음
