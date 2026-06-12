# Adding a data source (import profile)

A **profile** teaches the viewer to read one instrument export format. Profiles
are the only place format-specific code lives — everything downstream consumes
the single canonical run frame (see [ADR 0003](adr/0003-import-profile-edge.md)).
The registry is deliberately small and added to by hand; there is no plugin
system (this tool expects only a handful of formats).

## The canonical frame

A reader returns a Polars frame in **long form**, one row per (sweep, overtone):

| column | type | meaning |
|---|---|---|
| `timestamp` | int (µs) | sample time |
| `sequence` | int | sweep index (shared across overtones at one time) |
| `group` | int | overtone order n (1, 3, 5, …) |
| `fit_center` | float (Hz) | fitted resonance frequency |
| `fit_fwhm` | float (Hz) | resonance linewidth |
| `frequency` | float | a representative point (= `fit_center` for fit-only data) |

Optional columns enable more views: raw sweep (`frequency` points +
`conductance`/`susceptance`, or `raw_i`/`raw_q`) and electrochemistry
(`potential`/`current`/`charge`). Anything absent degrades gracefully.

## Steps

1. **Write a module** `qcm/profiles/<your_format>.py` with two functions:
   - `is_<your_format>(path) -> bool` — a cheap signature check (header sniff,
     extension, column names).
   - `read_<your_format>(path, *, rename=None) -> pl.DataFrame` — returns the
     canonical frame. (`rename` is optional, for variant column names.)
   Reuse the existing modules as templates — `standardized_csv.py` is the
   simplest.

2. **Register it** in `qcm/profiles/__init__.py`:
   - add a row to `_PROFILE_REGISTRY`:
     `("<your_format>", "qcm", is_<your_format>)` (use `"ps"` for a potentiostat
     overlay; detection order is priority order);
   - add an `elif name == "<your_format>": frame = read_<your_format>(source, rename=qcm_rename)`
     branch in `import_run`.

   That's it — detection, the CLI, and the Add-run UI pick it up automatically.

3. **Add a golden test** (regression net) — drop a folder under `tests/golden/`:

   ```
   tests/golden/<your_format>_basic/
     input.<ext>        # a small real-ish sample
     expected.parquet   # the canonical run table a full import produces
     expected.json      # {"profile","kind","columns","groups","n_rows"}
   ```

   `tests/test_golden_profiles.py` auto-discovers it and asserts that
   `detect_profile` picks your profile and a full `import_run` reproduces
   `expected.parquet` — so a future refactor can't silently change your importer.
   Generate the two `expected.*` files once from a known-good run and commit them
   (the harness's regeneration snippet is in the test's history).

## Verify

```bash
python -m pytest tests/test_golden_profiles.py tests/test_import_*.py -q
ruff check .
qcm view your_sample.<ext>        # imports and opens end-to-end
```
