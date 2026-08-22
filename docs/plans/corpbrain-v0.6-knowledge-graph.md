# 실행 플랜 — v0.6 지식그래프

- 스펙: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` (확정, 492줄)
- 결정 원장: `docs/grill/GRILL_LEDGER-v0.6*.md` 5종 (전부 ALL_RESOLVED)
- 최종 갱신: 2026-08-23

## 브랜치·PR 전략 [사용자 결정]

**순차 2-PR, 병렬 개발 없음.**

```
PR ①  feat/v0.6-graph-core
      GraphStore · 그래프 빌더 · 엔티티 정규화 · doc_facts
      파이프라인 2-패스 통합 · 렌더러 변경 · 「관련 문서」 주입
      → 머지 시점에 "상호연결된 위키"라는 사용자 가치가 완결된다

PR ②  feat/v0.6-graph-cli
      corpbrain graph 명령 · report.py 빌더 3개 · CLI 테스트 · 문서
      → 조회 표면을 더한다. PR① 머지 후 착수한다.

둘 다 머지된 뒤 v0.6.0 tag
```

근거:

- v0.6 스펙은 492줄로 v0.5(384줄)의 1.3배, 나머지 버전(106~163줄)의 3~4배다. v0.5는 단일
  PR로 가서 구현 커밋 8개 뒤에 코드리뷰·보안리뷰 수정 커밋 7개가 붙었다 — 리뷰 부하가
  뒤로 몰린 신호로 읽힌다.
- v0.6은 두 반쪽이 각각 독립적으로 완결되는 드문 경우다. PR①만으로 위키가 서로 이어지고,
  PR②는 순수 추가다. 3-PR로 더 쪼개면 첫 PR 머지 후 `main`에 아무도 호출하지 않는
  `GraphStore`가 남는 죽은 코드 구간이 생긴다.
- `ROADMAP.md` §2가 "기능마다 `feat/*` 단기 브랜치 → PR → `main` 머지, 버전 마일스톤 = tag"로
  정한 것과 맞다. PR 단위는 기능이고 버전은 tag다.

### 병렬 개발을 하지 않는 이유 [사용자 결정]

서브에이전트 2개 이상으로 동시 개발하는 안을 검토했으나 채택하지 않는다.

- **텍스트 충돌은 문제가 아니다.** `models.py`·`core/__init__.py`·`config.py`는 항목을 덧붙이는
  변경이라 대부분 자동 병합되고 해결도 기계적이다.
- **의미 충돌이 실제 위험이다.** 각자 옳게 작성했는데 합치면 조용히 틀리는 경우다. 예를 들어
  `GraphStats.edges_by_type`의 키 문자열 표기가 스펙에 없어, 코어 담당이 `"TAGGED_WITH"`로
  넣고 표면 담당이 `"tagged_with"`를 기대하면 타입 검사도 각자의 단위테스트도 통과하지만
  통합 시점에야 드러난다. 같은 종류가 「관련 문서」 근거 문구의 구분자, `--neighbors` 출력
  들여쓰기, 종료 요약 줄의 접두 공백에도 남아 있다.
- **병렬의 실익이 작다.** 임계 경로가 `doc_facts 스키마 → 그래프 빌더 → 파이프라인 2-패스 →
  「관련 문서」 주입 → 통합테스트`로 한 줄기다. 떼어낼 수 있는 것은 CLI·리포트 표면 정도인데,
  앞 사슬이 끝나야 그 출력이 맞는지 검증할 수 있다. 병렬로 앞당겨지는 것은 작성 시간이지
  검증 시간이 아니다.
- 병렬을 하려면 타입과 문자열 계약을 문자 수준까지 선행 확정해 머지하는 단위(U0)가 필요한데,
  그 비용을 치르고 얻는 병렬 구간이 전체의 30% 남짓이다.
- **v0.5의 병렬 전례와 모순되지 않는다.** `docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md`는
  "서로도, 메인 작업과도 파일이 겹치지 않는 독립 leaf 모듈"에 한해 서브에이전트 2개를 동시에
  띄웠고 성공했다. 그때 병렬 대상(`pii.py`·`consent.py`)은 **공유 타입 표면이 없는 신규 leaf
  파일**이었다. v0.6의 두 축(그래프 코어 / CLI·리포트 표면)은 `models.py`의 타입을 공유하므로
  같은 조건이 아니다.

## 작업 단위 (10개) [사용자 결정]

v0.2 플랜이 세운 «값 타입 → 코어 → 렌더러 → 배선 → 조인» **계층별 분해**를 계승한다.
단위끼리 건드리는 파일이 거의 겹치지 않아 커밋 경계가 자연스럽고, `graph.py`·정렬 규칙·
통합테스트 코퍼스를 각각 한 번씩만 쓴다.

### PR ① `feat/v0.6-graph-core`

| | 단위 | 건드리는 파일 | depends |
|---|---|---|---|
| U1 | 값 타입·설정 | `models.py`(`DocFacts`·`GraphStats`·`GraphOutcome`·`GraphSkipReason`·`InjectionFailure`) · `config.py`(2필드) · `core/__init__.py` | — |
| U2 | `GraphStore` | `graphstore.py` — Protocol 8메서드 + `SqliteGraphStore` + `schema_version` | U1 |
| U3 | 요약 스키마 확장 | `llm/base.py`(`entities` 선택 필드 검증) · `llm/summarize.py`(프롬프트) · `llm/anthropic_client.py`(tool `properties`) | — |
| U4 | 그래프 빌더 | `graph.py`(정규화·4종 엣지·자기루프 제외·`>=`·`src<dst`) · `vectorstore.py`(`iter_vectors`) · `pipeline.py`(`_NoIndexStore`) | U1·U2 |
| U5 | 렌더러·파서 | `render.py`(마커·빈 블록·`SECTION_HEADERS`) · `embedding_text.py`(`_ALL_SECTIONS`·3-튜플) · `_backfill_embedding` 호출부 · 기존 테스트 4곳 | — |
| U6 | 파이프라인 통합 | `pipeline.py`(2-패스·store 수명·주입·내용비교·`GraphOutcome`·재료 복원 fallback) · `report.py`(종료 요약) · `cli.py`(`scan` 옵션 2개) | U3·U4·U5 |
| U7 | 통합테스트·조인 | 인라인 6문서 코퍼스 · 완료의 정의 1·2·4·5·6·7 · 네트워크 불변식 1케이스 | U6 |

### PR ② `feat/v0.6-graph-cli`

| | 단위 | 건드리는 파일 | depends |
|---|---|---|---|
| U8 | 리포트 빌더 | `report.py` 빌더 3개 · `tests/unit/test_graph_report.py` | PR① 머지 |
| U9 | `graph` CLI | `cli.py` 서브커맨드·경로 해석·오류 계약 · `tests/test_cli_graph.py` · 네트워크 소켓 0건 케이스 | U8 |
| U10 | 문서 | `docs/USAGE.md` · `docs/SMOKE.md` 실행 H · 스펙 상태 → 완료 | U9 |

### 실행 순서

병렬이 없으므로 선형이다. `U3`와 `U5`는 앞 단위에 의존하지 않아 앞뒤로 옮길 여지가 있다.

```
U1 → U2 → U3 → U4 → U5 → U6 → U7 → [PR① 머지]
   → U8 → U9 → U10 → [PR② 머지] → v0.6.0 tag
```

### 커밋 프리픽스

v0.5의 단계 표기를 계승한다.

```
v0.6(core):   U1 · U2 · U4
v0.6(llm):    U3
v0.6(render): U5
v0.6(wiring): U6
v0.6(test):   U7
v0.6(report): U8
v0.6(cli):    U9
v0.6(docs):   U10
```

### 수직 슬라이스를 채택하지 않은 이유

엣지 종류별 end-to-end 분해(태그 → 엔티티 → 유사도 → 참조)도 검토했다. 슬라이스마다 동작하는
그래프가 나오고 실패가 격리되는 장점이 있으나 채택하지 않는다.

- `graph.py`·「관련 문서」 정렬 규칙·근거 문구·통합테스트 코퍼스를 **각각 네 번** 고쳐 쓴다.
  계층별로는 각각 한 번이다.
- 계층적 정렬이 `① REFERENCES → ② 유사도 → ③ 공유 엔티티 → ④ 공유 태그` 순인데, 태그부터
  슬라이스하면 **가장 낮은 우선순위부터 만들고 가장 높은 것을 마지막에** 끼워 넣게 되어 정렬
  함수를 네 번 다시 쓴다.
- 첫 슬라이스가 `models.py`·`graphstore.py`·2-패스 구조·`render.py`·주입까지 삼켜 인프라의
  70%를 짊어진다. 슬라이스가 균등하지 않아 "일찍 눈에 보인다"는 이점도 크게 줄어든다.

## 실행 문서 구성 [사용자 결정]

v0.1·v0.2 방식대로 두 문서를 둔다. 역할이 겹치지 않는다.

- **이 문서(`docs/plans/`)** — 사람이 읽는 정본. 작업 단위·의존·실행 순서와 «채택하지 않은
  안의 근거»를 담는다.
- **`docs/goals/corpbrain-v0.6-knowledge-graph-loop.md`** — 에이전트 실행 지시(`/goal`).
  종료 조건·자율 범위·금지 행위를 담는다. grill 5라운드 결정이 전부 스펙에 들어가 있으므로
  v0.5의 goal 프롬프트보다 짧아진다 — 세부 계약은 "스펙과 이 계획 문서를 정본으로 삼는다"로
  가리키면 된다.

## 커밋 규율 [사용자 결정]

**모든 커밋이 green이어야 한다** — 각 단위 커밋은 자기 단위테스트를 함께 담는다.

CI는 `main` push와 모든 PR에서 돌므로 제도적 검사 단위는 커밋이 아니라 push다. 그럼에도
커밋 단위 green을 요구하는 이유는, 계층별 분해를 택한 덕에 각 단위가 독립적으로 테스트
가능해서 사실상 공짜로 얻어지는 성질이기 때문이다. v0.5처럼 리뷰 수정 커밋이 여럿 붙는
상황에서 회귀를 추적할 때 `git bisect`가 실제로 동작한다.

강제되는 결합은 하나뿐이다 — **U5의 `parse_wiki_markdown` 3-튜플 변경**은 호출부
(`pipeline._backfill_embedding`)와 테스트 3곳(`tests/unit/test_embedding_text.py:52`·`:70`·`:92`)을
같은 커밋에서 고쳐야 green이다. 나머지 단위는 신규 파일이거나 항목 추가라 자연히 green이다.

## 불변식 (모든 단위 공통)

`docs/ROADMAP.md` §5의 버전 불변식을 그대로 따른다 — 단일 게이트웨이 경유, 기본 로컬,
코어 no-I/O, 하위 호환(신규 파라미터는 선택·기본값 보존), `ruff check .` · `pytest` green.
