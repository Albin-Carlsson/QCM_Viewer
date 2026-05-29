"""Workbench shell.

Owns the persistent triad (anchor plot + selection bar + live stats) and a
focus rail that swaps the secondary panel and re-targets the plot brush. All
analysis state stays in the single ViewerControls instance; ``focus`` is
transient UI state held here.
"""
from __future__ import annotations

from html import escape

import panel as pn

from . import nav
from .actions import ViewerActions
from .components import section_title
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

        # Build once so each call to view() reuses the same Panel objects.
        # Widget singletons (t_range, group_select, etc.) can live in only one
        # place in the layout tree; rebuilding these on every view() call would
        # mount them in both the persistent shell and the QC drawer simultaneously.
        self._cached_context_bar = self._build_context_bar()
        self._cached_right_stats = self.live_stats()
        self._cached_phase_inline_table = pn.bind(
            lambda *_: self._steps["phases"].phases_table(),
            self.controls.annotation_version,
        )
        self._sync_stats_placement(self.focus.value)
        self._cached_selection_bar = self._build_selection_bar()
        self._cached_drawer = self._build_drawer()

    # -- reactions --------------------------------------------------------
    def _on_focus_change(self, event) -> None:
        self.controls.brush_mode.value = nav.brush_target_for_step(nav.step_id(int(event.new)))
        self._sync_stats_placement(event.new)

    def _sync_stats_placement(self, active: int) -> None:
        if not hasattr(self, "_cached_right_stats") or not hasattr(self, "_cached_phase_inline_table"):
            return
        in_phases = nav.step_id(int(active)) == "phases"
        self._cached_right_stats.visible = not in_phases
        self._cached_phase_inline_table.visible = in_phases

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
    def _build_context_bar(self):
        inspect = pn.widgets.Button(name="Inspect raw sweeps", button_type="default", icon="microscope")
        inspect.on_click(self._open_drawer)
        info = pn.pane.HTML(
            "<div class='qcm-runline'>"
            f"<span class='run'>{escape(str(self.info.run_id))}</span>"
            f"<span class='meta'>Duration: {self.info.span_s:,.0f} s</span>"
            f"<span class='meta'>Channels: {len(self.info.groups)}</span>"
            "</div>",
            margin=0,
        )
        return pn.Row(
            info,
            pn.layout.HSpacer(),
            self.controls.compact_channel_controls(),
            inspect,
            self.controls.save_state_button,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-context-bar"],
        )

    def context_bar(self):
        return self._cached_context_bar

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
            self.controls.mark_start,
            self.controls.mark_end,
            self.controls.analysis_region_select,
            self.controls.annotation_version,
            self.controls.plot_reset_version,
        )

    def _build_selection_bar(self):
        tools = pn.Column(
            self.controls.quantity_select,
            self.controls.brush_mode,
            pn.bind(self.controls.draw_mode_status, self.controls.brush_mode),
            pn.Row(self.controls.plot_reset_button(),
                   margin=0, sizing_mode="stretch_width", css_classes=["range-actions"]),
            self._cached_phase_inline_table,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selection-tools"],
        )
        return pn.Row(
            self.controls.active_range_editor(quantity_key=self.controls.quantity_select),
            tools,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-selection-bar"],
        )

    def selection_bar(self):
        return self._cached_selection_bar

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

    def below_plot(self):
        """Wide, focus-specific analysis area beneath the anchor plot.

        Heavy tables/fingerprints live here (full width) instead of the narrow
        right rail, so e.g. Quantify's statistics do not run far off the bottom.
        """
        def render(active):
            return self._active_step(active).below_plot_panel()
        return pn.bind(render, self.focus)

    def _build_drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
        # Use pn.bind so the QC view is a ParamFunction in the layout tree rather
        # than a concrete Column whose .objects the double-mount walker descends
        # into. The QC drawer shares persistent widget singletons (t_range,
        # group_select, …) with the selection bar and context bar; embedding it as
        # a live object would put those singletons in two places simultaneously.
        qc_content = pn.bind(lambda _open: self._qc.view() if _open else pn.Spacer(height=0),
                             self.drawer_open)
        panel = pn.Column(
            pn.Row(pn.pane.HTML("<b>Raw sweep / QC inspection</b>", margin=0),
                   pn.layout.HSpacer(), close, margin=0, sizing_mode="stretch_width",
                   css_classes=["qcm-drawer-header"]),
            qc_content,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        return panel

    def drawer(self):
        return self._cached_drawer

    def view(self):
        plotzone = pn.Column(
            pn.Card(self.anchor(), hide_header=True, margin=0,
                    sizing_mode="stretch_width", css_classes=["qcm-anchor"]),
            self.selection_bar(),
            self.below_plot(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-plotzone"],
        )
        rightzone = pn.Column(
            self._cached_right_stats, self.secondary(),
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
