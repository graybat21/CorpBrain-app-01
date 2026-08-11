# CorpBrain MVP 첫 슬라이스 — 의사결정 로그 · 루프 2 (조기 종료 체크포인트)

- 시작: 2026-08-12, W4/FR-005부터 재개
- 이전 루프 이력: `docs/loop/DECISION_LOG.md` (MINOR 10건 + 사용자 확정 U-001~U-003)
- 확정 사항(카운트 제외): `docs/decisions/implementation-decisions.md` 10건, 스펙 §4.4 출력 파일명 규칙

## 카운터
CORE: 0
MINOR: 0

<!-- 위 두 줄은 오케스트레이터만 갱신한다. 권위 있는 값은 아래 엔트리 줄 수:
     grep -c '^- \[CORE\]' docs/loop/DECISION_LOG_L2.md
     grep -c '^- \[MINOR\]' docs/loop/DECISION_LOG_L2.md
     조기 종료: CORE >= 3 또는 MINOR >= 10 -->

## 엔트리 (append only — 단일 `cat >>` 명령으로만 추가, 기존 줄 편집 금지)
- [MINOR] L2-001 | FR-011 | agent:orchestrator | 2026-08-12T23:10:00+09:00 | `## 태그·키워드` 섹션은 태그를 쉼표+공백으로 이어 한 줄로 렌더한다(`영업, 실적, 2026`). 해시태그(`#영업`)나 불릿 목록을 쓰지 않는다 | 근거: 스펙 §4.4가 `<태그 목록>`이라고만 표기해 형식 미지정. 한 줄 쉼표 구분이 마크다운 뷰어·grep 모두에서 단순하고, 빈 배열일 때도 헤더 아래 빈 줄만 남아 "섹션 누락 불가" 규칙을 자연스럽게 만족한다.
- [MINOR] L2-002 | FR-009 | agent:worker-ollama | 2026-08-12T23:35:00+09:00 | 헬스체크 URL은 `--ollama-url`을 항상 슬래시로 끝나는 베이스로 만든 뒤 `api/tags`를 결합한다 — 베이스에 경로가 있으면(`http://host/ollama`) 그 경로를 보존한다(`http://host/ollama/api/tags`) | 근거: 스펙 §4.3은 URL 조립 규칙 미지정. 맨 urljoin은 베이스의 마지막 경로 세그먼트를 잘라내 리버스 프록시 뒤의 Ollama를 못 찾는다. 기본값(`http://127.0.0.1:11434`)에서는 동작 차이가 없다.
