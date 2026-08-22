# CorpBrain GUI 화면 설계 및 AI Studio 의뢰용 상세 명세서

- **문서 번호**: 02
- **작성일**: 2026-08-21
- **작성자**: AI 동료 다온 (수신: 회비서)
- **상태**: 확정 및 프로토타입 제작 완료
- **목적**: 지식그래프 확장까지 아우르는 완성형 GUI 화면을 AI Studio나 프론트엔드 개발자에게 정확하게 의뢰하고 시각적으로 검증할 수 있도록 세부 설계 및 프로토타입을 제공함.

---

## 1. GUI 디자인 철학 및 시스템 아키텍처

### 1.1 디자인 원칙
1. **Local-First & High-Trust Identity**: 100% 로컬 구동이라는 보안성과 신뢰성을 전달하는 프리미엄 다크/글래스모피즘(Glassmorphism) 테마.
2. **Information Density & Clarity**: 기술 전문가 및 사내 지식 관리자가 한눈에 시스템 상태, 스캔 진행률, 지식 연결 구조를 파악할 수 있는 고밀도 대시보드 레이아웃.
3. **Seamless Navigation**: [대시보드] ↔ [플랜/스캔] ↔ [지식그래프] ↔ [위키 리더] ↔ [하이브리드 검색] 간의 유기적인 상태 연동(노드 클릭 시 위키 열기, 검색 결과 클릭 시 그래프 포커싱 등).
4. **Zero-Latency Simulation**: 외부 백엔드가 없어도 모든 UI 인터랙션과 시뮬레이션이 즉각 반응하는 클라이언트 사이드 완성도.

---

## 2. 6대 핵심 화면(View) 세부 기능 명세

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🧠 CorpBrain (Design Preview)     [● Local: 127.0.0.1] [Theme] [Settings]   │
├───────────────┬─────────────────────────────────────────────────────────────┤
│ 📊 Dashboard  │  [ Doctor 진단 카드 ]   [ 핵심 통계 지표 카드 4종 ]          │
│ 🚀 Plan & Scan│  ---------------------------------------------------------  │
│ 🕸️ Graph View │  [ 메인 작업 영역: 탭에 따라 동적 전환 ]                    │
│ 📖 Wiki Reader│  - Force-Directed 2D 지식그래프 캔버스                      │
│ 🔍 Search     │  - 실시간 스캔 모니터 및 Pre-scan 리포트                    │
│ ⚙️ Settings   │  - 마크다운 위키 뷰어 & PII 마스킹 인스펙터                 │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

### View 1. 대시보드 (Dashboard & System Status)
- **시스템 상태 패널 (Doctor Diagnostic Overview)**:
  - `Ollama Status`: 구동 여부 (`127.0.0.1:11434`), 요약 모델 (`qwen2.5:7b-instruct`).
  - `GPU Hardware`: 가속기 감지 상태 (`NVIDIA GeForce RTX 4090 / CUDA`).
  - `Embedding Engine`: 로컬 임베딩 모델 (`nomic-embed-text`, 768차원).
  - `Cloud Engine Consent`: 클라우드 옵트인 동의 여부 (`Granted` / `Revoked`), API Key 마스킹 상태.
- **핵심 지표 카드**:
  - 생성된 위키 문서 수 (42 docs)
  - 추출된 엔티티 및 토픽 수 (128 entities)
  - 지식그래프 노드/엣지 연결 수 (170 nodes / 342 edges)
  - PII 안전 마스킹 처리 건수 (18 items)
- **최근 작업 타임라인 & 퀵 위키 목록**: 최근 스캔 이력 및 최근 조회 문서 빠른 진입.

---

### View 2. 플랜 & 스캔 허브 (Plan & Scan Hub)
- **입력/출력 설정 폼**:
  - 스캔 대상 폴더 경로 입력기 (`./company_inbox`) 및 출력 폴더 (`./corpbrain_wiki`).
  - 요약 엔진 셀렉터: `Local (Ollama)` vs `Cloud (Anthropic Claude Haiku)`.
  - 게이트 제어 토글: GPU 게이트, 토큰 예산 상한 (`200,000`), 파일 크기 상한 (`20MB`).
- **Pre-Scan (Plan) 인터랙션**:
  - `계량 실행(Plan)` 버튼 클릭 시 즉시 파일별 중요도 점수(0~100), 예상 토큰 수, 예상 처리 시간, 게이트 판정(`PASS`/`SKIP`/`WARN`) 테이블 출력.
- **Live Scan 인터랙션**:
  - `스캔 시작(Scan)` 버튼 클릭 시 전체 진행률 프로그레스 바 + 파일별 5단계 상태 스트림 라이브 애니메이션 (`추출` → `요약` → `PII 마스킹` → `임베딩` → `위키 생성 & 그래프 연결`).

---

### View 3. 인터랙티브 지식그래프 캔버스 (Knowledge Graph View)
- **HTML5 2D Canvas Force-Directed 시뮬레이션**:
  - 노드 물리 엔진: 인력/척력/중심력 기반 자동 배치, 드래그 & 드롭 고정, 마우스 휠 줌(0.2x ~ 3.0x), 캔버스 팬(Pan).
  - **노드 유형별 시각 디자인**:
    - 📄 **문서 노드 (Document)**: 에메랄드/청록색 글로우, 타이틀 라벨, 크기: 가중치 비례.
    - 🏷️ **태그/토픽 노드 (Tag/Topic)**: 퍼플/인디고 컬러, 분류 키워드.
    - 🏢 **엔티티 노드 (Entity)**: 골드/앰버 컬러, 부서/프로젝트/시스템/인물명.
  - **엣지 유형별 시각 디자인**:
    - 참조 관계 (`REFERENCES`): 실선 및 방향성 화살표.
    - 태그 소속 (`TAGGED_WITH`): 점선.
    - 시맨틱 유사도 (`SIMILARITY`): 네온 글로우 라인 (유사도 75% 이상).
- **인터랙티브 상세 패널 (Graph Inspector Panel)**:
  - 노드 호버 시 툴팁 및 연결된 엣지 하이라이트.
  - 노드 클릭 시 우측 슬라이드 패널 오픈: 문서 요약, 태그, 연결된 이웃 노드 목록, **[위키 뷰어에서 열기]** 버튼 제공.
  - 노드 필터링 제어기: 문서만 보기 / 엔티티만 보기 / 태그만 보기 / 최소 연결선 필터.

---

### View 4. 위키 탐색기 및 리더 (Wiki Explorer & Reader)
- **좌측 파일 트리 뷰어**: 폴더 계층 구조(`/hr`, `/security`, `/rnd`, `/finance`) 및 문서 검색.
- **중앙 마크다운 렌더러**:
  - YAML Front-matter 메타 배지 (`engine: local`, `model: qwen2.5`, `generated_at: 2026-08-21`).
  - PII 마스킹 상태 배지 (`[PII Masked: 3 items]`).
  - 문서 헤더, 핵심 요약(Key Points), 본문, 태그 칩.
- **우측 컨텍스트 카드**:
  - 원문 파일 메타데이터 (`format: .docx`, `size: 1.2MB`, `mtime: 2026-08-20`).
  - 지식그래프 연관 이웃 문서 퀵 링크.

---

### View 5. 시맨틱 & 하이브리드 검색기 (Hybrid Search)
- **자연어 검색창**: 키워드 및 시맨틱 쿼리 실시간 자동 완성.
- **하이브리드 결과 카드**:
  - 코사인 유사도 일치율 (% 표시 배지).
  - 매칭된 핵심 문장 하이라이팅.
  - **[그래프에서 위치 확인]** 버튼 클릭 시 즉시 Graph View로 전환되어 해당 노드로 포커싱 및 펄스 애니메이션 발생.

---

### View 6. 보안 및 환경 설정 (Settings & Governance)
- **클라우드 옵트인 동의 관리 (`corpbrain consent`)**:
  - `동의 상태(Grant)` 토글 스위치 (로컬 설정 저장 연동).
  - Anthropic API Key 입력 및 마스킹 상태.
  - NetworkGuard 단일 게이트웨이 보안 안내.
- **한국 특화 7종 PII 마스킹 규칙 및 테스터**:
  - 7대 규칙: 주민등록번호, 휴대전화번호, 이메일, 계좌번호, 카드번호, 사업자등록번호, 상세주소.
  - 실시간 PII 마스킹 라이브 테스트 인풋 박스 제공.

---

## 3. AI Studio / 프론트엔드 프롬프트 의뢰 가이드

AI Studio나 외부 생성형 UI 도구에 프롬프트를 넣을 때 활용할 수 있는 핵심 지시문입니다:

```text
[Role & Context]
CorpBrain은 100% 로컬 구동(Zero Outbound) AI 지식 관리 데스크톱 웹 소프트웨어입니다.
로컬 문서를 스캔하여 Ollama/Claude로 요약하고, 마크다운 위키 및 지식그래프를 자동 구축합니다.

[UI Theme & Styling]
- Theme: Dark Mode by default, Glassmorphism accents, Deep Charcoal (#0d1117, #161b22) background with Cyan (#00f2fe, #4facfe) and Emerald (#10b981) highlights.
- Typography: Clean Sans-serif (Inter / Pretendard / System-UI).
- Components: Sidebar navigation, Dashboard metrics, Plan/Scan hub, Force-Directed Knowledge Graph Canvas, Markdown reader, Hybrid search, and Settings.

[Interactivity Requirements]
- No external CDN dependency (Pure Vanilla JS + CSS).
- Interactive Canvas for Knowledge Graph with Physics-based Nodes & Dragging.
- Real-time Progress Simulator for Scanning.
- Seamless view-switching and node-to-wiki cross navigation.
```
