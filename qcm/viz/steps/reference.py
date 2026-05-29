"""Reference focus: highlight the zero/reference window + baseline helpers."""
from __future__ import annotations

import panel as pn

from ..components import hint
from ._base import BaseStep


class ReferenceStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("baseline")

    def secondary_panel(self):
        return pn.Column(
            hint("Pick a quiet, stable window before the experiment changes. "
                 "Drag on the plot (brush targets the reference range here).", tone="info"),
            pn.bind(self.controls.zero_reference_readout,
                    self.controls.t_range, self.controls.baseline_range),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
