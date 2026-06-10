"""Data-page hero: the full-run configurable analysis plot.

The shell mounts this step and calls :meth:`BaseStep.unified_anchor` directly to
render the hero figure; all other Data-page panels (signals, phases, statistics)
are assembled by the shell from :class:`ViewerControls`.
"""
from __future__ import annotations

from ._base import BaseStep


class ReviewStep(BaseStep):
    """Owns the Data-page hero plot via the shared ``unified_anchor`` builder."""
