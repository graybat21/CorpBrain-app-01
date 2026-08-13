# CorpBrain v0.3 — 의사결정 체크포인트 (조기 종료 카운터)

이 문서는 v0.3 구현 루프의 **조기 종료 판정 단일 근거**다. 기존 문서(v0.3 스펙·`GRILL_LEDGER-v0.3.md`·`docs/ROADMAP.md`)가 명확히 정해두지 **않은** 신규 결정만 여기에 누적한다. 이미 정해진 사항은 적지 않는다(오카운트 방지).

- 종료 임계: `CORE` ≥ 3 → STOP REASON: CORE_BUDGET · `MINOR` ≥ 10 → STOP REASON: MINOR_BUDGET
- 분류: CORE = 아키텍처·보안·외부 의존·데이터 모델·공개 API/CLI 계약·핵심 UX 계약 / MINOR = 네이밍·디렉터리·로그 문구·테스트 픽스처·내부 헬퍼 등 국소 결정
- 기록 형식(한 줄): `- [CORE|MINOR] <결정> | 근거 | 관련 파일` — 기록 직후 해당 카운터 +1

CORE: 0
MINOR: 2

## 결정 로그
- [MINOR] 자원 게이트(GPU·토큰)는 `--max` 상한 절단보다 먼저 평가한다 — 프리플라이트가 비절단 발견 집합으로 판정하므로, GPU 미탐지+상한초과 동시 상황에서 GPU(exit 1)가 상한(exit 3)보다 먼저 표면화된다 | 스펙 §4.2 프리플라이트에 max_files 위치 미명시 | corpbrain/core/pipeline.py
- [MINOR] `--max-file-size`는 정수 MB(십진 ×1,000,000) 입력, 코어는 바이트 저장 | 스펙 §4.1 "MB" 표기, int/float·진법 미명시 → 최소 1MB 정수 채택 | corpbrain/cli.py

## STOP
STOP REASON: ALL_DONE
<!-- v0.3 스펙 완료의 정의 9개 항목 충족 + `uv run ruff check .`·`uv run pytest`(273 passed) exit 0. -->
<!-- 누적 결정: CORE 0 / MINOR 2 (임계 미도달). -->

