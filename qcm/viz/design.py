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
