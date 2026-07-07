# 0004 — Multi-run: shared selection, per-run baseline/origin

Status: Accepted

## Context

The reference workflow's flagship figures overlay several experiments (e.g.
baseline vs. 40 mM TU vs. different Cu loadings) on shared axes, and compare the
same cycle across datasets. Each run starts at a different wall-clock time and
has its own baseline, but the *analysis intent* (which quantity, which time
window, which overtones) is shared across the comparison. A naive "just plot
several files" approach gets the alignment wrong and duplicates controls.

## Decision

`qcm/viz/runset.py::RunSet` holds an ordered collection of runs with exactly one
**active run**. The split:

- **Shared across the set:** the view selection — quantity, x-axis, time/analysis
  range, selected overtones.
- **Per run:** t0 alignment (elapsed-seconds origin) and baseline/reference, so
  overlays line up on a common seconds-from-start, referenced axis even though
  the raw clocks differ.
- **Overlay views** (quantity timelines, echem CV/CP plots, comparison tables)
  consume the whole set; **single-run views** (raw sweep inspector, report)
  follow the active run only — a deliberate scope limit, surfaced with an
  "active run" badge so it is never mistaken for an overlay.
- **Colour encodes identity:** run = hue family, overtone = lightness shade
  within the family (see [0005]), so the same cycle compares across runs by
  family.

Single-run views hold proxies (`ActiveRunView`, `ActiveAttrProxy`) that follow
the active-run selector; shared controls are sized once from the launch run.

## Consequences

- **Good:** the notebook's overlay/compare workflow becomes interactive and
  correct-by-construction; adding a run at runtime is a UI action.
- **Cost:** "shared selection but per-run baseline" is subtle; users must
  understand a window means the same elapsed interval per run, not the same
  wall-clock. Documented in CONTEXT.md's glossary.
- **Limit (intentional):** raw and report act on the active run only. Revisit if
  cross-run raw comparison is ever needed; today it keeps those surfaces simple.

[0005]: 0005-design-token-system.md
