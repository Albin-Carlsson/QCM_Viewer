"""Single source of truth for the QCM workbench look.

One :root token block + one scoped stylesheet (rules live under `.qcm-app`
so they win by structure, not by `!important`). Light only.

Layout model (three-page redesign):

    .qcm-app  ->  flex column
      .qcm-shell        (row)  sidebar | content
        .qcm-sidebar    (col)  brand, nav, run-info, help
        .qcm-content    (col)  topbar + the active page
          .qcm-topbar
          .qcm-page-data  / .qcm-page-results / .qcm-page-report
"""
from __future__ import annotations

APP_CSS = """
:root {
  color-scheme: light only;
  --qcm-bg: #eef2f7;
  --qcm-surface: #ffffff;
  --qcm-surface-muted: #f6f8fc;
  --qcm-border: #e2e8f0;
  --qcm-border-strong: #cbd5e1;
  --qcm-text: #0f172a;
  --qcm-text-soft: #334155;
  --qcm-muted: #64748b;
  --qcm-faint: #94a3b8;
  --qcm-accent: #2563eb;
  --qcm-accent-strong: #1d4ed8;
  --qcm-accent-soft: #eff6ff;
  --qcm-success: #16a34a;
  --qcm-warning: #d97706;
  --qcm-danger: #dc2626;
  --qcm-violet: #7c3aed;
  --qcm-space-1: 4px;
  --qcm-space-2: 8px;
  --qcm-space-3: 12px;
  --qcm-space-4: 16px;
  --qcm-space-5: 24px;
  --qcm-radius-sm: 8px;
  --qcm-radius-md: 12px;
  --qcm-radius-lg: 16px;
  --qcm-shadow-1: 0 1px 2px rgba(15, 23, 42, 0.06);
  --qcm-shadow-2: 0 12px 32px rgba(15, 23, 42, 0.10);
  --qcm-sidebar-w: 232px;
  --qcm-rail-w: 332px;
  --qcm-font: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

html, body {
  margin: 0;
  font-family: var(--qcm-font);
  background: var(--qcm-bg);
  color: var(--qcm-text);
  -webkit-font-smoothing: antialiased;
}
* { box-sizing: border-box; }
.main { max-width: 100vw; overflow-x: hidden; padding: 0; background: var(--qcm-bg); }
.sidebar, #sidebar, .bk-sidebar, aside.sidebar { display: none; width: 0; min-width: 0; padding: 0; border: 0; }

/* ===================================================================== shell */
.qcm-app { display: block; background: var(--qcm-bg); }
.qcm-shell { display: flex; align-items: stretch; min-height: 100vh; gap: 0; }

/* --- sidebar --------------------------------------------------------- */
.qcm-sidebar {
  flex: 0 0 var(--qcm-sidebar-w); width: var(--qcm-sidebar-w);
  display: flex; flex-direction: column; gap: var(--qcm-space-4);
  padding: var(--qcm-space-4) var(--qcm-space-3);
  background: var(--qcm-surface);
  border-right: 1px solid var(--qcm-border);
  position: sticky; top: 0; align-self: flex-start; height: 100vh; overflow-y: auto;
}
.qcm-brand { display: flex; align-items: center; gap: var(--qcm-space-2); padding: 0 var(--qcm-space-1) var(--qcm-space-1); }
.qcm-brand-mark { display: inline-flex; width: 30px; height: 30px; align-items: center; justify-content: center;
  color: #fff; background: linear-gradient(135deg, var(--qcm-accent), var(--qcm-violet)); border-radius: 9px; }
.qcm-brand-mark svg { width: 18px; height: 18px; }
.qcm-brand-name { font-size: 1.02rem; font-weight: 800; letter-spacing: -0.01em; }

.qcm-nav { display: flex; flex-direction: column; gap: var(--qcm-space-1); }
.qcm-nav-item { border-radius: var(--qcm-radius-md); padding: 2px 0; }
.qcm-nav-item .bk-btn {
  width: 100%; justify-content: flex-start; gap: 10px; text-align: left;
  border: 0; background: transparent; box-shadow: none;
  color: var(--qcm-text-soft); font-weight: 650; font-size: 0.92rem;
  padding: 9px 11px; border-radius: var(--qcm-radius-md);
}
.qcm-nav-item .bk-btn:hover { background: var(--qcm-surface-muted); color: var(--qcm-text); }
.qcm-nav-item .bk-btn svg, .qcm-nav-item .bk-btn .tabler-icon { width: 18px; height: 18px; opacity: .85; }
.qcm-nav-sub { color: var(--qcm-faint); font-size: 0.74rem; padding: 0 11px 4px 39px; margin-top: -4px; }
.qcm-nav-item.is-active { background: var(--qcm-accent-soft); box-shadow: inset 3px 0 0 var(--qcm-accent); }
.qcm-nav-item.is-active .bk-btn { color: var(--qcm-accent-strong); font-weight: 750; background: transparent; }
.qcm-nav-item.is-active .qcm-nav-sub { color: var(--qcm-accent); }

.qcm-sidebar-spacer { flex: 1 1 auto; }
.qcm-runinfo .bk-card-header { font-weight: 700; }
.qcm-help .bk-btn { width: 100%; justify-content: flex-start; gap: 8px; }

/* --- content + topbar ----------------------------------------------- */
.qcm-content { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-3);
  padding: var(--qcm-space-3) var(--qcm-space-4); }
.qcm-topbar {
  display: flex; align-items: center; gap: var(--qcm-space-3); flex-wrap: nowrap;
  background: var(--qcm-surface);
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-lg);
  padding: var(--qcm-space-2) var(--qcm-space-4); box-shadow: var(--qcm-shadow-1);
}
.qcm-runline { display: flex; align-items: baseline; }
.qcm-runline .run { font-size: 1.02rem; font-weight: 800; color: var(--qcm-text); }
.qcm-topbar .bk-btn { min-height: 34px; white-space: nowrap; }

/* ===================================================================== cards */
.qcm-card, .viewer-card, .bk-card, .qcm-anchor, .qcm-hero {
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md);
  background: var(--qcm-surface); box-shadow: var(--qcm-shadow-1); margin: 0;
}
.bk-card-header {
  min-height: 38px; padding: var(--qcm-space-2) var(--qcm-space-3);
  border-bottom: 1px solid var(--qcm-border);
  background: var(--qcm-surface); color: var(--qcm-text); font-weight: 700; font-size: 0.9rem;
}
.bk-card-body { padding: var(--qcm-space-3); }

.qcm-section-title-row { display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-2); }
.qcm-section-title { display: flex; flex-direction: column; gap: 2px; }
.qcm-section-title .eyebrow, .eyebrow { color: var(--qcm-muted); font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.qcm-section-title h2 { margin: 0; font-size: 1rem; font-weight: 800; color: var(--qcm-text); }
.qcm-section-action { color: var(--qcm-accent); font-size: 0.8rem; font-weight: 650; }

/* ============================================================= DATA page */
.qcm-page-data { display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-page-data-body { display: flex; gap: var(--qcm-space-3); align-items: flex-start; }
.qcm-plotzone { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-rail { flex: 0 0 var(--qcm-rail-w); width: var(--qcm-rail-w); display: flex; flex-direction: column; gap: var(--qcm-space-3);
  position: sticky; top: var(--qcm-space-3); max-height: calc(100vh - 2 * var(--qcm-space-3)); overflow-y: auto; }

/* plot-settings strip: a slim secondary header spanning the full content width.
   Labels sit inline to the left of each control so the whole bar stays short. */
.qcm-toolbar2 {
  display: flex; gap: var(--qcm-space-3); flex-wrap: nowrap; align-items: stretch;
  border: 1px solid var(--qcm-border); background: var(--qcm-surface);
  border-radius: var(--qcm-radius-md); padding: var(--qcm-space-2) var(--qcm-space-3); box-shadow: var(--qcm-shadow-1);
}
/* Every cell takes an equal share and is allowed to shrink to 0, so the strip
   can never exceed its container width. */
.qcm-toolcell, .qcm-toolcell.grow { display: flex; flex-direction: column; gap: 3px;
  flex: 1 1 0; min-width: 0; }
.qcm-toolcell > .eyebrow { padding: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.qcm-toolcell .bk-input-group { margin: 0; }
.qcm-toolcell .compact-select { width: 100%; min-width: 0; }
/* The eyebrow above each cell is the label, so hide the widgets' own labels
   (but keep checkbox labels — they carry an <input>). */
.qcm-toolcell .compact-select label,
.qcm-toolcell .bk-input-group > label:not(:has(input)) { display: none; margin: 0; }
.qcm-toolcell .bk-input, .qcm-toolcell select { min-height: 30px; height: 30px; padding-top: 2px; padding-bottom: 2px; }
/* Display toggles stack so the cell stays as narrow as the others. */
.qcm-tooltoggles { display: flex; flex-direction: column; gap: 5px; align-items: flex-start; }
.qcm-tooltoggles .bk-input-group { margin: 0; min-height: 20px; line-height: 1.25; }
.qcm-tooltoggles .bk-input-group label { display: inline-flex; align-items: center; gap: 6px; }

.qcm-anchor .bk-card-body { padding: var(--qcm-space-2); display: flex; flex-direction: column; gap: 2px; }

/* range slider mounted flush under the plot — reads as the plot's own scrubber */
.qcm-plot-rangeslider { padding: 2px var(--qcm-space-4) var(--qcm-space-1); border-top: 1px dashed var(--qcm-border); margin-top: 2px; }
.qcm-plot-rangeslider .bk-input-group > label { display: none; }
.qcm-plot-rangeslider .noUi-target, .qcm-plot-rangeslider .bk-slider-title { margin: 0; }

/* selection-mode cards */
.qcm-selection { display: flex; flex-direction: column; gap: var(--qcm-space-3);
  border: 1px solid var(--qcm-border); background: var(--qcm-surface);
  border-radius: var(--qcm-radius-md); padding: var(--qcm-space-3) var(--qcm-space-4); box-shadow: var(--qcm-shadow-1); }
.qcm-selrow { display: flex; gap: var(--qcm-space-4); align-items: flex-start; flex-wrap: wrap; }
.qcm-selrow > .qcm-selmode { flex: 2 1 420px; min-width: 0; }
.qcm-selrow > .qcm-selread-col { flex: 1 1 280px; min-width: 0; }

/* turn the brush-mode radio group into three big cards */
.draw-mode-toggle .bk-btn-group { display: grid !important; grid-template-columns: repeat(3, 1fr); gap: var(--qcm-space-2); }
.draw-mode-toggle .bk-btn {
  flex-direction: column; align-items: flex-start; gap: 2px; text-align: left;
  padding: 10px 12px; min-height: 58px; border: 1px solid var(--qcm-border-strong);
  background: var(--qcm-surface); color: var(--qcm-text-soft); border-radius: var(--qcm-radius-md);
  background-image: none; box-shadow: none; font-weight: 700; white-space: normal;
}
.draw-mode-toggle .bk-btn:hover { border-color: var(--qcm-accent); color: var(--qcm-text); }
.draw-mode-toggle .bk-btn.bk-active {
  border-color: var(--qcm-accent); background: var(--qcm-accent-soft);
  color: var(--qcm-accent-strong); background-image: none;
  box-shadow: inset 3px 0 0 var(--qcm-accent);
}
.qcm-selreadout { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--qcm-space-2); align-content: start; }
.qcm-selreadout .qcm-iconstat { min-width: 0; padding: var(--qcm-space-2); gap: var(--qcm-space-2); }
.qcm-selreadout .qcm-iconstat-body { min-width: 0; }
.qcm-selreadout .qcm-iconstat .value { font-size: 1rem; overflow-wrap: anywhere; }

/* ========================================================== right rail */
.qcm-rail .bk-card { box-shadow: var(--qcm-shadow-1); }
.qcm-rail .bk-card-header { background: var(--qcm-surface); }

.qcm-phase-list { display: flex; flex-direction: column; gap: 2px; }
.qcm-phase-row { display: flex; align-items: center; gap: var(--qcm-space-2); padding: 6px 4px; border-radius: var(--qcm-radius-sm); }
.qcm-phase-row:hover { background: var(--qcm-surface-muted); }
.qcm-phase-dot { width: 11px; height: 11px; border-radius: 50%; flex: 0 0 auto; box-shadow: 0 0 0 2px rgba(15,23,42,.04); }
.qcm-phase-name { font-weight: 650; color: var(--qcm-text); font-size: 0.88rem; }
.qcm-phase-time { margin-left: auto; color: var(--qcm-muted); font-size: 0.8rem; font-variant-numeric: tabular-nums; }

.qcm-selchip { display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-2);
  border: 1px solid var(--qcm-border); border-radius: 999px; padding: 6px 12px; background: var(--qcm-surface-muted); }
.qcm-selchip .k { color: var(--qcm-muted); font-size: 0.76rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.qcm-selchip .v { font-weight: 800; font-variant-numeric: tabular-nums; }
.qcm-selchip.accent { border-color: #bfdbfe; background: var(--qcm-accent-soft); }
.qcm-selchip.accent .v { color: var(--qcm-accent-strong); }

/* signals table — a clean, professional checkbox matrix */
.overtone-controls .bk-card-body { padding: 0; }
.overtone-controls-row { display: grid; grid-template-columns: minmax(56px, 1fr) repeat(3, minmax(52px, .9fr));
  gap: var(--qcm-space-2); align-items: center; padding: 6px var(--qcm-space-3); }
.overtone-controls-row:not(.overtone-controls-head) { border-top: 1px solid var(--qcm-border); }
.overtone-controls-row:not(.overtone-controls-head):hover { background: var(--qcm-surface-muted); }
/* header */
.overtone-controls-head { background: var(--qcm-surface-muted); border-radius: 0; padding-top: 8px; padding-bottom: 8px; }
.overtone-controls-header-cell { display: flex; flex-direction: column; gap: 3px; align-items: center; }
.overtone-controls-header-cell:first-child { align-items: flex-start; }
.ot-col { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.ot-n { color: var(--qcm-text); font-weight: 750; font-variant-numeric: tabular-nums; font-size: 0.88rem; }
/* center each checkbox in its column; the empty name leaves just the box */
.overtone-controls-row .bk-input-group { margin: 0; display: flex; justify-content: center; }
.overtone-controls-row > div:not(:first-child) { display: flex; justify-content: center; }
.overtone-controls input[type="checkbox"] { width: 17px; height: 17px; accent-color: var(--qcm-accent); cursor: pointer; }
/* "All" column toggles: subtle link-style chips under each header label */
.overtone-controls .overtone-all-toggle .bk-btn { min-height: 20px; padding: 0 8px; font-size: 0.66rem; line-height: 1;
  border: 1px solid var(--qcm-border-strong); background: var(--qcm-surface); color: var(--qcm-muted); border-radius: 999px; font-weight: 700; }
.overtone-controls .overtone-all-toggle .bk-btn:hover { border-color: var(--qcm-accent); color: var(--qcm-accent-strong); background: var(--qcm-accent-soft); }

/* ========================================================= components */
.qcm-metric-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--qcm-space-2); }
.qcm-stat { border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-md); background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-stat .label { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-stat .value { color: var(--qcm-text); font-size: 1.1rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.qcm-stat .caption { color: var(--qcm-muted); font-size: 0.78rem; }
.qcm-stat.accent { border-color: #bfdbfe; background: var(--qcm-accent-soft); }

.qcm-statgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--qcm-space-3); }
.qcm-iconstat { display: flex; gap: var(--qcm-space-3); align-items: center; border: 1px solid var(--qcm-border);
  border-radius: var(--qcm-radius-md); background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-iconstat-icon { flex: 0 0 auto; width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
  color: var(--qcm-accent); background: var(--qcm-accent-soft); }
.qcm-iconstat-icon svg { width: 20px; height: 20px; }
.qcm-iconstat .label { color: var(--qcm-muted); font-size: 0.72rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.qcm-iconstat .value { color: var(--qcm-text); font-size: 1.18rem; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.15; }
.qcm-iconstat .caption { color: var(--qcm-faint); font-size: 0.76rem; }
.qcm-iconstat.success .qcm-iconstat-icon { color: var(--qcm-success); background: #ecfdf5; }
.qcm-iconstat.warning .qcm-iconstat-icon { color: var(--qcm-warning); background: #fffbeb; }
.qcm-iconstat.danger  .qcm-iconstat-icon { color: var(--qcm-danger);  background: #fef2f2; }
.qcm-iconstat.accent  .qcm-iconstat-icon { color: var(--qcm-violet);  background: #f5f3ff; }

.qcm-pill { display: inline-grid; gap: 1px; min-width: 88px; border: 1px solid var(--qcm-border); border-radius: 999px; background: var(--qcm-surface-muted); padding: 6px 11px; }
.qcm-pill .label { color: var(--qcm-muted); font-size: 0.68rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-pill .value { color: var(--qcm-text); font-size: 0.92rem; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }

.qcm-empty { border: 1px dashed var(--qcm-border-strong); background: var(--qcm-surface-muted); border-radius: var(--qcm-radius-md); padding: var(--qcm-space-4); color: var(--qcm-muted); font-size: 0.86rem; }
.qcm-hint { display: flex; gap: var(--qcm-space-2); align-items: center; border-radius: var(--qcm-radius-md); padding: var(--qcm-space-2) var(--qcm-space-3); font-size: 0.86rem; }
.qcm-hint.info { border: 1px solid #bfdbfe; background: var(--qcm-accent-soft); color: var(--qcm-accent-strong); }
.qcm-hint.warning { border: 1px solid #fde68a; background: #fffbeb; color: #92400e; }

.qcm-kvtable { display: flex; flex-direction: column; gap: 2px; }
.qcm-kv { display: flex; align-items: baseline; justify-content: space-between; gap: var(--qcm-space-3); padding: 3px 0; }
.qcm-kv .k { color: var(--qcm-muted); font-size: 0.8rem; }
.qcm-kv .v { color: var(--qcm-text); font-size: 0.82rem; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }

.qcm-defs { display: flex; flex-direction: column; gap: var(--qcm-space-2); }
.qcm-def { display: grid; grid-template-columns: 84px 1fr; gap: var(--qcm-space-3); align-items: baseline; }
.qcm-def .term { font-weight: 800; color: var(--qcm-text); }
.qcm-def .desc { color: var(--qcm-muted); font-size: 0.86rem; }

/* ====================================================== RESULTS page */
/* The page is a Column (QCM-only run) or a Row (echem dashboard); Panel sets the
   direction, we only add the gap + alignment so both layouts read consistently. */
.qcm-page-results { gap: var(--qcm-space-3); align-items: flex-start; }
.qcm-results-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-results-side { flex: 0 0 320px; width: 320px; display: flex; flex-direction: column; gap: var(--qcm-space-3);
  position: sticky; top: var(--qcm-space-3); max-height: calc(100vh - 2 * var(--qcm-space-3)); overflow-y: auto; }
.qcm-results-plotrow { display: flex; gap: var(--qcm-space-3); }
.qcm-results-plotrow > * { flex: 1 1 0; min-width: 0; }
.echem-cycle-controls { gap: var(--qcm-space-2); }
.echem-cycle-controls .eyebrow { margin-bottom: 2px; }

/* ======================================================= REPORT page */
.qcm-page-report { display: flex; gap: var(--qcm-space-3); align-items: flex-start; }
.qcm-report-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-3); }
.qcm-report-side { flex: 0 0 340px; width: 340px; display: flex; flex-direction: column; gap: var(--qcm-space-3);
  position: sticky; top: var(--qcm-space-3); max-height: calc(100vh - 2 * var(--qcm-space-3)); overflow-y: auto; }
.qcm-report-preview .qcm-results-plotrow { margin-top: var(--qcm-space-3); }
/* tidy the config/export forms: eyebrow labels sit tight above each control */
.qcm-report-side .eyebrow { margin-top: var(--qcm-space-2); }
.qcm-report-side .bk-card-body > .eyebrow:first-child { margin-top: 0; }
.qcm-report-side .bk-btn { width: 100%; }

/* ===================================================== inputs / tables */
.bk-input, .bk-input-group input, select, textarea {
  border-radius: var(--qcm-radius-sm); border-color: var(--qcm-border-strong);
  color: var(--qcm-text); background-color: #fff; font-variant-numeric: tabular-nums;
}
.bk-btn { border-radius: var(--qcm-radius-sm); font-weight: 650; box-shadow: none; }
.range-number-row { gap: var(--qcm-space-2); }
.range-number-row .bk-input { text-align: right; }
.range-actions { gap: var(--qcm-space-2); }
.summary-table .tabulator, .tabulator { font-size: 0.8rem; border-radius: var(--qcm-radius-sm); border: 1px solid var(--qcm-border); overflow: hidden; }
.tabulator .tabulator-header { background: var(--qcm-surface-muted); }
.tabulator .tabulator-row .tabulator-cell, .tabulator .tabulator-header .tabulator-col { padding: 5px 9px; }
.tabulator .tabulator-row.tabulator-row-even { background: var(--qcm-surface-muted); }

/* frequency-display + technique + cycle-mode segmented toggles look like the mockup */
.freq-display-toggle .bk-btn, .echem-technique-toggle .bk-btn, .echem-cycle-mode .bk-btn {
  background: var(--qcm-surface-muted); background-image: none; color: var(--qcm-text-soft);
  border: 1px solid var(--qcm-border-strong); box-shadow: none; font-weight: 650;
}
.freq-display-toggle .bk-btn.bk-active, .echem-technique-toggle .bk-btn.bk-active, .echem-cycle-mode .bk-btn.bk-active {
  background: var(--qcm-accent-soft); background-image: none; color: var(--qcm-accent-strong);
  border-color: var(--qcm-accent); font-weight: 750;
}

/* ============================================================ drawer */
.qcm-drawer { position: fixed; top: 0; right: 0; height: 100vh; width: min(680px, 92vw);
  z-index: 60; overflow-y: auto; background: var(--qcm-surface);
  border-left: 1px solid var(--qcm-border); box-shadow: var(--qcm-shadow-2); padding: var(--qcm-space-4); }
.qcm-drawer-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--qcm-space-3); }

/* keep stray third-party dark-mode toggles hidden (defensive) */
button[title*="theme" i], button[aria-label*="theme" i], .theme-toggle, .pn-theme-toggle { display: none !important; }

/* ========================================================= responsive */
@media (max-width: 1280px) {
  .qcm-page-data-body, .qcm-page-report { flex-direction: column; }
  .qcm-rail, .qcm-report-side { flex: 1 1 auto; width: 100%; position: static; max-height: none; }
  .qcm-results-plotrow { flex-direction: column; }
}
@media (max-width: 900px) {
  .qcm-shell { flex-direction: column; }
  .qcm-sidebar { position: static; height: auto; width: 100%; flex: 1 1 auto;
    flex-direction: row; flex-wrap: wrap; align-items: center; }
  .qcm-nav { flex-direction: row; flex-wrap: wrap; }
  .qcm-nav-sub { display: none; }
  .qcm-sidebar-spacer { display: none; }
  .qcm-content { padding: var(--qcm-space-3); }
}
"""
