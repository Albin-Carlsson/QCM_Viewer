# QCM Viewer — Workbench UI Overhaul (Design Spec)

**Date:** 2026-05-29
**Status:** Design approved (Pattern 2); pending implementation plan
**Author:** brainstormed with Claude
**Supersedes the shell model introduced in:** the 2026-05-28 stepper overhaul

## Goal

Make the QCM Viewer look and behave like a finished, research-grade analysis
product — a calm, professional, **single visual vision** — and restructure the
shell so the core analysis loop is never hidden.

This is the **first** project in a larger roadmap (later rungs: fit-quality &
trust, multi-overtone diagnostics, viscoelastic modeling, reproducibility,
multi-run comparison). It is deliberately scoped to **presentation + shell
structure only**. No new science, quantities, plots, or data-model changes.

## The two problems this solves

1. **Styling entropy.** `design.py` is one `APP_CSS` string `+=`-appended six
   times. `:root` tokens are redefined four times (`--qcm-bg` has three values;
   `--qcm-shadow-1/2` are defined then overwritten to `none`). Nearly every rule
   carries `!important`, so specificity is meaningless and each tweak needs
   another `!important` to win. Two components the shell builds
   (`context_bar`, `footer`) are `display:none`-ed by later CSS blocks — **dead
   UI that is built then hidden**. Two parallel component systems coexist
   (`design.py`: `metric_card`/`metric_table`/`meta_pill`; `components.py`:
   `stat_badge`/`metric_strip`/`pill`). A "single vision" cannot be *added* on
   top of this; it must be reached by **consolidation and deletion**.

2. **Wrong shell pattern.** The current shell is a **linear wizard**
   (Review → Reference → Phases → Quantify → Report). QCM analysis is an
   **iterative inspect → select → measure loop**: brush a time region, read the
   derived numbers, nudge the region, compare, repeat. A wizard hides the plot
   and statistics on every step switch, which is the "go back and forth" tax.
   Industry tools (QSense Dfind *AutoPlotting*; Origin; Igor; GraphPad Prism's
   project navigator; scope/DAQ software) and the InfoVis canon (Coordinated
   Multiple Views + brushing & linking, governed by **focus + context**) all
   converge on a **persistent anchor plot with live, always-visible derived
   views**.

## Decision: Pattern 2 — persistent workbench with a focus rail

Replace the linear wizard with a **coordinated-views workbench**. The
**plot + selection bar + live statistics triad is always on screen**. A left
**focus rail** switches *task focus*; switching focus only (a) re-targets the
plot brush and (b) swaps the small **secondary panel** — it never hides the
triad. The wizard's guidance survives as non-blocking hints; the wizard's cost
(hiding the loop) disappears.

```
┌ Context bar: Run · channels · overtones · Current 100–200s · Zero 0–20s   [Inspect raw] ┐
├────────────┬───────────────────────────────────────────────┬────────────────────┤
│ FOCUS      │                                               │  LIVE STATS        │
│ ▸ Overview │            PERSISTENT  PLOT  (anchor)          │  (always on,       │
│   Reference│        overtones overlaid · brushable          │   tracks selection)│
│   Phases   │                                               │  Δf/n  -42.1 Hz    │
│   Quantify │                                               │  ΔD    3.2e-6      │
│   Report   ├───────────────────────────────────────────────┤  mass  745 ng/cm²  │
│            │ SELECTION (always on):                        │                    │
│ guidance:  │ Current[100–200] Ref[0–20] Mark[]  brush:◉ref │  ── focus panel ── │
│ hint text  │ [Set zero = current]                          │  reference tools / │
│            │                                               │  phase list / etc. │
└────────────┴───────────────────────────────────────────────┴────────────────────┘
```

**Rejected alternatives:** Pattern 1 (single canvas, no modes) — hits a clutter
wall once viscoelastic + multi-run features arrive. Keeping the linear wizard —
imposes the back-and-forth tax this project exists to remove.

## Non-goals (YAGNI)

- No new science, quantities, plot types, or modeling.
- No data-model / manifest / ingest changes.
- No multi-run comparison yet (the layout is *designed to accommodate* it later
  via the focus rail, but multi-run is a separate project).
- No dark mode / theme toggle. Light only.
- No backward-compat shims for retired modules.

## Architecture

**Principle:** analysis logic stays frozen; only the presentation + shell layer
changes. Keep the many-small-files convention.

### Layers that stay frozen

`run.py`, `data.py`, `science.py`, `plots.py`, `actions.py`, `theme.py`
(quantity registry), `state.py`, `nav.py`, `plot_theme.py`. `controls.py` keeps
all atomic widgets, `state()`, and range-sync logic; its Card-builder helpers
are re-composed by the workbench (logic reused, composition changes).

### Files that change

| File | Action |
|------|--------|
| `shell.py` | Rewritten: `ViewerShell` builds the workbench (context bar, focus rail, anchor plot, selection bar, live-stats panel, swappable focus panel, QC drawer). Owns transient `focus` state. |
| `steps/*.py` | Repurposed from full "pages" into **focus-panel + plot contributors**. Each focus module exposes the secondary-panel content and declares its brush target; the triad (plot/selection/stats) is owned by the shell, not the step. |
| `design.py` | Collapsed to **one** `:root` token block + **one** global stylesheet, rules scoped under a single app root (`.qcm-app`) to retire the `!important` arms race. The four orphaned helpers are deleted. |
| `components.py` | Becomes the **sole** component library. Gains any shared pieces the workbench needs (focus-rail item, selection-bar field, live-stat row) if not already present. |
| `app.py` | Updates the stale docstring; wires the rewritten shell (already imports `ViewerShell`). |

### Files deleted (confirmed dead)

- `layout.py` — imported by nothing.
- `pages.py` — imported only by `layout.py`.
- `design.py` helpers `metric_card`, `metric_table`, `section_header`,
  `meta_pill` — used only by the two dead files above.

## Shell behavior

### State model

- **All analysis state stays in the single `ViewerControls` instance**
  (channels, overtone orders, current range, zero/reference range, mark range,
  selected quantity). Switching focus never loses a selection.
- **`focus` is transient shell UI state** held by `ViewerShell` (a small
  reactive value), **not** added to `ViewState`. It mirrors today's
  `current_step` but drives panel-swapping, not page-hiding.
- The live-stats panel and selection bar **read live** from `ViewerControls` +
  `QCMViewData`, so they update with every brush/slider change (coordinated
  views).

### Brushing & linking (the loop)

- Dragging on the anchor plot sets a range; **which** range it sets follows the
  active focus, via the existing `nav.brush_target_for_step` logic
  (Overview → current, Reference → reference, Phases → mark). A subtle override
  control in the selection bar lets the user retarget the brush manually.
- The selection bar always shows Current / Reference / Mark ranges with numeric
  editors, plus **Set zero = current**.
- Any range change propagates immediately to the plot overlay, the live-stats
  panel, and dependent readouts.

### Focus modes and their secondary panels

| Focus | Brush target | Secondary panel contents (reused from today's steps) |
|-------|--------------|------------------------------------------------------|
| Overview | current | quantity selector, overtone toggles summary, current-range stats |
| Reference | reference | baseline tools, reference-range readout, zero-sync guidance |
| Phases | mark | saved-region/phase list (add/remove), compare-region table |
| Quantify | current | quantity detail, KPI/statistics table for current range |
| Report | current | export / notebook controls (existing actions) |

Non-blocking guidance: e.g. in Quantify, if a Δ (referenced) quantity is
selected but no reference range is set (or it equals the full run), an inline
hint links to **Reference**. It informs; it never blocks. (Seam left open so a
future fit-quality signal can feed these hints — see roadmap rung 1.)

### QC / raw-sweep drawer

Kept as today: a non-modal right-side **drawer** ("Inspect raw sweeps")
reachable from the context bar in any focus. Reactive, never a focus step.

## Styling system

- **One token source of truth** in a single `:root` block: color, spacing
  (`--qcm-space-*`), radius, shadow, and a small type scale. Every value used as
  `var(--…)`, defined once.
- **Scope, don't shout.** All component rules live under a single app root class
  so they win by structure; remove `!important` except where overriding
  third-party (Bokeh/Tabulator) styles genuinely requires it, and document each
  such case.
- **Restore the context bar and footer** as real, styled regions (no
  build-then-hide). The footer is optional in a workbench; if kept, it carries
  global actions, not Back/Next.
- **Density: calm but efficient.** Generous-enough spacing and clear hierarchy
  so the triad reads as a professional instrument; the anchor plot gets primary
  visual weight. Scrolling *within the secondary panel or stats* is acceptable;
  the triad stays in view.
- **Responsive:** below ~1200px the focus rail collapses to a top chip-row and
  the live-stats panel drops below the plot; the triad order is preserved.

## Error handling & empty states

- Empty/edge data (no overtones selected, empty range, missing reference) render
  via the existing `components.empty_state` / `hint`, never blank panels or
  tracebacks in the UI.
- All HTML-returning component helpers continue to escape data text (existing
  behavior; preserved by tests).

## Testing

- **Keep & update** `test_nav.py` (brush-target-follows-focus logic),
  `test_components.py` (escaping/markup), `test_plot_theme.py`.
- **Rework** `test_shell_smoke.py` into a workbench-composition smoke test:
  asserts the shell builds; the triad (plot region, selection bar, live-stats
  panel) is present in every focus; switching focus swaps the secondary panel
  **without** removing the triad; the QC drawer mounts.
- **Add** a focus-state test: changing focus updates the brush target and the
  secondary panel, and leaves `ViewerControls` selections intact.
- Behavior parity: existing analysis/export behavior is unchanged (logic layers
  frozen); a smoke check that export/notebook actions still wire through.
- Target: keep coverage ≥ 80% on the touched presentation modules.

## Cleanup / migration

1. Delete `layout.py`, `pages.py`, and the four orphaned `design.py` helpers.
2. Fix the stale `app.py` docstring.
3. Collapse the six `APP_CSS` blocks into one token block + one scoped
   stylesheet.
4. No alias shims; update the (already minimal) importers.

## Design tradeoffs

The workbench keeps the *entire* analysis loop on screen at the cost of denser
information at any instant than a wizard step. The focus rail + swappable
secondary panel + focus+context discipline keep that density legible and leave
room for the roadmap's future capabilities (diagnostics, viscoelastic modeling,
multi-run) to slot in as new focuses rather than new full-screen modes.
