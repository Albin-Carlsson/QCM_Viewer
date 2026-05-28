"""User-triggered mutations and exports for the QCM viewer."""
from __future__ import annotations

import io
import tempfile

from .controls import ViewerControls
from .data import QCMViewData
from .state import RunInfo

_US = 1_000_000


class ViewerActions:
    def __init__(self, run, info: RunInfo, controls: ViewerControls, data: QCMViewData):
        self.run = run
        self.info = info
        self.controls = controls
        self.data = data
        self.export_data_dl = None
        self.export_nb_dl = None
        self._wire_buttons()
        self._build_exports()
        self.refresh_marker_options()

    def _wire_buttons(self) -> None:
        self.controls.mark_window_button.on_click(self.add_window_marker)
        self.controls.mark_point_button.on_click(self.add_point_marker)
        self.controls.save_state_button.on_click(self.save_state)
        self.controls.use_selection_as_baseline.on_click(self.sync_baseline_to_selection)
        self.controls.revert_baseline.on_click(self.revert_baseline)

    def _build_exports(self) -> None:
        import panel as pn

        self.export_data_dl = pn.widgets.FileDownload(
            label="⬇ Current range data (.parquet)",
            filename="qcm_current_range_data.parquet",
            callback=self.data_file,
            button_type="default",
            sizing_mode="stretch_width",
        )
        self.export_nb_dl = pn.widgets.FileDownload(
            label="⬇ Notebook for chosen region",
            filename="qcm_region_analysis.ipynb",
            callback=self.notebook_file,
            button_type="primary",
            sizing_mode="stretch_width",
        )

    def notify(self, msg: str, kind: str = "info") -> None:
        self.controls.status.object = msg
        try:
            import panel as pn

            notifications = pn.state.notifications
            if notifications is not None:
                getattr(notifications, kind, notifications.info)(msg, duration=4000)
        except Exception:
            pass

    def _marker_label(self) -> str:
        label = self.controls.region_label.value.strip()
        kind = self.controls.region_type.value
        return label or kind.title()

    def add_window_marker(self, _event=None) -> None:
        state = self.controls.state()
        if hasattr(self.controls, "mark_range"):
            start_s, end_s = (float(v) for v in self.controls.mark_range.value)
            t0 = int(self.info.t0_us + start_s * _US)
            t1 = int(self.info.t0_us + end_s * _US)
        else:
            t0, t1 = state.t_us(self.info.t0_us)
            start_s, end_s = state.t_range_s
        f0, f1 = state.frequency_band
        label = self._marker_label()
        kind = self.controls.region_type.value
        self.run.add_annotation(
            type="range",
            t0=t0,
            t1=t1,
            label=label,
            tags=[kind],
            groups=state.groups,
            frequency_range=(float(f0), float(f1)),
        )
        self.controls.annotation_version.value += 1
        self.controls.region_label.value = ""
        self.refresh_marker_options()
        self.notify(f"Saved phase “{label}” ({start_s:,.2f}–{end_s:,.2f} s).", "success")

    def add_point_marker(self, _event=None) -> None:
        state = self.controls.state()
        if hasattr(self.controls, "mark_range"):
            start_s, end_s = (float(v) for v in self.controls.mark_range.value)
            mid_s = (start_s + end_s) / 2
        else:
            mid_s = (state.t_range_s[0] + state.t_range_s[1]) / 2
        t = int(self.info.t0_us + mid_s * _US)
        label = self._marker_label()
        kind = self.controls.region_type.value
        self.run.add_annotation(
            type="point",
            t0=t,
            t1=None,
            label=label,
            tags=[kind],
            groups=state.groups,
            frequency_range=None,
        )
        self.controls.annotation_version.value += 1
        self.controls.region_label.value = ""
        self.refresh_marker_options()
        self.notify(f"Marked “{label}” at {mid_s:.3f} s.", "success")

    def refresh_marker_options(self) -> None:
        current = self.controls.marker_select.value
        opts = {"Current range": "__current__"}
        for ann in self.data.annotations():
            if ann.type != "range" or ann.t1 is None:
                continue
            start_s = (ann.t0 - self.info.t0_us) / _US
            end_s = (ann.t1 - self.info.t0_us) / _US
            kind = ann.tags[0] if ann.tags else "marker"
            opts[f"{ann.label} · {kind} · {start_s:.1f}–{end_s:.1f} s"] = ann.id
        self.controls.marker_select.options = opts
        self.controls.marker_select.value = current if current in opts.values() else "__current__"

    def delete_annotation_by_row(self, row: int) -> None:
        try:
            anns = self.data.annotations()
            ann_id = anns[row].id
            label = anns[row].label
            self.run.remove_annotation(ann_id)
            self.controls.annotation_version.value += 1
            self.refresh_marker_options()
            self.notify(f"Deleted saved region “{label}”.", "warning")
        except Exception as exc:
            self.notify(f"Delete failed: {exc}", "error")

    def sync_baseline_to_selection(self, _event=None) -> None:
        """Use the current range as the zero/reference interval.

        This deliberately does only one thing: it copies Current range ->
        Zero/reference range. It must not move the current range, save a region,
        create a marker, or change the selected quantity.
        """
        previous = tuple(float(v) for v in self.controls.baseline_range.value)
        current_range = tuple(float(v) for v in self.controls.t_range.value)
        if previous != current_range:
            self.controls._last_baseline = previous
            self.controls.revert_baseline.disabled = False
        self.controls.baseline_range.value = current_range
        self.notify(
            f"Zero/reference set to {current_range[0]:,.3f}–{current_range[1]:,.3f} s. "
            "Current range was not moved or saved.",
            "success",
        )

    def revert_baseline(self, _event=None) -> None:
        if self.controls._last_baseline is None:
            self.notify("No previous zero/reference range to restore.", "warning")
            return
        current = tuple(self.controls.baseline_range.value)
        self.controls.baseline_range.value = self.controls._last_baseline
        self.controls._last_baseline = current
        self.notify(
            f"Restored previous zero/reference range: "
            f"{self.controls.baseline_range.value[0]:,.3f}–{self.controls.baseline_range.value[1]:,.3f} s.",
            "success",
        )

    def save_state(self, _event=None) -> None:
        out = self.run.save_view_state(self.controls.state().to_persisted_dict())
        self.notify(f"Saved workspace → {out.name}", "success")

    def apply_brush(self, boundsx=None) -> None:
        """Set the current or zero/reference range from a plot box-selection.

        ``boundsx`` is the ``(x0, x1)`` tuple emitted by an ``hv.streams.BoundsX``
        stream in elapsed seconds. Which range it targets is chosen by the
        ``brush_mode`` toggle so the same gesture can define either the analysis
        window or the baseline without a second slider.
        """
        if not boundsx:
            return
        try:
            lo, hi = (float(v) for v in boundsx)
        except (TypeError, ValueError):
            return
        if lo > hi:
            lo, hi = hi, lo
        if abs(hi - lo) < 1e-9:
            return
        mode = self.controls.brush_mode.value
        if mode == "reference":
            previous = tuple(float(v) for v in self.controls.baseline_range.value)
            if previous != (lo, hi):
                self.controls._last_baseline = previous
                self.controls.revert_baseline.disabled = False
            self.controls.set_reference_range_values(lo, hi)
            self.notify(f"Reference range set to {lo:,.2f}–{hi:,.2f} s.", "success")
        elif mode == "mark":
            self.controls.set_mark_range_values(lo, hi)
            self.notify(f"Mark range set to {lo:,.2f}–{hi:,.2f} s. Name it and save phase.", "success")
        else:
            self.controls.set_current_range_values(lo, hi)
            self.notify(f"Analysis range set to {lo:,.2f}–{hi:,.2f} s.", "success")

    def jump_to_seconds(self, seconds) -> None:
        if seconds is None:
            return
        try:
            sequence = self.data.nearest_sequence_at_seconds(float(seconds))
            if sequence is not None:
                self.controls.sequence.value = sequence
                self.notify(f"Loaded sweep {sequence} at t={float(seconds):.2f} s")
        except Exception:
            pass

    def _export_window_us(self) -> tuple[int, int, str]:
        selected = self.controls.marker_select.value
        if selected and selected != "__current__":
            for ann in self.data.annotations():
                if ann.id == selected and ann.t1 is not None:
                    return int(ann.t0), int(ann.t1), ann.label
        state = self.controls.state()
        t0, t1 = state.t_us(self.info.t0_us)
        return t0, t1, "current range"

    def data_file(self):
        state = self.controls.state()
        t0, t1, _label = self._export_window_us()
        cols = [c for c in ["fit_center", "fit_fwhm", "fit_gamma"] if c in self.run.columns]
        df = self.run.timeline(cols, t0=t0, t1=t1, groups=state.groups, level="raw")
        buf = io.BytesIO()
        df.write_parquet(buf)
        buf.seek(0)
        return buf

    def notebook_file(self):
        state = self.controls.state()
        t0, t1, label = self._export_window_us()
        tmp = tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False)
        self.run.to_notebook(
            tmp.name,
            columns=["fit_center", "fit_fwhm", "fit_gamma"],
            t0=t0,
            t1=t1,
            groups=state.groups,
            region_label=label,
            quantity_key=state.quantity,
        )
        return open(tmp.name, "rb")
