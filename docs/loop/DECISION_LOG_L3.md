# DECISION LOG — Loop 3 (run-status 관측 계층)

대상 스펙: `static/docs/specs/features/corpbrain-run-status-observability.md`
브랜치: `feat/run-status-observability`

스펙에 이미 확정되지 않은 추가 구현 결정만 기록한다. CORE=아키텍처·보안·계약 형태, MINOR=네이밍·포맷·라인 문구.

CORE: 0
MINOR: 7

## 항목
- [MINOR] L3-001 이벤트는 단일 기반 클래스 `ProgressEvent`(frozen dataclass) + 종류별 서브클래스 합집합으로 구현. `to_dict()`는 `dataclasses.asdict` 기반, `kind`는 property.
- [MINOR] L3-002 각 이벤트에 `at: float`(monotonic) 타임스탬프 필드를 둬 `reduce`를 순수·결정적으로 유지한다(테스트에서 고정값 주입 가능). 코어는 emit 시 `time.monotonic()`을 스탬프한다.
- [MINOR] L3-003 `last_net_latency`는 `ModelReady`(첫 요약)와 `FileGenerated`(각 파일 요약)에 `latency` 필드로 실어 전달한다. 게이트웨이는 변경하지 않는다.
- [MINOR] L3-004 `RunFinished`는 카운트를 싣지 않고 `state=done`만 전환한다. 라이브 스냅샷의 generated/skipped는 루프 이벤트 누적값이며, 스캔 단계의 미지원 스킵은 최종 요약(`report.build_summary_lines`)에만 반영된다.
- [MINOR] L3-005 CLI sink의 비-TTY 판정은 `stream.isatty()`, TTY 라인 클리어는 ANSI `\r\033[K`, 비-TTY는 이벤트별 개행.
- [MINOR] L3-006 진행 라인의 모델 로딩 표기는 `loading=true`/`loading=false` 토큰으로 렌더한다(사용자 확인 프리뷰와 일치).
- [MINOR] L3-007 스펙 §4.2가 `run_scan` 시그니처를 `(config, *, on_event=None)`으로 확정하므로, 그 시그니처를 단언하던 기존 인터페이스 결합 테스트(`tests/test_cli.py::fake_run_scan`, `tests/test_core_api_smoke.py`)를 최소 수정해 새 시그니처에 맞춘다(DoD 6 "전체 스위트 통과"를 위해 불가피). 활성 범위의 인터페이스 소비자로 간주.

STOP REASON: DONE — 스펙 완료의 정의 8개 항목 충족, 전체 스위트 통과, ruff clean.
