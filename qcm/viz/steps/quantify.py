"""Quantify step: the Data-page "Live statistics" readout.

The shell mounts this step only for its analysis-target summary table; the hero
plot and per-channel statistics live in the shell's own Data-page assembly.
"""
from __future__ import annotations

from dataclasses import replace

import panel as pn
import polars as pl

from ._base import BaseStep
from ..errors import surface_error

_US = 1_000_000


class QuantifyStep(BaseStep):
    """Analysis-target summary over the current range or a saved region."""

    def target_state(self):
        """Return the ViewState for the selected analysis target.

        Current range uses the live slider. A saved marker produces a temporary
        state whose time range is exactly the marker, so switching back to
        Current range restores the real live range without overwriting it.
        """
        state = self.controls.state()
        selected = self.controls.analysis_region_select.value
        if not selected or selected == "__current__":
            return state
        for ann in self.data.annotations():
            if ann.id == selected and ann.type == "range" and ann.t1 is not None:
                start_s = (ann.t0 - self.data.info.t0_us) / _US
                end_s = (ann.t1 - self.data.info.t0_us) / _US
                return replace(state, t_range_s=(float(start_s), float(end_s)))
        return state

    def selected_target_summary_table(self):
        try:
            state = self.target_state()
            summary = self.data.region_summary(state)
            if summary.is_empty():
                return self.empty_state("No data in the selected analysis target.")
            cols = [c for c in ["df_n", "dD", "mass", "Q", "dD_per_df"] if c in summary.columns]
            means = summary.select([pl.col(c).mean().alias(c) for c in cols]).to_dicts()[0]
            start, end = state.t_range_s
            duration = max(0.0, float(end) - float(start))
            rows = [
                ("Range", f"{start:,.2f}–{end:,.2f} s"),
                ("Duration", f"{duration:,.2f} s"),
                ("Mean Δf/n", self._fmt(means.get("df_n"), 2, " Hz")),
                ("Mean ΔD", self._fmt(means.get("dD"), 3, " ×10⁻⁶")),
                ("Mass", self._fmt(means.get("mass"), 1, " ng/cm²")),
                ("Mean Q", self._fmt(means.get("Q"), 0)),
                ("ΔD/Δf", self._fmt(means.get("dD_per_df"), 4)),
            ]
            table = pl.DataFrame(rows, schema=["Metric", "Value"], orient="row")
            return pn.widgets.Tabulator(
                table.to_pandas(),
                height=232,
                layout="fit_columns",
                show_index=False,
                sizing_mode="stretch_width",
                disabled=True,
                css_classes=["summary-table", "target-summary-table"],
            )
        except Exception as exc:  # pragma: no cover
            return surface_error("Target summary", exc)
