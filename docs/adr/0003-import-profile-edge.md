# 0003 — Import profiles at the edge → one canonical run

Status: Accepted

## Context

QCM and potentiostat vendors each export different formats, and a single vendor
changes its format between software versions. The reference workflow
(`QCM_data_treatment_examples.ipynb`) spends its first cells fighting this:
tab vs. comma, decimal commas, UTF-16, `skiprows`, regex header mapping,
scan-rate-from-filename. The lab's own guidance is "define data loading to be as
flexible as possible … account for differences in column names, formats, etc."
If format-handling leaks downstream, every viewer feature becomes format-aware
and brittle.

## Decision

A thin **adapter layer at the import edge** (`qcm/profiles/`) absorbs all format
variation and emits the single canonical long-form run frame
(`timestamp, sequence, group, fit_center, fit_fwhm, frequency`, one row per
sweep×overtone) that `qcm.ingest.ingest` consumes. Profiles:

- are **signature-detected** in priority order via a registry
  (`_PROFILE_REGISTRY`), with manual override and per-column mapping for variant
  CSVs;
- are typed `qcm` (a resonance source that becomes the run) or `ps` (a
  potentiostat export merged onto a QCM source);
- carry format-specific provenance forward (e.g. CV scan-rate source) rather
  than hiding it.

Current profiles: `standardized_csv`, `qsoft_txt`, `pstrace_cv`, `pstrace_cp`,
plus parquet. Everything downstream sees only the canonical contract.

## Consequences

- **Good:** new formats are isolated to the edge; the rest of the app never
  changes. Fit-only sources (Qsoft Fr/D) and EQCM sources share one contract.
- **Good:** auto-detection + auto-pairing of `*_PS.csv` removes the notebook's
  manual encoding/skiprow trial-and-error.
- **Cost:** detection is heuristic; ambiguous files can mis-detect (mitigated by
  override). The registry stays deliberately simple — a `(name, kind, predicate)`
  list plus an explicit reader dispatch in `import_run` — because this tool
  expects only a handful of formats added by hand. A `Profile`/entry-point plugin
  system and confidence-ranked detection were prototyped and **removed as
  over-engineering** (YAGNI for 2–3 formats); a golden-file harness
  (`tests/golden/`) is kept as the regression net for "add a format."
- **Obligation:** every profile must produce the *identical* canonical contract;
  divergence there breaks the one-read-path guarantee in [0002]. See
  `docs/add-a-data-source.md`.

[0002]: 0002-pure-science-layer.md
