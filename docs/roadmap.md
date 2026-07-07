# Beyond the industry tools — vision, UX, and architecture guide

How to take QCM Viewer from "excellent lab tool" to the best QCM-D/EQCM analysis
software available, commercial or open. Grounded in three things: the lab's
reference workflow (`QCM_data_treatment_examples.ipynb`), the published
tool landscape, and established UX principles.

---

## 1. The north star

No existing tool covers the whole journey from instrument export to publication
figure for **electrochemical** QCM work:

| Tool | What it does well | What it lacks |
|---|---|---|
| **QSense Dfind** (commercial) | Smartfit viscoelastic modeling with fit-quality "traffic lights", material library, **batch mode** (analyze 100 datasets in one go), guided raw-data → report flow | No electrochemistry at all; locked to QSense formats; license cost; Windows-only |
| **PyQTM** (AWSensors, free) | Voigt viscoelastic fitting with χ² landscape inspection | Modeling only — no viewer, no EQCM |
| **RheoQCM** (Shull group, open) | Multi-harmonic viscoelastic property extraction; acquisition | Specialist modeling tool, steep entry |
| **pyQCM-BraTaDio** (open, SoftwareX-class) | Manufacturer-agnostic import, interactive baseline/range selection, plot export | Tkinter-grade UX; no EQCM, no cycles, no multi-run, no data backbone |
| **openQCM software** (open) | Real-time acquisition for openQCM hardware | Viewer is basic; no analysis depth |
| **Origin/Excel + ad-hoc notebooks** (the real competitor) | Infinitely flexible; publication figures | Everything is manual, repeated, and irreproducible |

The EQCM literature (Vanoppen 2024 review on QCM for metal plating; Shpigel/Aurbach
"affordable electrogravimetry"; Leppin 2021 modulation-QCM) converges on the same
derived quantities this viewer already computes — mpe (mass per electron),
charge-based coulombic efficiency, mass-vs-charge slopes, Faraday-law overlays,
Sauerbrey-validity checks — but every group rebuilds that pipeline privately in
notebooks. **The dream tool is the one that makes that pipeline a product:**

> Drop in any instrument's files → everything is detected, aligned, and validated
> automatically → every number carries its assumptions visibly → one click yields
> a publication-grade figure or a reproducible notebook → and adding next year's
> instrument format is a 30-minute plugin, not a rewrite.

Strategy note: an open tool beats a commercial one on *distribution* (every
collaborator can open your runs), *transparency* (reviewers can audit the math),
and *integration* (echem + QCM in one place). Pair the roadmap below with a
JOSS/SoftwareX paper and a `CITATION.cff` and the tool markets itself.

---

## 2. Notebook parity audit

Everything `QCM_data_treatment_examples.ipynb` does, what the viewer does today,
and how to *improve on* (not just match) each step.

| Notebook step | Today in the notebook | Viewer status | How the viewer must beat it |
|---|---|---|---|
| Qsoft `.txt` → standardized CSV (regex header mapping, decimal comma) | Hand-edited path in a script; intermediate CSV written next to source | ✅ `qsoft_txt` profile, auto-detected, no intermediate file; `qcm standardize` emits the lab-exchange CSV for outside tooling | Done. Keep the notebook's spirit: **never break on a new header variant silently** — show the detected mapping and let the user remap (partially exists). |
| Load PSTrace CSV (utf-16, skiprows=5, unit columns) | Encoding/skiprow trial-and-error per file | ✅ `pstrace_csv` profile + auto-pairing of `*_PS.csv` | Done. |
| Manual trimming (`start_idx=2`) + re-zero time per dataset | Edit a constant, re-run | ✅ per-run t0 alignment + reference range | Done, and shared selection across runs is better than the notebook ever was. |
| **Stacked composite figure: E(t) / Δf(t) / ΔD(t), shared x, per-overtone shades, two experiments overlaid, colorblind palettes** | The notebook's flagship output (cell 5) | ✅ Figure page: composite builder with toggleable panels, run overlay, vector export | Done. |
| Axis label carries the reference electrode ("V vs. Ag\|AgCl") | Hardcoded string | ✅ `reference_electrode` experiment param flows into every potential axis, Run info, and the report | Done. |
| Crystal constants (f₀ = 4.95 MHz, ρq, µq → scale µg/C) | Redefined in every cell, drift risk | ✅ `ExperimentParams` + `sensitivity_from_f0` | Done — and provenance-visible. Add per-sensor presets so they're entered once per lab, ever (§3). |
| Static mpe per plating/stripping cycle, multi-dataset comparison | Manual time windows per file (`start_time=0, end_time=6000`) | ✅ half-cycle MPE table, cycle filtering, multi-run | Done; CE is charge-based with time fallback (better than the notebook's time-only). |
| Dynamic mpe (gradient Δf/ΔQ) + Savgol smoothing + twin axis | np.gradient + manual savgol params | ✅ mpe quantity + clip/smooth controls + twin axis | Done. Add uncertainty bands (§4 Tier 2). |
| CV: stitch `CV i vs E Scan n` columns, scan rate from filename, reconstruct time, per-cycle split | Fragile regex + fallback constant | ✅ `pstrace_cv` profile; scan-rate provenance shown in Run info | Done. Improve: when the filename token is missing, *ask* with the detected default instead of silently assuming 25 mV/s (§3, automation ladder). |
| CV zoom insets for small features | Static matplotlib insets | ✅ interactive wheel/box zoom (strictly better) | Consider "pinned zoom regions" that persist into exports so the inset survives into the figure. |
| CV direction arrows | "Haven't added that yet" (notebook) | ✅ direction arrows | Already ahead of the notebook. |
| Cycle wishlist (cell 4): select cycle / ranges, reset-to-origin compare, cross-dataset cycle compare, CE per cycle, mass accumulation | All listed as *future hopes* | ✅ all implemented | The viewer has fully absorbed the notebook's wishlist. |
| Publication-grade output (fonts, sizes, vector) | matplotlib → journal-ready | ✅ Figure page exports SVG/vector with journal presets | Done. |

**Conclusion (updated 2026-06):** every notebook step — and every wish in its
text discussion — now exists in the viewer, usually in a stronger form
(charge-based CE, measured-charge Faraday overlay, interactive zoom, shared
multi-run selection). The composite figure, vector export, reference electrode,
and per-sensor presets closed the last parity gaps; `qcm standardize` covers the
literal CSV-conversion step for tooling outside the viewer. The notebook can be
retired.

---

## 3. UX principles → workflow rules

Every design decision should be justifiable by a named principle. The ones that
matter here, and the concrete rules they produce:

**1. Zero-configuration first contact** (defaults over dialogs; Nielsen:
*flexibility & efficiency*). Opening a file must never ask a question it can
answer itself. Format, technique, cycles, pairing, scan rate — all detected.
Rule: *a new user gets a correct default view of any supported file in one
action with zero parameters.* Already largely true; protect it in tests.

**2. The automation ladder: detect → suggest → confirm → remember.** Automation
is good *if the user stays in charge* (Nielsen: *user control*; also the
"mixed-initiative" interaction literature). Apply it consistently:
- **Alignment:** the cross-correlation lag is already computed and even prints
  the right `--ps-offset`. Today acting on it means *re-importing from the CLI* —
  the single most frustrating step left. Make it one click: "Apply +1.4 s
  offset" in the alignment card, stored in the manifest, reversible.
- **Baseline:** auto-suggest the most stable window (minimum rolling variance of
  Δf over the run head) as a *pre-filled, visible, editable* reference range —
  never silently chosen. BraTaDio makes users pick baselines by hand every
  session; beating it means suggesting well.
- **Scan rate:** detected-from-filename is a guess; show it as a confirmable
  chip on import ("25 mV/s — from filename. Correct?"), not only in Run info.
- **Remember:** every confirmation becomes the default next time for that
  sensor/electrolyte (see presets, below).

**3. Don't make the user repeat themselves** (recognition over recall; DRY for
humans). Things typed twice are bugs:
- **Sensor/cell presets:** a named preset bundles f₀/sensitivity, electrode
  area, reference electrode, and species (M, z). One lab sets up "Cu 5 MHz disc,
  Ag|AgCl, Zn²⁺" once; every import offers it. Store in `~/.qcm_viewer/presets/`
  + per-run override in the manifest.
- **Analysis templates:** the saved view state generalized — selection +
  reference + quantities + cycle mode as a named template applicable to any run
  (this is also the seed of batch mode, §4).

**4. Direct manipulation on the data itself** (Shneiderman). Ranges are set by
dragging on the plot; cycles by clicking a cycle band; baseline by dragging the
suggested region's edges. Typed entry stays as the precision fallback, never the
primary path. (The selection-mode toggle + brush already embodies this — extend
it to cycle picking: click a cycle stripe on the hero to select that cycle.)

**5. Visibility of assumptions** (Nielsen: *visibility of system status*; also
basic scientific honesty). The viewer's best existing habit — CV time-base
provenance, MPE clipping notes, "n=1 (no normalization)" — should become a
formal rule: *every derived number can show its assumptions on hover/expand*
(sensitivity used, baseline window, area, alignment offset, despike on/off).
This is the feature reviewers and supervisors will love, and no commercial tool
has it.

**6. Errors must be visible, recoverable, and named** (Nielsen: *error
recovery*). The current 84 broad `except Exception` handlers keep the UI alive
but can hide real failures (today's box-select bug was invisible in the UI).
Policy: every caught exception is logged with context; user-facing alerts say
what failed *and what to try*; a debug panel surfaces the last N errors.

**7. Progressive disclosure.** The default surface stays as calm as the current
declutter pass made it (3 overtones, legends quiet). Power features (despike
windows, MPE clip bounds, per-channel orders) live behind disclosure — present,
never in the way.

**8. Undo everything.** "Undo zero change" exists; generalize to a small action
history (range changes, alignment offset, phase edits). Scientists explore;
exploration without undo is anxiety.

---

## 4. Stand-out features

### Tier 1 — finish the workflow (parity gaps + friction killers)

1. **Composite figure builder** — the notebook's stacked E(t)/Δf(t)/ΔD(t)
   shared-x layout as a first-class view and the default *export object*.
   Panels are toggleable (E, Δf, ΔD, I, Q, mpe), runs overlay with the existing
   colour families. This is simultaneously the missing parity feature and the
   publication-figure feature.
2. **Vector export with journal presets** — SVG/PDF (Bokeh supports SVG
   backends), presets for single/double-column widths, font sizes, and
   colorblind-safe palettes (the notebook already used Oranges/Blues ramps —
   formalize). Every plot gets a "download figure" affordance; the composite
   builder gets the full preset dialog.
3. **One-click alignment correction** (from §3) — kill the re-import loop.
4. **Auto-suggested baseline** (from §3).
5. **Reference-electrode metadata** — flows to every potential axis and export.
6. **Drift correction** — fit linear/polynomial drift on the reference window
   (or a dedicated "drift region") and subtract; standard in long QCM-D runs and
   conspicuously absent from the notebook *and* most tools. Show the fitted
   drift as an overlay before applying (automation ladder).
7. **Temperature channel** — ingest when present (Qsoft exports it), plot as a
   context strip like E(t), and warn when Δf correlates with ΔT (the classic
   artifact).

### Tier 2 — beat Dfind at its own game

8. **Batch mode / analysis templates** — Dfind's killer feature, reimagined:
   apply a named analysis template to a folder of runs; get the comparison
   table, per-cycle stats, and composite figures for all of them in one pass.
   The architecture is ready (runs are directories; the CLI exists) — this is
   mostly a `qcm batch` command + a results-grid page.
9. **Guided viscoelastic modeling** — Voigt/Voinova fitting of Δf/ΔD across
   overtones with χ²-landscape honesty (PyQTM's strength) and traffic-light fit
   quality (Dfind's strength). Scope it: thin-film Voigt first, with the
   existing `sauerbrey_check` deciding *when to offer it* ("film looks soft —
   model it?"). This is the single biggest analysis-depth gap vs. industry.
10. **Uncertainty everywhere** — CIs on CE, mpe, and mass-vs-charge slopes
    (bootstrap over cycles; SEM already exists in stats). Numbers without error
    bars don't survive review.
11. **Artifact detection** — flag spikes (despike already finds them — report
    them instead of only fixing), film loss events (Δf jumps), bubble
    signatures (simultaneous f/D excursions), and crystal-health verdicts from
    the raw sweep inspector (Q factor trend, fit residuals).
12. **Cross-experiment dashboards** — the lab's real question is "CE vs.
    additive concentration across these 12 runs". A meta-view over a run set
    (any per-cycle stat vs. run label/metadata field) turns the viewer into the
    lab's results database.

### Tier 3 — the dream

13. **FAIR data bundles** — export a run as a frictionless *datapackage* (CSV +
    JSON metadata with units, following echemdb/yadg practice) so datasets are
    citable, machine-readable, and repository-ready (Zenodo). Import the same
    format back. This positions the tool inside the emerging FAIR
    electrochemistry ecosystem rather than as another silo.
14. **Live companion mode** — watch a directory during acquisition and update
    the view (the file-backed architecture supports appending parts; Bokeh
    supports streaming). Even read-only live viewing beats QSoft's screen.
15. **Protocol-aware analysis** — parse the potentiostat *method* (applied
    program) when available, so cycles/steps come from the protocol rather than
    inferred from the data, with the inference as fallback.
16. **Scriptable public API** — `qcm.api.open_run(...)` returning the same
    frames the UI uses; documented; the notebook export then *imports the
    library* instead of embedding code. Power users extend instead of leaving.
17. **Community profile plugins** — see §5; new instruments without touching
    core. The moment two labs exchange a profile plugin, the tool has a
    community.

---

## 5. Architecture for flexibility (make extension trivial)

The current layering (profiles → ingest → run contract → `QCMRun` → pure
science → steps/UI) is right. The overhaul is about *formalizing the seams* so
each kind of extension has one obvious, documented, testable place.

### 5.1 Data sources as plugins (the highest-value seam)

Today `_PROFILE_REGISTRY` is a hardcoded list of `(name, kind, predicate)`.
Formalize it:

```python
class Profile(Protocol):
    name: str
    kind: Literal["qcm", "ps"]           # resonance source vs. echem overlay
    def detect(self, path: Path) -> float ...   # 0..1 confidence, cheap sniff
    def read(self, path: Path) -> ProfileResult ...  # canonical frame + metadata + warnings
```

- **Confidence scores, not booleans** — ambiguous files produce a ranked list
  the UI can show ("looks like PSTrace CP (0.9) — or standardized CSV (0.4)").
- **`ProfileResult` carries metadata + warnings** — scan-rate provenance,
  detected column mapping, dropped rows — so the UI's confirm step (§3) is fed
  by the contract, not by side channels.
- **Entry-point discovery**: `[project.entry-points."qcm.profiles"]` lets a new
  instrument ship as a separate pip package (`qcm-profile-gamry`); core never
  changes. Internal profiles register the same way — one mechanism.
- **Golden-file harness**: `tests/golden/<profile>/{input.*, expected.parquet,
  expected_manifest.json}`; one parametrized test auto-discovers all of them.
  Adding a format = drop two files in a folder. This is what makes "easy to add
  new data sources" *stay* true under refactoring.
- Document it: `docs/add-a-data-source.md` — target "new format in 30 minutes".

### 5.2 The run contract evolves by capability, not by version bump

`Manifest.schema_version` exists ("1.0") — add the missing halves:
- **Capabilities list** in the manifest (`["raw", "echem", "temperature"]`)
  replacing implicit marker columns (`has_raw` keys off `raw_i` today). UI
  surfaces key off capabilities; new data *types* (temperature, EIS, optical
  channel from a future combined instrument) become new optional column groups
  + a capability flag — no migration of old runs needed.
- **A migration ladder**: `qcm.migrations` with one function per version step,
  run lazily on open. Old run dirs must open forever; that's the contract that
  makes the file-backed design trustworthy.
- **Units in the contract**: column → unit map in the manifest (echemdb's core
  lesson: CSV without units is future pain). The quantity registry already
  knows display units; persist source units too.

### 5.3 Registries for quantities and techniques

- **Quantities**: the `theme.py` registry is close. Tighten to: a quantity is a
  dataclass with `key, label, unit, kind, requires (capabilities/columns),
  compute (Polars expr builder), referenced, normalized`. New derived signal =
  one registration; the Data-page menus, stats, exports, and notebook all pick
  it up. Keep the lockstep SQL path honest with a parametrized equivalence test
  (Polars vs. DuckDB on synthetic data) instead of a comment.
- **Techniques**: CV/CP are if/else branches in `results.py` today. Extract a
  `Technique` protocol — `detect(waveform) -> confidence`, `metadata()`,
  `derive_cycles()`, `headline_plots()` — so GITT, pulsed plating, or EIS-adjacent
  protocols slot in as new classes, and the Results page becomes a generic host.

### 5.4 Code-quality overhaul (the "super high quality" checklist)

1. **CI from day one** (GitHub Actions): pytest on Linux/macOS/Windows ×
   Python 3.11–3.13, ruff, and a coverage floor. The 149 tests are an asset
   only if something runs them. Add the screenshot harness as a manual-trigger
   job (Playwright + golden-image diff) for UI regressions.
2. **Static typing where it pays**: mypy (or pyright) strict on `qcm/` core
   (models, ingest, run, profiles, science, echem) — these are pure and will
   type cleanly. The viz layer can follow incrementally.
3. **Layering enforced, not promised**: import-linter contracts — `science`/
   `echem` may not import Panel; `qcm` core may not import `qcm.viz`. The
   README's "key invariants" become CI failures instead of prose.
4. **Split the god modules**: `controls.py` (1470 lines) → `state.py` (pure
   widget→state), `widgets.py` (construction), `layout.py` (toolbars/cards);
   `results.py` (900) shrinks when techniques are extracted (§5.3).
5. **Error policy** (§3.6): one `@guarded` decorator for UI surfaces that
   logs with context and renders the alert; grep-able structured logs
   (`logging` + run id + surface name). Ban bare `except Exception: pass` in
   science paths via ruff (`S110`/`BLE001`).
6. **Project hygiene**: LICENSE (pick MIT/BSD-3 for adoption), CITATION.cff,
   CHANGELOG (Keep-a-Changelog), real package name (not `qcm-refactor`), PyPI
   releases (`uv tool install qcm-viewer`), Windows launcher next to the macOS
   `.command`, versioned docs site (mkdocs-material) with task-based user
   guide and the developer guides above.
7. **ADRs**: `docs/adr/` is referenced by CLAUDE.md/CONTEXT.md but doesn't
   exist. Backfill the big decisions already made (file-backed run contract,
   pure-science layer, profile edge, multi-run semantics, design tokens) — they
   are the project's institutional memory and the onboarding path for any
   future contributor (human or agent).
8. **Performance budgets as tests**: open-run < 5 s for a 1 GB run, plot
   rebuild < 1 s on `demo --preset long` — assert in a perf smoke test so
   regressions are caught, not felt. Longer term, move from full plot rebuilds
   to Bokeh ColumnDataSource patching for the hot interactions (range moves).

### 5.5 Sequencing

| Phase | Theme | Contents |
|---|---|---|
| 0 (days) | Trust | CI, LICENSE, CITATION.cff, CHANGELOG, rename, error-logging policy, ADR backfill |
| 1 (weeks) | Finish the workflow | Composite figure + vector export, one-click alignment, auto-baseline, reference electrode, sensor presets, drift correction, temperature strip |
| 2 (weeks) | Extension seams | Profile protocol + entry points + golden harness, capabilities manifest, technique extraction, typing + import-linter |
| 3 (months) | Beat the field | Batch mode, Voigt modeling, uncertainty, artifact detection, cross-experiment dashboard |
| 4 (ongoing) | The dream | FAIR datapackages, live mode, public API, plugin ecosystem, JOSS paper |

Each phase is independently shippable; nothing in a later phase blocks daily lab
use during earlier ones.

---

## 6. References

- pyQCM-BraTaDio: [GitHub](https://github.com/b-pardi/BraTaDio) · [bioRxiv paper](https://www.biorxiv.org/content/10.1101/2023.12.15.571789v1)
- RheoQCM (Shull group): [GitHub](https://github.com/shullgroup/rheoQCM) · [group resources](https://shullgroup.northwestern.edu/resources/)
- PyQTM viscoelastic analysis: [AWSensors](https://awsensors.com/data-analysis-pyqtm/)
- openQCM Q-1 software: [openqcm.com](https://openqcm.com/introducing-the-new-openqcm-q-1-python-software.html)
- QSense Dfind (Smartfit, batch mode): [feature flyer](https://cdn2.hubspot.net/hubfs/516902/Pdf/QSense/Dfind-Flyer.pdf) · [Nanoscience overview](https://www.nanoscience.com/products/qsense-quartz-crystal-microbalance/software/dfind-data-analysis-software/)
- Vanoppen et al., *Exploring Metal Electroplating for Energy Storage by QCM: A Review*, Adv. Sensor Research 2024: [Wiley](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adsr.202400025)
- Shpigel, Aurbach et al., *Making Advanced Electrogravimetry an Affordable Analytical Tool for Battery Interface Characterization*, Anal. Chem.: [ACS](https://pubs.acs.org/doi/10.1021/acs.analchem.0c02233)
- Leppin et al., *A Modulation QCM Applied to Copper Electrodeposition and Stripping*, Electroanalysis 2021: [Wiley](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/10.1002/elan.202100471)
- FAIR electrochemistry data: [echemdb.org](https://www.echemdb.org/) · [echemdb toolkit (arXiv)](https://arxiv.org/pdf/2409.07083) · [yadg electrochemistry parsers](https://dgbowl.github.io/yadg/main/yadg.parsers.electrochem.html)
