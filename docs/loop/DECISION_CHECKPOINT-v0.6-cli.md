# v0.6 지식그래프 — 의사결정 체크포인트 (PR② graph-cli)

정본: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` §3 항목3·항목8 · §4.6 · §4.7 · §5 / `docs/plans/corpbrain-v0.6-knowledge-graph.md` U8~U10 / `docs/grill/GRILL_LEDGER-v0.6*.md`.
아래에는 **위 정본에 확정돼 있지 않은** 추가 의사결정만 기록한다.

CORE: 0
MINOR: 1

## CORE (아키텍처·보안·외부의존·데이터 모델)

(없음)

## MINOR (네이밍·디렉터리·로그 포맷·문구)

1. **노드 라벨을 저장소에서 읽지 않고 재료에서 다시 만든다** (`graph.label_index()`).
   라벨은 `nodes.label` 컬럼에 있지만 스펙 §4.4가 확정한 `GraphStore` 9메서드 계약에는 노드
   조회가 없다 — `neighbors()`는 엣지만, `degree_ranking()`은 `(id, 차수)`만 돌려준다.
   계약에 10번째 메서드를 더하면 스펙 §4.4를 고쳐야 하는데 PR② 범위에서 스펙 내용 변경은
   금지다. 그래서 `iter_facts()`로 얻은 재료에서 `build_graph()`와 **같은 규칙**(정규화 키 +
   최다 등장 라벨)으로 다시 만든다. 규칙을 공유하므로 위키 「관련 문서」의 라벨과 `graph`
   출력이 어긋나지 않고, `--max` 규모(기본 50)에서 비용도 무시할 만하다.
   `graph.py`에 **순수 함수를 추가**했을 뿐 기존 동작은 바꾸지 않았다. — U9

---

## 실행 기록

- 2026-08-23 · PR② `feat/v0.6-graph-cli` · 작업 단위 U8~U10 완료
- 검증: `uv run ruff check .` exit 0 · `uv run pytest` 710 passed (착수 시점 687 → +23)
- 완료의 정의 충족: §3 항목3(`graph --stats`/`--neighbors`/`--central`)과 항목8의
  `graph` 단독 소켓 0건. 이로써 v0.6 스펙의 완료의 정의 8개 항목이 전부 충족됐다.
- 남은 것은 실제 모델 수동 스모크(실행 H)와 `v0.6.0` 태그다.

STOP REASON: ALL_DONE
