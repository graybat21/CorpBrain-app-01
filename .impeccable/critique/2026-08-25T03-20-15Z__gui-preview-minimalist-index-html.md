---
target: gui_preview_minimalist/index.html
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
timestamp: 2026-08-25T03-20-15Z
slug: gui-preview-minimalist-index-html
---
Method: dual-agent (A: independent design-review subagent · B: independent detector+evidence subagent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3/4 | Scan log/progress/cancel messaging is excellent, but the Plan & Scan card doesn't clear when the active project changes — it can show status for the wrong project. |
| 2 | Match System / Real World | 3/4 | Korean domain terminology used fluently; a few terms (NetworkGuard, 게이트웨이) remain unexplained. |
| 3 | User Control and Freedom | 3/4 | Cancel button works cleanly with Escape+Cancel on the modal; scan/plan cards have no manual dismiss once triggered. |
| 4 | Consistency and Standards | 3/4 | Sidebar-footer vs. top-tab active states now consistent (round-2 fix verified live); undercut by the scan panel going stale across projects. |
| 5 | Error Prevention | 3/4 | Guarded setTimeout stage-logs after cancel verified live (no stray lines); empty-submit on the add-folder modal fails silently with no feedback. |
| 6 | Recognition Rather Than Recall | 4/4 | All nav text-labeled, counts/badges visible everywhere, inspector panels show connected context without requiring memory. |
| 7 | Flexibility and Efficiency of Use | 2/4 | Keyboard activation verified live; still no shortcuts, no bulk actions, and the Knowledge Graph remains 100% mouse-only. |
| 8 | Aesthetic and Minimalist Design | 4/4 | Genuinely clean; round-1 cognitive-load fix holds up, progressive disclosure used well throughout. |
| 9 | Error Recovery | 3/4 | Skip-summary gives specific per-file reasons (verified live); no other failure states modeled elsewhere. |
| 10 | Help and Documentation | 1/4 | No tooltip or inline help anywhere; the three gate toggles have labels but no consequence explanation. |
| **Total** | | **29/40** | **Good (low end)** — up from 26/40 |

## Design Specificity Verdict

**LLM assessment**: Content layer is genuinely product-specific — the "100% Local Guard / 127.0.0.1" indicator, Ollama/GPU/embedding doctor cards, the 7-category Korean PII regex tester with live masking preview, and a cloud-consent toggle that names "Anthropic Claude Haiku" explicitly. The typographic system (serif titles, ink-monochrome + desaturated pastel badges, zero gradients) also avoids the default SaaS look. The page *skeleton* — sidebar-of-cards + top-tab-bar + metric-grid + panel cards — remains a common admin-dashboard shape; stripped of the Korean HR/security copy, Dashboard and Settings could plausibly belong to other B2B tools. Verdict: strong content authorship, moderate structural genericness (unchanged assessment from prior rounds).

**Deterministic scan**: Clean — 0 findings (DEGRADED regex mode, so a weak signal, not a clean bill of health). The previously-suppressed `flat-type-hierarchy` finding correctly stays absent per the persisted ignore rule.

**Visual overlays**: Still not available — same tooling limitation as prior rounds; findings come from live screenshot review plus source verification.

## Overall Impression

Score moved **26/40 → 29/40**, crossing into "Good." All five round-2 fixes verified working live, including edge-case checks the fixes were specifically meant to survive (cancel-then-wait for stray logs, PII with multiple matches, node-select-then-switch-project). But both assessments — working independently — surfaced the *same* new bug: the exact class of cross-project state leak that was fixed for the graph inspector in round 2 still exists one screen over, in the Plan & Scan card. That's a good sign about the fix's correctness where applied, and a clear signal it needs to be applied systematically rather than screen-by-screen.

## What's Working

1. **Cancellation UX verified live under real timing stress** — cancelling mid-scan produces a single clean "취소됨" line with no stray stage-logs arriving afterward, confirmed by checking again ~1.5s later.
2. **PII highlighting is real and legible in running prose** — not just a settings-page demo; multiple PII types in one string all masked/highlighted correctly.
3. **Cross-project graph-inspector reset holds up under a real click-then-switch test** — not just code inspection, actually reproduced live.

## Priority Issues

**[P1] Plan & Scan progress/log state is not scoped to the active project** — What: cancelling or completing a scan on one project, then switching to a different project, leaves the previous project's scan log, folder names, and stuck progress bar visible under the new project's form. **Independently found by both assessments** without knowledge of each other's work. Why it matters: this is the identical bug class already fixed for the Knowledge Graph inspector in round 2 — `switchProject()` resets the sidebar, header, wiki tree/reader, and graph inspector, but never touches `scanProgressCard`/`scan-log-stream`/`skip-summary`/`AppState.isScanning`. A user could believe a scan is active for the wrong project. Fix: extend `switchProject()` to hide/reset the scan progress card and plan report card the same way it already resets the graph inspector — ideally as one unified "reset all per-project UI" pass rather than a hand-maintained list. Suggested command: `/impeccable harden`.

**[P2] The Wiki Explorer's tree search input is dead** — What: `.tree-search-input` (index.html:540, placeholder "위키 문서 검색...") has zero JS wiring — confirmed by source search and live typing (nothing filters). The nearly-identical sidebar `#project-search-input` a few pixels away IS wired and works. Why it matters: a control that looks interactive but silently does nothing is trust-eroding in a tool whose entire pitch is precise control over your own documents. Fix: wire it to filter `.tree-item` elements by title, mirroring the existing project-search handler. Suggested command: `/impeccable harden`.

**[P3] Zero contextual help for consequential gate toggles** — What: the three "고급 게이트" checkboxes have labels only, no explanation of what unchecking one does. Fix: add a small info affordance per toggle with a one-line consequence statement. Suggested command: `/impeccable clarify`.

**[P3] Cancel button doesn't reflect its own terminal state** — What: after a scan is cancelled or completes, `#btn-cancel-scan` stays fully enabled-looking even though clicking it again is a no-op. Fix: disable/mute the button once `AppState.isScanning` goes false. Suggested command: `/impeccable polish`.

## Persona Red Flags

**Riley (Stress Tester)**: Found the P1 cross-project leak by doing exactly what Riley does — cancel a scan, then navigate away via the sidebar instead of the happy path. Also stress-tested the PII masker with two phone numbers and two emails in one string; all four masked correctly, confirming the regexes are properly global/multi-match.

**Alex (Power User)**: No shortcuts for switching projects/tabs beyond linear Tab traversal (5+ presses from sidebar search to reach top nav). No bulk/multi-project actions — scanning two projects is fully serial (switch → scan → wait → switch → scan).

**Sam (Accessibility-Dependent)**: Focus indicators verified genuinely good live — clear focus ring, Enter correctly activates a focused project card. The Knowledge Graph's canvas-only, no-keyboard-path limitation remains unchanged (known, already deferred by prior agreement).

## Minor Observations

- The add-folder modal silently no-ops on an empty submission with zero feedback — low risk since the field ships with a non-empty default, but worth a toast/inline validation if someone clears it.
- Log-stage color coding differentiates by text color, but every row also carries distinguishing Korean text, so it doesn't fail "don't rely on color alone" in practice.
- The skip-summary `<details>` defaults collapsed — reasonable progressive disclosure, but a first-time user might miss that a file silently failed unless they notice the small red disclosure line.

## Questions to Consider

1. If the graph inspector correctly resets on project switch, should `switchProject()` do one blanket "reset all per-project UI" pass instead of a hand-maintained list of exceptions — so this bug class can't recur a third time on some other screen?
2. The scan simulation always skips exactly one hardcoded `.hwp` file — is that enough to validate the skip-summary UI against the spec's fuller list of failure reasons (permission denied, path too long, empty file, LLM parse failure)?
3. Given the audience is IT/HR staff rather than developers, is a help-free interface (heuristic #10 at 1/4) the right bet, or does this audience need more hand-holding than the current "power tool" aesthetic assumes?
