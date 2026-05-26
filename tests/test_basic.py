from pathlib import Path

import qcm
from qcm.demo import make_demo_data
from qcm.ingest import ingest


def test_demo_ingest_open(tmp_path: Path):
    raw = tmp_path / "raw"
    run_path = tmp_path / "run"
    make_demo_data(raw, groups=2, sequences=8, points_per_sweep=20)
    ingest(raw, run_path)
    run = qcm.open_run(run_path)
    assert run.id == "run"
    assert run.groups == [0, 1]
    df, meta = run.timeline(["fit_center"], include_meta=True)
    assert df.height > 0
    assert meta.level in {"100ms", "1s", "10s", "1min", "10min", "1h", "raw"}
    sweep = run.sweep(sequence=0, group=0)
    assert sweep.height == 20


def test_annotations(tmp_path: Path):
    raw = tmp_path / "raw"
    run_path = tmp_path / "run"
    make_demo_data(raw, groups=1, sequences=3, points_per_sweep=10)
    ingest(raw, run_path)
    run = qcm.open_run(run_path)
    ann = run.add_annotation(type="point", t0=run.time_start, label="start")
    assert ann.id.startswith("ann_")
    assert len(run.annotations()) == 1
