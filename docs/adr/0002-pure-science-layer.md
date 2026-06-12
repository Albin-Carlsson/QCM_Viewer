# 0002 — Panel-free, unit-tested science layer

Status: Accepted

## Context

The numbers this tool produces — Δf/n, dissipation, Sauerbrey mass, MPE,
coulombic efficiency, alignment lag — are the whole point; if they are wrong,
nothing else matters. Science logic entangled with UI callbacks is untestable
(needs a running Panel/Bokeh document) and unciteable (reviewers can't audit it).
There must also be one read path so level-routing and baseline aggregation can't
drift between the UI, the CLI, and exported notebooks.

## Decision

Two hard layering rules:

1. **Pure science.** `qcm/viz/science.py` and `qcm/viz/echem.py` are
   side-effect-free Polars/Python — no Panel imports — and unit-tested. Every
   science/behaviour constant (Sauerbrey 17.7, Faraday, dissipation scale,
   despike thresholds, electrode area, Sauerbrey-validity cutoffs) is **named
   and sourced** in `qcm/viz/theme.py`, not inlined as a magic number. The
   DuckDB SQL path (`science.raw_value_sql`) is kept in lockstep with the Polars
   path (`science._raw_value`).
2. **One read boundary.** UI, CLI, and exported notebooks all open a
   `qcm.run.QCMRun`; nobody reads Parquet directly. Level routing (pyramid vs.
   sweep index vs. raw) and baseline aggregation live there, once.

## Consequences

- **Good:** the science is tested without a browser, fast, and portable into the
  notebook export — which recomputes quantities with the UI's experiment
  parameters, so a result is reproducible.
- **Good:** changing a constant (e.g. sensitivity from f₀) changes every derived
  quantity consistently because they all read `ExperimentParams`/`theme`.
- **Cost:** the SQL/Polars lockstep is a manual invariant (currently a comment;
  the roadmap proposes a parametrized equivalence test to enforce it).
- **Obligation:** keep Panel out of `science`/`echem`. This is now **enforced by
  import-linter** (`[tool.importlinter]` in `pyproject.toml`, run in CI's `arch`
  job; see [0008]) — a CI failure, not a convention. The same rule lets
  `qcm/log.py` (core) be Panel-free while the UI error helper lives in
  `qcm/viz/errors.py` (see [0006]).

[0006]: 0006-ui-error-policy.md
[0008]: 0008-enforce-layering-with-import-linter.md
