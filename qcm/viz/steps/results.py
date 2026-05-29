"""Results page: a cycle-aware QCM-D / electrochemistry dashboard.

Composes existing data services into the at-a-glance results surface:

- headline stat cards (Δf/n, ΔD, mass, and — when an EC channel is present —
  charge, MPE, current density) over the current analysis range;
- a technique guess (CV / CP) with the derived metadata (vertices, scan rate,
  scan count, or applied current / steps);
- cycle selection (all / single / range) that filters the per-cycle table and
  the electrochemistry plots;
- a technique-aware headline plot plus mass- and current-density-vs-potential;
- a per-cycle summary table augmented with per-cycle MPE.

No new science lives here — every number comes from :class:`QCMViewData`,
:mod:`echem`, and :mod:`science` so the page stays consistent with the Data page.
"""
from __future__ import annotations

from dataclasses import replace

import panel as pn
import polars as pl

from .. import echem, plots
from ..components import icon_stat, stat_grid
from ..theme import (
    COMPACT_PLOT_HEIGHT,
    ELECTRODE_AREA_CM2,
    FARADAY_CONSTANT,
    PLOT_HEIGHT,
    RESULTS_PLOT_HEIGHT,
    axis,
    quantity,
)
from ._base import BaseStep

_E = "potential"
_I = "current"
_J = "current_density"
_Q = "charge"
_T = "time_s"
_E_LABEL = "Potential [V]"
_I_LABEL = "Current [A]"
_J_LABEL = "Current density [A/cm²]"
_Q_LABEL = "Charge [C]"
_T_LABEL = "Time [s]"


class ResultsStep(BaseStep):
    """Headline QCM-D / EQCM results with cycle handling over the analysis range."""

    def __init__(self, controls, data, actions):
        super().__init__(controls, data, actions)
        cycles = echem.cycle_values(self.data.echem_waveform()) if self.data.has_echem() else []
        c_lo = cycles[0] if cycles else 0
        c_hi = cycles[-1] if cycles else 0
        self._has_cycles = len(cycles) > 1

        self.technique_select = pn.widgets.RadioButtonGroup(
            name="", options={"Auto": "auto", "Cyclic voltammetry": "cv", "Chronopotentiometry": "cp"},
            value="auto", button_type="primary", sizing_mode="stretch_width",
            css_classes=["echem-technique-toggle"],
        )
        self.cycle_mode = pn.widgets.RadioButtonGroup(
            name="", options={"All": "all", "Single": "individual", "Range": "range"},
            value="all", button_type="default", sizing_mode="stretch_width",
            css_classes=["echem-cycle-mode"],
        )
        self.cycle_select = pn.widgets.IntSlider(
            name="Cycle", start=c_lo, end=max(c_hi, c_lo), value=c_lo, step=1,
            sizing_mode="stretch_width",
        )
        self.cycle_range = pn.widgets.IntRangeSlider(
            name="Cycle range", start=c_lo, end=max(c_hi, c_lo), value=(c_lo, max(c_hi, c_lo)),
            step=1, sizing_mode="stretch_width",
        )

    # --- inputs ------------------------------------------------------------
    @property
    def _cycle_inputs(self) -> tuple:
        return (self.technique_select, self.cycle_mode, self.cycle_select, self.cycle_range)

    def _technique(self) -> str:
        choice = self.technique_select.value
        if choice in ("cv", "cp"):
            return choice
        return echem.detect_technique(self.data.echem_waveform())

    def _selected_waveform(self) -> pl.DataFrame:
        wf = self.data.echem_waveform()
        if wf.is_empty():
            return wf
        wf = echem.filter_cycles(
            wf, self.cycle_mode.value,
            cycle=int(self.cycle_select.value),
            lo=int(self.cycle_range.value[0]),
            hi=int(self.cycle_range.value[1]),
        )
        if _I in wf.columns:
            wf = wf.with_columns((pl.col(_I) / ELECTRODE_AREA_CM2).alias(_J))
        return wf

    # --- aggregation -------------------------------------------------------
    def _means(self, state) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        try:
            summary = self.data.region_summary(state)
            if not summary.is_empty():
                for col in ("df_n", "dD", "mass", "Q", "dD_per_df"):
                    if col in summary.columns:
                        out[col] = float(summary[col].mean())
        except Exception:
            pass
        if self.data.has_echem():
            for key, name in (("charge", "charge"), ("current_density", "jdens"), ("mpe", "mpe")):
                try:
                    vdf, _ = self.data.value_df(state, key)
                    vals = vdf["value"].drop_nulls()
                    out[name] = float(vals.mean()) if vals.len() else None
                except Exception:
                    out[name] = None
        return out

    # --- headline cards ----------------------------------------------------
    def summary_cards(self):
        try:
            state = self.controls.state()
            m = self._means(state)
            cells = [
                icon_stat("Mean Δf/n", self._fmt(m.get("df_n"), 2, " Hz"), icon="frequency"),
                icon_stat("Mean ΔD", self._fmt(m.get("dD"), 3, " ×10⁻⁶"), icon="dissipation", tone="accent"),
                icon_stat("Mass (Sauerbrey)", self._fmt(m.get("mass"), 1, " ng/cm²"), icon="mass", tone="success"),
            ]
            if self.data.has_echem():
                charge = m.get("charge")
                jdens = m.get("jdens")
                cells += [
                    icon_stat("Charge", self._fmt(None if charge is None else charge * 1e3, 3, " mC"), icon="charge"),
                    icon_stat("MPE", self._fmt(m.get("mpe"), 1, " g/mol"), icon="mpe", tone="danger"),
                    icon_stat("Current density", self._fmt(None if jdens is None else jdens * 1e3, 2, " mA/cm²"), icon="density", tone="success"),
                ]
            return stat_grid(cells)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Summary failed: {exc}", alert_type="danger")

    # --- technique metadata ------------------------------------------------
    def metadata_card(self):
        try:
            if not self.data.has_echem():
                return self.empty_state("This run has no electrochemistry channel.")
            technique = self._technique()
            meta = echem.metadata(self.data.echem_waveform(), technique)
            if technique == "cp":
                rows = [
                    ("Technique", "Chronopotentiometry (CP)"),
                    ("Applied current", self._fmt(meta.get("applied_current", 0) * 1e6, 2, " µA")),
                    ("Applied current density", self._fmt(meta.get("applied_current_density", 0) * 1e6, 2, " µA/cm²")),
                    ("Step duration (median)", self._fmt(meta.get("step_duration"), 2, " s")),
                    ("Number of steps", self._fmt(meta.get("n_steps"), 0)),
                ]
            else:
                rows = [
                    ("Technique", "Cyclic voltammetry (CV)"),
                    ("E start", self._fmt(meta.get("e_start"), 3, " V")),
                    ("E vertex 1", self._fmt(meta.get("e_vertex1"), 3, " V")),
                    ("E vertex 2", self._fmt(meta.get("e_vertex2"), 3, " V")),
                    ("Scan rate", self._fmt((meta.get("scan_rate") or 0) * 1000, 1, " mV/s")),
                    ("Number of scans", self._fmt(meta.get("n_scans"), 0)),
                ]
            table = pl.DataFrame(rows, schema=["Property", "Value"], orient="row")
            return pn.widgets.Tabulator(
                table.to_pandas(), height=212, layout="fit_data_fill",
                show_index=False, sizing_mode="stretch_width", disabled=True,
                css_classes=["summary-table", "echem-metadata-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Metadata failed: {exc}", alert_type="danger")

    # --- cycle controls ----------------------------------------------------
    def cycle_controls(self):
        def picker(mode):
            if mode == "individual":
                return self.cycle_select
            if mode == "range":
                return self.cycle_range
            return pn.pane.HTML("<div class='qcm-empty' style='padding:8px'>Showing all detected cycles.</div>", margin=0)
        return pn.Column(
            pn.pane.HTML("<div class='eyebrow'>Cycles</div>", margin=0),
            self.cycle_mode,
            pn.bind(picker, self.cycle_mode),
            margin=0, sizing_mode="stretch_width", css_classes=["echem-cycle-controls"],
        )

    # --- per-cycle table ---------------------------------------------------
    def _augment_with_mpe(self, stats: pl.DataFrame) -> pl.DataFrame:
        """Add a per-cycle MPE column (Faraday slope of mass change vs charge)."""
        try:
            if stats.is_empty() or "cycle" not in stats.columns:
                return stats
            full = replace(self.controls.state(), t_range_s=(0.0, float(self.data.info.span_s)))
            mdf, _ = self.data.value_df(full, "sauerbrey_mass", "time")
            if mdf.is_empty():
                return stats
            mass_ts = mdf.group_by("timestamp").agg(pl.col("value").mean().alias("_mass"))
            wf = self._selected_waveform()
            if wf.is_empty() or _Q not in wf.columns or "cycle" not in wf.columns:
                return stats
            joined = (
                wf.select(["timestamp", pl.col("cycle").cast(pl.Int64), _Q])
                .join(mass_ts, on="timestamp", how="inner")
            )
            if joined.is_empty():
                return stats
            per = (
                joined.group_by("cycle")
                .agg([
                    (pl.col("_mass").sort_by("timestamp").last()
                     - pl.col("_mass").sort_by("timestamp").first()).alias("_dm_ng"),
                    (pl.col(_Q).sort_by("timestamp").last()
                     - pl.col(_Q).sort_by("timestamp").first()).alias("_dq"),
                ])
                .with_columns(
                    pl.when(pl.col("_dq").abs() > 1e-15)
                    .then(FARADAY_CONSTANT * (pl.col("_dm_ng") * ELECTRODE_AREA_CM2 * 1e-9) / pl.col("_dq"))
                    .otherwise(None)
                    .round(2)
                    .alias("MPE_g_per_mol")
                )
                .select(["cycle", "MPE_g_per_mol"])
            )
            return stats.join(per, on="cycle", how="left")
        except Exception:
            return stats

    def per_cycle_table(self):
        try:
            if not self.data.has_echem():
                return self.empty_state("This run has no electrochemistry channel, so per-cycle results are unavailable.")
            stats = echem.cycle_stats(self._selected_waveform(), self._technique())
            if stats.is_empty():
                return self.empty_state("No cycles in the current selection.")
            stats = self._augment_with_mpe(stats)
            for c in stats.columns:
                if stats[c].dtype in (pl.Float32, pl.Float64):
                    stats = stats.with_columns(pl.col(c).round(6))
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=min(320, max(120, 40 + stats.height * 28)),
                layout="fit_data_fill", show_index=False,
                sizing_mode="stretch_width", disabled=True,
                css_classes=["summary-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Per-cycle table failed: {exc}", alert_type="danger")

    # --- plots -------------------------------------------------------------
    def primary_echem_plot(self, height: int = RESULTS_PLOT_HEIGHT):
        """Technique-aware headline EC plot: CV voltammogram or CP potential profile."""
        try:
            if not self.data.has_echem():
                return self.empty_state("No electrochemistry channel.")
            wf = self._selected_waveform()
            if self._technique() == "cp":
                plot = plots.echem_curve(wf, _T, _E, _T_LABEL, _E_LABEL, "Potential vs time (CP)",
                                         by_cycle=False, monotonic=True, height=height, show_legend=False)
            else:
                plot = plots.echem_curve(wf, _E, _I, _E_LABEL, _I_LABEL, "Current vs potential (CV)",
                                         by_cycle=True, monotonic=False, height=height,
                                         show_legend=self._has_cycles)
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Plot failed: {exc}", alert_type="danger")

    def mass_vs_potential(self, height: int = PLOT_HEIGHT):
        try:
            state = self.controls.state()
            x_key = "potential" if self.data.has_echem() else "time"
            ax = axis(x_key)
            q = quantity("sauerbrey_mass")
            value_df, _ = self.data.value_df(state, "sauerbrey_mass", x_key)
            plot = plots.analysis_timeline(
                value_df, q, ax, state.groups, state.orders,
                f"Mass vs {ax.label}",
                annotation_spans=self.data.annotation_spans(state) if ax.is_time else None,
                select_x=False, height=height,
            )
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Mass plot failed: {exc}", alert_type="danger")

    def density_vs_potential(self, height: int = COMPACT_PLOT_HEIGHT):
        try:
            if not self.data.has_echem():
                return self.empty_state("No electrochemistry channel.")
            wf = self._selected_waveform()
            plot = plots.echem_curve(wf, _E, _J, _E_LABEL, _J_LABEL, "Current density vs potential",
                                     by_cycle=True, monotonic=False, height=height,
                                     show_legend=False)
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Plot failed: {exc}", alert_type="danger")

    # --- page surface ------------------------------------------------------
    def page(self):
        sig = self.controls.explore_inputs
        if not self.data.has_echem():
            # QCM-only run: headline cards + one big mass-vs-time plot.
            return pn.Column(
                self.panel(self.summary_cards, *sig, title="Summary (current analysis range)"),
                self.panel(lambda: self.mass_vs_potential(height=RESULTS_PLOT_HEIGHT),
                           *sig, self.controls.plot_reset_version, title="Mass vs time"),
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-results"],
            )

        cyc = self._cycle_inputs
        main = pn.Column(
            self.panel(self.summary_cards, *sig, title="Summary (current analysis range)"),
            self.panel(lambda: self.primary_echem_plot(), *sig, *cyc, self.controls.plot_reset_version,
                       title="Electrochemistry"),
            pn.Row(
                self.panel(lambda: self.mass_vs_potential(), *sig, self.controls.plot_reset_version,
                           title="Mass vs potential"),
                self.panel(lambda: self.density_vs_potential(), *sig, *cyc, self.controls.plot_reset_version,
                           title="Current density vs potential"),
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-plotrow"],
            ),
            self.panel(self.per_cycle_table, *sig, *cyc, title="Per-cycle summary"),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-main"],
        )
        side = pn.Column(
            pn.Card(
                self.technique_select,
                pn.bind(lambda *_: self.metadata_card(), self.technique_select),
                title="Technique", collapsible=False, margin=0,
                sizing_mode="stretch_width", css_classes=["qcm-card"],
            ),
            pn.Card(
                self.cycle_controls(),
                title="Cycle selection", collapsible=False, margin=0,
                sizing_mode="stretch_width", css_classes=["qcm-card"],
            ),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-side"],
        )
        return pn.Row(main, side, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-results"])
