"""Report step: summary and exports."""
from __future__ import annotations

import panel as pn

from ._base import BaseStep


class ReportStep(BaseStep):
    """Simple report/export surface using existing export capabilities."""

    def view(self):
        return pn.Column(
            self.panel(self.current_range_summary_cards, *self.controls.explore_inputs, title="Summary"),
            pn.Card(
                self.controls.marker_select,
                self.actions.export_data_dl,
                self.actions.export_nb_dl,
                self.controls.save_state_button,
                self.controls.status,
                title="Export",
                collapsible=True,
                collapsed=False,
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["workbench-page", "viewer-page"],
        )
