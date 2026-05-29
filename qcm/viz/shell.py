"""Workbench shell.

Owns the persistent triad (anchor plot + selection bar + live stats) and a
focus rail that swaps the secondary panel and re-targets the plot brush. All
analysis state stays in the single ViewerControls instance; ``focus`` is
transient UI state held here.
"""
from __future__ import annotations

import panel as pn

from . import nav
from .actions import ViewerActions
from .components import pill, section_title
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
    """Assemble the workbench without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

        self.focus = pn.widgets.IntInput(value=0, visible=False)
        # Back-compat alias: existing tests/scripts set shell.step.value.
        self.step = self.focus
        self.drawer_open = pn.widgets.Checkbox(value=False, visible=False)

        self._steps = {
            "review": ReviewStep(controls, data, actions),
            "reference": ReferenceStep(controls, data, actions),
            "phases": PhasesStep(controls, data, actions),
            "quantify": QuantifyStep(controls, data, actions),
            "report": ReportStep(controls, data, actions),
        }
        self._qc = QCDrawer(controls, data, actions)
        self.focus.param.watch(self._on_focus_change, "value")
        self.controls.brush_mode.value = nav.brush_target_for_step("review")

    # -- reactions --------------------------------------------------------
    def _on_focus_change(self, event) -> None:
        self.controls.brush_mode.value = nav.brush_target_for_step(nav.step_id(int(event.new)))

    def _go(self, index: int):
        def handler(_event=None):
            self.focus.value = nav.clamp_step(index)
        return handler

    def _open_drawer(self, _event=None) -> None:
        self.drawer_open.value = True

    def _close_drawer(self, _event=None) -> None:
        self.drawer_open.value = False

    def _active_step(self, active):
        return self._steps[nav.step_id(int(active))]

    # -- persistent regions ----------------------------------------------
    def context_bar(self):
        inspect = pn.widgets.Button(name="Inspect raw sweeps", button_type="default", icon="microscope")
        inspect.on_click(self._open_drawer)
        meta = pill("Duration", f"{self.info.span_s:,.0f} s") + pill("Channels", str(len(self.info.groups)))
        readout = pn.bind(self.controls.zero_reference_summary,
                          self.controls.t_range, self.controls.baseline_range)
        return pn.Row(
            pn.pane.HTML(f"<div class='qcm-run-id'>{self.info.run_id}</div>", margin=0),
            pn.pane.HTML(meta, margin=0),
            self.controls.compact_channel_controls(),
            pn.layout.HSpacer(),
            readout,
            inspect,
            self.controls.save_state_button,
            self.controls.status,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-context-bar"],
        )

    def focus_rail(self):
        def render(active: int):
            active = nav.clamp_step(int(active))
            buttons = []
            for i, step in enumerate(nav.STEPS):
                btn = pn.widgets.Button(
                    name=f"{i + 1}. {step.label}",
                    button_type="primary" if i == active else "default",
                    sizing_mode="stretch_width",
                )
                btn.on_click(self._go(i))
                buttons.append(btn)
            return pn.Column(*buttons, margin=0, sizing_mode="stretch_width")
        return pn.Column(
            pn.bind(render, self.focus),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-focus-rail"],
        )

    def anchor(self):
        def render(active, *_):
            return self._active_step(active).anchor_plot()
        return pn.bind(
            render, self.focus,
            *self.controls.explore_inputs,
            self.controls.mark_range.param.value_throttled,
            self.controls.analysis_region_select,
            self.controls.annotation_version,
            self.controls.plot_reset_version,
        )

    def selection_bar(self):
        tools = pn.Column(
            self.controls.quantity_select,
            self.controls.brush_mode,
            pn.bind(self.controls.draw_mode_status, self.controls.brush_mode),
            pn.Row(self.controls.plot_reset_button(), self.controls.use_selection_as_baseline,
                   margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
            margin=0, sizing_mode="stretch_width",
        )
        return pn.Row(
            self.controls.current_range_compact(),
            self.controls.zero_reference_controls(),
            tools,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selection-bar"],
        )

    def live_stats(self):
        body = pn.bind(lambda *_: self._steps["review"].current_range_summary_cards(),
                       *self.controls.signal_inputs)
        return pn.Column(
            section_title("Live statistics", eyebrow="current range"),
            body, margin=0, sizing_mode="stretch_width", css_classes=["qcm-stats"],
        )

    def secondary(self):
        def render(active):
            return self._active_step(active).secondary_panel()
        return pn.bind(render, self.focus)

    def drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
        panel = pn.Column(
            pn.Row(pn.pane.HTML("<b>Raw sweep / QC inspection</b>", margin=0),
                   pn.layout.HSpacer(), close, margin=0, sizing_mode="stretch_width",
                   css_classes=["qcm-drawer-header"]),
            self._qc.view(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        return panel

    def view(self):
        plotzone = pn.Column(
            pn.Card(self.anchor(), hide_header=True, margin=0,
                    sizing_mode="stretch_width", css_classes=["qcm-anchor"]),
            self.selection_bar(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-plotzone"],
        )
        rightzone = pn.Column(
            self.live_stats(), self.secondary(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-rightzone"],
        )
        body = pn.Row(
            self.focus_rail(), plotzone, rightzone,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-body"],
        )
        return pn.Column(
            self.context_bar(), body, self.drawer(),
            margin=0, sizing_mode="stretch_width",
            css_classes=["qcm-app"], stylesheets=[APP_CSS],
        )
