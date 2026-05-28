# QCM Viewer UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the QCM Viewer presentation layer into a guided linear stepper (Review → Reference → Phases → Quantify → Report) with a refined light-scientific look, a persistent context bar, and a raw-sweep QC drawer — without touching the data/science/plots/actions logic.

**Architecture:** Introduce a small `nav` (pure logic) + `components` (token-driven UI building blocks) + `shell` (stepper assembly) + `steps/` (one file per step) stack. Build the new stack alongside the old one so the app keeps running, cut `app.py` over to the new shell, then delete the retired `pages.py`/`layout.py` and orphaned `design.py` helpers. Pure logic is TDD'd; Panel composition is verified by a smoke test plus manual browser checks.

**Tech Stack:** Python 3.11+, Panel ≥1.5, HoloViews ≥1.19, Bokeh ≥3.4, Polars, DuckDB, pytest (+pytest-cov).

**Spec:** `docs/superpowers/specs/2026-05-28-qcm-ui-overhaul-design.md`

**Conventions for every task below:**
- The virtualenv at `.venv` is already active (its `python` is on PATH). Use `python -m pytest ...`.
- Frozen (do not edit): `qcm/viz/data.py`, `qcm/viz/science.py`, `qcm/viz/plots.py`, `qcm/viz/actions.py`, `qcm/viz/state.py`, and the `QUANTITIES` registry in `qcm/viz/theme.py`.
- During migration, `qcm/viz/pages.py` and `qcm/viz/layout.py` stay in place and working until Task 13. New step files are **copied-and-adapted** from the page classes (not moved), so the old app keeps running. The transient duplication is removed in Task 13.

---

## Task 1: Test infrastructure

**Files:**
- Modify: `pyproject.toml:28`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add pytest-cov to dev deps**

In `pyproject.toml`, replace line 28:

```toml
dev = ["pytest>=8", "ruff>=0.5"]
```

with:

```toml
dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.5"]
```

- [ ] **Step 2: Install dev extras into the venv**

Run: `python -m pip install -e ".[dev]"`
Expected: installs pytest and pytest-cov; ends with `Successfully installed ...`.

- [ ] **Step 3: Create a conftest that exposes the demo run path**

Create `tests/conftest.py`:

```python
"""Shared test fixtures for the QCM viewer."""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_RUN = _REPO_ROOT / "view-run"


@pytest.fixture(scope="session")
def demo_run_path() -> Path:
    """Path to the ingested demo run used by composition smoke tests."""
    if not (_DEMO_RUN / "manifest.json").exists():
        pytest.skip("view-run/manifest.json missing; run the ingest demo first")
    return _DEMO_RUN
```

- [ ] **Step 4: Verify pytest collects with no errors**

Run: `python -m pytest -q`
Expected: `no tests ran` (exit code 5) — confirms pytest works and conftest imports cleanly.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/conftest.py
git commit -m "test: add pytest-cov and demo-run fixture"
```

---

## Task 2: Design tokens & global stylesheet

Rewrite `qcm/viz/design.py` so the stylesheet is built from an explicit token set and gains the CSS classes the new components/shell need. **Keep** the existing helper functions (`_html`, `section_header`, `metric_card`, `metric_table`, `meta_pill`) untouched at the bottom of the file — `pages.py`/`layout.py` still use them until Task 13.

**Files:**
- Modify: `qcm/viz/design.py:13-353` (the `APP_CSS` string only)

- [ ] **Step 1: Replace the `APP_CSS` token block and add component classes**

In `qcm/viz/design.py`, replace the `:root { ... }` block (lines 14-31) with this expanded token set, and **append** the new component CSS (shown next) to the end of the existing `APP_CSS` string (before the closing `"""`). Keep all existing rules in between.

Replacement `:root` block:

```css
:root {
  color-scheme: light only;
  --qcm-bg: #f5f7fa;
  --qcm-surface: #ffffff;
  --qcm-surface-muted: #f8fafc;
  --qcm-border: #e2e8f0;
  --qcm-border-strong: #cbd5e1;
  --qcm-text: #0f172a;
  --qcm-text-soft: #334155;
  --qcm-muted: #64748b;
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
  --qcm-space-6: 32px;
  --qcm-radius-sm: 8px;
  --qcm-radius-md: 12px;
  --qcm-radius-lg: 16px;
  --qcm-shadow-1: 0 1px 2px rgba(15, 23, 42, 0.05);
  --qcm-shadow-2: 0 1px 2px rgba(15, 23, 42, 0.05), 0 8px 24px rgba(15, 23, 42, 0.06);
  --qcm-shadow-3: 0 12px 40px rgba(15, 23, 42, 0.16);
  --qcm-font: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
html, body { font-family: var(--qcm-font); }
```

CSS to **append** before the closing `"""` of `APP_CSS`:

```css

/* ---- New component layer (shell/steps/components) -------------------- */
.qcm-shell { display: flex; flex-direction: column; gap: var(--qcm-space-3); }

.qcm-context-bar {
  position: sticky; top: 0; z-index: 20;
  display: flex; flex-direction: column; gap: var(--qcm-space-2);
  border: 1px solid var(--qcm-border);
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(6px);
  border-radius: var(--qcm-radius-lg);
  padding: var(--qcm-space-3) var(--qcm-space-4);
  box-shadow: var(--qcm-shadow-1);
}
.qcm-context-row { display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-3); flex-wrap: wrap; }
.qcm-run-id { font-size: 1.05rem; font-weight: 700; color: var(--qcm-text); }
.qcm-context-readout { color: var(--qcm-muted); font-size: 0.82rem; font-variant-numeric: tabular-nums; }

.qcm-step-nav { display: flex; gap: var(--qcm-space-2); flex-wrap: wrap; }
.qcm-step-nav .bk-btn { border-radius: 999px !important; font-weight: 650 !important; }

.qcm-card {
  border: 1px solid var(--qcm-border) !important;
  border-radius: var(--qcm-radius-md) !important;
  background: var(--qcm-surface) !important;
  box-shadow: var(--qcm-shadow-1) !important;
}
.qcm-toolbar {
  display: flex; gap: var(--qcm-space-3); flex-wrap: wrap; align-items: flex-end;
  padding: var(--qcm-space-3); border: 1px solid var(--qcm-border);
  border-radius: var(--qcm-radius-md); background: var(--qcm-surface-muted);
}

.qcm-section-title { display: flex; flex-direction: column; gap: 2px; }
.qcm-section-title .eyebrow { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.qcm-section-title h2 { margin: 0; font-size: 1.2rem; font-weight: 700; color: var(--qcm-text); }

.qcm-metric-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--qcm-space-3); }
.qcm-stat { border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md); background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-stat .label { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-stat .value { color: var(--qcm-text); font-size: 1.1rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.qcm-stat .caption { color: var(--qcm-muted); font-size: 0.78rem; }
.qcm-stat.accent { border-color: #bfdbfe; background: var(--qcm-accent-soft); }
.qcm-stat.success { border-color: #bbf7d0; background: #f0fdf4; }
.qcm-stat.warning { border-color: #fed7aa; background: #fffbeb; }
.qcm-stat.danger { border-color: #fecaca; background: #fef2f2; }

.qcm-pill { display: inline-grid; gap: 1px; min-width: 88px; border: 1px solid var(--qcm-border); border-radius: 999px; background: var(--qcm-surface-muted); padding: 6px 11px; }
.qcm-pill .label { color: var(--qcm-muted); font-size: 0.68rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-pill .value { color: var(--qcm-text); font-size: 0.92rem; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }

.qcm-empty { border: 1px dashed var(--qcm-border-strong); background: var(--qcm-surface-muted); border-radius: var(--qcm-radius-md); padding: var(--qcm-space-4); color: var(--qcm-muted); }

.qcm-hint { display: flex; gap: var(--qcm-space-2); align-items: center; border-radius: var(--qcm-radius-md); padding: var(--qcm-space-2) var(--qcm-space-3); font-size: 0.86rem; }
.qcm-hint.info { border: 1px solid #bfdbfe; background: var(--qcm-accent-soft); color: var(--qcm-accent-strong); }
.qcm-hint.warning { border: 1px solid #fde68a; background: #fffbeb; color: #92400e; }

.qcm-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-3); border-top: 1px solid var(--qcm-border); padding-top: var(--qcm-space-3); }
.qcm-footer .hint { color: var(--qcm-muted); font-size: 0.82rem; }

.qcm-drawer {
  position: fixed; top: 0; right: 0; height: 100vh; width: min(680px, 92vw);
  z-index: 50; overflow-y: auto;
  background: var(--qcm-surface); border-left: 1px solid var(--qcm-border);
  box-shadow: var(--qcm-shadow-3); padding: var(--qcm-space-4);
}
.qcm-drawer-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--qcm-space-3); }
```

- [ ] **Step 2: Verify the module still imports**

Run: `python -c "from qcm.viz import design; assert 'qcm-drawer' in design.APP_CSS; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add qcm/viz/design.py
git commit -m "feat: expand design tokens and add component CSS classes"
```

---

## Task 3: Pure navigation & guidance logic (`nav.py`)

**Files:**
- Create: `qcm/viz/nav.py`
- Test: `tests/test_nav.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_nav.py`:

```python
from qcm.viz import nav


def test_steps_are_five_in_order():
    assert [s.id for s in nav.STEPS] == ["review", "reference", "phases", "quantify", "report"]


def test_clamp_step_bounds():
    assert nav.clamp_step(-3) == 0
    assert nav.clamp_step(99) == 4
    assert nav.clamp_step(2) == 2


def test_step_id_from_index():
    assert nav.step_id(0) == "review"
    assert nav.step_id(4) == "report"
    assert nav.step_id(50) == "report"


def test_next_prev_clamp_at_ends():
    assert nav.next_step(0) == 1
    assert nav.next_step(4) == 4
    assert nav.prev_step(0) == 0
    assert nav.prev_step(3) == 2


def test_brush_target_follows_step():
    assert nav.brush_target_for_step("review") == "current"
    assert nav.brush_target_for_step("reference") == "reference"
    assert nav.brush_target_for_step("phases") == "mark"
    assert nav.brush_target_for_step("quantify") == "current"
    assert nav.brush_target_for_step("report") == "current"
    assert nav.brush_target_for_step("unknown") == "current"


def test_reference_hint_only_when_referenced_and_unset():
    # Referenced quantity with reference == full run -> hint.
    assert nav.needs_reference_hint(True, (0.0, 100.0), 100.0) is True
    # Referenced quantity with a real sub-window -> no hint.
    assert nav.needs_reference_hint(True, (0.0, 20.0), 100.0) is False
    # Absolute quantity -> never hint.
    assert nav.needs_reference_hint(False, (0.0, 100.0), 100.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_nav.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'qcm.viz.nav'`.

- [ ] **Step 3: Implement `nav.py`**

Create `qcm/viz/nav.py`:

```python
"""Pure navigation and guidance logic for the stepper shell.

No Panel imports: everything here is unit-testable plain Python.
"""
from __future__ import annotations

from dataclasses import dataclass

_EPS = 1e-9


@dataclass(frozen=True)
class Step:
    id: str
    label: str


STEPS: tuple[Step, ...] = (
    Step("review", "Review"),
    Step("reference", "Reference"),
    Step("phases", "Phases"),
    Step("quantify", "Quantify"),
    Step("report", "Report"),
)

_BRUSH_BY_STEP = {
    "review": "current",
    "reference": "reference",
    "phases": "mark",
    "quantify": "current",
    "report": "current",
}


def clamp_step(index: int) -> int:
    return max(0, min(len(STEPS) - 1, int(index)))


def step_id(index: int) -> str:
    return STEPS[clamp_step(index)].id


def next_step(index: int) -> int:
    return clamp_step(index + 1)


def prev_step(index: int) -> int:
    return clamp_step(index - 1)


def brush_target_for_step(step_id: str) -> str:
    """Which range a plot box-drag should set, given the active step."""
    return _BRUSH_BY_STEP.get(step_id, "current")


def needs_reference_hint(
    quantity_referenced: bool,
    baseline_s: tuple[float, float],
    span_s: float,
) -> bool:
    """True when a Δ quantity is selected but no real reference window is set.

    "No real reference" means the reference range still spans the whole run.
    """
    if not quantity_referenced:
        return False
    lo, hi = baseline_s
    return abs(float(lo)) < _EPS and abs(float(hi) - float(span_s)) < _EPS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_nav.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/nav.py tests/test_nav.py
git commit -m "feat: add pure navigation and reference-hint logic"
```

---

## Task 4: Reusable UI components (`components.py`)

**Files:**
- Create: `qcm/viz/components.py`
- Test: `tests/test_components.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_components.py`:

```python
import panel as pn

from qcm.viz import components as c


def _html(obj) -> str:
    return obj.object if isinstance(obj, pn.pane.HTML) else str(obj)


def test_pill_returns_escaped_html_string():
    out = c.pill("Duration", "<b>10 s")
    assert "qcm-pill" in out
    assert "&lt;b&gt;10 s" in out  # value is escaped
    assert "Duration" in out


def test_section_title_has_classes_and_escapes():
    out = _html(c.section_title("Review", eyebrow="Step 1"))
    assert "qcm-section-title" in out
    assert "Review" in out
    assert "Step 1" in out


def test_stat_badge_tone_class():
    out = _html(c.stat_badge("Mass", "12.3 ng/cm²", tone="accent"))
    assert "qcm-stat accent" in out
    assert "12.3 ng/cm" in out


def test_metric_strip_renders_each_row():
    out = _html(c.metric_strip([("Range", "100 s", "0–100"), ("Mean", "5", "")]))
    assert "qcm-metric-strip" in out
    assert "Range" in out and "Mean" in out


def test_empty_state_text():
    out = _html(c.empty_state("Nothing here"))
    assert "qcm-empty" in out
    assert "Nothing here" in out


def test_hint_tone_class():
    out = _html(c.hint("Set a <b>reference</b>", tone="warning"))
    assert "qcm-hint warning" in out
    # Inline markup is allowed in hints (trusted callers), so it is NOT escaped.
    assert "<b>reference</b>" in out


def test_card_is_panel_with_class():
    card = c.card(pn.pane.Markdown("x"), title="T")
    assert isinstance(card, pn.Card)
    assert "qcm-card" in card.css_classes


def test_toolbar_is_row_with_class():
    bar = c.toolbar(pn.widgets.Button(name="A"))
    assert isinstance(bar, pn.Row)
    assert "qcm-toolbar" in bar.css_classes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_components.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'qcm.viz.components'`.

- [ ] **Step 3: Implement `components.py`**

Create `qcm/viz/components.py`:

```python
"""Token-driven, reusable Panel UI building blocks for the QCM shell/steps.

Presentational only. HTML-returning helpers escape user/data text; ``hint``
intentionally trusts its caller so step code can pass inline markup.
"""
from __future__ import annotations

from html import escape

import panel as pn


def _html(markup: str, *, css_classes: list[str] | None = None) -> pn.pane.HTML:
    return pn.pane.HTML(markup, margin=0, sizing_mode="stretch_width", css_classes=css_classes or [])


def section_title(title: str, eyebrow: str | None = None) -> pn.pane.HTML:
    eyebrow_html = f"<div class='eyebrow'>{escape(eyebrow)}</div>" if eyebrow else ""
    return _html(
        f"<div class='qcm-section-title'>{eyebrow_html}<h2>{escape(title)}</h2></div>"
    )


def pill(label: str, value: str) -> str:
    """Return an inline HTML pill string (used to compose the context bar)."""
    return (
        "<div class='qcm-pill'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        "</div>"
    )


def stat_badge(label: str, value: str, caption: str = "", *, tone: str = "neutral") -> pn.pane.HTML:
    safe_tone = tone if tone in {"accent", "success", "warning", "danger", "neutral"} else "neutral"
    caption_html = f"<div class='caption'>{escape(caption)}</div>" if caption else ""
    return _html(
        f"<div class='qcm-stat {safe_tone}'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        f"{caption_html}</div>"
    )


def metric_strip(items: list[tuple[str, str, str]]) -> pn.pane.HTML:
    cells = "".join(
        "<div class='qcm-stat'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        + (f"<div class='caption'>{escape(caption)}</div>" if caption else "")
        + "</div>"
        for label, value, caption in items
    )
    return _html(f"<div class='qcm-metric-strip'>{cells}</div>")


def empty_state(text: str) -> pn.pane.HTML:
    return _html(f"<div class='qcm-empty'>{escape(text)}</div>")


def hint(markup: str, *, tone: str = "info") -> pn.pane.HTML:
    safe_tone = tone if tone in {"info", "warning"} else "info"
    return _html(f"<div class='qcm-hint {safe_tone}'>{markup}</div>")


def card(*objects, title: str | None = None, collapsible: bool = False, collapsed: bool = False,
         css_classes: list[str] | None = None) -> pn.Card:
    classes = ["qcm-card", *(css_classes or [])]
    return pn.Card(
        *objects,
        title=title or "",
        collapsible=collapsible,
        collapsed=collapsed,
        hide_header=title is None,
        margin=0,
        sizing_mode="stretch_width",
        css_classes=classes,
    )


def toolbar(*objects) -> pn.Row:
    return pn.Row(*objects, margin=0, sizing_mode="stretch_width", css_classes=["qcm-toolbar"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_components.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/components.py tests/test_components.py
git commit -m "feat: add reusable token-driven UI components"
```

---

## Task 5: Shared Bokeh plot theme (`plot_theme.py`)

**Files:**
- Create: `qcm/viz/plot_theme.py`
- Test: `tests/test_plot_theme.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_plot_theme.py`:

```python
from bokeh.themes import Theme

from qcm.viz import plot_theme


def test_theme_is_bokeh_theme():
    assert isinstance(plot_theme.QCM_BOKEH_THEME, Theme)


def test_apply_is_idempotent_and_callable():
    # Should not raise when called more than once.
    plot_theme.apply()
    plot_theme.apply()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plot_theme.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'qcm.viz.plot_theme'`.

- [ ] **Step 3: Implement `plot_theme.py`**

Create `qcm/viz/plot_theme.py`:

```python
"""A shared Bokeh document theme so plots match the UI chrome.

Applied once at app startup via ``apply()``. Plot-building code in ``plots.py``
is not modified; this only sets document-level visual defaults.
"""
from __future__ import annotations

from bokeh.themes import Theme

_FONT = '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

QCM_BOKEH_THEME = Theme(
    json={
        "attrs": {
            "Plot": {"background_fill_color": "#ffffff", "border_fill_color": "#ffffff", "outline_line_color": None},
            "Axis": {
                "axis_label_text_font": _FONT,
                "axis_label_text_font_style": "normal",
                "axis_label_text_color": "#475569",
                "major_label_text_font": _FONT,
                "major_label_text_color": "#64748b",
                "axis_line_color": "#cbd5e1",
                "major_tick_line_color": "#cbd5e1",
                "minor_tick_line_color": None,
            },
            "Grid": {"grid_line_color": "#eef2f7"},
            "Legend": {
                "label_text_font": _FONT,
                "label_text_color": "#334155",
                "border_line_color": "#e2e8f0",
                "background_fill_alpha": 0.85,
            },
            "Title": {"text_font": _FONT, "text_color": "#0f172a", "text_font_style": "bold"},
        }
    }
)


def apply() -> None:
    """Make the QCM theme the active Bokeh/HoloViews document theme."""
    import holoviews as hv

    hv.renderer("bokeh").theme = QCM_BOKEH_THEME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plot_theme.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/plot_theme.py tests/test_plot_theme.py
git commit -m "feat: add shared Bokeh document theme"
```

---

## Task 6: Step base class (`steps/_base.py`)

Copy the shared `BasePage` helpers into the new package as `BaseStep`. This is a **verbatim copy** of `BasePage` with two changes: the `empty_state` staticmethod delegates to the shared component, and `current_range_summary_cards` returns a `metric_strip`.

**Files:**
- Create: `qcm/viz/steps/__init__.py`
- Create: `qcm/viz/steps/_base.py`

- [ ] **Step 1: Create the package marker**

Create `qcm/viz/steps/__init__.py`:

```python
"""Step views for the QCM stepper shell."""
```

- [ ] **Step 2: Create `_base.py` from `BasePage`**

Copy the entire `BasePage` class body from `qcm/viz/pages.py:21-268` into `qcm/viz/steps/_base.py`, renamed to `BaseStep`, with the header below. Then apply the two edits in Steps 3-4.

Top of `qcm/viz/steps/_base.py`:

```python
"""Shared presentation helpers for stepper step views (copied from BasePage)."""
from __future__ import annotations

from math import isfinite

import holoviews as hv
import panel as pn
import polars as pl

from .. import science  # noqa: F401  (kept for parity; used by subclasses)
from ..actions import ViewerActions
from ..components import empty_state, metric_strip
from ..controls import ViewerControls
from ..data import QCMViewData


class BaseStep:
    # ... (paste the BasePage method bodies here, unchanged except Steps 3-4) ...
```

(Do not copy the original `from .design import metric_card, metric_table, section_header` import line, and do not copy the original `from .theme import quantity` line unless a pasted method uses it — `BasePage` does not, so omit it.)

- [ ] **Step 3: Adapt the `empty_state` staticmethod**

In the copied `empty_state` staticmethod, replace the body so it delegates to the shared component (keeping the same call sites working):

```python
    @staticmethod
    def empty_state(text: str):
        return empty_state(text)
```

- [ ] **Step 4: Adapt `current_range_summary_cards` to use `metric_strip`**

In the copied `current_range_summary_cards`, replace the final `return metric_table(rows)` line with:

```python
            return metric_strip(rows)
```

(The `rows` variable is already a `list[tuple[str, str, str]]`, which `metric_strip` accepts.)

- [ ] **Step 5: Verify the module imports**

Run: `python -c "from qcm.viz.steps._base import BaseStep; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add qcm/viz/steps/__init__.py qcm/viz/steps/_base.py
git commit -m "feat: add BaseStep shared helpers for step views"
```

---

## Task 7: Review & Reference steps

**Files:**
- Create: `qcm/viz/steps/review.py`
- Create: `qcm/viz/steps/reference.py`

- [ ] **Step 1: Create `review.py`**

Copy the `RunReviewPage` class from `qcm/viz/pages.py:271-309` into `qcm/viz/steps/review.py` as `ReviewStep(BaseStep)`. Drop the `section_header("Review")` line from `view()` (the shell renders the step header). Full file:

```python
"""Review step: full-run QCM-D overview and range selection."""
from __future__ import annotations

from dataclasses import replace

import panel as pn

from .. import plots
from ._base import BaseStep


class ReviewStep(BaseStep):
    def hero_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            plot = plots.dual_axis_qcmd(
                norm_df, d_df, full.groups, full.orders, "QCM-D overview",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=state.t_range_s, select_x=True,
            )
            plot = self.with_phase_labels(plot, norm_df)
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"QCM-D plot failed: {exc}", alert_type="danger")

    def view(self):
        controls = pn.Column(
            self.controls.overview_range_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["compact-section"],
        )
        return pn.Column(
            self.panel(
                self.hero_plot, *self.controls.signal_inputs, self.controls.plot_reset_version,
                title="QCM-D overview", controls=controls, controls_position="top",
            ),
            self.panel(self.current_range_summary_cards, *self.controls.signal_inputs, title="Current range"),
            margin=0, sizing_mode="stretch_width", css_classes=["workbench-page", "viewer-page"],
        )
```

- [ ] **Step 2: Create `reference.py` (new step)**

This step is new: it shows the same overview plot with the reference band emphasized, plus the zero/reference editor and the "Set reference = current range" action (already inside `zero_reference_controls`). Full file:

```python
"""Reference step: define the zero/reference window for Δ quantities."""
from __future__ import annotations

from dataclasses import replace

import panel as pn

from .. import plots
from ..components import hint
from ._base import BaseStep


class ReferenceStep(BaseStep):
    def reference_plot(self):
        try:
            state = self.controls.state()
            full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
            norm_df, d_df = self.data.qcmd_frames(full)
            plot = plots.dual_axis_qcmd(
                norm_df, d_df, full.groups, full.orders, "Pick the reference window",
                baseline=state.baseline_s,
                annotation_spans=self.data.annotation_spans(state),
                window=state.baseline_s, select_x=True,
            )
            return self.interactive_plot(plot)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Reference plot failed: {exc}", alert_type="danger")

    def view(self):
        guidance = hint(
            "Drag on the plot or edit the numbers to choose a quiet, stable window. "
            "Δf, Δf/n, ΔD and Sauerbrey mass are measured relative to this window.",
            tone="info",
        )
        controls = pn.Column(
            self.controls.zero_reference_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["compact-section"],
        )
        return pn.Column(
            guidance,
            self.panel(
                self.reference_plot, *self.controls.signal_inputs, self.controls.plot_reset_version,
                title="Reference window", controls=controls, controls_position="top",
            ),
            margin=0, sizing_mode="stretch_width", css_classes=["workbench-page", "viewer-page"],
        )
```

- [ ] **Step 3: Verify both import**

Run: `python -c "from qcm.viz.steps.review import ReviewStep; from qcm.viz.steps.reference import ReferenceStep; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add qcm/viz/steps/review.py qcm/viz/steps/reference.py
git commit -m "feat: add Review and Reference step views"
```

---

## Task 8: Phases, Quantify & Report steps

**Files:**
- Create: `qcm/viz/steps/phases.py`
- Create: `qcm/viz/steps/quantify.py`
- Create: `qcm/viz/steps/report.py`

- [ ] **Step 1: Create `phases.py`**

Copy `PhaseBuilderPage` from `qcm/viz/pages.py:312-426` into `qcm/viz/steps/phases.py` as `PhasesStep(BaseStep)`. Apply exactly these edits:
- Use this header (replacing the original import lines):

```python
"""Phases step: mark, save, and compare experiment phases."""
from __future__ import annotations

import panel as pn
import polars as pl

from ._base import BaseStep
```

- In `view()`, delete the `section_header("Phases & Compare"),` line.
- In `view()`, insert `self.controls.mark_range_controls(),` as the **first** element of the returned `pn.Column(...)` (before `self.panel(self.phases_table, ...)`), so phases can be marked and saved on this step.

Keep `phases_table`, `_on_phase_action`, `phase_matrix`, `phase_rollup`, `phase_response_ranking` unchanged.

- [ ] **Step 2: Create `quantify.py`**

Copy `QuantifyPage` from `qcm/viz/pages.py:429-574` into `qcm/viz/steps/quantify.py` as `QuantifyStep(BaseStep)`. Apply exactly these edits:
- Use this header (replacing the original import lines):

```python
"""Quantify step: selected-quantity timeline, statistics, and fingerprint."""
from __future__ import annotations

import panel as pn
import polars as pl

from .. import plots, science
from ..components import hint
from ..nav import needs_reference_hint
from ..theme import quantity
from ._base import BaseStep
```

- In `view()`, delete the `section_header("Quantify"),` line.
- In `view()`, insert this reference-hint banner as the **first** element of the returned `pn.Column(...)`:

```python
            pn.bind(lambda *_: self._reference_hint(), *self.controls.explore_inputs),
```

- Add this method to the class:

```python
    def _reference_hint(self):
        state = self.controls.state()
        q = quantity(state.quantity)
        if needs_reference_hint(q.referenced, state.baseline_s, float(self.data.info.span_s)):
            return hint(
                "This is a Δ quantity but no reference window is set yet — "
                "go to <b>② Reference</b> to define zero.",
                tone="warning",
            )
        return pn.Spacer(height=0)
```

Keep `quantity_plot`, `_stats`, `summary_stats_table`, `full_stats_table`, `stats_view`, `region_readout`, `df_plot`, `controls_for_quantity` unchanged.

- [ ] **Step 3: Create `report.py`**

Copy `ReportPage` from `qcm/viz/pages.py:662-684` into `qcm/viz/steps/report.py` as `ReportStep(BaseStep)`. Apply exactly these edits:
- Use this header (replacing the original import lines):

```python
"""Report step: summary and exports."""
from __future__ import annotations

import panel as pn

from ._base import BaseStep
```

- In `view()`, delete the `section_header("Report"),` line.

- [ ] **Step 4: Verify all three import**

Run: `python -c "from qcm.viz.steps.phases import PhasesStep; from qcm.viz.steps.quantify import QuantifyStep; from qcm.viz.steps.report import ReportStep; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add qcm/viz/steps/phases.py qcm/viz/steps/quantify.py qcm/viz/steps/report.py
git commit -m "feat: add Phases, Quantify, and Report step views"
```

---

## Task 9: QC drawer (`steps/qc_drawer.py`)

**Files:**
- Create: `qcm/viz/steps/qc_drawer.py`

- [ ] **Step 1: Create `qc_drawer.py`**

Copy `QCPage` from `qcm/viz/pages.py:577-659` into `qcm/viz/steps/qc_drawer.py` as `QCDrawer(BaseStep)`. Apply exactly these edits:
- Use this header (replacing the original import lines):

```python
"""QC drawer: raw-sweep, I/Q, and waterfall inspection (overlay)."""
from __future__ import annotations

import panel as pn

from .. import plots
from ..components import stat_badge
from ._base import BaseStep
```

- In `view()`, delete the `section_header("QC & Raw Sweeps"),` line.
- Replace the `qc_cards` method (which used `metric_card` + `pn.GridBox`) with:

```python
    def qc_cards(self):
        state = self.controls.state()
        selected = len(state.selected_sweep_groups())
        return pn.Row(
            stat_badge("Sweep", str(int(state.sequence)), tone="accent"),
            stat_badge("Channels", str(selected)),
            stat_badge("Frequency band", f"{state.frequency_band[0]:,.1f}–{state.frequency_band[1]:,.1f} Hz"),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-metric-strip"],
        )
```

Keep `sweep_readout`, `sweep_plot`, `iq_plot`, `waterfall_plot` unchanged.

- [ ] **Step 2: Verify it imports**

Run: `python -c "from qcm.viz.steps.qc_drawer import QCDrawer; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add qcm/viz/steps/qc_drawer.py
git commit -m "feat: add QC raw-sweep drawer view"
```

---

## Task 10: Stepper shell (`shell.py`)

**Files:**
- Create: `qcm/viz/shell.py`

- [ ] **Step 1: Create `shell.py`**

Create `qcm/viz/shell.py`:

```python
"""Stepper shell: context bar, step navigator, step canvas, footer, QC drawer."""
from __future__ import annotations

from html import escape

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
    """Assemble the guided stepper UI without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

        self.step = pn.widgets.IntInput(value=0, visible=False)
        self.drawer_open = pn.widgets.Checkbox(value=False, visible=False)

        self._steps = {
            "review": ReviewStep(controls, data, actions),
            "reference": ReferenceStep(controls, data, actions),
            "phases": PhasesStep(controls, data, actions),
            "quantify": QuantifyStep(controls, data, actions),
            "report": ReportStep(controls, data, actions),
        }
        self._qc = QCDrawer(controls, data, actions)
        self.step.param.watch(self._on_step_change, "value")
        # Initialize the brush target for the first step.
        self.controls.brush_mode.value = nav.brush_target_for_step("review")

    # -- reactions --------------------------------------------------------
    def _on_step_change(self, event) -> None:
        self.controls.brush_mode.value = nav.brush_target_for_step(nav.step_id(int(event.new)))

    def _go(self, index: int):
        def handler(_event=None):
            self.step.value = nav.clamp_step(index)
        return handler

    def _open_drawer(self, _event=None) -> None:
        self.drawer_open.value = True

    def _close_drawer(self, _event=None) -> None:
        self.drawer_open.value = False

    # -- regions ----------------------------------------------------------
    def context_bar(self):
        channels = ", ".join(f"n={n}" for _, n in sorted(self.info.orders.items())) or "—"
        meta = "".join([
            pill("Duration", f"{self.info.span_s:,.1f} s"),
            pill("Channels", str(len(self.info.groups))),
            pill("Overtones", channels),
            pill("Sweeps", f"{self.info.n_sweeps:,}"),
        ])
        inspect_btn = pn.widgets.Button(name="Inspect raw sweeps", button_type="default", icon="microscope")
        inspect_btn.on_click(self._open_drawer)

        top = pn.Row(
            pn.pane.HTML(f"<div class='qcm-run-id'>{escape(str(self.info.run_id))}</div>", margin=0),
            pn.pane.HTML(f"<div style='display:flex;gap:8px;flex-wrap:wrap'>{meta}</div>", margin=0),
            inspect_btn,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-context-row"],
        )
        readout = pn.bind(self.controls.zero_reference_summary, self.controls.t_range, self.controls.baseline_range)
        channels_card = self.controls.channel_controls()
        channels_card.collapsed = True
        return pn.Column(
            top, readout, channels_card,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-context-bar"],
        )

    def navigator(self):
        def render(active: int):
            active = nav.clamp_step(int(active))
            buttons = []
            for i, step in enumerate(nav.STEPS):
                btn = pn.widgets.Button(
                    name=f"{i + 1}. {step.label}",
                    button_type="primary" if i == active else "default",
                )
                btn.on_click(self._go(i))
                buttons.append(btn)
            return pn.Row(*buttons, margin=0, sizing_mode="stretch_width", css_classes=["qcm-step-nav"])
        return pn.bind(render, self.step)

    def step_canvas(self):
        def render(active: int):
            idx = nav.clamp_step(int(active))
            step = nav.STEPS[idx]
            return pn.Column(
                section_title(step.label, eyebrow=f"Step {idx + 1} of {len(nav.STEPS)}"),
                self._steps[step.id].view(),
                margin=0, sizing_mode="stretch_width",
            )
        return pn.bind(render, self.step)

    def footer(self):
        back = pn.widgets.Button(name="‹ Back", button_type="default")
        nxt = pn.widgets.Button(name="Next ›", button_type="primary")
        back.on_click(lambda e: setattr(self.step, "value", nav.prev_step(int(self.step.value))))
        nxt.on_click(lambda e: setattr(self.step, "value", nav.next_step(int(self.step.value))))
        return pn.Row(back, pn.layout.HSpacer(), nxt, margin=0, sizing_mode="stretch_width", css_classes=["qcm-footer"])

    def drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
        panel = pn.Column(
            pn.Row(
                pn.pane.HTML("<b>Raw sweep / QC inspection</b>", margin=0), pn.layout.HSpacer(), close,
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer-header"],
            ),
            self._qc.view(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        return panel

    def view(self):
        return pn.Column(
            self.context_bar(),
            self.navigator(),
            self.step_canvas(),
            self.footer(),
            self.drawer(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-shell"],
            stylesheets=[APP_CSS],
        )
```

- [ ] **Step 2: Verify it imports**

Run: `python -c "from qcm.viz.shell import ViewerShell; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add qcm/viz/shell.py
git commit -m "feat: add stepper shell with context bar, navigator, footer, drawer"
```

---

## Task 11: Cut `app.py` over to the shell + composition smoke test

**Files:**
- Modify: `qcm/viz/app.py` (imports, startup, `__init__`, `view`)
- Test: `tests/test_shell_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_shell_smoke.py`:

```python
import panel as pn


def test_viewer_builds_against_demo_run(demo_run_path):
    from qcm.viz.app import app

    view = app(str(demo_run_path))
    assert view is not None
    # The root is a Panel object that can be served.
    assert hasattr(view, "servable")


def test_each_step_renders(demo_run_path):
    from qcm.viz.app import QCMViewer
    from qcm.viz import nav

    viewer = QCMViewer(str(demo_run_path))
    for i in range(len(nav.STEPS)):
        viewer.shell.step.value = i
        rendered = viewer.shell._steps[nav.step_id(i)].view()
        assert isinstance(rendered, pn.Column)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_shell_smoke.py -q`
Expected: FAIL — `QCMViewer` has no attribute `shell` (still uses `ViewerLayout`).

- [ ] **Step 3: Swap the layout import for the shell + theme in `app.py`**

In `qcm/viz/app.py`, replace the import line (line 25):

```python
from .layout import ViewerLayout
```

with these three lines:

```python
from .design import APP_CSS
from .plot_theme import apply as apply_plot_theme
from .shell import ViewerShell
```

- [ ] **Step 4: Apply the plot theme and register CSS at startup**

In `qcm/viz/app.py`, immediately after the `hv.extension("bokeh")` line (line 32), add:

```python
apply_plot_theme()
pn.config.raw_css.append(APP_CSS)
```

- [ ] **Step 5: Build the shell instead of the layout**

In `QCMViewer.__init__`, replace the line (line 44):

```python
        self.layout = ViewerLayout(self.run, self.info, self.controls, self.data, self.actions)
```

with:

```python
        self.shell = ViewerShell(self.run, self.info, self.controls, self.data, self.actions)
```

And replace the `view` method (lines 77-78):

```python
    def view(self):
        return self.layout.view()
```

with:

```python
    def view(self):
        return self.shell.view()
```

- [ ] **Step 6: Run the smoke test to verify it passes**

Run: `python -m pytest tests/test_shell_smoke.py -q`
Expected: PASS (2 passed). If the demo run is absent, both tests SKIP — re-create it with the README demo commands and re-run.

- [ ] **Step 7: Run the whole suite**

Run: `python -m pytest -q`
Expected: all green (nav, components, plot_theme, shell smoke).

- [ ] **Step 8: Commit**

```bash
git add qcm/viz/app.py tests/test_shell_smoke.py
git commit -m "feat: cut viewer over to the stepper shell"
```

---

## Task 12: Manual browser verification

No code changes — this gates the cleanup. The interactive feel cannot be asserted by tests, so verify it in a real browser.

- [ ] **Step 1: Serve the app**

Run: `python -m panel serve qcm/panel_app.py --show --args ./view-run`
Expected: a browser tab opens at `http://localhost:5006/panel_app`.

- [ ] **Step 2: Walk the checklist** (note pass/fail for each)

- [ ] Context bar is visible and sticky; run id + pills render; "Inspect raw sweeps" button present.
- [ ] Step navigator shows 5 steps; clicking each switches the canvas; the active step is highlighted.
- [ ] Back/Next move between steps and clamp at the ends.
- [ ] **State persists across steps:** set channels + current range on Review, switch to Quantify — selections are retained.
- [ ] **Brush follows the step:** drag on the plot in Review → current range updates; in Reference → reference range updates; in Phases → mark range updates.
- [ ] Reference step: "Set reference = current range" updates the zero range and the context-bar readout.
- [ ] Quantify step: selecting a Δ quantity with the reference still at full-run shows the warning hint; setting a real reference clears it.
- [ ] Phases step: marking + naming a phase adds it to the table; delete works.
- [ ] Report step: data export and notebook export download; "Save workspace" reports success.
- [ ] QC drawer opens as a right-side overlay from the context bar, shows sweep/I-Q/waterfall, and closes.
- [ ] Plots adopt the new theme (Inter font, light grid) and there are no console errors in the browser devtools.

- [ ] **Step 3: Stop the server** (Ctrl+C) once the checklist passes. If anything fails, fix it before Task 13 and note the fix in the commit.

---

## Task 13: Retire old modules & finalize

Now that the app runs on the new shell and the checklist passes, delete the retired files and the orphaned helpers, then confirm coverage.

**Files:**
- Delete: `qcm/viz/pages.py`
- Delete: `qcm/viz/layout.py`
- Modify: `qcm/viz/design.py` (remove orphaned helpers)

- [ ] **Step 1: Confirm nothing imports the retired modules**

Run: `grep -rn "viz.pages\|viz.layout\|from .pages\|from .layout\|import pages\|import layout" qcm --include='*.py' | grep -v __pycache__`
Expected: no output (the only importers were each other).

- [ ] **Step 2: Delete the retired modules**

```bash
git rm qcm/viz/pages.py qcm/viz/layout.py
```

- [ ] **Step 3: Remove orphaned helpers from `design.py`**

Confirm the old helpers are now unused:

Run: `grep -rn "section_header\|metric_card\|metric_table\|meta_pill" qcm --include='*.py' | grep -v __pycache__ | grep -v "def "`
Expected: no output.

Then delete the now-unused functions `section_header`, `metric_card`, `metric_table`, `meta_pill`, and the private `_html` helper (only used by them) from the bottom of `qcm/viz/design.py`. Keep `APP_CSS`.

- [ ] **Step 4: Verify imports and full suite still pass**

Run: `python -c "from qcm.viz.app import app; print('ok')"`
Expected: `ok`

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 5: Coverage check on the new logic**

Run: `python -m pytest --cov=qcm.viz.nav --cov=qcm.viz.components --cov=qcm.viz.plot_theme --cov-report=term-missing -q`
Expected: `nav.py` and `components.py` at/above 80%; note any gaps. (Shell/steps are exercised by the smoke test and the manual checklist, not line-covered — this is expected for Panel composition code.)

- [ ] **Step 6: Lint the changed files**

Run: `python -m ruff check qcm/viz/nav.py qcm/viz/components.py qcm/viz/shell.py qcm/viz/plot_theme.py qcm/viz/steps`
Expected: no errors (fix any reported).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: retire pages.py/layout.py and orphaned design helpers"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** tokens/components (Tasks 2, 4) → visual system; nav (Task 3) → stepper logic + brush-by-step + guidance; shell (Task 10) → context bar/navigator/footer/drawer; steps (Tasks 6-9) → the five steps + QC drawer; app cutover (Task 11) + Bokeh theme (Task 5); cleanup (Task 13) retires `pages.py`/`layout.py` with no alias shims. Backend modules are never edited.
- **Runnable throughout:** the old layout serves the app until Task 11; new files are copied (not moved) from `pages.py` so nothing breaks mid-migration; duplication is removed in Task 13.
- **Type consistency:** `metric_strip(items: list[tuple[str,str,str]])` matches the `rows` shape from `current_range_summary_cards`; `needs_reference_hint(bool, tuple, float)` matches the call in `QuantifyStep._reference_hint`; `nav.step_id`/`clamp_step`/`next_step`/`prev_step` are used consistently in `shell.py`.
- **Known gap to watch:** if any step view references a `BasePage`-only attribute that was not copied into `BaseStep`, the smoke test in Task 11 Step 6 will catch it — fix by copying the missing helper into `_base.py`.
