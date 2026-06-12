from __future__ import annotations

import json
import uuid
from pathlib import Path
from .fileio import write_text_atomic
from .models import Annotation, AnnotationType
from .timeutil import now_iso


def _path(run_path: str | Path) -> Path:
    return Path(run_path) / "annotations.json"


def load_annotations(run_path: str | Path) -> list[Annotation]:
    """All annotations of a run; a missing file is simply an empty list.

    Read-only: never writes. Runs are routinely opened from read-only
    locations (network shares, archived data), and a read must not fail there.
    """
    p = _path(run_path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    return [Annotation.model_validate(x) for x in raw]


def save_annotations(run_path: str | Path, anns: list[Annotation]) -> None:
    write_text_atomic(_path(run_path), json.dumps([a.model_dump() for a in anns], indent=2))


def create_annotation(
    run_path: str | Path,
    type: "AnnotationType",
    t0: int,
    label: str,
    t1: int | None = None,
    description: str = "",
    tags: list[str] | None = None,
    groups: list[int] | None = None,
    frequency_range: tuple[float, float] | None = None,
) -> Annotation:
    anns = load_annotations(run_path)
    ts = now_iso()
    ann = Annotation(
        id="ann_" + uuid.uuid4().hex[:10],
        type=type,
        t0=int(t0),
        t1=int(t1) if t1 is not None else None,
        label=label,
        description=description,
        tags=tags or [],
        groups=groups,
        frequency_range=frequency_range,
        created_at=ts,
        updated_at=ts,
    )
    anns.append(ann)
    save_annotations(run_path, anns)
    return ann
