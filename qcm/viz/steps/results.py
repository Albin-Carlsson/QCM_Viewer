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

import holoviews as hv
import panel as pn
import polars as pl

from .. import echem, plots, science
from ..components import icon_stat, stat_grid
from ..theme import (
    CHARGE_EPS_C,
    COMPACT_PLOT_HEIGHT,
    FARADAY_CONSTANT,
    NG_PER_CM2_TO_G,
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
        cycles = echem.cycle_values(self._cycle_source()) if self.data.has_echem() else []
        c_lo = cycles[0] if cycles else 0
        c_hi = cycles[-1] if cycles else 0
        self._has_cycles = len(cycles) > 1

        self.technique_select = pn.widgets.RadioButtonGroup(
            label="", options={"Auto": "auto", "CV": "cv", "CP": "cp"},
            value="auto", button_type="default", sizing_mode="stretch_width",
            css_classes=["echem-technique-toggle"],
        )
        self.cycle_mode = pn.widgets.RadioButtonGroup(
            label="", options={"All": "all", "Single": "individual", "Range": "range"},
            value="all", button_type="default", sizing_mode="stretch_width",
            css_classes=["echem-cycle-mode"],
        )
        self.cycle_select = pn.widgets.IntSlider(
            label="Cycle", start=c_lo, end=max(c_hi, c_lo), value=c_lo, step=1,
            sizing_mode="stretch_width",
        )
        self.cycle_range = pn.widgets.IntRangeSlider(
            label="Cycle range", start=c_lo, end=max(c_hi, c_lo), value=(c_lo, max(c_hi, c_lo)),
            step=1, sizing_mode="stretch_width",
        )
        self.cycle_zero = pn.widgets.Checkbox(label="Zero f/D at cycle start", value=True)

    # --- inputs ------------------------------------------------------------
    @property
    def _cycle_inputs(self) -> tuple:
        return (self.technique_select, self.cycle_mode, self.cycle_select, self.cycle_range,
                self.cycle_zero)

    def _technique(self) -> str:
        choice = self.technique_select.value
        if choice in ("cv", "cp"):
            return choice
        return echem.detect_technique(self.data.echem_waveform())

    # --- multi-run helpers -------------------------------------------------
    def _runset(self):
        return getattr(self.data, "runset", None)

    def _is_multi(self) -> bool:
        rs = self._runset()
        return rs is not None and rs.is_multi

    def _named_waveforms(self) -> list[tuple[str, pl.DataFrame]]:
        """``(label, raw waveform)`` per run, in run-set order for colour slots."""
        rs = self._runset()
        labels = rs.labels()
        return [(labels[i], d.echem_waveform()) for i, d in enumerate(rs.runs)]

    def _cycle_kwargs(self) -> dict:
        return dict(
            technique=self.technique_select.value,
            mode=self.cycle_mode.value,
            cycle=int(self.cycle_select.value),
            lo=int(self.cycle_range.value[0]),
            hi=int(self.cycle_range.value[1]),
        )

    def _cycle_source_for(self, data) -> pl.DataFrame:
        """Waveform with cycles populated for one run — CP cycles from current sign."""
        wf = data.echem_waveform()
        if wf.is_empty():
            return wf
        if echem.detect_technique(wf) == "cp":
            return echem.derive_cycles(wf)
        return wf

    def _cycle_source(self) -> pl.DataFrame:
        return self._cycle_source_for(self.data)

    def _selected_waveform_for(self, data) -> pl.DataFrame:
        wf = data.echem_waveform()
        if wf.is_empty():
            return wf
        if echem.resolve_technique(wf, self.technique_select.value) == "cp":
            wf = echem.derive_cycles(wf)
        wf = echem.filter_cycles(
            wf, self.cycle_mode.value,
            cycle=int(self.cycle_select.value),
            lo=int(self.cycle_range.value[0]),
            hi=int(self.cycle_range.value[1]),
        )
        if _I in wf.columns:
            area = self.controls.state().params.area_cm2
            wf = wf.with_columns((pl.col(_I) / area).alias(_J))
        return wf

    def _selected_waveform(self) -> pl.DataFrame:
        return self._selected_waveform_for(self.data)

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

    def _sauerbrey_cell(self, state) -> str | None:
        """Validity tile: overtone collapse + viscoelastic ratio over the range."""
        try:
            check = science.sauerbrey_check(self.data.region_summary(state))
        except Exception:
            return None
        if check is None:
            return None
        tone = {"ok": "success", "caution": "warning", "poor": "danger"}[check["verdict"]]
        label = {"ok": "Valid", "caution": "Caution", "poor": "Doubtful"}[check["verdict"]]
        bits = []
        if check["ratio"] is not None:
            bits.append(f"ΔD/−Δf {check['ratio']:.2f} ×10⁻⁶/Hz")
        if check["spread_pct"] is not None:
            bits.append(f"overtone spread {check['spread_pct']:.0f}%")
        return icon_stat("Sauerbrey check", label, icon="ratio", tone=tone,
                         caption=" · ".join(bits) or check["detail"])

    # --- headline cards ----------------------------------------------------
    def summary_cards(self):
        try:
            state = self.controls.state()
            m = self._means(state)
            cells = [
                icon_stat("Mean Δf/n", self._fmt(m.get("df_n"), 2, " Hz"), icon="frequency"),
                icon_stat("Mean ΔD", self._fmt(m.get("dD"), 3, " ×10⁻⁶"), icon="dissipation"),
                icon_stat("Mass (Sauerbrey)", self._fmt(m.get("mass"), 1, " ng/cm²"), icon="mass"),
            ]
            validity = self._sauerbrey_cell(state)
            if validity is not None:
                cells.append(validity)
            if self.data.has_echem():
                charge = m.get("charge")
                jdens = m.get("jdens")
                cells += [
                    icon_stat("Charge", self._fmt(None if charge is None else charge * 1e3, 3, " mC"), icon="charge"),
                    icon_stat("MPE", self._fmt(m.get("mpe"), 1, " g/mol"), icon="mpe"),
                    icon_stat("Current density", self._fmt(None if jdens is None else jdens * 1e3, 2, " mA/cm²"), icon="density"),
                ]
            return stat_grid(cells)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Summary failed: {exc}", alert_type="danger")

    def _comparison_frame(self) -> pl.DataFrame:
        """Per-run × per-channel summary frame shared by the table and its CSV export."""
        rs = self._runset()
        if rs is None or not rs.is_multi:
            return pl.DataFrame()
        summary = rs.overlay_region_summary(self.controls.state())
        if summary.is_empty():
            return summary
        if "run_slot" in summary.columns:
            summary = summary.drop("run_slot")
        order = ["run", "group", "n", "df_n", "dD", "mass", "Q", "dD_per_df"]
        return summary.select([c for c in order if c in summary.columns])

    def per_channel_comparison_table(self):
        """Per-run × per-channel headline summary over the analysis range.

        Only shown for a multi-run set; gives the cross-run per-channel
        comparison alongside the active-run KPI tiles.
        """
        try:
            summary = self._comparison_frame()
            if summary.is_empty():
                return self.empty_state("No data in the current analysis range.")
            order = ["run", "group", "n", "df_n", "dD", "mass", "Q", "dD_per_df"]
            return self._summary_tabulator(summary, order)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Comparison table failed: {exc}", alert_type="danger")

    # --- technique metadata ------------------------------------------------
    def metadata_card(self):
        try:
            if not self.data.has_echem():
                return self.empty_state("This run has no electrochemistry channel.")
            technique = self._technique()
            area = self.controls.state().params.area_cm2
            meta = echem.metadata(self.data.echem_waveform(), technique, area)
            if technique == "cp":
                rows = [
                    ("Technique", "Chronopotentiometry"),
                    ("Applied current", self._fmt(meta.get("applied_current", 0) * 1e6, 2, " µA")),
                    ("Applied current density", self._fmt(meta.get("applied_current_density", 0) * 1e6, 2, " µA/cm²")),
                    ("Step duration (median)", self._fmt(meta.get("step_duration"), 2, " s")),
                    ("Number of steps", self._fmt(meta.get("n_steps"), 0)),
                ]
            else:
                rows = [
                    ("Technique", "Cyclic voltammetry"),
                    ("E start", self._fmt(meta.get("e_start"), 3, " V")),
                    ("E vertex 1", self._fmt(meta.get("e_vertex1"), 3, " V")),
                    ("E vertex 2", self._fmt(meta.get("e_vertex2"), 3, " V")),
                    ("Scan rate", self._fmt((meta.get("scan_rate") or 0) * 1000, 1, " mV/s")),
                    ("Number of scans", self._fmt(meta.get("n_scans"), 0)),
                ]
            table = pl.DataFrame(rows, schema=["Property", "Value"], orient="row")
            return pn.widgets.Tabulator(
                table.to_pandas(), height=212, layout="fit_columns",
                widths={"Property": 96}, show_index=False,
                sizing_mode="stretch_width", disabled=True,
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
    def _augment_with_mpe(self, stats: pl.DataFrame, data=None, wf=None) -> pl.DataFrame:
        """Add per-cycle mass accumulation and MPE columns for one run.

        MPE is the Faraday slope of areal-mass change vs charge over an interval,
        ``F · Δm(g) / Δq``, using the run's configured electrode area. The
        whole-cycle value is always added; for CP, the plating and stripping
        half-cycles (from the current-sign markers) each get their own static
        MPE column. ``data``/``wf`` default to the active run's selected waveform;
        pass a specific run's data + waveform to augment another run (or the full,
        unfiltered waveform for the all-cycles trend).
        """
        try:
            if stats.is_empty() or "cycle" not in stats.columns:
                return stats
            data = data or self.data
            state = self.controls.state()
            area = state.params.area_cm2
            full = replace(state, t_range_s=(0.0, float(data.info.span_s)))
            mdf, _ = data.value_df(full, "sauerbrey_mass", "time")
            if mdf.is_empty():
                return stats
            mass_ts = mdf.group_by("timestamp").agg(pl.col("value").mean().alias("_mass"))
            wf = self._selected_waveform_for(data) if wf is None else wf
            if wf.is_empty() or _Q not in wf.columns or "cycle" not in wf.columns:
                return stats
            has_half = "_is_plate" in wf.columns
            cols = ["timestamp", pl.col("cycle").cast(pl.Int64), _Q]
            if has_half:
                cols.append("_is_plate")
            joined = wf.select(cols).join(mass_ts, on="timestamp", how="inner")
            if joined.is_empty():
                return stats

            dm = (pl.col("_mass").sort_by("timestamp").last()
                  - pl.col("_mass").sort_by("timestamp").first()).alias("_dm_ng")
            dq = (pl.col(_Q).sort_by("timestamp").last()
                  - pl.col(_Q).sort_by("timestamp").first()).alias("_dq")
            mpe = (
                pl.when(pl.col("_dq").abs() > CHARGE_EPS_C)
                .then(-FARADAY_CONSTANT * (pl.col("_dm_ng") * area * NG_PER_CM2_TO_G) / pl.col("_dq"))
                .otherwise(None)
                .round(2)
            )

            per = (
                joined.group_by("cycle").agg([dm, dq])
                .with_columns(
                    pl.col("_dm_ng").round(3).alias("mass_accum_ng_cm2"),
                    mpe.alias("MPE_g_per_mol"),
                )
                .select(["cycle", "mass_accum_ng_cm2", "MPE_g_per_mol"])
            )
            out = stats.join(per, on="cycle", how="left")

            if has_half:
                out = out.join(echem.half_cycle_mpe(joined, area), on="cycle", how="left")
            return out
        except Exception:
            return stats

    def _run_augmented_stats(self, data) -> pl.DataFrame:
        """All-cycle per-cycle stats (CE + whole/half-cycle MPE + mass) for one run.

        Computed over the full waveform so cycle numbers stay stable; callers
        filter the rows afterwards (the table) or use them whole (the trend).
        """
        wf = data.echem_waveform()
        if wf.is_empty():
            return pl.DataFrame()
        tech = echem.resolve_technique(wf, self.technique_select.value)
        stats = echem.cycle_stats(wf, tech)
        if stats.is_empty():
            return stats
        return self._augment_with_mpe(stats, data=data, wf=self._cycle_source_for(data))

    def _multi_augmented(self, *, filtered: bool) -> pl.DataFrame:
        """Per-run augmented cycle stats stacked with ``run``/``run_slot``.

        ``filtered`` applies the shared cycle selection to the stats rows (for the
        table); the trend passes ``filtered=False`` to show every cycle.
        """
        rs = self._runset()
        runs = rs.runs if rs is not None else [self.data]
        labels = rs.labels() if rs is not None else [self.data.info.run_id]
        frames: list[pl.DataFrame] = []
        for slot, d in enumerate(runs):
            stats = self._run_augmented_stats(d)
            if stats.is_empty():
                continue
            if filtered:
                stats = echem.filter_cycles(
                    stats, self.cycle_mode.value,
                    cycle=int(self.cycle_select.value),
                    lo=int(self.cycle_range.value[0]), hi=int(self.cycle_range.value[1]),
                )
                if stats.is_empty():
                    continue
            frames.append(stats.with_columns(
                pl.lit(labels[slot]).alias("run"),
                pl.lit(slot, dtype=pl.Int32).alias("run_slot"),
            ))
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed")

    @staticmethod
    def _robust_ylim(frame: pl.DataFrame, cols, *, include=None, pct=(2, 98)):
        """A y-range from a low/high percentile (+pad) so a few outlier points or
        a bad cycle can't compress the interesting band to a sliver.

        ``pct`` widens (e.g. ``(1, 99)``) when the headline trace's true peaks
        matter (CV currents) and tightens for noisy derived signals.
        """
        import numpy as np
        vals = []
        for c in cols:
            if c in frame.columns:
                vals.append(frame[c].drop_nulls().to_numpy())
        vals = np.concatenate(vals) if vals else np.array([])
        vals = vals[np.isfinite(vals)]
        if vals.size < 2:
            return None
        lo, hi = (float(v) for v in np.percentile(vals, list(pct)))
        if include is not None:
            lo, hi = min(lo, float(include)), max(hi, float(include))
        if hi <= lo:
            return None
        pad = (hi - lo) * 0.1 or 1.0
        return (lo - pad, hi + pad)

    def _with_ylim(self, plot, frame: pl.DataFrame, cols, *, pct=(2, 98)):
        """Apply a robust y-range to a built overlay (no-op if it can't be set)."""
        ylim = self._robust_ylim(frame, cols, pct=pct)
        if ylim is None:
            return plot
        try:
            return plot.opts(hv.opts.Overlay(ylim=ylim))
        except Exception:
            return plot

    def mpe_trend_plot(self, height: int = PLOT_HEIGHT):
        """MPE (plating + stripping) vs cycle number across runs, with M/z target."""
        try:
            frame = self._multi_augmented(filtered=False)
            if frame.is_empty() or "MPE_plating_g_per_mol" not in frame.columns:
                return self.empty_state("Per-cycle MPE needs a CP run with plating/stripping cycles.")
            target = self.controls.state().params.target_mpe
            ylim = self._robust_ylim(
                frame, ["MPE_plating_g_per_mol", "MPE_stripping_g_per_mol"], include=target)
            plot = plots.cycle_trend(
                frame,
                series=[("MPE_plating_g_per_mol", "plating", "circle"),
                        ("MPE_stripping_g_per_mol", "stripping", "triangle")],
                ylabel="MPE (g/mol)", title="MPE per cycle", target=target, ylim=ylim, height=height,
            )
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"MPE trend failed: {exc}", alert_type="danger")

    def ce_trend_plot(self, height: int = PLOT_HEIGHT):
        """Coulombic efficiency vs cycle number across runs.

        Reports charge-based CE = |Q_strip / Q_plate| × 100 — the standard
        plating/stripping efficiency — and falls back to the time ratio
        (t_strip / t_plate) only when no charge channel is present.
        """
        try:
            frame = self._multi_augmented(filtered=False)
            if frame.is_empty():
                return self.empty_state("Coulombic efficiency needs a CP run.")
            if "CE_charge" in frame.columns and frame["CE_charge"].drop_nulls().len():
                src, basis = "CE_charge", "charge"
            elif "CE_time" in frame.columns:
                src, basis = "CE_time", "time"
            else:
                return self.empty_state("Coulombic efficiency needs a CP run.")
            frame = frame.with_columns((pl.col(src) * 100.0).alias("CE_pct"))
            ylim = self._robust_ylim(frame, ["CE_pct"], include=100.0)
            plot = plots.cycle_trend(
                frame, series=[("CE_pct", "CE", "x")],
                ylabel="Coulombic efficiency (%)",
                title=f"CE per cycle ({basis}-based)", ylim=ylim, height=height,
            )
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"CE trend failed: {exc}", alert_type="danger")

    def _run_cycle_rel(self, data, state, q, zero: bool) -> pl.DataFrame:
        """Cycle-relative ``[timestamp, cycle, t_rel_s, value]`` for one run over
        the shared cycle selection, or an empty frame when it has no cycles."""
        full = replace(state, t_range_s=(0.0, float(data.info.span_s)))
        vdf, _ = data.value_df(full, state.quantity, "time")
        cyc = self._cycle_source_for(data).select(["timestamp", "cycle"]).unique(subset=["timestamp"])
        if vdf.is_empty() or cyc.is_empty() or "cycle" not in cyc.columns:
            return pl.DataFrame()
        joined = vdf.join(cyc, on="timestamp", how="inner")
        joined = echem.filter_cycles(
            joined, self.cycle_mode.value,
            cycle=int(self.cycle_select.value),
            lo=int(self.cycle_range.value[0]), hi=int(self.cycle_range.value[1]),
        )
        if state.groups:
            joined = joined.filter(pl.col("group") == state.groups[0])
        return echem.cycle_relative(joined.select(["timestamp", "cycle", "value"]), zero=zero)

    def cycle_overlay_plot(self, height: int = PLOT_HEIGHT):
        """Overlay the selected cycles of the chosen quantity on a common origin."""
        try:
            if not self.data.has_echem():
                return self.empty_state("No electrochemistry channel.")
            state = self.controls.state()
            q = quantity(state.quantity)
            # Zeroing only makes sense for shift-like resonance quantities, never
            # for an absolute signal such as potential.
            zero = bool(self.cycle_zero.value) and q.kind in ("frequency", "dissipation", "mass")
            zsuffix = " · zeroed at start" if zero else ""

            if self._is_multi():
                frames = []
                for slot, d in enumerate(self._runset().runs):
                    rel = self._run_cycle_rel(d, state, q, zero)
                    if rel.is_empty():
                        continue
                    frames.append(rel.with_columns(
                        pl.lit(self._runset().labels()[slot]).alias("run"),
                        pl.lit(slot, dtype=pl.Int32).alias("run_slot"),
                    ))
                if not frames:
                    return self.empty_state("No cycles to overlay.")
                frame = pl.concat(frames, how="diagonal_relaxed")
                title = f"{q.label} per cycle · all runs{zsuffix}"
                plot = self._with_ylim(plots.cycle_overlay_runs(frame, q, title, height=height),
                                       frame, ["value"])
                return self.nearest_hover(self.force_plot_height(plot, height))

            rel = self._run_cycle_rel(self.data, state, q, zero)
            if rel.is_empty():
                return self.empty_state("No cycles to overlay.")
            title = f"{q.label} per cycle{zsuffix}"
            plot = self._with_ylim(plots.cycle_overlay(rel, q, title, height=height), rel, ["value"])
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Cycle overlay failed: {exc}", alert_type="danger")

    def _per_cycle_frame(self) -> pl.DataFrame:
        """Per-cycle stats frame shared by the table and its CSV export."""
        if not self.data.has_echem():
            return pl.DataFrame()
        if self._is_multi():
            stats = self._multi_augmented(filtered=True)
            if stats.is_empty():
                return stats
            # Lead with the run label; drop the colour-slot helper column.
            if "run_slot" in stats.columns:
                stats = stats.drop("run_slot")
            return stats.select(["run"] + [c for c in stats.columns if c != "run"])
        stats = echem.cycle_stats(self._selected_waveform(), self._technique())
        if stats.is_empty():
            return stats
        return self._augment_with_mpe(stats)

    # --- alignment check -----------------------------------------------------
    def _alignment_frame(self) -> pl.DataFrame:
        """``[t_s, mass, current]`` on the QCM time base over the full run."""
        if not self.data.has_echem():
            return pl.DataFrame()
        state = self.controls.state()
        full = replace(state, t_range_s=(0.0, float(self.data.info.span_s)))
        mdf, _ = self.data.value_df(full, "sauerbrey_mass", "time")
        wf = self.data.echem_waveform()
        if mdf.is_empty() or wf.is_empty() or _I not in wf.columns:
            return pl.DataFrame()
        mass = mdf.group_by("timestamp").agg(pl.col("value").mean().alias("mass"))
        joined = (
            wf.select(["timestamp", _I]).join(mass, on="timestamp", how="inner")
            .sort("timestamp")
        )
        if joined.is_empty():
            return joined
        return joined.with_columns(
            ((pl.col("timestamp") - self.data.info.t0_us) / 1e6).alias("t_s")
        ).select(["t_s", "mass", pl.col(_I).alias("current")]).drop_nulls()

    def alignment_check(self, height: int = COMPACT_PLOT_HEIGHT):
        """Visual + cross-correlation check that the PS stream is aligned.

        Faraday's law couples the mass rate to −current, so the two normalized
        traces should pulse together; the lag estimate quantifies any residual
        import offset and suggests the ``--ps-offset`` to fix it.
        """
        try:
            import numpy as np

            df = self._alignment_frame()
            if df.is_empty() or df.height < 8:
                return self.empty_state("Needs both a QCM mass signal and an EC current channel.")
            t = df["t_s"].to_numpy()
            mass = df["mass"].to_numpy()
            cur = df["current"].to_numpy()
            rate = np.gradient(mass, t)

            def _norm(v: np.ndarray) -> np.ndarray:
                lo, hi = np.nanpercentile(v, [2, 98])
                half = max((hi - lo) / 2.0, 1e-12)
                return np.clip((v - (lo + hi) / 2.0) / half, -1.5, 1.5)

            frame = pl.DataFrame({
                "t_s": t, "rate_norm": _norm(rate), "neg_current_norm": _norm(-cur),
            })
            plot = self.nearest_hover(self.force_plot_height(
                plots.alignment_overlay(frame, height=height), height))

            est = science.alignment_lag(df)
            dt = float(np.median(np.diff(t))) if t.size > 1 else 0.0
            if est is None or est["corr"] < 0.1:
                msg = ("<b>Lag estimate:</b> not enough correlated signal — judge "
                       "alignment visually from the overlay above.")
                tone = "warning"
            elif abs(est["lag_s"]) <= max(2 * dt, 1.0):
                msg = (f"<b>Aligned.</b> Residual lag {est['lag_s']:+.1f} s "
                       f"(within sampling resolution; correlation {est['corr']:.2f}).")
                tone = "info"
            else:
                msg = (f"<b>Possible misalignment:</b> EC features arrive "
                       f"{est['lag_s']:+.1f} s relative to the QCM response "
                       f"(correlation {est['corr']:.2f}). Re-import with "
                       f"<code>--ps-offset {-est['lag_s']:.1f}</code> to realign.")
                tone = "warning"
            readout = pn.pane.HTML(f"<div class='qcm-hint {tone}'>{msg}</div>",
                                   margin=0, sizing_mode="stretch_width")
            return pn.Column(plot, readout, margin=0, sizing_mode="stretch_width")
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Alignment check failed: {exc}", alert_type="danger")

    def per_cycle_table(self):
        try:
            if not self.data.has_echem():
                return self.empty_state("This run has no electrochemistry channel, so per-cycle results are unavailable.")
            stats = self._per_cycle_frame()
            if stats.is_empty():
                return self.empty_state("No cycles in the current selection.")
            return self._render_cycle_table(stats)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Per-cycle table failed: {exc}", alert_type="danger")

    def _render_cycle_table(self, stats: pl.DataFrame):
        try:
            for c in stats.columns:
                if stats[c].dtype in (pl.Float32, pl.Float64):
                    stats = stats.with_columns(pl.col(c).round(6))
            return pn.widgets.Tabulator(
                stats.to_pandas(),
                height=min(320, max(120, 40 + stats.height * 28)),
                layout="fit_data_fill", show_index=False,
                titles=echem.pretty_column_titles(stats.columns),
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
            cp = self._technique() == "cp"
            ycol, ypct = (_E, (2, 98)) if cp else (_I, (1, 99))
            if self._is_multi():
                frame = echem.overlay_selected_waveforms(self._named_waveforms(), **self._cycle_kwargs())
                if cp:
                    plot = plots.echem_overlay(frame, _T, _E, _T_LABEL, _E_LABEL,
                                               "Potential vs time (CP) · all runs",
                                               by_cycle=False, monotonic=True, height=height)
                else:
                    plot = plots.echem_overlay(frame, _E, _I, _E_LABEL, _I_LABEL,
                                               "Current vs potential (CV) · all runs",
                                               by_cycle=True, monotonic=False, height=height)
                plot = self._with_ylim(plot, frame, [ycol], pct=ypct)
                return self.nearest_hover(self.force_plot_height(plot, height))
            wf = self._selected_waveform()
            if cp:
                plot = plots.echem_curve(wf, _T, _E, _T_LABEL, _E_LABEL, "Potential vs time (CP)",
                                         by_cycle=False, monotonic=True, height=height, show_legend=False)
            else:
                plot = plots.echem_curve(wf, _E, _I, _E_LABEL, _I_LABEL, "Current vs potential (CV)",
                                         by_cycle=True, monotonic=False, height=height,
                                         show_legend=self._has_cycles)
            plot = self._with_ylim(plot, wf, [ycol], pct=ypct)
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Plot failed: {exc}", alert_type="danger")

    def _mass_plot(self, x_key: str, height: int):
        state = self.controls.state()
        ax = axis(x_key)
        q = quantity("sauerbrey_mass")
        value_df, _ = self.data.value_df(state, "sauerbrey_mass", x_key)
        plot = plots.analysis_timeline(
            value_df, q, ax, state.groups, state.orders,
            f"Mass vs {ax.label}",
            annotation_spans=self.data.annotation_spans(state) if ax.is_time else None,
            select_x=False, height=height,
        )
        plot = self._with_ylim(plot, value_df, ["value"])
        return self.nearest_hover(self.force_plot_height(plot, height))

    def mass_vs_potential(self, height: int = PLOT_HEIGHT):
        try:
            # CP is galvanostatic (potential ≈ constant), so mass-vs-potential is
            # meaningless there — plot mass vs charge (the capacity curve) instead.
            if not self.data.has_echem():
                x_key = "time"
            elif self._technique() == "cp" and "charge" in self.data.run.columns:
                x_key = "charge"
            else:
                x_key = "potential"
            return self._mass_plot(x_key, height)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Mass plot failed: {exc}", alert_type="danger")

    def mass_vs_charge(self, height: int = PLOT_HEIGHT):
        """Mass vs charge (Δm–Q). Its slope is the apparent molar mass per electron
        (F·dm/dQ = M/z) — the standard quantitative EQCM check of Faraday's law."""
        try:
            x_key = "charge" if "charge" in self.data.run.columns else (
                "potential" if self.data.has_echem() else "time")
            return self._mass_plot(x_key, height)
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Mass-vs-charge plot failed: {exc}", alert_type="danger")

    def potential_vs_capacity(self, height: int = PLOT_HEIGHT):
        """CP voltage profile: potential vs charge (capacity) per cycle.

        The standard galvanostatic plot — each cycle's plating/stripping plateau
        read against passed charge. Replaces the current-density-vs-potential plot
        for CP, where constant current and a near-flat potential make that plot a
        meaningless blob.
        """
        try:
            if not self.data.has_echem():
                return self.empty_state("No electrochemistry channel.")
            if self._is_multi():
                frame = echem.overlay_selected_waveforms(self._named_waveforms(), **self._cycle_kwargs())
                plot = plots.echem_overlay(frame, _Q, _E, _Q_LABEL, _E_LABEL,
                                           "Voltage profile (potential vs charge) · all runs",
                                           by_cycle=True, monotonic=False, height=height)
                plot = self._with_ylim(plot, frame, [_E])
                return self.nearest_hover(self.force_plot_height(plot, height))
            wf = self._selected_waveform()
            plot = plots.echem_curve(wf, _Q, _E, _Q_LABEL, _E_LABEL,
                                     "Voltage profile (potential vs charge)",
                                     by_cycle=True, monotonic=False, height=height,
                                     show_legend=self._has_cycles)
            plot = self._with_ylim(plot, wf, [_E])
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Voltage profile failed: {exc}", alert_type="danger")

    def density_vs_potential(self, height: int = COMPACT_PLOT_HEIGHT):
        try:
            if not self.data.has_echem():
                return self.empty_state("No electrochemistry channel.")
            if self._is_multi():
                area = self.controls.state().params.area_cm2
                frame = echem.overlay_selected_waveforms(self._named_waveforms(), **self._cycle_kwargs())
                if not frame.is_empty() and _I in frame.columns:
                    frame = frame.with_columns((pl.col(_I) / area).alias(_J))
                plot = plots.echem_overlay(frame, _E, _J, _E_LABEL, _J_LABEL,
                                           "Current density vs potential · all runs",
                                           by_cycle=True, monotonic=False, height=height)
                plot = self._with_ylim(plot, frame, [_J], pct=(1, 99))
                return self.nearest_hover(self.force_plot_height(plot, height))
            wf = self._selected_waveform()
            plot = plots.echem_curve(wf, _E, _J, _E_LABEL, _J_LABEL, "Current density vs potential",
                                     by_cycle=True, monotonic=False, height=height,
                                     show_legend=False)
            plot = self._with_ylim(plot, wf, [_J], pct=(1, 99))
            return self.nearest_hover(self.force_plot_height(plot, height))
        except Exception as exc:  # pragma: no cover
            return pn.pane.Alert(f"Plot failed: {exc}", alert_type="danger")

    # --- technique-aware layout -------------------------------------------
    @staticmethod
    def _results_card(body, title: str):
        return pn.Card(body, title=title, collapsible=False, margin=0,
                       sizing_mode="stretch_width", css_classes=["qcm-card"])

    def _detail_plot_row(self, *_):
        """The two detail plots, chosen by technique.

        CV (the i–E experiment): mass-vs-potential + current-density-vs-potential.
        CP (galvanostatic): mass-vs-charge (capacity) + the voltage profile —
        the current-density-vs-potential plot is dropped because constant current
        and a flat potential make it meaningless there.
        """
        if self._technique() == "cp":
            left = self._results_card(self.mass_vs_potential(height=PLOT_HEIGHT),
                                      "Mass vs charge (capacity)")
            right = self._results_card(self.potential_vs_capacity(height=PLOT_HEIGHT),
                                       "Voltage profile (potential vs charge)")
        else:
            # CV: mass-vs-potential (where deposition happens) and mass-vs-charge
            # (slope = apparent molar mass M/z). Raw current-density-vs-potential
            # is the area-scaled headline and is reachable on the Data page, so it
            # isn't restated here.
            left = self._results_card(self.mass_vs_potential(height=PLOT_HEIGHT),
                                      "Mass vs potential")
            right = self._results_card(self.mass_vs_charge(height=PLOT_HEIGHT),
                                       "Mass vs charge (slope = M/z)")
        return pn.Row(left, right, margin=0, sizing_mode="stretch_width",
                      css_classes=["qcm-results-plotrow"])

    def _trend_plot_row(self, *_):
        """Per-cycle MPE + Coulombic-efficiency trends — CP only.

        Both are plating/stripping (half-cycle) quantities with no meaning for a
        CV sweep, so the row is hidden entirely off CP rather than showing two
        empty 'needs a CP run' cards.
        """
        if self._technique() != "cp":
            return pn.Spacer(height=0)
        return pn.Row(
            self._results_card(self.mpe_trend_plot(height=PLOT_HEIGHT), "MPE per cycle"),
            self._results_card(self.ce_trend_plot(height=PLOT_HEIGHT), "Coulombic efficiency per cycle"),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-plotrow"],
        )

    # --- page surface ------------------------------------------------------
    def page(self):
        sig = self.controls.explore_inputs
        rv = self.controls.runset_version
        if not self.data.has_echem():
            # QCM-only run: headline cards + one big mass-vs-time plot.
            children = [self.panel(self.summary_cards, *sig, rv, title="Summary (current analysis range)")]
            if self._is_multi():
                children.append(self.panel(
                    self.per_channel_comparison_table, *sig, rv,
                    title="Per-channel comparison (all runs)",
                    controls=pn.Row(self.csv_download(self._comparison_frame, "per_channel_comparison.csv"),
                                    margin=0), controls_position="bottom"))
            children.append(self.panel(lambda: self.mass_vs_potential(height=RESULTS_PLOT_HEIGHT),
                                       *sig, self.controls.plot_reset_version, title="Mass vs time"))
            return pn.Column(*children, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-results"])

        cyc = self._cycle_inputs
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
        # KPI strip across the top (tiles fill one full-width row), then the tall
        # headline plot sits beside the short Technique/Cycle controls so their
        # heights match (no dead column), and the detail plots + table span the
        # full width below.
        rows = [
            self.panel(self.summary_cards, *sig, rv, title="Summary (current analysis range)"),
        ]
        if self._is_multi():
            rows.append(self.panel(
                self.per_channel_comparison_table, *sig, rv,
                title="Per-channel comparison (all runs)",
                controls=pn.Row(self.csv_download(self._comparison_frame, "per_channel_comparison.csv"),
                                margin=0), controls_position="bottom"))
        rows += [
            pn.Row(
                self.panel(lambda: self.primary_echem_plot(), *sig, *cyc, rv, self.controls.plot_reset_version,
                           title="Electrochemistry"),
                side,
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-results-midrow"],
            ),
            # Detail plots adapt to the technique (CV: mass/J vs potential; CP:
            # mass vs charge + voltage profile).
            pn.bind(self._detail_plot_row, self.technique_select, *sig, *cyc, rv,
                    self.controls.plot_reset_version),
            self.panel(lambda: self.cycle_overlay_plot(), *sig, *cyc, rv, self.controls.plot_reset_version,
                       title="Cycle overlay", controls=pn.Row(self.cycle_zero, margin=0)),
            self.panel(lambda: self.alignment_check(), *sig, rv,
                       title="PS ↔ QCM alignment check", collapsible=True, collapsed=True),
            self.panel(self.per_cycle_table, *sig, *cyc, rv, title="Per-cycle summary",
                       controls=pn.Row(self.csv_download(self._per_cycle_frame, "per_cycle_summary.csv"),
                                       margin=0), controls_position="bottom"),
            # Per-cycle MPE + Coulombic efficiency — shown for CP only.
            pn.bind(self._trend_plot_row, self.technique_select, *sig, *cyc, rv,
                    self.controls.plot_reset_version),
        ]
        return pn.Column(*rows, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-results"])
