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
 * 이벤트 사이를 메우는 초 단위 시계.
 *
 * **실측이 요구한 것이다** — 문서 1건의 요약이 도는 동안 이벤트가 하나도 오지 않아 화면이
 * 최대 47초 멈춘 것처럼 보였다(`docs/SMOKE.md` 실행 K). 코어에 토큰 단위 이벤트를 더하는 것은
 * §4.7이 이벤트 11종으로 못박은 범위 밖이므로, **이미 받은 값에서 시간만 흘려** 화면이
 * 살아 있음을 보인다.
 *
 * 서버 값을 다시 계산하는 것이 아니다 — `elapsed`·`eta`는 그대로 서버 스냅샷이 소유하고,
 * 여기서는 마지막 프레임 이후 흐른 시간을 더해 **표시**할 뿐이며 다음 프레임이 오면 그
 * 값으로 덮인다.
 */
let ticker = null;
let lastFrameAt = null;

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
    // 프레임 시각은 **수신 지점 한 곳**에서 찍는다. 카드마다 찍으면 그 카드를 그리지 않는
    // 화면에 머무는 동안 값이 낡고, 돌아왔을 때 시계가 엉뚱한 값에서 시작한다.
    lastFrameAt = Date.now();
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
  // 시계는 스트림과 수명을 같이 한다 — 화면을 떠난 뒤에도 돌면 사라진 DOM 을 계속 만진다.
  stopTicker();
}

function openStream(onFrame) {
  closeStream();
  activeStream = connectEvents(onFrame);
}

/** 그래프 화면이 쥐고 있는 `resize` 리스너. 화면을 떠날 때 반드시 푼다. */
let graphResizeHandler = null;

function setGraphResizeHandler(handler) {
  clearGraphResizeHandler();
  graphResizeHandler = handler;
  window.addEventListener('resize', handler);
}

function clearGraphResizeHandler() {
  if (graphResizeHandler !== null) {
    window.removeEventListener('resize', graphResizeHandler);
    graphResizeHandler = null;
  }
}

function stopTicker() {
  if (ticker !== null) {
    window.clearInterval(ticker);
    ticker = null;
  }
}

function startTicker(onTick) {
  stopTicker();
  ticker = window.setInterval(onTick, 1000);
}

/** 초를 `mm:ss` 로 — CLI `render_status_line()` 과 같은 표기다. */
function mmss(seconds) {
  const total = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

/**
 * 「경과 · ETA · 단계」 줄을 붙이고 1초마다 다시 그린다.
 *
 * **진행 상태를 그리는 카드가 둘이므로 여기 한 곳에 둔다** — 대시보드의 「실행 상태」와 스캔
 * 화면의 「진행」이 같은 스냅샷을 보는데 한쪽만 시계를 가지면, 같은 스캔이 화면에 따라 살아
 * 있어 보이기도 하고 멈춰 보이기도 한다.
 *
 * 어휘(`경과`·`ETA`·단계 이름)는 CLI `render_status_line()` 이 쓰는 것을 그대로 쓴다.
 */
function appendClock(card) {
  const clock = el('p', 'metric-caption');
  card.appendChild(clock);
  const paint = () => {
    const drift = lastFrameAt === null ? 0 : (Date.now() - lastFrameAt) / 1000;
    const parts = [`경과 ${mmss((lastSnapshot.elapsed || 0) + drift)}`];
    if (typeof lastSnapshot.eta === 'number') parts.push(`ETA ${mmss(lastSnapshot.eta)}`);
    if (lastSnapshot.stage) parts.push(lastSnapshot.stage);
    clock.textContent = parts.join(' · ');
  };
  paint();
  startTicker(paint);
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
  // 대시보드에서 스캔을 지켜보는 경우도 있다. 시계가 없으면 문서 1건이 요약되는 47초 동안
  // 이 카드만 멈춘 것처럼 보인다 — 같은 스냅샷을 보는 두 카드가 다르게 읽히면 안 된다.
  if (lastRunning) {
    appendClock(card);
  } else {
    stopTicker();
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
  if (payload.kind === 'related_injected') {
    next.graph_stage = 'injecting';
    // 진행률까지 접는다. 서버 `reduce()` 는 이 값을 채우지만 스냅샷은 접속 때 한 번만 오므로,
    // 접지 않으면 패스3 내내 `graph_total` 이 0(스냅샷 시점 값)에 머물러 카운터가 사라진다 —
    // 파일 루프에서 고친 것과 같은 종류의 「멈춘 카운터」다.
    next.graph_index = payload.index;
    next.graph_total = payload.total;
  }
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

/* --- 폴더 선택 (§4.5) ----------------------------------------------------------- */

/**
 * 어느 입력을 위해 탐색기가 열려 있는가 (`folder` · `out_dir`), 그리고 지금 보고 있는 경로.
 *
 * **폴더를 고르는 즉시 자동 계량하지 않는다** (§4.3.4) — `plan_scan()`은 `nvidia-smi`
 * subprocess와 전체 stat 패스를 돌리므로, 폴더를 둘러보는 동안 그것이 반복되면 탐색이
 * 느려진다. 여기서 고르는 것은 입력값뿐이고 계량은 여전히 버튼이 시작한다.
 */
let browser = null;

function openBrowser(fieldName, startPath) {
  browser = { field: fieldName, path: startPath || null, showHidden: false };
  render();
}

function closeBrowser() {
  browser = null;
  render();
}

function browserCard() {
  const card = el('div', 'browser');
  const pathLine = el('div', 'browser-path', '불러오는 중…');
  card.appendChild(pathLine);
  const list = el('div', 'browser-list');
  card.appendChild(list);
  const actions = el('div', 'browser-actions');
  card.appendChild(actions);

  const load = async (path) => {
    const body = await getJson(
      path === null ? '/api/browse' : `/api/browse?path=${encodeURIComponent(path)}`
    );
    clear(list);
    clear(actions);
    if (isError(body)) {
      pathLine.textContent = body.message;
      const back = el('button', 'btn', '홈으로');
      back.type = 'button';
      back.addEventListener('click', () => load(null));
      actions.appendChild(back);
      return;
    }
    browser.path = body.path;
    pathLine.textContent = body.path;

    if (body.parent) {
      const up = el('button', 'browser-item', '⤴  상위 폴더');
      up.type = 'button';
      up.addEventListener('click', () => load(body.parent));
      list.appendChild(up);
    }
    const shown = body.directories.filter((entry) => browser.showHidden || !entry.hidden);
    for (const entry of shown) {
      const item = el('button', `browser-item${entry.hidden ? ' hidden-entry' : ''}`, `📁  ${entry.name}`);
      item.type = 'button';
      item.addEventListener('click', () => load(entry.path));
      list.appendChild(item);
    }
    if (!shown.length) list.appendChild(el('p', 'browser-count', '하위 폴더가 없습니다.'));

    const choose = el('button', 'btn btn-primary', '이 폴더 선택');
    choose.type = 'button';
    choose.addEventListener('click', () => {
      scanForm[browser.field] = body.path;
      closeBrowser();
    });
    actions.appendChild(choose);
    const cancel = el('button', 'btn', '닫기');
    cancel.type = 'button';
    cancel.addEventListener('click', closeBrowser);
    actions.appendChild(cancel);
    // 스캔 대상이 될 폴더이므로 「여기 스캔할 것이 있는가」를 함께 보인다.
    actions.appendChild(
      el('span', 'browser-count', `지원 포맷 ${body.supported_file_count}개`)
    );
    const hidden = el('button', 'btn', browser.showHidden ? '숨김 폴더 감추기' : '숨김 폴더 보기');
    hidden.type = 'button';
    hidden.addEventListener('click', () => {
      browser.showHidden = !browser.showHidden;
      load(browser.path);
    });
    actions.appendChild(hidden);
  };

  load(browser.path);
  return card;
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
 * 다음 렌더에서 한 번 보여 줄 안내 — **렌더를 넘겨야 하는** 메시지가 여기 담긴다.
 *
 * 409(이미 진행 중)처럼 「상태를 다시 읽어야 하는데 이유도 보여야 하는」 경우가 있다.
 * 화면 안에서만 그리면 곧바로 이어지는 `render()` 가 그것을 지워, 사용자는 아무 일도
 * 일어나지 않은 것처럼 본다. 렌더 밖에 두고 `renderScan` 이 한 번 소비한다.
 */
let scanNotice = null;

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

/**
 * 입력 하나를 그린다. `state` 는 값을 읽고 쓸 폼 객체다 — 스캔 폼과 검색 폼이 같은
 * 함수를 공유하므로 입력 모양이 화면마다 갈리지 않는다.
 *
 * `spec.idPrefix` 는 **같은 필드를 한 화면에 두 번 그릴 때** 준다 — `force_gates` 가 「고급」과
 * 게이트 박스 양쪽에 나오므로, id 가 같으면 두 `<label for=…>` 이 첫 번째 체크박스만 가리켜
 * 「고급」의 라벨을 눌렀는데 게이트 박스의 값이 바뀐다.
 */
function field(spec, state = scanForm) {
  const wrap = el('div', spec.type === 'check' ? 'field field-check' : 'field');
  const id = `${spec.idPrefix || 'field'}-${spec.name}`;
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
    input.value = state[spec.name] || spec.options[0];
    input.addEventListener('change', () => { state[spec.name] = input.value; });
  } else if (spec.type === 'check') {
    input = el('input');
    input.type = 'checkbox';
    input.checked = Boolean(state[spec.name]);
    input.addEventListener('change', () => { state[spec.name] = input.checked; });
  } else {
    input = el('input');
    input.type = spec.type;
    if (spec.step) input.step = spec.step;
    if (spec.placeholder) input.placeholder = spec.placeholder;
    input.value = state[spec.name] === undefined ? '' : state[spec.name];
    input.addEventListener('input', () => {
      state[spec.name] =
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
  for (const spec of SCAN_FIELDS_PRIMARY) {
    const wrap = field(spec);
    if (spec.name === 'folder' || spec.name === 'out_dir') {
      // 경로를 외워 적게 하지 않는다 (§4.5). 텍스트 입력은 그대로 두어 붙여넣기도 되게 한다.
      const pick = el('button', 'btn', '찾아보기');
      pick.type = 'button';
      pick.addEventListener('click', () => openBrowser(spec.name, scanForm[spec.name] || null));
      wrap.appendChild(pick);
    }
    grid.appendChild(wrap);
  }
  card.appendChild(grid);
  if (browser !== null) card.appendChild(browserCard());

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
  // 게이트 «판정»과 «강행 여부»는 다르다. `GateVerdict` 는 임계값만 보고 내려진 값이라
  // `force_gates` 를 켜도 그대로 걸려 있으므로, 문구까지 「막혔습니다」로 두면 곧 시작될
  // 스캔을 두고 막혔다고 말하게 된다.
  box.appendChild(
    el('strong', null, scanForm.force_gates ? '자원 게이트를 강행합니다' : '자원 게이트에 막혔습니다')
  );
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
  const toggle = field({
    name: 'force_gates',
    label: '이해했고 강행합니다 (force_gates)',
    type: 'check',
    idPrefix: 'gate',
  });
  // 토글을 켜면 위 문구가 곧바로 따라가야 한다 — 다시 계량할 때까지 「막혔습니다」가 남아
  // 있으면 사용자가 자기 조작이 먹혔는지 알 수 없다.
  toggle.querySelector('input').addEventListener('change', () => render());
  box.appendChild(toggle);
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
    appendClock(card);
  } else {
    stopTicker();
  }
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

  if (scanNotice) {
    showNotice(scanNotice.message, scanNotice.kind);
    scanNotice = null;
  } else if (state.failure) {
    showNotice(state.failure.message, 'fail');
  }

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
      // 409(이미 진행 중)도 여기로 온다. 상태는 다시 읽어야 하고(다른 탭에서 시작된 스캔을
      // 이 화면이 아직 모를 수 있다) 이유도 보여야 하므로, 안내를 렌더 밖에 남긴다.
      scanNotice = { message: body.message, kind: 'fail' };
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

//: 노드 반지름의 하한과 상한. 상한은 링의 이웃 간격에 따라 더 줄어들 수 있다 — 아래 `drawGraph`.
const NODE_RADIUS_MIN = 4;
const NODE_RADIUS_MAX = 18;

//: 엣지 불투명도. 선택이 없을 때는 전부 `IDLE`, 선택이 있으면 닿는 엣지만 `ACTIVE`이고
//: 나머지는 `MUTED`로 물러난다 — 그래야 선택이 실제로 무언가를 가른다.
const EDGE_ALPHA_IDLE = 0.18;
const EDGE_ALPHA_ACTIVE = 0.7;
const EDGE_ALPHA_MUTED = 0.05;

//: 라벨을 다는 상위 노드 수(차수 내림차순). 전부 달면 겹쳐서 하나도 못 읽는다.
//: 선택된 노드는 순위와 무관하게 항상 단다.
const NODE_LABEL_TOP = 12;
//: 라벨 최대 글자 수. 넘으면 말줄임.
const NODE_LABEL_CHARS = 14;

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
  // 가장 촘촘한 링의 이웃 사이 호 간격. 노드 반지름의 상한을 여기서 끌어와야 규모가 커져도
  // 원이 서로 겹치지 않는다 — 태그 링은 문서 링보다 훨씬 붐빈다.
  let gap = Infinity;
  for (const ring of rings) {
    const list = byType[ring.type];
    if (!list.length) continue;
    if (list.length > 1) gap = Math.min(gap, (2 * Math.PI * ring.radius) / list.length);
    list.forEach((node, index) => {
      const angle = (index / Math.max(1, list.length)) * Math.PI * 2 - Math.PI / 2;
      placed.set(node.id, {
        node,
        x: cx + Math.cos(angle) * ring.radius,
        y: cy + Math.sin(angle) * ring.radius,
      });
    });
  }
  return { placed, gap: Number.isFinite(gap) ? gap : unit };
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
  const ink = cssVar('--ink');
  const { placed, gap } = layoutNodes(data.nodes, width, height);
  const cx = width / 2;
  const cy = height / 2;

  // 반지름은 **넓이가 차수에 비례**하도록 제곱근으로 매긴다. 지름을 차수에 비례시키면
  // 허브 하나가 화면을 삼키고, 선형 가산(옛 `3 + degree * 0.35`)은 상한 6px에 연결 9개에서
  // 닿아 그 위로는 전부 같은 크기가 됐다 — 태그 링의 대다수가 그 구간에 있어 크기 차이가
  // 사실상 보이지 않았다.
  const maxDegree = data.nodes.reduce((max, node) => Math.max(max, node.degree), 0);
  // 상한은 가장 붐비는 링의 이웃 간격을 넘지 않는다 — 규모가 커지면 원이 저절로 작아진다.
  const cap = Math.max(NODE_RADIUS_MIN + 1, Math.min(NODE_RADIUS_MAX, gap * 0.45));
  const radiusOf = (node) =>
    maxDegree > 0
      ? NODE_RADIUS_MIN + Math.sqrt(node.degree / maxDegree) * (cap - NODE_RADIUS_MIN)
      : NODE_RADIUS_MIN;

  for (const edge of data.edges) {
    const from = placed.get(edge.src);
    const to = placed.get(edge.dst);
    if (!from || !to) continue;
    // 색은 **토큰에서 온 값**이고 흐리기는 `globalAlpha` 로 준다 — `rgba(…)` 리터럴을 쓰면
    // 토큰 값을 복제하게 되어, 팔레트가 바뀌어도 캔버스만 옛 색으로 남는다 (§4.10.5).
    const touches = selected && (edge.src === selected || edge.dst === selected);
    ctx.strokeStyle = touches ? colors.Document : ink;
    ctx.globalAlpha = selected
      ? touches
        ? EDGE_ALPHA_ACTIVE
        : EDGE_ALPHA_MUTED
      : EDGE_ALPHA_IDLE;
    ctx.lineWidth = touches ? 1.5 : 1;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.lineWidth = 1;

  for (const spot of placed.values()) {
    const isSelected = spot.node.id === selected;
    const radius = radiusOf(spot.node) + (isSelected ? 3 : 0);
    ctx.beginPath();
    ctx.arc(spot.x, spot.y, radius, 0, Math.PI * 2);
    ctx.fillStyle = colors[spot.node.type] || colors.Document;
    ctx.fill();
    if (isSelected) {
      ctx.strokeStyle = ink;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.lineWidth = 1;
    }
  }

  drawNodeLabels(ctx, { placed, selected, radiusOf, cx, cy, width });
  return placed;
}

/**
 * 차수 상위 노드에만 라벨을 그린다.
 *
 * 전부 달면 겹쳐서 하나도 못 읽고, 하나도 안 달면 캔버스가 「글자 없는 색점 밭」이 되어
 * 모든 식별이 옆 목록에서만 일어난다. 정렬 키는 노드 목록과 **같다**(차수 내림차순 →
 * id 사전순) — 두 화면이 같은 노드를 다르게 꼽으면 안 된다.
 *
 * 글꼴·색은 토큰에서 가져온다. 캔버스라고 해서 새 회색을 만들지 않는다.
 */
function drawNodeLabels(ctx, { placed, selected, radiusOf, cx, cy, width }) {
  const spots = [...placed.values()];
  const ranked = [...spots].sort(
    (a, b) => b.node.degree - a.node.degree || a.node.id.localeCompare(b.node.id)
  );
  const shown = new Set(ranked.slice(0, NODE_LABEL_TOP).map((spot) => spot.node.id));
  if (selected) shown.add(selected);

  ctx.font = `500 11px ${cssVar('--font-sans')}`;
  ctx.fillStyle = cssVar('--text-secondary');
  ctx.textBaseline = 'middle';
  for (const spot of spots) {
    if (!shown.has(spot.node.id)) continue;
    const raw = spot.node.label || spot.node.id;
    const text =
      raw.length > NODE_LABEL_CHARS ? `${raw.slice(0, NODE_LABEL_CHARS - 1)}…` : raw;
    // 중심에서 바깥쪽으로 밀어 낸다 — 동심원 배치라 라벨이 링을 가로지르지 않는다.
    const dx = spot.x - cx;
    const dy = spot.y - cy;
    const len = Math.hypot(dx, dy) || 1;
    const away = radiusOf(spot.node) + 6;
    const toLeft = dx < 0;
    ctx.textAlign = toLeft ? 'right' : 'left';
    const textWidth = ctx.measureText(text).width;
    let x = spot.x + (dx / len) * away;
    // 캔버스 밖으로 나가지 않게 붙든다.
    x = toLeft
      ? Math.max(x, 4 + textWidth)
      : Math.min(x, width - 4 - textWidth);
    ctx.fillText(text, x, spot.y + (dy / len) * away);
  }
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
  // 크기가 의미를 갖게 됐으므로 그 의미를 적는다 — 설명 없는 크기 차이는 장식으로 읽힌다.
  const size = el('div', 'legend-item');
  const small = el('span', 'legend-dot');
  small.style.cssText = 'width:5px;height:5px;background:var(--text-muted)';
  const large = el('span', 'legend-dot');
  large.style.cssText = 'width:13px;height:13px;background:var(--text-muted)';
  size.appendChild(small);
  size.appendChild(large);
  size.appendChild(el('span', null, '크기 = 연결 수'));
  box.appendChild(size);
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
  // 리스너를 **한 개만** 유지한다. 매 렌더마다 새로 등록하면 그래프 화면에 N 번 들어갔을 때
  // 창 크기를 한 번 바꾸는 것이 N 번의 `drawGraph` 를 돌리고(그중 N-1 번은 이미 사라진
  // 캔버스), 그 클로저가 노드·엣지 전체를 붙잡아 메모리도 놓이지 않는다.
  setGraphResizeHandler(() => { placed = drawGraph(canvas, data, selected); });
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

/* --- 지식 검색 (§4.3.3 · §4.6.1) ------------------------------------------------ */

/** 검색 폼 상태 — 앞면 2개 + 「고급」 4개 (§4.3.3). */
const searchForm = { q: '', top_k: 5, graph: true };

const SEARCH_FIELDS_ADVANCED = [
  // 확산을 끄는 것은 v0.4 동작으로 되돌리는 일이라 자주 만질 값이 아니다 — §4.3.3 표가
  // 앞면에 쿼리·`top_k` 둘만 두고 나머지를 접어 둔 그대로 따른다.
  { name: 'graph', label: '그래프 확산 사용', type: 'check' },
  { name: 'graph_decay', label: '확산 감쇠 α (실측 확정값)', type: 'number', step: 'any' },
  { name: 'expand_edges', label: '확산 엣지 (쉼표 구분)', type: 'text', placeholder: 'TAGGED_WITH,CONTAINS_ENTITY,REFERENCES' },
  { name: 'ollama_url', label: 'Ollama URL', type: 'text' },
];

function searchQueryString() {
  const params = new URLSearchParams();
  params.set('q', searchForm.q);
  if (searchForm.top_k) params.set('top_k', String(searchForm.top_k));
  if (searchForm.graph === false) params.set('graph', 'false');
  for (const spec of SEARCH_FIELDS_ADVANCED) {
    if (spec.name === 'graph') continue;  // 위에서 `graph=false` 로만 실어 보낸다
    const value = searchForm[spec.name];
    if (value !== undefined && value !== null && value !== '') params.set(spec.name, String(value));
  }
  return params.toString();
}

function resultCardFor(result) {
  const card = el('div', 'result-card');
  const head = el('div', 'result-head');
  head.appendChild(el('span', 'score-badge', result.score.toFixed(3)));
  head.appendChild(el('span', 'result-title', result.title));
  card.appendChild(head);
  card.appendChild(el('div', 'result-path', result.source_path));
  if (result.tags.length) {
    const tags = el('div');
    for (const tag of result.tags) tags.appendChild(el('span', 'tag-chip', tag));
    card.appendChild(tags);
  }
  if (result.expansion) {
    // 근거 줄은 `build_expansion_evidence()` 가 만든 문자열을 **그대로** 그린다 —
    // v0.7 §4.6 이 정확 문자열까지 못박은 계약이라 프론트가 다시 조립하지 않는다 (§4.6.1).
    card.appendChild(el('div', 'result-evidence', `└ ${result.expansion.evidence}`));
  }
  const actions = el('div', 'result-actions');
  const toWiki = el('button', 'btn', '위키에서 보기');
  toWiki.type = 'button';
  toWiki.addEventListener('click', () => navigateTo('wiki', { doc: result.doc_id }));
  actions.appendChild(toWiki);
  const toGraph = el('button', 'btn', '지식그래프에서 보기');
  toGraph.type = 'button';
  toGraph.addEventListener('click', () => navigateTo('graph', { node: result.doc_id }));
  actions.appendChild(toGraph);
  card.appendChild(actions);
  return card;
}

async function renderSearch(content, generation, params) {
  const initial = params.get('q');
  if (initial !== null) searchForm.q = initial;

  const formCard = el('div', 'card');
  formCard.appendChild(el('div', 'card-title', '지식 검색'));
  const row = el('div', 'search-row');
  const input = el('input');
  input.type = 'search';
  input.value = searchForm.q;
  input.placeholder = '무엇을 찾으시나요';
  input.setAttribute('aria-label', '검색어');
  input.addEventListener('input', () => { searchForm.q = input.value; });
  const submit = el('button', 'btn btn-primary', '검색');
  submit.type = 'button';
  const run = () => {
    if (!searchForm.q.trim()) return;
    navigateTo('search', { q: searchForm.q });
  };
  submit.addEventListener('click', run);
  input.addEventListener('keydown', (event) => { if (event.key === 'Enter') run(); });
  row.appendChild(input);
  row.appendChild(submit);
  formCard.appendChild(row);

  const options = el('div', 'form-grid');
  options.appendChild(field({ name: 'top_k', label: '결과 개수', type: 'number' }, searchForm));
  formCard.appendChild(options);

  const advanced = el('details', 'advanced');
  advanced.appendChild(el('summary', null, '고급'));
  advanced.appendChild(
    el('p', 'advanced-note', '확산 감쇠 α는 실측으로 확정된 값입니다 — 근거 없이 바꾸면 순위의 성질이 무너집니다.')
  );
  const advancedGrid = el('div', 'form-grid');
  for (const spec of SEARCH_FIELDS_ADVANCED) advancedGrid.appendChild(field(spec, searchForm));
  advanced.appendChild(advancedGrid);
  formCard.appendChild(advanced);
  content.appendChild(formCard);

  const results = el('div');
  content.appendChild(results);
  if (!searchForm.q.trim()) {
    results.appendChild(
      emptyState({ title: '검색어를 입력하세요', body: '코사인 상위 문서를 시드로 삼아 그래프로 이어진 문서까지 함께 찾습니다.' })
    );
    return;
  }

  results.appendChild(el('p', 'metric-caption', '검색 중…'));
  const body = await getJson(`/api/search?${searchQueryString()}`);
  if (generation !== renderGeneration) return;
  clear(results);
  if (isError(body)) {
    results.appendChild(
      emptyState({
        title: '검색하지 못했습니다',
        body: body.message,
        actionLabel: '플랜 & 스캔으로',
        actionView: 'scan',
      })
    );
    return;
  }
  if (!body.results.length) {
    // 결과 0건은 예외가 아니라 정상 응답이다 (v0.7 §5).
    results.appendChild(emptyState({ title: '결과 0건', body: '다른 표현으로 다시 찾아보세요.' }));
    return;
  }
  results.appendChild(el('p', 'metric-caption', `검색 결과 ${body.results.length}건`));
  for (const result of body.results) results.appendChild(resultCardFor(result));
}

/* --- 설정 (§4.8 · §4.9 · §4.11) ------------------------------------------------- */

async function renderSettings(content, generation) {
  content.appendChild(el('p', 'metric-caption', '불러오는 중…'));
  const body = await getJson('/api/settings');
  if (generation !== renderGeneration) return;
  clear(content);
  if (isError(body)) {
    content.appendChild(emptyState({ title: '설정을 불러오지 못했습니다', body: body.message }));
    return;
  }

  const grid = el('div', 'bento');

  const consentCard = el('div', 'card');
  consentCard.appendChild(el('div', 'card-title', '클라우드 엔진 동의'));
  if (isError(body.cloud_consent)) {
    consentCard.appendChild(el('p', 'metric-caption', body.cloud_consent.message));
  } else {
    const granted = body.cloud_consent.granted;
    consentCard.appendChild(
      el('p', 'metric-caption', granted
        ? '문서 내용이 외부(Anthropic)로 전송됩니다 — PII 7종은 자동 마스킹됩니다.'
        : '동의하지 않으면 `cloud` 엔진으로 스캔할 수 없습니다.')
    );
    const row = el('div', 'field field-check');
    const toggle = el('input');
    toggle.type = 'checkbox';
    toggle.id = 'field-cloud-consent';
    toggle.checked = granted;
    toggle.addEventListener('change', async () => {
      const result = await postJson('/api/settings', { cloud_consent: toggle.checked });
      if (isError(result)) window.alert(result.message);
      render();
    });
    const label = el('label', 'field-label', 'cloud 엔진(Anthropic API) 사용에 동의');
    label.htmlFor = toggle.id;
    row.appendChild(toggle);
    row.appendChild(label);
    consentCard.appendChild(row);
    // API 키는 GUI에서 입력받지 않는다 (§4.9) — 값이 아니라 「설정되어 있는가」만 보인다.
    consentCard.appendChild(
      el('p', 'metric-caption', 'API 키는 ANTHROPIC_API_KEY 환경변수로만 읽습니다 — 여기서 입력받지 않습니다.')
    );
  }
  grid.appendChild(consentCard);

  const piiCard = el('div', 'card');
  piiCard.appendChild(el('div', 'card-title', `마스킹 대상 ${body.pii_types.length}종`));
  piiCard.appendChild(
    el('p', 'metric-caption', '클라우드로 나가기 전에 자동으로 가려집니다.')
  );
  for (const kind of body.pii_types) {
    // 라벨·플레이스홀더를 프론트가 갖지 않는다 — 코어 `PiiType` 값을 그대로 그린다 (§4.11).
    const row = el('div', 'check-row');
    row.appendChild(el('div', 'check-name', kind.label));
    row.appendChild(el('div', 'check-detail', kind.placeholder));
    piiCard.appendChild(row);
  }
  grid.appendChild(piiCard);

  const fileCard = el('div', 'card');
  fileCard.appendChild(el('div', 'card-title', '설정 파일'));
  fileCard.appendChild(
    el('p', 'metric-caption', '동의와 GUI 설정이 한 파일에 나란히 저장됩니다 — 브라우저에 남기지 않습니다.')
  );
  const row = el('div', 'source-row');
  row.appendChild(el('div', 'source-path', body.config_path));
  row.appendChild(copyButton(body.config_path));
  fileCard.appendChild(row);
  grid.appendChild(fileCard);

  content.appendChild(grid);
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
  clearGraphResizeHandler();
  // 폴더 탐색기는 스캔 화면의 것이다 — 다른 화면으로 갔다가 돌아왔을 때 열린 채로
  // 남아 있으면 사용자가 열지 않은 패널을 보게 된다.
  if (view !== 'scan') browser = null;
  if (view === 'dashboard') {
    await renderDashboard(content, generation);
  } else if (view === 'scan') {
    await renderScan(content, generation);
  } else if (view === 'wiki') {
    await renderWiki(content, generation, params);
  } else if (view === 'graph') {
    await renderGraph(content, generation, params);
  } else if (view === 'search') {
    await renderSearch(content, generation, params);
  } else if (view === 'settings') {
    await renderSettings(content, generation);
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
