# Execution Plan

This project intentionally avoids a ground-up custom UI.

## Architecture

1. Keep data in parquet.
2. Ingest completed raw runs into a run folder.
3. Build a multi-resolution parquet pyramid.
4. Query through DuckDB.
5. Expose a stable Python API.
6. Build the UI in Panel/HoloViews/Datashader.
7. Make groups/harmonics first-class.
8. Let scientists export data and notebooks.

## Implementation Order

1. Python package skeleton
2. Demo data generator
3. Ingestion pipeline
4. Manifest model
5. Pyramid builder
6. DuckDB-backed run API
7. Timeline query API
8. Sweep query API
9. Annotation persistence
10. Derived QCM metrics
11. Export data
12. Notebook generation
13. Panel viewer
14. CLI
15. Tests
16. Documentation

## Why this avoids hassle

No React, no TypeScript, no custom WebGL, no server database, no frontend build system for the MVP.

The result is a Python-native scientific app that can later be polished or replaced without losing the important data/API layers.
