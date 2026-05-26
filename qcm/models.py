from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field


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


class Manifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    created_at: str
    source_path: str | None = None
    time: TimeInfo
    columns: list[str]
    groups: list[int] = Field(default_factory=list)
    pyramid_levels: list[str] = Field(default_factory=lambda: ["100ms", "1s", "10s", "1min", "10min", "1h"])
    paths: PathsInfo = Field(default_factory=PathsInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, run_path: str | Path) -> "Manifest":
        path = Path(run_path) / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing manifest: {path}")
        return cls.model_validate_json(path.read_text())

    def save(self, run_path: str | Path) -> None:
        Path(run_path).mkdir(parents=True, exist_ok=True)
        (Path(run_path) / "manifest.json").write_text(self.model_dump_json(indent=2))


class Annotation(BaseModel):
    id: str
    type: Literal["point", "range", "reference_region", "excluded_region", "event"]
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
