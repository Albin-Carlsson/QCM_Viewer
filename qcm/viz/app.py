"""The QCM viewer Panel application.

Design goals: read like one experiment, not nine charts. Time is shown in
elapsed seconds everywhere; controls speak the same overtone language as the
plots; the canonical QCM-D figure is the hero; and the workflow is split into
Overview / Sweep inspector / Data tabs.
"""
from __future__ import annotations

import io
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import holoviews as hv
import panel as pn
import polars as pl

from qcm.run import open_run

from . import plots, science
from .theme import ACCENT, HEADER_BG, QUANTITIES, quantity

pn.extension("tabulator", sizing_mode="stretch_width", notifications=True)
pn.config.loading_indicator = True
hv.extension("bokeh")

_QUANTITY_OPTIONS = {q.label: key for key, q in QUANTITIES.items()}
_US = 1_000_000  # microseconds per second


class QCMViewer:
    def __init__(self, run_path: str | Path):
        self.run = open_run(run_path)
        self.state = self.run.load_view_state()
        self.groups = self.run.groups or [0]
        self.orders = self.run.overtone_orders()
        self._t0_us = self.run.time_start
        self._span_s = max((self.run.time_end - self.run.time_start) / _US, 1e-6)

        self._read_index()
        self._build_controls()
        self._build_exports()

    # ------------------------------------------------------------------ setup
    def _read_index(self) -> None:
        try:
            idx = self.run.sweep_index()
            self._fmin = float(idx["frequency_min"].min())
            self._fmax = float(idx["frequency_max"].max())
            self._seq_min = int(idx["sequence"].min())
            self._seq_max = int(idx["sequence"].max())
            self._n_sweeps = int(idx["sequence"].n_unique())
        except Exception:
            self._fmin, self._fmax = 0.0, 1.0
            self._seq_min = self._seq_max = self._n_sweeps = 0

    def _build_controls(self) -> None:
        group_options = {f"n={self.orders.get(g, 1)} (group {g})": str(g) for g in self.groups}
        default_groups = [str(g) for g in self.state.get("groups", self.groups) if g in self.groups]
        self.group_select = pn.widgets.MultiChoice(
            name="Overtones", options=group_options,
            value=default_groups or [str(g) for g in self.groups], solid=False,
        )
        self.quantity_select = pn.widgets.Select(
            name="Explore quantity", options=_QUANTITY_OPTIONS,
            value=self.state.get("quantity", "sauerbrey_mass"),
        )
        self.orders_text = pn.widgets.TextInput(
            name="Overtone orders (group:n)",
            value=self.state.get("orders_text", ", ".join(f"g{g}:n={n}" for g, n in sorted(self.orders.items()))),
        )

        step = max(self._span_s / 1000, 1e-6)
        self.t_range = pn.widgets.EditableRangeSlider(
            name="Visible / selected time (s)", start=0.0, end=self._span_s,
            value=tuple(self.state.get("t_range_s", [0.0, self._span_s])), step=step, format="0.00",
        )
        self.baseline_range = pn.widgets.EditableRangeSlider(
            name="Baseline window (s)", start=0.0, end=self._span_s,
            value=tuple(self.state.get("baseline_s", [0.0, self._span_s * 0.1])), step=step, format="0.00",
        )
        self.use_selection_as_baseline = pn.widgets.Button(
            name="Set baseline = current selection", button_type="default", icon="anchor",
        )
        self.frequency_band = pn.widgets.RangeSlider(
            name="Frequency band (Hz)", start=self._fmin, end=self._fmax,
            value=tuple(self.state.get("frequency_band", [self._fmin, self._fmax])),
            step=max((self._fmax - self._fmin) / 1000, 1e-9),
        )

        self.sequence = pn.widgets.IntSlider(
            name="Sweep sequence", start=self._seq_min, end=max(self._seq_max, self._seq_min),
            value=int(self.state.get("sequence", self._seq_min)), step=1,
        )
        self.sweep_mode = pn.widgets.RadioButtonGroup(
            name="Sweep view", options=["all groups", "single group"],
            value=self.state.get("sweep_mode", "all groups"), button_type="primary",
        )
        self.group_for_single = pn.widgets.Select(
            name="Single sweep group", options={f"n={self.orders.get(g, 1)} (group {g})": str(g) for g in self.groups},
            value=str(self.state.get("single_group", self.groups[0])),
        )

        self.annotation_label = pn.widgets.TextInput(name="Annotation label", placeholder="binding / rinse / artifact")
        self.annotation_type = pn.widgets.Select(
            name="Annotation type",
            options=["reference_region", "range", "event", "excluded_region"], value="reference_region",
        )
        self.annotate_button = pn.widgets.Button(name="Add annotation", button_type="primary", icon="plus")
        self.save_state_button = pn.widgets.Button(name="Save workspace", button_type="success", icon="device-floppy")

        self._ann_version = pn.widgets.IntInput(value=0, visible=False)
        self.status = pn.pane.Alert("Ready.", alert_type="light")

        self.annotate_button.on_click(self._add_annotation)
        self.save_state_button.on_click(self._save_state)
        self.use_selection_as_baseline.on_click(self._sync_baseline_to_selection)

    def _build_exports(self) -> None:
        self.export_data_dl = pn.widgets.FileDownload(
            label="⬇ Selected data (.parquet)", filename="qcm_data.parquet",
            callback=self._data_file, button_type="default",
        )
        self.export_plot_dl = pn.widgets.FileDownload(
            label="⬇ Timeline figure (.html)", filename="qcm_timeline.html",
            callback=self._plot_file, button_type="default",
        )
        self.export_nb_dl = pn.widgets.FileDownload(
            label="⬇ Reproducible notebook (.ipynb)", filename="qcm_view.ipynb",
            callback=self._notebook_file, button_type="default",
        )

    # -------------------------------------------------------------- selectors
    def selected_groups(self) -> list[int]:
        groups = [int(v) for v in self.group_select.value]
        return groups or [self.groups[0]]

    def _orders(self) -> dict[int, int]:
        parsed: dict[int, int] = {}
        for chunk in self.orders_text.value.replace(";", ",").split(","):
            if ":" not in chunk:
                continue
            g, _, n = chunk.partition(":")
            try:
                parsed[int(g.strip().lstrip("g"))] = max(1, int(n.strip().lstrip("n=")))
            except ValueError:
                continue
        return {g: parsed.get(g, self.orders.get(g, 1)) for g in self.groups}

    def _t_us(self) -> tuple[int, int]:
        s0, s1 = self.t_range.value
        return int(self._t0_us + s0 * _US), int(self._t0_us + s1 * _US)

    def _baseline_us(self) -> tuple[int, int]:
        b0, b1 = self.baseline_range.value
        return int(self._t0_us + b0 * _US), int(self._t0_us + b1 * _US)

    def _add_elapsed(self, df: pl.DataFrame) -> pl.DataFrame:
        if df.is_empty() or "timestamp" not in df.columns:
            return df.with_columns(pl.lit(0.0).alias(plots.X)) if not df.is_empty() else df
        return df.with_columns(((pl.col("timestamp") - self._t0_us) / _US).alias(plots.X))

    # ------------------------------------------------------------ data access
    def _value_df(self, quantity_key: str) -> tuple[pl.DataFrame, float]:
        t0, t1 = self._t_us()
        groups = self.selected_groups()
        q = quantity(quantity_key)
        sources = list(q.sources)
        tic = time.perf_counter()
        main = self.run.timeline(sources, t0=t0, t1=t1, groups=groups)
        baseline = None
        if q.referenced:
            b0, b1 = self._baseline_us()
            baseline = self.run.timeline(sources, t0=b0, t1=b1, groups=groups, level="raw")
        value_df = science.compute(main, quantity_key, self._orders(), baseline_df=baseline)
        return self._add_elapsed(value_df), (time.perf_counter() - tic) * 1000

    def _annotation_spans(self) -> list:
        anns = self._annotations()
        out = []
        for a in anns:
            x0 = (a.t0 - self._t0_us) / _US
            x1 = ((a.t1 or a.t0) - self._t0_us) / _US
            out.append((a.type, x0, x1))
        return out

    # ------------------------------------------------------------------ plots
    def hero_plot(self):
        try:
            norm_df, _ = self._value_df("delta_f_norm")
            d_df, _ = self._value_df("delta_D")
            b0, b1 = self.baseline_range.value
            title = "QCM-D — Δf/n (left, solid) · ΔD (right, dashed) · referenced to baseline"
            plot = plots.dual_axis_qcmd(norm_df, d_df, self.selected_groups(), self._orders(), title, baseline=(b0, b1))
            self._attach_tap(plot)
            return plot
        except Exception as e:  # pragma: no cover - UI guard
            return pn.pane.Alert(f"QCM-D plot failed: {e}", alert_type="danger")

    def explore_plot(self):
        try:
            key = self.quantity_select.value
            value_df, elapsed = self._value_df(key)
            q = quantity(key)
            title = f"{q.label} ({q.unit}) — {value_df.height} pts · {elapsed:.0f} ms"
            baseline = tuple(self.baseline_range.value) if q.referenced else None
            plot = plots.timeline(
                value_df, q, self.selected_groups(), self._orders(), title,
                annotation_spans=self._annotation_spans(), baseline=baseline,
            )
            self._attach_tap(plot)
            return plot
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"Explore timeline failed: {e}", alert_type="danger")

    def df_plot(self):
        try:
            norm_df, _ = self._value_df("delta_f_norm")
            d_df, _ = self._value_df("delta_D")
            return plots.df_fingerprint(norm_df, d_df, self.selected_groups(), self._orders())
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"Df plot failed: {e}", alert_type="danger")

    def waterfall_plot(self):
        try:
            t0, t1 = self._t_us()
            f0, f1 = self.frequency_band.value
            df = self.run.frequency_band(
                f0=f0, f1=f1, t0=t0, t1=t1, groups=self.selected_groups(),
                columns=["timestamp", "group", "frequency", "conductance"],
            )
            return plots.waterfall(self._add_elapsed(df), "Conductance waterfall — selected groups & band")
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"Waterfall failed: {e}", alert_type="danger")

    def _sweep_df(self) -> pl.DataFrame:
        groups = self.selected_groups() if self.sweep_mode.value == "all groups" else [int(self.group_for_single.value)]
        return self.run.sweeps_at(sequence=self.sequence.value, groups=groups)

    def sweep_plot(self):
        try:
            return plots.sweep_curves(self._sweep_df(), f"Resonance curves at sequence {self.sequence.value}")
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"Sweep failed: {e}", alert_type="danger")

    def iq_plot(self):
        try:
            return plots.iq_scatter(self._sweep_df(), f"I/Q at sequence {self.sequence.value}")
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"I/Q failed: {e}", alert_type="danger")

    def stats_table(self):
        try:
            key = self.quantity_select.value
            value_df, _ = self._value_df(key)
            stats = science.summary_stats(value_df.select(["timestamp", "group", "value"]))
            if stats.is_empty():
                return pn.pane.Markdown("No statistics for the selected region.")
            q = quantity(key)
            stats = stats.with_columns(pl.lit(q.unit or "—").alias("unit"))
            return pn.widgets.Tabulator(
                stats.to_pandas(), height=240, layout="fit_data_stretch", show_index=False,
            )
        except Exception as e:  # pragma: no cover
            return pn.pane.Alert(f"Stats failed: {e}", alert_type="danger")

    def annotations_table(self):
        anns = self._annotations()
        if not anns:
            return pn.pane.Markdown(
                "_No annotations yet._ Select a region on a timeline, choose a type, and **Add annotation**. "
                "A `reference_region` also becomes the baseline window."
            )
        full = pl.DataFrame([a.model_dump() for a in anns])
        df = full.select([c for c in ["id", "type", "label", "t0", "t1", "groups"] if c in full.columns])
        table = pn.widgets.Tabulator(
            df.to_pandas(), height=240, show_index=False, layout="fit_data_stretch",
            buttons={"delete": '<i class="fa fa-trash"></i>'},
        )
        table.on_click(self._on_annotation_action)
        return table

    # ------------------------------------------------------- tap interaction
    def _attach_tap(self, obj) -> None:
        try:
            tap = hv.streams.SingleTap(source=obj, transient=True)
            tap.add_subscriber(lambda x=None, y=None: self._jump_to_seconds(x))
        except Exception:
            pass

    def _jump_to_seconds(self, x) -> None:
        if x is None:
            return
        try:
            ts = int(self._t0_us + float(x) * _US)
            idx = self.run.sweep_index()
            nearest = idx.with_columns((pl.col("timestamp") - ts).abs().alias("_d")).sort("_d")
            if not nearest.is_empty():
                self.sequence.value = int(nearest["sequence"][0])
                self._notify(f"Loaded sweep {self.sequence.value} at t={float(x):.2f} s")
        except Exception:
            pass

    # --------------------------------------------------------- annotations/io
    def _annotations(self):
        _ = self._ann_version.value  # reactive dependency
        return self.run.annotations()

    def _add_annotation(self, _event=None) -> None:
        t0, t1 = self._t_us()
        f0, f1 = self.frequency_band.value
        label = self.annotation_label.value or self.annotation_type.value
        ann = self.run.add_annotation(
            type=self.annotation_type.value, t0=t0, t1=t1, label=label,
            groups=self.selected_groups(), frequency_range=(float(f0), float(f1)),
        )
        if self.annotation_type.value == "reference_region":
            self.baseline_range.value = tuple(self.t_range.value)  # unify baseline concepts
        self._ann_version.value += 1
        self._notify(f"Added annotation “{label}”.", "success")

    def _on_annotation_action(self, event) -> None:
        if getattr(event, "column", None) != "delete":
            return
        try:
            anns = self._annotations()
            ann_id = anns[event.row].id
            self.run.remove_annotation(ann_id)
            self._ann_version.value += 1
            self._notify(f"Deleted annotation {ann_id}.", "warning")
        except Exception as e:
            self._notify(f"Delete failed: {e}", "error")

    def _sync_baseline_to_selection(self, _event=None) -> None:
        self.baseline_range.value = tuple(self.t_range.value)
        self._notify("Baseline window set to current selection.", "success")

    def _notify(self, msg: str, kind: str = "info") -> None:
        self.status.object = msg
        notifications = pn.state.notifications
        if notifications is not None:
            getattr(notifications, kind, notifications.info)(msg, duration=4000)

    def _current_state(self) -> dict[str, Any]:
        return {
            "groups": self.selected_groups(),
            "quantity": self.quantity_select.value,
            "t_range_s": list(self.t_range.value),
            "baseline_s": list(self.baseline_range.value),
            "orders_text": self.orders_text.value,
            "sequence": self.sequence.value,
            "single_group": int(self.group_for_single.value),
            "sweep_mode": self.sweep_mode.value,
            "frequency_band": list(self.frequency_band.value),
        }

    def _save_state(self, _event=None) -> None:
        out = self.run.save_view_state(self._current_state())
        self._notify(f"Saved workspace → {out.name}", "success")

    # ----------------------------------------------------------- export files
    def _data_file(self):
        t0, t1 = self._t_us()
        cols = [c for c in ["fit_center", "fit_fwhm", "fit_gamma"] if c in self.run.columns]
        df = self.run.timeline(cols, t0=t0, t1=t1, groups=self.selected_groups(), level="raw")
        buf = io.BytesIO()
        df.write_parquet(buf)
        buf.seek(0)
        return buf

    def _plot_file(self):
        key = self.quantity_select.value
        value_df, _ = self._value_df(key)
        q = quantity(key)
        plot = plots.timeline(value_df, q, self.selected_groups(), self._orders(), f"{q.label} ({q.unit})")
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        hv.save(plot, tmp.name)
        return open(tmp.name, "rb")

    def _notebook_file(self):
        t0, t1 = self._t_us()
        tmp = tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False)
        self.run.to_notebook(tmp.name, columns=["fit_center", "fit_fwhm"], t0=t0, t1=t1, groups=self.selected_groups())
        return open(tmp.name, "rb")

    # ----------------------------------------------------------------- layout
    def _orders_readout(self, *_):
        parsed = self._orders()
        return pn.pane.Markdown("✓ " + " · ".join(f"g{g}→n={n}" for g, n in sorted(parsed.items())))

    def _sweep_readout(self, *_):
        seq = self.sequence.value
        t = ""
        try:
            idx = self.run.sweep_index()
            row = idx.filter(pl.col("sequence") == seq)
            if not row.is_empty():
                t = f" · t={(row['timestamp'][0] - self._t0_us) / _US:.2f} s"
        except Exception:
            pass
        pos = (seq - self._seq_min + 1) if self._n_sweeps else 0
        return pn.pane.Markdown(f"**Sweep {seq}** ({pos}/{self._n_sweeps}){t} · _click any timeline point to jump here_")

    def _header(self) -> pn.pane.Markdown:
        overtones = ", ".join(f"n={n}" for _, n in sorted(self.orders.items()))
        rows = self.run.manifest.metadata.get("rows", "?")
        return pn.pane.Markdown(
            f"## `{self.run.id}`\n"
            f"**{self._span_s:.1f} s**  ·  **{len(self.groups)} overtones** ({overtones})  ·  "
            f"**{self._n_sweeps}** sweeps  ·  {rows} rows  ·  _baseline-referenced & overtone-normalized_",
        )

    def _sidebar(self):
        signal = pn.Card(
            self.group_select, self.orders_text, pn.bind(self._orders_readout, self.orders_text),
            self.quantity_select, title="Signal", collapsed=False,
        )
        timing = pn.Card(
            self.t_range, self.baseline_range, self.use_selection_as_baseline, self.frequency_band,
            title="Time & baseline", collapsed=False,
        )
        sweep = pn.Card(
            self.sequence, pn.bind(self._sweep_readout, self.sequence), self.sweep_mode, self.group_for_single,
            title="Sweep inspector", collapsed=True,
        )
        annotate = pn.Card(
            self.annotation_type, self.annotation_label, self.annotate_button,
            pn.layout.Divider(), self.save_state_button,
            self.export_data_dl, self.export_plot_dl, self.export_nb_dl,
            title="Annotate & export", collapsed=True,
        )
        return pn.Column(signal, timing, sweep, annotate, self.status)

    def _card(self, fn, *widgets, title: str):
        return pn.Card(pn.bind(lambda *_: fn(), *widgets), title=title, collapsible=False, margin=6)

    def _tabs(self):
        signal_widgets = (self.group_select, self.orders_text, self.t_range, self.baseline_range)
        overview = pn.Column(
            self._card(self.hero_plot, *signal_widgets, title="QCM-D · Δf/n & ΔD"),
            pn.Row(
                self._card(self.explore_plot, *signal_widgets, self.quantity_select, self._ann_version, title="Explore timeline"),
                self._card(self.df_plot, *signal_widgets, title="Df fingerprint"),
            ),
        )
        inspector = pn.Column(
            pn.Row(
                self._card(self.sweep_plot, self.sequence, self.group_select, self.group_for_single, self.sweep_mode, title="Resonance curves (G/B)"),
                self._card(self.iq_plot, self.sequence, self.group_select, self.group_for_single, self.sweep_mode, title="I/Q scatter"),
            ),
            self._card(self.waterfall_plot, *signal_widgets, self.frequency_band, title="Conductance waterfall"),
        )
        data = pn.Row(
            self._card(self.stats_table, *signal_widgets, self.quantity_select, title="Region statistics"),
            self._card(self.annotations_table, self._ann_version, title="Annotations"),
        )
        return pn.Tabs(
            ("Overview", overview), ("Sweep inspector", inspector), ("Data & annotations", data),
            dynamic=False,
        )

    def view(self):
        template = pn.template.FastListTemplate(
            title="QCM Viewer", theme="dark", theme_toggle=True,
            accent_base_color=ACCENT, header_background=HEADER_BG,
            sidebar=[self._sidebar()], main=[pn.Column(self._header(), self._tabs())],
            main_layout=None,
        )
        return template


def app(run_path: str | None = None):
    run_path = run_path or (sys.argv[-1] if len(sys.argv) > 1 else ".")
    return QCMViewer(run_path).view()
