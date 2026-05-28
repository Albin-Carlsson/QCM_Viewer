"""Top-level Panel layout assembly for the QCM analysis workbench."""
from __future__ import annotations

from html import escape

import panel as pn

from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .design import APP_CSS, meta_pill
from .pages import PhaseBuilderPage, QCPage, QuantifyPage, ReportPage, RunReviewPage
from .state import RunInfo
from .theme import ACCENT, HEADER_BG


class ViewerLayout:
    """Assemble the application shell without owning analysis behavior."""

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
        channels = ", ".join(f"n={n}" for _, n in sorted(self.info.orders.items())) or "—"
        meta = "".join(
            [
                meta_pill("Duration", f"{self.info.span_s:,.1f} s"),
                meta_pill("Channels", str(len(self.info.groups))),
                meta_pill("Overtones", channels),
                meta_pill("Sweeps", f"{self.info.n_sweeps:,}"),
                meta_pill("Rows", f"{self.info.rows}"),
            ]
        )
        return pn.Column(
            pn.pane.HTML(
                "<div class='run-hero' style='border:1px solid #d8e1ee;background:#fff;border-radius:18px;"
                "padding:12px 14px;box-shadow:0 1px 2px rgba(15,23,42,.05),0 14px 34px rgba(15,23,42,.06)'>"
                "<div class='run-header-row' style='display:flex;align-items:center;justify-content:space-between;"
                "gap:16px;flex-wrap:wrap'>"
                "<div>"
                "<div class='eyebrow' style='color:#64748b;font-size:.72rem;font-weight:760;letter-spacing:.075em;text-transform:uppercase'>QCM analysis workbench</div>"
                f"<div class='run-title' style='font-size:1.48rem;line-height:1.1;font-weight:810;color:#0f172a'>{escape(str(self.info.run_id))}</div>"
                "</div>"
                f"<div class='run-meta-inline' style='display:flex;gap:8px;flex-wrap:wrap;align-items:stretch;justify-content:flex-end'>{meta}</div>"
                "</div>"
                "</div>",
                margin=0,
                sizing_mode="stretch_width",
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["run-header"],
        )

    def global_controls(self):
        c = self.controls
        return pn.Row(
            pn.Card(
                pn.bind(c.channels_readout, c.group_select),
                c.group_select,
                c.show_all_channels_button,
                title="Channels",
                collapsible=True,
                collapsed=False,
                margin=0,
                sizing_mode="stretch_width",
                css_classes=["channels-card"],
            ),
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["global-controls-row"],
        )

    def tabs(self):
        return pn.Tabs(
            ("Review", RunReviewPage(self.controls, self.data, self.actions).view()),
            ("Phases & Compare", PhaseBuilderPage(self.controls, self.data, self.actions).view()),
            ("Quantify", QuantifyPage(self.controls, self.data, self.actions).view()),
            ("QC & Raw Sweeps", QCPage(self.controls, self.data, self.actions).view()),
            ("Report", ReportPage(self.controls, self.data, self.actions).view()),
            dynamic=True,
            sizing_mode="stretch_width",
            css_classes=["workflow-tabs"],
        )

    def view(self):
        return pn.template.FastListTemplate(
            title="QCM Analysis Workbench",
            theme="default",
            theme_toggle=False,
            accent_base_color=ACCENT,
            header_background=HEADER_BG,
            sidebar=[],
            main=[
                pn.Column(
                    self.header(),
                    self.global_controls(),
                    self.tabs(),
                    margin=0,
                    sizing_mode="stretch_width",
                    css_classes=["main-wrap"],
                )
            ],
            main_layout=None,
            sidebar_width=0,
            raw_css=[APP_CSS],
        )
