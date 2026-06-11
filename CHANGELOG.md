# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
