# v0.6 지식그래프 — 의사결정 체크포인트 (PR① graph-core)

정본: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` · `docs/plans/corpbrain-v0.6-knowledge-graph.md` · `docs/grill/GRILL_LEDGER-v0.6*.md`(30개 결정 ALL_RESOLVED).
아래에는 **위 정본에 확정돼 있지 않은** 추가 의사결정만 기록한다.

CORE: 0
MINOR: 1

## CORE (아키텍처·보안·외부의존·데이터 모델)

(없음)

## MINOR (네이밍·디렉터리·로그 포맷·문구)

1. **「관련 문서」 링크는 `--out` 루트 기준이 아니라 그 위키 파일 기준 상대경로로 쓴다.**
   스펙 §4.5는 "링크는 `--out` 기준 상대경로를 쓴다"고 적었으나, 같은 결정의 근거로
   "파일 탐색기·에디터에서 그대로 동작"을 명시하고 있다. 루트 기준 문자열을 그대로 링크에
   넣으면 하위 폴더 문서(`인사/채용계획.docx.md`)에서 `개발/설계.md.md`가 자기 폴더 아래
   (`인사/개발/설계.md.md`)를 가리켜 깨진다. 문구가 아니라 명시된 목적을 따랐다.
   최상위 문서에서는 두 값이 같다. 정렬 tie-break(§4.5 ⑤)는 문서 간 비교라 종전대로
   `--out` 기준 상대경로를 쓴다. — U5
   · **2026-08-23 해소**: 리뷰에서 승인받아 스펙 §4.5 문구를 구현에 맞춰 정정했다.
     이제 스펙과 구현이 글자 그대로 일치한다.

---

## 실행 기록

- 2026-08-23 · PR① `feat/v0.6-graph-core` · 작업 단위 U1~U7 완료
- 검증: `uv run ruff check .` exit 0 · `uv run pytest` 681 passed (착수 시점 585 → +96)
- 완료의 정의 충족: §3 항목 1·2·4·5·6·7 및 항목8의 `scan` 경로. 항목3(graph 조회 CLI)과
  항목8의 `graph` 단독 소켓 0건은 PR② 범위다.

STOP REASON: ALL_DONE
