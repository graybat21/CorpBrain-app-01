---
target: gui_preview_minimalist/index.html
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
timestamp: 2026-08-25T01-02-23Z
slug: gui-preview-minimalist-index-html
---
Method: dual-agent (A: independent design-review subagent · B: independent detector+evidence subagent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3/4 | Strong live progress/log stream, but Settings has a weak "you are here" signal and a stale graph inspector after a project switch. |
| 2 | Match System / Real World | 3/4 | Domain-correct copy/icons throughout; a few AI/infra terms (RAG, 코사인 유사도) still assume literacy. |
| 3 | User Control and Freedom | 2/4 | No cancel on an active scan; "새 프로젝트 폴더 열기" still drops into native `prompt()`/`alert()`. |
| 4 | Consistency and Standards | 3/4 | Disciplined token system now, undercut by top-tab vs. sidebar-footer active-state weight mismatch and native dialogs. |
| 5 | Error Prevention | 3/4 | Pre-Scan "Plan" dry run (gate PASS/FAIL + token estimate, "LLM/네트워크 0회") is a strong preventive pattern. |
| 6 | Recognition Rather Than Recall | 4/4 | Live tab-count badges, co-located wiki tree/reader/context, graph inspector surfaces neighbors inline. |
| 7 | Flexibility and Efficiency of Use | 2/4 | Keyboard tab/Enter now works app-wide (verified live), but still no bulk actions or documented shortcuts beyond one "빠른 스캔". |
| 8 | Aesthetic and Minimalist Design | 4/4 | Restrained palette, no gradients/glow, pastel semantic coding matches the graph legend to the canvas exactly. |
| 9 | Error Recovery | 1/4 | Still no failure/skip/precondition-failed state anywhere — only the 100%-success path is shown. |
| 10 | Help and Documentation | 1/4 | No tooltips or contextual docs; jargon like "게이트 판정" remains unexplained. |
| **Total** | | **26/40** | **Acceptable** (up from 20/40) |

## Design Specificity Verdict

**LLM assessment**: The composition is clearly authored for this product now, not a reskinned generic dashboard — the sidebar's real branch pills, the persistent "100% Local Guard / 127.0.0.1" indicator, the Plan step's explicit "LLM/네트워크 0회" copy, a Settings PII tester wired to real regex logic (not a static mock), and a genuinely-working force-directed Knowledge Graph. The one place genericness survives: the Dashboard's icon-chip + label + big-number + description stat-tile pattern is still a familiar "admin dashboard" shape even with the left-accent border removed and specific copy — a structural, not just decorative, genericness.

**Deterministic scan**: Only 1 finding this run (down from 5), and it's a likely false positive: `flat-type-hierarchy` at `index.html:133`, anchored on one inline `font-size:10px` span. Both assessments independently concluded this is an artifact of the detector's DEGRADED regex-fallback mode sampling a narrow local window rather than the file's real type scale, which does show clear steps elsewhere (10/11/12/13/14px small text through 16/17/19px sub-headers up to 26/30px numerals/headings). The `side-tab` (×2) and `layout-transition` findings from the prior run are confirmed gone in source: `.metric-box`/`.key-points-box` now carry plain `border: 1px solid var(--border)` with no accent, and `.progress-bar-fill` now animates via `transform: scaleX()` not `width`.

**Visual overlays**: Still not available — same tooling limitation as the first pass (Orca computer-use can't inject scripts or read console). Findings come from source reading plus live manual screenshot review of all 6 screens.

## Overall Impression

This is a real turnaround from the first pass: the flagship Knowledge Graph feature actually works now (physics settle, zoom/pan respond, node inspector opens with live data), keyboard access is verified working app-wide with a visible focus ring, and the generic "AI dashboard" accent-border tell is gone. Score moved from 20/40 (Acceptable, bottom of band) to 26/40 (solidly Acceptable). What's left is smaller and more specific: a data-integrity gap when switching projects with the graph inspector open, a complete absence of any failure/skip state despite the underlying spec requiring one, and a couple of loose ends (native dialogs, unstyled PII placeholders in the wiki body) that don't match the polish already achieved elsewhere.

## What's Working

1. **Knowledge Graph is genuinely fixed** — both assessments independently confirmed nodes render bounded and settled, zoom/pan/center controls visibly work, and clicking a node opens a working inspector. A real turnaround from the previous blank canvas.
2. **Pre-Scan "Plan" dry run** — explicit "LLM/네트워크 0회" copy plus a gate PASS/FAIL table lets users preview cost/risk before committing, a trust-building pattern specific to a privacy-first local tool.
3. **Keyboard accessibility is verified live, not just in source** — Tab reaches the top nav, Enter activates it, and a visible cyan focus ring appears, confirmed both by reading `makeActivatable()`'s 7 call sites in code and by direct keyboard interaction in the browser.

## Priority Issues

**[P1] Stale Knowledge Graph inspector state survives a project switch** — What: Switching projects via the sidebar while the graph inspector is open reloads the canvas correctly but leaves the inspector showing the *previous* project's selected node — reproduced live (switching CorpBrain-app-01 → CorpBrain-app left "CorpBrain 아키텍처" / "Ollama Engine" displayed, though neither exists in the new 4-node graph). **Independently corroborated**: Assessment B, gathering evidence with no knowledge of this finding, separately logged an incidental observation of the sidebar's selected project changing mid-session with stale panel content, flagged "for the coordinator's awareness." Why it matters: a user could click through to a document that belongs to the wrong project — a real trust break for a knowledge tool. Fix: reset/close the inspector (`AppState.selectedNode = null`, hide `.graph-inspector-panel`) inside `switchProject()` before calling `updateGraphDataset()`. Suggested command: `/impeccable harden`.

**[P2] No failure or skip state is represented anywhere** — What: All six screens show only the 100%-success path; the scan log always ends "총 5개 파일 스캔 완료." Why it matters: the backing spec requires a skip report with reasons (unsupported/empty/permission-denied/oversized files) and a non-zero exit on Ollama-not-detected — partial failure is the norm for this tool, not the edge case, yet the reference UI never shows it, so nobody has designed for it. Fix: add a collapsible "N개 스킵 ⚠" row with reasons to the scan progress card, and a precondition-failure state. Suggested command: `/impeccable clarify`.

**[P2] Settings has a weak "current location" signal** — What: The sidebar-footer Settings link's active pastel-lilac pill is far weaker than the top-tab's bold ink underline+background, and reads faintly against white. Why it matters: after a few navigation hops, users can lose track of where they are (heuristic 1). Fix: give the footer active state visual parity with top-tab weight, or add a small breadcrumb in the header. Suggested command: `/impeccable clarify`.

**[P3] No cancel affordance during an active scan, and folder-add still uses native browser dialogs** — What: Once a scan runs, only the trigger button disables — no cancel control; "새 로컬 프로젝트 폴더 열기" still drops into `window.prompt()`/`alert()`, breaking the custom UI at the moment users create new state. Fix: add a cancel button to the progress card; replace prompt/alert with an in-system modal. Suggested command: `/impeccable harden`.

**[P3] PII placeholder tokens render unstyled in the Wiki reader body** — What: `.pii-highlight` exists and works in the Settings tester, but `renderWikiDetail()` never applies it — the wiki document body shows raw `[PII: 휴대전화번호:001]` bracket text in plain paragraph styling. Why it matters: undercuts the adjacent "PII 마스킹 이력" panel's promise that these were flagged. Fix: wrap PII placeholder spans with `.pii-highlight` when rendering `doc.body`. Suggested command: `/impeccable polish`.

## Persona Red Flags

**Sam (Accessibility-dependent)**: Tab focus and Enter/Space activation are now genuinely fixed and verified live. But the Knowledge Graph — the app's flagship feature — is entirely `<canvas>`-based with raw x/y hit-testing; there is no keyboard or screen-reader path to select a node and open the inspector, so Sam cannot use the signature feature at all without a mouse.

**Riley (Stress Tester)**: Confirmed live — switching the active project while the graph inspector is open leaves orphaned data referencing nodes/documents that don't exist in the new project (P1 above, reproduced and independently corroborated by both assessments). The scan simulation is also fully canned regardless of input, so the spec's 51-file cap and empty-folder cases have nothing to probe yet.

**Alex (Power User)**: No batch/multi-select in the Plan report table; no cancel once a scan starts; keyboard nav works but is purely sequential Tab order, no jump-to-screen shortcuts beyond "빠른 스캔".

## Minor Observations

- The Cloud Opt-in toggle ships pre-granted by default; the backing CLI spec explicitly places the cloud-LLM path out of scope for this slice — a product-roadmap flag, not a UI defect.
- `.metric-box:first-child` spans 2 grid columns while the other three are single-column; the emphasis reads fine but the rationale isn't obvious.
- Search results are always the same 3 canned cards regardless of query — a "no results" empty state has never been observable in this prototype.
- Contrast fix holds up under recomputation: `--text-secondary` (#67655F) ≈ 5.8:1 and `--text-muted` (#736D62) ≈ 5.1:1 against white, both comfortably clearing WCAG AA.

## Questions to Consider

1. The Plan → Scan two-step (preview consequences, then commit) is the app's strongest trust-building idea — should that pattern extend to project switching and revoking cloud consent too, instead of those applying instantly?
2. The Knowledge Graph is the signature feature, but it's the one screen a keyboard/screen-reader user can't touch at all — is a mouse-only "headline" feature acceptable given how much effort went into fixing keyboard access everywhere else?
3. Given the CLI spec this GUI previews requires visible skip/failure reporting as a completion-definition requirement, should the reference mockup show at least one "imperfect run" state before stakeholders sign off on it as the design baseline?
