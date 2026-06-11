# Adding a data source (import profile)

A **profile** teaches the viewer to read one instrument export format. Profiles
are the only place format-specific code lives — everything downstream consumes
the single canonical run frame (see [ADR 0003](adr/0003-import-profile-edge.md)
and [ADR 0008](adr/0008-profile-plugin-protocol.md)). Adding one — in-tree or as
a separate pip package — should take ~30 minutes.

## The contract

A profile implements `qcm.profiles.base.Profile`:

```python
class Profile(Protocol):
    name: str            # stable id, also the UI "force profile" value
    kind: Literal["qcm", "ps"]   # run source, or potentiostat overlay
    def detect(self, path: Path) -> float: ...   # 0..1 confidence
    def read(self, path: Path, *, rename=None) -> ProfileResult: ...
```

- **`detect`** returns a confidence in `[0, 1]` (0 = "not mine"). Detection ranks
  all profiles by confidence, so return a higher number when the signature match
  is stronger; a boolean check can just return `1.0`/`0.0`.
- **`read`** (qcm profiles only) returns a `ProfileResult(frame, metadata,
  warnings)`:
  - `frame` — the **canonical long-form frame**: one row per (sweep, overtone)
    with `timestamp` (µs int), `sequence`, `group` (overtone order n),
    `fit_center` (Hz), `fit_fwhm` (Hz), and optionally `frequency`. Raw columns
    (`raw_i`, `conductance`, …) and echem columns are optional.
  - `metadata` — provenance folded into the run manifest.
  - `warnings` — non-fatal notes (assumed defaults, dropped rows) surfaced to the
    user without failing the import.
- A **`ps`** profile (potentiostat overlay) implements `detect` only; pairing is
  owned by `import_run`.

The quickest path reuses `FunctionProfile`, which wraps a predicate + reader:

```python
# qcm_profile_acme/__init__.py
from qcm.profiles.base import FunctionProfile, ProfileResult

def _detect(path): return 1.0 if path.suffix == ".acme" else 0.0
def _read(path, rename=None): return ProfileResult(frame=_to_canonical(path))

PROFILE = FunctionProfile("acme_qcm", "qcm", _detect, _read)
```

## Register it

**In-tree:** add the module's `PROFILE` to `_BUILTIN_PROFILES` in
`qcm/profiles/__init__.py` (detection-priority order; ties break by position).

**As a plugin package:** declare an entry point — no core change needed:

```toml
# the plugin package's pyproject.toml
[project.entry-points."qcm.profiles"]
acme = "qcm_profile_acme:PROFILE"   # a Profile instance, or a zero-arg factory
```

The viewer discovers it on startup via the `qcm.profiles` group. A plugin that
fails to load is skipped (it can't break import); names are de-duplicated
(built-ins win a name clash — plugins compete on detection confidence).

## Add a golden test (lock the output)

Drop a folder under `tests/golden/`:

```
tests/golden/acme_basic/
  input.acme         # a small real-ish sample
  expected.parquet   # the canonical frame your read() should produce
  expected.json      # {"profile","kind","columns","groups","n_rows","warnings"}
```

`tests/test_golden_profiles.py` auto-discovers it: it asserts `detect_profile`
picks your profile and `read()` reproduces `expected.parquet` exactly — so future
refactors can't silently change your importer. Generate the two `expected.*`
files once from your known-good reader and commit them.

## Verify

```bash
python -m pytest tests/test_golden_profiles.py tests/test_import_*.py -q
ruff check .
qcm view your_sample.acme        # imports and opens end-to-end
```
