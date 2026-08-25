# 실행 플랜 — v0.7 하이브리드 검색 (코사인 + 그래프 시드 확산, issue #43)

- 스펙: `static/docs/specs/features/corpbrain-v0.7-hybrid-search.md` (확정)
- 결정 원장: `docs/grill/GRILL_LEDGER-v0.7-hybrid-search.md`(계약 공백 11건) ·
  `-implementation-order.md`(이 문서의 근거)
- 최종 갱신: 2026-08-25

## 착수 전제 [사용자 결정 · grill-it Y1]

**PR #45(#42 임베딩 모델 재판단)가 `main`에 머지된 뒤에 코드를 시작한다.** 스펙 §1의 선행
조건을 글자 그대로 지킨다.

```
[지금]     PR #45 머지 (MERGEABLE · CI green — 머지 버튼만 남았다)
[그 다음]  git checkout main && git pull
           git switch -c feat/v0.7-hybrid-search
[대기 중]  이 계획 문서 작성까지만. 코드는 손대지 않는다.
```

- 대기 비용이 사실상 0이다 — #45는 리뷰 대기도 CI 실패도 아니고 머지만 남았다.
- 그 대가로 세 가지 위험이 한꺼번에 사라진다: ① `config.py` 상수 충돌 ② #45가 리뷰로
  바뀔 때의 리베이스 사슬 ③ 옛 임베딩 모델 위에서 잰 α가 무효가 되는 것(스펙 §4.8은 α가
  `qwen3-embedding:4b` 위에서만 유효하다고 못박았다).
- #45 브랜치 위에 얹어 병행하는 안은 채택하지 않는다. 얻는 것이 없고 PR 의존 사슬만 생긴다.

## 브랜치·PR 전략 [사용자 결정 · grill-it Y2]

**단일 PR `feat/v0.7-hybrid-search`. 병렬 개발 없음.**

```
feat/v0.7-hybrid-search
    U1…Un  →  스윕 스크립트·쿼리 세트  →  [사용자 스윕 대기]  →  α 확정
    → 머지 후 v0.7.0 tag
```

근거:

- **쪼갤 자리가 없다.** 구현 표면이 `search` 한 명령에 몰려 있고 신규 저장 계층·파이프라인
  변경·위키 산출물 변경이 전부 없다(스펙 §2). 코어 확산 로직의 호출자는 `search_index()`
  하나뿐이라, 코어를 먼저 머지하면 `main`에 **아무도 호출하지 않는 확산 함수**가 남는다 —
  v0.6이 3-PR을 거부한 것과 같은 근거다.
- **v0.6의 2-PR과 모순되지 않는다.** v0.6은 PR①만으로 「상호연결된 위키」라는 사용자 가치가
  완결되는 드문 경우였다. 이번엔 코어만으로는 아무것도 동작하지 않아 같은 조건이 아니다.
- **병렬 서브에이전트도 쓰지 않는다.** 임계 경로가 `타입 → 확산 계산 → 정렬 → 리포트 →
  CLI 배선 → 통합테스트` 한 줄기이고, 떼어낼 수 있는 표면(리포트)은 앞 사슬이 끝나야 출력이
  맞는지 검증된다. v0.6 플랜의 「의미 충돌이 실제 위험」 판단을 그대로 계승한다.
- α 실측 대기는 PR을 쪼개는 대신 **같은 PR 안의 커밋 경계**로 다룬다(아래 Y4 절).

## 작업 단위 (10개) [사용자 결정 · grill-it Y3]

v0.2·v0.6 플랜의 «값 타입 → 코어 → 렌더러 → 배선 → 조인» **계층 분해**를 계승한다. 단위끼리
건드리는 파일이 거의 겹치지 않아 커밋 경계가 자연스럽고, 각 단위가 자기 단위테스트를 함께
담아 모든 커밋이 green이다(v0.6 X3 계승).

| | 단위 | 건드리는 파일 | depends |
|---|---|---|---|
| U1 | 값 타입·설정 | `models.py`(`GraphExpansion` · `SearchResult.expansion`) · `config.py`(`DEFAULT_GRAPH_DECAY`=0.7 잠정 · `DEFAULT_EXPAND_EDGES`) · `core/__init__.py` | — |
| U2 | 확산 순위 계산 | `graph.py` — 점수 `max(cosine, seed×α)` · §4.3 계층 정렬 · 기준 시드 선택 · `tests/unit/test_search_ranking.py` | U1 |
| U3 | 입력 검증 | α 범위(`0<α<1`) · `--expand-edges` 파싱(trim·중복·빈 목록·대소문자) · 단위테스트 | U1 |
| U4 | 조회 조립 | `search.py` — `SqliteGraphStore(read_only=True)` 개봉 · 시드 이웃 수집 · 전체 코사인 매핑 · DB 부재/손상 분기 | U2·U3 |
| U5 | 리포트 | `report.py:build_search_lines()` 확장 · `tests/unit/test_search_report.py`(정확 문자열) | U1 |
| U6 | CLI 배선 | `cli.py` — `--no-graph`·`--graph-decay`·`--expand-edges` · `_run_search` · `tests/test_cli_search.py`(종료 코드·배선만) | U4·U5 |
| U7 | 통합·보안 테스트 | 인라인 코퍼스 통합테스트(DoD 1~7·9·10) · `tests/security/test_network_invariant.py` 케이스 추가 | U6 |
| U8 | 문서 | `docs/USAGE.md` 검색 절 · `docs/smoke/README.md` 절차 | U6 |
| U9 | 스윕 하네스 | `docs/smoke/graph_decay_sweep.py` · `graph_decay_queries.json` 초안 | U6 |
| U10 | α 확정 | 사용자 스윕 결과 → `config.py` 상수 교체 · `docs/smoke/` 결과 · 스펙 §0 기록 | U9 · **사용자** |

### 순수 계산과 저장소 조회를 가르는 자리 [사용자 결정]

확산의 **순수 계산부(점수·계층 정렬·기준 시드 선택)는 `graph.py`에 `rank_related` 옆에 둔다.**
저장소 조회와 조립만 `search.py`가 한다.

- `graph.py`의 독스트링이 세운 「파일도 네트워크도 저장소도 건드리지 않는다」가 유지되고,
  U2가 저장소 없이 단위테스트로 전부 덮인다.
- v0.6 `rank_related`와 순위 규칙이 한 파일에 나란히 놓여, 계층 정렬 키를 계승했다는 사실이
  코드에서 보인다.

### 실행 웨이브

```
W1  U1
W2  U2 · U3 · U5          (셋 다 U1만 의존 — 순차로 돈다, 병렬 개발 없음)
W3  U4
W4  U6                     ← 이 시점에 사용자가 손으로 써 볼 수 있다
W5  U7 · U8 · U9
W6  [사용자 스윕 실행]  →  U10
```

수직 슬라이스(엣지 종류별 end-to-end)는 채택하지 않는다 — `graph.py` 정렬 규칙·근거 문구·
통합테스트 코퍼스를 세 번 고쳐 쓰게 되고 첫 슬라이스가 인프라 대부분을 삼킨다(v0.6과 같은
판단). 굵은 4단위도 채택하지 않는다 — 커밋이 커져 `git bisect`가 무뎌지고 테스트가 뒤로
몰린다.

## α 실측 대기 구간 [사용자 결정 · grill-it Y4]

U9까지 끝나면 **draft PR**을 연다. 스윕 결과가 오면 U10 커밋을 얹고 ready로 전환해 머지한다.

```
U9 완료  →  draft PR (CI·리뷰가 대기 시간과 겹쳐 돈다)
             ↓  [사용자: 코퍼스 scan → α 스윕 → 원시 출력 전달]
U10 커밋  →  ready  →  머지  →  v0.7.0 tag
```

- **잠정값 0.7이 `main`에 들어가는 순간이 없다** — 스펙 T11의 「잠정값인 채로 릴리스하지
  않는다」가 머지 조건으로 자동 작동한다. 머지 조건은 스펙 §3 항목13(스윕 기록과 α 근거)이다.
- 대기 동안 CI와 리뷰가 함께 돌아 대기 시간이 낭비되지 않는다.
- U9까지 머지하고 U10을 후속 PR로 미는 안은 채택하지 않는다 — Y2에서 단일 PR로 정한 것을
  실질적으로 2-PR로 되돌린다.

### 사용자가 실행할 것 (U9 완료 시점에 안내한다)

```bash
# 1) 코퍼스를 새 임베딩 모델로 인덱싱 — LLM 요약이 24회 돈다 (시간이 걸린다)
corpbrain scan docs/smoke/corpus --out /tmp/corpbrain_v07_sweep

# 2) α 스윕 — 쿼리 임베딩만 돌고 LLM 요약은 0회다
uv run python docs/smoke/graph_decay_sweep.py --out /tmp/corpbrain_v07_sweep

# 3) 원시 출력 전체를 구현 세션에 전달
```

- 스윕 전에 `docs/smoke/graph_decay_queries.json`(쿼리 12~15개와 정답 목록)을 **사용자가
  검토·확정**한다(스펙 §4.8 2번).
- 스윕은 `search --graph-decay`를 반복 호출하는 것이므로 사용자와 같은 경로를 쓴다(§4.8 6번).
