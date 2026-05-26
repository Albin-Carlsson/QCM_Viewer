# QCM Viewer MVP

A Python-first QCM viewer for completed parquet runs.

Stack:

- Parquet storage
- DuckDB query layer
- Polars/PyArrow data access
- Panel + HoloViews + Datashader UI
- Python API for Jupyter

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Generate demo data
.___-
_:_Ö-_-ä.----.
*
```bash
qcm demo-data demo_raw --groups 3 --sequences 300 --points-per-sweep 600
```

## Ingest demo data

```bash
qcm ingest demo_raw demo_run
```

## Diagnose

```bash
qcm diagnose demo_run
```

## Launch viewer

```bash
qcm serve demo_run
```

or

```bash
panel serve qcm/panel_app.py --show --args demo_run
```

## Python API

```python
import qcm
run = qcm.open_run("demo_run")
run.timeline(["fit_center", "fit_fwhm"], target_points=2000)
run.sweep(sequence=10, group=0)
run.derived("sauerbrey_mass", group=0)
```
