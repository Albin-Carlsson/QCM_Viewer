"""The UI error policy: surface failures are logged *and* shown, never swallowed."""
from __future__ import annotations

import logging

from qcm.log import get_logger
from qcm.viz.errors import guarded, surface_error


def test_surface_error_logs_and_returns_alert(caplog):
    with caplog.at_level(logging.ERROR, logger="qcm"):
        alert = surface_error("Summary", ValueError("boom"))
    # User-facing text is unchanged from the inline alerts this replaced.
    assert "Summary failed: boom" in str(alert.object)
    assert alert.alert_type == "danger"
    # The failure was recorded with a traceback, not silently dropped.
    assert any("Summary failed" in r.message for r in caplog.records)
    assert any(r.exc_info for r in caplog.records)


def test_guarded_catches_and_reports(caplog):
    @guarded("Widget")
    def build(explode: bool):
        if explode:
            raise RuntimeError("kaboom")
        return "ok"

    assert build(False) == "ok"  # success passes through untouched
    with caplog.at_level(logging.ERROR, logger="qcm"):
        alert = build(True)
    assert "Widget failed: kaboom" in str(alert.object)


def test_get_logger_is_namespaced():
    assert get_logger().name == "qcm"
    assert get_logger("viz").name == "qcm.viz"
