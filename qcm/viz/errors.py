"""Error policy for UI surfaces.

Plot and table builders in ``qcm.viz.steps`` are intentionally defensive: a
failure returns an inline alert instead of blanking the page. The rule this
module enforces is that such a failure is *also logged* with a full traceback
and the failing surface's name, so defensive handling never hides a real bug
(the historical failure mode — see :mod:`qcm.log`).

Two entry points, one logging path:

- :func:`surface_error` — call inside an existing ``except`` block:
  ``return surface_error("Summary", exc)``. Logs, then returns the danger alert
  with the same user-facing text as before (``"<label> failed: <exc>"``).
- :func:`guarded` — decorator for *new* surface methods so they need no
  boilerplate ``try/except`` at all.

Panel is imported lazily so importing this module stays cheap and does not pull
the UI stack into non-UI callers.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from ..log import get_logger

_log = get_logger("viz")


def surface_error(label: str, exc: BaseException, *, alert_type: str = "danger"):
    """Log a surface failure with traceback and return an inline alert.

    ``label`` names the surface (e.g. ``"Summary"``, ``"Cycle overlay"``); the
    alert reads ``"<label> failed: <exc>"`` — unchanged from the inline alerts
    this replaced.
    """
    import panel as pn

    _log.exception("%s failed: %s", label, exc)
    return pn.pane.Alert(f"{label} failed: {exc}", alert_type=alert_type)


def guarded(label: str, *, alert_type: str = "danger") -> Callable:
    """Wrap a surface builder so any exception is logged and shown, not swallowed.

    Use on a method/function that returns a Panel renderable::

        @guarded("Summary")
        def summary_cards(self):
            ...

    On success the wrapped return value passes through unchanged; on failure the
    call is routed through :func:`surface_error`.
    """
    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — deliberate surface boundary
                return surface_error(label, exc, alert_type=alert_type)
        return wrapper
    return decorate
