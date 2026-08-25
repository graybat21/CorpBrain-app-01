---
target: gui_preview/index.html
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-08-24T09-53-28Z
slug: gui-preview-index-html
---
Method: dual-agent (A: independent design-review subagent · B: independent detector+evidence subagent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2/4 | Scan view has an excellent live log stream, but Knowledge Graph fails silently (no spinner/error/empty-state) and the top tab bar doesn't update when Settings opens via the sidebar. |
| 2 | Match System / Real World | 3/4 | Domain vocabulary fits an enterprise-IT/security audience; a few terms (NetworkGuard, 게이트 판정) are never defined inline. |
| 3 | User Control and Freedom | 2/4 | No cancel for an in-progress scan; "새 프로젝트 추가" uses a raw browser `prompt()`/`alert()`. |
| 4 | Consistency and Standards | 2/4 | Visual system is consistent, but nav items mix real `<button>`s with `<div>`/`<li>`/`<span>` + onclick, and the tab/sidebar active-state desyncs on Settings. |
| 5 | Error Prevention | 3/4 | Live PII-masking preview shows exactly what would leak before anything is sent; cloud opt-in has explicit granted/revoked state. |
| 6 | Recognition Rather Than Recall | 3/4 | Every nav item pairs icon + label; tabs show live counts; search offers suggestion chips. |
| 7 | Flexibility and Efficiency of Use | 1/4 | No keyboard shortcuts, no bulk actions across projects/wiki tree, no skip-straight-to-scan path. |
| 8 | Aesthetic and Minimalist Design | 3/4 | Chunking is disciplined (≤4 per group), but every metric tile carries an equally strong colored accent, so nothing reads as more important than anything else. |
| 9 | Error Recovery | 1/4 | No error state exists anywhere in the mockup; the one real failure (blank Knowledge Graph) produces no message at all. |
| 10 | Help and Documentation | 0/4 | No help affordance, tooltip, onboarding, or docs link in any of the 6 views. |
| **Total** | | **20/40** | **Acceptable — bottom of band, borderline Poor** |

## Design Specificity Verdict

**LLM assessment**: The *content* is unmistakably CorpBrain-specific — the "100% Local Guard / 127.0.0.1" footer, Ollama/GPU/embedding status cards, a live PII-masking tester with real Korean regex categories, per-document PII masking history, and a pipeline log that narrates extract→Ollama 요약→PII 검사→벡터 임베딩 stage by stage. But the *shell* — dark glassmorphism, cyan/emerald/purple gradient accents, pulsing glow dots, rounded cards with colored top bars, pills everywhere — is the same generic "AI dashboard" language currently blanketing every local-LLM tool mockup. Strip the Korean copy and this shell is interchangeable with a crypto dashboard or any other dark-mode SaaS. Worse, the neon-glow glass aesthetic reads as more "cloud platform" than "private, on-device tool" — working against the product's actual pitch.

**Deterministic scan**: 5 findings (detector ran in a degraded/regex-only mode — HTML parser modules unavailable, so this is an undercount): `flat-type-hierarchy` (index.html:131 area — font sizes cluster tightly at 11/12/13px), `dark-glow` (index.html:68 — zero-offset cyan box-shadow on a status dot), `side-tab` ×2 (style.css:723 key-points left-accent bar; style.css:618 metric-card top-accent stripe), `gradient-text` (style.css:131 — gradient-clipped "CorpBrain" wordmark). These give precise file:line evidence for exactly the "generic AI-dashboard skin" pattern the design review called out qualitatively — strong agreement between the two assessments. Two are borderline mislabels rather than clean false positives: the style.css:618 "side-tab" hit is actually a **top**-edge stripe, not the canonical side accent bar the rule targets, and the dark-glow hit is a tiny 6px dot glow, much smaller than the rule's "chromatic halo" framing implies.

**Visual overlays**: Not available — the only browser automation in this environment (Orca computer-use) cannot inject scripts or read console output, so no user-visible overlay was produced. Findings above come from direct source reading plus manual screenshot review in a real browser window (all 6 screens), not a verified in-page overlay.

## Overall Impression

The product thinking is genuinely strong and specific — this doesn't read like a template, it reads like someone who understands local-first AI tooling. But the execution has one real showstopper (a badge-`v0.6`, flagship feature that silently renders blank), a foundational accessibility gap (effectively zero keyboard navigation), and a visual skin that actively undercuts the "private, local, trustworthy" pitch by looking like every other neon-glow AI SaaS dashboard. The biggest opportunity: keep every product-specific detail exactly as-is, and put it inside a shell that feels like it belongs on someone's own machine rather than in someone else's cloud.

## What's Working

1. **Live pipeline log stream in Plan & Scan** — color-coded by stage, timestamped, auto-scrolling; narrates the actual local pipeline instead of hiding it behind a generic spinner, which builds trust for a privacy-first tool.
2. **Real-time PII masking tester in Settings** — lets the user type text and watch the exact masking regex fire live. Rare case of a UI element that demonstrates the core promise instead of just claiming it.
3. **Wiki reader's frontmatter box + PII masking history panel** — grounds an abstract "your data was protected" claim in concrete per-document artifacts (engine, model, generated_at, PII count).

## Priority Issues

**[P0] Knowledge Graph view renders completely blank** — What: Clicking 지식그래프 (badged v0.6, positioned as the flagship new feature) shows only the toolbar and legend; the canvas has zero nodes/edges despite the legend correctly reporting 8 document nodes / 5 entity nodes / 4 tags, and despite the dashboard elsewhere reporting 170/342 nodes/edges for the project. **Independently confirmed by both assessments** (design review and detector/evidence pass reached this screen separately and both found it blank). Why it matters: this is the screen most likely to be shown to a stakeholder to justify the v0.6 badge, and it fails with zero error signal — a user can't tell "broken" from "this project has zero nodes." Likely root cause: `initGraphCanvas()`/`resize()` in `gui_preview/app.js` (~lines 589-601) reads `canvas.parentElement.getBoundingClientRect()` while `.view-graph` is still `display:none` on first load, seeding `transform.x/y` from a 0×0 rect. Fix: fix the resize/centering timing, and add a visible loading/error/empty state so this can never fail silently again. Suggested command: `/impeccable harden`.

**[P1] Primary navigation is keyboard-inaccessible** — What: Top tab bar, sidebar project cards, wiki tree entries, search suggestion chips, and graph node pills are all plain `<div>`/`<li>`/`<span>` with only an onclick — no `<button>`/`<a>`, no `tabindex`, no `role`, no keydown handling. Why it matters: a keyboard-only or screen-reader user cannot reach or activate any core navigation — not the 6 main tabs, not the project switcher, not a single wiki document. For a tool headed toward a desktop app, this is foundational. Fix: convert to real `<button>` elements (or `role="button" tabindex="0"` + Enter/Space handling) app-wide. Suggested command: `/impeccable harden`.

**[P1] Navigation state desyncs between sidebar and top tabs** — What: Opening Settings via the sidebar footer correctly shows the Settings view and highlights the sidebar item, but the top tab bar keeps whichever tab was previously active — two contradictory "you are here" signals on screen at once. **Independently confirmed by both assessments.** Why it matters: this directly breaks visibility of system status/location, the exact job a tab bar exists to do. Fix: in `switchView()` (`app.js` ~line 407), explicitly clear top-tab active state when the target view isn't one of the 5 tabbed views. Suggested command: `/impeccable clarify`.

**[P2] Scan configuration screen exceeds working-memory limits before any action** — What: 4 form fields + 3 gate-toggle checkboxes + 2 primary buttons (Plan / Scan) are all visible and undifferentiated in one block. Why it matters: 9 simultaneous decision points at one screen is well past the ≤4 working-memory guideline, and mixes "configure" with "gate review" with "commit to run" into one undifferentiated step. Fix: collapse the 3 gate toggles into a de-emphasized "고급 게이트 설정" disclosure; visually separate configure → plan → execute into a lighter 3-stage flow. Suggested command: `/impeccable distill`.

**[P3] Contrast and undifferentiated card emphasis** — What: `--text-muted` (#64748b) on `--bg-primary` (#0a0e14) computes to ~4.07:1, just under WCAG AA's 4.5:1, and is used at the smallest sizes (10-11px timestamps, branch pills, doctor-card subtext) — corroborated by the detector's `flat-type-hierarchy` finding (sizes cluster at 11/12/13px). All four dashboard metric tiles carry an equally strong colored top-accent bar/glow (detector: `side-tab`/`dark-glow`), so hierarchy comes from position only, not weight. Fix: lift muted text to a lighter token or larger size; reserve full-saturation accent for one "most important" metric per screen. Suggested command: `/impeccable polish`.

## Persona Red Flags

**Alex (Power User)**: No keyboard shortcuts anywhere in a tool built for repeat, expert daily use. Switching between the 4 sidebar projects requires a mouse click every time. "새 로컬 프로젝트 폴더 열기" drops into a raw browser `prompt()`/`alert()` — reads as unfinished to an expert deciding whether to trust the tool with real folders. Scan always requires two full clicks (Plan, then Scan) with no skip-to-confirmed-run path.

**Sam (Accessibility-dependent)**: Cannot Tab into the top tab bar, sidebar project list, or wiki document tree at all (see P1). No `:focus-visible` style is defined anywhere beyond native input/select/button defaults, so even the few real `<button>` elements have no confirmed visible focus ring. `text-muted` at 10-11px sits below AA contrast.

**Riley (Stress Tester)**: Knowledge Graph (P0) is a clean "looks like it works, silently doesn't" failure — legend claims nodes exist, canvas shows nothing, zoom/reset produce no observable change. Settings-via-sidebar leaves the top-tab breadcrumb pointing at the wrong tab (P1), so a methodical tester refreshing their mental model of "where am I" gets an actively wrong answer.

## Minor Observations

- Emoji-as-icon system (🧠🔍📁⚙️🦙⚡📐☁️) is charming and on-brand but has no fallback; rendering will vary across OS/browser emoji sets.
- The mocked "폴더가 워크스페이스에 등록되었습니다" success message after the `prompt()` add-folder flow implies validation that never happens — for a tool whose entire pitch is careful local file handling, a fake-success message here undercuts trust more than most products would suffer from the same shortcut.
- Sidebar project names like "Legal-Compliance-2026" are already visually tight; no truncation/ellipsis behavior visible for longer real folder names.
- Plan & Scan's idle state leaves roughly the bottom 70% of the viewport empty before a scan is triggered — no placeholder content softens the wait for "configure, then act."
- The Plan report table was only exercised with 5 rows; nothing shows how it behaves near the CLI spec's 50-file cap (pagination/scroll/virtualization untested by the design).
- "⚡ 빠른 스캔" in the header jumps to Scan from anywhere, but there's no equivalent one-click shortcut back to Search or Graph from elsewhere.

## Questions to Consider

1. The Knowledge Graph is the one feature badged v0.6 and put front-and-center in the nav — if it's the reason someone opens this app, what does it say that it's the view most likely to look broken?
2. If not a single piece of primary navigation can be reached by keyboard, is this really being designed as a desktop app shell, or as a website that happens to look like one — and does that gap need closing before implementation starts?
3. CorpBrain's entire pitch is "100% local, we handle your data carefully" — is a raw browser `prompt()` dialog for adding a folder, and a knowledge graph that silently shows nothing, the first impression you want anyone evaluating that pitch to walk away with?
