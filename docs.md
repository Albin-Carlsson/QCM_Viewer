# Developer Notes

## Scientific primitives

Treat these as first-class:

- run
- sequence
- group
- frequency
- sweep
- selected time range
- selected frequency band
- annotation
- reference region

Never silently average groups together.

## Performance rules

- Use pyramid data for zoomed-out timelines.
- Use raw parquet only for narrow ranges or sweep inspection.
- Use Datashader for dense scatter/heatmap views.
- Never convert huge full runs to pandas.

## MVP limitations

This is a strong starting implementation, not the final polished commercial product.

Known future improvements:

- better linked crosshair behavior
- explicit frequency-band selection widget
- richer residual heatmap
- more advanced multi-run comparison
- real figure SVG export from current Panel state
- optional desktop packaging
