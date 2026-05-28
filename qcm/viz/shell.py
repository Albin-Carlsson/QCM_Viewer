"""Stepper shell: context bar, step navigator, step canvas, footer, QC drawer."""
from __future__ import annotations

import panel as pn

from . import nav
from .actions import ViewerActions
from .controls import ViewerControls
from .data import QCMViewData
from .design import APP_CSS
from .state import RunInfo
from .steps.phases import PhasesStep
from .steps.qc_drawer import QCDrawer
from .steps.quantify import QuantifyStep
from .steps.reference import ReferenceStep
from .steps.report import ReportStep
from .steps.review import ReviewStep


class ViewerShell:
    """Assemble the guided stepper UI without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

        self.step = pn.widgets.IntInput(value=0, visible=False)
        self.drawer_open = pn.widgets.Checkbox(value=False, visible=False)

        self._steps = {
            "review": ReviewStep(controls, data, actions),
            "reference": ReferenceStep(controls, data, actions),
            "phases": PhasesStep(controls, data, actions),
            "quantify": QuantifyStep(controls, data, actions),
            "report": ReportStep(controls, data, actions),
        }
        self._qc = QCDrawer(controls, data, actions)
        self.step.param.watch(self._on_step_change, "value")
        # Initialize the brush target for the first step.
        self.controls.brush_mode.value = nav.brush_target_for_step("review")

    # -- reactions --------------------------------------------------------
    def _on_step_change(self, event) -> None:
        self.controls.brush_mode.value = nav.brush_target_for_step(nav.step_id(int(event.new)))

    def _go(self, index: int):
        def handler(_event=None):
            self.step.value = nav.clamp_step(index)
        return handler

    def _open_drawer(self, _event=None) -> None:
        self.drawer_open.value = True

    def _close_drawer(self, _event=None) -> None:
        self.drawer_open.value = False

    # -- regions ----------------------------------------------------------
    def context_bar(self):
        """Compact persistent toolbar.

        The old run metadata block made the top of the app visually heavy and
        repeated information that is not needed while analysing. Keep only the
        controls that help orient the current workflow.
        """
        inspect_btn = pn.widgets.Button(name="Inspect raw sweeps", button_type="default", icon="microscope")
        inspect_btn.on_click(self._open_drawer)

        return pn.Row(
            pn.layout.HSpacer(),
            inspect_btn,
            margin=0,
            sizing_mode="stretch_width",
            css_classes=["qcm-context-bar", "is-compact", "top-tools-only"],
        )

    def navigator(self):
        def render(active: int):
            active = nav.clamp_step(int(active))
            buttons = []
            for i, step in enumerate(nav.STEPS):
                btn = pn.widgets.Button(
                    name=f"{i + 1}. {step.label}",
                    button_type="primary" if i == active else "default",
                )
                btn.on_click(self._go(i))
                buttons.append(btn)
            return pn.Row(*buttons, margin=0, sizing_mode="stretch_width", css_classes=["qcm-step-nav"])
        return pn.bind(render, self.step)

    def step_canvas(self):
        def render(active: int):
            idx = nav.clamp_step(int(active))
            step = nav.STEPS[idx]
            return pn.Column(
                self._steps[step.id].view(),
                margin=0, sizing_mode="stretch_width",
            )
        return pn.bind(render, self.step)

    def footer(self):
        back = pn.widgets.Button(name="‹ Back", button_type="default")
        nxt = pn.widgets.Button(name="Next ›", button_type="primary")
        back.on_click(lambda e: setattr(self.step, "value", nav.prev_step(int(self.step.value))))
        nxt.on_click(lambda e: setattr(self.step, "value", nav.next_step(int(self.step.value))))
        return pn.Row(back, pn.layout.HSpacer(), nxt, margin=0, sizing_mode="stretch_width", css_classes=["qcm-footer"])

    def drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
        panel = pn.Column(
            pn.Row(
                pn.pane.HTML("<b>Raw sweep / QC inspection</b>", margin=0), pn.layout.HSpacer(), close,
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer-header"],
            ),
            self._qc.view(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        return panel

    def view(self):
        return pn.Column(
            self.context_bar(),
            self.navigator(),
            self.step_canvas(),
            self.footer(),
            self.drawer(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-shell"],
            stylesheets=[APP_CSS],
        )
