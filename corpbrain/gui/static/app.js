/* CorpBrain GUI 프론트엔드 (v0.9 스펙 §4.10.4).
 *
 * **URL 해시가 화면 상태의 단일 출처다.** 화면 전환은 해시를 바꾸는 것으로만 일어나고 뷰
 * 전환 함수를 직접 부르지 않는다 — 그래야 해시와 화면이 어긋나지 않는다. `pushState`를 쓰지
 * 않는 이유는 서버가 모르는 경로 전부에서 index를 내주는 SPA fallback이 필요해져 404 처리
 * 규칙과 섞이기 때문이다. 해시는 서버로 전송되지 않으므로 라우팅을 한 줄도 건드리지 않는다.
 *
 * 마크다운 파서를 두지 않는다 (§4.6) — 서버가 구조화해 내려준 필드만 그린다.
 */

'use strict';

const VIEWS = [
  { id: 'dashboard', label: '대시보드', subtitle: '환경 준비 상태와 지식그래프 규모' },
  { id: 'scan', label: '플랜 & 스캔', subtitle: '계량 → 확인 → 실행' },
  { id: 'wiki', label: '위키 탐색기', subtitle: '생성된 문서 트리와 상세' },
  { id: 'graph', label: '지식그래프', subtitle: '문서·엔티티·태그의 연결' },
  { id: 'search', label: '지식 검색', subtitle: '코사인 + 그래프 확산' },
  { id: 'settings', label: '설정', subtitle: '엔진·클라우드 동의·마스킹' },
];

const DEFAULT_VIEW = 'dashboard';

/** 아직 구현되지 않은 화면의 빈 상태 (§5 — 탭을 잠그거나 강제 이동시키지 않는다). */
const PENDING_VIEWS = {
  scan: '스캔 화면은 다음 슬라이스에서 붙습니다.',
  wiki: '위키 탐색기는 다음 슬라이스에서 붙습니다.',
  graph: '지식그래프 화면은 다음 슬라이스에서 붙습니다.',
  search: '검색 화면은 다음 슬라이스에서 붙습니다.',
  settings: '설정 화면은 다음 슬라이스에서 붙습니다.',
};

/* --- 부트스트랩 -------------------------------------------------------------- */

/**
 * URL에서 부트스트랩 토큰을 지운다 (§4.2 · T6).
 *
 * 이 페이지를 받아 온 요청이 이미 세션 쿠키를 받았으므로 쿼리는 더 필요 없다. 남겨 두면
 * 토큰이 브라우저 히스토리·리퍼러에 계속 실린다. 해시는 건드리지 않는다 — 화면 상태의
 * 단일 출처라 층이 다르다 (§4.10.4).
 */
function stripBootstrapToken() {
  if (!window.location.search) return;
  const url = new URL(window.location.href);
  url.search = '';
  window.history.replaceState(null, '', url.toString());
}

/* --- 라우팅 (§4.10.4) --------------------------------------------------------- */

/** `#/graph?node=…` → `{ view: 'graph', params: URLSearchParams }`. */
function currentRoute() {
  const raw = window.location.hash.replace(/^#\/?/, '');
  const [path, query] = raw.split('?');
  const view = VIEWS.some((entry) => entry.id === path) ? path : DEFAULT_VIEW;
  return { view, params: new URLSearchParams(query || '') };
}

function navigate(view) {
  window.location.hash = `#/${view}`;
}

/* --- 서버 호출 ---------------------------------------------------------------- */

/**
 * JSON 엔드포인트 하나를 부른다.
 *
 * 쿠키는 `fetch`와 `EventSource`가 자동으로 함께 나른다 — 인증 경로가 하나로 유지되는
 * 이유다 (§4.2). 도메인 상태는 200 + `{error, message}`로 오므로 상태코드로 분기하지
 * 않고 본문의 `error` 유무로 가른다 (§4.3.2).
 */
async function getJson(path) {
  const response = await fetch(path, { credentials: 'same-origin' });
  if (response.status === 401 || response.status === 403) {
    return { error: 'Unauthorized', message: '세션이 만료되었습니다. 서버를 다시 띄우고 새 URL로 접속하세요.' };
  }
  try {
    return await response.json();
  } catch (_err) {
    return { error: 'InvalidResponse', message: '서버 응답을 해석하지 못했습니다.' };
  }
}

function isError(section) {
  return Boolean(section) && typeof section.error === 'string';
}

/**
 * 진행 스트림에 붙는다 (§4.3).
 *
 * `EventSource`는 커스텀 헤더를 붙일 수 없다 — 인증이 세션 쿠키인 이유이며, 쿠키는
 * 자동으로 함께 나가므로 여기에 인증 코드가 없다 (§4.2).
 *
 * 끊기면 브라우저가 알아서 재연결하고, 서버는 접속 즉시 현재 스냅샷을 한 번 보낸다.
 * 그래서 클라이언트가 놓친 이벤트를 되감을 필요가 없다 — 리플레이 버퍼가 없는 이유다.
 */
function connectEvents(onFrame) {
  const source = new EventSource('/api/events');
  source.addEventListener('message', (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (_err) {
      return; // keepalive 주석은 여기까지 오지 않지만, 깨진 프레임에 화면이 죽지 않게 둔다
    }
    onFrame(payload);
  });
  return source;
}

/* --- DOM 헬퍼 ----------------------------------------------------------------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/**
 * 빈 상태 카드 (§5).
 *
 * 화면마다 다른 규칙을 만들지 않는다 — 「비었지만 유효한 상태」와 「첫 실행」을 가르는 판정을
 * 늘리지 않기 위해 탭을 잠그거나 스캔 화면으로 강제 이동시키지도 않는다.
 */
function emptyState({ title, body, detail, actionLabel, actionView }) {
  const box = el('div', 'empty');
  box.appendChild(el('div', 'empty-title', title));
  box.appendChild(el('p', 'empty-body', body));
  if (detail) box.appendChild(el('div', 'empty-detail', detail));
  if (actionLabel) {
    const button = el('button', 'btn btn-primary', actionLabel);
    button.type = 'button';
    button.addEventListener('click', () => navigate(actionView));
    box.appendChild(button);
  }
  return box;
}

/* --- 사이드바 ----------------------------------------------------------------- */

function renderNav(activeView) {
  const nav = document.getElementById('nav');
  clear(nav);
  for (const entry of VIEWS) {
    // 클릭 가능한 요소는 전부 키보드로 닿아야 한다 — `<button>`이면 기본으로 닿는다 (§4.10.5).
    const item = el('button', 'nav-item', entry.label);
    item.type = 'button';
    item.setAttribute('role', 'listitem');
    if (entry.id === activeView) item.setAttribute('aria-current', 'page');
    item.addEventListener('click', () => navigate(entry.id));
    nav.appendChild(item);
  }
}

/* --- 화면 -------------------------------------------------------------------- */

async function renderDashboard(content) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const body = await getJson('/api/dashboard');
  clear(content);
  if (isError(body)) {
    content.appendChild(
      emptyState({ title: '대시보드를 불러오지 못했습니다', body: body.message })
    );
    return;
  }
  setWorkspacePath(body.out_dir);
  const grid = el('div', 'bento');
  const runCard = el('div', 'card');
  grid.appendChild(runCard);
  grid.appendChild(doctorCard(body.doctor));
  grid.appendChild(graphCard(body.graph, body.out_dir));
  content.appendChild(grid);
  renderRunCard(runCard, null);
  openStream((payload) => renderRunCard(runCard, payload));
}

/** 현재 화면이 쥐고 있는 SSE 연결. 화면을 떠날 때 반드시 닫는다. */
let activeStream = null;

function closeStream() {
  if (activeStream !== null) {
    activeStream.close();
    activeStream = null;
  }
}

function openStream(onFrame) {
  closeStream();
  activeStream = connectEvents(onFrame);
}

/** 마지막으로 받은 스냅샷 — 이벤트 프레임은 스냅샷을 통째로 주지 않으므로 함께 들고 있는다. */
let lastSnapshot = null;
let lastRunning = false;

function renderRunCard(card, payload) {
  if (payload !== null) {
    if (payload.kind === 'snapshot') {
      lastSnapshot = payload.snapshot;
      lastRunning = payload.running;
    } else {
      // 이벤트 프레임은 「무엇이 일어났는가」다. 집계는 서버가 접어 둔 스냅샷이 소유하므로
      // 여기서는 지금 무엇을 하고 있는지만 갱신한다 — 프론트에 reduce()를 두 벌로 두지 않는다.
      lastRunning = payload.kind !== 'run_finished';
      lastSnapshot = Object.assign({}, lastSnapshot || {}, describeEvent(payload));
    }
  }
  clear(card);
  card.appendChild(el('div', 'card-title', '실행 상태'));
  if (lastSnapshot === null) {
    card.appendChild(el('div', 'metric-number', '대기 중'));
    card.appendChild(el('p', 'metric-caption', '진행 중인 스캔이 없습니다.'));
    return;
  }
  const done = (lastSnapshot.generated || 0) + (lastSnapshot.skipped || 0);
  card.appendChild(el('div', 'metric-number', `${done} / ${lastSnapshot.total || 0}`));
  card.appendChild(el('p', 'metric-caption', lastRunning ? '진행 중' : '완료'));
  card.appendChild(countRow('생성', lastSnapshot.generated || 0));
  card.appendChild(countRow('스킵', lastSnapshot.skipped || 0));
  if (lastSnapshot.graph_stage) {
    card.appendChild(countRow('그래프 단계', lastSnapshot.graph_stage));
  }
  if (lastSnapshot.current_file) {
    card.appendChild(el('p', 'metric-caption', lastSnapshot.current_file));
  }
}

/** 이벤트 하나에서 화면이 바로 쓰는 필드만 뽑는다. */
function describeEvent(payload) {
  const patch = {};
  if (typeof payload.path === 'string') patch.current_file = payload.path;
  if (payload.kind === 'graph_started') patch.graph_stage = 'building';
  if (payload.kind === 'related_injected') patch.graph_stage = 'injecting';
  if (payload.kind === 'graph_finished') patch.graph_stage = 'done';
  return patch;
}

function badge(kind, label) {
  return el('span', `badge-status ${kind}`, label);
}

function checkRow(name, ok, detail, { warnOnly = false } = {}) {
  const row = el('div', 'check-row');
  const left = el('div', 'check-name', name);
  const right = el('div', 'check-row');
  if (detail) right.appendChild(el('span', 'check-detail', detail));
  right.appendChild(
    ok ? badge('pass', '준비됨') : badge(warnOnly ? 'warn' : 'fail', warnOnly ? '경고' : '미설정')
  );
  row.appendChild(left);
  row.appendChild(right);
  return row;
}

function doctorCard(doctor) {
  const card = el('div', 'card');
  card.appendChild(el('div', 'card-title', '환경 점검'));
  if (isError(doctor)) {
    card.appendChild(el('p', 'metric-caption', doctor.message));
    return card;
  }
  card.appendChild(checkRow('Ollama 설치', doctor.installed));
  card.appendChild(checkRow('Ollama 구동', doctor.running));
  card.appendChild(checkRow('요약 모델', doctor.model_present, doctor.model));
  card.appendChild(checkRow('임베딩 모델', doctor.embed_model_present, doctor.embed_model));
  card.appendChild(
    checkRow('GPU', doctor.hardware.gpu, doctor.hardware.label, { warnOnly: true })
  );
  card.appendChild(checkRow('클라우드 동의', doctor.cloud_consent, null, { warnOnly: true }));
  card.appendChild(checkRow('ANTHROPIC_API_KEY', doctor.cloud_api_key, null, { warnOnly: true }));
  return card;
}

function graphCard(graph, outDir) {
  const card = el('div', 'card');
  card.appendChild(el('div', 'card-title', '지식그래프'));
  if (isError(graph)) {
    // 첫 실행에 그래프 DB가 없는 것은 정상이다 — 카드가 자기 빈 상태를 그리고 스캔 화면으로
    // 보낸다. 탭을 잠그거나 강제 이동시키지 않는다 (§5).
    card.appendChild(el('p', 'metric-caption', graph.message));
    const button = el('button', 'btn', '플랜 & 스캔으로');
    button.type = 'button';
    button.addEventListener('click', () => navigate('scan'));
    card.appendChild(button);
    return card;
  }
  card.appendChild(el('div', 'metric-number', `${graph.nodes} / ${graph.edges}`));
  card.appendChild(el('p', 'metric-caption', '노드 / 엣지'));
  card.appendChild(countRow('문서', graph.documents));
  card.appendChild(countRow('엔티티', graph.entities));
  card.appendChild(countRow('태그', graph.tags));
  for (const [type, count] of Object.entries(graph.edges_by_type || {})) {
    // 엣지 종류 이름은 코어 `EdgeType` 값을 **그대로** 쓴다 — 프론트가 자기 리터럴을 가지면
    // `graph --stats` 출력·DB의 type 컬럼·`--expand-edges` 플래그와 어휘가 갈린다 (§4.11).
    card.appendChild(countRow(type, count));
  }
  card.appendChild(el('p', 'metric-caption', outDir));
  return card;
}

function countRow(name, value) {
  const row = el('div', 'check-row');
  row.appendChild(el('div', 'check-name', name));
  row.appendChild(el('div', 'check-detail', value));
  return row;
}

function renderPending(content, view) {
  content.appendChild(
    emptyState({
      title: '아직 볼 것이 없습니다',
      body: `${PENDING_VIEWS[view]} 먼저 스캔하면 이 화면이 채워집니다.`,
      actionLabel: '플랜 & 스캔으로',
      actionView: 'scan',
    })
  );
}

/* --- 렌더 루프 ---------------------------------------------------------------- */

function setWorkspacePath(path) {
  document.getElementById('workspace-path').textContent = path || '';
}

async function render() {
  const { view } = currentRoute();
  const entry = VIEWS.find((item) => item.id === view);
  document.getElementById('view-title').textContent = entry.label;
  document.getElementById('view-subtitle').textContent = entry.subtitle;
  renderNav(view);

  const content = document.getElementById('content');
  clear(content);
  closeStream();
  if (view === 'dashboard') {
    await renderDashboard(content);
  } else {
    renderPending(content, view);
  }
}

window.addEventListener('hashchange', render);
window.addEventListener('DOMContentLoaded', () => {
  stripBootstrapToken();
  if (!window.location.hash) {
    window.location.replace(`#/${DEFAULT_VIEW}`);
  }
  render();
});
