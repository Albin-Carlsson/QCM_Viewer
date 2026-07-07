"""CLI port fallback and the in-app 'Open other…' → picker handoff."""
from __future__ import annotations

import socket


def test_resolve_port_passes_zero_through():
    from qcm.cli import _resolve_port
    assert _resolve_port(0) == 0


def test_resolve_port_returns_free_port_when_busy():
    from qcm.cli import _resolve_port

    # Hold a port open for the duration of the call so it reads as busy.
    held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    held.bind(("", 0))
    busy = held.getsockname()[1]
    try:
        chosen = _resolve_port(busy)
        assert chosen != busy
        # The chosen port is actually bindable.
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("", chosen))
        probe.close()
    finally:
        held.close()


def test_request_landing_routes_to_picker_over_args():
    from qcm.viz import app as appmod

    appmod.request_landing()
    view = appmod.app(["/nonexistent/run"])  # pending landing wins over args
    # _landing builds the picker column; it must not raise and must render.
    assert view is not None
    assert hasattr(view, "servable") or hasattr(view, "objects")
