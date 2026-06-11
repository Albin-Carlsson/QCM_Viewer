# 0008 — Profile plugin protocol

Status: Accepted

## Context

[ADR 0003](0003-import-profile-edge.md) put format handling behind import
profiles at the edge, but the registry was a hardcoded list of
`(name, kind, predicate)` tuples with boolean detection and reader functions
scattered per module. Consequences flagged there as costs: an external package
could not add a format, detection was all-or-nothing (ambiguous files couldn't
be ranked), and there was no regression net, so a refactor could silently change
import output. Phase 2 ("extension seams") makes adding future hardware cheap and
safe.

## Decision

Formalise a **`Profile` plugin contract** (`qcm/profiles/base.py`):

- `Profile` protocol: `name`, `kind` (`"qcm"` run source | `"ps"` overlay),
  `detect(path) -> float` confidence in `[0,1]`, and `read(path, *, rename) ->
  ProfileResult` (qcm only). `ProfileResult` = canonical `frame` + `metadata`
  (folded into the manifest) + `warnings` (non-fatal, surfaced to the user).
- `FunctionProfile` adapts the existing per-format predicate + reader into a
  `Profile` without rewriting them; each profile module exposes a `PROFILE`.
- **Confidence-ranked detection**: `detect_profiles(path)` returns
  `(name, confidence)` ranked desc (ties keep registration order); `detect_profile`
  returns the top. This is the new primitive the import UI can use to show
  alternatives for ambiguous files.
- **Discovery**: the registry is the built-in `PROFILE`s plus anything declared
  under the `qcm.profiles` entry-point group, so a new instrument ships as a
  separate pip package. A broken plugin is skipped; names are de-duplicated
  (built-ins win a clash; plugins compete on confidence).
- **Golden-file harness** (`tests/golden/<case>/` + `tests/test_golden_profiles.py`):
  one parametrized test locks each profile's canonical output, so "add a format"
  = drop a folder and drift is caught.

Public functions (`detect_profile`, `profile_kind`, `import_run`,
`resolve_import_target`) and profile **names** are unchanged; the registry is
reimplemented underneath them. See `docs/add-a-data-source.md`.

## Consequences

- **Good:** new data sources (in-tree or third-party plugin) are a small,
  documented, test-locked step; ambiguous files can be ranked rather than
  guessed; import warnings reach the user.
- **Cost:** built-ins are a list, not entry points (entry points need installed
  dist metadata; a from-source run would otherwise lose the built-ins) — so there
  are two registration paths, but they merge through one `profiles()` function.
- **Deferred (later Phase 2):** graded confidence per profile (predicates still
  map to 1.0/0.0 today), a UI affordance for ranked alternatives, and the
  capabilities manifest / technique-protocol / typing-gate increments.
