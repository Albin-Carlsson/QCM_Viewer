"""Electrochemistry step: cyclic voltammetry (CV) and chronopotentiometry (CP).

Shows technique-specific metadata, the standard CV/CP plots, and cycle handling
(all / individual / range) with a per-cycle statistics summary. The technique is
auto-detected from the current waveform but can be overridden. Cycle selection is
local to this step — it filters only the electrochemistry views, not the QCM
resonance plots.
"""
from __future__ import annotations

import panel as pn
import polars as pl

from .. import echem, plots
from ..components import empty_state, hint
from ..controls import ViewerControls
from ..actions import ViewerActions
from ..data import QCMViewData
from ..theme import COMPACT_PLOT_HEIGHT, ELECTRODE_AREA_CM2, HERO_HEIGHT, PLOT_HEIGHT
from ._base import BaseStep

_E = "potential"
_I = "current"
_J = "current_density"
_Q = "charge"
_T = "time_s"
_CYC = "cycle"

_E_LABEL = "Potential [V]"
_I_LABEL = "Current [A]"
_J_LABEL = "Current density [A/cm²]"
_Q_LABEL = "Charge [C]"
_T_LABEL = "Time [s]"
_CYC_LABEL = "Cycle number"


class ElectrochemistryStep(BaseStep):
    """CV/CP views with derived metadata and cycle handling."""

    def __init__(self, controls: ViewerControls, data: QCMViewData, actions: ViewerActions):
        super().__init__(controls, data, actions)
        cycles = echem.cycle_values(self.data.echem_waveform()) if self.data.has_echem() else []
        c_lo = cycles[0] if cycles else 0
        c_hi = cycles[-1] if cycles else 0

        self.technique_select = pn.widgets.RadioButtonGroup(
            name="Technique",
            options={"Auto": "auto", "Cyclic voltammetry": "cv", "Chronopotentiometry": "cp"},
            value="auto",
            button_type="primary",
            sizing_mode="stretch_width",
            css_classes=["echem-technique-toggle"],
        )
        self.cycle_mode = pn.widgets.RadioButtonGroup(
            name="Cycles",
            options={"All cycles": "all", "Individual": "individual", "Range": "range"},
            value="all",
            button_type="default",
            sizing_mode="stretch_width",
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

    # --- inputs / state ----------------------------------------------------
    @property
    def _inputs(self) -> tuple:
        return (self.technique_select, self.cycle_mode, self.cycle_select, self.cycle_range)

    def effective_technique(self) -> str:
        choice = self.technique_select.value
        if choice in ("cv", "cp"):
            return choice
        return echem.detect_technique(self.data.echem_waveform())

    def _selected_waveform(self) -> pl.DataFrame:
        wf = self.data.echem_waveform()
        if wf.is_empty():
            return wf
        wf = echem.filter_cycles(
            wf,
            self.cycle_mode.value,
            cycle=int(self.cycle_select.value),
            lo=int(self.cycle_range.value[0]),
            hi=int(self.cycle_range.value[1]),
        )
        if _I in wf.columns:
            wf = wf.with_columns((pl.col(_I) / ELECTRODE_AREA_CM2).alias(_J))
        return wf

    # --- plots -------------------------------------------------------------
    def _plot(self, xcol, ycol, xlabel, ylabel, title, *, by_cycle=True, monotonic=False, height=PLOT_HEIGHT):
        wf = self._selected_waveform()
        return self.force_plot_height(
            plots.echem_curve(wf, xcol, ycol, xlabel, ylabel, title,
                              by_cycle=by_cycle, monotonic=monotonic, height=height),
            height,
        )

    def primary_plot(self):
        try:
            if not self.data.has_echem():
                return empty_state("This run has no electrochemistry channel.")
            if self.effective_technique() == "cp":
                return self.nearest_hover(self._plot(
                    _T, _E, _T_LABEL, _E_LABEL, "Potential vs time (CP)",
                    by_cycle=False, monotonic=True, height=HERO_HEIGHT))
            return self.nearest_hover(self._plot(
                _E, _I, _E_LABEL, _I_LABEL, "Current vs potential (CV voltammogram)",
                by_cycle=True, monotonic=False, height=HERO_HEIGHT))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Electrochemistry plot failed: {exc}", alert_type="danger")

    def secondary_plots(self):
        try:
            if not self.data.has_echem():
                return pn.Spacer(height=0)
            if self.effective_technique() == "cp":
                specs = [
                    (_Q, _E, _Q_LABEL, _E_LABEL, "Potential vs charge", False, False),
                    (_CYC, _E, _CYC_LABEL, _E_LABEL, "Potential vs cycle", False, True),
                    (_T, _I, _T_LABEL, _I_LABEL, "Current vs time", False, True),
                ]
            else:
                specs = [
                    (_E, _J, _E_LABEL, _J_LABEL, "Current density vs potential", True, False),
                    (_T, _E, _T_LABEL, _E_LABEL, "Potential vs time", False, True),
                    (_T, _I, _T_LABEL, _I_LABEL, "Current vs time", False, True),
                ]
            cards = [
                self.nearest_hover(self._plot(x, y, xl, yl, title, by_cycle=bc, monotonic=mono, height=COMPACT_PLOT_HEIGHT))
                for (x, y, xl, yl, title, bc, mono) in specs
            ]
            rows = pn.GridBox(*cards, ncols=2, sizing_mode="stretch_width")
            return rows
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Electrochemistry plots failed: {exc}", alert_type="danger")

    # --- metadata + cycle stats -------------------------------------------
    def metadata_card(self):
        try:
            if not self.data.has_echem():
                return pn.Spacer(height=0)
            technique = self.effective_technique()
            wf = self.data.echem_waveform()
            meta = echem.metadata(wf, technique)
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
                table.to_pandas(), height=210, layout="fit_data_fill",
                show_index=False, sizing_mode="stretch_width", disabled=True,
                css_classes=["summary-table", "echem-metadata-table"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Metadata failed: {exc}", alert_type="danger")

    def cycle_stats_table(self):
        try:
            if not self.data.has_echem():
                return pn.Spacer(height=0)
            stats = echem.cycle_stats(self._selected_waveform(), self.effective_technique())
            if stats.is_empty():
                return pn.pane.Markdown("No cycles in the current selection.")
            for c in stats.columns:
                if stats[c].dtype in (pl.Float32, pl.Float64):
                    stats = stats.with_columns(pl.col(c).round(6))
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=min(260, max(110, 38 + stats.height * 26)),
                layout="fit_data_fill", show_index=False,
                sizing_mode="stretch_width", disabled=True,
                css_classes=["summary-table", "echem-cycle-stats"],
            )
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Cycle stats failed: {exc}", alert_type="danger")

    def cycle_controls(self):
        def picker(mode):
            if mode == "individual":
                return self.cycle_select
            if mode == "range":
                return self.cycle_range
            return pn.pane.Markdown("<small>Showing all detected cycles.</small>", margin=0)
        return pn.Column(
            pn.pane.HTML("<b>Cycle handling</b>", margin=0),
            self.cycle_mode,
            pn.bind(picker, self.cycle_mode),
            margin=0, sizing_mode="stretch_width", css_classes=["echem-cycle-controls"],
        )

    # --- step surface ------------------------------------------------------
    def anchor_plot(self):
        return pn.bind(lambda *_: self.primary_plot(), *self._inputs)

    def secondary_panel(self):
        if not self.data.has_echem():
            return pn.Column(
                hint("This run has no electrochemistry channel, so CV/CP views are "
                     "unavailable. Re-ingest a run that includes potential/current.", tone="info"),
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
            )
        return pn.Column(
            self.technique_select,
            pn.bind(lambda *_: self.metadata_card(), self.technique_select),
            self.cycle_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary", "echem-secondary"],
        )

    def below_plot_panel(self):
        if not self.data.has_echem():
            return pn.Spacer(height=0)
        return pn.Column(
            pn.bind(lambda *_: self.secondary_plots(), *self._inputs),
            self.panel(
                lambda: self.cycle_stats_table(),
                *self._inputs, title="Cycle statistics",
            ),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-below-plot", "echem-below"],
        )
