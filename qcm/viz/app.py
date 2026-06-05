"""QCM viewer Panel application.

Composition root only. Architecture:

- ``state.py``: typed run/view state
- ``controls.py``: Panel widgets and widget -> state conversion
- ``data.py``: run queries and science transforms
- ``steps/*``: per-focus plot + secondary-panel contributors
- ``actions.py``: mutations and exports
- ``shell.py``: workbench assembly (context bar, focus rail, triad, drawer)
"""
from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import panel as pn

from .actions import ViewerActions
from .controls import ViewerControls
from .design import APP_CSS
from .plot_theme import apply as apply_plot_theme
from .runset import ActiveAttrProxy, ActiveRunView, RunSet
from .shell import ViewerShell

_US = 1_000_000

pn.extension("tabulator", sizing_mode="stretch_width", notifications=True)
pn.config.loading_indicator = True
hv.extension("bokeh")
apply_plot_theme()


def _ensure_app_css() -> None:
    """Register the app stylesheet for the *current* Panel session.

    ``pn.config.raw_css`` is per-session: the first time a session reads it,
    Panel copies the class-level default into ``_session_config[curdoc]``.
    Appending at module import only mutates the one session whose ``curdoc``
    happened to be active during the (cached) import, so every later session —
    e.g. a browser refresh under ``panel serve`` — starts from the empty
    default and renders unstyled. Re-registering here runs once per session
    (with that session's ``curdoc`` live), so the CSS survives reloads.
    """
    if APP_CSS not in pn.config.raw_css:
        pn.config.raw_css.append(APP_CSS)


class QCMViewer:
    """Thin composition root for the viewer.

    Accepts one or more run directories. The active run drives every single-run
    view; the full :class:`RunSet` drives the overlay views. A single run behaves
    exactly as before.
    """

    def __init__(self, run_path: str | Path | list[str | Path]):
        paths = [run_path] if isinstance(run_path, (str, Path)) else list(run_path)
        self.runset = RunSet.from_paths(paths)
        # Single-run views hold proxies that follow the active-run selector; the
        # shared controls are sized once from the launch run (the selection is
        # shared across runs, so they are not rebuilt when the active run flips).
        launch_info = self.runset.active.info
        self.data = ActiveRunView(self.runset)
        self.run = ActiveAttrProxy(lambda: self.runset.active.run)
        self.info = ActiveAttrProxy(lambda: self.runset.active.info)
        self.controls = ViewerControls(launch_info, self.runset.active.run.load_view_state())
        self.actions = ViewerActions(self.run, self.info, self.controls, self.data)
        self.shell = ViewerShell(self.run, self.info, self.controls, self.data,
                                 self.actions, self.runset)

    def view(self):
        _ensure_app_css()
        return self.shell.view()


def app(run_path: str | list[str] | None = None):
    if run_path is None:
        args = sys.argv[1:]
        run_path = args if args else ["."]
    return QCMViewer(run_path).view()
