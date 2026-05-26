# GUI Upgrade Pack

Implemented high-impact Panel-native improvements without introducing a custom React/WebGL frontend.

## Added

- FastGridTemplate layout with resizable grid-style panels where supported by Panel.
- Persistent workspace state saved to `viewer_state.json`.
- Group/harmonic manager through multi-select controls.
- Multi-group sweep curve viewer at a chosen sequence.
- Single-group or all-groups sweep inspection mode.
- I/Q scatter for all selected groups.
- Frequency-band selector for waterfall/sub-band inspection.
- Group-aware waterfall queries through `run.frequency_band(...)`.
- Selected-region statistics table by group.
- Annotation overlays on timelines.
- Group-aware annotations with frequency-range metadata.
- Export of selected data.
- Export of current timeline as HTML plus JSON metadata containing title, unit, groups, and time range.
- Improved notebook export with selected groups and statistics.
- SQL quoting fixes for DuckDB `"group"` keyword issues.

## Important design choice

PNG/SVG static image export is not guaranteed in every local environment because Bokeh static export needs browser-driver dependencies such as Selenium/geckodriver/chromedriver. The robust out-of-the-box export is HTML + metadata. Add PNG/SVG later once the app controls the export environment.

## Run

```bash
pip install -e .
qcm diagnose demo_run
qcm serve demo_run
```

