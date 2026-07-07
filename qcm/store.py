"""Persistent store for imported runs.

`qcm view file.csv` and the landing page used to import into a
``tempfile.mkdtemp`` directory, so everything a researcher then did —
annotations, the PS↔QCM alignment offset, experiment parameters, saved view
state, all written *into that run directory* — vanished on the next reboot when
the OS cleared ``/tmp``. This module gives every source file a **stable** run
directory under ``~/.qcm_viewer/runs/`` so that work survives, and reuses it on
reopen (preserving the analysis) unless the source file has changed.

Override the location with ``QCM_RUNS_DIR`` (tests point it at a tmp dir so they
never touch the user's real store).
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .profiles import import_run

_DEFAULT_RUNS_DIR = Path.home() / ".qcm_viewer" / "runs"


def runs_dir() -> Path:
    override = os.environ.get("QCM_RUNS_DIR")
    return Path(override) if override else _DEFAULT_RUNS_DIR


def _slug(text: str) -> str:
    keep = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in text)
    return keep.strip("-")[:48] or "run"


def persistent_run_dir(source: str | Path) -> Path:
    """Stable run directory for a source file/folder.

    The same source path always maps to the same directory (so reopening reuses
    the prior analysis); different paths that share a stem are disambiguated by a
    short hash of the absolute path, so ``a/mp.csv`` and ``b/mp.csv`` never
    collide.
    """
    source = Path(source)
    digest = hashlib.sha1(str(source.resolve()).encode()).hexdigest()[:8]
    return runs_dir() / f"{_slug(source.stem)}-{digest}"


def _is_fresh(run_dir: Path, *sources: Path | None) -> bool:
    """True when ``run_dir`` holds a run newer than all of its sources."""
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        return False
    run_mtime = manifest.stat().st_mtime
    for s in sources:
        if s is not None and Path(s).exists() and Path(s).stat().st_mtime > run_mtime:
            return False
    return True


def import_or_reuse(
    source: str | Path,
    *,
    ps_source: str | Path | None = None,
    profile: str | None = None,
    qcm_rename: dict[str, str] | None = None,
    cv_scan_rate: float | None = None,
    dest: Path | None = None,
) -> tuple[Path, bool]:
    """Return ``(run_dir, reused)`` for a source, importing into the persistent
    store when needed.

    Reuses an existing run when it is newer than the source (and its paired PS
    file), so a researcher's saved annotations/parameters survive a reopen.
    Re-imports (overwriting) when the source changed. An explicit profile,
    column rename, or CV scan rate forces a fresh import because each changes the
    derived data and can't be matched against a cached run.
    """
    dest = dest or persistent_run_dir(source)
    reusable = cv_scan_rate is None and profile is None and not qcm_rename
    ps_path = Path(ps_source) if ps_source is not None else None
    if reusable and _is_fresh(dest, Path(source), ps_path):
        return dest, True
    import_run(
        source, dest, profile=profile, qcm_rename=qcm_rename,
        ps_source=ps_source, cv_scan_rate=cv_scan_rate, overwrite=True,
    )
    return dest, False
