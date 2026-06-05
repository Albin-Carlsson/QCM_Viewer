"""Multi-run support: a run set + the overlay-frame builder.

A :class:`RunSet` holds one or more loaded runs, each wrapped in its own
:class:`~qcm.viz.data.QCMViewData` so it keeps an independent baseline
reference, time origin, and query cache. One run is *active*: every single-run
view (raw sweeps, report, results) operates on it exactly as before. The
overlay views consume :meth:`RunSet.overlay_value_df`, which applies the shared
view selection to every run and stacks the results into one long-form frame
tagged with a run identifier.

Each run is aligned to its own start (``value_df`` derives elapsed seconds from
that run's ``t0_us``) and referenced to its own baseline window, so the shared
selection — a quantity, a time range in seconds-from-start, a baseline window —
is meaningful across runs that were recorded at different wall-clock times.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl

from qcm.run import QCMRun, open_run

from . import echem
from .data import QCMViewData
from .state import RunInfo, ViewState

_US = 1_000_000


def read_run_info(run: QCMRun) -> RunInfo:
    """Stable per-run facts used by controls, headers, and elapsed-time math."""
    groups = run.groups or [0]
    orders = run.overtone_orders()
    t0_us = run.time_start
    t1_us = run.time_end
    span_s = max((t1_us - t0_us) / _US, 1e-6)
    try:
        idx = run.sweep_index()
        fmin = float(idx["frequency_min"].min())
        fmax = float(idx["frequency_max"].max())
        seq_min = int(idx["sequence"].min())
        seq_max = int(idx["sequence"].max())
        n_sweeps = int(idx["sequence"].n_unique())
    except Exception:
        fmin, fmax = 0.0, 1.0
        seq_min = seq_max = n_sweeps = 0
    return RunInfo(
        run_id=run.id,
        groups=groups,
        orders=orders,
        t0_us=t0_us,
        t1_us=t1_us,
        span_s=span_s,
        fmin=fmin,
        fmax=fmax,
        seq_min=seq_min,
        seq_max=seq_max,
        n_sweeps=n_sweeps,
        rows=run.manifest.metadata.get("rows", "?"),
        has_echem=echem.has_echem(run.columns),
    )


def load_run(path: str | Path) -> QCMViewData:
    """Open one run directory and wrap it in a data service."""
    run = open_run(path)
    return QCMViewData(run, read_run_info(run))


class RunSet:
    """An ordered collection of loaded runs with one active.

    The active run drives every single-run view; the whole set drives the
    overlay views. Each run carries a stable ``run_slot`` (its index in the set)
    that the colour system maps to a hue family, so a run keeps the same colour
    regardless of which run is active.
    """

    def __init__(self, runs: list[QCMViewData], active: int = 0):
        if not runs:
            raise ValueError("RunSet needs at least one run")
        self.runs = runs
        self.active_index = max(0, min(active, len(runs) - 1))
        # Editable display labels, seeded from each run's id. Legends, tables, and
        # the run-manager card read these; the id stays the stable identity.
        self._labels = [d.info.run_id for d in runs]
        # Back-reference so a step holding only the active data service can reach
        # the full set (and decide whether to overlay) without a wider signature.
        for d in runs:
            d.runset = self

    @classmethod
    def from_paths(cls, paths: list[str | Path], active: int = 0) -> "RunSet":
        return cls([load_run(p) for p in paths], active=active)

    @property
    def active(self) -> QCMViewData:
        return self.runs[self.active_index]

    @property
    def is_multi(self) -> bool:
        return len(self.runs) > 1

    def labels(self) -> list[str]:
        return list(self._labels)

    def set_label(self, slot: int, text: str) -> None:
        text = (text or "").strip()
        if 0 <= slot < len(self._labels) and text:
            self._labels[slot] = text

    def set_active(self, slot: int) -> None:
        if 0 <= slot < len(self.runs):
            self.active_index = slot

    def add_run(self, data: QCMViewData) -> int:
        """Append a loaded run; returns its slot (new colour family)."""
        data.runset = self
        self.runs.append(data)
        self._labels.append(data.info.run_id)
        return len(self.runs) - 1

    def add_path(self, path: str | Path) -> int:
        return self.add_run(load_run(path))

    def overlay_value_df(
        self,
        state: ViewState,
        quantity_key: str | None = None,
        x_axis: str | None = None,
    ) -> pl.DataFrame:
        """Apply the shared selection to every run and stack the results.

        Returns a long-form frame with the per-run ``value_df`` columns plus a
        ``run`` label and integer ``run_slot``. Each run is computed against its
        own time origin and baseline, so curves overlay on a common
        seconds-from-start / referenced axis. Empty runs (no data in range) are
        dropped; an all-empty set yields an empty frame.
        """
        frames: list[pl.DataFrame] = []
        for slot, d in enumerate(self.runs):
            df, _ = d.value_df(state, quantity_key, x_axis)
            if df.is_empty():
                continue
            frames.append(
                df.with_columns(
                    pl.lit(self._labels[slot]).alias("run"),
                    pl.lit(slot, dtype=pl.Int32).alias("run_slot"),
                )
            )
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed")

    def overlay_region_summary(self, state: ViewState) -> pl.DataFrame:
        """Per-channel headline summary stacked across runs (``run``/``run_slot``).

        Each run is summarized over the shared analysis range against its own
        baseline, giving one row set per run × overtone channel for the
        cross-run comparison table.
        """
        frames: list[pl.DataFrame] = []
        for slot, d in enumerate(self.runs):
            summary = d.region_summary(state)
            if summary.is_empty():
                continue
            frames.append(
                summary.with_columns(
                    pl.lit(self._labels[slot]).alias("run"),
                    pl.lit(slot, dtype=pl.Int32).alias("run_slot"),
                )
            )
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed")


class ActiveRunView:
    """Transparent stand-in for the run set's active :class:`QCMViewData`.

    Every single-run view (raw-sweep drawer, report/export, results dashboard)
    holds one of these instead of a fixed run, so flipping the active-run
    selector repoints them all without rebuilding their wiring. Attribute access
    delegates to ``runset.active``; overlay views still reach the whole set via
    the delegated ``.runset`` back-reference.
    """

    def __init__(self, runset: "RunSet"):
        object.__setattr__(self, "_rs", runset)

    def __getattr__(self, name):
        return getattr(self._rs.active, name)


class ActiveAttrProxy:
    """Follow one attribute of the active run (e.g. its ``run`` or ``info``)."""

    def __init__(self, get):
        object.__setattr__(self, "_get", get)

    def __getattr__(self, name):
        return getattr(self._get(), name)
