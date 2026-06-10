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


def _is_run_dir(path: str | Path) -> bool:
    """True for an already-ingested run directory (has a manifest)."""
    p = Path(path)
    return p.is_dir() and (p / "manifest.json").exists()


def _landing():
    """Friendly empty state: pick a run folder or instrument file, then open it.

    Shown when the viewer is served with no (valid) run, so a non-technical user
    sees a file picker instead of a stack trace. Imports the chosen source in
    place and swaps the page to the live viewer on success.
    """
    import tempfile

    from qcm.profiles import import_run, resolve_import_target

    _ensure_app_css()
    root = pn.Column(sizing_mode="stretch_width", css_classes=["qcm-app"])
    browser = pn.widgets.FileSelector(
        directory=str(Path.cwd()), only_files=False, sizing_mode="stretch_width",
    )
    status = pn.pane.Alert(
        "Pick a run folder, or a QCM instrument file (.csv / .txt) or parquet, then Open.",
        alert_type="light", sizing_mode="stretch_width",
    )
    open_btn = pn.widgets.Button(name="Open", button_type="primary", icon="folder-open")

    def _set(kind: str, msg: str) -> None:
        status.alert_type = kind
        status.object = msg

    def _open(_event=None):
        selected = browser.value
        paths = selected if isinstance(selected, list) else ([selected] if selected else [])
        if not paths:
            _set("warning", "Select a file or folder first.")
            return
        run_dirs: list[Path] = []
        for src in paths:
            src = Path(src)
            try:
                qcm_src, ps_src = resolve_import_target(src)
                if _is_run_dir(qcm_src):
                    run_dirs.append(qcm_src)
                else:
                    paired = f" + {ps_src.name}" if ps_src else ""
                    _set("light", f"Importing {qcm_src.name}{paired} …")
                    dest = Path(tempfile.mkdtemp(prefix="qcm_view_")) / f"{qcm_src.stem}_run"
                    import_run(qcm_src, dest, ps_source=ps_src)
                    run_dirs.append(dest)
            except Exception as exc:  # noqa: BLE001
                _set("danger", f"Could not open {src.name}: {exc}")
                return
        try:
            root.objects = [QCMViewer(run_dirs).view()]
        except Exception as exc:  # noqa: BLE001
            _set("danger", f"Failed to load: {exc}")

    open_btn.on_click(_open)
    root.objects = [pn.Column(
        pn.pane.HTML(
            "<div style='max-width:760px;margin:48px auto 0'>"
            "<h1 style='margin:0 0 4px'>QCM-D Viewer</h1>"
            "<p style='color:#64748b;margin:0 0 20px'>Open a measurement to begin.</p></div>"
        ),
        pn.Column(browser, pn.Row(open_btn, margin=0), status,
                  css_classes=["qcm-card"], margin=(0, 0, 0, 0),
                  styles={"max-width": "760px", "margin": "0 auto"}),
        sizing_mode="stretch_width",
    )]
    return root


def app(run_path: str | list[str] | None = None):
    if run_path is None:
        args = sys.argv[1:]
        run_path = args if args else None
    if not run_path:
        return _landing()
    paths = [run_path] if isinstance(run_path, (str, Path)) else list(run_path)
    valid = [p for p in paths if _is_run_dir(p)]
    if not valid:
        return _landing()
    return QCMViewer(valid).view()
