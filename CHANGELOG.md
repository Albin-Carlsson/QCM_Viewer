# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Persistent run store** — `qcm view file.csv` and the file picker now import
  into `~/.qcm_viewer/runs/` (override: `QCM_RUNS_DIR`) instead of a temp dir,
  so annotations, the alignment offset, experiment parameters and saved view
  state **survive a reboot**. Reopening the same file reuses the prior run (your
  analysis comes back); a changed source re-imports automatically
  (`qcm/store.py`).
- **Windows launcher** — `Start QCM Viewer.bat` mirrors the macOS `.command`
  (one-time uv bootstrap, then `qcm view --port 0`), so lab Windows PCs get the
  same double-click start.
- **Remove a run from the overlay** — each run row has a quiet × control
  (disabled when only one run remains); `RunSet.remove` closes the run's DuckDB
  connection. Non-destructive: the imported files persist in the store, so the
  run (and its saved annotations) can be added back.
- **"Open other measurement…"** — switch to a different file without restarting;
  returns to the picker (the current workspace is remembered and resumable).
- **In-app orientation** — an always-available, collapsed **How this works**
  card (sidebar) lays out the four-page workflow and the two concepts everything
  hinges on (the reference range that defines Δ = 0, overtone normalisation), so
  the tool explains itself instead of needing a written guide. The left/right
  Y-axis and analysis-target selectors gained inline descriptions.

### Changed
- **Denser interface** — a single `UI_SCALE` knob (0.8) scales every size token,
  the Bokeh theme's font sizes, and the fixed plot heights in lockstep, giving
  the whole app the density it reads best at without browser zoom (CSS `zoom`
  breaks Bokeh's responsive canvas sizing). Cycle band markers are now legible
  chips (bold ink on a translucent pill) and thin out instead of overlapping
  when a run has many cycles.
- **Graceful port fallback** — a busy `--port` (default 5006) now falls back to
  a free port with a notice instead of crashing with "address already in use".
- **Clearer landing page** — says what the tool does, lists the supported
  formats inline, and explains the picker's move-to-the-right step.

### Fixed
- **Run directories under quoted paths** (e.g. ``viktor's data/``) broke every
  query with a DuckDB parser error: all embedded ``read_parquet('…')`` paths now
  go through one escaping helper (`qcm/sqlutil.py`), and the near-duplicate
  query builders in `QCMRun` were consolidated while fixing it. Regression
  suite: `tests/test_quoted_paths.py`.
- **CP echem fabrication beyond the potentiostat's recording**: the sidecar
  stream interpolation clamped at the endpoints (`np.interp`), freezing the
  last current/potential across a QCM tail recorded after the potentiostat
  stopped — corrupting cycle detection and CE there. Out-of-span samples are
  now null, matching the CV attach convention.
- **Read-only run directories**: `load_annotations` wrote an empty
  `annotations.json` on its *read* path, crashing annotation reads on
  read-only locations (network shares, archives). Reads no longer write.
- **Failed imports no longer poison the destination**: `ingest` removes the
  half-written run dir on any failure, multi-file sources copy only the
  optional columns common to *all* files, and the DuckDB memory limit is
  validated with a clear error instead of a SQL parser error.
- **Silent failure surfaces**: a failed results-table CSV export no longer
  downloads as a silently empty file (it logs and embeds the error), and
  tap-to-jump / drag-select wiring failures are logged instead of dying
  invisibly (the historical box-select failure mode).

### Changed
- **Pure science layer extracted to `qcm/science/`** (`transforms`, `echem`,
  `quantities`) out of the UI namespace; `qcm.viz.science`/`qcm.viz.echem`/
  `qcm.viz.theme` remain as compatible re-export shims. The import-linter
  contracts got stronger: `qcm.run` and `qcm.notebooks` are now viz-free too.
- **All small JSON writes are atomic** (temp file + rename): manifest,
  annotations, viewer state, session, presets — a crash mid-write can no
  longer truncate a run's metadata.
- **`QCMRun` is closeable** (`close()` / context manager); transient CLI opens
  release their DuckDB connections.
- **Error policy is now machine-enforced**: ruff `BLE001` bans blind
  `except Exception` outside the UI render surfaces; every remaining broad
  catch is logged and carries a reasoned `noqa`.
- **Type-checking in CI**: mypy runs on the core (models, ingest, run,
  profiles, fileio, sqlutil, annotations, timeutil) in the arch job.
- **Dependencies slimmed**: removed unused `datashader`; `jupyterlab`/
  `ipykernel`/`jupyter-bokeh` moved to the optional `[notebook]` extra
  (writing the exported .ipynb needs only `nbformat`).
- **Deprecated `button_type=` swept to `color=`** across the UI (Panel 2.0
  readiness); the suite now fails on any reintroduction (warnings ratchet:
  1198 warnings → 1).
- Golden import harness now covers **PS-paired imports** (CP sidecar + CV
  baked columns); CI coverage floor raised 65 → 70 (suite at 73 %, 210 tests).

### Added
- **`qcm standardize` command**: converts any supported QCM instrument export
  (e.g. a Qsoft `.txt`) into the lab's standardized wide `Time_N/Fr_N/D_N` csv,
  written next to the source by default — the reference notebook's
  data-standardization cell as a one-liner, for tooling outside the viewer
  (`write_standardized_csv` in `qcm/profiles/standardized_csv.py`). The viewer
  itself still imports instrument files directly with no intermediate file.
- **Architecture enforcement** (Phase 2): import-linter contracts
  (`[tool.importlinter]`) make the ADR layering invariants CI failures — the
  pure science layer (`qcm.viz.science`/`echem`) and the core data/IO modules
  never pull rendering libraries, and the storage/model/profile modules never
  import `qcm.viz`. Runs in a dedicated CI `arch` job (`lint-imports`).
- **Import golden-file harness** (Phase 2): `tests/golden/` + `test_golden_profiles.py`
  lock each import profile end to end (detect → read → ingest), so adding a
  format is "drop a folder" and reader drift is caught. The import registry stays
  a simple hand-edited list (a prototyped `Profile`/entry-point plugin system was
  removed as over-engineering — see `docs/add-a-data-source.md` and ADR 0003).

- **Baseline drift correction** (Phase 1): a "Drift correction" toggle (linear or
  quadratic) in the Signal cleanup card fits a polynomial trend of the referenced
  resonance signal over the **reference window** and subtracts it — extrapolated —
  from the whole run, generalising baseline-mean subtraction to remove thermal /
  crystal-aging drift while preserving real steps. Applies consistently to Δf/n,
  ΔD, and Sauerbrey mass across plots, stats, and export; the plot title notes
  "drift-corrected (linear/quadratic)" (`science.detrend`). Toggle off/on to
  compare before/after.
- **Composite figure builder** (Phase 1): a new **Figure** page that composes the
  reference notebook's flagship output — E(t) / Δf/n(t) / ΔD(t) (and optionally
  Current / Charge / Mass / MPE) stacked on a shared time axis, every loaded run
  overlaid as a colour family with per-overtone shades. Toggle panels, pick a
  journal column width, and download **true vector PDF/SVG** (or PNG) rendered
  with matplotlib. Reuses the existing `value_df`/`overlay_value_df` services and
  the design-token colours, and honours the reference-electrode label on the E
  panel. New `qcm/viz/figure.py` (UI-free builder) + `qcm/viz/steps/figure.py`.
- **One-click PS↔QCM alignment** (Phase 1): the alignment card's residual-lag
  estimate can now be applied in-app — no CLI re-import. CP EQCM imports retain
  the raw potentiostat stream as a sidecar (`echem.parquet`); the echem channels
  are derived onto the QCM clock at a manifest `ps_offset_s`, so **Apply this
  offset** / **Reset** re-align instantly and exactly (re-interpolated from the
  raw stream), reversibly, and the offset persists with the run and shows in Run
  info. Echem reads are funnelled through one chokepoint (`QCMViewData._timeline`);
  the offset is part of the cache key.
- **Auto-suggested baseline** (Phase 1): a "Suggest stable window" button on the
  Reference range card finds the flattest stretch near the run start (minimum
  variance of the resonance signal, `science.stablest_window`) and fills the
  reference range with it — a suggestion the user can accept or nudge, never
  applied silently.
- **Sensor/cell presets** (Phase 1): named presets bundling the experiment
  parameters (electrode area, Sauerbrey sensitivity, molar mass M, valency z,
  reference electrode), persisted globally at `~/.qcm_viewer/presets.json`
  (override `QCM_PRESETS_FILE`). Load/save/delete from the Experiment parameters
  card so a cell is configured once and reused on every run.
- **Reference-electrode metadata** (Phase 1): a per-run `reference_electrode`
  experiment parameter that annotates every potential axis ("Potential
  [V vs Ag|AgCl]") across the Data hero, the E(t) strip, the Results echem plots
  (CP profile, voltage profile, cycle overlay), the Run info card, and the HTML
  report. Persists with the run's view state. Notebook-parity ("V vs. Ag|AgCl").
- Continuous integration (GitHub Actions): pytest matrix on Linux/macOS/Windows
  across Python 3.11–3.13, plus a Ruff lint gate.
- `LICENSE` (PolyForm Noncommercial 1.0.0), `CITATION.cff`, and this changelog.
- `qcm.logging` error policy: a `guarded` decorator that logs caught exceptions
  with context (run id + surface name) instead of swallowing them silently,
  applied to the plot/table surfaces in `qcm/viz/steps/`.
- Architecture decision records under `docs/adr/` covering the file-backed run
  contract, the pure science layer, the import-profile edge, multi-run
  semantics, and the design-token system.
- `docs/roadmap.md`: a vision/UX/architecture guide for surpassing existing
  QCM-D/EQCM tools.

### Changed
- Project renamed from `qcm-refactor` to `qcm-viewer`.
- CP PSTrace imports no longer bake potential/current/charge into the main fit
  table — they are retained as the raw stream (`echem.parquet`) and derived on
  read, enabling the editable alignment offset above. CV and parquet-native
  echem are unchanged.

### Fixed
- Raw resonance-sweep exports **without I/Q** (conductance/susceptance-only, e.g.
  a custom acquisition tool's parquet) are now recognised as raw runs — the
  sweep/waterfall inspector is available instead of the run being mistaken for
  fit-only. `has_raw` keys off any per-point measured signal (I/Q *or*
  conductance/susceptance), and the I/Q scatter degrades to a clear
  "No I/Q traces in this export" note rather than erroring.
- Box-select brushing and typed Start/End range edits now apply (the programmatic
  `value_throttled` write is wrapped in `edit_constant`, which previously raised
  server-side and silently dropped the gesture).
- Results-page plots reset their axis scale to the selected cycle / cycle range
  (`linked_axes=False` opts each figure out of Panel's document-wide range union).
- Topbar button tooltips render on screen (explicit bottom-positioned `Tooltip`),
  including the disabled "Inspect raw sweeps" explanation.
- Run-info card restyled to the design system.

## [0.3.0] — 2026-06-10

Baseline release: the viewer at the end of the import + multi-run + EQCM cycling
work (tracker issues #1–#15).

### Added
- **Flexible multi-format import** via auto-detected profiles: Qsoft `.txt`,
  standardized `Time_N/Fr_N/D_N` CSV, PSTrace CP and CV potentiostat CSV, and
  parquet — with override and per-column mapping for variant CSVs. Fit-only
  sources (Qsoft Fr/D) are first-class; raw-only views degrade gracefully.
- **EQCM electrochemistry analysis**: technique auto-detection (CV/CP),
  current-sign half-cycle model, per-cycle Coulombic efficiency (charge basis
  with time fallback), whole- and half-cycle mass-per-electron, mass-vs-charge
  (M/z slope), Faraday-law prediction overlay, and a PS↔QCM cross-correlation
  alignment check that suggests the import offset.
- **Multi-run overlay**: a run set with one active run, shared selection, and
  per-run baseline / time origin; run = colour family, overtone = shade.
- **Editable per-run experiment parameters** (electrode area, Sauerbrey
  sensitivity, molar mass, valency) feeding every derived quantity consistently,
  with a sensitivity-from-f₀ helper.
- **Cycle handling**: all / single / range selection; cycle overlay on a common
  origin with optional f/D zeroing; per-cycle summary table.
- **Sauerbrey validity check** (overtone spread + viscoelastic ratio) and an
  honest-provenance UI (CV scan-rate source, MPE clipping, n=1 no-op notes).
- Run manager (add run at runtime, edit label, pick active), saved phases,
  manual Y window, CV direction arrows, E(t) context strip.
- Reproducible notebook export capturing the UI experiment parameters.
- File-backed run contract (manifest + chunked raw parquet + decimation pyramid
  + sweep index) read through a single `QCMRun` boundary (DuckDB + Polars).
- CLI: `view`, `serve`, `import`, `ingest`, `demo-data`, `diagnose`,
  `notebook`, `export-data`.

[Unreleased]: https://github.com/Albin-Carlsson/QCM_Viewer/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Albin-Carlsson/QCM_Viewer/releases/tag/v0.3.0
