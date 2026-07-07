"""Named experiment-parameter presets: persistence + controls integration."""
from __future__ import annotations

import json

from qcm.viz import presets as presets_store
from qcm.viz.controls import ViewerControls
from qcm.viz.state import RunInfo
from qcm.viz.theme import ExperimentParams


def _info():
    return RunInfo(run_id="t", groups=[0], orders={0: 1}, t0_us=0, t1_us=1_000_000,
                   span_s=1.0, fmin=0.0, fmax=1.0, seq_min=0, seq_max=0, n_sweeps=1)


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("QCM_PRESETS_FILE", str(tmp_path / "presets.json"))


def test_save_load_delete_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert presets_store.load_presets() == {}

    p = ExperimentParams(area_cm2=1.13, sensitivity=18.0, molar_mass=65.38,
                         valency=2, reference_electrode="Ag|AgCl")
    presets_store.save_preset("Zn on Cu", p)
    loaded = presets_store.load_presets()
    assert loaded["Zn on Cu"] == p
    # Persisted as JSON on disk under the override path.
    on_disk = json.loads((tmp_path / "presets.json").read_text())
    assert on_disk["Zn on Cu"]["reference_electrode"] == "Ag|AgCl"

    presets_store.delete_preset("Zn on Cu")
    assert presets_store.load_presets() == {}


def test_blank_name_rejected_and_junk_file_tolerated(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    try:
        presets_store.save_preset("  ", ExperimentParams())
        assert False, "blank name should raise"
    except ValueError:
        pass
    # A corrupt presets file degrades to "no presets", never crashes.
    (tmp_path / "presets.json").write_text("{ not json")
    assert presets_store.load_presets() == {}


def test_controls_apply_preset_populates_fields(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    presets_store.save_preset(
        "Cu sensor",
        ExperimentParams(area_cm2=2.0, sensitivity=12.5, molar_mass=58.69,
                         valency=3, reference_electrode="SCE"),
    )
    controls = ViewerControls(_info(), {})
    controls._refresh_preset_options()
    controls.preset_select.value = "Cu sensor"  # fires _apply_preset

    p = controls.params()
    assert abs(p.area_cm2 - 2.0) < 1e-9
    assert abs(p.sensitivity - 12.5) < 1e-9
    assert p.valency == 3
    assert p.reference_electrode == "SCE"


def test_controls_save_preset_from_current_fields(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    controls = ViewerControls(_info(), {})
    controls.param_reference_electrode.value = "Hg|HgO"
    controls.param_valency.value = 2
    controls.preset_name.value = "My cell"
    controls._save_preset()

    saved = presets_store.load_presets()
    assert "My cell" in saved
    assert saved["My cell"].reference_electrode == "Hg|HgO"
    # Name box clears and the new preset is selectable.
    assert controls.preset_name.value == ""
    assert "My cell" in controls.preset_select.options.values()
