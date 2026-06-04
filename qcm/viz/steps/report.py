"""Report page: configure, preview, and export a run report.

Every control here does something real:

- **Include** drives which sections appear in the generated report;
- **Data format** switches the current-range data download between Parquet/CSV;
- **Download report (HTML)** builds a self-contained HTML document (run info,
  statistics, the headline plot, per-cycle summary, and saved phases) that opens
  offline in any browser;
- the notebook download exports the analysis notebook for the chosen region.
"""
from __future__ import annotations

import io
import tempfile
from html import escape

import panel as pn
import polars as pl

from .. import echem
from ..design import ACCENT_BUTTON_STYLESHEET
from ..tokens import COLORS, FONT, MONO
from ._base import BaseStep

_SECTIONS = ["Run information", "Statistics (current range)", "Plots", "Per-cycle summary", "Phase table"]

# CheckBoxGroup options render inside the widget's shadow root, out of reach of the
# app stylesheet. Panel injects these rules into that shadow root so each box lines
# up with its label and the rows sit tight (the global 34px input height otherwise
# top-aligns the box and stretches the rows).
_CHECKBOX_CSS = """
.bk-input-group { display: flex; flex-direction: column; gap: 6px; }
.bk-input-group label, .bk-input-group > div {
  display: flex; align-items: center; gap: 8px; margin: 0; min-height: 0;
  font-size: 13px; color: #334155;
}
.bk-input-group input[type="checkbox"] {
  width: 16px; height: 16px; min-height: 0; flex: 0 0 auto; margin: 0; padding: 0;
  accent-color: var(--qcm-accent, #4d93ff); cursor: pointer;
}
.bk-label { line-height: 1.3; }
"""


class ReportStep(BaseStep):
    def __init__(self, controls, data, actions):
        super().__init__(controls, data, actions)
        self.include = pn.widgets.CheckBoxGroup(
            name="", options=_SECTIONS, value=list(_SECTIONS), sizing_mode="stretch_width",
            stylesheets=[_CHECKBOX_CSS],
        )
        self.data_format = pn.widgets.Select(
            name="", options={"Parquet (.parquet)": "parquet", "CSV (.csv)": "csv"},
            value="parquet", sizing_mode="stretch_width", css_classes=["compact-select"],
        )
        self.data_dl = pn.widgets.FileDownload(
            label="⬇ Current range data", filename="qcm_current_range.parquet",
            callback=self._data_file, button_type="primary", sizing_mode="stretch_width",
            stylesheets=[ACCENT_BUTTON_STYLESHEET],
        )
        self.data_format.param.watch(self._on_format, "value")
        self.report_html_dl = pn.widgets.FileDownload(
            label="⬇ Download report (HTML)", filename="qcm_report.html",
            callback=self._report_html_file, button_type="primary", sizing_mode="stretch_width",
            stylesheets=[ACCENT_BUTTON_STYLESHEET],
        )

    # --- data export (format-aware) ---------------------------------------
    def _on_format(self, _event=None) -> None:
        ext = "csv" if self.data_format.value == "csv" else "parquet"
        self.data_dl.filename = f"qcm_current_range.{ext}"

    def _export_df(self) -> pl.DataFrame:
        state = self.controls.state()
        t0, t1, _label = self.actions._export_window_us()
        cols = [c for c in ["fit_center", "fit_fwhm", "fit_gamma"] if c in self.actions.run.columns]
        return self.actions.run.timeline(cols, t0=t0, t1=t1, groups=state.groups, level="raw")

    def _data_file(self):
        df = self._export_df()
        buf = io.BytesIO()
        if self.data_format.value == "csv":
            df.write_csv(buf)
        else:
            df.write_parquet(buf)
        buf.seek(0)
        return buf

    # --- shared content ----------------------------------------------------
    def _run_info_rows(self) -> list[tuple[str, str]]:
        info = self.data.info
        try:
            method = echem.detect_technique(self.data.echem_waveform()).upper() if self.data.has_echem() else "QCM-D"
        except Exception:
            method = "—"
        overtones = ", ".join(str(n) for n in sorted(set(info.orders.values()))) or "—"
        return [
            ("Run", str(info.run_id)),
            ("Duration", f"{info.span_s:,.2f} s"),
            ("Channels", str(len(info.groups))),
            ("Overtones", overtones),
            ("Method", method),
            ("Sweeps", str(info.n_sweeps)),
        ]

    # --- HTML report builder ----------------------------------------------
    @staticmethod
    def _kv_html(rows: list[tuple[str, str]]) -> str:
        body = "".join(f"<tr><th>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>" for k, v in rows)
        return f"<table class='kv'>{body}</table>"

    @staticmethod
    def _df_html(df: pl.DataFrame) -> str:
        if df is None or df.is_empty():
            return "<p class='muted'>No data.</p>"
        rounded = df
        for c in rounded.columns:
            if rounded[c].dtype in (pl.Float32, pl.Float64):
                rounded = rounded.with_columns(pl.col(c).round(4))
        return rounded.to_pandas().to_html(index=False, border=0, classes="data")

    def _stats_html(self) -> str:
        try:
            summary = self.data.region_summary(self.controls.state())
            return self._df_html(summary)
        except Exception:
            return "<p class='muted'>Statistics unavailable.</p>"

    def _per_cycle_html(self) -> str:
        try:
            stats = echem.cycle_stats(self.data.echem_waveform(), echem.detect_technique(self.data.echem_waveform()))
            return self._df_html(stats)
        except Exception:
            return "<p class='muted'>No per-cycle data.</p>"

    def _phase_html(self) -> str:
        rows = []
        for ann in self.data.annotations():
            if ann.type != "range" or ann.t1 is None:
                continue
            t0_us = self.data.info.t0_us
            start = (ann.t0 - t0_us) / 1_000_000
            end = (ann.t1 - t0_us) / 1_000_000
            kind = ann.tags[0] if ann.tags else "phase"
            rows.append((ann.label or kind.title(), kind, f"{start:,.2f} – {end:,.2f} s"))
        if not rows:
            return "<p class='muted'>No phases saved.</p>"
        body = "".join(
            f"<tr><td>{escape(name)}</td><td>{escape(kind)}</td><td>{escape(when)}</td></tr>"
            for name, kind, when in rows
        )
        return f"<table class='data'><thead><tr><th>Phase</th><th>Type</th><th>Time</th></tr></thead><tbody>{body}</tbody></table>"

    # Standalone export, so values are inlined — but sourced from tokens.py so the
    # exported report matches the live UI (white base, mono numerics, blue accent).
    _REPORT_CSS = f"""
    body {{ font-family: {FONT}; color: {COLORS['text']}; margin: 32px auto; max-width: 960px; }}
    h1 {{ font-size: 1.5rem; }} h2 {{ font-size: 1.05rem; margin-top: 28px; border-bottom: 1px solid {COLORS['border']}; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; font-size: 0.86rem; }} table.kv th {{ text-align: left; color: {COLORS['muted']}; padding-right: 16px; }}
    table.kv td, table.kv th {{ padding: 3px 8px; }} table.data {{ width: 100%; }}
    table.data th {{ background: {COLORS['surface-muted']}; color: {COLORS['text-soft']}; text-align: left; }} table.data th, table.data td {{ border: 1px solid {COLORS['border']}; padding: 5px 9px; }}
    table.data td {{ font-family: {MONO}; font-variant-numeric: tabular-nums; }}
    .muted {{ color: {COLORS['faint']}; }}
    """

    def _report_html_file(self):
        try:
            from bokeh.resources import INLINE

            inc = set(self.include.value)
            run_id = str(self.data.info.run_id)
            blocks: list = [pn.pane.HTML(f"<style>{self._REPORT_CSS}</style><h1>QCM-D report — run {escape(run_id)}</h1>")]
            if "Run information" in inc:
                blocks.append(pn.pane.HTML(f"<h2>Run information</h2>{self._kv_html(self._run_info_rows())}"))
            if "Statistics (current range)" in inc:
                blocks.append(pn.pane.HTML(f"<h2>Statistics (current analysis range)</h2>{self._stats_html()}"))
            if "Plots" in inc:
                blocks.append(pn.pane.HTML("<h2>Headline plot</h2>"))
                blocks.append(pn.pane.HoloViews(self.unified_anchor(window="current", height=360), sizing_mode="stretch_width"))
            if "Per-cycle summary" in inc and self.data.has_echem():
                blocks.append(pn.pane.HTML(f"<h2>Per-cycle summary</h2>{self._per_cycle_html()}"))
            if "Phase table" in inc:
                blocks.append(pn.pane.HTML(f"<h2>Phases</h2>{self._phase_html()}"))
            layout = pn.Column(*blocks, sizing_mode="stretch_width")
            tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
            tmp.close()
            layout.save(tmp.name, resources=INLINE, title=f"QCM report — {run_id}")
            return open(tmp.name, "rb")
        except Exception as exc:  # pragma: no cover
            buf = io.BytesIO(f"<h1>Report generation failed</h1><pre>{escape(str(exc))}</pre>".encode())
            buf.seek(0)
            return buf

    # --- export console (this page's only unique job) ----------------------
    def report_card(self):
        """The headline artifact: pick which sections the HTML report contains,
        then download it. Holds the page's single primary action."""
        return pn.Card(
            pn.pane.HTML("<div class='eyebrow'>Sections to include</div>", margin=0),
            self.include,
            self.report_html_dl,
            title="Report (HTML)", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-report-config"],
        )

    def raw_exports_card(self):
        """Region-scoped raw outputs (data file + notebook). The Region selector
        governs both buttons, so they live together with it."""
        return pn.Card(
            pn.pane.HTML("<div class='eyebrow'>Region</div>", margin=0),
            self.controls.marker_select,
            pn.pane.HTML("<div class='eyebrow'>Data</div>", margin=0),
            self.data_format,
            self.data_dl,
            pn.pane.HTML("<div class='eyebrow'>Notebook</div>", margin=0),
            pn.pane.HTML("<div class='qcm-export-note'>Exports the analysis notebook "
                         "for the chosen region.</div>", margin=0),
            self.actions.export_nb_dl,
            title="Raw exports", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-report-export"],
        )

    # --- page surface ------------------------------------------------------
    def page(self):
        """A focused export console — config + export only, centered. Everything
        else a report could show is already on the Data / Results pages and the
        sidebar Run-info card, so it isn't restated here."""
        return pn.Column(
            self.report_card(),
            self.raw_exports_card(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-export"],
        )

    # --- legacy hook (kept so the old shell paths still resolve) -----------
    def secondary_panel(self):
        return self.raw_exports_card()
