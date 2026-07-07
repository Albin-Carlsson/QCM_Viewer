"""Data service for the QCM viewer.

This module is the boundary between UI state and run/science APIs. It owns data
queries, elapsed-time conversion, and small composition logic. It does not own
Panel widgets or layout.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import replace
from typing import Any, Callable

import polars as pl

from qcm.log import get_logger
from qcm.run import QCMRun

from . import echem, plots, science
from .state import RunInfo, ViewState
from .theme import axis, quantity

_US = 1_000_000
_CACHE_SIZE = 64

_log = get_logger("viz.data")


class QCMViewData:
    def __init__(self, run: QCMRun, info: RunInfo, *, cache_size: int = _CACHE_SIZE):
        self.run = run
        self.info = info
        # Set when this run is part of a multi-run set (see runset.RunSet); the
        # hero plot reads it to decide whether to overlay. None == single-run.
        self.runset = None
        # Bounded LRU over query results keyed by their full argument tuple. The
        # hero plot issues two value_df calls and Analyze renders a plot plus a
        # stats table from the same state; without this they would re-scan the
        # same parquet. Cached frames are never mutated (compute/add_elapsed
        # return new frames), so sharing them is safe.
        self._query_cache: "OrderedDict[tuple, Any]" = OrderedDict()
        self._cache_max = cache_size

    def _cache_get(self, key: tuple, compute: Callable[[], Any]) -> Any:
        cache = self._query_cache
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        value = compute()
        cache[key] = value
        if len(cache) > self._cache_max:
            cache.popitem(last=False)
        return value

    def _timeline(self, columns: tuple[str, ...], t0: int, t1: int, groups: tuple[int, ...], level: str | None = None) -> pl.DataFrame:
        # Echem channels held in the retained PS stream are derived on read by
        # interpolating onto the QCM clock at the current alignment offset, so a
        # changed offset re-applies instantly (the offset is part of the key).
        roles = self.run.echem_stream_roles
        echem_cols = tuple(c for c in columns if c in roles)
        if not echem_cols:
            key = ("timeline", level, columns, int(t0), int(t1), groups)
            return self._cache_get(key, lambda: self.run.timeline(list(columns), t0=t0, t1=t1, groups=list(groups) or None, level=level))
        key = ("timeline_echem", level, columns, int(t0), int(t1), groups, self.run.ps_offset_s)
        return self._cache_get(key, lambda: self._derive_timeline(columns, echem_cols, t0, t1, groups, level))

    def _derive_timeline(self, columns: tuple[str, ...], echem_cols: tuple[str, ...], t0: int, t1: int, groups: tuple[int, ...], level: str | None) -> pl.DataFrame:
        stored = [c for c in columns if c not in echem_cols]
        # A skeleton (timestamp + group) is needed to broadcast echem across
        # overtone rows even when only echem columns were requested.
        read = stored or ["fit_center"]
        base = self.run.timeline(read, t0=t0, t1=t1, groups=list(groups) or None, level=level)
        base = self._attach_echem(base, echem_cols)
        drop = [c for c in read if c not in columns]  # the skeleton fit_center, if borrowed
        return base.drop(drop) if drop else base

    def _attach_echem(self, df: pl.DataFrame, roles: tuple[str, ...]) -> pl.DataFrame:
        """Interpolate the retained PS stream's roles onto ``df``'s timestamps at
        the run's alignment offset, broadcasting across overtone groups.

        QCM samples outside the PS stream's recorded span get null (not a held
        endpoint value): ``np.interp`` clamps at the ends, which would freeze
        the last current/potential across a QCM tail recorded after the
        potentiostat stopped — fabricating a phantom applied current that
        corrupts cycle detection and CE. Same convention as the CV attach.
        """
        import numpy as np

        null_cols = [pl.lit(None, dtype=pl.Float64).alias(r) for r in roles]
        stream = self.run.echem_stream()
        if df.is_empty() or "timestamp" not in df.columns or stream.is_empty():
            return df.with_columns(null_cols)
        ps_t = stream["time_s"].to_numpy() + self.run.ps_offset_s
        ts = df["timestamp"].unique().sort()
        q_elapsed = (ts.to_numpy() - self.info.t0_us) / _US
        inside = (q_elapsed >= ps_t[0] - 1e-9) & (q_elapsed <= ps_t[-1] + 1e-9)
        out: dict[str, Any] = {"timestamp": ts}
        for r in roles:
            if r in stream.columns:
                out[r] = np.where(inside, np.interp(q_elapsed, ps_t, stream[r].to_numpy()), np.nan)
        echem_df = pl.DataFrame(out).with_columns(
            pl.col(r).fill_nan(None) for r in roles if r in stream.columns
        )
        return df.join(echem_df, on="timestamp", how="left")

    def clear_echem_cache(self) -> None:
        """Drop cached echem-derived frames after the alignment offset changes."""
        for k in [k for k in self._query_cache if k and k[0] in ("timeline_echem", "echem_wf")]:
            del self._query_cache[k]

    def _baseline_mean(self, value_expr: str, b0: int, b1: int, groups: tuple[int, ...]) -> pl.DataFrame:
        key = ("baseline", value_expr, int(b0), int(b1), groups)
        return self._cache_get(key, lambda: self.run.baseline_mean(value_expr, t0=b0, t1=b1, groups=list(groups) or None))

    def add_elapsed(self, df: pl.DataFrame) -> pl.DataFrame:
        if df.is_empty() or "timestamp" not in df.columns:
            return df.with_columns(pl.lit(0.0).alias(plots.X)) if not df.is_empty() else df
        return df.with_columns(((pl.col("timestamp") - self.info.t0_us) / _US).alias(plots.X))

    def value_df(
        self,
        state: ViewState,
        quantity_key: str | None = None,
        x_axis: str | None = None,
    ) -> tuple[pl.DataFrame, float]:
        key = quantity_key or state.quantity
        x_key = x_axis if x_axis is not None else state.x_axis
        ax = axis(x_key)
        q = quantity(key)
        groups = tuple(state.groups)
        t0, t1 = state.t_us(self.info.t0_us)
        tic = time.perf_counter()
        main = self._timeline(tuple(q.sources), t0, t1, groups)
        base_means = None
        if q.referenced:
            b0, b1 = state.baseline_us(self.info.t0_us)
            # Only the per-group mean of the baseline window is needed; aggregate
            # it in SQL instead of scanning the raw window into Python.
            base_means = self._baseline_mean(science.raw_value_sql(q), b0, b1, groups)
        out = science.compute(main, key, state.orders, baseline_means_df=base_means,
                              params=state.params)
        # Drift correction: subtract a per-group trend fitted over the reference
        # window (generalises baseline-mean subtraction to a linear/poly drift).
        # Only the referenced resonance family drifts meaningfully; echem and the
        # MPE derivative are left alone.
        if state.detrend and q.kind in ("frequency", "dissipation", "mass"):
            b0, b1 = state.baseline_us(self.info.t0_us)
            ref_main = self._timeline(tuple(q.sources), b0, b1, groups)
            ref_out = science.compute(ref_main, key, state.orders, baseline_means_df=base_means,
                                      params=state.params)
            out = science.detrend(out, ref_out, t0_us=self.info.t0_us,
                                  order=state.detrend_order)
        # Despike resonance-derived traces (spikes originate in the resonance
        # fit, so cell-level echem channels are left untouched).
        if state.despike and (q.is_resonance or q.kind == "mpe"):
            out = science.despike(out, window=state.despike_window)
        if key == "mpe":
            clip = (state.mpe_clip_lo, state.mpe_clip_hi) if state.mpe_clip else None
            out = science.smooth_clip_mpe(
                out, clip=clip,
                smooth=state.mpe_smooth,
                window=state.mpe_window,
            )
        out = self.add_elapsed(out)
        out = self._attach_x(out, ax, t0, t1, groups)
        return out, (time.perf_counter() - tic) * 1000

    def _attach_x(self, out: pl.DataFrame, ax, t0: int, t1: int, groups: tuple[int, ...]) -> pl.DataFrame:
        """Add an ``x`` column carrying the selected x-axis values.

        Time uses the elapsed-seconds column already derived; every other axis
        reads its stored column over the same window/groups and joins it in. The
        ``x`` column is what plots map to the horizontal axis, leaving ``value``
        (y) and the time-based overlays untouched.
        """
        if out.is_empty():
            return out.with_columns(pl.lit(None, dtype=pl.Float64).alias("x"))
        if ax.is_time:
            return out.with_columns(pl.col(plots.X).cast(pl.Float64).alias("x"))
        if ax.source == "cycle":
            # CP cycles are derived from current sign, not stored, so build the
            # cycle-per-timestamp map from the (derived) echem waveform rather
            # than querying a column that may not exist.
            return self._attach_cycle_x(out)
        xdf = self._timeline((ax.source,), t0, t1, groups)
        if xdf.is_empty() or ax.source not in xdf.columns:
            return out.with_columns(pl.lit(None, dtype=pl.Float64).alias("x"))
        # The electrochemistry x-source columns repeat for every frequency point
        # of a sweep (they are constant per sweep), so collapse to one row per
        # (timestamp, group) before joining — otherwise a raw-level join is
        # many-to-many and blows up the row count.
        xdf = (
            xdf.select(["timestamp", "group", pl.col(ax.source).cast(pl.Float64).alias("x")])
            .unique(subset=["timestamp", "group"], keep="first")
        )
        return out.join(xdf, on=["timestamp", "group"], how="left")

    def _cycle_by_timestamp(self) -> pl.DataFrame:
        """``[timestamp, cycle]`` from the echem waveform, deriving CP cycles."""
        wf = self.echem_waveform()
        if not wf.is_empty() and echem.detect_technique(wf) == "cp":
            wf = echem.derive_cycles(wf)
        if wf.is_empty() or "cycle" not in wf.columns or "timestamp" not in wf.columns:
            return pl.DataFrame()
        return wf.select(["timestamp", "cycle"]).drop_nulls("cycle").unique(subset=["timestamp"])

    def _attach_cycle_x(self, out: pl.DataFrame) -> pl.DataFrame:
        cyc = self._cycle_by_timestamp()
        if cyc.is_empty():
            return out.with_columns(pl.lit(None, dtype=pl.Float64).alias("x"))
        cyc = cyc.select(["timestamp", pl.col("cycle").cast(pl.Float64).alias("x")])
        return out.join(cyc, on="timestamp", how="left")

    def time_window_for_x(self, x_axis: str, x0: float, x1: float) -> tuple[float, float] | None:
        """Elapsed-seconds window enclosing the rows whose x-axis value is in
        ``[x0, x1]``. Drives drag-select on non-time axes: a brushed range on a
        monotonic axis (e.g. cycle number) maps to the analysis time window.

        Time is the identity. Other axes read their source column over the full
        run and return the min/max timestamp (as elapsed seconds) of the rows in
        range, or ``None`` when nothing matches.
        """
        ax = axis(x_axis)
        lo, hi = sorted((float(x0), float(x1)))
        if ax.is_time:
            return (lo, hi)
        if x_axis == "cycle_number":
            # CP cycles are derived (not stored); snap the brushed bounds to the
            # cycles they touch and return their enclosing time window.
            cyc = self._cycle_by_timestamp()
            if cyc.is_empty():
                return None
            sel = cyc.filter((pl.col("cycle") >= round(lo)) & (pl.col("cycle") <= round(hi)))
            if sel.is_empty():
                return None
            t_lo = (int(sel["timestamp"].min()) - self.info.t0_us) / _US
            t_hi = (int(sel["timestamp"].max()) - self.info.t0_us) / _US
            return (t_lo, t_hi)
        df = self._timeline((ax.source,), self.info.t0_us, self.info.t1_us, ())
        if df.is_empty() or ax.source not in df.columns or "timestamp" not in df.columns:
            return None
        sel = df.filter((pl.col(ax.source) >= lo) & (pl.col(ax.source) <= hi)).drop_nulls(ax.source)
        if sel.is_empty():
            return None
        t_lo = (int(sel["timestamp"].min()) - self.info.t0_us) / _US
        t_hi = (int(sel["timestamp"].max()) - self.info.t0_us) / _US
        return (t_lo, t_hi)

    def qcmd_frames(self, state: ViewState) -> tuple[pl.DataFrame, pl.DataFrame]:
        norm_df, _ = self.value_df(state, "delta_f_norm")
        d_df, _ = self.value_df(state, "delta_D")
        return norm_df, d_df

    _SUMMARY_QUANTITIES = (
        ("delta_f_norm", "df_n"),
        ("delta_D", "dD"),
        ("sauerbrey_mass", "mass"),
        ("quality_factor", "Q"),
    )

    def region_summary(self, state: ViewState) -> pl.DataFrame:
        """Per-channel mean of the headline QCM-D quantities over the current range.

        Reuses the cached ``value_df`` queries (the hero plot already warms
        Δf/n and ΔD), so this glanceable readout is cheap.
        """
        frames = {name: self.value_df(state, key)[0] for key, name in self._SUMMARY_QUANTITIES}
        return science.region_overtone_summary(frames, state.orders)

    def regions_comparison(self, state: ViewState) -> pl.DataFrame:
        """Stack :meth:`region_summary` for every saved range region.

        The current quantity selection is irrelevant here; each saved range is
        summarized on the same fixed set of headline quantities, referenced to
        the active zero/reference range, so regions can be compared side by side.
        """
        rows: list[pl.DataFrame] = []
        for ann in self.annotations():
            if ann.type != "range" or ann.t1 is None:
                continue
            start_s = (ann.t0 - self.info.t0_us) / _US
            end_s = (ann.t1 - self.info.t0_us) / _US
            region_state = replace(state, t_range_s=(start_s, end_s))
            summary = self.region_summary(region_state)
            if summary.is_empty():
                continue
            rows.append(
                summary.with_columns(
                    pl.lit(ann.label).alias("region"),
                    pl.lit(round(max(0.0, end_s - start_s), 2)).alias("duration_s"),
                )
            )
        if not rows:
            return pl.DataFrame()
        return pl.concat(rows, how="diagonal_relaxed")

    def has_echem(self) -> bool:
        return echem.has_echem(self.run.columns)

    def has_raw(self) -> bool:
        """Whether raw frequency-point views (sweep inspector, waterfall) apply."""
        return self.run.has_raw

    def echem_waveform(self) -> pl.DataFrame:
        """Full-run electrochemistry waveform: one row per sweep with the cell
        signals. The channel is identical across overtones, so a single group is
        read; results are cached because every EC view derives from this frame."""
        cols = tuple(c for c in echem.ECHEM_COLUMNS if c in self.run.columns)
        if not cols:
            return pl.DataFrame()
        groups = (self.info.groups[0],) if self.info.groups else ()
        key = ("echem_wf", cols, groups, self.run.ps_offset_s)
        return self._cache_get(
            key,
            lambda: echem.waveform(self._timeline(cols, self.info.t0_us, self.info.t1_us, groups)),
        )

    def cycle_spans(self) -> list[tuple[int, float, float]]:
        """Per-cycle ``(cycle_number, t0_s, t1_s)`` windows in elapsed seconds.

        Cycles are contiguous in time, so each maps to one [start, end] span. Used
        to overlay cycle boundaries on the time-axis plots. Cheap (one row per
        sweep) and cached with the echem waveform query.
        """
        wf = self.echem_waveform()
        if wf.is_empty() or "cycle" not in wf.columns or "timestamp" not in wf.columns:
            return []
        agg = (
            wf.drop_nulls("cycle")
            .group_by("cycle")
            .agg([pl.col("timestamp").min().alias("t0"), pl.col("timestamp").max().alias("t1")])
            .sort("cycle")
        )
        spans: list[tuple[int, float, float]] = []
        for row in agg.iter_rows(named=True):
            x0 = (row["t0"] - self.info.t0_us) / _US
            x1 = (row["t1"] - self.info.t0_us) / _US
            spans.append((int(row["cycle"]), float(x0), float(x1)))
        return spans

    def waterfall_df(self, state: ViewState) -> pl.DataFrame:
        t0, t1 = state.t_us(self.info.t0_us)
        f0, f1 = state.frequency_band
        groups = tuple(state.groups)
        key = ("waterfall", int(t0), int(t1), float(f0), float(f1), groups)
        df = self._cache_get(
            key,
            lambda: self.run.frequency_band(
                f0=f0,
                f1=f1,
                t0=t0,
                t1=t1,
                groups=list(groups) or None,
                columns=["timestamp", "group", "frequency", "conductance"],
            ),
        )
        return self.add_elapsed(df)

    def sweep_df(self, state: ViewState) -> pl.DataFrame:
        return self.run.sweeps_at(sequence=state.sequence, groups=state.selected_sweep_groups())

    def annotations(self):
        return self.run.annotations()

    def annotation_spans(self, state: ViewState) -> list[tuple]:
        _ = state.annotation_version  # explicit reactive dependency
        spans: list[tuple] = []
        for ann in self.annotations():
            x0 = (ann.t0 - self.info.t0_us) / _US
            x1 = ((ann.t1 or ann.t0) - self.info.t0_us) / _US
            marker_kind = ann.tags[0] if ann.tags else "marker"
            spans.append((ann.type, x0, x1, ann.label, marker_kind))
        return spans

    def nearest_sequence_at_seconds(self, seconds: float) -> int | None:
        ts = int(self.info.t0_us + float(seconds) * _US)
        idx = self.run.sweep_index()
        nearest = idx.with_columns((pl.col("timestamp") - ts).abs().alias("_d")).sort("_d")
        if nearest.is_empty():
            return None
        return int(nearest["sequence"][0])

    def sequence_readout(self, sequence: int) -> str:
        suffix = ""
        try:
            idx = self.run.sweep_index()
            row = idx.filter(pl.col("sequence") == sequence)
            if not row.is_empty():
                suffix = f" · t={(row['timestamp'][0] - self.info.t0_us) / _US:.2f} s"
        except Exception:  # noqa: BLE001 — cosmetic suffix; degrade but record
            _log.exception("sequence_readout: sweep index lookup failed")
        pos = (sequence - self.info.seq_min + 1) if self.info.n_sweeps else 0
        return f"**Sweep {sequence}** ({pos}/{self.info.n_sweeps}){suffix} · _click any timeline point to jump here_"
