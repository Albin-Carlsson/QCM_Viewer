"""Composite figure page — the publication-figure composer.

Reproduces (and generalises) the reference notebook's flagship output: a stack
of E(t) / Δf/n(t) / ΔD(t) panels sharing one time axis, with every loaded run
overlaid as a colour family. The user toggles which panels to include, sees a
live matplotlib preview, and downloads it as true vector PDF/SVG (or PNG).

The heavy lifting (data → arrays) reuses the same ``value_df`` /
``overlay_value_df`` services as every other view, and the colours come from the
shared design tokens, so a run looks identical here and on the Data page.
"""
from __future__ import annotations

from dataclasses import replace

import panel as pn
import polars as pl

from ..design import ACCENT_BUTTON_STYLESHEET
from ..errors import surface_error
from ..figure import Panel, Series, composite_figure, figure_bytes
from ..theme import potential_axis_label, quantity
from ..tokens import color_for_run, color_for_run_overtone
from ._base import BaseStep


class CompositeFigureStep(BaseStep):
    """Stacked, shared-x, multi-run publication figure with vector export."""

    def __init__(self, controls, data, actions):
        super().__init__(controls, data, actions)
        echem = self.data.has_echem()
        options: dict[str, str] = {}
        if echem:
            options["E (potential)"] = "potential"
        options["Δf / n"] = "delta_f_norm"
        options["ΔD"] = "delta_D"
        options["Mass"] = "sauerbrey_mass"
        if echem:
            options["Current"] = "current"
            options["Charge"] = "charge"
            options["MPE"] = "mpe"
        # Default = the notebook's stack: E (if present) + Δf/n + ΔD.
        default = (["potential"] if echem else []) + ["delta_f_norm", "delta_D"]
        self.panel_select = pn.widgets.CheckBoxGroup(
            options=options, value=[v for v in default if v in options.values()],
            inline=False, css_classes=["qcm-figure-panels"],
        )
        # Journal width presets (inches): single vs double column.
        self.width_select = pn.widgets.RadioButtonGroup(
            options={"Single column (3.4″)": 3.4, "Double column (7.2″)": 7.2},
            value=7.2, color="default", sizing_mode="stretch_width",
        )

    # --- data → panel specs ------------------------------------------------
    def _runset(self):
        return getattr(self.data, "runset", None)

    def _visible_groups(self, q) -> list[int]:
        """Which channels to draw for a quantity (mirrors the hero's logic)."""
        if q.is_echem:
            groups = self.controls.selected_groups()
            return groups[:1]  # cell-level: identical across overtones, draw once
        if q.kind == "dissipation":
            return self.controls.dissipation_groups()
        if q.kind in ("frequency", "mass", "mpe"):
            return self.controls.frequency_groups()
        return self.controls.selected_groups()

    def _series_for(self, qkey: str, *, multi: bool) -> list[Series]:
        q = quantity(qkey)
        span = float(self.data.info.span_s)
        full = replace(self.controls.state(), t_range_s=(0.0, span))
        groups = self._visible_groups(q)
        orders = self.data.info.orders
        out: list[Series] = []

        def add_run(frame: pl.DataFrame, slot: int, label: str) -> None:
            if frame.is_empty() or "x" not in frame.columns:
                return
            present = [g for g in groups if g in frame["group"].unique().to_list()]
            for ot_slot, g in enumerate(present):
                sub = frame.filter(pl.col("group") == g).select(["x", "value"]).drop_nulls().sort("x")
                if sub.is_empty():
                    continue
                if q.is_echem:
                    color = color_for_run(slot)
                    name = label if multi else q.label
                else:
                    color = color_for_run_overtone(slot, ot_slot)
                    n = orders.get(g, 1)
                    name = f"{label} · n={n}" if multi else f"n = {n}"
                out.append(Series(label=name, color=color,
                                  x=sub["x"].to_numpy(), y=sub["value"].to_numpy()))

        runset = self._runset()
        if multi and runset is not None:
            frame = runset.overlay_value_df(full, qkey, "time")
            labels = runset.labels()
            for slot in sorted(int(s) for s in frame["run_slot"].unique().to_list()) if not frame.is_empty() else []:
                add_run(frame.filter(pl.col("run_slot") == slot), slot, labels[slot])
        else:
            vdf, _ = self.data.value_df(full, qkey, "time")
            add_run(vdf, 0, self.data.info.run_id)
        return out

    def _panels(self) -> list[Panel]:
        runset = self._runset()
        multi = runset is not None and runset.is_multi
        ref = self.controls.params().reference_electrode
        panels: list[Panel] = []
        for qkey in self.panel_select.value:
            q = quantity(qkey)
            ylabel = potential_axis_label(ref) if qkey == "potential" else q.axis_label
            panels.append(Panel(ylabel=ylabel, series=self._series_for(qkey, multi=multi)))
        return panels

    def _figure(self):
        return composite_figure(self._panels(), width_in=float(self.width_select.value))

    # --- view --------------------------------------------------------------
    def _preview(self, *_):
        try:
            if not self.panel_select.value:
                return self.empty_state("Pick one or more panels to build the figure.")
            fig = self._figure()
            return pn.pane.Matplotlib(fig, format="png", tight=True,
                                      sizing_mode="stretch_width",
                                      css_classes=["qcm-figure-preview"])
        except Exception as exc:  # pragma: no cover
            return surface_error("Composite figure", exc)

    def _download(self, fmt: str):
        def cb():
            return figure_bytes(self._figure(), fmt=fmt)
        return cb

    def _downloads(self):
        rows = []
        for label, fmt, primary in (("⬇ PDF (vector)", "pdf", True),
                                    ("⬇ SVG (vector)", "svg", False),
                                    ("⬇ PNG", "png", False)):
            dl = pn.widgets.FileDownload(
                label=label, filename=f"qcm_composite.{fmt}", callback=self._download(fmt),
                color="primary" if primary else "default",
                stylesheets=[ACCENT_BUTTON_STYLESHEET] if primary else [],
                sizing_mode="stretch_width",
            )
            rows.append(dl)
        return pn.Row(*rows, margin=0, sizing_mode="stretch_width")

    def page(self):
        sig = self.controls.explore_inputs
        rv = self.controls.runset_version
        controls = pn.Card(
            pn.pane.HTML("<div class='eyebrow'>Panels (stacked top→bottom)</div>", margin=0),
            self.panel_select,
            pn.pane.HTML("<div class='eyebrow'>Figure width</div>", margin=0),
            self.width_select,
            self._downloads(),
            title="Composite figure", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card"],
        )
        preview = self.panel(
            lambda: self._preview(), self.panel_select, self.width_select, *sig, rv,
            title="Preview",
        )
        return pn.Column(controls, preview, margin=0, sizing_mode="stretch_width",
                         css_classes=["qcm-page-figure"])
