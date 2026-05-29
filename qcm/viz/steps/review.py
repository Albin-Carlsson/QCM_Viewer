"""Overview focus: full-run QCM-D anchor + channel/advanced controls."""
from __future__ import annotations

import panel as pn

from ..components import hint
from ._base import BaseStep


class ReviewStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("current")

    def secondary_panel(self):
        return pn.Column(
            hint("Inspect the full experiment and choose the analysis range by "
                 "dragging on the plot.", tone="info"),
            self.controls.advanced_controls(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )

    def view(self):
        return pn.Column(self.anchor_plot(), self.secondary_panel(),
                         margin=0, sizing_mode="stretch_width")
