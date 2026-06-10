# 0001 — File-backed run contract

Status: Accepted

## Context

A measurement ("run") can be small (a fit-only CSV) or large (a multi-GB raw
frequency-point parquet). The tool is local-first: a researcher's laptop, no
database server, files that must stay openable years later. We need a storage
shape that (a) loads broad overviews instantly without scanning raw data, (b)
still serves individual raw sweeps on demand, and (c) is inspectable and
portable (copy a folder, hand it to a collaborator).

## Decision

An imported run is a **directory of Parquet + JSON**, not a database, described
by a `manifest.json` (`qcm/models.py::Manifest`). Layout:

- `manifest.json` — schema version, time bounds, columns, groups, metadata.
- `raw/part-*.parquet` — the raw frequency-point table, chunked.
- `sweeps/index.parquet` — one row per (sequence, group): fast fit timelines.
- `pyramid/<level>/…` — precomputed time-bucket decimations (`100ms`…`1h`) for
  broad overviews.
- `annotations.json`, `expressions.json` — saved phases and reserved derived
  expressions.

The minimal contract (`qcm/ingest.py::CORE_REQUIRED`) is
`timestamp, sequence, group, fit_center, fit_fwhm`. Raw and electrochemistry
columns are **optional** column groups, so fit-only instrument exports are
first-class. Timestamps are integer microseconds; the UI works in elapsed
seconds. Ingest is streaming/front-loaded so a multi-GB source is never held as
one in-memory object.

## Consequences

- **Good:** overviews read tiny pyramid/index files, not raw — the app scales to
  large runs (`qcm diagnose` verifies the routing). Runs are portable and
  git/Zenodo-friendly. Old runs keep opening as long as the manifest is honoured.
- **Good:** optionality of column groups is what makes fit-only runs and future
  channels additive rather than breaking.
- **Cost:** import does real work up front (pyramids + index) — slower first
  open in exchange for fast interaction after.
- **Obligation:** the schema must evolve compatibly (see the roadmap's
  capabilities-list + migration-ladder proposal); `schema_version` exists for
  this. Nothing may read the Parquet directly except through the single read
  boundary (see [0002]).

[0002]: 0002-pure-science-layer.md
