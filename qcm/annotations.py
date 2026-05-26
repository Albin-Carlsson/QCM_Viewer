from __future__ import annotations

import json
import uuid
from pathlib import Path
from .models import Annotation
from .timeutil import now_iso


def _path(run_path: str | Path) -> Path:
    return Path(run_path) / "annotations.json"


def load_annotations(run_path: str | Path) -> list[Annotation]:
    p = _path(run_path)
    if not p.exists():
        p.write_text("[]")
    raw = json.loads(p.read_text())
    return [Annotation.model_validate(x) for x in raw]


def save_annotations(run_path: str | Path, anns: list[Annotation]) -> None:
    _path(run_path).write_text(json.dumps([a.model_dump() for a in anns], indent=2))


def create_annotation(
    run_path: str | Path,
    type: str,
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
