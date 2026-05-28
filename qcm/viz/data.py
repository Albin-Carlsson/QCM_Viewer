"""Data service for the QCM viewer.

This module is the boundary between UI state and run/science APIs. It owns data
queries, elapsed-time conversion, and small composition logic. It does not own
Panel widgets or layout.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable

import polars as pl

from qcm.run import QCMRun

from . import plots, science
from .state import RunInfo, ViewState
from .theme import quantity

_US = 1_000_000
_CACHE_SIZE = 64


class QCMViewData:
    def __init__(self, run: QCMRun, info: RunInfo, *, cache_size: int = _CACHE_SIZE):
        self.run = run
        self.info = info
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
        key = ("timeline", level, columns, int(t0), int(t1), groups)
        return self._cache_get(key, lambda: self.run.timeline(list(columns), t0=t0, t1=t1, groups=list(groups) or None, level=level))

    def _baseline_mean(self, value_expr: str, b0: int, b1: int, groups: tuple[int, ...]) -> pl.DataFrame:
        key = ("baseline", value_expr, int(b0), int(b1), groups)
        return self._cache_get(key, lambda: self.run.baseline_mean(value_expr, t0=b0, t1=b1, groups=list(groups) or None))

    def add_elapsed(self, df: pl.DataFrame) -> pl.DataFrame:
        if df.is_empty() or "timestamp" not in df.columns:
            return df.with_columns(pl.lit(0.0).alias(plots.X)) if not df.is_empty() else df
        return df.with_columns(((pl.col("timestamp") - self.info.t0_us) / _US).alias(plots.X))

    def value_df(self, state: ViewState, quantity_key: str | None = None) -> tuple[pl.DataFrame, float]:
        key = quantity_key or state.quantity
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
        out = science.compute(main, key, state.orders, baseline_means_df=base_means)
        return self.add_elapsed(out), (time.perf_counter() - tic) * 1000

    def qcmd_frames(self, state: ViewState) -> tuple[pl.DataFrame, pl.DataFrame]:
        norm_df, _ = self.value_df(state, "delta_f_norm")
        d_df, _ = self.value_df(state, "delta_D")
        return norm_df, d_df

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
        except Exception:
            pass
        pos = (sequence - self.info.seq_min + 1) if self.info.n_sweeps else 0
        return f"**Sweep {sequence}** ({pos}/{self.info.n_sweeps}){suffix} · _click any timeline point to jump here_"
