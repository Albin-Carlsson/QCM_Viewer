"""QCM viewer Panel application.

This file intentionally only composes the app. The architecture is:

- ``state.py``: typed run/view state
- ``controls.py``: Panel widgets and widget -> state conversion
- ``data.py``: run queries and science transforms
- ``pages.py``: visual components/pages
- ``actions.py``: mutations and exports
- ``layout.py``: template/sidebar/tabs assembly
"""
from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import panel as pn

from qcm.run import open_run

from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .design import APP_CSS
from .plot_theme import apply as apply_plot_theme
from .shell import ViewerShell
from .state import RunInfo

_US = 1_000_000

pn.extension("tabulator", sizing_mode="stretch_width", notifications=True)
pn.config.loading_indicator = True
hv.extension("bokeh")
apply_plot_theme()
pn.config.raw_css.append(APP_CSS)


class QCMViewer:
    """Thin composition root for the viewer."""

    def __init__(self, run_path: str | Path):
        self.run = open_run(run_path)
        self.info = self._read_run_info()
        self.controls = ViewerControls(self.info, self.run.load_view_state())
        self.data = QCMViewData(self.run, self.info)
        self.actions = ViewerActions(self.run, self.info, self.controls, self.data)
        self.shell = ViewerShell(self.run, self.info, self.controls, self.data, self.actions)

    def _read_run_info(self) -> RunInfo:
        groups = self.run.groups or [0]
        orders = self.run.overtone_orders()
        t0_us = self.run.time_start
        t1_us = self.run.time_end
        span_s = max((t1_us - t0_us) / _US, 1e-6)
        try:
            idx = self.run.sweep_index()
            fmin = float(idx["frequency_min"].min())
            fmax = float(idx["frequency_max"].max())
            seq_min = int(idx["sequence"].min())
            seq_max = int(idx["sequence"].max())
            n_sweeps = int(idx["sequence"].n_unique())
        except Exception:
            fmin, fmax = 0.0, 1.0
            seq_min = seq_max = n_sweeps = 0
        return RunInfo(
            run_id=self.run.id,
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
            rows=self.run.manifest.metadata.get("rows", "?"),
        )

    def view(self):
        return self.shell.view()


def app(run_path: str | None = None):
    run_path = run_path or (sys.argv[-1] if len(sys.argv) > 1 else ".")
    return QCMViewer(run_path).view()
