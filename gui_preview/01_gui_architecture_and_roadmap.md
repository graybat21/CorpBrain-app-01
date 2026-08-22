# CorpBrain 지식그래프 및 GUI 아키텍처 참고안

- **문서 번호**: 01
- **작성일**: 2026-08-21
- **작성자**: AI 동료 다온 (수신: 회비서)
- **상태**: 디자인 관점 참고 자료 — 특정 버전의 실행 계획이 아니며, 버전 범위는 `static/docs/specs/features/` 의 확정 스펙과 `docs/ROADMAP.md` 가 정한다

---

## 1. 개요 및 배경

CorpBrain은 v0.1부터 v0.5까지 단계적으로 발전하여 다음 핵심 역량을 갖춘 100% 로컬 우선(Local-First) AI 지식 관리 코어 엔진을 구축했습니다:
1. **v0.1**: 로컬 문서(.docx, .txt, .md) 스캔 → Ollama 요약 → 결정적 마크다운 위키 생성 (단일 네트워크 관문).
2. **v0.2**: .pdf 포맷 확장, 사전 계량(plan) 및 중요도 점수화, 소요시간·토큰 추정.
3. **v0.3**: 하드웨어/자원 게이팅(GPU 필수 검사, 파일 크기·토큰 상한) 및 환경 진단(`doctor`).
4. **v0.4**: 로컬 벡터 임베딩(`nomic-embed-text`) + SQLite 벡터 스토어 + 시맨틱 검색(`search`).
5. **v0.5**: 클라우드 옵트인(Anthropic Claude), 사용자 동의 시스템, 한국 특화 7종 PII 마스킹, NetworkGuard 보안 불변식.

이 문서가 다루는 것은 **(2c) 지식그래프(Knowledge Graph)** 시각화와, 사용자가 직관적으로 시스템을 제어하고 지식을 탐색할 수 있는 **GUI(Graphical User Interface) 화면**의 디자인 관점 검토입니다.

---

## 2. 핵심 아키텍처 원칙 (불변식)

1. **Local-First & Zero Outbound**: 기본 구동은 100% 로컬(`127.0.0.1`)이며, 외부 네트워크로 어떠한 텔레메트리나 비인가 트래픽도 발생하지 않음.
2. **Core No-I/O & Clean Architecture**: 비즈니스 로직은 코어 패키지(`corpbrain.core`)에 순수 함수/객체로 존재하며, CLI 및 GUI는 코어를 호출하는 얇은 어댑터 레이어로 작동.
3. **Single Gateway Invariant**: 클라우드 옵트인 사용 시에도 모든 외부 호출은 단일 관문(`gateway.request_json`) 및 NetworkGuard allowlist를 통해서만 통제.
4. **Deterministic Graph & Vector Invariant**: 지식그래프와 벡터 인덱스는 재현 가능하고 독립적인 로컬 스토리지에 격리 저장.
5. **Zero External CDN Dependency**: GUI는 오프라인 로컬 환경에서도 100% 구동될 수 있도록 모든 정적 자산(CSS, JS, 폰트, 아이콘, 그래프 엔진)을 로컬에 번들링.

---

## 3. 지식그래프(Knowledge Graph) 엔진 설계

### 3.1 그래프 모델 (Graph Schema)
- **노드 (Node Types)**:
  - `Document`: 위키 문서 노드 (doc_id, title, path, summary, tags, created_at)
  - `Entity`: 핵심 개체 (인물, 부서, 시스템, 프로젝트, 기술명 등)
  - `Topic / Tag`: 문서 분류 카테고리 및 키워드
- **엣지 (Edge Types)**:
  - `REFERENCES`: 문서가 다른 문서를 직접 언급/참조
  - `CONTAINS_ENTITY`: 문서가 특정 엔티티를 포함
  - `TAGGED_WITH`: 문서가 특정 태그를 보유
  - `SEMANTICALLY_SIMILAR`: 벡터 유사도 임계치(예: cosine >= 0.75) 이상의 문서 간 연결
  - `RELATES_TO`: 엔티티 간의 유의미한 관계

### 3.2 그래프 스토리지 및 API
- `SqliteGraphStore`: `<out_dir>/.corpbrain_graph.sqlite` (또는 인덱스 DB 통합)
- `build_graph_from_wiki()`: 위키 문서들의 프론트매터, 요약, 엔티티, 벡터 유사도를 결합하여 그래프 모델 구축
- `query_graph()`: 노드/엣지 데이터, 중심성(Centrality), 서브그래프(k-hop), 연관 경로 조회 API

---

## 4. GUI 시스템 아키텍처 및 화면 구성

```
┌───────────────────────────────────────────────────────────────┐
│                 CorpBrain GUI (Desktop / Web)                 │
│  [Dashboard] [Plan & Scan] [Wiki Explorer] [Graph] [Search]   │
└──────────────────────────────┬────────────────────────────────┘
                               │ HTTP / SSE (127.0.0.1)
┌──────────────────────────────▼────────────────────────────────┐
│               CorpBrain Local GUI Server (Adapter)            │
│       FastAPI / Starlette + SSE Event Stream Dispatcher       │
└──────────────────────────────┬────────────────────────────────┘
                               │ Direct Python Core Calls
┌──────────────────────────────▼────────────────────────────────┐
│                   CorpBrain Core Library                      │
│ ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│ │ run_scan()   │ plan_scan()  │ diagnose()   │ search_index │ │
│ ├──────────────┼──────────────┼──────────────┼──────────────┤ │
│ │ VectorStore  │  GraphStore  │ PII Engine   │ Consent/Auth │ │
│ └──────────────┴──────────────┴──────────────┴──────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 4.1 6대 핵심 화면(View) 사양

1. **대시보드 (Dashboard & System Health)**
   - Doctor 실시간 진단 상태: Ollama 데몬, GPU 가용성, 임베딩 모델(`nomic-embed-text`), 클라우드 동의 및 API 키 상태.
   - 통계 지표: 생성된 위키 수, 인덱싱된 문서 수, 지식그래프 노드/엣지 수, 최근 처리 기록.

2. **플랜 & 스캔 제어 허브 (Plan & Scan Hub)**
   - 폴더 브라우저 및 입력 경로 지정.
   - 실행 옵션 제어: 엔진 선택(로컬/클라우드), 요약 모델, 파일 크기 및 토큰 예산 게이트 설정.
   - Pre-scan 계량 리포트: 예상 소요 시간, 중요도 점수 분포, 게이트 통과 여부 미리보기.
   - 실시간 스캔 모니터: SSE 스트림 기반 파일별 실시간 진행률, 추출/요약/임베딩/그래프 단계 라이브 표시.

3. **인터랙티브 지식그래프 캔버스 (Knowledge Graph View)**
   - 2D/3D Force-Directed Graph 시각화 (노드 물리학, 줌/팬, 드래그).
   - 노드 필터링(문서, 엔티티, 태그), 클러스터별 컬러 코딩.
   - 노드 클릭 시 요약 카드 및 연관 문서 링크 팝업, 위키 뷰어 연동.

4. **위키 탐색기 및 뷰어 (Wiki Explorer & Reader)**
   - 좌측 계층형 폴더/문서 트리 뷰.
   - 중앙 고품질 마크다운 렌더러: 표, 코드블록, 헤더 네비게이션, 프론트매터 메타 배지.
   - 우측 문서 컨텍스트 패널: 추출된 PII 마스킹 내역, 연결된 지식그래프 이웃 문서, 벡터 유사 문서 추천.

5. **시맨틱 & 그래프 하이브리드 검색기 (Hybrid Search)**
   - 자연어 질의 입력창 및 실시간 검색.
   - 코사인 유사도 점수와 그래프 연결 가중치를 결합한 검색 결과 카드.
   - 검색 결과 클릭 시 해당 노드로 지식그래프 캔버스 즉시 포커싱.

6. **설정 및 보안 센터 (Settings & Governance)**
   - 클라우드 옵트인 동의(`consent grant/revoke`) 토글 스위치.
   - Anthropic API Key 상태 확인 및 NetworkGuard 목적지 화이트리스트 검증.
   - 한국 특화 7종 PII 마스킹 규칙 확인 및 실시간 마스킹 테스터.

---

## 5. 단계별 실행 계획 (Phased Roadmap)

### Phase 1: 지식그래프 코어 엔진 개발
- [ ] 지식그래프 데이터 모델 (`GraphNode`, `GraphEdge`, `GraphData`) 정의
- [ ] `SqliteGraphStore` 구현 및 엔티티/관계 추출 로직(`corpbrain.core.graph`) 개발
- [ ] 파이프라인(`run_scan`)에 그래프 인덱싱 단계 통합
- [ ] 지식그래프 단위 테스트 및 통합 테스트 작성

### Phase 2: GUI 백엔드 로컬 API 서버 어댑터 구축
- [ ] `corpbrain.server` 또는 `corpbrain.gui_server` 모듈 구현 (FastAPI/Starlette 기반, 127.0.0.1 전용)
- [ ] SSE(Server-Sent Events) 이벤트 브리지 구현 (코어 `ProgressEvent` → 프론트엔드 실시간 전송)
- [ ] CLI 명령 `corpbrain gui` (또는 `corpbrain app`) 추가 및 자동 브라우저 오픈 기능

### Phase 3: GUI 프론트엔드 디자인 시스템 및 공통 레이아웃 구축
- [ ] 모던 다크/라이트 테마, 글래스모피즘, 반응형 사이드바 및 네비게이션
- [ ] 대시보드(Doctor 환경 진단 + 지표 통계) 컴포넌트
- [ ] 설정 & 보안 센터(클라우드 동의, PII 테스터) 컴포넌트

### Phase 4: 스캔 워크스페이스 & 위키 뷰어 구현
- [ ] Plan 계량 결과 시각화 및 실시간 스캔 프로그레스 모니터
- [ ] 위키 문서 트리 탐색기 및 완성도 높은 마크다운 렌더러

### Phase 5: 인터랙티브 지식그래프 시각화 및 하이브리드 검색 구현
- [ ] Force-Directed 지식그래프 캔버스 엔진 연동
- [ ] 시맨틱 + 지식그래프 하이브리드 검색 인터페이스 연동
- [ ] 그래프 노드 클릭 ↔ 위키 문서 상호 이동 네비게이션 완성

### Phase 6: 종합 검증 및 품질 게이트
- [ ] 전체 pytest 스위트 실행 및 통과 검증
- [ ] 네트워크 불변식(100% 로컬, 비인가 외부 연결 0) 보안 검증
- [ ] ruff lint & format 검증
- [ ] 사용자 가이드 및 스모크 테스트 문서 업데이트

---

## 6. 이 문서의 위치

이 문서는 GUI와 지식그래프 시각화를 **디자인 관점에서 검토하기 위한 참고안**이다. 승인 절차나
구현 착수의 근거가 아니며, §5의 단계별 계획도 특정 버전에 배정된 실행 계획이 아니라 GUI를
만들 때 밟게 될 순서를 스케치한 것이다.

실제 구현 범위와 착수 여부는 다음이 정한다.

- 확정 스펙: `static/docs/specs/features/` — 여기에 스펙이 있는 것만 구현 대상이다.
- 버전 배정: `docs/ROADMAP.md` — v0.7 이후는 v0.6 완료 후 다시 정리한다.
- 착수 절차: `CLAUDE.md`의 스펙 주도 워크플로우 (`/interview` → `/spec` → 구현 → `/spec-check`).

따라서 이 문서의 내용을 구현하려면, 먼저 해당 범위를 `/interview`로 확정하고 `/spec`으로
확정 스펙을 만든 뒤에 시작한다.
