"""Project logging utility.

A single place to get a configured logger so caught exceptions are *recorded*
rather than silently swallowed. The viewer renders most plot/table surfaces
defensively (a failure returns an inline alert instead of blanking the page),
which is good for the user but historically hid real bugs — a failure was
invisible unless it happened to surface in the ``panel serve`` console. Routing
those handlers through :func:`get_logger` makes every caught exception greppable
with a full traceback and the failing surface's name.

This module is deliberately Panel-free (it lives in the core ``qcm`` package, not
``qcm.viz``) so the science/IO layers can log too without importing UI code.
Library convention: we attach a :class:`logging.NullHandler` and never call
``basicConfig`` here — the application entry point (or the host, e.g. ``panel
serve``) owns handler/level configuration. Set ``QCM_LOG_LEVEL`` to raise or
lower verbosity without code changes.
"""
from __future__ import annotations

import logging
import os

_ROOT_NAME = "qcm"
_configured = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the ``qcm`` logger (or a ``qcm.<name>`` child).

    The first call attaches a ``NullHandler`` to the package root logger and
    applies ``QCM_LOG_LEVEL`` (e.g. ``DEBUG``) if set, so logging works whether
    or not the host configured handlers.
    """
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if not _configured:
        root.addHandler(logging.NullHandler())
        level = os.environ.get("QCM_LOG_LEVEL")
        if level:
            root.setLevel(level.upper())
        _configured = True
    if name and name != _ROOT_NAME:
        return root.getChild(name)
    return root
