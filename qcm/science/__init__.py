"""The pure science layer: UI-free Polars/NumPy math for QCM-D and EQCM.

Three modules, no rendering imports anywhere (enforced by import-linter):

- :mod:`qcm.science.quantities` — science constants, ``ExperimentParams``, and
  the quantity/axis registries.
- :mod:`qcm.science.transforms` — referencing, normalization, Sauerbrey mass,
  MPE, despike/detrend/smoothing, baseline suggestion, alignment, Faraday
  prediction (formerly ``qcm.viz.science``).
- :mod:`qcm.science.echem` — technique detection, cycle derivation, CE, and
  per-cycle statistics (formerly ``qcm.viz.echem``).

``qcm.viz.science`` / ``qcm.viz.echem`` remain as import shims so existing
code and notebooks keep working.
"""
from __future__ import annotations
