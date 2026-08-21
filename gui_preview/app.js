/* ==========================================================================
   CorpBrain v0.6 GUI Prototype Interactive Engine
   2-Axis Architecture: Left Sidebar (Projects) + Top Horizontal Tabs
   ========================================================================== */

// --- Multi-Project Workspaces Dataset ---
const MULTI_PROJECTS = {
  p1: {
    id: "p1",
    name: "CorpBrain-app-01",
    branch: "feat/v0.5-cloud-opt-in",
    tag: "기본",
    inputFolder: "./CorpBrain-app-01/inbox",
    outputFolder: "./CorpBrain-app-01/corpbrain_wiki",
    stats: { wikiDocs: 42, entities: 128, graphNodes: 170, graphEdges: 342, piiMasked: 18 },
    doctor: {
      ollama: { status: "정상 가동 중", url: "http://127.0.0.1:11434", model: "qwen2.5:7b-instruct" },
      gpu: { status: "감지됨", device: "NVIDIA GeForce RTX 4090", vram: "24GB" },
      embed: { status: "준비 완료", model: "nomic-embed-text (768 dim)" },
      cloud: { consent: true, provider: "Anthropic Claude Haiku", status: "동의 완료 (Granted)" }
    },
    activities: [
      { icon: "✅", text: "연구개발팀 아키텍처 문서 스캔 및 지식그래프 갱신", time: "방금 전 · 3개 파일 처리 완료" },
      { icon: "🔒", text: "사내 보안 가이드라인 PII 마스킹 (5건 보호 처리)", time: "15분 전 · security/vpn_access_guide.pdf" },
      { icon: "📐", text: "인사 규정 문서 벡터 임베딩 인덱스 동기화", time: "1시간 전 · .corpbrain_index.sqlite" }
    ],
    wikiTree: [
      {
        folder: "01. 인사 및 복무 규정",
        docs: [
          { id: "hr-01", title: "재택근무 및 유연근무제 가이드라인", path: "hr/remote_work_policy.md", format: "docx", size: "1.4MB", date: "2026-08-15", pii: 2 },
          { id: "hr-02", title: "2026 연차 휴가 및 경조휴가 규정", path: "hr/annual_leave_2026.md", format: "pdf", size: "890KB", date: "2026-08-10", pii: 4 },
          { id: "hr-03", title: "신규 입사자 온보딩 및 장비 지급 지침", path: "hr/onboarding_hardware.md", format: "docx", size: "2.1MB", date: "2026-08-01", pii: 1 }
        ]
      },
      {
        folder: "02. 정보보안 및 IT 시스템",
        docs: [
          { id: "sec-01", title: "사내 보안 인증 및 VPN 접속 가이드", path: "security/vpn_access_guide.md", format: "pdf", size: "3.2MB", date: "2026-08-18", pii: 5 },
          { id: "sec-02", title: "클라우드 인프라 보안 감사 체크리스트", path: "security/cloud_audit_checklist.md", format: "md", size: "450KB", date: "2026-08-12", pii: 0 },
          { id: "sec-03", title: "개인정보(PII) 처리 및 데이터 마스킹 표준", path: "security/pii_handling_standard.md", format: "docx", size: "1.8MB", date: "2026-08-05", pii: 6 }
        ]
      },
      {
        folder: "03. 연구개발 및 아키텍처",
        docs: [
          { id: "rnd-01", title: "CorpBrain 로컬 AI 아키텍처 명세서", path: "rnd/corpbain_arch_spec.md", format: "md", size: "1.1MB", date: "2026-08-20", pii: 0 },
          { id: "rnd-02", title: "Ollama 및 온디바이스 LLM 파이프라인 설계", path: "rnd/ollama_pipeline_design.md", format: "docx", size: "2.8MB", date: "2026-08-16", pii: 0 }
        ]
      }
    ],
    graph: {
      nodes: [
        { id: "doc-hr01", name: "재택근무 가이드", type: "doc", val: 18, wikiId: "hr-01" },
        { id: "doc-hr02", name: "연차 휴가 규정", type: "doc", val: 14, wikiId: "hr-02" },
        { id: "doc-hr03", name: "온보딩 장비 지침", type: "doc", val: 12, wikiId: "hr-03" },
        { id: "doc-sec01", name: "보안인증 및 VPN", type: "doc", val: 20, wikiId: "sec-01" },
        { id: "doc-sec02", name: "클라우드 감사", type: "doc", val: 10, wikiId: "sec-02" },
        { id: "doc-sec03", name: "PII 마스킹 표준", type: "doc", val: 16, wikiId: "sec-03" },
        { id: "doc-rnd01", name: "CorpBrain 아키텍처", type: "doc", val: 22, wikiId: "rnd-01" },
        { id: "doc-rnd02", name: "Ollama 파이프라인", type: "doc", val: 14, wikiId: "rnd-02" },
        { id: "ent-hr_team", name: "인사팀", type: "entity", val: 12 },
        { id: "ent-sec_team", name: "정보보안팀", type: "entity", val: 15 },
        { id: "ent-rnd_team", name: "연구개발팀", type: "entity", val: 14 },
        { id: "ent-vpn", name: "사내 VPN망", type: "entity", val: 16 },
        { id: "ent-ollama", name: "Ollama Engine", type: "entity", val: 15 },
        { id: "tag-security", name: "#정보보안", type: "tag", val: 8 },
        { id: "tag-policy", name: "#사내규정", type: "tag", val: 8 },
        { id: "tag-ai", name: "#로컬AI", type: "tag", val: 8 },
        { id: "tag-graph", name: "#지식그래프", type: "tag", val: 8 }
      ],
      edges: [
        { source: "doc-hr01", target: "doc-sec01", type: "ref" },
        { source: "doc-hr01", target: "ent-hr_team", type: "entity" },
        { source: "doc-hr01", target: "ent-vpn", type: "entity" },
        { source: "doc-hr01", target: "tag-policy", type: "tag" },
        { source: "doc-hr02", target: "ent-hr_team", type: "entity" },
        { source: "doc-hr02", target: "tag-policy", type: "tag" },
        { source: "doc-sec01", target: "ent-sec_team", type: "entity" },
        { source: "doc-sec01", target: "ent-vpn", type: "entity" },
        { source: "doc-sec01", target: "tag-security", type: "tag" },
        { source: "doc-sec01", target: "doc-rnd01", type: "ref" },
        { source: "doc-sec03", target: "ent-sec_team", type: "entity" },
        { source: "doc-sec03", target: "doc-rnd01", type: "ref" },
        { source: "doc-sec03", target: "tag-security", type: "tag" },
        { source: "doc-rnd01", target: "ent-rnd_team", type: "entity" },
        { source: "doc-rnd01", target: "ent-ollama", type: "entity" },
        { source: "doc-rnd01", target: "tag-ai", type: "tag" },
        { source: "doc-rnd01", target: "tag-graph", type: "tag" },
        { source: "doc-rnd01", target: "doc-rnd02", type: "ref" },
        { source: "doc-rnd02", target: "ent-ollama", type: "entity" },
        { source: "doc-rnd02", target: "tag-ai", type: "tag" },
        { source: "ent-vpn", target: "tag-security", type: "tag" },
        { source: "ent-ollama", target: "tag-ai", type: "tag" }
      ]
    }
  },
  p2: {
    id: "p2",
    name: "CorpBrain-app",
    branch: "main",
    tag: "기본",
    inputFolder: "./CorpBrain-app/inbox",
    outputFolder: "./CorpBrain-app/wiki",
    stats: { wikiDocs: 18, entities: 45, graphNodes: 63, graphEdges: 120, piiMasked: 4 },
    doctor: {
      ollama: { status: "정상 가동 중", url: "http://127.0.0.1:11434", model: "qwen2.5:7b-instruct" },
      gpu: { status: "감지됨", device: "NVIDIA GeForce RTX 4090", vram: "24GB" },
      embed: { status: "준비 완료", model: "nomic-embed-text" },
      cloud: { consent: false, provider: "None", status: "미동의 (Local Only)" }
    },
    activities: [
      { icon: "📦", text: "v0.4 릴리스 베이스라인 인덱스 동기화 완료", time: "어제 · 18개 문서 인덱싱" }
    ],
    wikiTree: [
      {
        folder: "01. 코어 문서",
        docs: [
          { id: "cb-01", title: "CorpBrain v0.4 아키텍처 개요", path: "core/arch_v04.md", format: "md", size: "620KB", date: "2026-08-01", pii: 0 },
          { id: "cb-02", title: "SQLite 벡터 인덱스 명세서", path: "core/vectorstore_spec.md", format: "md", size: "480KB", date: "2026-08-02", pii: 0 }
        ]
      }
    ],
    graph: {
      nodes: [
        { id: "doc-cb01", name: "CorpBrain v0.4 아키텍처", type: "doc", val: 18, wikiId: "cb-01" },
        { id: "doc-cb02", name: "SQLite 벡터 인덱스", type: "doc", val: 16, wikiId: "cb-02" },
        { id: "ent-sqlite", name: "SQLite VectorStore", type: "entity", val: 14 },
        { id: "tag-vector", name: "#벡터인덱스", type: "tag", val: 10 }
      ],
      edges: [
        { source: "doc-cb01", target: "doc-cb02", type: "ref" },
        { source: "doc-cb02", target: "ent-sqlite", type: "entity" },
        { source: "doc-cb02", target: "tag-vector", type: "tag" }
      ]
    }
  },
  p3: {
    id: "p3",
    name: "HR-KnowledgeBase",
    branch: "main",
    tag: "기본",
    inputFolder: "./HR-KnowledgeBase/docs",
    outputFolder: "./HR-KnowledgeBase/wiki",
    stats: { wikiDocs: 12, entities: 38, graphNodes: 50, graphEdges: 98, piiMasked: 12 },
    doctor: {
      ollama: { status: "정상 가동 중", url: "http://127.0.0.1:11434", model: "qwen2.5:7b-instruct" },
      gpu: { status: "감지됨", device: "NVIDIA GeForce RTX 4090", vram: "24GB" },
      embed: { status: "준비 완료", model: "nomic-embed-text" },
      cloud: { consent: true, provider: "Anthropic Claude Haiku", status: "동의 완료" }
    },
    activities: [
      { icon: "👥", text: "2026년 복무 규정 및 평가 지침 통합 스캔", time: "3일 전 · 12개 파일 완료" }
    ],
    wikiTree: [
      {
        folder: "인사 총무 규정",
        docs: [
          { id: "hr-01", title: "재택근무 및 유연근무제 가이드라인", path: "hr/remote_work_policy.md", format: "docx", size: "1.4MB", date: "2026-08-15", pii: 2 },
          { id: "hr-02", title: "2026 연차 휴가 및 경조휴가 규정", path: "hr/annual_leave_2026.md", format: "pdf", size: "890KB", date: "2026-08-10", pii: 4 }
        ]
      }
    ],
    graph: {
      nodes: [
        { id: "doc-hr01", name: "재택근무 가이드", type: "doc", val: 18, wikiId: "hr-01" },
        { id: "doc-hr02", name: "연차 휴가 규정", type: "doc", val: 14, wikiId: "hr-02" },
        { id: "ent-hr_team", name: "인사팀", type: "entity", val: 12 }
      ],
      edges: [
        { source: "doc-hr01", target: "ent-hr_team", type: "entity" },
        { source: "doc-hr02", target: "ent-hr_team", type: "entity" }
      ]
    }
  },
  p4: {
    id: "p4",
    name: "Legal-Compliance-2026",
    branch: "v0.4-vector",
    tag: "",
    inputFolder: "./Legal-Compliance-2026/contracts",
    outputFolder: "./Legal-Compliance-2026/wiki",
    stats: { wikiDocs: 24, entities: 64, graphNodes: 88, graphEdges: 164, piiMasked: 22 },
    doctor: {
      ollama: { status: "정상 가동 중", url: "http://127.0.0.1:11434", model: "qwen2.5:7b-instruct" },
      gpu: { status: "감지됨", device: "NVIDIA GeForce RTX 4090", vram: "24GB" },
      embed: { status: "준비 완료", model: "nomic-embed-text" },
      cloud: { consent: true, provider: "Anthropic Claude Haiku", status: "동의 완료" }
    },
    activities: [
      { icon: "⚖️", text: "표준 계약서 양식 및 개인정보 처리방침 스캔", time: "5일 전 · 24개 파일 완료" }
    ],
    wikiTree: [
      {
        folder: "법무 및 계약",
        docs: [
          { id: "sec-03", title: "개인정보(PII) 처리 및 데이터 마스킹 표준", path: "security/pii_handling_standard.md", format: "docx", size: "1.8MB", date: "2026-08-05", pii: 6 }
        ]
      }
    ],
    graph: {
      nodes: [
        { id: "doc-sec03", name: "PII 마스킹 표준", type: "doc", val: 18, wikiId: "sec-03" },
        { id: "ent-sec_team", name: "정보보안팀", type: "entity", val: 14 }
      ],
      edges: [
        { source: "doc-sec03", target: "ent-sec_team", type: "entity" }
      ]
    }
  }
};

// Global Wiki Details
const WIKI_DETAILS_DB = {
  "hr-01": {
    title: "재택근무 및 유연근무제 가이드라인",
    frontmatter: { engine: "local", model: "qwen2.5:7b-instruct", generated_at: "2026-08-15 14:32:01", pii_masked: 2 },
    oneLine: "전사 임직원의 자율적 업무 몰입을 위한 주 2회 재택근무 및 코어타임 기반 유연근무제 운영 기준.",
    keyPoints: [
      "주 최대 2회까지 사전 승인 후 재택근무 신청 가능 (월/금 권장 자제)",
      "코어타임(10:00 ~ 15:00) 필수 접속 및 사내 메신저 상시 응답 유지",
      "자택 보안 환경 점검: 사내 VPN 필수 연결 및 화면 잠금 생활화",
      "신청 기한: 전주 금요일 18시까지 사내 그룹웨어 시스템 등록"
    ],
    body: `본 가이드라인은 CorpBrain 도입과 더불어 분산 업무 환경에서 업무 생산성을 극대화하고 임직원의 워라밸을 보장하기 위해 제정되었습니다.

재택근무 대상자는 입사 3개월 이상의 정규직 임직원이며, 업무 특성상 현장 대응이 필수적인 부서(시설 관리, 오프라인 보안 등)는 부서장 재량에 따라 별도 협의합니다.

신청 시 개인 연락처 및 비상연락망([PII: 휴대전화번호:001])을 최신화해야 하며, 급여 및 복리후생에 대한 문의는 인사팀([PII: 이메일:002])으로 접수 바랍니다.`,
    tags: ["인사규정", "재택근무", "유연근무", "VPN접속", "코어타임"],
    entities: ["인사팀", "사내 그룹웨어", "VPN 시스템", "보안팀"],
    relatedDocs: ["hr-02", "sec-01"]
  },
  "sec-01": {
    title: "사내 보안 인증 및 VPN 접속 가이드",
    frontmatter: { engine: "local", model: "qwen2.5:7b-instruct", generated_at: "2026-08-18 09:15:22", pii_masked: 5 },
    oneLine: "원격지에서 사내 내부망에 안전하게 접속하기 위한 2단계 OTP 인증 및 WireGuard 기반 VPN 설정 절차.",
    keyPoints: [
      "모든 외부 접속 시 전용 사내 VPN 클라이언트 및 2차 인증(OTP) 필수",
      "비인가 단말기(개인 PC) 접속 금지, 자산 등록된 보안 노트북만 허용",
      "연속 5회 이상 인증 실패 시 계정 잠금 및 정보보안팀 자동 통보",
      "공공 와이파이 이용 시 보안 프로토콜 강화 설정 적용"
    ],
    body: `외부에서 사내망 자원(GitLab, 사내 위키, 데이터베이스)에 접근하기 위해서는 사전 승인된 VPN 프로필을 설치해야 합니다.

인증 서버는 SSO와 연동되어 사내 사번 및 2단계 일회용 패스워드(OTP)를 요구합니다. 보안 담당자([PII: 이메일:003])의 승인을 받아야 키가 발급됩니다.

위반 행위 적발 시 보안 정책 규정에 의거하여 접근 권한이 즉시 회수됩니다.`,
    tags: ["정보보안", "VPN접속", "2단계인증", "OTP", "네트워크보안"],
    entities: ["정보보안팀", "VPN 서버", "SSO 게이트웨이"],
    relatedDocs: ["hr-01", "sec-03", "rnd-01"]
  },
  "rnd-01": {
    title: "CorpBrain 로컬 AI 아키텍처 명세서",
    frontmatter: { engine: "local", model: "qwen2.5:7b-instruct", generated_at: "2026-08-20 17:44:10", pii_masked: 0 },
    oneLine: "외부 데이터 유출 0%를 보장하는 단일 관문(Gateway) 기반 온디바이스 AI 지식 관리 코어 아키텍처.",
    keyPoints: [
      "비즈니스 로직은 순수 코어 라이브러리에 격리 (No-I/O)",
      "단일 게이트웨이(gateway.request_json)를 통한 외부 호출 100% 통제",
      "Ollama 기반 요약 및 nomic-embed-text 벡터 인덱싱 파이프라인 내장",
      "v0.6: 엔티티 및 토픽 관계를 시각화하는 지식그래프(Knowledge Graph) 엔진 탑재"
    ],
    body: `CorpBrain은 엔터프라이즈 환경의 지식 분산 문제를 해결하면서도 기밀 데이터 유출 위험을 원천 차단하기 위해 설계되었습니다.

문서 파싱(.docx, .pdf, .md)부터 요약, 벡터 인덱싱, 지식그래프 생성까지 전 과정을 로컬 리소스만으로 수행합니다. 클라우드 옵트인 선택 시에도 엄격한 PII 마스킹 및 단일 관문 NetworkGuard를 통과합니다.`,
    tags: ["시스템아키텍처", "로컬AI", "지식그래프", "벡터RAG", "보안게이트웨이"],
    entities: ["연구개발팀", "Ollama Engine", "VectorStore", "GraphStore"],
    relatedDocs: ["sec-01", "rnd-02", "sec-03"]
  },
  "cb-01": {
    title: "CorpBrain v0.4 아키텍처 개요",
    frontmatter: { engine: "local", model: "qwen2.5:7b-instruct", generated_at: "2026-08-01 10:00:00", pii_masked: 0 },
    oneLine: "v0.4 벡터 인덱싱과 코사인 유사도 검색을 지원하는 기본 아키텍처.",
    keyPoints: ["로컬 임베딩 파이프라인", "SQLite 기반 고속 벡터 검색"],
    body: `CorpBrain v0.4는 로컬 임베딩을 통한 벡터 인덱싱을 기본 탑재합니다.`,
    tags: ["아키텍처", "벡터검색"],
    entities: ["Ollama", "SQLite"],
    relatedDocs: ["cb-02"]
  },
  "sec-03": {
    title: "개인정보(PII) 처리 및 데이터 마스킹 표준",
    frontmatter: { engine: "local", model: "qwen2.5:7b-instruct", generated_at: "2026-08-05 16:20:00", pii_masked: 6 },
    oneLine: "사내 7대 개인정보 패턴에 대한 자동 탐지 및 마스킹 보안 표준.",
    keyPoints: ["한국 특화 7종 PII 마스킹", "NetworkGuard 목적지 통제"],
    body: `본 문서는 클라우드 전송 전 수행되는 마스킹 규칙을 정의합니다.`,
    tags: ["개인정보보호", "PII", "보안표준"],
    entities: ["정보보안팀", "NetworkGuard"],
    relatedDocs: ["sec-01"]
  }
};

// --- App State ---
const AppState = {
  currentProject: "p1",
  currentView: "dashboard",
  selectedWikiId: "hr-01",
  selectedNode: null,
  isScanning: false,
  scanProgress: 0,
  cloudConsent: true
};

// --- Startup Initializer ---
document.addEventListener("DOMContentLoaded", () => {
  initProjectNavigation();
  initTopTabsNavigation();
  initDashboard();
  initScanHub();
  initGraphCanvas();
  initWikiReader();
  initHybridSearch();
  initSettings();
});

// --- 1. Multi-Project Workspace Switcher (Sidebar) ---
function initProjectNavigation() {
  const projectCards = document.querySelectorAll(".project-card-item");
  const projectSearch = document.getElementById("project-search-input");
  const btnAddFolder = document.getElementById("btn-add-folder");
  const btnAddProject = document.getElementById("btn-add-project");

  projectCards.forEach(card => {
    card.addEventListener("click", () => {
      const pid = card.getAttribute("data-project-id");
      if (pid && MULTI_PROJECTS[pid]) {
        switchProject(pid);
      }
    });
  });

  if (projectSearch) {
    projectSearch.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll(".project-card-item").forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? "flex" : "none";
      });
    });
  }

  const handleAdd = () => {
    const folderName = prompt("새로 추가할 로컬 프로젝트/폴더명을 입력하세요:", "New-Project-2026");
    if (folderName) {
      alert(`📁 '${folderName}' 폴더가 워크스페이스에 등록되었습니다.\n상단 '플랜 & 스캔' 탭에서 인덱싱을 진행해 주세요.`);
    }
  };

  if (btnAddFolder) btnAddFolder.addEventListener("click", handleAdd);
  if (btnAddProject) btnAddProject.addEventListener("click", handleAdd);
}

function switchProject(pid) {
  AppState.currentProject = pid;
  const project = MULTI_PROJECTS[pid];

  // Update Sidebar active card
  document.querySelectorAll(".project-card-item").forEach(card => {
    card.classList.toggle("active", card.getAttribute("data-project-id") === pid);
  });

  // Update Top Header Workspace Title & Branch
  document.getElementById("current-project-title").textContent = project.name;
  document.getElementById("current-project-branch").textContent = project.branch;

  // Update Tab Badges
  document.getElementById("tab-badge-wiki").textContent = project.stats.wikiDocs;

  // Update Scan Inputs
  const inFolder = document.getElementById("scan-input-folder");
  const outFolder = document.getElementById("scan-output-folder");
  if (inFolder && outFolder) {
    inFolder.value = project.inputFolder;
    outFolder.value = project.outputFolder;
  }

  // Update Dashboard Stats & Activity
  initDashboard();

  // Update Wiki Tree & Reader
  initWikiReader();

  // Re-render Graph Canvas
  if (window.updateGraphDataset) {
    window.updateGraphDataset(project.graph);
  }
}

// --- 2. Top Horizontal Tabs & Global Settings Navigation ---
function initTopTabsNavigation() {
  const tabItems = document.querySelectorAll(".tab-item");
  const globalNavItem = document.querySelector(".global-nav-item");
  const viewContents = document.querySelectorAll(".view-content");

  tabItems.forEach(tab => {
    tab.addEventListener("click", () => {
      const view = tab.getAttribute("data-view");
      switchView(view);
    });
  });

  if (globalNavItem) {
    globalNavItem.addEventListener("click", () => {
      switchView("settings");
    });
  }

  window.switchView = function(viewName) {
    AppState.currentView = viewName;
    
    // Toggle active on top tabs
    tabItems.forEach(t => t.classList.toggle("active", t.getAttribute("data-view") === viewName));
    
    // Toggle active on global settings
    if (globalNavItem) {
      globalNavItem.classList.toggle("active", viewName === "settings");
    }

    // Toggle view contents
    viewContents.forEach(v => v.classList.toggle("active", v.id === `view-${viewName}`));

    if (viewName === "graph" && window.resizeGraphCanvas) {
      window.resizeGraphCanvas();
    }
  };
}

// --- 3. Dashboard Initializer ---
function initDashboard() {
  const project = MULTI_PROJECTS[AppState.currentProject];

  document.getElementById("metric-wiki-count").textContent = project.stats.wikiDocs;
  document.getElementById("metric-entity-count").textContent = project.stats.entities;
  document.getElementById("metric-graph-count").textContent = `${project.stats.graphNodes} / ${project.stats.graphEdges}`;
  document.getElementById("metric-pii-count").textContent = project.stats.piiMasked;

  const actList = document.getElementById("dashboard-activity-list");
  if (actList) {
    actList.innerHTML = project.activities.map(a => `
      <div class="activity-item">
        <div class="activity-icon">${a.icon}</div>
        <div class="activity-info">
          <div class="activity-text">${a.text}</div>
          <div class="activity-time">${a.time}</div>
        </div>
      </div>
    `).join("");
  }

  const quickContainer = document.getElementById("quick-wiki-container");
  if (quickContainer) {
    quickContainer.innerHTML = "";
    const docs = project.wikiTree[0]?.docs || [];
    docs.slice(0, 4).forEach(d => {
      const fullDoc = WIKI_DETAILS_DB[d.id] || { oneLine: "로컬 문서 요약 정보", tags: ["문서"] };
      const card = document.createElement("div");
      card.className = "quick-wiki-card";
      card.innerHTML = `
        <div class="quick-wiki-title">${d.title}</div>
        <div class="quick-wiki-snippet">${fullDoc.oneLine}</div>
        <div class="tag-list">
          ${fullDoc.tags.slice(0, 3).map(t => `<span class="tag-badge">#${t}</span>`).join("")}
        </div>
      `;
      card.addEventListener("click", () => {
        AppState.selectedWikiId = d.id;
        renderWikiDetail(d.id);
        switchView("wiki");
      });
      quickContainer.appendChild(card);
    });
  }
}

// --- 4. Plan & Scan Hub ---
function initScanHub() {
  const btnPlan = document.getElementById("btn-run-plan");
  const btnScan = document.getElementById("btn-run-scan");
  const planReportCard = document.getElementById("plan-report-card");
  const scanProgressCard = document.getElementById("scan-progress-card");
  const logStream = document.getElementById("scan-log-stream");
  const progressFill = document.getElementById("scan-progress-fill");
  const progressPercent = document.getElementById("scan-progress-percent");

  btnPlan.addEventListener("click", () => {
    planReportCard.style.display = "block";
    scanProgressCard.style.display = "none";
    planReportCard.scrollIntoView({ behavior: "smooth" });
  });

  btnScan.addEventListener("click", () => {
    if (AppState.isScanning) return;
    AppState.isScanning = true;
    btnScan.disabled = true;
    scanProgressCard.style.display = "block";
    logStream.innerHTML = "";
    AppState.scanProgress = 0;

    const files = [
      { name: "hr/remote_work_policy.docx", size: "1.4MB", est: 4200 },
      { name: "hr/annual_leave_2026.pdf", size: "890KB", est: 2800 },
      { name: "security/vpn_access_guide.pdf", size: "3.2MB", est: 8500 },
      { name: "security/pii_handling_standard.docx", size: "1.8MB", est: 5100 },
      { name: "rnd/corpbain_arch_spec.md", size: "1.1MB", est: 3900 }
    ];

    let fileIdx = 0;
    addLog("시스템", `[${MULTI_PROJECTS[AppState.currentProject].name}] 사전 환경 진단(GPU, Ollama, Embedding) 검증 완료`, "stage-done");

    const interval = setInterval(() => {
      if (fileIdx >= files.length) {
        clearInterval(interval);
        AppState.isScanning = false;
        btnScan.disabled = false;
        progressFill.style.width = "100%";
        progressPercent.textContent = "100%";
        addLog("완료", "총 5개 파일 스캔 완료: 5개 위키 생성, 벡터 인덱싱 및 지식그래프 갱신 완료", "stage-done");
        return;
      }

      const f = files[fileIdx];
      AppState.scanProgress = Math.round(((fileIdx + 1) / files.length) * 100);
      progressFill.style.width = `${AppState.scanProgress}%`;
      progressPercent.textContent = `${AppState.scanProgress}%`;

      addLog(f.name, "텍스트 추출 완료 (" + f.size + ")", "stage-extract");
      setTimeout(() => addLog(f.name, "Ollama 요약 완료 (예상 토큰 " + f.est + "t)", "stage-summarize"), 200);
      setTimeout(() => addLog(f.name, "PII 검사 및 마스킹 적용 완료", "stage-pii"), 400);
      setTimeout(() => addLog(f.name, "벡터 임베딩 및 지식그래프 노드/엣지 연결 완료", "stage-embed"), 600);

      fileIdx++;
    }, 900);
  });

  function addLog(source, message, stageClass) {
    const time = new Date().toTimeString().split(" ")[0];
    const el = document.createElement("div");
    el.className = `log-entry ${stageClass}`;
    el.innerHTML = `<span class="time">[${time}]</span> <strong>[${source}]</strong> ${message}`;
    logStream.appendChild(el);
    logStream.scrollTop = logStream.scrollHeight;
  }
}

// --- 5. Interactive Force-Directed Knowledge Graph Canvas ---
function initGraphCanvas() {
  const canvas = document.getElementById("graph-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const inspector = document.getElementById("graph-inspector-panel");

  let width, height;
  let transform = { x: 0, y: 0, k: 1 };
  let isDragging = false;
  let dragNode = null;
  let startX, startY;
  let hoveredNode = null;

  let nodes = [];
  let edges = [];

  function loadDataset(graphData) {
    nodes = (graphData.nodes || []).map(n => ({
      ...n,
      x: (Math.random() - 0.5) * 400,
      y: (Math.random() - 0.5) * 400,
      vx: 0,
      vy: 0,
      radius: n.type === "doc" ? 14 : (n.type === "entity" ? 11 : 8)
    }));

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    edges = (graphData.edges || []).map(e => ({
      ...e,
      sourceNode: nodeMap.get(e.source),
      targetNode: nodeMap.get(e.target)
    })).filter(e => e.sourceNode && e.targetNode);

    const docCount = nodes.filter(n => n.type === "doc").length;
    const entCount = nodes.filter(n => n.type === "entity").length;
    const tagCount = nodes.filter(n => n.type === "tag").length;
    document.getElementById("legend-doc-count").textContent = `문서 노드 (${docCount})`;
    document.getElementById("legend-entity-count").textContent = `엔티티 노드 (${entCount})`;
    document.getElementById("legend-tag-count").textContent = `분류 태그 (${tagCount})`;
  }

  window.updateGraphDataset = loadDataset;
  loadDataset(MULTI_PROJECTS[AppState.currentProject].graph);

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    width = canvas.width = rect.width;
    height = canvas.height = rect.height;
    if (transform.x === 0 && transform.y === 0) {
      transform.x = width / 2;
      transform.y = height / 2;
    }
  }

  window.resizeGraphCanvas = resize;
  window.addEventListener("resize", resize);
  resize();

  function stepPhysics() {
    nodes.forEach(n => {
      n.vx -= n.x * 0.002;
      n.vy -= n.y * 0.002;
    });

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < 220) {
          const force = (220 - dist) / dist * 0.45;
          a.vx -= dx * force * 0.05;
          a.vy -= dy * force * 0.05;
          b.vx += dx * force * 0.05;
          b.vy += dy * force * 0.05;
        }
      }
    }

    edges.forEach(e => {
      const a = e.sourceNode;
      const b = e.targetNode;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const targetDist = e.type === "ref" ? 90 : 70;
      const force = (dist - targetDist) * 0.015;
      a.vx += dx / dist * force;
      a.vy += dy / dist * force;
      b.vx -= dx / dist * force;
      b.vy += dy / dist * force;
    });

    nodes.forEach(n => {
      if (n === dragNode) return;
      n.vx *= 0.88;
      n.vy *= 0.88;
      n.x += n.vx;
      n.y += n.vy;
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    edges.forEach(e => {
      const isConnected = hoveredNode && (e.sourceNode === hoveredNode || e.targetNode === hoveredNode);
      ctx.beginPath();
      ctx.moveTo(e.sourceNode.x, e.sourceNode.y);
      ctx.lineTo(e.targetNode.x, e.targetNode.y);

      if (e.type === "ref") {
        ctx.strokeStyle = isConnected ? "#00f2fe" : "rgba(0, 242, 254, 0.3)";
        ctx.lineWidth = isConnected ? 2.5 : 1.2;
        ctx.setLineDash([]);
      } else if (e.type === "entity") {
        ctx.strokeStyle = isConnected ? "#f59e0b" : "rgba(245, 158, 11, 0.25)";
        ctx.lineWidth = isConnected ? 2 : 1;
        ctx.setLineDash([]);
      } else {
        ctx.strokeStyle = isConnected ? "#a855f7" : "rgba(168, 85, 247, 0.2)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
      }
      ctx.stroke();
    });
    ctx.setLineDash([]);

    nodes.forEach(n => {
      const isHovered = n === hoveredNode;
      const isSelected = AppState.selectedNode && AppState.selectedNode.id === n.id;

      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius * (isHovered ? 1.25 : 1), 0, Math.PI * 2);

      let fill = "#00f2fe";
      if (n.type === "doc") {
        fill = "#00f2fe";
        ctx.shadowColor = "#00f2fe";
      } else if (n.type === "entity") {
        fill = "#f59e0b";
        ctx.shadowColor = "#f59e0b";
      } else {
        fill = "#a855f7";
        ctx.shadowColor = "#a855f7";
      }

      ctx.shadowBlur = (isHovered || isSelected) ? 16 : 6;
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.lineWidth = isSelected ? 3 : 1.5;
      ctx.strokeStyle = isSelected ? "#ffffff" : "rgba(255, 255, 255, 0.4)";
      ctx.stroke();

      ctx.font = `${isHovered ? "bold 12px" : "11px"} Pretendard, sans-serif`;
      ctx.fillStyle = isHovered ? "#ffffff" : "#cbd5e1";
      ctx.textAlign = "center";
      ctx.fillText(n.name, n.x, n.y + n.radius + 14);
    });

    ctx.restore();

    stepPhysics();
    requestAnimationFrame(render);
  }

  render();

  function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - transform.x) / transform.k,
      y: (e.clientY - rect.top - transform.y) / transform.k,
      screenX: e.clientX,
      screenY: e.clientY
    };
  }

  function findNodeAt(x, y) {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy <= (n.radius + 6) * (n.radius + 6)) {
        return n;
      }
    }
    return null;
  }

  canvas.addEventListener("mousedown", (e) => {
    const pos = getMousePos(e);
    const node = findNodeAt(pos.x, pos.y);
    if (node) {
      dragNode = node;
      AppState.selectedNode = node;
      openInspector(node);
    } else {
      isDragging = true;
      startX = e.clientX - transform.x;
      startY = e.clientY - transform.y;
    }
  });

  canvas.addEventListener("mousemove", (e) => {
    const pos = getMousePos(e);
    if (dragNode) {
      dragNode.x = pos.x;
      dragNode.y = pos.y;
      dragNode.vx = dragNode.vy = 0;
    } else if (isDragging) {
      transform.x = e.clientX - startX;
      transform.y = e.clientY - startY;
    } else {
      hoveredNode = findNodeAt(pos.x, pos.y);
      canvas.style.cursor = hoveredNode ? "pointer" : "default";
    }
  });

  window.addEventListener("mouseup", () => {
    dragNode = null;
    isDragging = false;
  });

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newK = Math.min(Math.max(0.3, transform.k * zoomFactor), 3);
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    transform.x = mouseX - (mouseX - transform.x) * (newK / transform.k);
    transform.y = mouseY - (mouseY - transform.y) * (newK / transform.k);
    transform.k = newK;
  });

  function openInspector(node) {
    inspector.classList.add("open");
    document.getElementById("inspector-node-type").textContent = node.type.toUpperCase();
    document.getElementById("inspector-node-title").textContent = node.name;

    const wikiDoc = node.wikiId ? WIKI_DETAILS_DB[node.wikiId] : null;
    const summaryEl = document.getElementById("inspector-summary-text");
    const openWikiBtn = document.getElementById("btn-open-wiki-from-graph");

    if (wikiDoc) {
      summaryEl.textContent = wikiDoc.oneLine;
      openWikiBtn.style.display = "inline-flex";
      openWikiBtn.onclick = () => {
        AppState.selectedWikiId = node.wikiId;
        renderWikiDetail(node.wikiId);
        switchView("wiki");
      };
    } else {
      summaryEl.textContent = `엔티티/태그 노드입니다. 관련된 문서 및 엔티티들과 연결되어 있습니다. (가중치: ${node.val})`;
      openWikiBtn.style.display = "none";
    }

    const listEl = document.getElementById("inspector-connected-list");
    listEl.innerHTML = "";
    const connected = edges.filter(e => e.sourceNode === node || e.targetNode === node);
    connected.forEach(e => {
      const other = e.sourceNode === node ? e.targetNode : e.sourceNode;
      const item = document.createElement("div");
      item.className = "connected-node-item";
      item.innerHTML = `<span>${other.name}</span> <span class="badge-status pass">${e.type}</span>`;
      item.onclick = () => openInspector(other);
      listEl.appendChild(item);
    });
  }

  document.getElementById("btn-close-inspector").onclick = () => {
    inspector.classList.remove("open");
  };

  document.getElementById("btn-zoom-in").onclick = () => { transform.k = Math.min(3, transform.k * 1.2); };
  document.getElementById("btn-zoom-out").onclick = () => { transform.k = Math.max(0.3, transform.k * 0.8); };
  document.getElementById("btn-zoom-reset").onclick = () => {
    transform = { x: width / 2, y: height / 2, k: 1 };
  };
}

// --- 6. Wiki Reader Initializer ---
function initWikiReader() {
  const treeContainer = document.getElementById("wiki-tree-container");
  if (!treeContainer) return;
  treeContainer.innerHTML = "";

  const project = MULTI_PROJECTS[AppState.currentProject];
  const tree = project.wikiTree || [];

  tree.forEach(folderGroup => {
    const groupEl = document.createElement("div");
    groupEl.className = "tree-group";
    groupEl.innerHTML = `<div class="tree-folder-title">📁 ${folderGroup.folder}</div>`;

    const ul = document.createElement("ul");
    ul.className = "tree-list";

    folderGroup.docs.forEach(d => {
      const li = document.createElement("li");
      li.className = `tree-item ${d.id === AppState.selectedWikiId ? "active" : ""}`;
      li.innerHTML = `<span>📄</span> <span>${d.title}</span>`;
      li.onclick = () => {
        document.querySelectorAll(".tree-item").forEach(el => el.classList.remove("active"));
        li.classList.add("active");
        AppState.selectedWikiId = d.id;
        renderWikiDetail(d.id);
      };
      ul.appendChild(li);
    });

    groupEl.appendChild(ul);
    treeContainer.appendChild(groupEl);
  });

  const firstDocId = tree[0]?.docs[0]?.id || "hr-01";
  AppState.selectedWikiId = firstDocId;
  renderWikiDetail(firstDocId);
}

function renderWikiDetail(wikiId) {
  const doc = WIKI_DETAILS_DB[wikiId] || WIKI_DETAILS_DB["hr-01"];
  const mainEl = document.getElementById("wiki-reader-content");
  if (!mainEl) return;

  mainEl.innerHTML = `
    <div class="wiki-frontmatter-box">
      <div class="frontmatter-badge">엔진: <strong>${doc.frontmatter.engine}</strong></div>
      <div class="frontmatter-badge">모델: <strong>${doc.frontmatter.model}</strong></div>
      <div class="frontmatter-badge">생성일: <strong>${doc.frontmatter.generated_at}</strong></div>
      <div class="frontmatter-badge">PII 마스킹: <strong style="color:var(--accent-amber)">${doc.frontmatter.pii_masked}건</strong></div>
    </div>

    <div class="wiki-document-body">
      <h1>${doc.title}</h1>
      
      <h2>📌 한 줄 핵심 요약</h2>
      <p style="font-size:15px; font-weight:600; color:var(--accent-cyan);">${doc.oneLine}</p>

      <h2>📋 핵심 포인트 (Key Points)</h2>
      <div class="key-points-box">
        <ul>
          ${doc.keyPoints.map(p => `<li>${p}</li>`).join("")}
        </ul>
      </div>

      <h2>📝 상세 요약 본문</h2>
      <p>${doc.body.replace(/\n\n/g, "</p><p>")}</p>

      <h2>🏷️ 연관 태그 & 엔티티</h2>
      <div class="tag-list" style="margin-top:10px;">
        ${doc.tags.map(t => `<span class="tag-badge">#${t}</span>`).join("")}
        ${doc.entities.map(e => `<span class="tag-badge" style="background:rgba(245,158,11,0.15); color:var(--accent-amber); border-color:rgba(245,158,11,0.3)">@${e}</span>`).join("")}
      </div>
    </div>
  `;
}

// --- 7. Hybrid Search Initializer ---
function initHybridSearch() {
  const searchInput = document.getElementById("hybrid-search-input");
  const resultsContainer = document.getElementById("hybrid-search-results");

  const mockSearchResults = [
    {
      id: "hr-01",
      title: "재택근무 및 유연근무제 가이드라인",
      score: "94.8%",
      snippet: "주 최대 2회까지 사전 승인 후 재택근무 신청 가능하며, 코어타임(10:00 ~ 15:00) 필수 접속 및 사내 VPN 연결이 요구됩니다.",
      tags: ["재택근무", "유연근무", "코어타임"]
    },
    {
      id: "sec-01",
      title: "사내 보안 인증 및 VPN 접속 가이드",
      score: "89.2%",
      snippet: "원격지에서 사내 내부망에 안전하게 접속하기 위한 2단계 OTP 인증 및 WireGuard 기반 VPN 설정 절차를 안내합니다.",
      tags: ["정보보안", "VPN접속", "2단계인증"]
    },
    {
      id: "rnd-01",
      title: "CorpBrain 로컬 AI 아키텍처 명세서",
      score: "82.5%",
      snippet: "비즈니스 로직은 순수 코어 라이브러리에 격리하며, 단일 게이트웨이와 지식그래프 엔진을 통해 안전한 지식 관리를 수행합니다.",
      tags: ["시스템아키텍처", "로컬AI", "지식그래프"]
    }
  ];

  function renderSearchResults(query = "") {
    resultsContainer.innerHTML = "";
    mockSearchResults.forEach(res => {
      const card = document.createElement("div");
      card.className = "search-result-card";
      card.innerHTML = `
        <div class="search-result-header">
          <div class="result-title">${res.title}</div>
          <div class="similarity-badge">코사인 유사도 ${res.score}</div>
        </div>
        <div class="result-snippet">${res.snippet}</div>
        <div class="result-footer">
          <div class="tag-list">
            ${res.tags.map(t => `<span class="tag-badge">#${t}</span>`).join("")}
          </div>
          <button class="btn btn-outline btn-sm">🕸️ 지식그래프에서 보기</button>
        </div>
      `;

      card.querySelector(".btn-outline").onclick = (e) => {
        e.stopPropagation();
        switchView("graph");
      };

      card.onclick = () => {
        AppState.selectedWikiId = res.id;
        renderWikiDetail(res.id);
        switchView("wiki");
      };

      resultsContainer.appendChild(card);
    });
  }

  renderSearchResults();

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      renderSearchResults(e.target.value);
    });
  }

  document.querySelectorAll(".suggestion-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = chip.textContent;
        renderSearchResults(chip.textContent);
      }
    });
  });
}

// --- 8. Settings & Governance Initializer ---
function initSettings() {
  const consentToggle = document.getElementById("cloud-consent-toggle");
  const consentStatus = document.getElementById("cloud-consent-status");
  const piiInput = document.getElementById("pii-test-input");
  const piiOutput = document.getElementById("pii-test-output");

  if (consentToggle) {
    consentToggle.addEventListener("change", (e) => {
      AppState.cloudConsent = e.target.checked;
      consentStatus.textContent = e.target.checked ? "동의 부여됨 (Granted)" : "동의 철회됨 (Revoked)";
      consentStatus.style.color = e.target.checked ? "var(--accent-emerald)" : "var(--accent-rose)";
    });
  }

  if (piiInput && piiOutput) {
    const maskPII = (text) => {
      let res = text;
      res = res.replace(/\b(\d{6})[- ]?([1-4]\d{6})\b/g, "[PII: 주민등록번호:***]");
      res = res.replace(/\b(01[016789])[- ]?(\d{3,4})[- ]?(\d{4})\b/g, "[PII: 휴대전화번호:***]");
      res = res.replace(/\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b/g, "[PII: 이메일:***]");
      res = res.replace(/\b(\d{3})[- ]?(\d{2})[- ]?(\d{5})\b/g, "[PII: 사업자번호:***]");
      res = res.replace(/\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b/g, "[PII: 카드번호:***]");
      return res;
    };

    piiInput.addEventListener("input", (e) => {
      piiOutput.value = maskPII(e.target.value);
    });
  }
}
