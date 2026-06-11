# Architecture Decision Records

Each ADR captures one significant decision: the context that forced it, the
choice made, and the consequences (good and bad). They are the project's
institutional memory — read the ones touching an area before changing it.

These initial records are a **backfill**: the decisions were already made and
embedded in the code; this writes them down. New decisions get a new numbered
file going forward (never edit a decided ADR — supersede it with a new one).

Format: lightweight [MADR](https://adr.github.io/madr/). Status is one of
`Accepted`, `Superseded by NNNN`, or `Proposed`.

| # | Title | Status |
|---|---|---|
| [0001](0001-file-backed-run-contract.md) | File-backed run contract | Accepted |
| [0002](0002-pure-science-layer.md) | Panel-free, unit-tested science layer | Accepted |
| [0003](0003-import-profile-edge.md) | Import profiles at the edge → one canonical run | Accepted |
| [0004](0004-multi-run-semantics.md) | Multi-run: shared selection, per-run baseline/origin | Accepted |
| [0005](0005-design-token-system.md) | Single tokenised stylesheet under shadow DOM | Accepted |
| [0006](0006-ui-error-policy.md) | Defensive surfaces must log, not swallow | Accepted |
| [0007](0007-noncommercial-license.md) | PolyForm Noncommercial license | Accepted |
| [0008](0008-profile-plugin-protocol.md) | Profile plugin protocol (confidence detection, entry points, golden harness) | Accepted |
