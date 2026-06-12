# QCM Viewer

A local, interactive viewer and analysis tool for QCM-D and EQCM measurements.

It reads raw instrument exports (Qsoft `.txt`, standardized `Time_N/Fr_N/D_N`
CSV, PSTrace potentiostat CSV) or pre-ingested run directories, and gives you
Δf/n, ΔD, Sauerbrey mass, charge, current density, and mass-per-electron (MPE)
with cycle-aware electrochemistry views — all offline, on your own files.

---

## Quick start (no command line)

**macOS:** double-click **`Start QCM Viewer.command`** in this folder. The first
run installs everything it needs (a minute or two); after that it starts in
seconds and opens the viewer in your browser. If macOS warns about an
unidentified developer, right-click the file and choose *Open* the first time.

The viewer opens on a **file picker** — choose a measurement folder or
instrument file and click *Open*. If you analysed something last time, a
**Resume last session** button restores that workspace (runs, labels, active
run) with one click.

## Quick start (command line)

```bash
pip install uv                      # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv run qcm view measurement.csv     # imports if needed, opens the browser
```

(With a classic environment: `python -m pip install -e .` then `qcm view …`.)

`qcm view` accepts:

- a raw instrument file (`.txt`, `.csv`) or a `.parquet`,
- an already-ingested run folder,
- or several of the above to **overlay** them:

```bash
qcm view runA.csv runB.csv          # overlay two runs
qcm view                            # no file: picker page + resume-last-session
```

A sibling `*_PS.csv` potentiostat export next to the QCM file is paired
automatically.

### Pair a potentiostat (EQCM)

A PSTrace export carries the electrochemistry channel. Import it alongside the
QCM source:

```bash
qcm import qcm.csv ./my-run --ps potentiostat.csv
qcm view ./my-run
```

> **CV note:** a cyclic-voltammetry PSTrace export has no time axis, so the time
> base is reconstructed from the scan rate. The rate is taken from (in order) an
> explicit override, a `…25mVs…` token in the filename, then a 0.025 V/s default.
> Whatever was used — and where it came from — is shown in the **Run info** card,
> because it scales the entire reconstructed time axis.

---

## Try the demo

```bash
qcm demo-data ./demo-run --preset small        # quick synthetic dataset
qcm view ./demo-run/demo.parquet
```

`--preset long` writes a ~500 MB stream for performance testing
(`--target-mb 1000` for ~1 GB).

---

## Concepts (the UI mental model)

The app has three pages — **Data** (explore & visualize), **Results** (mass /
charge / MPE dashboard), and **Export** — and three interaction concepts:

1. **Analysis range** — the time window that drives plots, statistics, and
   exports. Set it by dragging on the plot, the slider beneath it, or the
   Start/End boxes.
2. **Reference range** — the baseline subtracted from Δ (referenced) quantities
   (Δf, Δf/n, ΔD, Sauerbrey mass, MPE). It does not crop the plot.
3. **Saved phases** — named time spans (baseline / rinse / sample / artifact)
   overlaid on plots and reusable for reports and notebook export.

The **Selection mode** toggle on the Data page chooses which of these a drag
edits.

### Experiment parameters

The *Experiment parameters* card (Data page rail) sets the electrode area,
Sauerbrey sensitivity, molar mass, and valency. These feed **every** derived
quantity consistently — Sauerbrey mass, MPE, and current density — and are
captured into exported notebooks so the notebook reproduces exactly what you saw.

---

## Architecture

QCM Viewer is local-first and file-backed. An imported run is a directory of
Parquet + JSON, not a database server:

```text
source (csv / txt / parquet)
        │  qcm.profiles.import_run → qcm.ingest.ingest
        ▼
run-dir/
  manifest.json            schema, time bounds, columns, groups, metadata
  raw/part-*.parquet       raw frequency-point table, chunked
  sweeps/index.parquet     one row per (sequence, group) — fast fit timelines
  pyramid/<level>/…        precomputed time buckets for broad overviews
  annotations.json         saved phases/markers
  expressions.json         reserved for run-local derived expressions
        │  qcm.run.QCMRun  (read boundary: DuckDB + Polars)
        ▼
qcm.viz.data.QCMViewData + qcm.science.transforms / qcm.science.echem  (pure)
        ▼
qcm.viz.controls (widgets→state) · steps/* (page bodies) · plots.py (figures)
        ▼
qcm.viz.shell.ViewerShell  (assembles sidebar · topbar · pages · drawer)
qcm.viz.app.QCMViewer       (composition root)  →  qcm/panel_app.py (serve entry)
```

Key invariants:

- **Pure science layer.** `qcm/science/` (transforms, echem, quantities) is
  Panel-free and unit-tested — enforced in CI by import-linter. The quantity
  registry and all science constants live in `qcm/science/quantities.py`;
  display policy (colours, plot sizes) stays in `qcm/viz/`. The old
  `qcm.viz.science`/`qcm.viz.echem` import paths remain as shims.
- **One read path.** UI, CLI, and exported notebooks all open a `QCMRun`; nobody
  reads Parquet directly, so level-routing and baseline aggregation stay shared.
- **Multi-run overlay.** `qcm/viz/runset.py` holds several runs (one *active*);
  each keeps its own baseline and time origin, so overlays line up on a common
  seconds-from-start / referenced axis.

### Run directory contract

Required input columns: `timestamp, sequence, group, fit_center, fit_fwhm`.
Optional raw columns (`frequency, fit_gamma, conductance, susceptance, raw_i,
raw_q`) enable the sweep inspector and waterfall. Optional EQCM columns
(`potential, current, charge, cycle, cycle_time`) enable the electrochemistry
views. Fit-only sources (e.g. Qsoft Fr/D) import fine and degrade raw-only views
gracefully. Timestamps are integer microseconds; the UI works in elapsed seconds.

---

## CLI reference

```bash
qcm view <source...>             # import-if-needed + serve + open browser (easy path)
qcm serve <run-dir...>           # serve already-ingested run dirs
qcm import <source> <dest> [--ps ps.csv]   # import a raw source into a run dir
qcm ingest <parquet> <dest> [--overwrite]  # raw-parquet ingest (large-file tuned)
qcm demo-data <dir> [--preset small|long] [--technique cv|cp]
qcm diagnose <run-dir>           # data-level routing / performance check
qcm notebook <run-dir> [out.ipynb]
qcm export-data <run-dir> <out> [--fmt parquet|csv]
qcm standardize <qsoft.txt> [out.csv]      # instrument export → standardized Time_N/Fr_N/D_N csv
```

### Large files

Ingest is front-loaded and streaming, so a multi-GB parquet is never held as one
object. Tune with `--raw-part-rows` and `--memory-limit`:

```bash
qcm ingest big.parquet ./run --overwrite --memory-limit 2GB --raw-part-rows 250000
```

`qcm diagnose ./run` should report pyramid/sweep-index reads, not full raw scans.

### Serving note (security)

The viewer is a local, single-user tool: the landing page exposes a filesystem
browser and an import pipeline to whoever can reach the port. Keep it on
`localhost` (the default). Do **not** serve it on a shared network
(`--address 0.0.0.0`) — anyone on the network could browse your files.

---

## Notebook export

From the **Export** page, pick *Current range* or a saved region and download the
analysis notebook. It re-opens the run, recomputes the selected quantity and the
QCM-D quantities **with the experiment parameters captured from the UI**, and
includes statistics, a representative raw sweep, and overlapping saved regions.

If the notebook kernel is missing dependencies, the first cell installs them; or
select the project `.venv` kernel in Jupyter.

---

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q          # 152 tests
ruff check .                 # lint (CI gate)
python tools/shoot.py        # screenshot the running app (Playwright + Chrome)
```

Tests cover importers/profiles, the science/echem transforms, multi-run overlay,
and shell/step composition smoke tests. CI (`.github/workflows/ci.yml`) runs the
suite on Linux/macOS/Windows across Python 3.11–3.13 plus the Ruff lint gate.
Architecture decisions are recorded in [`docs/adr/`](docs/adr/); the project
direction is in [`docs/roadmap.md`](docs/roadmap.md).

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE):
free for research, education, and other noncommercial use; commercial use
requires permission. See [ADR 0007](docs/adr/0007-noncommercial-license.md).
