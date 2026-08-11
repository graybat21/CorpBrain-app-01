# CorpBrain MVP 첫 슬라이스 — 의사결정 로그 (조기 종료 체크포인트)

근거 목표: `docs/goals/corpbrain-mvp-first-slice-loop.md` §2.4

## 카운터
CORE: 0
MINOR: 10

<!-- 위 두 줄은 오케스트레이터만 갱신한다. 권위 있는 값은 아래 엔트리 줄 수:
     grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md
     grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md
     조기 종료: CORE >= 3 또는 MINOR >= 10 -->

## 엔트리 (append only — 단일 `cat >>` 명령으로만 추가, 기존 줄 편집 금지)
- [MINOR] D-001 | FR-002 | agent:orchestrator | 2026-08-12T21:40:00+09:00 | 코어 공개 API 표면을 `run_scan(config: ScanConfig) -> ScanResult`로 두고 코어를 config/models/errors/pipeline + 후속 모듈(gateway·scanner·extract/·ollama·summarize·render·output·report)로 분할 | 근거: FR-002가 "코어 공개 진입점·모듈 경계 정의"를 지시하되 이름·시그니처·파일 분할은 미지정. 스펙 §4.1 기본값을 ScanConfig에 그대로 싣고, W3 이후 병렬 워커의 파일 충돌을 막기 위해 모듈 배치를 먼저 확정함.
- [MINOR] D-002 | FR-006/FR-007 | agent:orchestrator | 2026-08-12T21:55:00+09:00 | 추출 실패 신호를 "빈 문자열" 대신 예외 `ExtractionError`(CorpBrainError 상속)로 통일하고, 빈 문자열은 오직 "내용 없음"만 의미하게 분리. PermissionError는 `__cause__`에 보존해 호출자가 permission_denied와 extraction_failed를 구분 | 근거: FR-006 명세가 "빈 문자열/예외" 중 선택을 위임(23행). 두 신호를 겹치면 FR-008이 빈 문서와 추출 실패를 구분할 수 없어 스펙 §5의 스킵 사유 분류가 무너진다.
- [MINOR] D-003 | FR-008 | agent:orchestrator | 2026-08-12T22:05:00+09:00 | 길이 제한·스킵 판정 지점을 `core/extract.py`의 `prepare_summary_input(path, max_chars) -> PreparedDocument(text|skipped)` 단일 함수로 확정(파이프라인 경계가 아니라 추출 모듈에 둠) | 근거: FR-008이 "extract.py 또는 파이프라인 경계" 중 선택을 위임(19행). 추출 실패 예외를 잡는 지점과 절단·빈문서 판정을 한곳에 모아야 FR-015 파이프라인이 분기 없이 스킵을 수집할 수 있다.
- [MINOR] D-003 | FR-014 | agent:worker-cli | 2026-08-12T04:27:13+09:00 | 환경변수 이름을 `corpbrain.cli.MODEL_ENV_VAR` 상수로 노출하고, 값이 빈 문자열·공백뿐이면 미설정으로 간주해 `DEFAULT_MODEL`로 폴백 | 근거: 스펙 §4.1은 `CORPBRAIN_MODEL` 사용만 정하고 빈 값 처리를 미지정. 빈 값을 모델명으로 넘기면 Ollama 요청이 무의미하게 실패하므로 미설정과 동일 취급이 안전하고, 상수화로 테스트·후속 어댑터가 문자열을 재타이핑하지 않는다.
- [MINOR] D-004 | FR-014 | agent:worker-cli | 2026-08-12T04:27:13+09:00 | argparse dest를 `ScanConfig` 필드명에 1:1로 맞춤(`--out`→`out_dir`, `--max`→`max_files`) | 근거: 스펙 §4.1은 플래그 철자만 규정하고 내부 dest는 미지정. dest를 필드명과 일치시키면 `build_config`가 단순 매핑으로 남아 CLI에 변환 로직이 쌓이지 않는다(§4.5 얇은 어댑터).
- [MINOR] D-005 | FR-014 | agent:worker-cli | 2026-08-12T04:27:13+09:00 | 서브커맨드를 `required=True`로 두고, 사용법 오류(서브커맨드 누락·미지원 플래그)는 `main` 반환값이 아니라 argparse 기본 동작(SystemExit 2)으로 처리 | 근거: 스펙 §3-5는 선행조건 실패의 비-0 종료만 규정하고 사용법 오류 코드는 미지정. FR-016이 종료 코드 매핑을 담당하므로 이번 슬라이스에서는 argparse 표준 동작을 그대로 두어 FR-016이 덮어쓸 여지를 남긴다.
- [MINOR] D-006 | FR-003 | agent:worker-gateway | 2026-08-12T04:28:00+09:00 | 관문 감시 훅을 모듈 레벨 URL 기록 + `requested_urls()`/`reset_requested_urls()` 조회·초기화 함수로 노출하고, 소켓을 열기 전에 기록해 실패한 호출도 남긴다. `GatewayError`에는 대상 URL을 담는 `.url` 속성을 둔다 | 근거: FR-003이 "테스트에서 관찰 가능한 단일 진입점 노출"만 지시하고 형태는 미지정. 완료의 정의 6번은 '연결 시도' 자체가 localhost 외로 나가지 않음을 봐야 하므로 성공 응답이 아니라 시도 시점을 기록하는 편이 검증에 정확하다.
- [MINOR] D-007 | FR-003 | agent:worker-gateway | 2026-08-12T04:28:00+09:00 | AC 시나리오 2(관문 우회 방지)를 `tests/test_gateway.py`의 AST 정적 검사 테스트로 강제한다. `corpbrain` 패키지 내 gateway.py 외 모든 모듈에서 socket·ssl·http·urllib.request·urllib.error·requests·httpx·urllib3·aiohttp 계열 import를 금지하고, 순수 문자열 처리인 `urllib.parse`는 허용 | 근거: FR-003 AC 시나리오 2가 "정적 분석으로 확인"을 요구하나 수단은 미지정. 후속 FR(특히 FR-009 ollama)이 관문을 우회하면 회귀가 조용히 통과하므로 테스트로 고정했고, `urljoin` 같은 비-네트워크 유틸까지 막으면 과도해 예외로 뒀다.
- [MINOR] D-006 | FR-004 | agent:worker-scanner | 2026-08-12T04:28:00+09:00 | 재귀 순회를 `os.walk` + 디렉터리·파일명 이름 오름차순 정렬로 고정해 실행마다 순서가 같게 함 | 근거: 스펙 §4.2는 "재귀 순회"만 정하고 순서를 정하지 않는데, FR-005의 상한(50) 컷 지점과 스킵 리포트 순서가 실행마다 달라지면 재현 불가·테스트 불안정이 되므로 결정적 순서를 채택.
- [MINOR] D-007 | FR-004 | agent:worker-scanner | 2026-08-12T04:28:10+09:00 | 절대경로화를 `root.resolve()`로 하고 반환 경로는 모두 그 아래에서 조립(= 심볼릭 링크까지 정규화된 절대경로) | 근거: 오케스트레이터가 "절대경로 반환"만 고정했고 `absolute()`/`resolve()` 선택은 미지정. 스펙 §4.4 front-matter `source_path`가 정본 절대경로를 요구하고 상대 root 인자도 허용해야 하므로 정규화를 선택. 대신 FR-012 미러링은 `path.relative_to(root.resolve())`로 계산해야 한다.
