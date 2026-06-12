"""Compatibility shim — the pure science transforms live in :mod:`qcm.science`.

Kept so existing imports (``from qcm.viz import science``, exported notebooks,
user scripts) continue to work; new code should import
``qcm.science.transforms`` directly.
"""
from qcm.science.transforms import *  # noqa: F401,F403
