"""Publication composite figure (matplotlib) — stacked panels, shared time axis.

Mirrors the reference notebook's flagship output: E(t) / Δf/n(t) / ΔD(t) stacked
on a shared x-axis with multiple runs overlaid as colour families. Rendered with
matplotlib so the download is true vector (PDF/SVG), not a rasterised canvas.

This module is UI-free and data-source-agnostic: it takes plain :class:`Panel`
specs (each a list of :class:`Series`) and returns a matplotlib ``Figure``. The
colours come from the same design tokens the interactive plots use, so a run
keeps its identity between the app and the exported figure.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Series:
    """One line in a panel: ``label`` for the legend, ``color`` (hex), and the
    elapsed-seconds ``x`` / value ``y`` arrays."""
    label: str
    color: str
    x: Any
    y: Any


@dataclass
class Panel:
    ylabel: str
    series: list[Series] = field(default_factory=list)


def composite_figure(
    panels: list[Panel],
    *,
    x_label: str = "Time [s]",
    width_in: float = 7.2,
    panel_height_in: float = 1.9,
    dpi: int = 150,
    title: str | None = None,
):
    """Stack ``panels`` vertically on a shared x-axis and return the Figure.

    Built on ``matplotlib.figure.Figure`` directly (not ``pyplot``) so nothing is
    registered in the global figure manager — safe to call repeatedly in a
    long-running server without leaking figures."""
    from matplotlib.figure import Figure

    drawable = [p for p in panels if p.series]
    if not drawable:
        fig = Figure(figsize=(width_in, 2.0), dpi=dpi)
        ax = fig.subplots()
        ax.text(0.5, 0.5, "No panels selected, or no data in range.",
                ha="center", va="center", color="0.4")
        ax.axis("off")
        return fig

    n = len(drawable)
    fig = Figure(figsize=(width_in, panel_height_in * n), dpi=dpi)
    axes = list(fig.subplots(n, 1, sharex=True, squeeze=False)[:, 0])
    for ax, panel in zip(axes, drawable):
        for s in panel.series:
            ax.plot(s.x, s.y, color=s.color, lw=1.3, label=s.label)
        ax.set_ylabel(panel.ylabel, fontsize=9)
        ax.grid(True, color="0.88", lw=0.6)
        ax.tick_params(labelsize=8)
        ax.margins(x=0.01)
        # Legend only when it disambiguates (more than one line in the panel).
        if len(panel.series) > 1:
            ncol = 1 if len(panel.series) <= 4 else 2
            ax.legend(fontsize=6.5, frameon=False, loc="best", ncol=ncol)
    axes[-1].set_xlabel(x_label, fontsize=9)
    if title:
        fig.suptitle(title, fontsize=11, y=0.995)
    try:
        fig.align_ylabels(axes)
    except Exception:  # noqa: BLE001 — purely cosmetic alignment; never block the export
        pass
    fig.tight_layout()
    return fig


def figure_bytes(fig, fmt: str = "pdf") -> io.BytesIO:
    """Serialise a figure to an in-memory buffer (``pdf``/``svg`` = vector)."""
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight")
    buf.seek(0)
    return buf
