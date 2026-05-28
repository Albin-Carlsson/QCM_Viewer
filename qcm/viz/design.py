"""Light-mode design helpers for the QCM analysis workbench.

This module is intentionally presentational: shared CSS plus tiny HTML helpers.
Behavior stays in controls/actions/data/pages.
"""
from __future__ import annotations

from html import escape

import panel as pn


APP_CSS = """
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
:root { --qcm-radius: var(--qcm-radius-md); --qcm-shadow: var(--qcm-shadow-2); }
html, body {
  margin: 0 !important;
  background: var(--qcm-bg) !important;
  color: var(--qcm-text) !important;
}
body { overscroll-behavior-y: none; }
* { box-sizing: border-box; }

/* Shell ---------------------------------------------------------------- */
.main {
  max-width: 100vw !important;
  overflow-x: hidden !important;
  padding: 16px 22px 28px 22px !important;
  background: var(--qcm-bg) !important;
}
.sidebar,
#sidebar,
.bk-sidebar,
aside.sidebar {
  display: none !important;
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  border: 0 !important;
}
.main-wrap,
.viewer-page,
.workbench-page,
.compact-section,
.plot-controls {
  gap: 12px !important;
}
.main-wrap {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* Typography ------------------------------------------------------------ */
.markdown p,
.markdown h1,
.markdown h2,
.markdown h3,
.markdown ul { margin-top: 0 !important; }
.markdown p { line-height: 1.42 !important; }
.run-title,
.workbench-section h2,
.metric-card h3 {
  margin: 0 !important;
  color: var(--qcm-text);
}
.eyebrow,
.run-meta-label,
.metric-label,
.phase-label {
  color: var(--qcm-muted);
  font-size: 0.72rem;
  font-weight: 760;
  letter-spacing: .075em;
  text-transform: uppercase;
}
.section-copy,
.metric-caption,
.microcopy {
  color: var(--qcm-muted);
  font-size: 0.86rem;
  line-height: 1.35;
}

/* Header ---------------------------------------------------------------- */
.run-hero {
  border: 1px solid var(--qcm-border);
  background: #ffffff;
  border-radius: var(--qcm-radius-lg);
  padding: 12px 14px;
  box-shadow: var(--qcm-shadow);
}
.run-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.run-title {
  font-size: 1.48rem;
  line-height: 1.1;
  font-weight: 810;
}
.run-meta-inline {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: stretch;
  justify-content: flex-end;
}
.run-meta-pill {
  min-width: 92px;
  border: 1px solid var(--qcm-border);
  border-radius: 999px;
  background: var(--qcm-surface-muted);
  padding: 7px 11px;
  display: grid;
  gap: 1px;
}
.run-meta-value {
  color: var(--qcm-text);
  font-size: 0.98rem;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Sections and cards ---------------------------------------------------- */
.workbench-section {
  border: 1px solid var(--qcm-border);
  background: var(--qcm-surface);
  border-radius: var(--qcm-radius-lg);
  padding: 12px 14px;
  box-shadow: var(--qcm-shadow);
}
.workbench-section h2 {
  font-size: 1.18rem;
  line-height: 1.2;
}
.global-controls-row { gap: 12px !important; }
.bk-card,
.viewer-card {
  max-width: 100% !important;
  border: 1px solid var(--qcm-border) !important;
  border-radius: var(--qcm-radius) !important;
  background: var(--qcm-surface) !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.045) !important;
}
.viewer-card { margin: 0 !important; }
.bk-card-header {
  min-height: 34px !important;
  padding: 9px 13px !important;
  border-bottom: 1px solid var(--qcm-border) !important;
  background: var(--qcm-surface-muted) !important;
  color: var(--qcm-text) !important;
  font-weight: 760 !important;
  cursor: pointer !important;
}
.bk-card-body { padding: 12px 13px !important; }

/* Tabs ------------------------------------------------------------------ */
.bk-tabs-header {
  border-bottom: 1px solid var(--qcm-border) !important;
  margin-bottom: 12px !important;
  padding-bottom: 5px !important;
}
.bk-tab,
.bk-tab:not(.bk-active),
.bk-tab:not(.active) {
  border-radius: 999px !important;
  margin-right: 7px !important;
  padding: 7px 11px !important;
  color: #334155 !important;
  font-weight: 740 !important;
  background: transparent !important;
  border: 1px solid transparent !important;
}
.bk-tab.bk-active,
.bk-tab.active,
.bk-tab[aria-selected="true"] {
  color: #ffffff !important;
  background: var(--qcm-accent) !important;
  border-color: var(--qcm-accent) !important;
}

/* Metrics and tables ---------------------------------------------------- */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
  width: 100%;
}
.metric-card {
  border: 1px solid var(--qcm-border);
  background: var(--qcm-surface);
  border-radius: var(--qcm-radius);
  padding: 11px 13px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035);
}
.metric-value {
  color: var(--qcm-text);
  font-size: 1.16rem;
  font-weight: 780;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}
.metric-card.accent { border-color: #bfdbfe; background: #eff6ff; }
.metric-card.success { border-color: #bbf7d0; background: #f0fdf4; }
.metric-card.warning { border-color: #fed7aa; background: #fff7ed; }
.metric-card.danger { border-color: #fecaca; background: #fef2f2; }
.tabulator {
  max-width: 100% !important;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--qcm-border) !important;
  font-size: 0.86rem;
}

/* Inputs and buttons ---------------------------------------------------- */
.bk-input-group { margin-bottom: 8px !important; }
.bk-input,
.bk-input-group input,
select,
textarea {
  border-radius: 10px !important;
  border-color: var(--qcm-border-strong) !important;
  color: var(--qcm-text) !important;
  background-color: #ffffff !important;
  font-variant-numeric: tabular-nums;
}
.bk-btn {
  border-radius: 10px !important;
  font-weight: 720 !important;
  box-shadow: none !important;
}
.range-mode-toggle .bk-btn-group { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)) !important; gap: 8px !important; }
.range-number-row,
.range-actions { gap: 10px !important; }
.range-editor-card .bk-card-body { padding-top: 10px !important; }
.phase-empty-state {
  border: 1px dashed var(--qcm-border-strong);
  background: var(--qcm-surface-muted);
  border-radius: var(--qcm-radius);
  padding: 14px;
}
.plot-first-card .bk-card-body > :first-child { margin-bottom: 12px !important; }


.channels-card .bk-card-body { padding-top: 10px !important; }
.channel-toggles .bk-btn-group {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)) !important;
  gap: 7px !important;
}


.draw-mode-status {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 0.82rem;
  font-weight: 720;
  display: inline-flex;
  width: fit-content;
}
.draw-mode-toggle .bk-btn {
  min-height: 36px !important;
}
.channels-card {
  max-width: 100% !important;
}


.kpi-table-wrap {
  border: 1px solid var(--qcm-border);
  border-radius: var(--qcm-radius);
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035);
}
.kpi-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.kpi-table th {
  background: var(--qcm-surface-muted);
  color: var(--qcm-muted);
  font-size: 0.72rem;
  letter-spacing: .075em;
  text-transform: uppercase;
  text-align: left;
  padding: 9px 12px;
  border-bottom: 1px solid var(--qcm-border);
}
.kpi-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--qcm-border);
  vertical-align: middle;
}
.kpi-table tr:last-child td { border-bottom: 0; }
.kpi-table .kpi-label {
  color: var(--qcm-muted);
  font-weight: 760;
  width: 28%;
}
.kpi-table .kpi-value {
  color: var(--qcm-text);
  font-size: 1rem;
  font-weight: 780;
  font-variant-numeric: tabular-nums;
  width: 32%;
}
.kpi-table .kpi-detail {
  color: var(--qcm-muted);
  font-variant-numeric: tabular-nums;
}

/* Defensive: dark-mode controls should not appear even if Panel changes. */
button[title*="theme" i],
button[aria-label*="theme" i],
.theme-toggle,
.pn-theme-toggle { display: none !important; }

@media (max-width: 1100px) {
  .main { padding-left: 12px !important; padding-right: 12px !important; }
  .run-header-row { align-items: stretch; }
  .run-meta-inline { justify-content: flex-start; }
  .run-meta-pill { min-width: 120px; }
  .metric-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
}

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
"""


def _html(markup: str, *, css_classes: list[str] | None = None) -> pn.pane.HTML:
    return pn.pane.HTML(markup, margin=0, sizing_mode="stretch_width", css_classes=css_classes or [])


def section_header(title: str, _subtitle: str | None = None, copy: str | None = None) -> pn.pane.HTML:
    """Minimal page header.  The UI should be self-explanatory, so no subtitle copy."""
    return _html(
        "<div class='workbench-section page-title-section'>"
        f"<h2>{escape(title)}</h2>"
        "</div>"
    )


def metric_card(label: str, value: str, caption: str = "", *, tone: str = "neutral") -> pn.pane.HTML:
    safe_tone = tone if tone in {"accent", "success", "warning", "danger", "neutral"} else "neutral"
    caption_markup = f"<p class='metric-caption'>{escape(caption)}</p>" if caption else ""
    return _html(
        f"<div class='metric-card {safe_tone}'>"
        f"<div class='metric-label'>{escape(label)}</div>"
        f"<div class='metric-value'>{escape(value)}</div>"
        f"{caption_markup}"
        "</div>"
    )


def metric_table(rows: list[tuple[str, str, str]]) -> pn.pane.HTML:
    body = "".join(
        "<tr>"
        f"<td class='kpi-label'>{escape(label)}</td>"
        f"<td class='kpi-value'>{escape(value)}</td>"
        f"<td class='kpi-detail'>{escape(detail)}</td>"
        "</tr>"
        for label, value, detail in rows
    )
    return _html(
        "<div class='kpi-table-wrap'>"
        "<table class='kpi-table'>"
        "<thead><tr><th>Metric</th><th>Value</th><th>Window / note</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>",
        css_classes=["kpi-table-pane"],
    )

def meta_pill(label: str, value: str) -> str:
    return (
        "<div class='run-meta-pill' style='min-width:92px;border:1px solid #d8e1ee;border-radius:999px;"
        "background:#f8fafc;padding:7px 11px;display:grid;gap:1px'>"
        f"<div class='run-meta-label' style='color:#64748b;font-size:0.72rem;font-weight:760;"
        f"letter-spacing:.075em;text-transform:uppercase'>{escape(label)}</div>"
        f"<div class='run-meta-value' style='color:#0f172a;font-size:0.98rem;font-weight:800;"
        f"line-height:1.1;font-variant-numeric:tabular-nums;white-space:nowrap'>{escape(value)}</div>"
        "</div>"
    )


# Compact scientific-workbench overrides -------------------------------------
APP_CSS += """
:root {
  --qcm-bg: #eef2f7;
  --qcm-surface: #ffffff;
  --qcm-surface-muted: #f3f6fa;
  --qcm-border: #c9d4e2;
  --qcm-border-strong: #aebcd0;
  --qcm-text: #0f172a;
  --qcm-text-soft: #1f2937;
  --qcm-muted: #475569;
  --qcm-shadow-1: none;
  --qcm-shadow-2: none;
}
.main { padding: 8px 10px 14px 10px !important; }
.qcm-shell,
.viewer-page,
.workbench-page,
.compact-section,
.plot-controls { gap: 8px !important; }
.qcm-context-bar {
  border: 1px solid var(--qcm-border-strong) !important;
  background: var(--qcm-surface) !important;
  border-radius: 12px !important;
  padding: 8px !important;
  margin-bottom: 6px !important;
}
.global-toolbar { align-items: end !important; gap: 8px !important; }
.qcm-step-nav {
  border: 1px solid var(--qcm-border-strong) !important;
  background: var(--qcm-surface-muted) !important;
  border-radius: 12px !important;
  padding: 6px !important;
  gap: 6px !important;
}
.qcm-step-nav .bk-btn { min-height: 30px !important; font-weight: 700 !important; }
.qcm-section-title,
.section-title,
.workbench-section h2 { margin: 0 !important; font-size: 1.05rem !important; line-height: 1.2 !important; }
.bk-card,
.viewer-card {
  border: 1px solid var(--qcm-border-strong) !important;
  border-radius: 12px !important;
  box-shadow: none !important;
  background: var(--qcm-surface) !important;
  margin: 0 !important;
}
.bk-card-header {
  min-height: 30px !important;
  padding: 6px 10px !important;
  background: var(--qcm-surface-muted) !important;
  border-bottom: 1px solid var(--qcm-border) !important;
  font-size: .92rem !important;
  font-weight: 750 !important;
}
.bk-card-body { padding: 8px 10px !important; }
.range-editor-card .bk-card-body { padding: 8px !important; }
.range-number-row { gap: 6px !important; }
.range-actions { gap: 6px !important; }
.summary-table .tabulator { font-size: 12px !important; }
.quantify-split { gap: 8px !important; align-items: flex-start !important; }
.quantify-side-panel { gap: 8px !important; }
.phase-empty-state { padding: 8px 10px !important; }
.markdown p { line-height: 1.32 !important; margin-bottom: 6px !important; }
"""

APP_CSS += """
/* ---- Compact page-specific layout fixes ---------------------------------- */
.qcm-context-bar.top-tools-only {
  padding: 4px 6px !important;
  min-height: 0 !important;
  border-color: transparent !important;
  background: transparent !important;
  margin-bottom: 0 !important;
}
.plot-tools-row {
  align-items: flex-end !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
}
.plot-tools-row > .bk-btn,
.plot-tools-row .bk-btn {
  min-width: 150px !important;
}
.plot-tools-row .bk-input-group {
  max-width: 320px !important;
  min-width: 220px !important;
  margin-bottom: 0 !important;
}
.plot-tools-row .channel-controls {
  max-width: 340px !important;
}
.channel-controls .bk-card-header {
  cursor: pointer !important;
}
.compact-two-column {
  display: flex !important;
  gap: 8px !important;
  align-items: flex-start !important;
}
.compact-two-column > *:first-child {
  min-width: 0 !important;
  flex: 1 1 auto !important;
}
.compact-three-column {
  display: grid !important;
  grid-template-columns: minmax(360px, 1.2fr) minmax(360px, 1fr) minmax(360px, 1fr) !important;
  gap: 8px !important;
  align-items: start !important;
}
.review-controls-summary,
.quantify-controls-summary,
.phase-controls-saved {
  margin-top: 6px !important;
}
.review-summary-stack,
.quantify-summary-stack,
.phase-table-stack {
  max-width: 430px !important;
}
.review-page .plot-first-card .bk-card-body,
.phases-page .plot-first-card .bk-card-body,
.quantify-page .plot-first-card .bk-card-body {
  padding: 6px 8px !important;
}
.current-range-card .bk-card-body,
.reference-range-card .bk-card-body,
.mark-range-card .bk-card-body {
  display: grid !important;
  gap: 6px !important;
}
.range-number-row .bk-input-group {
  margin-bottom: 0 !important;
}
.range-number-row .bk-input-group label,
.plot-tools-row .bk-input-group label {
  font-size: 11px !important;
  margin-bottom: 2px !important;
}
.phase-analysis-row > * {
  flex: 1 1 0 !important;
  min-width: 0 !important;
}
.quantify-lower-row > * {
  min-width: 0 !important;
}
.summary-table .tabulator-row .tabulator-cell,
.tabulator-row .tabulator-cell {
  padding-top: 5px !important;
  padding-bottom: 5px !important;
}
.summary-table .tabulator {
  font-size: 11.5px !important;
}
.bk-card-header {
  min-height: 26px !important;
  padding-top: 4px !important;
  padding-bottom: 4px !important;
}
.bk-card-body {
  padding: 6px 8px !important;
}
@media (max-width: 1200px) {
  .compact-two-column,
  .compact-three-column {
    display: flex !important;
    flex-direction: column !important;
  }
  .review-summary-stack,
  .quantify-summary-stack,
  .phase-table-stack {
    width: 100% !important;
    max-width: 100% !important;
  }
}

"""

APP_CSS += """
/* Single-screen compaction pass ------------------------------------------ */
.qcm-shell, .viewer-page, .workbench-page { gap: 6px !important; }
.qcm-step-nav { gap: 6px !important; margin-bottom: 4px !important; }
.qcm-step-nav .bk-btn { padding: 5px 8px !important; min-height: 30px !important; }
.qcm-context-bar { min-height: 0 !important; padding: 0 !important; margin: 0 !important; }
.qcm-footer { display: none !important; }
.viewer-card, .bk-card { margin: 0 !important; }
.bk-card-header { min-height: 28px !important; padding: 5px 9px !important; }
.bk-card-body { padding: 7px 9px !important; }
.plot-controls, .compact-section, .quantify-control-stack, .readout-stats-stack, .stacked-stats { gap: 6px !important; }
.range-editor-card .bk-card-body { padding: 6px 8px !important; }
.range-number-row { gap: 6px !important; }
.range-actions { gap: 6px !important; }
.analysis-region-row { align-items: stretch !important; gap: 8px !important; }
.analysis-region-row > *:first-child { flex: 0 0 230px !important; max-width: 230px !important; }
.analysis-region-row .current-range-card { flex: 1 1 auto !important; }
.quantify-controls-summary { gap: 8px !important; align-items: stretch !important; }
.quantify-summary-stack { max-width: 360px !important; }
.summary-table .tabulator-row .tabulator-cell,
.bk-DataTabulator .tabulator-row .tabulator-cell { padding: 3px 6px !important; }
.quantify-lower-row { gap: 8px !important; align-items: stretch !important; }
.quantify-lower-row > * { min-width: 0 !important; }
.readout-stats-stack { flex: 1.1 1 0 !important; }
.compact-two-column > * { min-width: 0 !important; }

"""


APP_CSS += """
/* Iteration: one-screen compact layout + consistent control style ---------- */
:root {
  --qcm-bg: #eef2f7;
  --qcm-surface-muted: #f8fafc;
  --qcm-border: #c7d2e1;
  --qcm-border-strong: #94a3b8;
  --qcm-muted: #475569;
}
.main { padding: 8px 12px 12px 12px !important; }
.qcm-shell { gap: 4px !important; }
.qcm-context-bar { display: none !important; }
.qcm-step-nav { margin-bottom: 2px !important; }
.qcm-step-nav .bk-btn,
.plot-tools-row .bk-btn,
.range-actions .bk-btn {
  min-height: 28px !important;
  height: 28px !important;
  padding: 3px 8px !important;
  border-radius: 8px !important;
  border: 1px solid var(--qcm-border-strong) !important;
  box-shadow: none !important;
}
.bk-card,
.viewer-card,
.channel-controls,
.range-editor-card {
  border-radius: 10px !important;
  border-color: var(--qcm-border) !important;
  box-shadow: none !important;
}
.bk-card-header {
  min-height: 24px !important;
  padding: 4px 8px !important;
  font-size: 12px !important;
  letter-spacing: 0 !important;
}
.bk-card-body { padding: 5px 7px !important; }
.plot-tools-row {
  gap: 6px !important;
  align-items: flex-start !important;
  margin-bottom: 2px !important;
}
.plot-tools-row > * { min-width: 0 !important; }
.plot-tools-row .bk-input-group { margin-bottom: 0 !important; }
.plot-tools-row .bk-select { min-height: 28px !important; }
.channel-controls { max-width: 280px !important; }
.channel-controls .bk-card-body { max-height: 190px !important; overflow: auto !important; }
.analysis-target-row { gap: 6px !important; align-items: stretch !important; }
.analysis-target-row > *:first-child { flex: 0 0 190px !important; max-width: 190px !important; }
.analysis-target-row .current-range-card { flex: 1 1 auto !important; }
.quantify-controls-summary,
.review-controls-summary,
.phase-controls-saved { gap: 6px !important; }
.review-summary-stack,
.quantify-summary-stack,
.phase-table-stack { max-width: 320px !important; width: 320px !important; }
.current-range-card .bk-card-body,
.reference-range-card .bk-card-body,
.mark-range-card .bk-card-body { gap: 4px !important; }
.range-number-row .bk-input-group label,
.plot-tools-row .bk-input-group label,
.analysis-target-row .bk-input-group label {
  font-size: 10.5px !important;
  margin-bottom: 1px !important;
}
.range-number-row .bk-input,
.analysis-target-row .bk-input,
.plot-tools-row .bk-input { min-height: 26px !important; height: 26px !important; }
.range-actions { gap: 4px !important; }
.quantify-lower-row { gap: 6px !important; }
.quantify-lower-row > :first-child { flex: 0.95 1 0 !important; }
.readout-stats-stack { flex: 1.05 1 0 !important; gap: 5px !important; }
.summary-table .tabulator { font-size: 11px !important; }
.summary-table .tabulator-row .tabulator-cell,
.tabulator-row .tabulator-cell { padding: 2px 5px !important; }
.phase-analysis-row,
.compact-two-column { gap: 6px !important; }
.viewer-page > .bk-panel-models-layout-Column { gap: 5px !important; }


/* Compact one-screen workflow overrides ----------------------------------- */
.qcm-shell, .viewer-page, .workbench-page {
  gap: 6px !important;
}
.main {
  padding: 8px 12px 12px 12px !important;
}
.viewer-card, .bk-card {
  border-color: var(--qcm-border-strong) !important;
  box-shadow: none !important;
}
.bk-card-header {
  min-height: 26px !important;
  padding: 5px 9px !important;
  font-size: 0.82rem !important;
}
.bk-card-body {
  padding: 7px 8px !important;
}
.plot-tools-row {
  align-items: end !important;
  gap: 8px !important;
}
.plot-tools-row .bk-btn {
  min-height: 32px !important;
}
.compact-select .bk-input-group,
.quantity-select .bk-input-group,
.analysis-target-select .bk-input-group {
  margin-bottom: 0 !important;
}
.quantity-select, .analysis-target-select {
  min-width: 260px !important;
}
.quantity-select select, .analysis-target-select select {
  background: var(--qcm-surface-muted) !important;
  border: 1px solid var(--qcm-border-strong) !important;
  border-radius: 10px !important;
  min-height: 32px !important;
  font-weight: 650 !important;
}
.range-editor-card .bk-card-body {
  padding: 6px 8px !important;
}
.range-number-row {
  gap: 6px !important;
}
.compact-two-column {
  gap: 8px !important;
  align-items: stretch !important;
}
.compact-panel {
  gap: 6px !important;
}
.review-controls-summary, .reference-controls-row, .analysis-target-row {
  align-items: start !important;
}
.phase-controls-saved {
  max-width: 980px !important;
}
.phases-page .summary-table,
.target-summary-table {
  max-width: 100% !important;
}
.quantify-controls-summary .analysis-target-stack {
  max-width: 430px !important;
  min-width: 320px !important;
}
.quantify-lower-row > *:first-child {
  max-width: 45% !important;
}
.tabulator {
  font-size: 0.78rem !important;
}
.tabulator .tabulator-header .tabulator-col,
.tabulator .tabulator-row .tabulator-cell {
  padding: 3px 6px !important;
}
.qcm-step-nav {
  gap: 6px !important;
}
.qcm-step-nav .bk-btn {
  min-height: 30px !important;
  padding: 4px 9px !important;
}
.qcm-context-bar {
  display: none !important;
}
.qcm-footer {
  display: none !important;
}
"""
