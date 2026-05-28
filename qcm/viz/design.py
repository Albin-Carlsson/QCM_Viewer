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
  --qcm-bg: #f6f8fb;
  --qcm-surface: #ffffff;
  --qcm-surface-muted: #f8fafc;
  --qcm-border: #d8e1ee;
  --qcm-border-strong: #aebace;
  --qcm-text: #0f172a;
  --qcm-muted: #64748b;
  --qcm-accent: #2563eb;
  --qcm-accent-soft: #dbeafe;
  --qcm-success: #16a34a;
  --qcm-warning: #f97316;
  --qcm-danger: #dc2626;
  --qcm-radius: 14px;
  --qcm-radius-lg: 18px;
  --qcm-shadow: 0 1px 2px rgba(15, 23, 42, 0.05), 0 14px 34px rgba(15, 23, 42, 0.06);
}
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
