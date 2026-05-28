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
    def __init__(
        self,
        run,
        info: RunInfo,
        controls: ViewerControls,
        data: QCMViewData,
        actions: ViewerActions,
    ):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

    def header(self) -> pn.Column:
        channels = ", ".join(f"n={n}" for _, n in sorted(self.info.orders.items()))
        return pn.Column(
            pn.pane.Markdown(
                f"## `{self.info.run_id}`\n"
                f"**{self.info.span_s:.1f} s** · **{len(self.info.groups)} channels** ({channels}) · "
                f"**{self.info.n_sweeps} sweeps** · {self.info.rows} rows",
                margin=0,
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["run-header"],
        )

    def sidebar(self):
        c = self.controls
        title = pn.pane.Markdown(
            "### QCM Viewer\n"
            "Global setup only. Range, statistics, and saved-region controls live on their pages.",
            margin=0,
            sizing_mode="stretch_width",
        )
        overtones = pn.Card(
            c.group_select,
            c.show_all_channels_button,
            title="Visible channels",
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        exports = pn.Card(
            c.save_state_button,
            self.actions.export_data_dl,
            pn.pane.Markdown(
                "<small>Notebook export lives on Analyze so it can use the current range or a saved region."
                "</small>",
                margin=0,
            ),
            title="Save & export",
            collapsed=False,
            margin=0,
            sizing_mode="stretch_width",
        )
        advanced = pn.Card(
            c.orders_text,
            pn.bind(c.orders_readout, c.orders_text),
            title="Advanced",
            collapsed=True,
            margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Column(
            title,
            overtones,
            exports,
            advanced,
            c.status,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["sidebar-wrap"],
        )

    def tabs(self):
        overview = OverviewPage(self.controls, self.data, self.actions).view()
        explore = ExplorePage(self.controls, self.data, self.actions).view()
        sweep = SweepPage(self.controls, self.data, self.actions).view()
        return pn.Tabs(
            ("Overview", overview),
            ("Analyze", explore),
            ("Sweep Inspector", sweep),
            dynamic=False,
            sizing_mode="stretch_width",
        )

    def view(self):
        return pn.template.FastListTemplate(
            title="QCM Viewer",
            theme="dark",
            theme_toggle=False,
            accent_base_color=ACCENT,
            header_background=HEADER_BG,
            sidebar=[self.sidebar()],
            main=[
                pn.Column(
                    self.header(),
                    self.tabs(),
                    margin=0,
                    sizing_mode="stretch_width",
                    css_classes=["main-wrap"],
                )
            ],
            main_layout=None,
            sidebar_width=280,
            raw_css=[
                """
                :root { color-scheme: dark; }
                html, body { margin: 0 !important; }
                body { overscroll-behavior-y: none; }
                .main {
                  max-width: 100vw !important;
                  min-height: 0 !important;
                  overflow-x: hidden !important;
                  padding: 10px 14px 0 14px !important;
                }
                .main-wrap {
                  width: 100% !important;
                  max-width: 100% !important;
                  min-height: 0 !important;
                  margin: 0 !important;
                  padding: 0 !important;
                  gap: 8px !important;
                }
                .viewer-page,
                .compact-section,
                .plot-controls,
                .sidebar-wrap {
                  gap: 6px !important;
                }
                .overview-page {
                  min-height: 0 !important;
                  margin-bottom: 0 !important;
                  padding-bottom: 0 !important;
                }
                .run-header .markdown h2,
                .run-header .markdown p,
                .main .markdown p {
                  margin-top: 0 !important;
                  margin-bottom: 4px !important;
                }
                .bk-card {
                  max-width: 100% !important;
                  border-radius: 8px !important;
                }
                .viewer-card {
                  margin: 0 0 8px 0 !important;
                }
                .bk-card-header {
                  min-height: 30px !important;
                  padding: 6px 10px !important;
                  font-weight: 700;
                }
                .bk-card-body {
                  padding: 8px 10px !important;
                }
                .sidebar {
                  padding-top: 8px !important;
                }
                .sidebar .bk-card {
                  border-radius: 8px !important;
                  margin-bottom: 8px !important;
                }
                .sidebar .markdown {
                  line-height: 1.25;
                }
                .plot-controls {
                  padding: 0 !important;
                  margin: 0 !important;
                  max-width: 100%;
                }
                .range-row,
                .range-actions {
                  gap: 8px !important;
                }
                .analyze-controls {
                  padding-bottom: 2px !important;
                }
                .compact-range-controls,
                .compact-reference-controls {
                  gap: 4px !important;
                }
                .paired-ranges .bk-input-group,
                .analyze-controls .bk-input-group,
                .paired-ranges .bk-form,
                .analyze-controls .bk-form,
                .paired-ranges .bk-slider-title {
                  margin-bottom: 0 !important;
                }
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
