"""Compatibility shim — the pure electrochemistry analysis lives in
:mod:`qcm.science.echem`.

Kept so existing imports (``from qcm.viz import echem``, exported notebooks,
user scripts) continue to work; new code should import ``qcm.science.echem``
directly.
"""
from qcm.science.echem import *  # noqa: F401,F403
