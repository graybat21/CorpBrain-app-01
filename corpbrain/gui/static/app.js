/* CorpBrain v0.9 GUI (스펙 §4.8 · 설계 지침 docs/design/corpbrain-v0.9-ui-spec.md).
 *
 * 빌드 없는 Vanilla JS 다. 외부 CDN 을 참조하지 않는다.
 *
 * 토큰은 **첫 진입 URL 에서만** 읽어 메모리에 두고, 읽은 직후 history.replaceState() 로
 * 주소창에서 지운다. 쿠키나 localStorage 에 저장하지 않는다 — 쿠키는 브라우저가 다른 탭의
 * 요청에도 자동으로 붙여 보내 토큰을 둔 목적(CSRF 차단) 자체를 무효로 만든다 (§4.6.1).
 */
(function () {
  "use strict";

  // --- 토큰 (§4.6.1) --------------------------------------------------------

  /* 첫 진입 URL 에서 읽고, **같은 탭 안에서만** sessionStorage 에 이어 둔다.
   *
   * 새로고침할 때마다 토큰을 다시 받아 오라고 하는 것은 쓰기 불편할 뿐 얻는 것이 없다.
   * 중요한 것은 «다른 출처가 이 토큰을 쓸 수 있는가»이고, 그 방어는 **커스텀 헤더**가 한다 —
   * 다른 사이트의 스크립트는 우리 헤더를 붙일 수 없고, sessionStorage 는 출처별로 격리돼
   * 읽을 수도 없다. 쿠키였다면 브라우저가 다른 탭 요청에도 자동으로 붙여 보내 방어가
   * 무너지지만 sessionStorage 는 그렇지 않다.
   *
   * localStorage 가 아니라 sessionStorage 인 이유는 수명이다 — 탭을 닫으면 사라지므로
   * 서버가 꺼진 뒤 죽은 토큰이 디스크에 남지 않는다. */
  var TOKEN_KEY = "corpbrain.token";
  var urlToken = new URLSearchParams(location.search).get("t") || "";
  var TOKEN = urlToken || safeRead(TOKEN_KEY);

  if (urlToken) {
    safeWrite(TOKEN_KEY, urlToken);
    history.replaceState(null, "", location.pathname);
  }

  /* 사생활 보호 모드나 저장소 차단 설정에서는 접근 자체가 예외를 던진다. 그때는 저장을
   * 포기하고 이번 세션만 동작한다 — 화면이 통째로 실패하지 않는다. */
  function safeRead(key) {
    try { return sessionStorage.getItem(key) || ""; } catch (e) { return ""; }
  }
  function safeWrite(key, value) {
    try { sessionStorage.setItem(key, value); } catch (e) { /* 무시 */ }
  }

  function api(path, options) {
    var opts = options || {};
    var headers = { "X-CorpBrain-Token": TOKEN };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    return fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body)
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || ("요청이 실패했습니다 (" + res.status + ")"));
        return data;
      });
    });
  }

  // --- 잡동사니 -------------------------------------------------------------

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text !== undefined) node.textContent = text;   // 언제나 textContent — innerHTML 금지
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  /* 「?」 도움말 아이콘. `index.html` 의 정적 `?` 와 **같은 그림**이어야 하므로 모양을 바꾸면
   * 양쪽을 함께 고친다. 도안은 Feather Icons 의 `help-circle`(MIT).
   *
   * `el()` 로는 만들 수 없다 — SVG 는 HTML 과 다른 네임스페이스라 `createElement` 로 만든
   * 요소는 화면에 그려지지 않는다. `innerHTML` 을 쓰지 않는 이 파일의 규칙도 그대로 지킨다. */
  var SVG_NS = "http://www.w3.org/2000/svg";
  var HELP_ICON = [
    ["circle", { cx: "12", cy: "12", r: "10" }],
    ["path", { d: "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" }],
    ["path", { d: "M12 17h.01" }]
  ];

  function helpIcon() {
    var svg = document.createElementNS(SVG_NS, "svg");
    var attrs = {
      viewBox: "0 0 24 24", width: "15", height: "15", fill: "none",
      stroke: "currentColor", "stroke-width": "1.9",
      "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true"
    };
    Object.keys(attrs).forEach(function (key) { svg.setAttribute(key, attrs[key]); });
    HELP_ICON.forEach(function (spec) {
      var node = document.createElementNS(SVG_NS, spec[0]);
      Object.keys(spec[1]).forEach(function (key) { node.setAttribute(key, spec[1][key]); });
      svg.appendChild(node);
    });
    return svg;
  }

  function toast(message, kind) {
    var box = $("#toast");
    box.textContent = message;
    box.className = "toast " + (kind || "");
    box.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(function () { box.hidden = true; }, 4000);
  }

  // --- 상태 -----------------------------------------------------------------

  var state = { workspaces: [], current: null, wiki: [], selected: null, polling: null };

  // --- 화면 전환 -------------------------------------------------------------

  var TITLES = { explore: "탐색", scan: "스캔", dash: "대시보드", settings: "설정" };

  function show(view) {
    $$(".nav-item").forEach(function (b) {
      if (b.dataset.view === view) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    Object.keys(TITLES).forEach(function (k) {
      $("#v-" + k).classList.toggle("on", k === view);
    });
    $("#viewTitle").textContent = TITLES[view];
    if (view === "dash") loadDashboard();
    if (view === "scan") loadPlan();
    if (view === "settings") loadSettings();
    if (view === "explore") loadWikiTree();
  }

  // --- 워크스페이스 ----------------------------------------------------------

  function loadWorkspaces() {
    return api("/api/workspaces").then(function (data) {
      state.workspaces = data.workspaces || [];
      if (!state.current && state.workspaces.length) state.current = state.workspaces[0];
      renderWorkspaceButton();
      renderWorkspaceList();
      return state.workspaces;
    });
  }

  /* 워크스페이스를 바꾸면 **이전 것의 흔적을 모두 지운다.** 그러지 않으면 앞서 열어 둔
   * 본문·편집 중이던 원고·그래프가 그대로 남아 새 워크스페이스의 내용처럼 보인다.
   * 편집기가 열린 채 남는 것이 특히 위험하다 — 그 상태로 저장하면 **새** 워크스페이스의
   * 같은 경로를 향한다. 지울 곳이 여럿이라 전환 지점마다 되풀이하지 않고 여기로 모은다. */
  function useWorkspace(ws) {
    state.current = ws;
    state.wiki = [];
    graphData = { nodes: [], edges: [] };
    graphView = { scale: 1, ox: 0, oy: 0 };
    installedModels = null;
    openPage = null;
    focusedDocId = null;
    selectedPath = null;
    collapsedDirs = {};
    $("#q").value = "";
    $("#editArea").value = "";
    $("#docTitle").textContent = "문서를 선택하세요";
    clear($("#docBody"));
    $("#docBody").appendChild(
      el("p", { class: "hint" }, "검색 결과를 클릭하면 여기에 본문이 열립니다.")
    );
    $("#editBtn").disabled = true;
    setPane("body");
    clear($("#results"));
    $("#results").appendChild(el("div", { class: "meta" }, "불러오는 중…"));
    $("#scanDone").hidden = true;
    renderWorkspaceButton();
    renderWorkspaceList();
  }

  function renderWorkspaceButton() {
    var label = $("#wsName");
    label.textContent = state.current ? state.current.name : "워크스페이스 없음";
    $("#wsBtn").disabled = state.workspaces.length < 2;
  }

  function renderWorkspaceList() {
    var box = $("#wsList");
    clear(box);
    if (!state.workspaces.length) {
      box.appendChild(el("p", { class: "hint" }, "아직 워크스페이스가 없습니다. 아래에서 추가하세요."));
      return;
    }
    state.workspaces.forEach(function (ws) {
      var row = el("div", { class: "wsrow" });
      var left = el("div");
      left.appendChild(el("div", { style: "font-weight:500" }, ws.name));
      left.appendChild(el("div", { class: "p" }, ws.source_dir + " → " + ws.out_dir));
      row.appendChild(left);

      var actions = el("div", { style: "display:flex;gap:6px" });
      if (state.current && ws.id === state.current.id) {
        actions.appendChild(el("span", { class: "ws-active" }, "활성"));
      } else {
        var open = el("button", { class: "btn" }, "열기");
        open.addEventListener("click", function () {
          useWorkspace(ws);
          show("dash");
        });
        actions.appendChild(open);
      }
      var del = el("button", { class: "btn danger" }, "제거");
      del.addEventListener("click", function () {
        api("/api/workspaces/" + encodeURIComponent(ws.id), { method: "DELETE" })
          .then(function () {
            // 활성 워크스페이스를 지우면 `loadWorkspaces()` 가 다른 것을 활성으로 잡는다 —
            // 화면에 남은 이전 내용이 그 워크스페이스의 것처럼 보이지 않게 함께 지운다.
            if (state.current && state.current.id === ws.id) useWorkspace(null);
            toast("목록에서 제거했습니다. 파일은 그대로 있습니다.");
            return loadWorkspaces();
          })
          .catch(function (e) { toast(e.message, "stop"); });
      });
      actions.appendChild(del);
      row.appendChild(actions);
      box.appendChild(row);
    });
  }

  // --- 폴더 탐색 -------------------------------------------------------------

  var picker = { path: null, target: null };

  function openPicker(targetInput) {
    picker.target = targetInput;
    $("#picker").hidden = false;
    browse(targetInput.value || null);
  }

  function browse(path) {
    var q = path ? "?path=" + encodeURIComponent(path) : "";
    api("/api/fs/list" + q)
      .then(function (data) {
        picker.path = data.path;
        $("#pickerPath").textContent = data.path;
        var list = $("#pickerList");
        clear(list);
        if (data.parent) {
          var up = el("button", { class: "hit" }, "⬆ 상위 폴더");
          up.addEventListener("click", function () { browse(data.parent); });
          list.appendChild(up);
        }
        (data.entries || []).forEach(function (entry) {
          var row = el("button", { class: "hit" }, entry.name);
          row.addEventListener("click", function () { browse(entry.path); });
          list.appendChild(row);
        });
        if (!data.entries.length) {
          list.appendChild(el("p", { class: "hint", style: "padding:12px" }, "하위 폴더가 없습니다."));
        }
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  // --- 대시보드 --------------------------------------------------------------

  /* 엣지 종류 4가지의 뜻. **이름은 그대로 둔다** — 저장소의 `type` 컬럼·`corpbrain graph`
   * 출력·`--expand-edges` 플래그가 모두 이 문자열이라, 화면만 우리말로 바꾸면 어휘가 갈린다.
   * 대신 뜻을 `?` 로 옆에 단다.
   *
   * 넷 중 **둘만 문서와 문서를 직접 잇는다.** 그 사실을 설명에 적는다 — 그러지 않으면
   * 「엣지 71개」인데 그래프 그림에는 선이 두 개뿐인 것이 설명되지 않는다(태그·이름을
   * 거치는 연결은 그림에 문서만 그리므로 나타나지 않는다). */
  var EDGE_HELP = {
    TAGGED_WITH:
      "요약이 뽑은 문서의 주제어(태그)를 문서마다 센 수입니다. 같은 태그가 여러 문서에 "
      + "붙으면 각각 셉니다. 그래프에는 나타나지 않습니다.",
    CONTAINS_ENTITY:
      "문서 안에 나오는 이름(사람·부서·시스템·프로젝트)을 문서마다 센 수입니다. 같은 "
      + "이름이 여러 문서에 나오면 각각 셉니다. 그래프에는 나타나지 않습니다.",
    SEMANTICALLY_SIMILAR:
      "내용이 비슷한 문서끼리 잇습니다. 문서 한 쌍에 하나입니다. 그래프에 나타납니다.",
    REFERENCES:
      "문서 안에 다른 문서의 파일 이름이 그대로 적혀 있을 때 생깁니다. 몇 번 적혔든 문서 "
      + "한 쌍에 하나이고, 서로 적었으면 둘입니다. 그래프에 나타납니다."
  };

  function loadDashboard() {
    if (!state.current) return renderEmptyDash();
    api("/api/workspaces/" + state.current.id + "/dashboard")
      .then(function (data) {
        $("#tWiki").textContent = data.wiki_count;
        $("#tEdges").textContent = data.graph ? data.graph.edges : "0";
        $("#tEntities").textContent = data.graph ? data.graph.entities : "0";
        $("#tLast").textContent = data.last_run ? shortTime(data.last_run.finished_at) : "없음";

        var box = $("#edgeKinds");
        clear(box);
        var kinds = (data.graph && data.graph.edges_by_type) || {};
        if (!Object.keys(kinds).length) {
          box.appendChild(el("p", { class: "hint" }, "아직 그래프가 없습니다. 스캔을 실행하세요."));
        }
        Object.keys(kinds).forEach(function (kind) {
          var row = el("div", { class: "kv" });
          var name = el("span", {}, kind);
          var help = EDGE_HELP[kind];
          if (help) {
            /* `tabindex` 를 주어 키보드로도 설명을 볼 수 있게 한다. `aria-label` 에 설명을
             * 통째로 담는 것은 화면 낭독기에는 `?` 한 글자가 아무 뜻도 없기 때문이다. */
            var mark = el("span", {
              class: "qm", role: "button", tabindex: "0", "aria-expanded": "false",
              "data-tip": help, "aria-label": kind + " 설명: " + help
            });
            mark.appendChild(helpIcon());
            name.appendChild(mark);
          }
          row.appendChild(name);
          row.appendChild(el("span", {}, String(kinds[kind])));
          box.appendChild(row);
        });

        renderSkips($("#dashSkips"), data.last_run);
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  function renderEmptyDash() {
    ["tWiki", "tEdges", "tEntities"].forEach(function (id) { $("#" + id).textContent = "0"; });
    $("#tLast").textContent = "없음";
  }

  function renderSkips(box, lastRun) {
    clear(box);
    var skipped = (lastRun && lastRun.skipped) || [];
    if (!skipped.length) {
      box.appendChild(el("p", { class: "hint" }, "건너뛴 문서가 없습니다."));
      return;
    }
    skipped.forEach(function (item) {
      var row = el("div", { class: "skiprow" });
      row.appendChild(el("span", {}, item.path));
      row.appendChild(el("span", { class: "chip mute" }, item.reason));
      box.appendChild(row);
    });
  }

  function shortTime(iso) {
    if (!iso) return "없음";
    var d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString();
  }

  // --- 스캔 ------------------------------------------------------------------

  function loadPlan() {
    fillOptions();
    refreshModelSelects();

    var box = $("#planBox");
    clear(box);
    if (!state.current) {
      box.appendChild(el("p", { class: "hint" }, "먼저 워크스페이스를 만드세요."));
      return;
    }
    box.appendChild(el("p", { class: "hint" }, "견적을 내는 중…"));
    api("/api/workspaces/" + state.current.id + "/plan")
      .then(function (plan) {
        clear(box);
        [
          ["파일", plan.file_count + "개"],
          ["예상 토큰", plan.total_est_tokens.toLocaleString()],
          ["예상 소요", Math.max(1, Math.round(plan.est_seconds / 60)) + "분"],
          ["하드웨어", plan.hardware.label]
        ].forEach(function (pair) {
          var row = el("div", { class: "kv" });
          row.appendChild(el("span", {}, pair[0]));
          row.appendChild(el("span", {}, pair[1]));
          box.appendChild(row);
        });
        if (plan.gate) {
          appendGate(box, "GPU 게이트", plan.gate.gpu_ok || !plan.gate.gpu_enforced);
          appendGate(box, "토큰 게이트", plan.gate.tokens_ok);
        }
      })
      .catch(function (e) {
        clear(box);
        box.appendChild(el("p", { class: "hint" }, e.message));
      });
  }

  function appendGate(box, label, ok) {
    var row = el("div", { class: "kv" });
    row.appendChild(el("span", {}, label));
    row.appendChild(el("span", { class: "chip " + (ok ? "ok" : "stop") }, ok ? "OK" : "차단"));
    box.appendChild(row);
  }

  /* 저장된 실행 옵션을 폼에 되돌린다 (§4.5).
   *
   * 서버는 `last_options` 를 밑에 깔고 요청으로 덮으므로, **화면이 비어 있어도 저장된 값이
   * 그대로 쓰인다.** 채워 두지 않으면 자리 표시로 보이는 기본값(`50`)과 실제로 도는 값(`100`)이
   * 어긋나고, 사용자가 그 사실을 알 길이 없다.
   *
   * `force`·`force_gates` 는 저장 대상이 아니며(§4.5) 언제나 꺼진 채로 시작한다 — 어제 켠
   * 강제 재생성이 오늘도 켜져 있으면 전체 재요약이 돌아 비용이 예기치 않게 발생한다. */
  function fillOptions() {
    var saved = (state.current && state.current.last_options) || {};
    if (saved.engine) $("#engine").value = saved.engine;
    $$("[data-opt]").forEach(function (input) {
      if (input.type === "checkbox") { input.checked = false; return; }
      var value = saved[input.dataset.opt];
      input.value = value === undefined || value === null ? "" : String(value);
    });
    // 저장된 고급 값이 있으면 접기를 펴 둔다 — 접힌 채로는 채워 넣어도 보이지 않는다.
    var adv = $("details.adv");
    if (adv) {
      adv.open = $$("[data-opt]", adv).some(function (input) {
        return input.type !== "checkbox" && input.value !== "";
      });
    }
  }

  function collectOptions() {
    var options = {};
    var engine = $("#engine").value;
    if (engine) options.engine = engine;
    $$("[data-opt]").forEach(function (input) {
      var key = input.dataset.opt;
      if (input.type === "checkbox") {
        if (input.checked) options[key] = true;
        return;
      }
      var value = input.value.trim();
      if (!value) return;
      options[key] = input.dataset.kind === "number" ? Number(value) : value;
    });
    return options;
  }

  function startScan() {
    if (!state.current) return toast("먼저 워크스페이스를 만드세요.", "warn");
    api("/api/scan", {
      method: "POST",
      body: { workspace_id: state.current.id, options: collectOptions() }
    })
      .then(function () {
        $("#scanForm").hidden = true;
        $("#scanRun").hidden = false;
        $("#scanDone").hidden = true;
        poll();
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  function stopScan() {
    api("/api/scan", { method: "DELETE" })
      .then(function () { toast("중지했습니다. 생성된 위키는 남아 있습니다."); })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  /* 1초 폴링이다 — SSE 를 쓰지 않는다 (§4.3). 문서 1개 요약에 수십 초가 걸리는 작업이라
   * 밀리초 단위 실시간성이 의미가 없고, 폴링은 연결이 끊겨도 다음 요청이 복구한다. */
  function poll() {
    clearTimeout(state.polling);
    api("/api/scan")
      .then(function (status) {
        renderScanStatus(status);
        if (status.running) state.polling = setTimeout(poll, 1000);
        else finishScan(status);
      })
      .catch(function () { state.polling = setTimeout(poll, 2000); });
  }

  function renderScanStatus(status) {
    var snap = status.snapshot || {};
    var total = snap.total || 0;
    var index = snap.index || 0;

    /* 코어는 그래프 단계(패스2·패스3)에 이벤트를 하나도 내지 않는다 (§5). 진행바를
     * 불확정 상태로 바꾸고 무엇을 하는 중인지 말해 준다 — 멈춘 것처럼 보이면 안 된다. */
    var graphPhase = status.phase === "graph";
    $("#runPhase").textContent = graphPhase ? "그래프 만드는 중" : "문서 요약 중";
    $("#progWrap").classList.toggle("indet", graphPhase);
    $("#progBar").style.width = total ? (index / total * 100) + "%" : "0%";
    $("#progCount").textContent = index + " / " + total;
    $("#progEta").textContent = "경과 " + fmt(snap.elapsed || 0);

    var log = $("#runLog");
    clear(log);
    (status.log || []).forEach(function (entry) {
      var row = el("div");
      row.appendChild(el("b", {}, "[" + entry.index + "/" + entry.total + "]"));
      var verb = entry.kind === "file_skipped" ? "스킵 " : "생성 ";
      row.appendChild(document.createTextNode(verb + entry.path));
      log.appendChild(row);
    });
    log.scrollTop = log.scrollHeight;
  }

  function finishScan(status) {
    $("#scanRun").hidden = true;
    $("#scanForm").hidden = false;
    if (!status.record && !status.error) return;
    $("#scanDone").hidden = false;

    var chips = $("#doneChips");
    clear(chips);
    var record = status.record || {};
    if (status.error) {
      chips.appendChild(el("span", { class: "chip stop" }, status.error));
    } else {
      chips.appendChild(el("span", { class: "chip ok" }, "처리 " + (record.generated || []).length + "건"));
      chips.appendChild(el("span", { class: "chip warn" }, "스킵 " + (record.skipped || []).length + "건"));
      if (record.graph) {
        chips.appendChild(el("span", { class: "chip mute" },
          "관련 문서 갱신 " + (record.graph.related_updated_count || 0) + "건"));
      }
    }
    renderSkips($("#doneSkips"), record);
    if (state.current) loadDashboard();
  }

  function fmt(seconds) {
    var s = Math.max(0, Math.floor(seconds));
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  // --- 탐색: 검색 ------------------------------------------------------------

  function search() {
    if (!state.current) return toast("먼저 워크스페이스를 만드세요.", "warn");
    var q = $("#q").value.trim();
    // 검색어를 비우는 것은 목록으로 돌아가는 것이지 열어 둔 문서를 닫는 것이 아니다.
    if (!q) { renderWikiList(); drawGraph(); return; }
    var box = $("#results");
    clear(box);
    box.appendChild(el("div", { class: "meta" }, "검색 중…"));

    api("/api/workspaces/" + state.current.id + "/search?q=" + encodeURIComponent(q))
      .then(function (data) { renderResults(data); })
      .catch(function (e) {
        clear(box);
        box.appendChild(el("div", { class: "meta" }, e.message));
      });
  }

  function renderResults(data) {
    var box = $("#results");
    clear(box);
    var results = data.results || [];
    box.appendChild(el("div", { class: "meta" },
      "결과 " + results.length + "건" + (data.graph_used ? " · 그래프 확산 켜짐" : "")));
    if (!results.length) {
      box.appendChild(el("p", { class: "hint", style: "padding:14px" }, "일치하는 문서가 없습니다."));
      return;
    }
    results.forEach(function (item) {
      var hit = el("button", { class: "hit", "data-doc": item.doc_id });
      var top = el("div", { class: "top" });
      top.appendChild(el("span", { class: "t" }, item.title));
      top.appendChild(el("span", { class: "s" }, item.score.toFixed(3)));
      hit.appendChild(top);
      hit.appendChild(el("div", { class: "p" }, item.source_path));
      if (item.expansion) hit.appendChild(el("div", { class: "why" }, evidence(item)));
      // 표시는 렌더가 끝난 뒤 `markSelection()` 이 한 번에 붙인다.
      hit.addEventListener("click", function () {
        focusedDocId = item.doc_id;
        markSelection();
        openWikiFor(item);          // 위키 경로(`selectedPath`)는 여기서 찾아 채운다
        drawGraph();
      });
      box.appendChild(hit);
    });
    markSelection();
  }

  /* 근거 줄은 v0.6 render.py 의 관용구를 따른다 — 항목을 `·` 로 기계적으로 잇는다.
   * 조사로 문장을 만들지 않는다(라벨 받침에 따라 조사가 갈린다). */
  function evidence(item) {
    var ex = item.expansion;
    var parts = [];
    if (ex.cosine !== null && ex.cosine !== undefined && Math.abs(ex.cosine - item.score) > 1e-9) {
      parts.push("코사인 " + ex.cosine.toFixed(3));
    }
    parts.push("시드 «" + ex.seed_title + "»");
    if (ex.shared_tags && ex.shared_tags.length) parts.push("공유 태그 " + ex.shared_tags.join(", "));
    if (ex.shared_entities && ex.shared_entities.length) {
      parts.push("공유 엔티티 " + ex.shared_entities.join(", "));
    }
    var REF = { outgoing: "시드를 참조함", incoming: "시드가 참조함", mutual: "서로 참조함" };
    if (REF[ex.reference]) parts.push(REF[ex.reference]);
    return parts.join(" · ");
  }

  // --- 탐색: 위키 본문 --------------------------------------------------------

  function loadWikiTree() {
    if (!state.current) return;
    api("/api/workspaces/" + state.current.id + "/wiki")
      .then(function (data) {
        state.wiki = data.entries || [];
        // 검색 전이면 전체 목록을 보여 준다 — 빈 화면은 막다른 길이다.
        if (!$("#q").value.trim()) renderWikiList();
      })
      .catch(function () { state.wiki = []; });
  }

  /* 검색하지 않았을 때의 기본 화면. 「찾기」뿐 아니라 「둘러보기」도 되게 한다. */
  function renderWikiList() {
    var box = $("#results");
    clear(box);
    if (!state.wiki.length) {
      box.appendChild(el("div", { class: "meta" }, "아직 문서가 없습니다"));
      box.appendChild(el("p", { class: "hint", style: "padding:14px" },
        "스캔을 실행하면 여기에 문서가 나옵니다."));
      return;
    }
    box.appendChild(el("div", { class: "meta" }, "문서 " + state.wiki.length + "개"));
    renderTree(box, buildTree(state.wiki), 0);
    markSelection();
  }

  /* 위키 상대경로(`인사/온보딩.md.md`)를 폴더 트리로 접는다. 평면 목록은 줄마다 같은
   * 접두사(`인사/`)를 반복해 읽을 것만 늘렸다. 폴더 이름은 한 번만 적는다. */
  function buildTree(entries) {
    var root = { dirs: {}, files: [], count: 0 };
    entries.forEach(function (entry) {
      var parts = entry.path.split("/");
      parts.pop();                     // 파일 이름은 트리 구조에 쓰지 않는다
      var node = root;
      var prefix = "";
      root.count += 1;
      parts.forEach(function (part) {
        prefix = prefix ? prefix + "/" + part : part;
        if (!node.dirs[part]) {
          node.dirs[part] = { name: part, path: prefix, dirs: {}, files: [], count: 0 };
        }
        node = node.dirs[part];
        node.count += 1;               // 하위 폴더까지 포함한 문서 수
      });
      node.files.push(entry);
    });
    return root;
  }

  /* 폴더 먼저, 그다음 그 폴더에 바로 든 문서. 접힌 폴더는 자식을 그리지 않는다. */
  function renderTree(box, node, depth) {
    Object.keys(node.dirs).sort().forEach(function (key) {
      var dir = node.dirs[key];
      var open = !collapsedDirs[dir.path];
      var row = el("button", {
        class: "dir",
        style: "--depth:" + depth,
        "aria-expanded": String(open)
      });
      row.appendChild(el("span", { class: "caret" }, "▾"));
      row.appendChild(el("span", { class: "n" }, dir.name));
      row.appendChild(el("span", { class: "c" }, String(dir.count)));
      row.addEventListener("click", function () {
        if (collapsedDirs[dir.path]) delete collapsedDirs[dir.path];
        else collapsedDirs[dir.path] = true;
        renderWikiList();              // 접힘 상태는 변수에 있으므로 다시 그려도 남는다
      });
      box.appendChild(row);
      if (open) renderTree(box, dir, depth + 1);
    });
    node.files.forEach(function (entry) {
      var hit = el("button", {
        class: "hit doc",
        style: "--depth:" + depth,
        "data-wiki": entry.path
      });
      hit.appendChild(el("div", { class: "t" }, entry.title || entry.name));
      hit.addEventListener("click", function () {
        selectedPath = entry.path;
        markSelection();
        openWikiByPath(entry.path, entry.title || entry.name);
      });
      box.appendChild(hit);
    });
  }

  /* 선택 표시를 **DOM 에만** 두면 목록이 다시 그려지는 순간 사라진다 — 다른 화면에 갔다
   * 오거나(`show("explore")` → `loadWikiTree()`) 검색을 다시 하면, 본문은 열려 있는데
   * 왼쪽에는 아무것도 골라져 있지 않은 어긋난 상태가 된다. 그래서 «지금 열어 둔 문서»를
   * 변수로 들고(`selectedPath`·`focusedDocId`) 표시는 **언제나 그 변수에서 다시 만든다.**
   *
   * 목록과 검색 결과가 가진 식별자가 다르다 — 목록은 위키 상대경로, 검색 결과는 원문
   * 절대경로다. 둘 다 심어 두고 여기서 함께 맞춘다. */
  function markSelection() {
    $$(".hit").forEach(function (hit) {
      var mine = (hit.dataset.wiki && hit.dataset.wiki === selectedPath)
              || (hit.dataset.doc && hit.dataset.doc === focusedDocId);
      hit.setAttribute("aria-selected", mine ? "true" : "false");
    });
  }

  function openWikiByPath(path, title) {
    api("/api/workspaces/" + state.current.id + "/wiki/"
        + path.split("/").map(encodeURIComponent).join("/"))
      .then(function (page) {
        selectedPath = path;
        focusedDocId = (page.front_matter || {}).source_path || null;
        markSelection();          // 그래프에서 눌러 열었을 때도 목록 표시가 따라온다
        showDoc(title, page.html, page);
        drawGraph();
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  function openWikiFor(item) {
    /* 검색 결과는 원문 절대경로를 준다. 위키 파일명은 「원본이름.확장자.md」이므로
     * 트리에서 접미사로 맞춘다 — 서버에 경로 해석을 넘기지 않는다. */
    var name = item.source_path.replace(/\\/g, "/").split("/").pop();
    var match = state.wiki.filter(function (w) { return w.name === name + ".md"; })[0];
    if (!match) {
      selectedPath = null;
      showDoc(item.title, "<p>이 문서의 위키를 찾지 못했습니다.</p>", null);
      return;
    }
    selectedPath = match.path;
    api("/api/workspaces/" + state.current.id + "/wiki/" + match.path.split("/").map(encodeURIComponent).join("/"))
      .then(function (page) { showDoc(item.title, page.html, page); })
      .catch(function (e) { showDoc(item.title, "", null) || toast(e.message, "stop"); });
  }

  var openPage = null;
  var focusedDocId = null;   // 그래프에서 강조할 문서 (원문 절대경로)
  var selectedPath = null;   // 목록에서 표시할 문서 (위키 상대경로)
  var collapsedDirs = {};    // 접어 둔 폴더 (경로 → true). 다시 그려도 유지된다.

  /* 본문·편집기·그래프는 **한 번에 하나만** 보인다 (스펙 §4.8 — 한 화면에서 «전환»한다).
   * 세 곳이 각자 `hidden` 을 만지던 것을 여기로 모은다. 그러지 않으면 그래프를 보는 중에
   * 문서를 클릭했을 때 본문이 함께 열려, 이미 큰 크기로 그려진 캔버스가 작아진 상자에
   * 갇혀 잘려 보인다 — 캔버스는 자기 픽셀 크기를 그릴 때 정하므로 상자만 줄어든다. */
  function setPane(name) {
    $("#paneBody").hidden = name !== "body";
    $("#editor").hidden = name !== "editor";
    $("#paneGraph").hidden = name !== "graph";
    var pressed = name === "graph" ? "graph" : "body";
    $$(".seg button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.pane === pressed ? "true" : "false");
    });
    if (name === "graph") drawGraph();
  }

  function showDoc(title, html, page) {
    openPage = page;
    $("#docTitle").textContent = title;
    var body = $("#docBody");
    clear(body);
    var wrap = el("div", { class: "body" });
    /* 서버가 이스케이프한 HTML 조각이다 (§4.9) — 원문의 태그는 이미 글자로 바뀌어 있다. */
    wrap.innerHTML = html;
    body.appendChild(wrap);
    $("#editBtn").disabled = !page;
    /* 그래프를 보는 중이면 그 자리에 머문다 — 방금 고른 문서가 노란색으로 바뀌는 것을
     * 보는 것이 그 화면의 목적이다. 본문은 「본문」 버튼으로 넘어간다. */
    setPane($("#paneGraph").hidden ? "body" : "graph");
  }

  function openEditor() {
    if (!openPage) return;
    $("#editArea").value = openPage.raw;
    setPane("editor");
  }

  function saveEditor() {
    if (!openPage) return;
    api("/api/workspaces/" + state.current.id + "/wiki/" + openPage.path.split("/").map(encodeURIComponent).join("/"), {
      method: "PUT",
      body: { raw: $("#editArea").value }
    })
      .then(function (page) {
        toast("저장했습니다. --force 로 재스캔하면 이 내용은 덮입니다.", "warn");
        // 방금 쓴 내용을 바로 보여 준다 — 새로고침해야 반영되면 저장이 안 된 줄 안다.
        if (page.html === undefined) setPane("body");
        else showDoc(page.title || $("#docTitle").textContent, page.html, page);
        loadWikiTree();   // 제목을 고쳤으면 왼쪽 목록에도 반영한다
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  // --- 탐색: 그래프 -----------------------------------------------------------

  var graphData = { nodes: [], edges: [] };

  /* 확대·축소·이동 상태. **배치 계산은 이 값을 모른다** — 확대는 그리는 단계에서만 일어나므로
   * 확대해도 문서 자리가 재계산되지 않고, 되돌리면 원래 그림이 정확히 돌아온다. */
  var graphView = { scale: 1, ox: 0, oy: 0 };
  var MIN_SCALE = 0.4, MAX_SCALE = 4;

  function loadGraph() {
    if (!state.current) return;
    api("/api/workspaces/" + state.current.id + "/graph")
      .then(function (data) { graphData = data; drawGraph(); })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  function cssv(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function drawGraph() {
    var cv = $("#gcv");
    var wrap = cv.parentElement;
    var w = wrap.clientWidth, h = wrap.clientHeight;
    if (!w || !h) return;
    var dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr; cv.height = h * dpr;
    cv.style.width = w + "px"; cv.style.height = h + "px";
    var ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var nodes = graphData.nodes || [];
    if (!nodes.length) {
      // 안내 문구는 확대와 무관하게 늘 같은 크기로 가운데에 둔다.
      ctx.fillStyle = cssv("--ink-3");
      ctx.font = "13px " + cssv("--font-ui");
      ctx.textAlign = "center";
      ctx.fillText("아직 그래프가 없습니다. 스캔을 실행하세요.", w / 2, h / 2);
      return;
    }

    /* 원형 배치다 — 물리 시뮬레이션을 돌리지 않는다. 배치는 노드 순서(차수 내림차순)로
     * 결정되므로 같은 그래프는 언제나 같은 그림이 된다. 조회 화면이 클라이언트에서
     * 파생값을 다시 계산하지 않는다는 불변식과도 맞는다. */
    ctx.save();
    ctx.translate(graphView.ox, graphView.oy);
    ctx.scale(graphView.scale, graphView.scale);

    /* 위아래 띠는 안내문(위)과 범례(아래)가 덮으므로 그림에서 비워 둔다 — 여기에
     * 노드를 놓으면 글자가 안내문 뒤로 숨는다. */
    var padTop = 62, padBottom = 34;
    var band = Math.max(60, h - padTop - padBottom);
    var cx = w / 2, cy = padTop + band / 2;
    /* 라벨을 고리 **바깥**에 두므로 그만큼 자리를 비운다. 노드 바로 위에 두던 종전 방식은
     * 상자가 작아져 고리가 줄면 이웃 노드의 글자와 겹쳤다. */
    var labelRoom = Math.min(160, Math.max(60, w * 0.2));
    var rOuter = Math.max(30, Math.min(w / 2 - labelRoom, band / 2 - 14));

    /* **방사형 배치.** 고른 문서(없으면 연결이 가장 많은 문서)를 가운데 두고, 그 문서와
     * 직접 이어진 문서를 안쪽 고리에, 나머지를 바깥 고리에 놓는다. 다각형 한 겹으로
     * 늘어놓던 종전 배치는 어느 문서가 중심인지 그림이 말해 주지 않았다.
     *
     * 중심 선택도 이웃 판정도 **서버가 준 값**(연결 수 · 엣지)을 읽기만 한다. 화면이
     * 중심성을 다시 계산하지 않는다는 불변식(§4.11)을 지킨다. */
    var center = null;
    nodes.forEach(function (node) { if (node.id === focusedDocId) center = node; });
    if (!center) center = nodes[0];

    var linked = {};
    (graphData.edges || []).forEach(function (edge) {
      if (edge.src === center.id) linked[edge.dst] = true;
      else if (edge.dst === center.id) linked[edge.src] = true;
    });

    var inner = [], outer = [];
    nodes.forEach(function (node) {
      if (node.id === center.id) return;
      (linked[node.id] ? inner : outer).push(node);
    });
    var rInner = inner.length ? rOuter * 0.52 : 0;

    var pos = {};
    pos[center.id] = {
      x: cx, y: cy, angle: Math.PI / 2, radius: 6 + Math.min(6, center.degree), hub: true
    };
    function placeRing(ring, radius) {
      ring.forEach(function (node, i) {
        var angle = (i / ring.length) * Math.PI * 2 - Math.PI / 2;
        pos[node.id] = {
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
          angle: angle,
          radius: 5 + Math.min(5, node.degree)
        };
      });
    }
    placeRing(inner, rInner);
    placeRing(outer, rOuter);

    /* 선은 **곡선**이다. 직선으로 이으면 지름을 가로지르는 선이 수직·수평 막대처럼 보여
     * 그림이 거칠어진다. 가운데에서 바깥으로 휘게 해 선들이 중심에서 뭉치지 않게 한다. */
    ctx.strokeStyle = cssv("--line-2");
    ctx.lineWidth = 1.2;
    (graphData.edges || []).forEach(function (edge) {
      var a = pos[edge.src], b = pos[edge.dst];
      if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      var nx = -dy / len, ny = dx / len;
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      if ((mx - cx) * nx + (my - cy) * ny < 0) { nx = -nx; ny = -ny; }
      var bow = Math.min(28, len * 0.16);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(mx + nx * bow, my + ny * bow, b.x, b.y);
      ctx.stroke();
    });

    /* 노드 사이 간격이 글자 높이보다 좁아지면 라벨은 어떻게 놓아도 겹친다. 그때는
     * 라벨을 접고 **고른 문서 하나만** 남긴다 — 읽히지 않는 글자 더미보다 낫다. */
    var ring = Math.max(1, outer.length || inner.length);
    var gap = (2 * Math.PI * rOuter) / ring;
    var fs = gap < 17 ? 10 : 11.5;
    var showLabels = gap >= fs + 3;
    ctx.font = fs + "px " + cssv("--font-ui");
    ctx.textBaseline = "middle";

    // 고른 문서를 맨 나중에 그려 다른 노드에 덮이지 않게 한다.
    var order = nodes.slice().sort(function (a, b) {
      return (a.id === focusedDocId ? 1 : 0) - (b.id === focusedDocId ? 1 : 0);
    });
    graphHits = [];
    order.forEach(function (node) {
      var p = pos[node.id];
      var focused = node.id === focusedDocId;
      var rad = p.radius + (focused ? 2 : 0);
      ctx.beginPath();
      ctx.arc(p.x, p.y, rad, 0, Math.PI * 2);
      ctx.fillStyle = focused ? cssv("--warn") : cssv("--accent");
      ctx.fill();
      if (focused) {
        ctx.lineWidth = 3;
        ctx.strokeStyle = cssv("--surface");
        ctx.stroke();
      }
      // 클릭 판정에 쓸 자리. 그린 그대로를 담으므로 그림과 어긋날 수 없다.
      graphHits.push({ id: node.id, x: p.x, y: p.y, r: rad + 6 });

      if (!showLabels && !focused && !p.hub) return;
      if (p.hub) {
        // 가운데 노드는 바깥으로 밀 방향이 없다. 점 아래에 가운데 정렬로 적는다.
        ctx.textAlign = "center";
        ctx.fillStyle = focused ? cssv("--warn") : cssv("--ink");
        ctx.fillText(ellipsize(ctx, node.label, rOuter * 1.4), p.x, p.y + rad + 10);
        return;
      }
      var toRight = Math.cos(p.angle) >= 0;
      var lx = p.x + Math.cos(p.angle) * (rad + 6);
      var ly = p.y + Math.sin(p.angle) * (rad + 6);
      ctx.textAlign = toRight ? "left" : "right";
      ctx.fillStyle = focused ? cssv("--warn") : cssv("--ink-2");
      ctx.fillText(ellipsize(ctx, node.label, toRight ? w - lx - 6 : lx - 6), lx, ly);
    });
    ctx.restore();
  }

  /* 마지막으로 그린 노드의 자리. 캔버스에는 클릭할 요소가 없으므로 좌표로 직접 맞힌다. */
  var graphHits = [];

  function nodeAt(event) {
    var cv = $("#gcv");
    var rect = cv.getBoundingClientRect();
    // 화면 좌표를 **그림 좌표**로 되돌린다 — `graphHits` 는 확대 전 좌표를 담고 있다.
    var x = (event.clientX - rect.left - graphView.ox) / graphView.scale;
    var y = (event.clientY - rect.top - graphView.oy) / graphView.scale;
    var best = null, bestDist = Infinity;
    graphHits.forEach(function (hit) {
      var dist = Math.sqrt((x - hit.x) * (x - hit.x) + (y - hit.y) * (y - hit.y));
      if (dist <= hit.r && dist < bestDist) { best = hit; bestDist = dist; }
    });
    return best;
  }

  /* 그래프의 점을 누르면 **옆 목록에서 그 문서를 고른 것과 똑같이** 동작한다 — 본문이
   * 열리고 목록에 표시가 가고 그 점이 노란색이 된다. 그림과 목록이 서로 다른 것을 가리키는
   * 상태를 만들지 않는다. */
  function openGraphNode(docId) {
    var name = docId.replace(/\\/g, "/").split("/").pop();
    var match = state.wiki.filter(function (entry) { return entry.name === name + ".md"; })[0];
    if (!match) {
      focusedDocId = docId;
      drawGraph();
      return toast("이 문서의 위키를 찾지 못했습니다.", "warn");
    }
    openWikiByPath(match.path, match.title || match.name);
  }

  /* 남은 폭에 맞춰 글자를 줄인다 — 잘라 낸 사실은 «…»로 알린다. */
  function ellipsize(ctx, text, maxWidth) {
    if (maxWidth <= 10) return "";
    if (ctx.measureText(text).width <= maxWidth) return text;
    var cut = text;
    while (cut.length > 1 && ctx.measureText(cut + "…").width > maxWidth) {
      cut = cut.slice(0, -1);
    }
    return cut + "…";
  }

  // --- 설치된 모델 목록 -------------------------------------------------------

  var installedModels = null;   // null = 아직 안 받음

  /* 자유 입력 대신 **고르게** 한다 — 오타로 없는 모델을 적어 스캔이 실패하는 일이 사라진다.
   * 응답의 `resolved` 는 «지금 실제로 쓰일 모델»이라, 화면이 「기본값 사용」 같은 항목을
   * 둘 때 그것이 어떤 모델인지 글자로 적을 수 있다. 이름 없는 «기본값»은 확인할 방법이 없다. */
  function loadModels(force) {
    if (installedModels && !force) return Promise.resolve(installedModels);
    var q = state.current ? "?workspace_id=" + encodeURIComponent(state.current.id) : "";
    return api("/api/models" + q)
      .then(function (data) { installedModels = data; return data; })
      .catch(function () {
        installedModels = { models: [], available: false, resolved: {} };
        return installedModels;
      });
  }

  /* 설정 화면용 — **빈 항목을 두지 않는다.** 언제나 구체적인 모델 하나가 선택돼 있다.
   * 「코어 기본값 사용」처럼 이름 없는 항목은 무엇이 골라지는지 알 수 없고, 그 값은 어차피
   * 바로 아래 목록에 이미 들어 있다. */
  function fillConcreteSelect(select, current) {
    var data = installedModels || { models: [] };
    var names = data.models.slice();
    // 지금은 설치돼 있지 않은 모델도 항목으로 남긴다 — 조용히 사라지면 사용자는 자기
    // 설정이 바뀐 줄 모른다.
    if (current && names.indexOf(current) === -1) names.unshift(current);
    clear(select);
    names.forEach(function (name) {
      var installed = data.models.indexOf(name) !== -1;
      select.appendChild(el("option", { value: name },
        installed ? name : name + "  (설치되지 않음)"));
    });
    if (!names.length) select.appendChild(el("option", { value: "" }, "설치된 모델 없음"));
    select.value = current || (names[0] || "");
  }

  /* 고르는 컨트롤 대신 **결과를 보여 준다.** 엔진에 따라 실제로 쓰이는 필드가 다르므로
   * (`model` vs `cloud_model`), 클라우드를 골랐는데 Ollama 모델 이름이 보이면 아무 효과
   * 없는 값을 읽게 된다. */
  function renderEffectiveModel() {
    var target = $("#effectiveModel");
    if (!target) return;
    var resolved = (installedModels && installedModels.resolved) || {};
    var cloud = $("#engine").value === "cloud";
    target.textContent = (cloud ? resolved.cloud_model : resolved.model) || "-";
  }

  function refreshModelSelects() {
    var saved = (state.current && state.current.last_options) || {};
    return loadModels().then(function (data) {
      var resolved = data.resolved || {};
      if ($("#defModel")) {
        fillConcreteSelect($("#defModel"), saved.model || resolved.model || "");
        fillConcreteSelect($("#defEmbed"), saved.embed_model || resolved.embed_model || "");
      }
      renderEffectiveModel();
      /* **잘 되고 있을 때는 아무 말도 하지 않는다.** 목록은 드롭다운을 열면 보이고
       * 새로고침 버튼은 바로 위에 있다 — 개수를 세어 주는 줄은 소음이다.
       * 문제가 있을 때만 자리를 쓴다. */
      var hint = $("#modelsHint");
      if (hint) {
        hint.hidden = data.available;
        hint.textContent = data.available
          ? ""
          : "Ollama 가 응답하지 않아 목록을 받지 못했습니다. 데몬을 띄운 뒤 새로고침하세요.";
      }
      return data;
    });
  }

  // --- 설정 -------------------------------------------------------------------

  var STATUS_LABEL = { ok: "정상", warn: "주의", fail: "해결 필요" };

  /* 상태를 **색으로만** 알리지 않는다 — 칩에 글자가 함께 있고, 막히는 항목은 별도 배너로
   * 한 번 더 말한다. CLI 텍스트를 그대로 뿌리면 OK 와 실패가 같은 줄 모양이라 눈에 안 든다. */
  function renderDoctor(data) {
    var box = $("#doctorBox");
    clear(box);

    var blocking = (data.checks || []).filter(function (c) { return c.blocking; });
    var banner = el("div", { class: "doctor-banner " + (blocking.length ? "bad" : "good") });
    banner.appendChild(el("strong", {},
      blocking.length ? "스캔할 수 없습니다 (" + blocking.length + "건 해결 필요)" : "스캔할 준비가 됐습니다"));
    if (blocking.length) {
      banner.appendChild(el("span", {}, blocking.map(function (c) { return c.label; }).join(" · ")));
    }
    box.appendChild(banner);

    (data.checks || []).forEach(function (c) {
      var row = el("div", { class: "check-row " + c.status });
      var head = el("div", { class: "check-head" });
      head.appendChild(el("span", { class: "chip " + (c.status === "fail" ? "stop" : c.status) },
        STATUS_LABEL[c.status] || c.status));
      head.appendChild(el("span", { class: "check-label" }, c.label));
      if (c.detail) head.appendChild(el("span", { class: "check-detail mono" }, c.detail));
      row.appendChild(head);
      if (c.action) row.appendChild(el("div", { class: "check-action" }, c.action));
      box.appendChild(row);
    });

  }


  function loadSettings() {
    refreshModelSelects();

    var box = $("#doctorBox");
    clear(box);
    box.appendChild(el("p", { class: "hint" }, "점검 중…"));
    /* 점검할 모델을 함께 넘긴다 — 안 넘기면 코어 기본값을 확인해, 다른 모델을 받아 둔
     * 사용자에게 「모델 없음」이라고 잘못 알린다. */
    var q = state.current ? "?workspace_id=" + encodeURIComponent(state.current.id) : "";
    api("/api/doctor" + q)
      .then(function (data) { renderDoctor(data); })
      .catch(function (e) { clear(box); box.appendChild(el("p", { class: "hint" }, e.message)); });

    api("/api/settings/cloud")
      .then(function (data) {
        var list = $("#cloudNotices");
        clear(list);
        (data.notices || []).forEach(function (line) { list.appendChild(el("li", {}, line)); });
        $("#cloudState").textContent = "현재 상태: " + (data.granted ? "동의함" : "동의 없음");
        $("#cloudBtn").textContent = data.granted ? "동의 철회" : "동의하고 켜기";
        $("#cloudBtn").dataset.next = data.granted ? "revoke" : "grant";
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  /* 스캔을 돌리지 않고도 모델을 저장한다. 그러지 않으면 «스캔이 실패해 옵션이 저장되지
   * 않고 → 점검은 계속 기본 모델을 보고 → 원인을 알 수 없는» 순환에 갇힌다. */
  function saveModels() {
    if (!state.current) return toast("먼저 워크스페이스를 만드세요.", "warn");
    var options = {};
    var model = $("#defModel").value.trim();
    var embed = $("#defEmbed").value.trim();
    if (model) options.model = model;
    if (embed) options.embed_model = embed;
    api("/api/workspaces/" + state.current.id + "/options", { method: "PUT", body: options })
      .then(function (ws) {
        state.current = ws;
        renderIndexWarning(ws.index);
        toast("모델을 저장했습니다.");
        loadSettings();
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  /* **미리 겁주지 않는다.** 검색용 모델을 실제로 바꿔 기존 검색 데이터를 못 쓰게 됐을
   * 때만 나타나고, 그때 할 수 있는 일을 버튼으로 준다. 코어의 안내는 `--force` 같은 CLI
   * 문구라 화면에 그대로 내보내면 쓸모가 없다. */
  function renderIndexWarning(index) {
    var box = $("#embedWarning");
    if (!box) return;
    if (!index || !index.rebuild_required) { box.hidden = true; return; }
    $("#embedWarningText").textContent =
      "지금까지 만든 검색 데이터는 이전 모델(" + (index.model || "알 수 없음")
      + ")로 만든 것이라 함께 쓸 수 없습니다. 다시 만들어야 검색이 동작합니다.";
    box.hidden = false;
  }

  function rebuildIndex() {
    if (!state.current) return;
    api("/api/workspaces/" + state.current.id + "/index", { method: "DELETE" })
      .then(function () {
        $("#embedWarning").hidden = true;
        toast("지웠습니다. 스캔을 한 번 돌리면 새 모델로 다시 만들어집니다.");
        show("scan");
      })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  function toggleCloud() {
    var grant = $("#cloudBtn").dataset.next === "grant";
    api("/api/settings/cloud", { method: "PUT", body: { granted: grant } })
      .then(function () { loadSettings(); toast(grant ? "동의를 기록했습니다." : "동의를 철회했습니다."); })
      .catch(function (e) { toast(e.message, "stop"); });
  }

  // --- 배선 -------------------------------------------------------------------

  function init() {
    $$(".nav-item").forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.view); });
    });

    $("#themeBtn").addEventListener("click", function () {
      var root = document.documentElement;
      var cur = root.getAttribute("data-theme");
      if (!cur) cur = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      root.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
      drawGraph();
    });

    $("#wsBtn").addEventListener("click", function () { show("settings"); });
    $("#searchBtn").addEventListener("click", search);
    $("#q").addEventListener("keydown", function (e) { if (e.key === "Enter") search(); });
    $("#engine").addEventListener("change", renderEffectiveModel);
    // 「설정에서 바꾸세요」라고 말하는 대신 데려다준다.
    $("#goSettings").addEventListener("click", function () { show("settings"); });
    $("#runBtn").addEventListener("click", startScan);
    $("#stopBtn").addEventListener("click", stopScan);
    $("#editBtn").addEventListener("click", openEditor);
    $("#saveBtn").addEventListener("click", saveEditor);
    $("#cancelEdit").addEventListener("click", function () { setPane("body"); });

    /* 본문의 「바로가기」 — 브라우저는 `file://` 로 갈 수 없으므로 서버가 대신 폴더를 연다.
     * 본문은 문서를 열 때마다 새로 만들어지므로 버튼 하나하나에 붙이지 않고 위임한다. */
    $("#docBody").addEventListener("click", function (event) {
      var button = event.target.closest(".reveal");
      if (!button || !state.current) return;
      api("/api/workspaces/" + state.current.id + "/reveal",
          { method: "POST", body: { path: button.dataset.path } })
        .then(function (data) {
          toast(data.selected ? "원본이 있는 폴더를 열었습니다."
                              : "원본은 없지만 그 폴더를 열었습니다.", data.selected ? "" : "warn");
        })
        .catch(function (e) { toast(e.message, "stop"); });
    });
    $("#cloudBtn").addEventListener("click", toggleCloud);
    $("#saveModels").addEventListener("click", saveModels);
    $("#rebuildIndex").addEventListener("click", rebuildIndex);
    $("#reloadModels").addEventListener("click", function () {
      loadModels(true).then(refreshModelSelects).then(function () {
        toast("모델 목록을 다시 받았습니다.");
      });
    });

    $$(".seg button").forEach(function (b) {
      b.addEventListener("click", function () {
        var graph = b.dataset.pane === "graph";
        setPane(graph ? "graph" : "body");
        if (graph) loadGraph();
      });
    });

    $("#browseSource").addEventListener("click", function () { openPicker($("#newSource")); });
    $("#browseOut").addEventListener("click", function () { openPicker($("#newOut")); });
    $("#pickerPick").addEventListener("click", function () {
      if (picker.target && picker.path) picker.target.value = picker.path;
      $("#picker").hidden = true;
    });
    $("#pickerClose").addEventListener("click", function () { $("#picker").hidden = true; });

    $("#addWs").addEventListener("click", function () {
      api("/api/workspaces", {
        method: "POST",
        body: {
          name: $("#newName").value.trim(),
          source_dir: $("#newSource").value.trim(),
          out_dir: $("#newOut").value.trim()
        }
      })
        .then(function (ws) {
          useWorkspace(ws);
          $("#newName").value = ""; $("#newSource").value = ""; $("#newOut").value = "";
          toast("워크스페이스를 추가했습니다.");
          // 설정 화면에 머무르므로 여기서 다시 그린다 — 이전 워크스페이스의 모델·경고가
          // 새 워크스페이스의 것처럼 남아 있지 않게 한다.
          return loadWorkspaces().then(loadSettings);
        })
        .catch(function (e) { toast(e.message, "stop"); });
    });

    /* 점을 누르면 그 문서를 연다. 누를 수 있다는 것이 보이도록 커서를 바꾼다 — 캔버스는
     * 그림 한 장이라 브라우저가 대신 알려 주지 못한다. */
    var gcv = $("#gcv");
    var drag = null, dragged = false;

    gcv.addEventListener("click", function (event) {
      // 끌어서 옮긴 것은 클릭이 아니다 — 이동을 마칠 때마다 문서가 열리면 안 된다.
      if (dragged) { dragged = false; return; }
      var hit = nodeAt(event);
      if (hit) openGraphNode(hit.id);
    });

    /* **휠로 확대·축소.** 커서가 가리키는 지점을 고정하고 그 둘레가 늘고 줄게 한다 —
     * 화면 한가운데를 기준으로 하면 보고 있던 곳이 시야 밖으로 밀려난다.
     * `passive:false` 로 잡아 페이지가 함께 스크롤되지 않게 한다. */
    gcv.addEventListener("wheel", function (event) {
      event.preventDefault();
      var rect = this.getBoundingClientRect();
      var mx = event.clientX - rect.left, my = event.clientY - rect.top;
      var next = Math.min(MAX_SCALE, Math.max(MIN_SCALE,
        graphView.scale * (event.deltaY < 0 ? 1.12 : 1 / 1.12)));
      var k = next / graphView.scale;      // 한계에 닿았으면 1 이 되어 아무 일도 일어나지 않는다
      graphView.ox = mx - (mx - graphView.ox) * k;
      graphView.oy = my - (my - graphView.oy) * k;
      graphView.scale = next;
      drawGraph();
    }, { passive: false });

    // 끌어서 이동. 확대하면 그림이 화면을 넘어가므로 옮길 수 있어야 한다.
    gcv.addEventListener("mousedown", function (event) {
      drag = { x: event.clientX, y: event.clientY, ox: graphView.ox, oy: graphView.oy };
      dragged = false;
    });
    window.addEventListener("mousemove", function (event) {
      if (!drag) return;
      var dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!dragged && Math.abs(dx) + Math.abs(dy) <= 3) return;   // 손떨림은 클릭으로 둔다
      dragged = true;
      graphView.ox = drag.ox + dx;
      graphView.oy = drag.oy + dy;
      drawGraph();
    });
    window.addEventListener("mouseup", function () { drag = null; });

    gcv.addEventListener("mousemove", function (event) {
      this.style.cursor = drag ? "grabbing" : (nodeAt(event) ? "pointer" : "grab");
    });

    // 빈 곳을 두 번 누르면 처음 크기로. 점 위에서는 문서를 여는 동작이 우선이다.
    gcv.addEventListener("dblclick", function (event) {
      if (nodeAt(event)) return;
      graphView = { scale: 1, ox: 0, oy: 0 };
      drawGraph();
    });

    /* 「?」 도움말은 **호버에만 의존하지 않는다** (ui-ux-pro-max · Hover vs Tap).
     * 터치 기기에는 호버가 없고, 마우스를 오래 얹기 어려운 사용자도 있다. 클릭·Enter·Space
     * 로 여닫고 Esc 나 바깥 클릭으로 닫는다. 화면 어디에서 만들어진 `?` 든 같게 동작하도록
     * 문서 한 곳에 위임한다. */
    function closeTips(except) {
      $$(".qm").forEach(function (node) {
        if (node !== except) node.setAttribute("aria-expanded", "false");
      });
    }
    document.addEventListener("click", function (event) {
      var qm = event.target.closest && event.target.closest(".qm");
      closeTips(qm);
      if (!qm) return;
      // 라벨 안에 있는 `?` 를 눌렀을 때 입력칸이 함께 활성화되지 않게 한다.
      event.preventDefault();
      qm.setAttribute("aria-expanded", qm.getAttribute("aria-expanded") === "true" ? "false" : "true");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") return closeTips(null);
      var active = document.activeElement;
      if (!active || !active.classList || !active.classList.contains("qm")) return;
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      closeTips(active);
      active.setAttribute("aria-expanded", active.getAttribute("aria-expanded") === "true" ? "false" : "true");
    });

    window.addEventListener("resize", drawGraph);
    /* 창뿐 아니라 **상자** 크기가 바뀌어도 다시 그린다. 캔버스는 그릴 때의 크기를 픽셀로
     * 굳히므로, 다시 그리지 않으면 이전 크기 그대로 남아 잘려 보인다. */
    if (window.ResizeObserver) new ResizeObserver(drawGraph).observe($("#paneGraph"));

    if (!TOKEN) {
      toast("접속 토큰이 없습니다. 터미널에 찍힌 주소로 다시 들어오세요.", "stop");
    }

    loadWorkspaces()
      .then(function (list) { show(list.length ? "dash" : "settings"); })
      .catch(function (e) { toast(e.message, "stop"); show("settings"); });

    // 서버가 재시작되지 않았다면 진행 중인 스캔이 있을 수 있다.
    api("/api/scan").then(function (status) {
      if (status && status.running) { show("scan"); $("#scanForm").hidden = true; $("#scanRun").hidden = false; poll(); }
    }).catch(function () {});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
