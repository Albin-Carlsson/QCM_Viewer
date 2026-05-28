from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .timeutil import parse_time

if TYPE_CHECKING:
    from .run import QCMRun


def write_analysis_notebook(
    run: "QCMRun",
    output: str | Path,
    columns: list[str] | None = None,
    t0=None,
    t1=None,
    groups: list[int] | None = None,
    region_label: str = "current range",
    quantity_key: str = "sauerbrey_mass",
) -> Path:
    """Write a reproducible notebook for the current range or a saved region."""
    import nbformat as nbf

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or ["fit_center", "fit_fwhm", "fit_gamma"]
    t0p = parse_time(t0, run.time_start)
    t1p = parse_time(t1, run.time_end)
    groups_arg = groups if groups is not None else run.groups
    orders = run.overtone_orders()
    project_root = Path(__file__).resolve().parents[1]

    setup = f'''# Environment and imports
# Run this cell first. It installs missing packages into THIS Jupyter kernel.
from pathlib import Path
import importlib
import subprocess
import sys

PROJECT_ROOT = Path(r"{project_root}").resolve()
RUN_PATH = Path(r"{run.path}").resolve()
T0 = {t0p!r}
T1 = {t1p!r}
GROUPS = {groups_arg!r}
ORDERS = {orders!r}
COLUMNS = {columns!r}
REGION_LABEL = {region_label!r}
SELECTED_QUANTITY = {quantity_key!r}
US = 1_000_000

REQUIRED = [
    ("polars", "polars"),
    ("pandas", "pandas"),
    ("holoviews", "holoviews"),
    ("hvplot", "hvplot.polars"),
    ("bokeh", "bokeh"),
    ("pyarrow", "pyarrow"),
    ("duckdb", "duckdb"),
    ("jupyter-bokeh", "jupyter_bokeh"),
]

def ensure_import(package_name, import_name):
    try:
        return importlib.import_module(import_name)
    except Exception:
        print("Installing missing package into this notebook kernel:", package_name)
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return importlib.import_module(import_name)

for package_name, import_name in REQUIRED:
    ensure_import(package_name, import_name)

try:
    import qcm
except Exception:
    if PROJECT_ROOT.exists():
        print("Installing local qcm package into this notebook kernel:", PROJECT_ROOT)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(PROJECT_ROOT)])
        import qcm
    else:
        raise RuntimeError(
            "Could not import qcm and the original project folder was not found. "
            "Open Jupyter from the qcm_refactor folder, or run: python -m pip install -e /path/to/qcm_refactor"
        )

import polars as pl
import pandas as pd
import holoviews as hv
import hvplot.polars  # registers .hvplot on Polars DataFrames
from qcm.viz import science
from qcm.viz.theme import QUANTITIES, quantity

hv.extension("bokeh")

run = qcm.open_run(RUN_PATH)
span_s = (T1 - T0) / US
print("Run:", run.id)
print("Region:", REGION_LABEL)
print("Selected UI quantity:", SELECTED_QUANTITY)
print(f"Window: {{span_s:.3f}} s")
print("Groups:", GROUPS)
'''

    load = '''# Load raw fit data for this exact exported region.
raw = run.timeline(COLUMNS, t0=T0, t1=T1, groups=GROUPS, level="raw")
raw = raw.with_columns(((pl.col("timestamp") - T0) / US).alias("elapsed_s"))
print(f"Rows: {raw.height:,}")
raw.head()
'''

    helpers = '''# Helper functions used in this notebook.
def add_elapsed(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty() or "timestamp" not in df.columns:
        return df
    return df.with_columns(((pl.col("timestamp") - T0) / US).alias("elapsed_s"))

# Default notebook zero/reference range: first 10% of the exported region.
# Change BASELINE_START_S / BASELINE_END_S and re-run cells below if needed.
BASELINE_START_S = 0.0
BASELINE_END_S = max(span_s * 0.10, min(span_s, 1.0))
B0 = int(T0 + BASELINE_START_S * US)
B1 = int(T0 + BASELINE_END_S * US)
print(f"Notebook zero/reference range: {BASELINE_START_S:.3f}–{BASELINE_END_S:.3f} s")
'''

    selected = '''# Plot the same quantity that was selected in the UI when this notebook was exported.
q = quantity(SELECTED_QUANTITY)
main_selected = run.timeline(list(q.sources), t0=T0, t1=T1, groups=GROUPS)
baseline_selected = None
if q.referenced:
    baseline_selected = run.timeline(list(q.sources), t0=B0, t1=B1, groups=GROUPS, level="raw")
selected_df = add_elapsed(science.compute(main_selected, SELECTED_QUANTITY, ORDERS, baseline_df=baseline_selected))
selected_title = f"{q.label} — {REGION_LABEL}"
selected_plot = selected_df.hvplot.line(
    x="elapsed_s", y="value", by="group", responsive=True, height=420,
    title=selected_title, xlabel="Time in exported region [s]", ylabel=q.axis_label,
).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair", "box_zoom", "reset"])
selected_plot
'''

    qcmd = '''# Compute canonical QCM-D quantities.
baseline = run.timeline(["fit_center", "fit_fwhm"], t0=B0, t1=B1, groups=GROUPS, level="raw")
main = run.timeline(["fit_center", "fit_fwhm"], t0=T0, t1=T1, groups=GROUPS)

df_norm = add_elapsed(science.compute(main, "delta_f_norm", ORDERS, baseline_df=baseline))
dD = add_elapsed(science.compute(main, "delta_D", ORDERS, baseline_df=baseline))

qcmd_long = pl.concat([
    df_norm.with_columns(pl.lit("delta_f_norm").alias("quantity_key"), pl.lit("Δf/n [Hz]").alias("quantity")),
    dD.with_columns(pl.lit("delta_D").alias("quantity_key"), pl.lit("ΔD [×10⁻⁶]").alias("quantity")),
], how="diagonal")
qcmd_long.head()
'''

    stats = '''# Rich per-group statistics for every registered quantity in this exported region.
stat_frames = []
for key in QUANTITIES:
    q = quantity(key)
    source_cols = list(q.sources)
    main_q = run.timeline(source_cols, t0=T0, t1=T1, groups=GROUPS)
    baseline_q = None
    if q.referenced:
        baseline_q = run.timeline(source_cols, t0=B0, t1=B1, groups=GROUPS, level="raw")
    values = science.compute(main_q, key, ORDERS, baseline_df=baseline_q)
    s = science.summary_stats(values).with_columns(
        pl.lit(key).alias("quantity_key"),
        pl.lit(q.label).alias("quantity"),
        pl.lit(q.unit or "—").alias("unit"),
    )
    stat_frames.append(s)

all_stats = pl.concat(stat_frames, how="diagonal") if stat_frames else pl.DataFrame()
all_stats
'''

    plot1 = '''# Interactive QCM-D overview for the exported region.
df_plot = df_norm.hvplot.line(
    x="elapsed_s", y="value", by="group", responsive=True, height=360,
    title=f"Δf/n — {REGION_LABEL}", xlabel="Time in exported region [s]", ylabel="Δf/n [Hz]",
).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair", "box_zoom", "reset"])
dD_plot = dD.hvplot.line(
    x="elapsed_s", y="value", by="group", responsive=True, height=360,
    title=f"ΔD — {REGION_LABEL}", xlabel="Time in exported region [s]", ylabel="ΔD [×10⁻⁶]",
).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair", "box_zoom", "reset"])
df_plot + dD_plot
'''

    fingerprint = '''# Df fingerprint: ΔD vs Δf/n.
fingerprint_df = df_norm.rename({"value": "delta_f_norm"}).join(
    dD.rename({"value": "delta_D"}), on=["timestamp", "group", "elapsed_s"], how="inner"
)
fingerprint_df.hvplot.line(
    x="delta_f_norm", y="delta_D", by="group", responsive=True, height=420,
    title=f"Df fingerprint — {REGION_LABEL}", xlabel="Δf/n [Hz]", ylabel="ΔD [×10⁻⁶]"
).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair", "box_zoom", "reset"])
'''

    sweep = '''# Inspect a raw sweep from the middle of the exported region.
idx = run.sweep_index(t0=T0, t1=T1, groups=GROUPS)
mid_sequence = int(idx["sequence"][idx.height // 2]) if idx.height else None
sweep = run.sweeps_at(sequence=mid_sequence, groups=GROUPS) if mid_sequence is not None else pl.DataFrame()
if not sweep.is_empty():
    display(sweep.hvplot.line(
        x="frequency", y=["conductance", "susceptance"], by="group", responsive=True, height=420,
        title=f"Raw resonance sweep {mid_sequence}", xlabel="Frequency [Hz]", ylabel="Signal [a.u.]"
    ).opts(active_tools=["wheel_zoom"], tools=["hover", "crosshair", "box_zoom", "reset"]))
    display(sweep.hvplot.scatter(
        x="raw_i", y="raw_q", by="group", responsive=True, height=420, size=5,
        title=f"I/Q sweep {mid_sequence}", xlabel="Raw I [a.u.]", ylabel="Raw Q [a.u.]"
    ).opts(active_tools=["wheel_zoom"], tools=["hover", "box_zoom", "reset"]))
else:
    print("No sweep found for this region.")
'''

    regions = '''# Saved regions that overlap this exported region.
saved_regions = run.annotations(t0=T0, t1=T1)
region_rows = []
for a in saved_regions:
    start_s = (a.t0 - T0) / US
    end_s = ((a.t1 or a.t0) - T0) / US
    region_rows.append({
        "label": a.label,
        "type": a.type,
        "kind": a.tags[0] if a.tags else "region",
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": max(0, end_s - start_s),
        "groups": a.groups,
        "created_at": a.created_at,
    })
region_table = pl.DataFrame(region_rows) if region_rows else pl.DataFrame()
region_table
'''

    export = '''# Optional exports from the notebook.
# raw.write_parquet("region_raw.parquet")
# selected_df.write_csv("selected_quantity_timeseries.csv")
# all_stats.write_csv("region_stats.csv")
# qcmd_long.write_csv("region_qcmd_timeseries.csv")
# region_table.write_csv("saved_regions.csv")
'''

    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.cells = [
        nbf.v4.new_markdown_cell(f"# QCM region analysis: {run.id}"),
        nbf.v4.new_markdown_cell(
            "This notebook was generated from QCM Viewer for one current range or saved region. "
            "It starts with the quantity selected in the UI, then adds QCM-D overview plots, statistics, "
            "a representative raw sweep, and overlapping saved regions."
        ),
        nbf.v4.new_code_cell(setup),
        nbf.v4.new_markdown_cell("## Load exported region"),
        nbf.v4.new_code_cell(load),
        nbf.v4.new_markdown_cell("## Zero/reference range used inside this notebook"),
        nbf.v4.new_code_cell(helpers),
        nbf.v4.new_markdown_cell("## Selected UI quantity"),
        nbf.v4.new_code_cell(selected),
        nbf.v4.new_markdown_cell("## Compute QCM-D quantities"),
        nbf.v4.new_code_cell(qcmd),
        nbf.v4.new_markdown_cell("## Statistics for all quantities"),
        nbf.v4.new_code_cell(stats),
        nbf.v4.new_markdown_cell("## QCM-D overview plots"),
        nbf.v4.new_code_cell(plot1),
        nbf.v4.new_code_cell(fingerprint),
        nbf.v4.new_markdown_cell("## Raw sweep check"),
        nbf.v4.new_code_cell(sweep),
        nbf.v4.new_markdown_cell("## Saved regions overlapping this region"),
        nbf.v4.new_code_cell(regions),
        nbf.v4.new_markdown_cell("## Optional exports"),
        nbf.v4.new_code_cell(export),
    ]
    nbf.write(nb, out)
    return out
