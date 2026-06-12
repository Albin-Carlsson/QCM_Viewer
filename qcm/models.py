from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field

from .fileio import write_text_atomic


class TimeInfo(BaseModel):
    start: int
    end: int
    unit: Literal["microseconds"] = "microseconds"


class PathsInfo(BaseModel):
    raw: str = "raw"
    pyramid: str = "pyramid"
    sweeps: str = "sweeps/index.parquet"
    annotations: str = "annotations.json"
    expressions: str = "expressions.json"
    # Raw potentiostat stream (CP EQCM): the cell channels on their own time base,
    # retained so the PS↔QCM alignment offset can be re-applied without re-import.
    echem: str = "echem.parquet"


class Manifest(BaseModel):
    schema_version: str = "1.1"
    run_id: str
    created_at: str
    source_path: str | None = None
    time: TimeInfo
    columns: list[str]
    groups: list[int] = Field(default_factory=list)
    pyramid_levels: list[str] = Field(default_factory=lambda: ["100ms", "1s", "10s", "1min", "10min", "1h"])
    paths: PathsInfo = Field(default_factory=PathsInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # What the run carries ("raw", "echem", "temperature"). UI surfaces and the
    # CLI key off these explicit flags rather than sniffing marker columns; new
    # optional column groups become a new flag here, not a schema break.
    capabilities: list[str] = Field(default_factory=list)
    # column → source unit for known columns (including sidecar stream roles),
    # so exported data stays self-describing.
    units: dict[str, str] = Field(default_factory=dict)
    # PS↔QCM alignment: seconds the potentiostat stream is shifted before being
    # interpolated onto the QCM clock. Editable in-app (no re-import); 0 = as
    # imported. Only meaningful for runs with a retained echem stream.
    ps_offset_s: float = 0.0

    @classmethod
    def load(cls, run_path: str | Path) -> "Manifest":
        path = Path(run_path) / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing manifest: {path}")
        return cls.model_validate_json(path.read_text())

    def save(self, run_path: str | Path) -> None:
        # Atomic: a crash mid-write must never leave a truncated manifest —
        # that would make the whole run unopenable.
        write_text_atomic(Path(run_path) / "manifest.json", self.model_dump_json(indent=2))


AnnotationType = Literal["point", "range", "reference_region", "excluded_region", "event"]


class Annotation(BaseModel):
    id: str
    type: AnnotationType
    t0: int
    t1: int | None = None
    label: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    groups: list[int] | None = None
    frequency_range: tuple[float, float] | None = None
    color: str = "auto"
    created_at: str
    updated_at: str


class TimelineResult(BaseModel):
    level: str
    t0: int
    t1: int
    columns: list[str]
    row_count: int
    elapsed_ms: float
