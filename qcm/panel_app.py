"""Panel entry point served by ``qcm serve``.

The viewer itself lives in :mod:`qcm.viz.app`; this module only wires the run
path from ``--args`` into the app and makes it servable.
"""
from __future__ import annotations

import sys

import panel as pn

from qcm.viz.app import app

try:
    APP = app(sys.argv[-1] if len(sys.argv) > 1 else ".")
    APP.servable()
except Exception as exc:  # pragma: no cover - surfaced in the browser
    pn.pane.Alert(f"Could not start QCM viewer: {exc}", alert_type="danger").servable()
