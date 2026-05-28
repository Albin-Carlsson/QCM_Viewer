"""Top-level Panel layout assembly."""
from __future__ import annotations

import panel as pn

from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .pages import ExplorePage, OverviewPage, SweepPage
from .state import RunInfo
from .theme import ACCENT, HEADER_BG


class ViewerLayout:
    def __init__(self, run, info: RunInfo, controls: ViewerControls, data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

    def header(self) -> pn.Column:
        overtones = ", ".join(f"n={n}" for _, n in sorted(self.info.orders.items()))
        return pn.Column(
            pn.pane.Markdown(
                f"## `{self.info.run_id}`\n"
                f"**{self.info.span_s:.1f} s** · **{len(self.info.groups)} overtones** ({overtones}) · "
                f"**{self.info.n_sweeps} sweeps** · {self.info.rows} rows"
            ),
            sizing_mode="stretch_width",
        )

    def sidebar(self):
        c = self.controls
        title = pn.pane.Markdown(
            "### QCM Viewer\n"
            "Global setup only. Range, statistics, and saved-region controls live on the pages where they are used.",
            sizing_mode="stretch_width",
        )
        overtones = pn.Card(
            c.group_select,
            title="Overtones",
            collapsed=False,
            sizing_mode="stretch_width",
        )
        exports = pn.Card(
            c.save_state_button,
            self.actions.export_data_dl,
            pn.pane.Markdown("<small>Notebook export lives on Analyze so it can use the current range or a saved region.</small>"),
            title="Save & export",
            collapsed=False,
            sizing_mode="stretch_width",
        )
        advanced = pn.Card(
            c.orders_text,
            pn.bind(c.orders_readout, c.orders_text),
            title="Advanced",
            collapsed=True,
            sizing_mode="stretch_width",
        )
        return pn.Column(title, overtones, exports, advanced, c.status, sizing_mode="stretch_width")

    def tabs(self):
        overview = OverviewPage(self.controls, self.data, self.actions).view()
        explore = ExplorePage(self.controls, self.data, self.actions).view()
        sweep = SweepPage(self.controls, self.data, self.actions).view()
        return pn.Tabs(("Overview", overview), ("Analyze", explore), ("Sweep Inspector", sweep), dynamic=False, sizing_mode="stretch_width")

    def view(self):
        return pn.template.FastListTemplate(
            title="QCM Viewer",
            theme="dark",
            theme_toggle=False,
            accent_base_color=ACCENT,
            header_background=HEADER_BG,
            sidebar=[self.sidebar()],
            main=[pn.Column(self.header(), self.tabs(), sizing_mode="stretch_width", css_classes=["main-wrap"])],
            main_layout=None,
            sidebar_width=280,
            raw_css=[
                """
                :root { color-scheme: dark; }
                .main { max-width: 100vw !important; overflow-x: hidden !important; }
                .main-wrap { width: 100% !important; max-width: 100% !important; }
                .bk-card { max-width: 100% !important; }
                .bk-card-header { font-weight: 700; }
                .sidebar .bk-card { border-radius: 14px; margin-bottom: 10px; }
                .sidebar .markdown { line-height: 1.35; }
                .plot-controls { padding: 0 4px 8px 4px; max-width: 100%; }
                .bk-root .bk-input-group { max-width: 100%; }
                .bk-input, .bk-input-group input { min-width: 0 !important; }
                .tabulator { max-width: 100% !important; }
                @media (max-width: 900px) {
                  .sidenav { width: 240px !important; }
                  .main { padding-left: 8px !important; padding-right: 8px !important; }
                }
                """
            ],
        )
