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
from ..components import empty_state, icon_stat, run_info_table, stat_grid
from ..theme import COMPACT_PLOT_HEIGHT
from ._base import BaseStep

_SECTIONS = ["Run information", "Statistics (current range)", "Plots", "Per-cycle summary", "Phase table"]


class ReportStep(BaseStep):
    def __init__(self, controls, data, actions):
        super().__init__(controls, data, actions)
        self.include = pn.widgets.CheckBoxGroup(
            name="", options=_SECTIONS, value=list(_SECTIONS), sizing_mode="stretch_width",
        )
        self.data_format = pn.widgets.Select(
            name="", options={"Parquet (.parquet)": "parquet", "CSV (.csv)": "csv"},
            value="parquet", sizing_mode="stretch_width", css_classes=["compact-select"],
        )
        self.data_dl = pn.widgets.FileDownload(
            label="⬇ Current range data", filename="qcm_current_range.parquet",
            callback=self._data_file, button_type="default", sizing_mode="stretch_width",
        )
        self.data_format.param.watch(self._on_format, "value")
        self.report_html_dl = pn.widgets.FileDownload(
            label="⬇ Download report (HTML)", filename="qcm_report.html",
            callback=self._report_html_file, button_type="primary", sizing_mode="stretch_width",
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

    # --- report overview ---------------------------------------------------
    def _region_means(self, state) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        try:
            summary = self.data.region_summary(state)
            if not summary.is_empty():
                for col in ("df_n", "dD", "mass"):
                    if col in summary.columns:
                        out[col] = float(summary[col].mean())
        except Exception:
            pass
        return out

    def report_overview(self):
        try:
            state = self.controls.state()
            lo, hi = state.t_range_s
            m = self._region_means(state)
            cells = [
                icon_stat("Selected range", f"{max(0.0, float(hi) - float(lo)):,.2f} s",
                          icon="time", caption=f"{lo:,.2f} – {hi:,.2f} s"),
                icon_stat("Mean Δf/n", self._fmt(m.get("df_n"), 2, " Hz"), icon="frequency"),
                icon_stat("Mean ΔD", self._fmt(m.get("dD"), 3, " ×10⁻⁶"), icon="dissipation", tone="accent"),
                icon_stat("Mass (Sauerbrey)", self._fmt(m.get("mass"), 1, " ng/cm²"), icon="mass", tone="success"),
            ]
            return stat_grid(cells)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Overview failed: {exc}", alert_type="danger")

    def overview_card(self):
        return pn.Card(
            pn.bind(lambda *_: self.report_overview(), *self.controls.explore_inputs),
            title="Report overview — current analysis range", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card"],
        )

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

    def per_cycle_preview(self):
        try:
            if not self.data.has_echem():
                return empty_state("No electrochemistry channel.")
            stats = echem.cycle_stats(self.data.echem_waveform(), echem.detect_technique(self.data.echem_waveform()))
            if stats.is_empty():
                return empty_state("No cycles detected.")
            stats = stats.head(4)
            for c in stats.columns:
                if stats[c].dtype in (pl.Float32, pl.Float64):
                    stats = stats.with_columns(pl.col(c).round(4))
            return pn.widgets.Tabulator(
                stats.to_pandas(), height=170, layout="fit_data_fill",
                show_index=False, sizing_mode="stretch_width", disabled=True, css_classes=["summary-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Preview failed: {exc}", alert_type="danger")

    def preview_card(self):
        plot = pn.bind(lambda *_: self.unified_anchor(window="current", height=COMPACT_PLOT_HEIGHT, show_legend=False),
                       *self.controls.explore_inputs, self.controls.plot_reset_version)
        return pn.Card(
            pn.Row(
                pn.Column(pn.pane.HTML("<div class='eyebrow'>Run information</div>", margin=0),
                          run_info_table(self._run_info_rows()),
                          margin=0, sizing_mode="stretch_width"),
                pn.Column(plot, margin=0, sizing_mode="stretch_width"),
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-plotrow"],
            ),
            pn.pane.HTML("<div class='eyebrow'>Per-cycle summary (preview)</div>", margin=0),
            pn.bind(lambda *_: self.per_cycle_preview(), *self.controls.explore_inputs),
            title="Report preview", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-report-preview"],
        )

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

    _REPORT_CSS = """
    body { font-family: 'Inter', system-ui, -apple-system, sans-serif; color: #0f172a; margin: 32px auto; max-width: 960px; }
    h1 { font-size: 1.5rem; } h2 { font-size: 1.05rem; margin-top: 28px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }
    table { border-collapse: collapse; font-size: 0.86rem; } table.kv th { text-align: left; color: #64748b; padding-right: 16px; }
    table.kv td, table.kv th { padding: 3px 8px; } table.data { width: 100%; }
    table.data th { background: #f6f8fc; color: #334155; text-align: left; } table.data th, table.data td { border: 1px solid #e2e8f0; padding: 5px 9px; }
    .muted { color: #94a3b8; }
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

    # --- configuration / export columns -----------------------------------
    def config_card(self):
        return pn.Card(
            pn.pane.HTML("<div class='eyebrow'>Include in report</div>", margin=0), self.include,
            pn.pane.HTML("<div class='eyebrow'>Data export format</div>", margin=0), self.data_format,
            title="Configuration", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-report-config"],
        )

    def export_card(self):
        return pn.Card(
            pn.pane.HTML("<div class='eyebrow'>Report</div>", margin=0),
            self.report_html_dl,
            pn.pane.HTML("<div class='eyebrow'>Current range data</div>", margin=0),
            self.controls.marker_select,
            self.data_dl,
            pn.pane.HTML("<div class='eyebrow'>Notebook</div>", margin=0),
            self.actions.export_nb_dl,
            title="Export", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-report-export"],
        )

    # --- page surface ------------------------------------------------------
    def page(self):
        """Coherent two-column report: overview + preview (main) · config + export (side)."""
        main = pn.Column(
            self.overview_card(),
            self.preview_card(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-report-main"],
        )
        side = pn.Column(
            self.config_card(),
            self.export_card(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-report-side"],
        )
        return pn.Row(main, side, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-report"])

    # --- legacy hooks (kept so the old shell paths still resolve) ----------
    def anchor_plot(self):
        return self.overview_anchor("current")

    def secondary_panel(self):
        return self.export_card()
