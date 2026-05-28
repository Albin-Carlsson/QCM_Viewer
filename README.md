# QCM Viewer

A local interactive QCM/QCM-D viewer for Parquet runs.

## Install

From the project folder:

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -e .
```

This installs Panel, HoloViews, hvPlot, Polars, DuckDB, PyArrow, Pandas, Jupyter support, and the rest of the runtime dependencies.

## Try the demo

```bash
# Small quick dataset for UI testing
python -m qcm.cli demo-data ./demo-run --preset small

# OR: long stress-test dataset, approximately 500 MB on disk
python -m qcm.cli demo-data ./demo-run --preset long

python -m qcm.cli ingest ./demo-run/demo.parquet ./view-run --overwrite
python -m panel serve qcm/panel_app.py --show --args ./view-run
```

Open the browser page printed by Panel, usually `http://localhost:5006/panel_app`.

## Architectural discussion

QCM Viewer is a local-first, file-backed analysis application. 
The central architectural choice is that an imported run is not an in-memory object and not a database server. 
It is a directory of Parquet and JSON files with a small manifest that defines the contract between ingestion, 
the Python API, the Panel UI, and exported notebooks.

```text
source parquet file(s)
        |
        v
qcm.ingest
        |
        v
view-run/
  manifest.json
  raw/part-*.parquet
  sweeps/index.parquet
  pyramid/<level>/data.parquet
  annotations.json
  expressions.json
        |
        v
qcm.run.QCMRun
        |
        v
qcm.viz.data + qcm.viz.science
        |
        v
qcm.viz.controls/pages/plots/actions/layout
```

This structure keeps large measurement data on disk, makes the run folder portable, 
and gives every consumer the same read path. 
The UI, notebook export, CLI diagnostics, 
and Python API all open a `QCMRun` instead of each inventing their own Parquet access pattern.

### Run directory contract

`qcm.ingest` converts source Parquet into a normalized run directory. The required input columns are:

```text
timestamp, sequence, group, frequency,
raw_i, raw_q, conductance, susceptance,
fit_center, fit_gamma, fit_fwhm
```

The run directory separates data by access pattern:

- `manifest.json` records schema version, run id, source path, time bounds, available columns, groups, pyramid levels, 
- relative paths, and ingest metadata.

- `raw/part-*.parquet` stores the original frequency-point table in manageable chunks. 
- This is the authoritative data source for raw sweep inspection, focused exports, and frequency-band queries.

- `sweeps/index.parquet` stores one row per `sequence` and `group`. 
- It is the efficient source for fit-parameter timelines because `fit_center`, `fit_gamma`, and `fit_fwhm` 
- are constant across the frequency points of one sweep.

- `pyramid/<level>/data.parquet` stores precomputed time buckets such as 
- `100ms`, `1s`, `10s`, `1min`, `10min`, and `1h`. 
- These tables support broad overview plots without scanning a full raw file.

- `annotations.json` stores user-created saved regions and markers.

- `expressions.json` is reserved for run-local derived expressions.

Timestamps are stored as integer microseconds. The UI converts them to elapsed seconds relative to the run start so sliders, axes, and notebooks use human-scale values while the persisted data keeps exact timestamps.

### Ingest pipeline

Ingest is deliberately front-loaded. The expensive work happens once, before the interactive app starts:

1. Validate the input schema from the source Parquet file or directory.
2. Stream Arrow batches into `raw/part-*.parquet` so a large file is never held as one Python object.
3. Ask DuckDB for run metadata such as min/max timestamp, row count, and group list.
4. Build `sweeps/index.parquet` with one row per sequence/group.
5. Build the pyramid tables with SQL aggregation over the raw parts.
6. Initialize mutable sidecar files and write `manifest.json`.

DuckDB does the heavy relational work and writes Parquet directly. Polars is used for the smaller data frames that cross into Python for transforms, statistics, and plotting. This split keeps ingest and query behavior predictable for files that are hundreds of MB to multiple GB.

### Read path

`qcm.run.QCMRun` is the read-side boundary. It owns the run path, the loaded `Manifest`, a DuckDB in-memory connection, and a small cache for the full sweep index. Its methods return Polars DataFrames and do not depend on Panel.

Important methods:

- `timeline(columns, t0, t1, groups, target_points, level)` chooses a data level for time-series reads. If `level` is omitted, `choose_level(...)` picks raw or a pyramid level from the requested duration and target point count.
- `sweep(...)` and `sweeps_at(...)` read raw frequency curves for one sequence.
- `sweep_index(...)` reads the compact sequence/group index.
- `baseline_mean(...)` pushes per-group baseline aggregation into DuckDB so a zero/reference window does not need to be materialized row by row in Python.
- `frequency_band(...)` reads raw data for the waterfall view.
- `annotations(...)`, `add_annotation(...)`, and `remove_annotation(...)` manage saved regions.
- `export_data(...)`, `save_view_state(...)`, and `to_notebook(...)` provide user-facing outputs.

The main invariant is that UI code should ask `QCMRun` or `QCMViewData` for data. It should not call `read_parquet` directly, because doing so bypasses level routing, baseline aggregation, and the sweep-index optimization.

### Science and quantity model

The UI quantity registry lives in `qcm/viz/theme.py`. Each `Quantity` declares:

- the stable key used by state and exports,
- label and unit,
- source columns needed from the run,
- whether the quantity is referenced to a zero range,
- whether it is normalized by overtone order.

`qcm/viz/science.py` is the pure transform layer. It turns source columns into tidy frames with:

```text
timestamp, group, value
```

Referenced quantities subtract the per-group mean of the zero/reference range. Normalized frequency shifts divide by the overtone order `n`. Dissipation is computed as `fit_fwhm / fit_center * 1e6`. Sauerbrey mass uses `-17.7 * Δf/n` in `ng/cm²`.

Overtone orders are inferred from the first sweep-index frequencies, using the lowest-frequency group as the base. The UI exposes a manual override because real datasets may contain missing, renamed, or nonstandard channels.

### Panel UI composition

The Panel app is split by responsibility:

- `qcm/viz/app.py` is the composition root. It opens the run, builds stable `RunInfo`, and wires controls, data, actions, and layout.
- `qcm/viz/state.py` defines `RunInfo` and `ViewState`. `ViewState` is the complete snapshot needed to render plots, statistics, and exports.
- `qcm/viz/controls.py` owns widgets and converts widget values into `ViewState`.
- `qcm/viz/data.py` bridges UI state to `QCMRun` and `science.compute(...)`. It also owns a bounded LRU cache for repeated plot/table queries.
- `qcm/viz/actions.py` owns mutations: saving annotations, deleting annotations, saving viewer state, synchronizing the zero/reference range, and building file downloads.
- `qcm/viz/pages.py` defines task-oriented pages: Overview, Analyze, and Sweep Inspector.
- `qcm/viz/plots.py` builds HoloViews/Bokeh objects. Plot functions receive prepared DataFrames; they do not query files or mutate state.
- `qcm/viz/layout.py` assembles the FastListTemplate, sidebar, header, and tabs.
- `qcm/panel_app.py` is only the Panel serving entry point.

This keeps circular dependencies out of the UI. Widgets produce state, data services produce frames, pages compose controls and visualizations, actions mutate files, and plots render prepared data.

### Interaction state

The UI is organized around three user concepts:

- Current range: the time interval currently being inspected. It drives plots, tables, data export, and notebook export.
- Zero/reference range: the interval whose per-group mean is subtracted for referenced quantities such as Δf, Δf/n, ΔD, and Sauerbrey mass.
- Saved regions: named points or ranges stored as annotations and overlaid on plots.

Only durable workspace settings are persisted in `viewer_state.json`. Transient UI details such as a partially typed annotation label and the internal annotation refresh counter are intentionally excluded.

### Plotting and browser performance

There are two levels of downsampling:

1. Data-level routing chooses raw, sweep-index, or pyramid tables before data reaches Python.
2. Plot-level envelope decimation in `plots._decimate_xy(...)` limits the number of Bokeh glyph points per curve while preserving spikes and artifacts visually.

These layers solve different problems. Pyramid tables reduce disk and Python work for broad time windows. Plot decimation reduces browser redraw cost after the relevant data has already been selected.

The interactive statistics table uses the same scalable value frame as the selected UI quantity. For exact raw post-processing over a focused interval, export the current range or generate a notebook; those paths explicitly load raw-resolution data for the chosen region.

### Persistence and mutability

The imported measurement artifacts are treated as rebuildable and effectively immutable:

```text
raw/
sweeps/
pyramid/
manifest.json
```

User workspace artifacts are mutable:

```text
annotations.json
expressions.json
viewer_state.json
exported notebooks/data files
```

Because annotations are stored in a simple JSON file, the app is optimized for local single-user work. Running multiple viewer sessions against the same run directory can overwrite annotation changes if both sessions edit at the same time.

### Extension points

To add a new plottable quantity:

1. Add a `Quantity` entry in `qcm/viz/theme.py`.
2. Extend `qcm/viz/science._raw_value(...)` and `raw_value_sql(...)` if it is not a direct source-column passthrough.
3. Confirm whether it should be referenced, normalized, or absolute.
4. Add a focused test or notebook check against a small demo run.

To add a new page:

1. Add a page class in `qcm/viz/pages.py`.
2. Read state through `ViewerControls.state()`.
3. Fetch data through `QCMViewData` or `QCMRun`.
4. Render with functions in `plots.py` or add a new plot function that accepts prepared frames.
5. Register the page in `ViewerLayout.tabs()`.

To change the run format, update `Manifest`/`PathsInfo` in `qcm/models.py`, keep path values relative to the run directory, and preserve backward-compatible defaults when possible. If a change cannot be backward compatible, bump `schema_version` and add an explicit migration or clear error message.

### Design tradeoffs

The project intentionally avoids a long-running database service. A run directory can be copied, archived, inspected with ordinary Parquet tools, and opened by notebooks. The cost is that ingest precomputes extra files and local JSON sidecars are not a multi-user synchronization mechanism.

The UI favors responsiveness over pretending that a billion-row raw table is interactive at full resolution. Broad views use sweep indexes and pyramids; raw data remains available for the operations where exact frequency-point detail matters: individual sweeps, waterfall inspection, focused exports, and reproducible notebooks.

## The UI mental model

The app has three concepts:

### 1. Current range

This is the time span you are working on.

It controls:

- what the plots show
- what the statistics summarize
- what the data export writes
- what the notebook export uses by default

### 2. Zero/reference range

This only matters for Δ quantities, such as Δf, Δf/n, ΔD, and Sauerbrey mass.

It defines what counts as zero. Usually choose a quiet stable part before the experiment changes.

It does **not** crop the plot. It only changes the reference used for delta values.

### 3. Saved regions

A saved region is a named point or time interval shown as an overlay on plots.

Use saved regions for things like:

- artifact
- rinse
- sample added
- stable baseline
- region to export to notebook

Workflow:

```text
choose Current range → inspect plot/statistics → optionally Save current range
```

## Notebook export

On the Analyze page, choose either:

- `Current range`, or
- one of your saved regions

then click notebook export.

The exported notebook is intended to run from the installed project environment. If a notebook kernel is missing dependencies, select the `.venv`/project kernel in Jupyter, or run:

```bash
python -m pip install -e .
python -m ipykernel install --user --name qcm-viewer --display-name "Python (qcm-viewer)"
```

Then switch the notebook kernel to **Python (qcm-viewer)**.

## Common issues

### `ModuleNotFoundError: No module named 'qcm'`

You are using a Jupyter kernel that does not know this project. Run:

```bash
python -m pip install -e .
python -m ipykernel install --user --name qcm-viewer --display-name "Python (qcm-viewer)"
```

Then restart Jupyter and select **Python (qcm-viewer)**.

### `ModuleNotFoundError: No module named 'pyarrow'`

Install the project dependencies again:

```bash
python -m pip install -e .
```


## Set zero = current range

This button copies the current range into the zero/reference range. It does not move the current range, save a region, create a marker, or change the selected quantity.

Use it when the current range is a stable reference period and you want Δf, Δf/n, ΔD, or Sauerbrey mass to be calculated relative to the average value in that interval.

Example:

```text
Current range:        100–200 s
Press:                Set zero = current range
Zero/reference range: 100–200 s
```

Then you can move the current range to another part of the experiment while the zero/reference range stays fixed.


## Demo data size presets

Use `--preset small` for a quick development run. Use `--preset long` to generate a larger stream for performance testing. The long preset targets about 500 MB by default.

```bash
python -m qcm.cli demo-data ./demo-run --preset small
python -m qcm.cli demo-data ./demo-run --preset long
python -m qcm.cli demo-data ./demo-run --preset long --target-mb 1000
```

The long preset writes parquet in chunks so it does not need to hold the full dataset in memory.

---

# Large file workflow: 1 GB parquet imports

The project is optimized so the viewer does **not** load a 1 GB parquet file into memory.

During ingest it creates:

```text
view-run/
  raw/part-00000.parquet       # raw data split into manageable chunks
  raw/part-00001.parquet
  sweeps/index.parquet         # one row per sequence/group
  pyramid/100ms/data.parquet   # compact overview levels
  pyramid/1s/data.parquet
  pyramid/10s/data.parquet
  pyramid/1min/data.parquet
  manifest.json
```

The app should use:

```text
pyramid tables  -> overview plots
sweep index     -> Δf / ΔD timelines and statistics
raw parts       -> one sweep, waterfall, or explicit export only
```

## Import a large file

```bash
python -m qcm.cli ingest \
  ./large-input.parquet \
  ./view-run \
  --overwrite \
  --memory-limit 4GB \
  --raw-part-rows 1000000
```

If your machine has less memory, lower the part size and memory limit:

```bash
python -m qcm.cli ingest \
  ./large-input.parquet \
  ./view-run \
  --overwrite \
  --memory-limit 2GB \
  --raw-part-rows 250000
```

## Generate a large stress-test file

About 500 MB:

```bash
python -m qcm.cli demo-data ./demo-run --preset long
```

About 1 GB:

```bash
python -m qcm.cli demo-data ./demo-run --preset long --target-mb 1000
```

Then ingest it:

```bash
python -m qcm.cli ingest ./demo-run/demo.parquet ./view-run --overwrite
```

## Diagnose performance

```bash
python -m qcm.cli diagnose ./view-run
```

The diagnose command intentionally avoids a full raw-table scan. A fast app should mostly report pyramid/sweep-index reads, not raw reads.

## Performance rules

For large files, keep these rules:

1. Do not convert the full raw table to pandas.
2. Do not collect the full raw table into a Polars DataFrame.
3. Use `run.timeline(...)` for plots; it routes broad views to pyramid tables.
4. Use raw data only for individual sweeps, current-range export, or waterfall inspection.
5. Keep current ranges reasonably focused when exporting raw data.
