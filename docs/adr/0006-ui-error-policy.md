# 0006 — Defensive surfaces must log, not swallow

Status: Accepted

## Context

Plot and table builders in `qcm/viz/steps/` are wrapped in broad
`except Exception` handlers that return an inline alert instead of blanking the
page — good for a user mid-analysis. But the handlers logged nothing, so a real
bug was invisible unless it happened to print to the `panel serve` console. A
concrete instance: a brush/range write raised server-side every time and the
gesture silently did nothing; the UI gave no signal at all.

## Decision

Defensive handling stays, but **every caught exception is logged with a
traceback and the failing surface's name**. Two pieces:

- `qcm/log.py` — a Panel-free `get_logger()` for the whole `qcm` package
  (NullHandler attached; level via `QCM_LOG_LEVEL`; no `basicConfig` in library
  code). Lives in core so science/IO can log too, honouring [0002].
- `qcm/viz/errors.py` — `surface_error(label, exc)` logs then returns the same
  danger alert as before (user-facing text unchanged), and a `guarded(label)`
  decorator for new surface methods so they need no boilerplate `try/except`.
  Panel is imported lazily so core stays UI-free.

The ~23 existing `return pn.pane.Alert("… failed: {exc}")` sites were retrofitted
to `surface_error(...)`. Behaviour for the user is identical; failures are now
greppable.

## Consequences

- **Good:** failures are recorded with context; the class of invisible bug above
  cannot recur silently.
- **Cost:** broad `except Exception` at surface boundaries remains (deliberately,
  to keep the page alive) — now justified and logged rather than ad-hoc.
- **Obligation:** new surfaces use `@guarded`/`surface_error`; bare
  `except: pass` in science paths is banned (the roadmap proposes enforcing it
  via ruff `BLE001`/`S110`).

[0002]: 0002-pure-science-layer.md
