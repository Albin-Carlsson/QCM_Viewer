"""Panel entry point served by ``qcm serve``."""
from __future__ import annotations

import sys

import panel as pn

from qcm.viz.app import app

try:
    APP = app(sys.argv[1:] if len(sys.argv) > 1 else None)
    APP.servable()
except Exception as exc:  # noqa: BLE001 — entry point: any startup failure renders in the browser
    pn.pane.Alert(f"Could not start QCM viewer: {exc}", alert_type="danger").servable()
