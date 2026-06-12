# QCM Viewer — domain context

A local, file-backed viewer/analysis tool for QCM-D and EQCM measurements.
This file fixes the project's vocabulary; use these terms in issues, tests,
and docs.

## Glossary

- **Run** — one ingested measurement: a directory of Parquet + JSON with a
  `manifest.json` (see README → Architecture). The unit everything operates on.
- **Run set** — an ordered collection of loaded runs with one **active run**
  (`qcm/viz/runset.py`). Single-run views follow the active run; overlay views
  consume the whole set. Persisted as the **session**
  (`~/.qcm_viewer/last_session.json`).
- **Profile** — a format adapter at the import edge (`qcm/profiles/`):
  Qsoft `.txt`, standardized `Time_N/Fr_N/D_N` CSV, PSTrace CP CSV, PSTrace CV
  CSV, parquet. Auto-detected, overridable, with per-column mapping for
  variant CSVs. All profiles produce the same run contract.
- **Group / channel** — one resonance channel in the data (`group` column).
  Maps to an **overtone order n** (editable; `Δf/n` normalization).
- **Fit-only run** — a run imported from fitted Fr/D values with no raw
  frequency-point data; raw views (sweep inspector, waterfall) degrade
  gracefully.
- **Analysis range / Reference range / Saved phases** — the three selection
  concepts (see README → Concepts). The reference range defines zero for Δ
  quantities; per run in a set, t0 alignment and baseline are independent,
  while the selection itself is shared.
- **Quantity** — a plottable derived signal registered in
  `qcm/science/quantities.py` (re-exported via `qcm/viz/theme.py`)
  (`Δf`, `Δf/n`, `ΔD`, Sauerbrey mass, current, potential, charge, MPE, …).
- **Technique** — CV (cyclic voltammetry) or CP (chronopotentiometry /
  galvanostatic cycling), auto-detected from the waveform, overridable.
- **Cycle** — for CP, derived from the current sign (plating = negative
  current, stripping = positive); never read from an instrument column. For
  CV, one scan.
- **CE (Coulombic efficiency)** — per cycle, `|Q_strip / Q_plate|` (charge
  basis, primary) or `t_strip / t_plate` (time fallback).
- **MPE (mass per electron)** — `F · Δm / Δq` in g/mol; dynamic (per sample,
  noisy → clip/smooth display controls) or static per (half-)cycle. Target
  MPE = M/z from the experiment parameters.
- **Experiment parameters** — per-run editable area, Sauerbrey sensitivity,
  molar mass M, valency z. Feed every derived quantity consistently.
- **PS pairing / alignment** — a PSTrace export is zeroed at start and
  interpolated onto QCM timestamps at import (`--ps`, `--ps-offset`). CV has
  no time axis; its time base is reconstructed from the scan rate.

## Key decisions (summary)

- Import is a profile/adapter layer at the edge feeding **one canonical run
  contract**; raw columns are optional, fit-only runs are first-class.
- Multi-run: shared selection, per-run baseline/origin; overlay applies to
  time-series, echem plots, and comparison tables — raw and report views act
  on the active run only.
- Colours: run = hue family, overtone = lightness shade within the family
  (`qcm/viz/tokens.py`).
- Panel/Bokeh ship shadow DOM: cross-component CSS silently fails; cards need
  the explicit `qcm-card` class. Verify UI work with screenshots
  (`tools/shoot.py`), not by reading CSS.

## Issue tracker

GitHub Issues on remote `Albin-Carlsson/QCM_Viewer` via `gh`
(see `docs/agents/issue-tracker.md`).
