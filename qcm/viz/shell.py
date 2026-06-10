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

import tempfile
from html import escape
from pathlib import Path

import panel as pn

from qcm.profiles import detect_profile, import_run, profile_kind

from . import echem, nav
from .actions import ViewerActions
from .design import ACCENT_BUTTON_STYLESHEET
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
from .theme import ELECTRODE_AREA_CM2, HERO_HEIGHT, area_to_diameter_mm
from .tokens import (
    PHASE_COLORS as _PHASE_COLORS,
    PHASE_DEFAULT as _PHASE_DEFAULT,
    color_for_run,
)
from .steps.phases import PhasesStep
from .steps.qc_drawer import QCDrawer
from .steps.quantify import QuantifyStep
from .steps.report import ReportStep
from .steps.results import ResultsStep
from .steps.review import ReviewStep

_US = 1_000_000

class ViewerShell:
    """Assemble the three-page workbench without owning analysis behavior."""

    def __init__(self, run, info: RunInfo, controls: ViewerControls,
                 data: QCMViewData, actions: ViewerActions, runset=None):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.actions = actions
        self.runset = runset

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

        # Built before the sidebar so the "Add run" button can open it.
        self._run_modal = self._build_add_run_modal() if self.runset is not None else None
        self._cached_topbar = self._build_topbar()
        self._cached_sidebar = self._build_sidebar()
        self._cached_drawer = self._build_drawer()

        self.mode.param.watch(self._on_mode_change, "value")
        # When the run set changes (run added / relabelled / active switched) the
        # single-run pages must rebuild against the new active run; the mounted
        # page host is updated in place so the change shows without a reload.
        self.controls.runset_version.param.watch(self._on_runset_change, "value")
        self._sync_pages(self.mode.value)

    # -- reactions --------------------------------------------------------
    def _on_mode_change(self, event) -> None:
        self._sync_pages(int(event.new))

    def _on_runset_change(self, _event=None) -> None:
        self._page_data = self._build_data_page()
        self._page_results = self._build_results_page()
        self._page_report = self._build_report_page()
        self._pages = {"data": self._page_data, "results": self._page_results, "report": self._page_report}
        self._sync_pages(self.mode.value)
        # Persist the workspace (paths + labels + active) on every set change.
        self.runset.save_session()

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
        # Reflect the active run: rebuild when the run set / active run changes.
        return pn.bind(self._run_info_card_body, self.controls.runset_version)

    def _run_info_card_body(self, *_):
        meta = {}
        try:
            meta = dict(self.run.manifest.metadata)
        except Exception:
            pass
        overtones = ", ".join(str(n) for n in sorted(set(self.info.orders.values()))) or "—"
        # The active run's configured area (falls back to the default constant).
        try:
            _area = float(self.controls.params().area_cm2)
        except Exception:
            _area = ELECTRODE_AREA_CM2
        rows = [("Run", str(self.info.run_id))]
        date = meta.get("date") or meta.get("started_at") or meta.get("timestamp")
        if date:
            rows.append(("Date", str(date)))
        rows += [
            ("Duration", f"{self.info.span_s:,.2f} s"),
            ("Channels", str(len(self.info.groups))),
            ("Overtones", overtones),
            ("Electrode area", f"{_area:.3f} cm² (⌀ {area_to_diameter_mm(_area):.1f} mm)"),
        ]
        if meta.get("sample_rate") is not None:
            rows.append(("Sample rate", f"{meta['sample_rate']} Hz"))
        if meta.get("temperature") is not None:
            rows.append(("Temperature", f"{meta['temperature']} °C"))
        # A CV's time axis is reconstructed from this rate, so make the assumption
        # (and where it came from) visible rather than silent.
        cv_rate = meta.get("cv_scan_rate_v_per_s")
        if cv_rate is not None:
            src = meta.get("cv_scan_rate_source", "")
            suffix = f" ({src})" if src else ""
            rows.append(("CV scan rate", f"{float(cv_rate) * 1000:.1f} mV/s{suffix}"))
        rows.append(("Sweeps", str(self.info.n_sweeps)))
        return pn.Card(
            run_info_table(rows),
            title="Run info", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-runinfo"],
        )

    # =====================================================  run manager
    def _bump_runset(self) -> None:
        self.controls.runset_version.value += 1

    def _runs_card(self):
        """Run-manager card: list runs (swatch · label · active), add a run."""
        if self.runset is None:
            return pn.Spacer(height=0)
        return pn.Card(
            pn.bind(self._runs_card_body, self.controls.runset_version),
            title="Runs", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-runs"],
        )

    def _runs_card_body(self, *_):
        rows = [self._run_row(slot) for slot in range(len(self.runset.runs))]
        return pn.Column(*rows, self._add_run_control(),
                         margin=0, sizing_mode="stretch_width", css_classes=["qcm-runs-body"])

    def _run_row(self, slot: int):
        is_active = slot == self.runset.active_index
        color = color_for_run(slot)
        label = pn.widgets.TextInput(
            value=self.runset.labels()[slot], margin=0, sizing_mode="stretch_width",
            css_classes=["qcm-run-label"],
        )
        label.param.watch(lambda e, s=slot: self._on_label_edit(s, e.new), "value")
        # The radio doubles as the legend key: it is tinted with the run's family
        # colour. Filled (circle-dot) = active run, which drives the single-run
        # views; an open circle picks a run. Inactive runs still show in the
        # overlay — this is not a hide toggle.
        icon = "circle-dot" if is_active else "circle"
        # Strip the button chrome so only the coloured glyph shows (no grey box to
        # butt against the card edge) and center it. Panel's button box can live on
        # the host or any button variant, so reset them all.
        reset = ("background:transparent !important;border:0 !important;"
                 "box-shadow:none !important;padding:0 !important;")
        sheet = (f":host{{{reset}}}"
                 f"button,.bk-btn,.bk-btn-default,.bk-btn-group{{{reset}"
                 f"color:{color} !important;opacity:1 !important;"
                 "display:flex;align-items:center;justify-content:center;}"
                 f"svg{{color:{color};stroke:{color};}}")
        pick = pn.widgets.Button(
            icon=icon, button_type="default", width=34, margin=0, disabled=is_active,
            stylesheets=[sheet], css_classes=["qcm-run-active" if is_active else "qcm-run-pick"],
            description=("Active run — drives the raw & report views" if is_active
                         else "Make this the active run (raw & report views)"),
        )
        if not is_active:
            pick.on_click(lambda _e, s=slot: self._on_set_active(s))
        # Fixed toggle leads so it is always visible; the label takes the rest.
        return pn.Row(pick, label, margin=0, sizing_mode="stretch_width",
                      css_classes=["qcm-run-row"] + (["is-active"] if is_active else []))

    def _add_run_control(self):
        # The directory browser is ~600px wide and would blow out the fixed
        # sidebar, so the sidebar only carries a compact button; the browser
        # itself lives in a modal (built once, mounted at the app root).
        open_btn = pn.widgets.Button(label="Add run", icon="plus", button_type="default",
                                     sizing_mode="stretch_width", css_classes=["qcm-add-run-btn"])
        open_btn.on_click(lambda _e: self._open_add_run_modal())
        return open_btn

    # Display names + the QCM-source override choices (PS profiles attach via the
    # optional pairing, not as a run source).
    _PROFILE_LABELS = {
        "standardized_csv": "Standardized QCM CSV",
        "qsoft_txt": "Qsoft .txt",
        "pstrace_cv": "PSTrace CV",
        "pstrace_cp": "PSTrace CP",
        "parquet": "Ingested run / parquet",
    }
    _OVERRIDE_OPTIONS = {
        "Auto-detect": "auto",
        "Standardized QCM CSV": "standardized_csv",
        "Qsoft .txt": "qsoft_txt",
        "Map columns (variant CSV)…": "map",
    }
    _IGNORE_ROLE = "(ignore)"
    # Canonical roles a variant column can be mapped to (Time/Fr/D per overtone).
    _CANONICAL_ROLES = [_IGNORE_ROLE] + [
        f"{role}_{n}" for n in (1, 3, 5, 7, 9, 11, 13) for role in ("Time", "Fr", "D")
    ]

    @classmethod
    def _guess_role(cls, name: str) -> str:
        """Best-guess canonical role for a variant column name (n=1 default)."""
        low = name.lower()
        if "freq" in low or "fr" in low:
            return "Fr_1"
        if "diss" in low or low.startswith("d"):
            return "D_1"
        if "time" in low or low.startswith("t"):
            return "Time_1"
        return cls._IGNORE_ROLE

    @classmethod
    def _build_rename(cls, assignments: dict[str, str]) -> dict[str, str]:
        """actual→canonical rename map from role assignments, dropping ignores."""
        return {col: role for col, role in assignments.items() if role != cls._IGNORE_ROLE}

    def _build_add_run_modal(self):
        root = str(self.runset.active.run.path.parent)
        self._run_browser = pn.widgets.FileSelector(
            directory=root, margin=0, sizing_mode="stretch_width", css_classes=["qcm-run-browser"],
        )
        self._ps_browser = pn.widgets.FileSelector(
            directory=root, margin=0, sizing_mode="stretch_width", css_classes=["qcm-run-browser"],
        )
        self._profile_override = pn.widgets.Select(
            label="Profile", options=self._OVERRIDE_OPTIONS, value="auto", sizing_mode="stretch_width",
        )
        # Holds one Select per file column while the mapping editor is shown.
        self._col_role_selects: dict[str, pn.widgets.Select] = {}
        add = pn.widgets.Button(label="Import & add", icon="plus", button_type="primary")
        add.on_click(lambda _e: self._confirm_add_run())
        detected = pn.bind(self._detected_profile_html, self._run_browser.param.value,
                           self._profile_override)
        mapping = pn.bind(self._column_mapping_editor, self._run_browser.param.value,
                          self._profile_override)
        return pn.Modal(
            pn.pane.HTML("<div class='qcm-drawer-title'>Add a run to the overlay</div>", margin=0),
            pn.pane.HTML("<div class='eyebrow'>Run directory or instrument file</div>", margin=0),
            self._run_browser,
            pn.Row(self._profile_override, pn.Column(detected, margin=0, sizing_mode="stretch_width"),
                   margin=0, sizing_mode="stretch_width", css_classes=["qcm-import-detect"]),
            pn.Column(mapping, margin=0, sizing_mode="stretch_width"),
            pn.Card(
                pn.pane.HTML("<div class='eyebrow'>Pair a potentiostat (PSTrace) export — CV or CP</div>", margin=0),
                self._ps_browser,
                title="Electrochemistry (optional)", collapsible=True, collapsed=True,
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-card"],
            ),
            pn.Row(pn.layout.HSpacer(), add, margin=0, sizing_mode="stretch_width"),
            width=760, show_close_button=True, background_close=True,
            margin=0, css_classes=["qcm-run-modal"],
            # Panel's .dialog-content scrolls (overflow:auto) but has no height
            # cap, so a tall body (two file browsers + mapping editor) runs off
            # the screen. Cap it to the viewport so it scrolls inside instead.
            stylesheets=[".dialog-content{max-height:86vh;max-width:94vw;}"],
        )

    @staticmethod
    def _first_path(value):
        if isinstance(value, list):
            return value[0] if value else None
        return value or None

    def _detected_profile_html(self, value, override):
        p = self._first_path(value)
        if not p:
            return pn.pane.HTML("<div class='qcm-import-msg'>Choose a run directory or instrument file.</div>")
        path = Path(p)
        if path.is_dir() and (path / "manifest.json").exists():
            return pn.pane.HTML("<div class='qcm-import-ok'>✓ Ingested run — loads directly</div>")
        if override == "map":
            return pn.pane.HTML("<div class='qcm-import-msg'>Map the columns below, then import.</div>")
        if override != "auto":
            return pn.pane.HTML(
                f"<div class='qcm-import-ok'>Forcing profile: "
                f"{escape(self._PROFILE_LABELS.get(override, override))}</div>")
        name = detect_profile(path)
        if name is None:
            return pn.pane.HTML(
                f"<div class='qcm-import-warn'>⚠ No profile matched ‘{escape(path.name)}’. "
                f"Pick a profile to override, or check the file.</div>")
        if profile_kind(name) == "ps":
            return pn.pane.HTML(
                f"<div class='qcm-import-warn'>⚠ ‘{escape(path.name)}’ is a potentiostat export — "
                f"add it under <em>Electrochemistry</em> pairing, not as the run source.</div>")
        return pn.pane.HTML(
            f"<div class='qcm-import-ok'>✓ Detected: {escape(self._PROFILE_LABELS.get(name, name))}</div>")

    def _column_mapping_editor(self, value, override):
        """Per-column role pickers shown when 'Map columns' is chosen.

        Reads the selected CSV's header and offers a canonical-role dropdown per
        column (pre-filled with a best guess). The chosen assignments become the
        ``qcm_rename`` map at import time, so a renamed-column variant imports
        without code changes.
        """
        self._col_role_selects = {}
        if override != "map":
            return pn.Spacer(height=0)
        p = self._first_path(value)
        if not p or Path(p).suffix.lower() != ".csv":
            return pn.pane.HTML("<div class='qcm-import-msg'>Select a CSV file to map its columns.</div>")
        try:
            import polars as pl
            columns = pl.read_csv(p, n_rows=0).columns
        except Exception as exc:  # noqa: BLE001
            return pn.pane.HTML(f"<div class='qcm-import-warn'>⚠ Could not read columns: {escape(str(exc))}</div>")
        rows = [pn.pane.HTML("<div class='eyebrow'>Map each column to a canonical role</div>", margin=0)]
        for col in columns:
            sel = pn.widgets.Select(
                options=self._CANONICAL_ROLES, value=self._guess_role(col),
                width=150, margin=0,
            )
            self._col_role_selects[col] = sel
            rows.append(pn.Row(
                pn.pane.HTML(f"<div class='qcm-map-col'>{escape(col)}</div>", margin=0),
                pn.pane.HTML("<div class='qcm-map-arrow'>→</div>", margin=0), sel,
                margin=0, sizing_mode="stretch_width", css_classes=["qcm-map-row"],
            ))
        return pn.Column(*rows, margin=0, sizing_mode="stretch_width", css_classes=["qcm-map-editor"])

    def _open_add_run_modal(self) -> None:
        self._run_modal.show()

    def _confirm_add_run(self) -> None:
        ps = self._first_path(self._ps_browser.value)
        override = self._profile_override.value
        rename = None
        if override == "map":
            rename = self._build_rename({c: s.value for c, s in self._col_role_selects.items()})
        self._on_add_run(self._run_browser.value, ps=ps, override=override, rename=rename)
        try:
            self._run_modal.hide()
        except Exception:
            pass

    def _on_label_edit(self, slot: int, text: str) -> None:
        if text and text.strip() and text.strip() != self.runset.labels()[slot]:
            self.runset.set_label(slot, text)
            self._bump_runset()

    def _on_set_active(self, slot: int) -> None:
        self.runset.set_active(slot)
        self.actions.notify(f"Active run: {self.runset.labels()[slot]}", "info")
        self._bump_runset()

    def _import_or_load(self, path: Path, ps, override: str, rename=None) -> None:
        """Add an already-ingested run dir directly, or import a raw instrument
        file (auto-detected, forced, or column-mapped via ``override``) then add
        it. ``rename`` (with override 'map') remaps a variant CSV's columns."""
        if path.is_dir() and (path / "manifest.json").exists():
            self.runset.add_path(path)
            return
        # 'map' forces the standardized-csv reader with a column rename; 'auto'
        # lets detection choose; any other value forces that profile by name.
        profile = None if override in ("auto", "map") else override
        if override == "map":
            profile = "standardized_csv"
        dest = Path(tempfile.mkdtemp(prefix="qcm_import_")) / f"{path.stem}_run"
        import_run(path, dest, profile=profile, qcm_rename=rename, ps_source=ps)
        self.runset.add_path(dest)

    def _on_add_run(self, selected, *, ps=None, override: str = "auto", rename=None) -> None:
        paths = selected if isinstance(selected, list) else ([selected] if selected else [])
        if not paths:
            self.actions.notify("Pick a run directory or instrument file first.", "warning")
            return
        added = 0
        for p in paths:
            try:
                self._import_or_load(Path(p), ps, override, rename=rename)
                added += 1
            except Exception as exc:  # noqa: BLE001
                self.actions.notify(f"Could not add ‘{Path(p).name}’: {exc}", "error")
        if added:
            self.actions.notify(f"Added {added} run(s) to the overlay.", "success")
            self._bump_runset()

    def _nav(self):
        def render(active: int):
            active = nav.clamp_mode(int(active))
            items = []
            for i, mode in enumerate(nav.MODES):
                btn = pn.widgets.Button(label=mode.label, icon=mode.icon,
                                        button_type="default", sizing_mode="stretch_width")
                btn.on_click(self._go(i))
                classes = ["qcm-nav-item"] + (["is-active"] if i == active else [])
                items.append(pn.Column(btn, nav_sublabel(mode.sublabel),
                                       margin=0, sizing_mode="stretch_width", css_classes=classes))
            return pn.Column(*items, margin=0, sizing_mode="stretch_width", css_classes=["qcm-nav"])
        return pn.bind(render, self.mode)

    def _build_sidebar(self):
        help_btn = pn.widgets.Button(label="Help & shortcuts", icon="help", button_type="default",
                                     sizing_mode="stretch_width")
        help_btn.on_click(lambda _e: self.actions.notify(
            "Drag on the plot to set the active range · click a point to load that sweep · "
            "use Selection mode to switch what a drag targets.", "info"))
        return pn.Column(
            brand("QCM-D Viewer"),
            self._nav(),
            self._runs_card(),
            self._run_info_card(),
            pn.layout.Spacer(css_classes=["qcm-sidebar-spacer"]),
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
        export_btn = pn.widgets.Button(label="Export", icon="download", button_type="primary",
                                       description="Build a shareable report and data export from the current view.",
                                       stylesheets=[ACCENT_BUTTON_STYLESHEET],
                                       sizing_mode="fixed")
        export_btn.on_click(self._go(nav.mode_index("report")))
        inspect = pn.widgets.Button(label="Inspect raw sweeps", icon="microscope", button_type="default",
                                    description="Open the raw resonance sweeps and I/Q traces for QC.",
                                    sizing_mode="fixed")
        inspect.on_click(self._open_drawer)
        # Hug content so the group stays tight on the right (the shared save button
        # otherwise inherits stretch_width from its definition).
        self.controls.save_state_button.sizing_mode = "fixed"
        actions = pn.Row(
            self.controls.save_state_button, inspect, export_btn,
            margin=0, css_classes=["qcm-topbar-actions"],
        )
        return pn.Row(
            info, pn.layout.HSpacer(), actions,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-topbar"],
        )

    # =====================================================  DATA page
    def _data_hero(self):
        def render(mode_val, *_):
            window = mode_val if mode_val in ("current", "reference", "mark") else "current"
            hero = self._data_plot.unified_anchor(window=window, height=HERO_HEIGHT)
            strip = self._potential_strip()
            if strip is None:
                return hero
            return pn.Column(strip, hero, margin=0, sizing_mode="stretch_width",
                             css_classes=["qcm-hero-stack"])
        body = pn.bind(
            render,
            self.controls.brush_mode,
            *self.controls.explore_inputs,
            self.controls.quantity_select_right,
            self.controls.show_phases,
            self.controls.zero_line,
            self.controls.show_cycles,
            self.controls.show_potential,
            self.controls.mark_range.param.value_throttled,
            self.controls.mark_start,
            self.controls.mark_end,
            self.controls.annotation_version,
            self.controls.plot_reset_version,
            self.controls.runset_version,
        )
        # The active-range slider rides flush under the plot inside the same card,
        # matching the plot width so it reads as the plot's own range scrubber.
        return pn.Card(
            body,
            self.controls.plot_range_slider(),
            hide_header=True, margin=0, sizing_mode="stretch_width", css_classes=["qcm-anchor"],
        )

    def _potential_strip(self):
        """Full-run E(t) context band for EQCM runs (the notebook reads potential
        and the QCM response on the same clock). None = not applicable/off."""
        try:
            if not self.data.has_echem() or not bool(self.controls.show_potential.value):
                return None
            state = self.controls.state()
            from .theme import axis as _axis
            if not _axis(state.x_axis).is_time or state.quantity == "potential":
                return None
            from . import plots as _plots
            return _plots.potential_strip(
                self.data.echem_waveform(), self.info.t0_us, window=state.t_range_s,
            )
        except Exception:
            return None

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
        return pn.Card(
            pn.bind(body, self.controls.annotation_version),
            title="Phases", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-phases-card"],
        )

    def _rail_edit_phases(self):
        return pn.Card(
            pn.bind(lambda *_: self._phases.phases_table(), self.controls.annotation_version),
            title="Edit phases", collapsible=True, collapsed=True, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-editphases-card"],
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
            title="Live statistics", collapsible=False, margin=0,
            sizing_mode="stretch_width", css_classes=["qcm-card", "qcm-stats"],
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
            self._rail_edit_phases(),
            self._rail_live_stats(),
            self.controls.experiment_params_panel(),
            self.controls.overtone_orders_panel(),
            self.controls.signal_cleanup_panel(),
            self.controls.mpe_display_panel(),
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-rail"],
        )
        body = pn.Row(plotzone, rail, margin=0, sizing_mode="stretch_width", css_classes=["qcm-page-data-body"])
        # The plot-settings strip rides directly under the topbar as a secondary
        # header spanning the full content width (plot + rail).
        return pn.Column(
            self.controls.data_toolbar(include_cycles=has_cycles,
                                       include_potential=self.data.has_echem()),
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
        close = pn.widgets.Button(label="Close", icon="x", button_type="default")
        close.on_click(self._close_drawer)
        qc_content = pn.bind(lambda _open: self._qc.view() if _open else pn.Spacer(height=0),
                             self.drawer_open)
        panel = pn.Column(
            pn.Row(pn.pane.HTML("<div class='qcm-drawer-title'>Raw sweep · QC inspection</div>", margin=0),
                   pn.layout.HSpacer(), close, margin=0, sizing_mode="stretch_width",
                   css_classes=["qcm-drawer-header"]),
            qc_content,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-drawer"], visible=False,
        )
        self.drawer_open.link(panel, value="visible")
        # A click-anywhere backdrop that dims the page and closes the drawer.
        scrim = pn.widgets.Button(label="", css_classes=["qcm-scrim"], visible=False)
        scrim.on_click(self._close_drawer)
        self.drawer_open.link(scrim, value="visible")
        return pn.Column(scrim, panel, margin=0, css_classes=["qcm-drawer-layer"])

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
        children = [shell, self._cached_drawer]
        if self._run_modal is not None:
            children.append(self._run_modal)
        return pn.Column(
            *children,
            margin=0, sizing_mode="stretch_width", css_classes=["qcm-app"],
        )
