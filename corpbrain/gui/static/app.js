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

/**
 * 상태를 바꾸는 엔드포인트를 부른다.
 *
 * 브라우저가 같은 오리진 POST 에 `Origin` 을 자동으로 붙이므로 여기에 그 코드가 없다 —
 * 서버는 상태 변경 메서드에서 그 헤더를 **필수**로 요구한다 (§4.2). 409 는 프로토콜 층
 * 사건이라 본문의 `error` 로 그대로 내려온다 (§4.3.2).
 */
async function postJson(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
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

async function renderDashboard(content, generation) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const body = await getJson('/api/dashboard');
  // `/api/dashboard` 는 `diagnose()` 를 부르고 그것은 Ollama 를 실제로 두드린다 — 데몬이
  // 죽어 있으면 수 초가 걸린다. 그 사이 사용자가 다른 화면으로 옮겨 갔다면 이 응답은
  // **버린다.** 그러지 않으면 다른 화면의 제목 아래에 대시보드가 그려지고, 떠난 화면을
  // 위해 SSE 연결이 열린 채로 남는다.
  if (generation !== renderGeneration) return;
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
      // 스냅샷은 **재동기화 지점**이다 — 접속·재접속 때 한 번 오고 그때까지의 집계를
      // 통째로 복원한다 (§4.3).
      lastSnapshot = payload.snapshot;
      lastRunning = payload.running;
    } else {
      lastSnapshot = foldEvent(lastSnapshot, payload);
      lastRunning = payload.kind !== 'run_finished';
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

/**
 * 라이브 이벤트 하나를 현재 상태에 접는다.
 *
 * 서버는 스냅샷을 **접속 때 한 번만** 보내고 다시 보내지 않는다(리플레이 버퍼가 없는 것과
 * 같은 이유 — §4.3). 그래서 화면이 이벤트를 접지 않으면 진행 카운터가 접속 시점 값에 멈춘
 * 채 파일 이름만 바뀐다: 문서 50개를 도는 내내 `0 / 0` 이 보인다.
 *
 * 코어 `reduce()` 를 옮겨 오지 않는다 — 여기서 세는 것은 **화면이 그리는 값**(생성·스킵·
 * 현재 파일·그래프 단계)뿐이고, rate·ETA 같은 파생값과 재동기화는 그대로 서버 스냅샷이
 * 소유한다. 재접속 한 번이면 이 지역 집계가 서버 값으로 덮인다.
 */
function foldEvent(snapshot, payload) {
  const next = Object.assign({}, snapshot || {});
  if (payload.kind === 'run_started') {
    next.total = payload.total;
    next.generated = 0;
    next.skipped = 0;
  }
  if (payload.kind === 'file_generated') next.generated = (next.generated || 0) + 1;
  if (payload.kind === 'file_skipped') next.skipped = (next.skipped || 0) + 1;
  if (typeof payload.path === 'string') next.current_file = payload.path;
  if (payload.kind === 'graph_started') {
    next.graph_stage = 'building';
    next.current_file = null;
  }
  if (payload.kind === 'related_injected') next.graph_stage = 'injecting';
  if (payload.kind === 'graph_finished') {
    next.graph_stage = 'done';
    next.current_file = null;
  }
  return next;
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

/* --- 플랜 & 스캔 (§4.3.3 · §4.3.4) --------------------------------------------- */

/**
 * 폼이 다루는 필드 — 앞면 5개 + 「고급」 10개.
 *
 * **`ScanConfig` 15필드를 전부 다룰 수 있게 한다** (§4.3.3). `force` 없이는 재요약을 시킬 수
 * 없고 `max_files` 기본 50을 넘는 폴더는 GUI 에서 아예 스캔이 막히므로, 「CLI 로 돌아가야만
 * 되는 일」을 남기면 GUI 를 만든 목적이 줄어든다.
 *
 * **실측으로 확정된 상수는 앞면에 두지 않는다.** `similarity_threshold`(0.5717…)는 #42 가,
 * `graph_decay`(0.5)는 v0.7 §0 이 실측으로 세운 값이다. 앞면에 있으면 근거 없이 만져지고,
 * 만지면 그 성질이 조용히 무너진다. 접기 하나로 「전부 다룰 수 있다」와 「근거 있는 기본값을
 * 지킨다」를 동시에 만족시킨다.
 *
 * 값의 **타당성은 검증하지 않는다** — 그대로 서버로 보내고 코어가 판정한다 (§4.3.3).
 */
const SCAN_FIELDS_PRIMARY = [
  { name: 'folder', label: '입력 폴더', type: 'text', placeholder: '/Users/me/documents' },
  { name: 'out_dir', label: '출력 폴더', type: 'text', placeholder: '(서버 기본값)' },
  { name: 'engine', label: '엔진', type: 'select', options: ['local', 'cloud'] },
  { name: 'max_files', label: '최대 파일 수', type: 'number' },
  { name: 'force', label: 'mtime 무관 강제 재생성 (force)', type: 'check' },
];

const SCAN_FIELDS_ADVANCED = [
  { name: 'model', label: '요약 모델', type: 'text' },
  { name: 'embed_model', label: '임베딩 모델', type: 'text' },
  { name: 'cloud_model', label: '클라우드 모델', type: 'text' },
  { name: 'ollama_url', label: 'Ollama URL', type: 'text' },
  { name: 'max_chars', label: '문서당 최대 문자수', type: 'number' },
  { name: 'max_file_size', label: '파일 크기 상한 (바이트)', type: 'number' },
  { name: 'max_total_tokens', label: '총 토큰 예산', type: 'number' },
  { name: 'related_top_k', label: '「관련 문서」 개수', type: 'number' },
  { name: 'similarity_threshold', label: '유사도 임계값 (실측 확정값)', type: 'number', step: 'any' },
  { name: 'force_gates', label: '게이트 무시하고 강행 (force_gates)', type: 'check' },
];

/**
 * 폼 입력값 — 화면을 오갈 때 유지된다.
 *
 * 브라우저 `localStorage` 를 쓰지 않는다 (§4.8) — 브라우저를 바꾸거나 시크릿 창에서 열면
 * 사라지고 CLI 와 값을 공유할 길이 없다. 프로세스를 넘어선 영속화는
 * `~/.corpbrain/config.json` 의 `gui` 섹션이 맡으며 설정 화면과 함께 붙는다.
 */
const scanForm = { engine: 'local' };

function scanPayload() {
  const payload = {};
  for (const [name, value] of Object.entries(scanForm)) {
    if (value === '' || value === undefined || value === null) continue;
    payload[name] = value;
  }
  return payload;
}

function field(spec) {
  const wrap = el('div', spec.type === 'check' ? 'field field-check' : 'field');
  const id = `scan-${spec.name}`;
  const label = el('label', 'field-label', spec.label);
  label.htmlFor = id;
  let input;
  if (spec.type === 'select') {
    input = el('select');
    for (const option of spec.options) {
      const node = el('option', null, option);
      node.value = option;
      input.appendChild(node);
    }
    input.value = scanForm[spec.name] || spec.options[0];
    input.addEventListener('change', () => { scanForm[spec.name] = input.value; });
  } else if (spec.type === 'check') {
    input = el('input');
    input.type = 'checkbox';
    input.checked = Boolean(scanForm[spec.name]);
    input.addEventListener('change', () => { scanForm[spec.name] = input.checked; });
  } else {
    input = el('input');
    input.type = spec.type;
    if (spec.step) input.step = spec.step;
    if (spec.placeholder) input.placeholder = spec.placeholder;
    input.value = scanForm[spec.name] === undefined ? '' : scanForm[spec.name];
    input.addEventListener('input', () => {
      scanForm[spec.name] =
        spec.type === 'number' && input.value !== '' ? Number(input.value) : input.value;
    });
  }
  input.id = id;
  if (spec.type === 'check') {
    wrap.appendChild(input);
    wrap.appendChild(label);
  } else {
    wrap.appendChild(label);
    wrap.appendChild(input);
  }
  return wrap;
}

function scanFormCard(onMeasure, running) {
  const card = el('div', 'card');
  card.appendChild(el('div', 'card-title', '1. 계량하기'));
  card.appendChild(
    el('p', 'metric-caption', '파일 수·예상 토큰·게이트 판정을 먼저 봅니다. 이 단계는 LLM을 부르지 않습니다.')
  );
  const grid = el('div', 'form-grid');
  for (const spec of SCAN_FIELDS_PRIMARY) grid.appendChild(field(spec));
  card.appendChild(grid);

  const advanced = el('details', 'advanced');
  advanced.appendChild(el('summary', null, '고급'));
  advanced.appendChild(
    el('p', 'advanced-note', '유사도 임계값은 실측으로 확정된 값입니다 — 근거 없이 바꾸면 「관련 문서」와 검색 순위의 성질이 무너집니다.')
  );
  const advancedGrid = el('div', 'form-grid');
  for (const spec of SCAN_FIELDS_ADVANCED) advancedGrid.appendChild(field(spec));
  advanced.appendChild(advancedGrid);
  card.appendChild(advanced);

  const actions = el('div', 'actions');
  const measure = el('button', 'btn btn-primary', '계량하기');
  measure.type = 'button';
  measure.disabled = running;
  measure.addEventListener('click', onMeasure);
  actions.appendChild(measure);
  if (running) actions.appendChild(el('span', 'metric-caption', '스캔이 도는 동안에는 계량할 수 없습니다.'));
  card.appendChild(actions);
  return card;
}

function gateBox(gate) {
  const box = el('div', 'gate-box');
  box.appendChild(el('strong', null, '자원 게이트에 막혔습니다'));
  const list = el('ul');
  if (gate.gpu_enforced && !gate.gpu_ok) {
    list.appendChild(el('li', null, 'GPU를 감지하지 못했습니다 — CPU로 강행하려면 아래 토글을 켜세요.'));
  }
  if (!gate.tokens_ok) {
    list.appendChild(
      el('li', null, `예상 토큰이 예산(${gate.max_total_tokens})을 넘습니다 — 예산을 올리거나 폴더를 좁히세요.`)
    );
  }
  box.appendChild(list);
  // 게이트를 둔 이유가 「비용이 큰 작업을 무심코 시작하지 않게」이므로, 이유와 강행 토글을
  // 같은 자리에서 보여 준다 — CLI 가 exit 3 으로 막는 자리와 같다 (§4.3.4).
  box.appendChild(field({ name: 'force_gates', label: '이해했고 강행합니다 (force_gates)', type: 'check' }));
  return box;
}

function planCard(measurement, onRun, running) {
  const card = el('div', 'card');
  const plan = measurement.plan;
  const findings = measurement.findings;
  card.appendChild(el('div', 'card-title', '2. 확인하고 실행'));
  card.appendChild(el('div', 'metric-number', `${plan.file_count}개 문서`));
  card.appendChild(
    el('p', 'metric-caption', `예상 토큰 ${plan.total_est_tokens} · 예상 ${plan.est_seconds}초 · ${plan.hardware.label}`)
  );
  if (findings.limit_exceeded) {
    card.appendChild(
      el('p', 'metric-caption', `상한 초과 — ${findings.discovered_count}건 발견. 「최대 파일 수」를 올리세요.`)
    );
  }
  if (findings.skipped.length) {
    card.appendChild(countRow('스캔 단계 스킵', findings.skipped.length));
  }

  const scroll = el('div', 'table-scroll');
  const table = el('table', 'plan-table');
  const head = el('tr');
  for (const name of ['경로', '확장자', '크기', '예상 토큰', '중요도']) {
    head.appendChild(el('th', null, name));
  }
  table.appendChild(head);
  for (const entry of plan.entries) {
    const row = el('tr');
    row.appendChild(el('td', 'path', entry.path));
    row.appendChild(el('td', null, entry.ext));
    row.appendChild(el('td', 'num', entry.size_bytes));
    row.appendChild(el('td', 'num', entry.est_tokens));
    row.appendChild(el('td', 'num', entry.importance));
    table.appendChild(row);
  }
  scroll.appendChild(table);
  card.appendChild(scroll);

  if (plan.gate && plan.gate.blocked) card.appendChild(gateBox(plan.gate));

  const actions = el('div', 'actions');
  const run = el('button', 'btn btn-primary', '스캔 시작');
  run.type = 'button';
  run.disabled = running;
  run.addEventListener('click', onRun);
  actions.appendChild(run);
  if (running) actions.appendChild(el('span', 'metric-caption', '이미 스캔이 진행 중입니다.'));
  card.appendChild(actions);
  return card;
}

function progressCard(onCancel, cancelRequested) {
  const card = el('div', 'card');
  renderProgressCard(card, null, onCancel, cancelRequested);
  return card;
}

function renderProgressCard(card, payload, onCancel, cancelRequested) {
  if (payload !== null) {
    if (payload.kind === 'snapshot') {
      lastSnapshot = payload.snapshot;
      lastRunning = payload.running;
    } else {
      lastSnapshot = foldEvent(lastSnapshot, payload);
      lastRunning = payload.kind !== 'run_finished';
    }
  }
  clear(card);
  card.appendChild(el('div', 'card-title', '진행'));
  if (lastSnapshot === null) {
    card.appendChild(el('div', 'metric-number', '대기 중'));
    card.appendChild(el('p', 'metric-caption', '진행 중인 스캔이 없습니다.'));
    return;
  }
  const total = lastSnapshot.total || 0;
  const done = (lastSnapshot.generated || 0) + (lastSnapshot.skipped || 0);
  card.appendChild(el('div', 'metric-number', `${done} / ${total}`));
  const track = el('div', 'progress-track');
  const fill = el('div', 'progress-fill');
  fill.style.width = total ? `${Math.min(100, Math.round((done / total) * 100))}%` : '0%';
  track.appendChild(fill);
  card.appendChild(track);
  card.appendChild(countRow('생성', lastSnapshot.generated || 0));
  card.appendChild(countRow('스킵', lastSnapshot.skipped || 0));
  if (lastSnapshot.graph_stage) {
    // 그래프 단계는 파일 루프와 **별도 축**이다 — 진행률은 쪼갤 수 있는 패스3 에만 실린다.
    const total3 = lastSnapshot.graph_total || 0;
    card.appendChild(
      countRow(
        '그래프 단계',
        total3 ? `${lastSnapshot.graph_stage} ${lastSnapshot.graph_index || 0}/${total3}` : lastSnapshot.graph_stage
      )
    );
  }
  if (lastSnapshot.current_file) card.appendChild(el('p', 'metric-caption', lastSnapshot.current_file));
  if (lastRunning) {
    const actions = el('div', 'actions');
    const cancel = el('button', 'btn', cancelRequested ? '멈추는 중…' : '취소');
    cancel.type = 'button';
    cancel.disabled = Boolean(cancelRequested);
    cancel.addEventListener('click', onCancel);
    actions.appendChild(cancel);
    // 진행 중인 HTTP 호출은 끊지 않는다 — 요약 1건의 소켓 타임아웃만큼 기다릴 수 있다 (§4.7).
    actions.appendChild(el('span', 'metric-caption', '진행 중인 문서를 마친 뒤 멈춥니다.'));
    card.appendChild(actions);
  }
}

function resultCard(result) {
  const card = el('div', 'card');
  card.appendChild(el('div', 'card-title', result.cancelled ? '중단된 스캔' : '지난 스캔 결과'));
  card.appendChild(el('div', 'metric-number', `${result.generated_count} / ${result.generated_count + result.skipped_count}`));
  card.appendChild(el('p', 'metric-caption', '생성 / 처리'));
  // 종료 요약 줄은 `report.py` 의 빌더가 만든 것을 **그대로** 싣는다 — 갈라지면 안 되는 것은
  // 「어휘」이고, 스킵 사유 라벨·「그래프 미반영」 같은 문구를 프론트가 다시 구현하면 CLI 와
  // GUI 가 같은 결과를 다른 말로 설명한다 (§4.6.1).
  card.appendChild(el('pre', 'summary-lines', (result.summary_lines || []).join('\n')));
  return card;
}

async function renderScan(content, generation) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const state = await getJson('/api/scan');
  if (generation !== renderGeneration) return;
  clear(content);
  if (isError(state)) {
    content.appendChild(emptyState({ title: '스캔 상태를 불러오지 못했습니다', body: state.message }));
    return;
  }

  const notice = el('div');
  content.appendChild(notice);

  const showNotice = (message, kind) => {
    clear(notice);
    if (!message) return;
    const box = el('div', 'gate-box');
    if (kind) box.appendChild(badge(kind, kind === 'fail' ? '오류' : '안내'));
    box.appendChild(el('span', null, ` ${message}`));
    notice.appendChild(box);
  };

  if (state.failure) showNotice(state.failure.message, 'fail');

  const onMeasure = async () => {
    showNotice('계량 중…');
    const body = await postJson('/api/scan/plan', scanPayload());
    if (isError(body)) {
      showNotice(body.message, 'fail');
      return;
    }
    render();
  };

  const onRun = async () => {
    const body = await postJson('/api/scan', scanPayload());
    if (isError(body)) {
      // 409(이미 진행 중)도 여기로 온다 — 화면은 이유를 그대로 보여 주고 상태를 다시 읽는다.
      showNotice(body.message, 'fail');
    }
    render();
  };

  const onCancel = async () => {
    await postJson('/api/scan/cancel', {});
    render();
  };

  const grid = el('div', 'bento');
  grid.appendChild(scanFormCard(onMeasure, state.running));
  if (state.plan) grid.appendChild(planCard(state.plan, onRun, state.running));
  const progress = progressCard(onCancel, state.cancel_requested);
  grid.appendChild(progress);
  if (state.result) grid.appendChild(resultCard(state.result));
  content.appendChild(grid);

  openStream((payload) => {
    renderProgressCard(progress, payload, onCancel, state.cancel_requested);
    // 스캔이 끝나면 결과 카드와 버튼 상태를 서버 값으로 다시 맞춘다.
    if (payload.kind === 'run_finished') render();
  });
}

/* --- 위키 탐색기 (§4.6 · §4.6.2 · §4.10.4) ------------------------------------- */

/** `#/wiki?doc=<doc_id>` 로 이동한다 — 화면 전환은 해시를 바꾸는 것으로만 일어난다. */
function navigateTo(view, params) {
  const query = new URLSearchParams(params || {}).toString();
  window.location.hash = query ? `#/${view}?${query}` : `#/${view}`;
}

function treeCard(tree, selected) {
  const card = el('div', 'card tree');
  card.appendChild(el('div', 'card-title', '문서'));
  if (tree.message) card.appendChild(el('p', 'metric-caption', tree.message));
  const groups = new Map();
  for (const entry of tree.documents) {
    if (!groups.has(entry.directory)) groups.set(entry.directory, []);
    groups.get(entry.directory).push(entry);
  }
  for (const [directory, entries] of groups) {
    const group = el('div', 'tree-group');
    group.appendChild(el('div', 'tree-dir', directory));
    for (const entry of entries) {
      const item = el('button', 'tree-item', entry.title || entry.name);
      item.type = 'button';
      item.title = entry.doc_id;
      if (entry.doc_id === selected) item.setAttribute('aria-current', 'true');
      item.addEventListener('click', () => navigateTo('wiki', { doc: entry.doc_id }));
      group.appendChild(item);
    }
    card.appendChild(group);
  }
  return card;
}

function copyButton(text) {
  const button = el('button', 'btn', '경로 복사');
  button.type = 'button';
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = '복사됨';
      window.setTimeout(() => { button.textContent = '경로 복사'; }, 1500);
    } catch (_err) {
      button.textContent = '복사 실패';
    }
  });
  return button;
}

function section(title, build) {
  const box = el('div', 'doc-section');
  box.appendChild(el('h3', null, title));
  box.appendChild(build());
  return box;
}

function documentCard(doc) {
  const card = el('div', 'card');
  card.appendChild(el('div', 'doc-title', doc.title || '(제목 없음)'));
  card.appendChild(el('p', 'doc-lead', doc.one_line_summary));

  const meta = el('div', 'doc-meta');
  // `engine` 을 가장 먼저 보인다 — 「이 문서가 외부로 나갔는가」를 생성물만 보고 아는
  // 값이다 (v0.5 §4.6 · §4.6).
  meta.appendChild(badge(doc.engine === 'cloud' ? 'warn' : 'info', `engine: ${doc.engine || '?'}`));
  meta.appendChild(badge('info', `model: ${doc.model || '?'}`));
  meta.appendChild(badge('info', `${doc.source_bytes} bytes`));
  meta.appendChild(badge('info', doc.generated_at || '?'));
  card.appendChild(meta);

  card.appendChild(section('핵심 포인트', () => {
    const list = el('ul');
    for (const point of doc.key_points) list.appendChild(el('li', null, point));
    return list;
  }));
  card.appendChild(section('요약', () => el('p', null, doc.summary)));
  card.appendChild(section('태그·키워드', () => {
    const box = el('div');
    for (const tag of doc.tags) box.appendChild(el('span', 'tag-chip', tag));
    return box;
  }));
  card.appendChild(section('원문', () => {
    // `file://` 링크는 http 페이지에서 브라우저가 **차단**한다 — 죽은 링크를 그리지 않고
    // 경로 표시 + 복사 버튼으로 낸다 (§4.6 · IX2). 파일을 OS 기본 앱으로 여는 엔드포인트는
    // 두지 않는다 (MVP 스펙 §2 비목표).
    const row = el('div', 'source-row');
    row.appendChild(el('div', 'source-path', doc.source_path || '(알 수 없음)'));
    if (doc.source_path) row.appendChild(copyButton(doc.source_path));
    return row;
  }));
  card.appendChild(section('관련 문서', () => {
    const box = el('div');
    if (!doc.related.length) {
      box.appendChild(el('p', 'metric-caption', '관련 문서 없음'));
      return box;
    }
    for (const item of doc.related) {
      const row = el('div', 'related-item');
      const link = el('button', 'related-link', item.title);
      link.type = 'button';
      if (item.doc_id) {
        // 서버가 실어 준 `doc_id` 로 해시를 조립하기만 한다 — 프론트에 경로 해석 규칙이
        // 생기지 않는다 (§4.6 · IX3).
        link.addEventListener('click', () => navigateTo('wiki', { doc: item.doc_id }));
      } else {
        link.disabled = true;
        link.title = '대상 위키를 찾지 못했습니다';
      }
      row.appendChild(link);
      if (item.evidence) row.appendChild(el('div', 'related-evidence', item.evidence));
      box.appendChild(row);
    }
    return box;
  }));
  return card;
}

async function renderWiki(content, generation, params) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const tree = await getJson('/api/wiki');
  if (generation !== renderGeneration) return;
  clear(content);
  if (isError(tree)) {
    content.appendChild(
      emptyState({
        title: '아직 볼 것이 없습니다',
        body: tree.message,
        actionLabel: '플랜 & 스캔으로',
        actionView: 'scan',
      })
    );
    return;
  }

  const selected = params.get('doc') || '';
  const split = el('div', 'split');
  split.appendChild(treeCard(tree, selected));
  const detail = el('div');
  split.appendChild(detail);
  content.appendChild(split);

  if (!selected) {
    detail.appendChild(
      emptyState({ title: '문서를 고르세요', body: '왼쪽 트리에서 문서를 선택하면 상세가 열립니다.' })
    );
    return;
  }
  const doc = await getJson(`/api/wiki/document?doc=${encodeURIComponent(selected)}`);
  if (generation !== renderGeneration) return;
  clear(detail);
  if (isError(doc)) {
    detail.appendChild(emptyState({ title: '문서를 불러오지 못했습니다', body: doc.message }));
    return;
  }
  detail.appendChild(documentCard(doc));
}

/* --- 지식그래프 (§4.3.1 · §4.11 · §5) ------------------------------------------- */

/**
 * 노드 종류별 색 — **계승한 디자인 토큰만** 쓴다 (§4.10.5).
 *
 * 캔버스는 CSS 변수를 직접 못 쓰므로 이름만 들고 있다가 그릴 때 한 번 푼다. 새 색을 여기
 * 하드코딩하면 토큰 밖의 값이 생기고, minimalist 가 대비비를 재서 올린 비용이 무효가 된다.
 */
const NODE_COLOR_VARS = {
  Document: '--accent-blue',
  Entity: '--accent-purple',
  Tag: '--accent-emerald',
};

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * 결정적 레이아웃 — 종류별 동심원.
 *
 * 물리 시뮬레이션을 쓰지 않는다. 같은 그래프가 열 때마다 다르게 배치되면 「이 문서가 어디
 * 있었더라」가 성립하지 않고, 규모가 커질수록 프레임 예산이 먼저 무너진다(§5의 알려진 한계를
 * 더 나쁘게 만든다). 각도는 노드 id 순서로 결정되므로 두 번 열어도 같은 그림이다.
 */
function layoutNodes(nodes, width, height) {
  const byType = { Document: [], Entity: [], Tag: [] };
  for (const node of nodes) (byType[node.type] || byType.Document).push(node);
  const cx = width / 2;
  const cy = height / 2;
  const unit = Math.min(width, height) / 2 - 28;
  const rings = [
    { type: 'Document', radius: unit * 0.42 },
    { type: 'Entity', radius: unit * 0.78 },
    { type: 'Tag', radius: unit * 1.0 },
  ];
  const placed = new Map();
  for (const ring of rings) {
    const list = byType[ring.type];
    list.forEach((node, index) => {
      const angle = (index / Math.max(1, list.length)) * Math.PI * 2 - Math.PI / 2;
      placed.set(node.id, {
        node,
        x: cx + Math.cos(angle) * ring.radius,
        y: cy + Math.sin(angle) * ring.radius,
      });
    });
  }
  return placed;
}

function drawGraph(canvas, data, selected) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const colors = Object.fromEntries(
    Object.entries(NODE_COLOR_VARS).map(([type, name]) => [type, cssVar(name)])
  );
  const placed = layoutNodes(data.nodes, width, height);
  ctx.lineWidth = 1;
  ctx.strokeStyle = 'rgba(17, 17, 17, 0.10)';
  for (const edge of data.edges) {
    const from = placed.get(edge.src);
    const to = placed.get(edge.dst);
    if (!from || !to) continue;
    const touches = selected && (edge.src === selected || edge.dst === selected);
    ctx.strokeStyle = touches ? 'rgba(46, 106, 147, 0.55)' : 'rgba(17, 17, 17, 0.08)';
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
  }
  for (const spot of placed.values()) {
    const radius = spot.node.id === selected ? 7 : Math.min(6, 3 + spot.node.degree * 0.35);
    ctx.beginPath();
    ctx.arc(spot.x, spot.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = colors[spot.node.type] || colors.Document;
    ctx.fill();
    if (spot.node.id === selected) {
      ctx.strokeStyle = '#111111';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    }
  }
  return placed;
}

function graphLegend() {
  const box = el('div', 'legend');
  for (const [type, name] of Object.entries(NODE_COLOR_VARS)) {
    const item = el('div', 'legend-item');
    const dot = el('span', 'legend-dot');
    dot.style.background = `var(${name})`;
    item.appendChild(dot);
    item.appendChild(el('span', null, type));
    box.appendChild(item);
  }
  return box;
}

async function renderGraph(content, generation, params) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const data = await getJson('/api/graph');
  if (generation !== renderGeneration) return;
  clear(content);
  if (isError(data)) {
    content.appendChild(
      emptyState({
        title: '아직 그래프가 없습니다',
        body: data.message,
        actionLabel: '플랜 & 스캔으로',
        actionView: 'scan',
      })
    );
    return;
  }

  const selected = params.get('node') || '';
  const split = el('div', 'split');

  const listCard = el('div', 'card node-list');
  listCard.appendChild(el('div', 'card-title', `노드 ${data.stats.nodes} / 엣지 ${data.stats.edges}`));
  for (const node of [...data.nodes].sort((a, b) => b.degree - a.degree || a.id.localeCompare(b.id))) {
    const item = el('button', 'tree-item', node.label || node.id);
    item.type = 'button';
    item.title = node.id;
    if (node.id === selected) item.setAttribute('aria-current', 'true');
    item.appendChild(el('span', 'node-degree', ` · ${node.type} ${node.degree}`));
    item.addEventListener('click', () => navigateTo('graph', { node: node.id }));
    listCard.appendChild(item);
  }

  const canvasCard = el('div', 'card graph-canvas-wrap');
  const canvas = el('canvas', 'graph-canvas');
  // 캔버스도 키보드로 닿아야 한다 — 클릭으로만 되는 조작을 남기지 않는다 (§4.10.5).
  canvas.tabIndex = 0;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute(
    'aria-label',
    `지식그래프 — 노드 ${data.stats.nodes}개, 엣지 ${data.stats.edges}개. 왼쪽 목록에서 노드를 고르세요.`
  );
  canvasCard.appendChild(canvas);
  canvasCard.appendChild(graphLegend());
  const detail = el('div');
  canvasCard.appendChild(detail);

  split.appendChild(listCard);
  split.appendChild(canvasCard);
  content.appendChild(split);

  let placed = drawGraph(canvas, data, selected);
  const redraw = () => { placed = drawGraph(canvas, data, selected); };
  window.addEventListener('resize', redraw);
  canvas.addEventListener('click', (event) => {
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    let hit = null;
    for (const spot of placed.values()) {
      if ((spot.x - x) ** 2 + (spot.y - y) ** 2 <= 100) { hit = spot.node; break; }
    }
    if (hit) navigateTo('graph', { node: hit.id });
  });

  if (selected) {
    const node = data.nodes.find((entry) => entry.id === selected);
    if (node) {
      detail.appendChild(el('div', 'card-title', node.label || node.id));
      detail.appendChild(el('p', 'metric-caption', `${node.type} · 연결 ${node.degree}`));
      if (node.type === 'Document') {
        // 문서 노드의 id 가 곧 `doc_id` 다 — 위키 화면과 **같은 키**를 쓴다 (§4.6.2).
        const open = el('button', 'btn btn-primary', '위키에서 보기');
        open.type = 'button';
        open.addEventListener('click', () => navigateTo('wiki', { doc: node.id }));
        detail.appendChild(open);
      }
    }
  }
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

/** 렌더 세대 — 화면이 바뀔 때마다 증가한다. 늦게 온 응답을 가려내는 유일한 기준이다. */
let renderGeneration = 0;

async function render() {
  const generation = ++renderGeneration;
  const { view, params } = currentRoute();
  const entry = VIEWS.find((item) => item.id === view);
  document.getElementById('view-title').textContent = entry.label;
  document.getElementById('view-subtitle').textContent = entry.subtitle;
  renderNav(view);

  const content = document.getElementById('content');
  clear(content);
  closeStream();
  if (view === 'dashboard') {
    await renderDashboard(content, generation);
  } else if (view === 'scan') {
    await renderScan(content, generation);
  } else if (view === 'wiki') {
    await renderWiki(content, generation, params);
  } else if (view === 'graph') {
    await renderGraph(content, generation, params);
  } else {
    renderPending(content, view);
  }
}

window.addEventListener('hashchange', render);
window.addEventListener('DOMContentLoaded', () => {
  stripBootstrapToken();
  if (!window.location.hash) {
    // 해시를 넣는 것 자체가 `hashchange`를 큐에 넣는다. 여기서 `render()`까지 부르면 콜드
    // 로드마다 대시보드를 **두 번** 그려 `/api/dashboard`(= `diagnose()` 네트워크 호출)가
    // 두 번 나가고 `EventSource`도 두 번 열린다. 해시가 화면 상태의 단일 출처라는 것은
    // (§4.10.4) 첫 렌더도 해시가 몰아야 한다는 뜻이다.
    window.location.replace(`#/${DEFAULT_VIEW}`);
    return;
  }
  render();
});
