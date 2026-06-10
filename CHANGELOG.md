# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Fixed
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
