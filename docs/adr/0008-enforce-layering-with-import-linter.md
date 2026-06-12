# 0008 — Enforce layering with import-linter

Status: Accepted

## Context

[ADR 0001](0001-file-backed-run-contract.md) and
[ADR 0002](0002-pure-science-layer.md) promise a layered design: a pure,
Panel-free science layer and a core data/IO layer that never depends on the UI.
Until now these were conventions — easy to violate by accident (a stray
`import panel` in `science.py`, or a core module reaching into `qcm.viz`), and
nothing would catch it.

## Decision

Make the layering invariants **CI failures** with
[import-linter](https://import-linter.readthedocs.io) (`[tool.importlinter]` in
`pyproject.toml`, run by the `arch` job in CI). Three forbidden contracts:

1. **Pure science layer is UI-free** — `qcm.viz.science` and `qcm.viz.echem` may
   not import `panel`, `bokeh`, `holoviews`, `hvplot`, or `datashader`.
2. **Core data/IO never pulls rendering libraries** — `qcm.run`, `qcm.ingest`,
   `qcm.models`, `qcm.profiles`, `qcm.timeutil`, `qcm.annotations`, `qcm.log`
   stay free of those same libraries (verified transitively).
3. **Storage/model layer is viz-free** — `qcm.ingest`, `qcm.models`,
   `qcm.profiles`, `qcm.timeutil`, `qcm.annotations`, `qcm.log` may not import
   `qcm.viz` at all.

## Consequences

- **Good:** the architecture the ADRs describe is now mechanically enforced, not
  trusted; a regression fails CI with the exact offending import chain.
- **Known wrinkle (documented in the contracts):** `qcm.run` is intentionally
  excluded from contract 3 because its notebook export (`to_notebook`) reuses the
  *pure* science layer, which today is namespaced under `qcm.viz`
  (`qcm.viz.science`/`theme` are UI-free). Relocating that pure layer out of
  `qcm.viz` would let `run` join contract 3 too — future work, not blocking.
- **Cost:** the `arch` CI job installs the package to build the import graph, so
  it is heavier than the pure-text ruff job (kept separate so ruff stays fast).
