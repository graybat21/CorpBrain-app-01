# CorpBrain MVP 첫 슬라이스 — 의사결정 로그 (조기 종료 체크포인트)

근거 목표: `docs/goals/corpbrain-mvp-first-slice-loop.md` §2.4

## 카운터
CORE: 0
MINOR: 1

<!-- 위 두 줄은 오케스트레이터만 갱신한다. 권위 있는 값은 아래 엔트리 줄 수:
     grep -c '^- \[CORE\]' docs/loop/DECISION_LOG.md
     grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG.md
     조기 종료: CORE >= 3 또는 MINOR >= 10 -->

## 엔트리 (append only — 단일 `cat >>` 명령으로만 추가, 기존 줄 편집 금지)
- [MINOR] D-001 | FR-002 | agent:orchestrator | 2026-08-12T21:40:00+09:00 | 코어 공개 API 표면을 `run_scan(config: ScanConfig) -> ScanResult`로 두고 코어를 config/models/errors/pipeline + 후속 모듈(gateway·scanner·extract/·ollama·summarize·render·output·report)로 분할 | 근거: FR-002가 "코어 공개 진입점·모듈 경계 정의"를 지시하되 이름·시그니처·파일 분할은 미지정. 스펙 §4.1 기본값을 ScanConfig에 그대로 싣고, W3 이후 병렬 워커의 파일 충돌을 막기 위해 모듈 배치를 먼저 확정함.
