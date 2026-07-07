"""Named experiment-parameter presets, persisted across runs and sessions.

A preset bundles the per-cell/per-species experiment parameters — electrode
area, Sauerbrey sensitivity, molar mass M, valency z, reference electrode — so a
lab configures its sensor once ("Cu 5 MHz disc, Ag|AgCl, Zn²⁺") and reuses it on
every import instead of retyping. Presets are *global* (a reusable template),
distinct from a run's own saved view state.

Stored as JSON at ``~/.qcm_viewer/presets.json`` — the same ``~/.qcm_viewer``
home as the remembered session — overridable with ``QCM_PRESETS_FILE`` (tests
point it at a tmp file so they never touch the user's real presets). This module
is Panel-free; it deals only in :class:`~qcm.viz.theme.ExperimentParams`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..log import get_logger
from .theme import ExperimentParams

_log = get_logger("presets")

_DEFAULT_PRESETS_FILE = Path.home() / ".qcm_viewer" / "presets.json"


def presets_file() -> Path:
    override = os.environ.get("QCM_PRESETS_FILE")
    return Path(override) if override else _DEFAULT_PRESETS_FILE


def load_presets() -> dict[str, ExperimentParams]:
    """All saved presets as ``{name: ExperimentParams}`` (empty if none/unreadable)."""
    path = presets_file()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("Could not read presets at %s: %s", path, exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, ExperimentParams] = {}
    for name, data in raw.items():
        if isinstance(name, str) and name.strip() and isinstance(data, dict):
            out[name] = ExperimentParams.from_dict(data)
    return out


def save_preset(name: str, params: ExperimentParams) -> dict[str, ExperimentParams]:
    """Add/replace a preset and persist; returns the updated preset map."""
    name = (name or "").strip()
    if not name:
        raise ValueError("preset name required")
    presets = load_presets()
    presets[name] = params
    _write(presets)
    return presets


def delete_preset(name: str) -> dict[str, ExperimentParams]:
    """Remove a preset (no-op if absent) and persist; returns the updated map."""
    presets = load_presets()
    if name in presets:
        del presets[name]
        _write(presets)
    return presets


def _write(presets: dict[str, ExperimentParams]) -> None:
    from qcm.fileio import write_text_atomic

    payload = {name: p.to_dict() for name, p in presets.items()}
    write_text_atomic(presets_file(), json.dumps(payload, indent=2))
