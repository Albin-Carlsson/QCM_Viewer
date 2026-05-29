"""Workbench shell — three-page redesign.

Layout:

    sidebar (brand · nav · run-info · help) | content (topbar + active page)

The three pages are Data (explore & visualize), Results (mass/charge/MPE
dashboard), and Report (export). All analysis state lives in the single
:class:`ViewerControls` instance; the shell only holds transient UI state
(``mode`` and ``drawer_open``).

Mounting rule: a Panel widget singleton (``t_range``, ``group_select``, the
overtone checkboxes, ``marker_select`` …) may appear in only one place in the
layout tree. Each persistent widget below is mounted in exactly one page, and
everything that merely *reacts* to a widget references it through ``pn.bind``
(which does not mount it). The pages are built once and toggled with ``visible``.
"""
from __future__ import annotations

from html import escape

import panel as pn

from . import echem, nav
from .actions import ViewerActions
from .components import (
    brand,
    nav_sublabel,
    phase_list,
    phase_row,
    run_info_table,
    section_title,
)
from .controls import ViewerControls
from .data import QCMViewData
from .state import RunInfo
from .theme import ELECTRODE_AREA_CM2, HERO_HEIGHT
from .steps.phases import PhasesStep
from .steps.qc_drawer import QCDrawer
from .steps.quantify import QuantifyStep
from .steps.report import ReportStep
from .steps.results import ResultsStep
from .steps.review import ReviewStep

_US = 1_000_000

_PHASE_COLORS = {
    "baseline": "#22c55e",
    "phase": "#7c3aed",
    "buffer": "#0ea5e9",
    "sample": "#f59e0b",
    "regeneration": "#ec4899",
    "artifact": "#ef4444",
    "exclude": "#64748b",
    "note": "#14b8a6",
}
_PHASE_DEFAULT = "#7c3aed"


class ViewerShell:
    """Assemble the three-page workbench without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions

        self.mode = pn.widgets.IntInput(value=0, visible=False)
        # Back-compat aliases for tests/scripts that poke shell.step / shell.focus.
        self.focus = self.mode
        self.step = self.mode
        self.drawer_open = pn.widgets.Checkbox(value=False, visible=False)

        # Step objects supply the heavy rendering; the shell arranges them.
        self._data_plot = ReviewStep(controls, data, actions)   # owns the hero (unified_anchor)
        self._phases = PhasesStep(controls, data, actions)
        self._quantify = QuantifyStep(controls, data, actions)
        self._results = ResultsStep(controls, data, actions)
        self._report = ReportStep(controls, data, actions)
        self._qc = QCDrawer(controls, data, actions)

        # Build persistent pieces once.
        self._page_data = self._build_data_page()
        self._page_results = self._build_results_page()
        self._page_report = self._build_report_page()
        self._pages = {"data": self._page_data, "results": self._page_results, "report": self._page_report}

        # Exactly one page is mounted at a time. Swapping ``objects`` (rather than
        # toggling ``visible`` on three always-mounted pages) guarantees the pages
        # are truly separate and avoids any leftover layout from a hidden page.
        self._page_host = pn.Column(margin=0, sizing_mode="stretch_width", css_classes=["qcm-pagehost"])

        self._cached_topbar = self._build_topbar()
        self._cached_sidebar = self._build_sidebar()
        self._cached_drawer = self._build_drawer()

        self.mode.param.watch(self._on_mode_change, "value")
        self._sync_pages(self.mode.value)

    # -- reactions --------------------------------------------------------
    def _on_mode_change(self, event) -> None:
        self._sync_pages(int(event.new))

    def _sync_pages(self, index: int) -> None:
        active = nav.mode_id(index)
        self._page_host.objects = [self._pages[active]]

    def _go(self, index: int):
        def handler(_event=None):
            self.mode.value = nav.clamp_mode(index)
        return handler

    def _open_drawer(self, _event=None) -> None:
        self.drawer_open.value = True

    def _close_drawer(self, _event=None) -> None:
        self.drawer_open.value = False

    # =====================================================  sidebar
    def _run_info_card(self):
        meta = {}
        try:
            meta = dict(self.run.manifest.metadata)
        except Exception:
            pass
        overtones = ", ".join(str(n) for n in sorted(set(self.info.orders.values()))) or "—"
        rows = [("Run", str(self.info.run_id))]
        date = meta.get("date") or meta.get("started_at") or meta.get("timestamp")
        if date:
            rows.append(("Date", str(date)))
        rows += [
            ("Duration", f"{self.info.span_s:,.2f} s"),
            ("Channels", str(len(self.info.groups))),
            ("Overtones", overtones),
            ("Electrode area", f"{ELECTRODE_AREA_CM2:g} cm²"),
        ]
        if meta.get("sample_rate") is not None:
            rows.append(("Sample rate", f"{meta['sample_rate']} Hz"))
        if meta.get("temperature") is not None:
            rows.append(("Temperature", f"{meta['temperature']} °C"))
        rows.append(("Sweeps", str(self.info.n_sweeps)))
        return pn.Card(
            run_info_table(rows),
            title="Run info", collapsible=True, collapsed=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-runinfo"],
        )

    def _nav(self):
        def render(active: int):
            active = nav.clamp_mode(int(active))
            items = []
            for i, mode in enumerate(nav.MODES):
                btn = pn.widgets.Button(name=mode.label, icon=mode.icon,
                                        button_type="default", sizing_mode="stretch_width")
                btn.on_click(self._go(i))
                classes = ["qcm-nav-item"] + (["is-active"] if i == active else [])
                items.append(pn.Column(btn, nav_sublabel(mode.sublabel),
                                       margin=0, sizing_mode="stretch_width", css_classes=classes))
            return pn.Column(*items, margin=0, sizing_mode="stretch_width", css_classes=["qcm-nav"])
        return pn.bind(render, self.mode)

    def _build_sidebar(self):
        help_btn = pn.widgets.Button(name="Help & shortcuts", icon="help", button_type="default",
                                     sizing_mode="stretch_width")
        help_btn.on_click(lambda _e: self.actions.notify(
            "Drag on the plot to set the active range · click a point to load that sweep · "
            "use Selection mode to switch what a drag targets.", "info"))
        return pn.Column(
            brand("QCM-D Viewer"),
            self._nav(),
            pn.layout.Spacer(css_classes=["qcm-sidebar-spacer"]),
            self._run_info_card(),
            pn.Column(help_btn, margin=0, sizing_mode="stretch_width", css_classes=["qcm-help"]),
            margin=0, css_classes=["qcm-sidebar"],
        )

    # =====================================================  topbar
    def _build_topbar(self):
        info = pn.pane.HTML(
            "<div class='qcm-runline'>"
            f"<span class='run'>Run {escape(str(self.info.run_id))}</span>"
            "</div>",
            margin=0, sizing_mode="stretch_width",
        )
        export_btn = pn.widgets.Button(name="Export", icon="download", button_type="primary")
        export_btn.on_click(self._go(nav.mode_index("report")))
        inspect = pn.widgets.Button(name="Inspect raw sweeps", icon="microscope", button_type="default")
        inspect.on_click(self._open_drawer)
        return pn.Row(
            info,
            self.controls.save_state_button, export_btn, inspect,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-topbar"],
        )

    # =====================================================  DATA page
    def _data_hero(self):
        def render(mode_val, *_):
            window = mode_val if mode_val in ("current", "reference", "mark") else "current"
            return self._data_plot.unified_anchor(window=window, height=HERO_HEIGHT)
        body = pn.bind(
            render,
            self.controls.brush_mode,
            *self.controls.explore_inputs,
            self.controls.quantity_select_right,
            self.controls.show_phases,
            self.controls.zero_line,
            self.controls.show_cycles,
            self.controls.mark_range.param.value_throttled,
            self.controls.mark_start,
            self.controls.mark_end,
            self.controls.annotation_version,
            self.controls.plot_reset_version,
        )
        # The active-range slider rides flush under the plot inside the same card,
        # matching the plot width so it reads as the plot's own range scrubber.
        return pn.Card(
            body,
            self.controls.plot_range_slider(),
            hide_header=True, margin=0, sizing_mode="stretch_width", css_classes=["qcm-anchor"],
        )

    def _rail_signals(self):
        return self.controls.overtone_controls()

    def _rail_phases(self):
        def body(*_):
            rows = []
            for ann in self.data.annotations():
                start = (ann.t0 - self.info.t0_us) / _US
                kind = ann.tags[0] if ann.tags else "phase"
                color = _PHASE_COLORS.get(kind, _PHASE_DEFAULT)
                if ann.t1 is not None:
                    end = (ann.t1 - self.info.t0_us) / _US
                    when = f"{start:,.2f} – {end:,.2f} s"
                else:
                    when = f"{start:,.2f} s"
                rows.append(phase_row(color, ann.label or kind.title(), when))
            return phase_list(rows)
        edit = pn.Card(
            pn.bind(lambda *_: self._phases.phases_table(), self.controls.annotation_version),
            title="Edit phases", collapsible=True, collapsed=True, margin=0,
            sizing_mode="stretch_width",
        )
        return pn.Card(
            pn.bind(body, self.controls.annotation_version),
            edit,
            title="Phases", collapsible=True, collapsed=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-phases-card"],
        )

    def _rail_live_stats(self):
        table = pn.bind(
            lambda *_: self._quantify.selected_target_summary_table(),
            *self.controls.explore_inputs,
            self.controls.analysis_region_select,
            self.controls.annotation_version,
        )
        return pn.Card(
            pn.Row(
                pn.pane.HTML("<div class='eyebrow'>Show</div>", margin=0),
                self.controls.analysis_region_select,
                margin=0, sizing_mode="stretch_width",
            ),
            table,
            title="Live statistics", collapsible=True, collapsed=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-stats"],
        )

    def _build_data_page(self):
        try:
            has_cycles = self.data.has_echem() and len(echem.cycle_values(self.data.echem_waveform())) > 1
        except Exception:
            has_cycles = False
        plotzone = pn.Column(
            self._data_hero(),
            self.controls.selection_cards(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-plotzone"],
        )
        rail = pn.Column(
            self._rail_signals(),
            self._rail_phases(),
            self._rail_live_stats(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-rail"],
        )
        body = pn.Row(plotzone, rail, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-data-body"])
        # The plot-settings strip rides directly under the topbar as a secondary
        # header spanning the full content width (plot + rail).
        return pn.Column(
            self.controls.data_toolbar(include_cycles=has_cycles),
            body,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-data"],
        )

    # =====================================================  RESULTS page
    def _build_results_page(self):
        return self._results.page()

    # =====================================================  REPORT page
    def _build_report_page(self):
        return self._report.page()

    # =====================================================  drawer
    def _build_drawer(self):
        close = pn.widgets.Button(name="Close ✕", button_type="default")
        close.on_click(self._close_drawer)
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

    # =====================================================  assembly
    def view(self):
        content = pn.Column(
            self._cached_topbar,
            self._page_host,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-content"],
        )
        shell = pn.Row(
            self._cached_sidebar, content,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-shell"],
        )
        return pn.Column(
            shell, self._cached_drawer,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-app"],
        )
