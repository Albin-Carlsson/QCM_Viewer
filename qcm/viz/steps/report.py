"""Report focus: overview anchor + export controls."""
from __future__ import annotations

import panel as pn

from ._base import BaseStep


class ReportStep(BaseStep):
    def anchor_plot(self):
        return self.overview_anchor("current")

    def secondary_panel(self):
        return pn.Card(
            self.controls.marker_select,
            self.actions.export_data_dl,
            self.actions.export_nb_dl,
            title="Export", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-secondary"],
        )
