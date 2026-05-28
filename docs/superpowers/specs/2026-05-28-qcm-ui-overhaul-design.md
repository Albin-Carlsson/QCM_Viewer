# QCM Viewer UI Overhaul — Design Spec

**Date:** 2026-05-28
**Status:** Approved (design); pending implementation plan
**Author:** brainstormed with Claude

## Goal

Revamp the QCM Viewer UI into a production-quality analysis tool on par with
industry instrument software (e.g. Biolin Scientific / QSense Dfind & Analyzer).

The two pillars driving this work, as confirmed by the user:

1. **Visual design / polish** — it should look like a finished commercial product,
   not a research/dev tool.
2. **Workflow / layout** — a guided analysis flow, with global context always
   reachable, instead of control-heavy full-width card stacks across loose tabs.

The plotting engine, interaction fidelity, and the set of scientific quantities
are **not** the focus and are left functionally intact.

## Constraints & decisions (locked in)

- **Stack:** Stay in Panel + HoloViews + Bokeh, served locally. Push Panel hard
  via custom template, tokens, CSS, and a reusable component layer. No SPA/React
  rewrite. (Reuses ~95% of existing code.)
- **Shell model:** A **guided linear stepper**: Review → Reference → Phases →
  Quantify → Report.
- **QC / raw-sweep inspection:** an **always-available side drawer**, reachable
  from any step. It is reactive ("something looks weird, investigate"), so it is
  not a numbered step and never blocks the flow.
- **Visual direction:** **Refined light scientific** — calm, precise, lab-instrument
  feel. Light only (no dark mode).
- **Backend frozen:** `data.py`, `science.py`, `plots.py`, `actions.py` logic and
  the `theme.py` quantity registry are untouched. Only the presentation layer changes.

## Non-goals (YAGNI)

- No new science / quantities / viscoelastic or multi-overtone modeling.
- No new plot types or plotting-engine changes.
- No dark mode / theme toggle.
- No multi-user, server-deployment, or auth changes (stays local-first).
- No ingest / manifest / data-model / run-format changes.
- No backward-compat alias shims for retired modules.

## Architecture

**Principle:** logic layers stay frozen; the presentation layer is restructured
into a small, focused `shell → steps → components → tokens` stack (honoring the
many-small-files convention).

### Files that change vs. stay

| File | Today | After |
|------|-------|-------|
| `app.py` | composition root | same role; wires the new shell instead of `ViewerLayout` |
| `state.py` | `RunInfo`, `ViewState` | unchanged — navigation state is transient UI and lives in the shell, not in `ViewState` |
| `controls.py` | widgets + `state()` + Card-builder blocks | **keep** all atomic widgets and `state()`/range-sync logic; the Card-building helpers are re-skinned as step toolbars (logic reused, composition changes) |
| `data.py`, `science.py`, `plots.py`, `actions.py` | logic layers | **untouched** |
| `design.py` | CSS blob + HTML helpers | becomes the **design-token + global stylesheet** module only; HTML helpers move to `components.py` |
| `theme.py` | look constants + quantity registry | quantity registry kept; look constants migrate into the token system |

### New files (component + shell layer)

- `viz/components.py` — reusable, token-driven presentational building blocks
  shared by every step: `card`, `section_title`, `toolbar`, `metric_strip` /
  `stat_badge` (unifies today's `metric_card` + `metric_table` + `kpi-table`),
  `pill`, `empty_state`, `drawer`, the stepper navigator, the footer action bar,
  and the inline guidance banner. Absorbs the duplicated inline CSS currently in
  `design.py`, `layout.py`, and `pages.py`.
- `viz/shell.py` — the **stepper shell**. Owns the reactive `current_step`;
  renders the persistent context bar, the step navigator, the active step view,
  the per-step action footer, and mounts the QC drawer. Replaces `layout.py`.
- `viz/steps/` — one small, focused file per step view:
  `review.py`, `reference.py`, `phases.py`, `quantify.py`, `report.py`, plus
  `qc_drawer.py`. Replaces the 690-line `pages.py`.

`pages.py` and `layout.py` are retired; their importers (`app.py`, and any in
`notebooks.py`) are updated. No alias shims.

## The shell

### Anatomy (top → bottom)

```
┌─ Context bar (persistent) ───────────────────────────────────┐
│ RunID · [duration][channels][overtones][sweeps]   Channels▾  │
│ Current: 100–200s · Zero: 0–20s        [Inspect raw sweeps ⤢]│
├─ Step navigator ─────────────────────────────────────────────┤
│ ①Review ─ ②Reference ─ ③Phases ─ ④Quantify ─ ⑤Report         │
├─ Step canvas (the active step) ──────────────────────────────┤
│  step toolbar (controls for THIS step)                        │
│  PLOT / tables / cards                                         │
├─ Action footer ──────────────────────────────────────────────┤
│ [‹ Back]              step hint            [primary] [Next ›]  │
└──────────────────────────────────────────────────────────────┘
```

### Navigation & state model

- The shell owns a reactive `current_step` (0–4). The numbered navigator allows
  **free jumping** to any step (no hard gates). Back/Next in the footer for
  linear movement. The active step is rendered lazily (only the active step's
  plots are built).
- **All global state stays in the single `ViewerControls` instance** (channels,
  orders, current range, zero range, mark range). Moving between steps never
  loses selections — this reconciles a linear flow with persistent context.
- The persistent **context bar** keeps run identity, a live **Channels** popover
  (reusing the existing `CheckButtonGroup`), and the current/zero range readout
  visible from every step.
- **Brush target follows the step:** dragging on a plot sets the *current* range
  in Review/Quantify, the *reference* range in Reference, and the *mark* range in
  Phases — automatically. This removes the need for the prominent `brush_mode`
  toggle (kept only as a subtle override).
- **Non-blocking guidance:** e.g. in Quantify, if a Δ (referenced) quantity is
  selected but no reference range is set (or it equals the full run), an inline
  hint links back to ② Reference. It informs; it never blocks.

### The five steps (content reused from existing pages)

| Step | Reuses | Purpose & primary action |
|------|--------|--------------------------|
| **① Review** | `RunReviewPage` | Full-run dual-axis QCM-D overview + current-range summary. Brush to pick the region of interest. Footer: *Next*. |
| **② Reference** | `zero_reference_*` controls + overview plot | Overview with the reference band highlighted. Primary action: **"Set reference = current range"**. Defines zero for Δ quantities. |
| **③ Phases** | `PhaseBuilderPage` | Mark + name phases; saved-phases table; rollup / per-channel matrix / response ranking. Primary action: **"Save phase"**. |
| **④ Quantify** | `QuantifyPage` | Quantity selector + timeline, summary cards, per-channel readout, summary + advanced statistics, ΔD-vs-Δf/n fingerprint. |
| **⑤ Report** | `ReportPage` | Region selector, data export (.parquet), notebook export (.ipynb), save workspace. Primary action: **"Export notebook"**. |

### QC drawer

Reuses `QCPage`. The *Inspect raw sweeps* button in the context bar opens an
overlay drawer containing the sweep controls (sequence, prev/next, mode, single
channel), resonance curves, I/Q scatter, and waterfall. Reachable from any step;
never blocks the flow.

## Visual design system

### Tokens (defined once in `design.py`)

- **Color:** refined light-scientific palette — layered neutrals
  (`bg` / `surface` / `surface-muted`), two border weights, primary + muted text,
  one confident accent (the existing blue, refined), and semantic
  success / warning / danger. **Data-series colors keep the Wong colorblind-safe
  palette** already in `theme.py`.
- **Typography:** a disciplined type scale (display / title / section / body /
  label / caption), replacing the ad-hoc heavy weights (810/760). Clean sans
  stack; **tabular numerals** wherever numbers appear.
- **Spacing / radius / elevation:** 8px-based spacing scale, 3 radius tokens, a
  3-level shadow scale (resting vs. raised). Density tuned
  "comfortable-but-information-rich," like instrument software.

### Components

`components.py` provides the token-driven building blocks listed under
Architecture. They unify today's scattered inline styles into one consistent
visual language.

### Plot styling

`plots.py` logic stays frozen. Visual consistency comes from applying a shared
**Bokeh theme** document-wide (fonts, grid, axis, legend) so charts match the UI
chrome without editing plot-building code. Minor `.opts()` pass-throughs are
acceptable only if strictly presentational.

### Shell chrome

Expect to drop `FastListTemplate` (its sidebar is no longer needed) in favor of a
leaner custom template / `pn.Column` shell, for full control over header and
footer. The QC drawer is a CSS-positioned overlay toggled by a reactive boolean
(fallback: `template.open_modal`).

## Testing

Per the project's pytest + TDD + 80%-coverage rules:

- **TDD the extractable pure logic:**
  - step navigation state machine (`current_step` transitions, clamping),
  - brush-target-by-step mapping,
  - the Δ-quantity guidance predicate (when to show the "set a reference" hint),
  - `components.py` helper output (correct CSS classes, HTML escaping).
- **Composition smoke test:** `QCMViewer("view-run").view()` builds without error
  against the existing demo run — catches import/wiring breakage.
- **Manual browser verification:** `panel serve`, click through all 5 steps + the
  QC drawer; confirm state persists across steps, brush targets follow the step,
  and guidance appears/clears correctly. Optionally a Playwright smoke pass for E2E.
- Interactive feel is verified in-browser, not by tests alone.

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Panel/Bokeh styling ceiling for a bespoke look | Custom `raw_css` + per-widget `stylesheets`; custom template instead of `FastListTemplate` |
| Step-swap rebuild performance with heavy plots | Lazy-render only the active step; reuse existing throttled inputs + `data.py` LRU cache |
| No native Panel drawer component | CSS-positioned overlay toggled by a reactive boolean; `template.open_modal` fallback |
| Reshaping `controls.py` composition could regress range-sync behavior | Reuse the atomic widgets and `state()`/sync methods verbatim; only change how they are assembled into toolbars |

## Open questions

None blocking. Implementation-plan stage will sequence the work (tokens +
components first, then shell, then port steps one at a time behind the new shell,
then retire `pages.py`/`layout.py`).
