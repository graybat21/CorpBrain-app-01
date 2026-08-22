# Grill Ledger — v0.6 지식그래프 (3라운드: 스펙 자체 정합성)

1라운드(실행 수준 설계) `GRILL_LEDGER-v0.6.md` · 2라운드(기존 코드 통합) `GRILL_LEDGER-v0.6-integration.md` — 둘 다 ALL_RESOLVED.

참조 범위: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md` 전문 + 기존 확정 스펙 6종
관심 방향: 인터뷰 1회 + grill 2라운드로 15회 이상 증분 수정된 문서의 내부 모순·중복·누락과 기존 스펙과의 충돌
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.6-knowledge-graph.md`, 필요 시 `CLAUDE.md`

## 질문 없이 정정한 것 (결정이 아니라 문서가 스스로와 어긋난 곳)

- C1·C2 — §4.1 엣지 표의 «재료»가 §4.4 재빌드 전략과 어긋났다. 엣지는 `SummaryResult`가 아니라 `doc_facts`에서 파생하며(스킵 문서는 `SummaryResult`가 없다), `REFERENCES`의 재료도 "추출된 원문 텍스트"가 아니라 요약 입력 텍스트(§5)다.
- C3 — §4.5가 「관련 문서」를 "7번째 필수 섹션"이라 했으나 `SECTION_HEADERS` 기준으로는 6번째 원소다(v0.1 스펙은 `# 제목`을 포함해 센다). 두 셈을 함께 명시했다.
- C4 — §4.5의 «내용이 달라졌을 때만 기록»이 «렌더러가 빈 블록을 소유한다»의 하위 불릿으로 잘못 들여쓰기돼 있었다. 독립 항목으로 올렸다.
- C5 — §4.6이 `InjectionFailure`를 참조만 하고 정의하지 않았다. v0.4 `EmbeddingFailure`와 동형(`path`, `detail`)으로 정의를 추가했다.
- C6 — §1의 파이프라인 단계 순서가 실제와 달랐다(인덱싱은 렌더 뒤다).
- C7 — §3 항목4의 `generated_at` 예외 조건이 불명확했다. 무옵션 재실행은 파일을 다시 쓰지 않으므로 바이트 동일하고, `--force` 2회 비교에서만 예외가 필요하다.

RESOLVED: 4 / TOTAL: 4  ·  STOP: ALL_RESOLVED

- [x] V1 | CORE  | graph 명령의 --similarity-threshold/--related-top-k가 조회 전용 명령에서 하는 일 | status:RESOLVED | decision:두 옵션을 graph에서 제거하고 순수 조회 명령으로 확정. 임계치 실험은 scan 재실행(임계치는 should_regenerate가 보지 않아 LLM 호출 0). 조회 시 재계산은 --stats가 DB·위키와 어긋나 완료의 정의 3번 위반 | applied:corpbrain-v0.6-knowledge-graph.md §4.7, CLAUDE.md
- [x] V2 | CORE  | LLM 응답에 entities 필드가 없을 때의 처리와 v0.5 tool 스키마 반영 범위 | status:RESOLVED | decision:entities는 선택 필드(누락 시 빈 배열) — 위키 템플릿에 렌더되지 않는 그래프 전용 재료라 생성 실패 사유가 될 수 없음. 기존 5필드는 필수 유지. 두 엔진에 같은 규칙(validate_summary_fields 공유 유지), Anthropic properties에는 추가하되 required에는 넣지 않음 | applied:corpbrain-v0.6-knowledge-graph.md §4.2, CLAUDE.md
- [x] V3 | MINOR | GraphStore Protocol의 메서드 계약을 스펙에 명시할지 | status:RESOLVED | decision:v0.4 선례대로 전체 계약을 스펙에 명시 — upsert_facts/get_facts/iter_facts/delete_facts/replace_graph/stats/neighbors/degree_ranking/close, 각 메서드에 요구 근거 표기. v0.4가 3→6메서드로 넓혔던 누락을 반복하지 않기 위함 | applied:corpbrain-v0.6-knowledge-graph.md §4.4
- [x] V4 | MINOR | 그래프 DB 스키마 버전·마이그레이션 정책 | status:RESOLVED | decision:v0.4 동형 — meta.schema_version(초깃값 "1") 불일치·손상 시 자동 복구 없이 PreconditionError exit 1 + 삭제·재실행 안내. §2 비목표에 마이그레이션 명시. 조용한 폐기는 데이터 손실이 뒤늦게 드러나므로 비채택 | applied:corpbrain-v0.6-knowledge-graph.md §2, §4.4, §5, CLAUDE.md
