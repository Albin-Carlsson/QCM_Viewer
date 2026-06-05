"""Multi-run support: run set, overlay-frame builder, run-family colours, and
the multi-run hero plot (issue #4)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import polars as pl

from qcm.profiles import import_run
from qcm.viz import plots
from qcm.viz.controls import ViewerControls
from qcm.viz.runset import RunSet, load_run
from qcm.viz.steps.review import ReviewStep
from qcm.viz.actions import ViewerActions
from qcm.viz.tokens import color_for_run, color_for_run_overtone


def _make_run(tmp_path, name: str, *, f0: float, n_rows: int = 30):
    """Import a standardized two-overtone csv into its own run directory."""
    t = np.round(np.arange(n_rows) * 0.5, 3)
    csv = tmp_path / f"{name}.csv"
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.linspace(f0, f0 - 200.0, n_rows), "D_1": np.full(n_rows, 500.0),
        "Time_3": t, "Fr_3": np.linspace(3 * f0, 3 * f0 - 600.0, n_rows), "D_3": np.full(n_rows, 200.0),
    }).write_csv(csv)
    run_dir = tmp_path / name
    import_run(csv, run_dir)
    return run_dir


def _two_run_set(tmp_path) -> RunSet:
    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    b = _make_run(tmp_path, "run_b", f0=6_000_000.0)
    return RunSet.from_paths([a, b])


# --- run set ---------------------------------------------------------------

def test_runset_loads_multiple(tmp_path):
    rs = _two_run_set(tmp_path)
    assert rs.is_multi
    assert rs.labels() == ["run_a", "run_b"]
    assert rs.active.info.run_id == "run_a"
    # Each run holds an independent data service with a back-reference.
    for d in rs.runs:
        assert d.runset is rs


def test_single_run_set_is_not_multi(tmp_path):
    a = _make_run(tmp_path, "solo", f0=5_000_000.0)
    rs = RunSet([load_run(a)])
    assert not rs.is_multi
    assert rs.active.runset is rs


# --- overlay-frame builder -------------------------------------------------

def test_overlay_frame_tags_each_run(tmp_path):
    rs = _two_run_set(tmp_path)
    state = ViewerControls(rs.active.info, {}).state()
    full = replace(state, t_range_s=(0.0, float(rs.active.info.span_s)))
    frame = rs.overlay_value_df(full, "delta_f_norm", "time")
    assert not frame.is_empty()
    assert {"run", "run_slot"}.issubset(frame.columns)
    assert sorted(frame["run"].unique().to_list()) == ["run_a", "run_b"]
    assert sorted(frame["run_slot"].unique().to_list()) == [0, 1]


def test_overlay_frame_aligns_each_run_to_own_start(tmp_path):
    rs = _two_run_set(tmp_path)
    state = ViewerControls(rs.active.info, {}).state()
    full = replace(state, t_range_s=(0.0, float(rs.active.info.span_s)))
    frame = rs.overlay_value_df(full, "delta_f_norm", "time")
    # Both runs start their elapsed-time axis at ~0 regardless of wall clock.
    for slot in (0, 1):
        xs = frame.filter(pl.col("run_slot") == slot)["x"].drop_nulls()
        assert float(xs.min()) < 1e-6


# --- run-family colours ----------------------------------------------------

def test_run_colours_are_distinct_families(tmp_path):
    assert color_for_run(0) != color_for_run(1)
    # First overtone uses the base hue; later overtones are distinct shades.
    assert color_for_run_overtone(0, 0) == color_for_run(0)
    assert color_for_run_overtone(0, 1) != color_for_run_overtone(0, 0)
    assert color_for_run_overtone(0, 2) != color_for_run_overtone(0, 1)
    # Different runs never collide on their base hue.
    assert color_for_run_overtone(0, 0) != color_for_run_overtone(1, 0)


def _hue(hex_color: str) -> float:
    import colorsys
    r, g, b = (int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0]


def test_shades_preserve_hue_family(tmp_path):
    # Overtone shades vary lightness but keep the family's hue (not fade to grey).
    base_hue = _hue(color_for_run(0))
    # Tolerance covers 8-bit hex quantization only; a hue shift would be far larger.
    for k in range(1, 4):
        assert abs(_hue(color_for_run_overtone(0, k)) - base_hue) < 0.01


# --- plot + hero -----------------------------------------------------------

def test_overlay_timeline_builds(tmp_path):
    import holoviews as hv
    from qcm.viz.theme import axis, quantity

    rs = _two_run_set(tmp_path)
    state = ViewerControls(rs.active.info, {}).state()
    full = replace(state, t_range_s=(0.0, float(rs.active.info.span_s)))
    frame = rs.overlay_value_df(full, "delta_f_norm", "time")
    plot = plots.overlay_timeline(
        frame, quantity("delta_f_norm"), axis("time"),
        run_labels=rs.labels(),
        run_orders=[d.info.orders for d in rs.runs],
        title="t",
    )
    assert isinstance(plot, hv.Overlay)
    # One curve per (run, visible overtone): 2 runs x 2 overtones.
    curves = [e for e in plot.values() if isinstance(e, hv.Curve)]
    assert len(curves) == 4


def test_hero_overlays_when_multi_run(tmp_path):
    rs = _two_run_set(tmp_path)
    controls = ViewerControls(rs.active.info, {})
    actions = ViewerActions(rs.active.run, rs.active.info, controls, rs.active)
    step = ReviewStep(controls, rs.active, actions)
    hero = step.unified_anchor()
    # A successful overlay returns a HoloViews object, not an error Alert.
    assert hero.__class__.__name__ not in ("Alert",)


# --- run manager (issue #10) -----------------------------------------------

def test_set_label_and_active(tmp_path):
    rs = _two_run_set(tmp_path)
    rs.set_label(0, "Baseline")
    assert rs.labels()[0] == "Baseline"
    rs.set_label(1, "   ")  # blank ignored
    assert rs.labels()[1] == "run_b"
    rs.set_active(1)
    assert rs.active_index == 1
    assert rs.active.info.run_id == "run_b"


def test_add_run_joins_overlay_with_new_family(tmp_path):
    rs = _two_run_set(tmp_path)
    c = _make_run(tmp_path, "run_c", f0=7_000_000.0)
    slot = rs.add_path(c)
    assert slot == 2 and len(rs.runs) == 3
    assert rs.runs[slot].runset is rs
    state = ViewerControls(rs.active.info, {}).state()
    full = replace(state, t_range_s=(0.0, float(rs.active.info.span_s)))
    frame = rs.overlay_value_df(full, "delta_f_norm", "time")
    assert "run_c" in frame["run"].unique().to_list()


def test_overlay_legend_uses_edited_labels(tmp_path):
    rs = _two_run_set(tmp_path)
    rs.set_label(0, "Baseline")
    state = ViewerControls(rs.active.info, {}).state()
    full = replace(state, t_range_s=(0.0, float(rs.active.info.span_s)))
    frame = rs.overlay_value_df(full, "delta_f_norm", "time")
    assert "Baseline" in frame["run"].unique().to_list()
    assert "run_a" not in frame["run"].unique().to_list()


def test_active_run_view_follows_selector(tmp_path):
    from qcm.viz.runset import ActiveRunView

    rs = _two_run_set(tmp_path)
    proxy = ActiveRunView(rs)
    assert proxy.info.run_id == "run_a"
    assert proxy.runset is rs  # overlay views still reach the whole set
    rs.set_active(1)
    assert proxy.info.run_id == "run_b"


def test_shell_run_manager_handlers(tmp_path):
    from qcm.viz.app import QCMViewer

    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    b = _make_run(tmp_path, "run_b", f0=6_000_000.0)
    viewer = QCMViewer([a, b])
    shell = viewer.shell
    v0 = shell.controls.runset_version.value

    shell._on_label_edit(0, "Baseline")
    assert viewer.runset.labels()[0] == "Baseline"
    assert shell.controls.runset_version.value > v0

    shell._on_set_active(1)
    assert viewer.runset.active_index == 1
    # Single-run views follow the active selector through the proxy.
    assert viewer.data.info.run_id == "run_b"

    c = _make_run(tmp_path, "run_c", f0=7_000_000.0)
    shell._on_add_run([str(c)])
    assert "run_c" in viewer.runset.labels()
    # The sidebar (run-manager card) still builds after the set grows.
    assert shell._build_sidebar() is not None


def test_overlay_region_summary_stacks_runs(tmp_path):
    rs = _two_run_set(tmp_path)
    state = ViewerControls(rs.active.info, {}).state()
    out = rs.overlay_region_summary(state)
    assert "run" in out.columns
    assert "group" in out.columns  # one row set per channel
    assert sorted(out["run"].unique().to_list()) == ["run_a", "run_b"]
    # Edited labels flow through to the comparison table.
    rs.set_label(0, "Baseline")
    out2 = rs.overlay_region_summary(state)
    assert "Baseline" in out2["run"].unique().to_list()


def test_add_run_imports_raw_instrument_file(tmp_path):
    """The run manager auto-detects + imports a raw QCM csv and joins it."""
    from qcm.viz.app import QCMViewer

    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    viewer = QCMViewer([a])
    raw = tmp_path / "raw_qcm.csv"
    t = np.round(np.arange(20) * 0.5, 3)
    pl.DataFrame({
        "Time_1": t, "Fr_1": np.full(20, 5_000_000.0), "D_1": np.full(20, 500.0),
    }).write_csv(raw)

    n0 = len(viewer.runset.runs)
    viewer.shell._on_add_run([str(raw)], override="auto")
    assert len(viewer.runset.runs) == n0 + 1


def test_import_detect_readout(tmp_path):
    from qcm.viz.app import QCMViewer

    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    sh = QCMViewer([a]).shell

    raw = tmp_path / "raw_qcm.csv"
    pl.DataFrame({"Time_1": [0.0, 0.5], "Fr_1": [5e6, 5e6], "D_1": [500.0, 500.0]}).write_csv(raw)
    assert "Detected" in sh._detected_profile_html([str(raw)], "auto").object

    junk = tmp_path / "junk.csv"
    junk.write_text("a,b\n1,2\n", encoding="utf-8")
    assert "No profile matched" in sh._detected_profile_html([str(junk)], "auto").object


def test_column_role_guess_and_rename(tmp_path):
    from qcm.viz.app import QCMViewer

    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    sh = QCMViewer([a]).shell
    assert sh._guess_role("Frequency_1") == "Fr_1"
    assert sh._guess_role("Diss_1") == "D_1"
    assert sh._guess_role("t_1") == "Time_1"
    assert sh._guess_role("notes") == "(ignore)"
    # Only assigned columns end up in the rename map.
    rename = sh._build_rename({"t_1": "Time_1", "Frequency_1": "Fr_1", "notes": "(ignore)"})
    assert rename == {"t_1": "Time_1", "Frequency_1": "Fr_1"}


def test_add_run_with_column_mapping_imports_variant(tmp_path):
    """A renamed-column CSV imports through the run manager via the map editor."""
    from qcm.viz.app import QCMViewer

    a = _make_run(tmp_path, "run_a", f0=5_000_000.0)
    viewer = QCMViewer([a])
    variant = tmp_path / "variant.csv"
    t = np.round(np.arange(20) * 0.5, 3)
    pl.DataFrame({
        "t_1": t, "Frequency_1": np.full(20, 5_000_000.0), "Diss_1": np.full(20, 500.0),
    }).write_csv(variant)

    rename = {"t_1": "Time_1", "Frequency_1": "Fr_1", "Diss_1": "D_1"}
    n0 = len(viewer.runset.runs)
    viewer.shell._on_add_run([str(variant)], override="map", rename=rename)
    assert len(viewer.runset.runs) == n0 + 1
    assert 1 in viewer.runset.runs[-1].info.groups
