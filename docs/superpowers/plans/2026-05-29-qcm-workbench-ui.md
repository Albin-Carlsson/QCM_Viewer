# QCM Workbench UI Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the linear stepper wizard with a persistent coordinated-views "workbench" (always-visible plot + selection bar + live-stats triad, a focus rail that swaps a secondary panel and re-targets the plot brush) on a consolidated styling foundation.

**Architecture:** Presentation + shell layer only. All analysis logic (`run/data/science/plots/actions/theme/state/nav`) is frozen. `shell.py` is rewritten to own the persistent triad; the `steps/*` modules each expose an `anchor_plot()` and a `secondary_panel()` instead of a full-page `view()`; `design.py` collapses from six appended CSS blocks into one token block + one scoped stylesheet; dead `pages.py`/`layout.py` and four orphaned helpers are deleted.

**Tech Stack:** Python 3, Panel, HoloViews/Bokeh, Polars, pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-qcm-workbench-ui-design.md`

---

## Widget ownership map (CRITICAL — read before any task)

A Panel widget **instance** can be mounted in exactly one place in the layout tree. The workbench mounts the context bar, selection bar, live-stats, and one secondary panel **at the same time**, so every shared `ViewerControls` widget gets exactly one owner:

| Widget(s) | Single owner |
|-----------|--------------|
| `save_state_button`, `status`, channels (`compact_channel_controls` → `group_select`), "Inspect raw" button | **Context bar** |
| `t_range` (+ start/end inputs, full button), `baseline_range` (+ inputs, full button, `use_selection_as_baseline`, `revert_baseline`), `brush_mode`, `quantity_select`, `plot_reset_button()` | **Selection bar** |
| `current_range_summary_cards()` (bound, read-only) | **Live-stats panel** |
| `mark_range` (+ inputs), `region_label`, `region_type`, `mark_point_button`, `mark_window_button`, `phases_table`, phase analysis tables | **Phases secondary panel only** |
| `analysis_region_select`, stats tables, ΔD–Δf fingerprint | **Quantify secondary panel only** |
| `orders_text` (advanced) | **Overview secondary panel only** |
| `marker_select`, `export_data_dl`, `export_nb_dl` | **Report secondary panel only** |
| `sequence`, sweep buttons, `sweep_mode`, `group_for_single`, `frequency_band` | **QC drawer only** |

Secondary panels must contain only their focus-specific widgets (above) plus read-only bound content; they must **not** re-mount any selection-bar/context-bar widget.

---

## Phase 0 — Safety net and dead-code removal

### Task 1: Lock current behavior with a baseline smoke run

**Files:**
- Test: `tests/test_shell_smoke.py` (read only this task)

- [ ] **Step 1: Run the existing suite to confirm a green baseline**

Run: `python -m pytest -q`
Expected: PASS (or only the `demo_run_path` skip if `view-run/manifest.json` is absent). If `view-run/manifest.json` is missing, first run:
`python -m qcm.cli demo-data ./demo-run --preset small && python -m qcm.cli ingest ./demo-run/demo.parquet ./view-run --overwrite`
then re-run the suite. Do not proceed until green.

- [ ] **Step 2: Commit nothing — this is a checkpoint only.**

---

### Task 2: Delete dead modules and orphaned helpers

**Files:**
- Delete: `qcm/viz/pages.py`
- Delete: `qcm/viz/layout.py`
- Modify: `qcm/viz/design.py` (remove helpers `section_header`, `metric_card`, `metric_table`, `meta_pill`, and the now-unused `_html`/`escape`/`import pn` if no longer referenced — keep only `APP_CSS`)
- Modify: `qcm/viz/app.py:1-11` (fix stale docstring)
- Test: `tests/test_no_dead_imports.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_no_dead_imports.py
"""Guards that retired modules and helpers stay gone."""
import importlib

import pytest


def test_pages_and_layout_modules_removed():
    for name in ("qcm.viz.pages", "qcm.viz.layout"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_design_exposes_only_css():
    from qcm.viz import design

    assert hasattr(design, "APP_CSS")
    for gone in ("section_header", "metric_card", "metric_table", "meta_pill"):
        assert not hasattr(design, gone), f"{gone} should be deleted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_no_dead_imports.py -q`
Expected: FAIL (`pages`/`layout` still import; helpers still present).

- [ ] **Step 3: Delete the dead files and helpers**

```bash
git rm qcm/viz/pages.py qcm/viz/layout.py
```

In `qcm/viz/design.py`, delete the functions `_html`, `section_header`, `metric_card`, `metric_table`, and `meta_pill` (lines ~437–490 in the current file) so the module ends right after the `APP_CSS` string assignments. Remove the now-unused top imports `from html import escape` and `import panel as pn` (the file becomes a pure CSS string module). Leave every `APP_CSS = ...` / `APP_CSS += ...` block intact for now — Task 6 consolidates them.

- [ ] **Step 4: Fix the stale `app.py` docstring**

In `qcm/viz/app.py`, replace the module docstring (lines 1–11) with:

```python
"""QCM viewer Panel application.

Composition root only. Architecture:

- ``state.py``: typed run/view state
- ``controls.py``: Panel widgets and widget -> state conversion
- ``data.py``: run queries and science transforms
- ``steps/*``: per-focus plot + secondary-panel contributors
- ``actions.py``: mutations and exports
- ``shell.py``: workbench assembly (context bar, focus rail, triad, drawer)
"""
```

- [ ] **Step 5: Run tests to verify green**

Run: `python -m pytest tests/test_no_dead_imports.py tests/test_shell_smoke.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove dead pages/layout modules and orphaned design helpers"
```

---

## Phase 1 — Navigation labels

### Task 3: Rename the first focus label to "Overview"

**Files:**
- Modify: `qcm/viz/nav.py:18-24`
- Test: `tests/test_nav.py` (add one assertion)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_nav.py`:

```python
def test_focus_labels_use_overview_first():
    assert [s.label for s in nav.STEPS] == [
        "Overview", "Reference", "Phases", "Quantify", "Report",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nav.py::test_focus_labels_use_overview_first -q`
Expected: FAIL (label is "Review").

- [ ] **Step 3: Change the label (keep the id `review` so brush map + other tests pass)**

In `qcm/viz/nav.py`, change the first tuple entry:

```python
STEPS: tuple[Step, ...] = (
    Step("review", "Overview"),
    Step("reference", "Reference"),
    Step("phases", "Phases"),
    Step("quantify", "Quantify"),
    Step("report", "Report"),
)
```

- [ ] **Step 4: Run the nav tests**

Run: `python -m pytest tests/test_nav.py -q`
Expected: PASS (all, including `test_steps_are_five_in_order` which checks ids).

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/nav.py tests/test_nav.py
git commit -m "feat: relabel first focus to Overview"
```

---

## Phase 2 — Step focus contract

### Task 4: Add `overview_anchor` to BaseStep (DRY the three full-run plots)

**Files:**
- Modify: `qcm/viz/steps/_base.py` (add imports + method)
- Test: `tests/test_steps_contract.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_steps_contract.py
import panel as pn

from qcm.viz import nav


def _viewer(demo_run_path):
    from qcm.viz.app import QCMViewer
    return QCMViewer(str(demo_run_path))


def test_base_overview_anchor_builds(demo_run_path):
    v = _viewer(demo_run_path)
    step = v.shell._steps["review"]
    obj = step.overview_anchor("current")
    assert obj is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_steps_contract.py::test_base_overview_anchor_builds -q`
Expected: FAIL (`AttributeError: 'ReviewStep' object has no attribute 'overview_anchor'`).

- [ ] **Step 3: Implement `overview_anchor` in BaseStep**

In `qcm/viz/steps/_base.py`, add these imports near the top (after the existing imports):

```python
from dataclasses import replace

from .. import plots
from ..theme import HERO_HEIGHT
```

Add this method to `class BaseStep` (place it just before `current_range_summary_cards`):

```python
    def overview_anchor(self, window: str = "current"):
        """Full-run dual-axis QCM-D plot used as the anchor for Overview,
        Reference, and Report. ``window`` selects which range is highlighted."""
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            win = state.t_range_s if window == "current" else state.baseline_s
            plot = plots.dual_axis_qcmd(
                norm_df, d_df, full.groups, full.orders, "QCM-D overview",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=win, select_x=True, height=HERO_HEIGHT,
            )
            plot = self.with_phase_labels(plot, norm_df, height=HERO_HEIGHT)
            return self.interactive_plot(self.force_plot_height(plot, HERO_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_steps_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/steps/_base.py tests/test_steps_contract.py
git commit -m "feat: add shared overview_anchor to BaseStep"
```

---

### Task 5: Give each step `anchor_plot()` and `secondary_panel()`

**Files:**
- Modify: `qcm/viz/steps/review.py`
- Modify: `qcm/viz/steps/reference.py`
- Modify: `qcm/viz/steps/phases.py`
- Modify: `qcm/viz/steps/quantify.py`
- Modify: `qcm/viz/steps/report.py`
- Test: `tests/test_steps_contract.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_steps_contract.py`:

```python
def test_every_step_has_anchor_and_secondary(demo_run_path):
    v = _viewer(demo_run_path)
    for sid in ("review", "reference", "phases", "quantify", "report"):
        step = v.shell._steps[sid]
        assert step.anchor_plot() is not None, f"{sid} anchor_plot"
        assert isinstance(step.secondary_panel(), pn.viewable.Viewable), f"{sid} secondary_panel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_steps_contract.py::test_every_step_has_anchor_and_secondary -q`
Expected: FAIL (`anchor_plot` not defined).

- [ ] **Step 3: Implement in each step**

**`qcm/viz/steps/review.py`** — replace the whole file (delete `hero_plot`, `compact_review_controls`, `view`):

```python
"""Overview focus: full-run QCM-D anchor + channel/advanced controls."""
from __future__ import annotations

import panel as pn

from ..components import hint
from ._base import BaseStep


class ReviewStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("current")

    def secondary_panel(self):
        return pn.Column(
            hint("Inspect the full experiment and choose the analysis range by "
                 "dragging on the plot.", tone="info"),
            self.controls.advanced_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
```

**`qcm/viz/steps/reference.py`** — replace the whole file:

```python
"""Reference focus: highlight the zero/reference window + baseline helpers."""
from __future__ import annotations

import panel as pn

from ..components import hint
from ._base import BaseStep


class ReferenceStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("baseline")

    def secondary_panel(self):
        return pn.Column(
            hint("Pick a quiet, stable window before the experiment changes. "
                 "Drag on the plot (brush targets the reference range here).", tone="info"),
            pn.bind(self.controls.zero_reference_readout,
                    self.controls.t_range, self.controls.baseline_range),
            pn.Row(self.controls.revert_baseline, self.controls.baseline_full_range_button,
                   margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
```

Note: `baseline_range`, its number inputs, and `use_selection_as_baseline` are mounted by the selection bar (Task 7); the Reference secondary panel only adds the read-only readout plus the `revert_baseline` and `baseline_full_range_button` buttons (which the selection bar does not mount).

**`qcm/viz/steps/quantify.py`** — keep `target_state`, `selected_target_summary_table`, `quantity_plot`, `_stats`, `summary_stats_table`, `full_stats_table`, `region_readout`, `df_plot`, `_reference_hint`. Delete `controls_for_quantity`, `stats_view`, and `view`. Add the two methods below (the file already imports `panel as pn`):

```python
    def anchor_plot(self):
        return self.quantity_plot()

    def secondary_panel(self):
        hint_block = pn.bind(lambda *_: self._reference_hint(), *self.controls.explore_inputs)
        target = pn.Column(
            self.controls.analysis_region_select,
            pn.bind(lambda *_: self.selected_target_summary_table(),
                    *self.controls.explore_inputs,
                    self.controls.analysis_region_select, self.controls.annotation_version),
            margin=0, sizing_mode="stretch_width", css_classes=["analysis-target-stack"],
        )
        stats = pn.Column(
            self.panel(self.summary_stats_table, *self.controls.explore_inputs, title="Statistics"),
            self.panel(self.region_readout, *self.controls.explore_inputs, title="Per-channel readout"),
            self.panel(self.df_plot, *self.controls.explore_inputs,
                       self.controls.plot_reset_version, title="ΔD vs Δf/n"),
            self.panel(self.full_stats_table, *self.controls.explore_inputs, title="Advanced statistics"),
            margin=0, sizing_mode="stretch_width",
        )
        return pn.Column(hint_block, target, stats, margin=0,
                         sizing_mode="stretch_width", css_classes=["qcm-secondary"])
```

**`qcm/viz/steps/phases.py`** — keep `phase_plot`, `phases_table`, `_on_phase_action`, `phase_matrix`, `phase_rollup`, `phase_response_ranking`. Delete `compact_phase_controls` and `view`. Add (the file already imports `panel as pn` and `hint`):

```python
    def anchor_plot(self):
        return self.phase_plot()

    def secondary_panel(self):
        mark_editor = pn.Card(
            self.controls.mark_range,
            self.controls._number_row("mark"),
            pn.Row(self.controls.mark_full_range_button, margin=0,
                   sizing_mode="stretch_width", css_classes=["range-actions"]),
            self.controls.phase_mark_controls(include_card=False),
            title="Mark range", collapsible=False, margin=0,
            sizing_mode="stretch_width",
            css_classes=["plot-controls", "range-editor-card", "mark-range-card"],
        )
        return pn.Column(
            hint("Mark injections, rinses, equilibrations, or artifacts. Saved "
                 "phases can be analyzed in Quantify and included in exports.", tone="info"),
            mark_editor,
            pn.bind(lambda *_: self.phases_table(), self.controls.annotation_version),
            self.panel(self.phase_rollup, *self.controls.explore_inputs, title="Phase rollup"),
            self.panel(self.phase_response_ranking, *self.controls.explore_inputs, title="Response ranking"),
            self.panel(self.phase_matrix, *self.controls.explore_inputs, title="Per-channel matrix"),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
```

The `mark_range`, its number row, the mark full-range button, and `phase_mark_controls` (region label/type + mark buttons) are mounted **only** here — they appear when Phases is the active focus.

**`qcm/viz/steps/report.py`** — replace the whole file:

```python
"""Report focus: overview anchor + export controls."""
from __future__ import annotations

import panel as pn

from ._base import BaseStep


class ReportStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("current")

    def secondary_panel(self):
        return pn.Card(
            self.controls.marker_select,
            self.actions.export_data_dl,
            self.actions.export_nb_dl,
            title="Export", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_steps_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/steps/
git commit -m "feat: give each step an anchor_plot and secondary_panel for the workbench"
```

---

## Phase 3 — Consolidated styling

### Task 6: Replace `design.py` with one token block + one scoped stylesheet

**Files:**
- Modify: `qcm/viz/design.py` (full rewrite of the CSS)
- Test: `tests/test_design_tokens.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_design_tokens.py
from qcm.viz.design import APP_CSS


def test_single_root_token_block():
    # Tokens defined exactly once: no competing :root redefinitions.
    assert APP_CSS.count(":root") == 1


def test_no_appended_css_war():
    # The stylesheet is one string, not six appended override passes.
    assert "Single-screen compaction" not in APP_CSS
    assert "Iteration:" not in APP_CSS


def test_triad_regions_not_hidden():
    # The workbench regions must never be display:none-d.
    for region in (".qcm-context-bar { display: none",
                   ".qcm-context-bar{display:none",
                   ".qcm-footer { display: none"):
        assert region not in APP_CSS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_design_tokens.py -q`
Expected: FAIL (multiple `:root`, appended blocks, hidden regions present).

- [ ] **Step 3: Replace the entire `design.py` module**

Replace everything in `qcm/viz/design.py` with the following single module:

```python
"""Single source of truth for the QCM workbench look.

One :root token block + one scoped stylesheet (rules live under `.qcm-app`
so they win by structure, not by `!important`). Light only.
"""
from __future__ import annotations

APP_CSS = """
:root {
  color-scheme: light only;
  --qcm-bg: #eef2f7;
  --qcm-surface: #ffffff;
  --qcm-surface-muted: #f5f8fc;
  --qcm-border: #d3dce8;
  --qcm-border-strong: #b3c0d3;
  --qcm-text: #0f172a;
  --qcm-text-soft: #334155;
  --qcm-muted: #5b6b82;
  --qcm-accent: #2563eb;
  --qcm-accent-strong: #1d4ed8;
  --qcm-accent-soft: #eff6ff;
  --qcm-success: #16a34a;
  --qcm-warning: #d97706;
  --qcm-danger: #dc2626;
  --qcm-space-1: 4px;
  --qcm-space-2: 8px;
  --qcm-space-3: 12px;
  --qcm-space-4: 16px;
  --qcm-space-5: 24px;
  --qcm-radius-sm: 8px;
  --qcm-radius-md: 12px;
  --qcm-radius-lg: 16px;
  --qcm-shadow-1: 0 1px 2px rgba(15, 23, 42, 0.05);
  --qcm-shadow-2: 0 8px 24px rgba(15, 23, 42, 0.08);
  --qcm-font: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

html, body {
  margin: 0;
  font-family: var(--qcm-font);
  background: var(--qcm-bg);
  color: var(--qcm-text);
}
* { box-sizing: border-box; }
.main { max-width: 100vw; overflow-x: hidden; padding: var(--qcm-space-4) var(--qcm-space-5); background: var(--qcm-bg); }
.sidebar, #sidebar, .bk-sidebar, aside.sidebar { display: none; width: 0; min-width: 0; padding: 0; border: 0; }

/* App shell layout ----------------------------------------------------- */
.qcm-app { display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-body { display: flex; gap: var(--qcm-space-3); align-items: flex-start; }

.qcm-context-bar {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; gap: var(--qcm-space-3); flex-wrap: wrap;
  border: 1px solid var(--qcm-border); background: rgba(255,255,255,0.92);
  backdrop-filter: blur(6px); border-radius: var(--qcm-radius-lg);
  padding: var(--qcm-space-2) var(--qcm-space-4); box-shadow: var(--qcm-shadow-1);
}
.qcm-run-id { font-size: 1.05rem; font-weight: 800; color: var(--qcm-text); }
.qcm-context-readout { color: var(--qcm-muted); font-size: 0.82rem; font-variant-numeric: tabular-nums; }

.qcm-focus-rail { flex: 0 0 188px; display: flex; flex-direction: column; gap: var(--qcm-space-2);
  border: 1px solid var(--qcm-border); background: var(--qcm-surface);
  border-radius: var(--qcm-radius-lg); padding: var(--qcm-space-3); }
.qcm-focus-rail .bk-btn { width: 100%; justify-content: flex-start; border-radius: var(--qcm-radius-sm); font-weight: 650; }

.qcm-plotzone { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-rightzone { flex: 0 0 380px; display: flex; flex-direction: column; gap: var(--qcm-space-3); }

.qcm-anchor, .qcm-card, .viewer-card, .bk-card {
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md);
  background: var(--qcm-surface); box-shadow: var(--qcm-shadow-1); margin: 0;
}
.bk-card-header { min-height: 32px; padding: var(--qcm-space-2) var(--qcm-space-3);
  border-bottom: 1px solid var(--qcm-border); background: var(--qcm-surface-muted);
  color: var(--qcm-text); font-weight: 700; }
.bk-card-body { padding: var(--qcm-space-3); }

.qcm-selection-bar { display: flex; gap: var(--qcm-space-3); align-items: flex-start; flex-wrap: wrap; }
.qcm-selection-bar > * { flex: 1 1 280px; min-width: 0; }

.qcm-stats { display: flex; flex-direction: column; gap: var(--qcm-space-2);
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md);
  background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-secondary { display: flex; flex-direction: column; gap: var(--qcm-space-3); }

/* Components (used by components.py) ----------------------------------- */
.qcm-section-title { display: flex; flex-direction: column; gap: 2px; }
.qcm-section-title .eyebrow, .eyebrow { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.qcm-section-title h2 { margin: 0; font-size: 1.05rem; font-weight: 800; color: var(--qcm-text); }
.qcm-metric-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--qcm-space-2); }
.qcm-stat { border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md); background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-stat .label { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-stat .value { color: var(--qcm-text); font-size: 1.1rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.qcm-stat .caption { color: var(--qcm-muted); font-size: 0.78rem; }
.qcm-stat.accent { border-color: #bfdbfe; background: var(--qcm-accent-soft); }
.qcm-pill { display: inline-grid; gap: 1px; min-width: 88px; border: 1px solid var(--qcm-border); border-radius: 999px; background: var(--qcm-surface-muted); padding: 6px 11px; }
.qcm-pill .label { color: var(--qcm-muted); font-size: 0.68rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-pill .value { color: var(--qcm-text); font-size: 0.92rem; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }
.qcm-empty { border: 1px dashed var(--qcm-border-strong); background: var(--qcm-surface-muted); border-radius: var(--qcm-radius-md); padding: var(--qcm-space-4); color: var(--qcm-muted); }
.qcm-hint { display: flex; gap: var(--qcm-space-2); align-items: center; border-radius: var(--qcm-radius-md); padding: var(--qcm-space-2) var(--qcm-space-3); font-size: 0.86rem; }
.qcm-hint.info { border: 1px solid #bfdbfe; background: var(--qcm-accent-soft); color: var(--qcm-accent-strong); }
.qcm-hint.warning { border: 1px solid #fde68a; background: #fffbeb; color: #92400e; }

/* Inputs / tables ------------------------------------------------------ */
.bk-input, .bk-input-group input, select, textarea { border-radius: var(--qcm-radius-sm); border-color: var(--qcm-border-strong); color: var(--qcm-text); background-color: #fff; font-variant-numeric: tabular-nums; }
.bk-btn { border-radius: var(--qcm-radius-sm); font-weight: 650; box-shadow: none; }
.range-number-row { gap: var(--qcm-space-2); }
.range-number-row .bk-input { text-align: right; }
.range-actions { gap: var(--qcm-space-2); }
.summary-table .tabulator, .tabulator { font-size: 0.8rem; border-radius: var(--qcm-radius-sm); border: 1px solid var(--qcm-border); overflow: hidden; }
.tabulator .tabulator-row .tabulator-cell, .tabulator .tabulator-header .tabulator-col { padding: 4px 8px; }

/* QC drawer ------------------------------------------------------------ */
.qcm-drawer { position: fixed; top: 0; right: 0; height: 100vh; width: min(680px, 92vw);
  z-index: 50; overflow-y: auto; background: var(--qcm-surface);
  border-left: 1px solid var(--qcm-border); box-shadow: var(--qcm-shadow-2); padding: var(--qcm-space-4); }
.qcm-drawer-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--qcm-space-3); }

/* Keep any stray dark-mode toggles hidden (defensive, third-party). */
button[title*="theme" i], button[aria-label*="theme" i], .theme-toggle, .pn-theme-toggle { display: none !important; }

@media (max-width: 1200px) {
  .qcm-body { flex-direction: column; }
  .qcm-focus-rail { flex-direction: row; flex-wrap: wrap; flex: 1 1 auto; }
  .qcm-rightzone { flex: 1 1 auto; width: 100%; }
  .main { padding: var(--qcm-space-3); }
}
"""
```

- [ ] **Step 4: Run the design test + the dead-import test**

Run: `python -m pytest tests/test_design_tokens.py tests/test_no_dead_imports.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/design.py tests/test_design_tokens.py
git commit -m "refactor: collapse design.py into one token block + scoped stylesheet"
```

---

## Phase 4 — The workbench shell

### Task 7: Rewrite `shell.py` as the workbench

**Files:**
- Modify: `qcm/viz/shell.py` (full rewrite)
- Test: `tests/test_shell_smoke.py` (rewrite — Task 8)

- [ ] **Step 1: Replace `qcm/viz/shell.py` entirely**

```python
"""Workbench shell.

Owns the persistent triad (anchor plot + selection bar + live stats) and a
focus rail that swaps the secondary panel and re-targets the plot brush. All
analysis state stays in the single ViewerControls instance; ``focus`` is
transient UI state held here.
"""
from __future__ import annotations

import panel as pn

from . import nav
from .actions import ViewerActions
from .components import pill, section_title
from .controls import ViewerControls
from .data import QCMViewData
from .design import APP_CSS
from .state import RunInfo
from .steps.phases import PhasesStep
from .steps.qc_drawer import QCDrawer
from .steps.quantify import QuantifyStep
from .steps.reference import ReferenceStep
from .steps.report import ReportStep
from .steps.review import ReviewStep


class ViewerShell:
    """Assemble the workbench without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

        self.focus = pn.widgets.IntInput(value=0, visible=False)
        # Back-compat alias: existing tests/scripts set shell.step.value.
        self.step = self.focus
        self.drawer_open = pn.widgets.Checkbox(value=False, visible=False)

        self._steps = {
            "review": ReviewStep(controls, data, actions),
            "reference": ReferenceStep(controls, data, actions),
            "phases": PhasesStep(controls, data, actions),
            "quantify": QuantifyStep(controls, data, actions),
            "report": ReportStep(controls, data, actions),
        }
        self._qc = QCDrawer(controls, data, actions)
        self.focus.param.watch(self._on_focus_change, "value")
        self.controls.brush_mode.value = nav.brush_target_for_step("review")

    # -- reactions --------------------------------------------------------
    def _on_focus_change(self, event) -> None:
        self.controls.brush_mode.value = nav.brush_target_for_step(nav.step_id(int(event.new)))

    def _go(self, index: int):
        def handler(_event=None):
            self.focus.value = nav.clamp_step(index)
        return handler

    def _open_drawer(self, _event=None) -> None:
        self.drawer_open.value = True

    def _close_drawer(self, _event=None) -> None:
        self.drawer_open.value = False

    def _active_step(self, active):
        return self._steps[nav.step_id(int(active))]

    # -- persistent regions ----------------------------------------------
    def context_bar(self):
        inspect = pn.widgets.Button(name="Inspect raw sweeps", button_type="default", icon="microscope")
        inspect.on_click(self._open_drawer)
        meta = pill("Duration", f"{self.info.span_s:,.0f} s") + pill("Channels", str(len(self.info.groups)))
        readout = pn.bind(self.controls.zero_reference_summary,
                          self.controls.t_range, self.controls.baseline_range)
        return pn.Row(
            pn.pane.HTML(f"<div class='qcm-run-id'>{self.info.run_id}</div>", margin=0),
            pn.pane.HTML(meta, margin=0),
            self.controls.compact_channel_controls(),
            pn.layout.HSpacer(),
            readout,
            inspect,
            self.controls.save_state_button,
            self.controls.status,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-context-bar"],
        )

    def focus_rail(self):
        def render(active: int):
            active = nav.clamp_step(int(active))
            buttons = []
            for i, step in enumerate(nav.STEPS):
                btn = pn.widgets.Button(
                    name=f"{i + 1}. {step.label}",
                    button_type="primary" if i == active else "default",
                    sizing_mode="stretch_width",
                )
                btn.on_click(self._go(i))
                buttons.append(btn)
            return pn.Column(*buttons, margin=0, css_classes=["qcm-focus-rail"])
        return pn.bind(render, self.focus)

    def anchor(self):
        def render(active, *_):
            return self._active_step(active).anchor_plot()
        return pn.bind(
            render, self.focus,
            *self.controls.explore_inputs,
            self.controls.mark_range.param.value_throttled,
            self.controls.analysis_region_select,
            self.controls.annotation_version,
            self.controls.plot_reset_version,
        )

    def selection_bar(self):
        tools = pn.Column(
            self.controls.quantity_select,
            self.controls.brush_mode,
            pn.bind(self.controls.draw_mode_status, self.controls.brush_mode),
            pn.Row(self.controls.plot_reset_button(), self.controls.use_selection_as_baseline,
                   margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
            margin=0, sizing_mode="stretch_width",
        )
        return pn.Row(
            self.controls.current_range_compact(),
            self.controls.zero_reference_controls(),
            tools,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selection-bar"],
        )

    def live_stats(self):
        body = pn.bind(lambda *_: self._steps["review"].current_range_summary_cards(),
                       *self.controls.signal_inputs)
        return pn.Column(
            section_title("Live statistics", eyebrow="current range"),
            body, margin=0, sizing_mode="stretch_width", css_classes=["qcm-stats"],
        )

    def secondary(self):
        def render(active):
            return self._active_step(active).secondary_panel()
        return pn.bind(render, self.focus)

    def drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
        panel = pn.Column(
            pn.Row(pn.pane.HTML("<b>Raw sweep / QC inspection</b>", margin=0),
                   pn.layout.HSpacer(), close, margin=0, sizing_mode="stretch_width",
                   css_classes=["qcm-drawer-header"]),
            self._qc.view(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        return panel

    def view(self):
        plotzone = pn.Column(
            pn.Card(self.anchor(), hide_header=True, margin=0,
                    sizing_mode="stretch_width", css_classes=["qcm-anchor"]),
            self.selection_bar(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-plotzone"],
        )
        rightzone = pn.Column(
            self.live_stats(), self.secondary(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-rightzone"],
        )
        body = pn.Row(
            self.focus_rail(), plotzone, rightzone,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-body"],
        )
        return pn.Column(
            self.context_bar(), body, self.drawer(),
            margin=0, sizing_mode="stretch_width",
            css_classes=["qcm-app"], stylesheets=[APP_CSS],
        )
```

- [ ] **Step 2: Smoke-check the app builds before rewriting the test**

Run: `python -c "from qcm.viz.app import app; print(type(app('view-run')))"`
Expected: prints a Panel type (e.g. `<class 'panel.layout.base.Column'>`) with no traceback.

- [ ] **Step 3: Commit**

```bash
git add qcm/viz/shell.py
git commit -m "feat: rewrite shell as persistent coordinated-views workbench"
```

---

### Task 8: Rewrite the shell smoke test for the workbench

**Files:**
- Modify: `tests/test_shell_smoke.py` (full rewrite)

- [ ] **Step 1: Write the new tests**

```python
# tests/test_shell_smoke.py
import panel as pn

from qcm.viz import nav


def _classes(obj, found=None):
    """Recursively collect css_classes across the Panel tree."""
    found = found if found is not None else set()
    for c in getattr(obj, "css_classes", None) or []:
        found.add(c)
    for child in getattr(obj, "objects", None) or []:
        _classes(child, found)
    return found


def test_app_builds(demo_run_path):
    from qcm.viz.app import app
    view = app(str(demo_run_path))
    assert view is not None
    assert hasattr(view, "servable")


def test_triad_present_in_every_focus(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    for i in range(len(nav.STEPS)):
        viewer.shell.focus.value = i
        classes = _classes(viewer.shell.view())
        for region in ("qcm-anchor", "qcm-selection-bar", "qcm-stats", "qcm-focus-rail"):
            assert region in classes, f"{region} missing in focus {nav.step_id(i)}"


def test_focus_change_keeps_controls_state(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    ctrls = viewer.shell.controls
    ctrls.t_range.value = (10.0, 20.0)
    viewer.shell.focus.value = 3  # Quantify
    assert tuple(ctrls.t_range.value) == (10.0, 20.0)
    # Brush target follows the focus.
    assert ctrls.brush_mode.value == nav.brush_target_for_step("quantify")
    viewer.shell.focus.value = 2  # Phases
    assert ctrls.brush_mode.value == nav.brush_target_for_step("phases")


def test_drawer_toggles(demo_run_path):
    from qcm.viz.app import QCMViewer
    viewer = QCMViewer(str(demo_run_path))
    viewer.shell._open_drawer()
    assert viewer.shell.drawer_open.value is True
    viewer.shell._close_drawer()
    assert viewer.shell.drawer_open.value is False
```

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (nav, components, plot_theme, design tokens, steps contract, dead imports, shell smoke).

- [ ] **Step 3: Commit**

```bash
git add tests/test_shell_smoke.py
git commit -m "test: workbench composition smoke tests (triad in every focus)"
```

---

## Phase 5 — Verify in the running app

### Task 9: Manual verification and coverage check

**Files:** none (verification only)

- [ ] **Step 1: Serve the app and eyeball the workbench**

Run: `python -m panel serve qcm/panel_app.py --show --args ./view-run`
Verify in the browser:
- The plot, the selection bar (current + reference range editors), and the live-stats panel are **all visible at once** in every focus.
- Clicking a focus-rail item swaps the right-hand secondary panel **without** the plot/selection/stats disappearing.
- Dragging on the plot updates the current range in Overview/Quantify, the reference range in Reference, and the mark range in Phases.
- "Inspect raw sweeps" opens the drawer; "Close ✕" closes it.
- No context bar / footer is hidden-but-built; the layout reads as one calm, professional surface.

- [ ] **Step 2: Coverage on the touched presentation modules**

Run: `python -m pytest --cov=qcm.viz --cov-report=term-missing -q`
Expected: suite green; review that `nav`, `design`, `shell`, `components`, and `steps/*` are exercised. Add a focused test for any uncovered pure-logic branch you introduced.

- [ ] **Step 3: Final commit (if any coverage tests were added)**

```bash
git add -A
git commit -m "test: cover remaining workbench logic branches"
```

---

## Self-review notes (author)

- **Spec coverage:** styling consolidation → Task 2 + Task 6; dead-code deletion → Task 2; wizard→workbench (persistent triad + focus rail + brush-follows-focus) → Tasks 4/5/7/8; QC drawer retained → Task 7; frozen logic layers → respected (no edits to run/data/science/plots/actions/theme/state); tests → Tasks 1–9.
- **Footer:** the spec left it optional; this plan **drops** it (Back/Next is meaningless in a workbench) and moves Save workspace into the context bar.
- **Widget single-mount:** enforced via the ownership map; Reference/Phases/Quantify/Report secondary panels never re-mount selection-bar widgets.
- **Naming consistency:** `shell.focus` is the canonical attribute; `shell.step` is kept as an alias so any external script setting `step.value` still works. `nav.step_id`/`clamp_step`/`brush_target_for_step` are reused unchanged.
