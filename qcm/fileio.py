"""Atomic small-file writes.

The run contract keeps several JSON files next to the parquet data (manifest,
annotations, viewer state) and the app keeps session/preset JSON under
``~/.qcm_viewer``. All of them are rewritten in place; a crash or full disk
mid-write would otherwise leave truncated JSON that makes a run unopenable.
Writing to a sibling temp file and ``os.replace``-ing it in is atomic on every
platform we support.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: str | Path, text: str) -> Path:
    """Write ``text`` to ``path`` atomically (temp file + rename).

    The temp file lives in the destination directory so the rename never
    crosses a filesystem boundary. Parent directories are created.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
