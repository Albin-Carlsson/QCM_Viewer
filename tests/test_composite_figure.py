"""Composite figure builder + the Figure-page step."""
from __future__ import annotations

import numpy as np

from qcm.viz.figure import Panel, Series, composite_figure, figure_bytes


def test_builder_stacks_panels_and_exports_vector():
    panels = [
        Panel("Δf/n [Hz]", [Series("n=3", "#e07b39", np.arange(20), np.arange(20) * -1.0)]),
        Panel("ΔD [×10⁻⁶]", [Series("n=3", "#3b82c4", np.arange(20), np.cos(np.arange(20)))]),
    ]
    fig = composite_figure(panels, width_in=7.2)
    assert len(fig.axes) == 2
    # Bottom panel carries the shared x label; panels carry their y labels.
    assert fig.axes[-1].get_xlabel() == "Time [s]"
    assert fig.axes[0].get_ylabel() == "Δf/n [Hz]"
    # Vector formats are non-trivial and SVG is text (XML).
    assert len(figure_bytes(fig, "pdf").read()) > 1000
    assert b"<svg" in figure_bytes(fig, "svg").read()[:400]


def test_builder_empty_is_graceful():
    fig = composite_figure([])
    assert len(fig.axes) == 1  # placeholder message, no crash


def test_figure_step_builds_panels_and_figure():
    from qcm.viz.app import QCMViewer

    viewer = QCMViewer(["/tmp/real-echem-run"])
    step = viewer.shell._figure
    # Default selection includes E + Δf/n + ΔD for an EQCM run.
    assert "potential" in step.panel_select.value
    assert "delta_f_norm" in step.panel_select.value

    panels = step._panels()
    assert len(panels) == len(step.panel_select.value)
    assert any(p.series for p in panels)  # real data produced lines
    fig = step._figure()
    assert len(fig.axes) >= 1
    assert len(figure_bytes(fig, "pdf").read()) > 1000
