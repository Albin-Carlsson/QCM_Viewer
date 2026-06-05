"""The QCM-D viewer stylesheet — one unified pattern language.

This file is the single source of *structure*; `tokens.py` is the single source
of *values*. Together they implement `docs/design-system.md`. Read that document
before changing anything here — every rule below is an instance of a definition
in the spec, not an ad-hoc tweak.

Conventions:
- `:root` custom properties come from ``tokens.root_css()``; nothing here hardcodes
  a value that belongs in a token.
- Rules are scoped by class so they win on structure, never with ``!important``.
  The only exceptions are two Bokeh ``display:grid`` overrides (the framework sets
  the button-group display inline) and one defensive hide of third-party toggles.
- One material (white card, hairline border, no shadow). One accent. 4px grid.
  Numerics in mono. Everything fits its box (``min-width:0`` + clipped overflow).
"""
from __future__ import annotations

from .tokens import root_css

APP_CSS = root_css() + """

/* ===================================================================== base */
html, body {
  margin: 0;
  font-family: var(--qcm-font);
  font-size: var(--qcm-fs-body);
  line-height: 1.45;
  background: var(--qcm-bg);
  color: var(--qcm-text);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
* { box-sizing: border-box; }
.main { max-width: 100vw; overflow-x: hidden; padding: 0; background: var(--qcm-bg); }
/* Panel's own sidebar is unused — we build our own. */
.sidebar, #sidebar, .bk-sidebar, aside.sidebar { display: none; width: 0; min-width: 0; padding: 0; border: 0; }

/* numerics: one mono treatment everywhere a figure appears */
.qcm-stat .value, .qcm-iconstat .value, .qcm-pill .value, .qcm-selchip .v,
.qcm-kv .v, .qcm-phase-time, .ot-n, .qcm-def .term,
.range-number-row .bk-input, .tabulator, .qcm-runline .run {
  font-family: var(--qcm-mono); font-feature-settings: "tnum" 1;
}

/* shared label atoms */
.eyebrow, .qcm-section-title .eyebrow {
  color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 700;
  letter-spacing: .06em; text-transform: uppercase;
}

/* ==================================================================== shell */
.qcm-app { display: block; background: var(--qcm-bg); }
.qcm-shell { display: flex; align-items: stretch; min-height: 100vh; gap: 0; }
.qcm-shell > * { min-width: 0; }

/* --- sidebar --------------------------------------------------------------- */
.qcm-sidebar {
  flex: 0 0 var(--qcm-sidebar-w); width: var(--qcm-sidebar-w);
  /* A flex item's default min-width is its content's min-content size. The
     directory browser is intrinsically ~600px wide, so without this floor it
     would blow the sidebar out to ~40% of the screen. Pin the width and clip. */
  min-width: 0; max-width: var(--qcm-sidebar-w);
  display: flex; flex-direction: column; gap: var(--qcm-space-4);
  padding: var(--qcm-space-4) var(--qcm-space-3);
  background: var(--qcm-surface);
  border-right: 1px solid var(--qcm-border);
  position: sticky; top: 0; align-self: flex-start; height: 100vh;
  overflow-y: auto; overflow-x: hidden;
}
/* Keep every sidebar card inside the pinned width regardless of intrinsic
   child sizes (the file browser in particular). */
.qcm-sidebar > * { min-width: 0; max-width: 100%; }
.qcm-brand { display: flex; align-items: center; gap: var(--qcm-space-2); padding: 0 var(--qcm-space-1) var(--qcm-space-2); }
.qcm-brand-mark {
  display: inline-flex; width: 30px; height: 30px; align-items: center; justify-content: center;
  color: var(--qcm-on-accent); background: var(--qcm-accent); border-radius: var(--qcm-radius-control);
}
.qcm-brand-mark svg { width: 18px; height: 18px; }
.qcm-brand-name { font-size: var(--qcm-fs-title); font-weight: 800; letter-spacing: -0.01em; }

.qcm-nav { display: flex; flex-direction: column; gap: var(--qcm-space-1); }
.qcm-nav-item { border-radius: var(--qcm-radius-control); }
.qcm-nav-item .bk-btn {
  width: 100%; justify-content: flex-start; gap: var(--qcm-space-2); text-align: left;
  border: 0; background: transparent; box-shadow: none;
  color: var(--qcm-text-soft); font-weight: 650; font-size: var(--qcm-fs-label);
  padding: 9px 11px; border-radius: var(--qcm-radius-control); min-height: 0;
  transition: background var(--qcm-motion), color var(--qcm-motion);
}
.qcm-nav-item .bk-btn:hover { background: var(--qcm-surface-muted); color: var(--qcm-text); }
.qcm-nav-item .bk-btn svg, .qcm-nav-item .bk-btn .tabler-icon { width: 18px; height: 18px; opacity: .85; }
.qcm-nav-sub { color: var(--qcm-faint); font-size: var(--qcm-fs-caption); padding: 0 11px 4px 39px; margin-top: -4px; }
.qcm-nav-item.is-active { background: var(--qcm-accent-soft); box-shadow: inset 3px 0 0 var(--qcm-accent); }
.qcm-nav-item.is-active .bk-btn { color: var(--qcm-accent-strong); font-weight: 750; background: transparent; }
.qcm-nav-item.is-active .qcm-nav-sub { color: var(--qcm-accent); }

.qcm-sidebar-spacer { flex: 1 1 auto; }
.qcm-help .bk-btn { width: 100%; justify-content: flex-start; gap: var(--qcm-space-2); }
/* the sidebar Run-info card sits on a white surface, so a hairline border is
   invisible — give it the stronger outline so it reads as its own contained box.
   (Targets the card's own class: Panel renders each component in its own shadow
   root, so a `.qcm-sidebar .qcm-card` descendant rule can't reach across it.) */
.qcm-runinfo { border-color: var(--qcm-border-strong); }

/* --- run manager ----------------------------------------------------------- */
.qcm-runs { border-color: var(--qcm-border-strong); }
/* Inset the rows so the radio and label fields breathe inside the card. */
.qcm-runs-body { display: flex; flex-direction: column; gap: var(--qcm-space-2); padding: 2px 2px 4px; }
/* Panel's Row writes align-items inline (default `start`); override it so the
   radio lines up with the label text vertically. */
.qcm-run-row { align-items: center !important; gap: var(--qcm-space-3); padding: 0; min-width: 0; }
.qcm-run-row.is-active { font-weight: 600; }
/* Let the label field shrink so the fixed swatch + active toggle always fit
   inside the sidebar instead of overflowing (and clipping) the toggle. */
.qcm-run-label { min-width: 0; flex: 1 1 auto; }
.qcm-run-active, .qcm-run-pick { flex: 0 0 auto; }
/* The run rows live in the fixed-width sidebar; the bulky directory browser is
   in a modal (.qcm-run-modal), so nothing here can force the sidebar wider. */
.qcm-runs, .qcm-run-row { max-width: 100%; }
.qcm-add-run-btn { margin-top: var(--qcm-space-2); }
.qcm-run-modal .qcm-run-browser { min-height: 280px; }
.qcm-import-detect { align-items: center; gap: var(--qcm-space-3); margin-top: var(--qcm-space-2); }
.qcm-import-ok { color: var(--qcm-accent); font-size: 12px; font-weight: 600; }
.qcm-import-warn { color: #b45309; font-size: 12px; font-weight: 600; }
.qcm-import-msg { color: var(--qcm-ink-soft); font-size: 12px; }
.qcm-map-editor { margin-top: var(--qcm-space-2); gap: 4px; max-height: 220px; overflow-y: auto; }
.qcm-map-row { align-items: center !important; gap: var(--qcm-space-2); }
.qcm-map-col { font-family: var(--qcm-mono, monospace); font-size: 12px; min-width: 120px; }
.qcm-map-arrow { color: var(--qcm-ink-soft); }

/* --- content + top bar ----------------------------------------------------- */
.qcm-content {
  flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column;
  gap: var(--qcm-space-4); padding: var(--qcm-space-4);
}
.qcm-content > * { min-width: 0; }
.qcm-pagehost { display: block; min-width: 0; }

.qcm-topbar {
  display: flex; align-items: center; gap: var(--qcm-space-3); flex-wrap: nowrap;
  background: var(--qcm-surface);
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-card);
  padding: var(--qcm-space-2) var(--qcm-space-4);
  position: sticky; top: 0; z-index: 30; box-shadow: var(--qcm-shadow-1);
}
.qcm-runline { display: flex; align-items: baseline; min-width: 0; }
.qcm-runline .run { font-size: var(--qcm-fs-display); font-weight: 800; color: var(--qcm-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qcm-topbar-actions { display: flex; align-items: center; gap: var(--qcm-space-2); flex: 0 0 auto; }
.qcm-topbar-actions .bk-btn { white-space: nowrap; }

/* ==================================================================== cards */
/* The one material: white surface, hairline border, no shadow. */
.qcm-card, .viewer-card, .bk-card, .qcm-anchor, .qcm-hero {
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-card);
  background: var(--qcm-surface); box-shadow: none; margin: 0;
}
.bk-card-header {
  min-height: var(--qcm-header-h); padding: 0 var(--qcm-space-4);
  display: flex; align-items: center;
  border-bottom: 1px solid var(--qcm-border);
  background: var(--qcm-surface); color: var(--qcm-text);
  font-weight: 700; font-size: var(--qcm-fs-title);
}
.bk-card-header .bk-btn { color: var(--qcm-muted); }
.bk-card-body { padding: var(--qcm-space-3); }

.qcm-section-title-row { display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-2); }
.qcm-section-title { display: flex; flex-direction: column; gap: 2px; }
.qcm-section-title h2 { margin: 0; font-size: var(--qcm-fs-title); font-weight: 800; color: var(--qcm-text); }
.qcm-section-action { color: var(--qcm-accent); font-size: var(--qcm-fs-label); font-weight: 650; }

/* ================================================================ DATA page */
.qcm-page-data { display: flex; flex-direction: column; gap: var(--qcm-space-4); }
.qcm-page-data-body { display: flex; gap: var(--qcm-space-4); align-items: flex-start; }
.qcm-page-data-body > * { min-width: 0; }
.qcm-plotzone { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-4); }
.qcm-plotzone > * { min-width: 0; }
.qcm-rail {
  flex: 0 0 var(--qcm-rail-w); width: var(--qcm-rail-w);
  display: flex; flex-direction: column; gap: var(--qcm-space-4);
  position: sticky; top: calc(var(--qcm-header-h) + var(--qcm-space-5));
  max-height: calc(100vh - var(--qcm-space-5)); overflow-y: auto;
}
.qcm-rail > * { min-width: 0; }

/* plot-settings strip: a slim secondary header spanning the full content width */
.qcm-toolbar2 {
  display: flex; gap: var(--qcm-space-3); flex-wrap: nowrap; align-items: stretch;
  border: 1px solid var(--qcm-border); background: var(--qcm-surface);
  border-radius: var(--qcm-radius-card); padding: var(--qcm-space-3);
}
.qcm-toolcell, .qcm-toolcell.grow { display: flex; flex-direction: column; gap: 3px; flex: 1 1 0; min-width: 0; }
/* the Display checkboxes need only their own width, so let the selects take the rest */
.qcm-toolbar2 > .qcm-toolcell-display { flex: 0 0 auto; }
.qcm-toolcell > .eyebrow { padding: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.qcm-toolcell .bk-input-group { margin: 0; }
.qcm-toolcell .compact-select { width: 100%; min-width: 0; }
.qcm-toolcell .compact-select label,
.qcm-toolcell .bk-input-group > label:not(:has(input)) { display: none; margin: 0; }
.qcm-tooltoggles { display: flex; flex-direction: column; gap: 5px; align-items: flex-start; }
.qcm-tooltoggles .bk-input-group { margin: 0; min-height: 20px; line-height: 1.25; }
.qcm-tooltoggles .bk-input-group label { display: inline-flex; align-items: center; gap: 6px; }

/* plot card: borderless plot, range slider flush beneath as the plot's scrubber */
.qcm-anchor { overflow: hidden; }
.qcm-anchor .bk-card-body { padding: var(--qcm-space-2); display: flex; flex-direction: column; gap: 2px; }
.qcm-plot-rangeslider { padding: 2px var(--qcm-space-4) var(--qcm-space-1); border-top: 1px dashed var(--qcm-border); margin-top: 2px; }
.qcm-plot-rangeslider .bk-input-group > label { display: none; }
.qcm-plot-rangeslider .noUi-target, .qcm-plot-rangeslider .bk-slider-title { margin: 0; }

/* selection cards */
.qcm-selection {
  display: flex; flex-direction: column; gap: var(--qcm-space-3);
  border: 1px solid var(--qcm-border); background: var(--qcm-surface);
  border-radius: var(--qcm-radius-card); padding: var(--qcm-space-3);
}
.qcm-selrow { display: flex; gap: var(--qcm-space-4); align-items: flex-start; flex-wrap: wrap; }
.qcm-selrow > .qcm-selmode { flex: 2 1 420px; min-width: 0; }
.qcm-selrow > .qcm-selread-col { flex: 1 1 280px; min-width: 0; }

/* range-model explainer that fills the selection card and teaches the 3 modes */
.qcm-mode-help { display: flex; flex-direction: column; gap: 6px; margin-top: var(--qcm-space-3);
  padding-top: var(--qcm-space-3); border-top: 1px solid var(--qcm-border); }
.qcm-mode-help .r { display: flex; gap: var(--qcm-space-2); font-size: var(--qcm-fs-body); color: var(--qcm-muted); line-height: 1.4; }
.qcm-mode-help .r .b { color: var(--qcm-text); font-weight: 700; flex: 0 0 116px; }
.qcm-mode-help .tip { margin-top: 2px; font-size: var(--qcm-fs-caption); color: var(--qcm-faint); }

.qcm-selreadout { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--qcm-space-2); align-content: start; }
.qcm-selreadout .qcm-iconstat { min-width: 0; padding: var(--qcm-space-2); gap: var(--qcm-space-2); }
.qcm-selreadout .qcm-iconstat-body { min-width: 0; }
.qcm-selreadout .qcm-iconstat .value { font-size: var(--qcm-fs-value); overflow-wrap: anywhere; }

/* ============================================================== right rail */
.qcm-phase-list { display: flex; flex-direction: column; gap: 2px; }
.qcm-phase-row { display: flex; align-items: center; gap: var(--qcm-space-2); padding: 6px 4px; border-radius: var(--qcm-radius-sm); }
.qcm-phase-row:hover { background: var(--qcm-surface-muted); }
.qcm-phase-dot { width: 11px; height: 11px; border-radius: var(--qcm-radius-pill); flex: 0 0 auto; box-shadow: 0 0 0 2px rgba(15,23,42,.04); }
.qcm-phase-name { font-weight: 650; color: var(--qcm-text); font-size: var(--qcm-fs-body); }
.qcm-phase-time { margin-left: auto; color: var(--qcm-muted); font-size: var(--qcm-fs-body); }

.qcm-selchip {
  display: flex; align-items: center; justify-content: space-between; gap: var(--qcm-space-2);
  border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-pill);
  padding: 6px 12px; background: var(--qcm-surface-muted);
}
.qcm-selchip .k { color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.qcm-selchip .v { font-weight: 800; }
.qcm-selchip.accent { border-color: var(--qcm-accent-border); background: var(--qcm-accent-soft); }
.qcm-selchip.accent .v { color: var(--qcm-accent-strong); }

/* signals matrix — a clean checkbox grid */
.overtone-controls .bk-card-body { padding: 0; }
.overtone-controls-row {
  display: grid; grid-template-columns: minmax(56px, 1fr) repeat(3, minmax(52px, .9fr));
  gap: var(--qcm-space-2); align-items: center; padding: 6px var(--qcm-space-3);
}
.overtone-controls-row:not(.overtone-controls-head) { border-top: 1px solid var(--qcm-border); }
.overtone-controls-row:not(.overtone-controls-head):hover { background: var(--qcm-surface-muted); }
.overtone-controls-head { background: var(--qcm-surface-muted); padding-top: 8px; padding-bottom: 8px; }
.overtone-controls-header-cell { display: flex; flex-direction: column; gap: 3px; align-items: center; }
.overtone-controls-header-cell:first-child { align-items: flex-start; }
.ot-col { color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.ot-n { color: var(--qcm-text); font-weight: 750; font-size: var(--qcm-fs-body); }
.overtone-controls-row .bk-input-group { margin: 0; display: flex; justify-content: center; }
.overtone-controls-row > div:not(:first-child) { display: flex; justify-content: center; }
.overtone-controls input[type="checkbox"] { width: 17px; height: 17px; accent-color: var(--qcm-accent); cursor: pointer; }
.overtone-controls .overtone-all-toggle .bk-btn {
  min-height: 20px; padding: 0 8px; font-size: var(--qcm-fs-caption); line-height: 1;
  border: 1px solid var(--qcm-border-strong); background: var(--qcm-surface);
  color: var(--qcm-muted); border-radius: var(--qcm-radius-pill); font-weight: 700;
}
.overtone-controls .overtone-all-toggle .bk-btn:hover { border-color: var(--qcm-accent); color: var(--qcm-accent-strong); background: var(--qcm-accent-soft); }

/* ============================================================= stat family */
/* one definition behind every metric tile, icon-stat, pill, and chip */
.qcm-metric-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--qcm-space-3); }
.qcm-stat { border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-card); background: var(--qcm-surface); padding: var(--qcm-space-3); }
.qcm-stat .label { color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-stat .value { color: var(--qcm-text); font-size: var(--qcm-fs-value); font-weight: 800; }
.qcm-stat .caption { color: var(--qcm-muted); font-size: var(--qcm-fs-caption); }
.qcm-stat.accent { border-color: var(--qcm-accent-border); background: var(--qcm-accent-soft); }

.qcm-statgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--qcm-space-3); }
.qcm-iconstat {
  display: flex; gap: var(--qcm-space-3); align-items: center; border: 1px solid var(--qcm-border);
  border-radius: var(--qcm-radius-card); background: var(--qcm-surface); padding: var(--qcm-space-3);
}
.qcm-iconstat-icon {
  flex: 0 0 auto; width: 36px; height: 36px; border-radius: var(--qcm-radius-control);
  display: flex; align-items: center; justify-content: center;
  color: var(--qcm-accent); background: var(--qcm-accent-soft);
}
.qcm-iconstat-icon svg { width: 20px; height: 20px; }
.qcm-iconstat .label { color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.qcm-iconstat .value { color: var(--qcm-text); font-size: var(--qcm-fs-value-lg); font-weight: 800; line-height: 1.2; }
.qcm-iconstat .value .unit { font-family: var(--qcm-font); font-size: var(--qcm-fs-label); font-weight: 600; color: var(--qcm-muted); margin-left: 4px; }
.qcm-iconstat .caption { color: var(--qcm-faint); font-size: var(--qcm-fs-caption); }
.qcm-iconstat.success .qcm-iconstat-icon { color: var(--qcm-success); background: var(--qcm-success-soft); }
.qcm-iconstat.warning .qcm-iconstat-icon { color: var(--qcm-warning); background: var(--qcm-warning-soft); }
.qcm-iconstat.danger  .qcm-iconstat-icon { color: var(--qcm-danger);  background: var(--qcm-danger-soft); }
.qcm-iconstat.accent  .qcm-iconstat-icon { color: var(--qcm-violet);  background: var(--qcm-violet-soft); }

.qcm-pill { display: inline-grid; gap: 1px; min-width: 88px; border: 1px solid var(--qcm-border); border-radius: var(--qcm-radius-pill); background: var(--qcm-surface-muted); padding: 6px 11px; }
.qcm-pill .label { color: var(--qcm-muted); font-size: var(--qcm-fs-eyebrow); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.qcm-pill .value { color: var(--qcm-text); font-size: var(--qcm-fs-label); font-weight: 800; white-space: nowrap; }

.qcm-empty { border: 1px dashed var(--qcm-border-strong); background: var(--qcm-surface-muted); border-radius: var(--qcm-radius-card); padding: var(--qcm-space-4); color: var(--qcm-muted); font-size: var(--qcm-fs-body); }
.qcm-hint { display: flex; gap: var(--qcm-space-2); align-items: center; border-radius: var(--qcm-radius-control); padding: var(--qcm-space-2) var(--qcm-space-3); font-size: var(--qcm-fs-body); }
.qcm-hint.info { border: 1px solid var(--qcm-accent-border); background: var(--qcm-accent-soft); color: var(--qcm-accent-strong); }
.qcm-hint.warning { border: 1px solid var(--qcm-warning-border); background: var(--qcm-warning-soft); color: var(--qcm-warning-text); }

.qcm-kvtable { display: flex; flex-direction: column; gap: 2px; }
.qcm-kv { display: flex; align-items: baseline; justify-content: space-between; gap: var(--qcm-space-3); padding: 3px 0; }
.qcm-kv .k { color: var(--qcm-muted); font-size: var(--qcm-fs-label); }
.qcm-kv .v { color: var(--qcm-text); font-size: var(--qcm-fs-label); font-weight: 700; text-align: right; }

.qcm-defs { display: flex; flex-direction: column; gap: var(--qcm-space-2); }
.qcm-def { display: grid; grid-template-columns: 84px 1fr; gap: var(--qcm-space-3); align-items: baseline; }
.qcm-def .term { font-weight: 800; color: var(--qcm-text); }
.qcm-def .desc { color: var(--qcm-muted); font-size: var(--qcm-fs-body); }

/* ============================================================ RESULTS page */
.qcm-page-results { gap: var(--qcm-space-4); align-items: flex-start; }
.qcm-page-results > * { min-width: 0; }
/* headline plot (grow) beside the short Technique/Cycle column — heights match */
.qcm-results-midrow { display: flex; gap: var(--qcm-space-4); align-items: flex-start; }
.qcm-results-midrow > *:first-child { flex: 1 1 0; min-width: 0; }
.qcm-results-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--qcm-space-4); }
.qcm-results-side {
  flex: 0 0 var(--qcm-rail-w); width: var(--qcm-rail-w); display: flex; flex-direction: column; gap: var(--qcm-space-4);
  position: sticky; top: calc(var(--qcm-header-h) + var(--qcm-space-5)); max-height: calc(100vh - var(--qcm-space-5)); overflow-y: auto;
}
.qcm-results-plotrow { display: flex; gap: var(--qcm-space-4); }
.qcm-results-plotrow > * { flex: 1 1 0; min-width: 0; }
.echem-cycle-controls { gap: var(--qcm-space-2); }
.echem-cycle-controls .eyebrow { margin-bottom: 2px; }

/* ===================================== EXPORT page (config + export only) */
/* The report page is a focused export console: nothing it could show is unique
   (stats/plots/run-info all live on Data/Results + the sidebar), so it carries
   only Configuration + Export, centered so short content reads as a panel. */
.qcm-page-export {
  max-width: 760px; margin: 0 auto; width: 100%;
  display: flex; flex-direction: column; gap: var(--qcm-space-4);
}
.qcm-page-export > * { min-width: 0; }
/* eyebrows separate the grouped controls within each card */
.qcm-page-export .eyebrow { margin-top: var(--qcm-space-3); }
.qcm-page-export .bk-card-body > .eyebrow:first-child { margin-top: 0; }
/* small helper line under a control group (quiet, not a loud info box) */
.qcm-export-note { color: var(--qcm-muted); font-size: var(--qcm-fs-caption); margin: 2px 0 var(--qcm-space-1); }
/* (config checkboxes are styled via stylesheets= injected into the widget shadow
   root — see report.py _CHECKBOX_CSS — since the boxes live in shadow DOM.) */

/* ============================================== inputs / buttons / tables */
.bk-input, .bk-input-group input, select, textarea {
  min-height: var(--qcm-control-h); height: var(--qcm-control-h);
  border-radius: var(--qcm-radius-control); border: 1px solid var(--qcm-border-strong);
  color: var(--qcm-text); background-color: var(--qcm-surface); font-size: var(--qcm-fs-body);
  padding: 0 10px; font-variant-numeric: tabular-nums;
  transition: border-color var(--qcm-motion), box-shadow var(--qcm-motion);
}
textarea { height: auto; padding: 8px 10px; }
.bk-input:focus, .bk-input-group input:focus, select:focus, textarea:focus {
  outline: none; border-color: var(--qcm-accent); box-shadow: var(--qcm-ring);
}

/* buttons — base + the three variants from the spec */
.bk-btn {
  min-height: var(--qcm-control-h); padding: 0 14px; gap: var(--qcm-space-2);
  border-radius: var(--qcm-radius-control); font-weight: 650; font-size: var(--qcm-fs-body);
  box-shadow: none; background-image: none;
  transition: background var(--qcm-motion), border-color var(--qcm-motion), color var(--qcm-motion), box-shadow var(--qcm-motion);
}
.bk-btn svg, .bk-btn .tabler-icon { width: 18px; height: 18px; }
.bk-btn:focus-visible { outline: none; box-shadow: var(--qcm-ring); }
.bk-btn-default {
  background: var(--qcm-surface); color: var(--qcm-text-soft);
  border: 1px solid var(--qcm-border-strong);
}
.bk-btn-default:hover { border-color: var(--qcm-accent); color: var(--qcm-text); background: var(--qcm-surface); }
.bk-btn-primary {
  background: var(--qcm-accent); color: var(--qcm-on-accent);
  border: 1px solid var(--qcm-accent);
}
.bk-btn-primary:hover { background: var(--qcm-accent-strong); border-color: var(--qcm-accent-strong); }
.bk-btn-primary:active { background: var(--qcm-accent-active); border-color: var(--qcm-accent-active); }

.range-number-row { gap: var(--qcm-space-2); }
.range-number-row .bk-input { text-align: right; }
.range-actions { gap: var(--qcm-space-2); }
.range-editor-card { border-radius: var(--qcm-radius-card); }
.range-duration { min-height: var(--qcm-control-h); display: flex; align-items: center; }
.quantity-context { border-left: 3px solid var(--qcm-accent); padding-left: 10px; }
.controls-muted { color: var(--qcm-muted); }

/* tables: contained, hairline dividers, sunken header, mono numbers */
.summary-table .tabulator, .tabulator {
  font-size: var(--qcm-fs-body); border-radius: var(--qcm-radius-card);
  border: 1px solid var(--qcm-border); overflow: hidden;
}
.tabulator .tabulator-header { background: var(--qcm-surface-muted); border-bottom: 1px solid var(--qcm-border); }
.tabulator .tabulator-header .tabulator-col { background: transparent; color: var(--qcm-muted);
  font-size: var(--qcm-fs-eyebrow); font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.tabulator .tabulator-row .tabulator-cell, .tabulator .tabulator-header .tabulator-col { padding: 6px 10px; }
.tabulator .tabulator-row { border-top: 1px solid var(--qcm-border); background: var(--qcm-surface); }
.tabulator .tabulator-row:hover { background: var(--qcm-surface-muted); }

/* segmented toggles — ONE rule for every RadioButtonGroup / CheckButtonGroup:
   a sunken track with a raised white active segment. The chip-grid channel
   chooser opts out below. This is the single source of the toggle look. */
.bk-btn-group {
  background: var(--qcm-surface-muted); border-radius: var(--qcm-radius-control);
  padding: 3px; gap: 3px; border: 1px solid var(--qcm-border);
}
.bk-btn-group .bk-btn {
  background: transparent; background-image: none; color: var(--qcm-text-soft);
  border: 1px solid transparent; box-shadow: none; font-weight: 650;
  border-radius: var(--qcm-radius-sm); min-height: 28px;
}
.bk-btn-group .bk-btn:hover { color: var(--qcm-text); }
.bk-btn-group .bk-btn.bk-active {
  background: var(--qcm-surface); background-image: none; color: var(--qcm-accent-strong);
  border-color: var(--qcm-border); font-weight: 750; box-shadow: var(--qcm-shadow-1);
}

/* channel chooser (absorbed from controls.py) — a chip grid, not a track, so it
   resets the segmented background/border above and styles its own chips. */
.channel-toggles .bk-btn-group {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--qcm-space-2); width: 100%;
  background: transparent; border: 0; padding: 0;
}
.channel-toggles .bk-btn {
  width: 100%; justify-content: flex-start; text-align: left; white-space: normal;
  border: 1px solid var(--qcm-border-strong); background: var(--qcm-surface);
  background-image: none; color: var(--qcm-text-soft); box-shadow: none;
}
.channel-toggles .bk-btn:hover { border-color: var(--qcm-faint); color: var(--qcm-text); }
.channel-toggles .bk-btn.bk-active {
  border-color: var(--qcm-accent); background: var(--qcm-accent-soft); background-image: none;
  color: var(--qcm-accent-strong); font-weight: 700; box-shadow: inset 3px 0 0 var(--qcm-accent);
}

/* =================================================================== drawer */
.qcm-drawer-layer { display: contents; }
/* click-anywhere backdrop that dims the page and focuses the drawer */
.qcm-scrim {
  position: fixed; inset: 0; z-index: 55; width: 100%; height: 100%;
  background: var(--qcm-scrim); border: 0; border-radius: 0; box-shadow: none;
  padding: 0; cursor: pointer;
}
.qcm-scrim:hover { background: var(--qcm-scrim); }
.qcm-drawer {
  position: fixed; top: 0; right: 0; height: 100vh; width: min(680px, 92vw);
  z-index: 60; overflow-y: auto; background: var(--qcm-surface);
  border-left: 1px solid var(--qcm-border); box-shadow: var(--qcm-shadow-2); padding: var(--qcm-space-4);
}
.qcm-drawer-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--qcm-space-3); margin-bottom: var(--qcm-space-4);
  padding-bottom: var(--qcm-space-3); border-bottom: 1px solid var(--qcm-border);
}
.qcm-drawer-title { font-size: var(--qcm-fs-display); font-weight: 800; color: var(--qcm-text); white-space: nowrap; }

/* keep stray third-party dark-mode toggles hidden (defensive) */
button[title*="theme" i], button[aria-label*="theme" i], .theme-toggle, .pn-theme-toggle { display: none !important; }

/* =============================================================== responsive */
@media (max-width: 1280px) {
  .qcm-page-data-body { flex-direction: column; }
  .qcm-rail { flex: 1 1 auto; width: 100%; position: static; max-height: none; }
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
  .qcm-topbar { top: var(--qcm-space-3); }
}
"""


# Per-widget stylesheet that paints a filled-accent (blue) button — the same blue
# as the brand mark (var(--qcm-accent)). Bokeh renders every Button/FileDownload in
# its OWN shadow root with its own base.css, so the app stylesheet's .bk-btn-primary
# rule can't reach it (that's why the topbar Export stayed Bokeh's default blue).
# Inject this into each accent button via its `stylesheets=` param. `!important`
# is needed here to beat Bokeh's base rules inside the same shadow root; custom
# properties (--qcm-*) inherit across the shadow boundary so var() resolves.
#   NB: a regular Button renders `.bk-btn-primary`, but FileDownload renders
#   `.bk-btn-default` regardless of button_type — so target `.bk-btn` broadly.
#   Safe because this is injected only into the specific accent widgets.
ACCENT_BUTTON_STYLESHEET = """
.bk-btn {
  background: var(--qcm-accent) !important; background-image: none !important;
  border: 1px solid var(--qcm-accent) !important; color: var(--qcm-text) !important;
  box-shadow: none !important; font-weight: 700;
}
.bk-btn:hover {
  background: var(--qcm-accent-strong) !important; border-color: var(--qcm-accent-strong) !important;
}
.bk-btn:active {
  background: var(--qcm-accent-active) !important; border-color: var(--qcm-accent-active) !important;
}
"""
