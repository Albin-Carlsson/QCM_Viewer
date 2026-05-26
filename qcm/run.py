from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Any

import duckdb
import polars as pl

from .models import Manifest, TimelineResult, Annotation
from .timeutil import parse_time, choose_level
from .annotations import load_annotations, create_annotation, save_annotations
from . import derived as derived_mod

SWEEP_TIMELINE_COLUMNS = {"fit_center", "fit_gamma", "fit_fwhm"}


class QCMRun:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.manifest = Manifest.load(self.path)
        self.id = self.manifest.run_id
        self.conn = duckdb.connect(database=":memory:")

    @property
    def time_start(self) -> int:
        return self.manifest.time.start

    @property
    def time_end(self) -> int:
        return self.manifest.time.end

    @property
    def columns(self) -> list[str]:
        return self.manifest.columns

    @property
    def groups(self) -> list[int]:
        return self.manifest.groups

    def overtone_orders(self) -> dict[int, int]:
        """Infer the overtone order n for each group from resonance frequencies.

        QCM overtones sit at odd multiples of the fundamental (n = 1, 3, 5, ...).
        We derive n per group by rounding ``fit_center(group) / fit_center(base)``
        where ``base`` is the lowest-frequency group. Channels that are not true
        overtones collapse to n = 1, which makes Δf/n normalization a safe no-op.
        """
        try:
            idx = self.sweep_index()
        except Exception:
            return {g: 1 for g in self.groups}
        if idx.is_empty():
            return {g: 1 for g in self.groups}
        centers = (
            idx.group_by("group")
            .agg(pl.col("fit_center").first().alias("fc"))
            .sort("group")
        )
        rows = {int(r["group"]): float(r["fc"]) for r in centers.iter_rows(named=True)}
        if not rows:
            return {g: 1 for g in self.groups}
        base = min(rows.values())
        return {g: max(1, round(fc / base)) for g, fc in rows.items()}

    def _parquet_glob(self, level: str) -> str:
        if level == "raw":
            return str(self.path / self.manifest.paths.raw / "*.parquet")
        return str(self.path / self.manifest.paths.pyramid / level / "*.parquet")

    def _read_parquet(
        self,
        level: str,
        columns: list[str],
        t0: int,
        t1: int,
        groups: list[int] | None,
        order_by: str = 'timestamp, "group"',
    ) -> pl.DataFrame:
        path = self._parquet_glob(level)
        wanted = ["timestamp"] + (["group"] if "group" not in columns else []) + columns
        wanted = list(dict.fromkeys(wanted))
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        sql = f"SELECT {col_sql} FROM read_parquet('{path}') WHERE timestamp >= ? AND timestamp <= ?"
        params: list[object] = [int(t0), int(t1)]
        if groups:
            placeholders = ",".join("?" for _ in groups)
            sql += f" AND \"group\" IN ({placeholders})"
            params.extend([int(g) for g in groups])
        if order_by:
            sql += f" ORDER BY {order_by}"
        return self.conn.execute(sql, params).pl()

    def _read_sweep_timeline(self, columns: list[str], t0: int, t1: int, groups: list[int] | None) -> pl.DataFrame:
        path = self.path / self.manifest.paths.sweeps
        wanted = ["timestamp"] + (["group"] if "group" not in columns else []) + columns
        wanted = list(dict.fromkeys(wanted))
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        sql = f"SELECT {col_sql} FROM read_parquet('{path}') WHERE timestamp >= ? AND timestamp <= ?"
        params: list[object] = [int(t0), int(t1)]
        if groups:
            placeholders = ",".join("?" for _ in groups)
            sql += f" AND \"group\" IN ({placeholders})"
            params.extend([int(g) for g in groups])
        sql += ' ORDER BY timestamp, "group"'
        return self.conn.execute(sql, params).pl()

    def timeline(
        self,
        columns: Iterable[str],
        t0: int | str | None = None,
        t1: int | str | None = None,
        target_points: int = 2000,
        groups: list[int] | None = None,
        level: str | None = None,
        include_meta: bool = False,
    ):
        cols = list(columns)
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        chosen = level or choose_level(end - start, target_points, self.manifest.pyramid_levels)
        tic = time.perf_counter()

        # Fit timeline columns are constant within a sweep. At raw resolution, the
        # scientifically correct source is the sweep index, not the raw frequency-point table.
        if chosen == "raw" and set(cols).issubset(SWEEP_TIMELINE_COLUMNS):
            df = self._read_sweep_timeline(cols, start, end, groups)
            reported_level = "sweeps"
        else:
            df = self._read_parquet(chosen, cols, start, end, groups)
            reported_level = chosen

        elapsed = (time.perf_counter() - tic) * 1000
        meta = TimelineResult(level=reported_level, t0=start, t1=end, columns=cols, row_count=df.height, elapsed_ms=elapsed)
        return (df, meta) if include_meta else df

    def sweep(self, sequence: int | None = None, timestamp: int | str | None = None, group: int | None = None) -> pl.DataFrame:
        raw_path = self._parquet_glob("raw")
        if sequence is None:
            if timestamp is None:
                raise ValueError("Provide sequence or timestamp")
            t = parse_time(timestamp)
            sql = f"SELECT sequence FROM read_parquet('{raw_path}') WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
            row = self.conn.execute(sql, [t]).fetchone()
            if row is None:
                raise ValueError("No sweep found near timestamp")
            sequence = int(row[0])
        sql = f"SELECT * FROM read_parquet('{raw_path}') WHERE sequence = ?"
        params: list[object] = [int(sequence)]
        if group is not None:
            sql += " AND \"group\" = ?"
            params.append(int(group))
        sql += ' ORDER BY "group", frequency'
        return self.conn.execute(sql, params).pl()

    def sweeps_at(self, sequence: int | None = None, timestamp: int | str | None = None, groups: list[int] | None = None) -> pl.DataFrame:
        """Return all selected group curves for one sequence/timestamp."""
        raw_path = self._parquet_glob("raw")
        if sequence is None:
            if timestamp is None:
                raise ValueError("Provide sequence or timestamp")
            t = parse_time(timestamp)
            sql = f"SELECT sequence FROM read_parquet('{raw_path}') WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
            row = self.conn.execute(sql, [t]).fetchone()
            if row is None:
                raise ValueError("No sweep found near timestamp")
            sequence = int(row[0])
        sql = f"SELECT * FROM read_parquet('{raw_path}') WHERE sequence = ?"
        params: list[object] = [int(sequence)]
        if groups:
            sql += " AND \"group\" IN (" + ",".join("?" for _ in groups) + ")"
            params.extend([int(g) for g in groups])
        sql += ' ORDER BY "group", frequency'
        return self.conn.execute(sql, params).pl()

    def sweep_index(self, t0: int | str | None = None, t1: int | str | None = None, groups: list[int] | None = None) -> pl.DataFrame:
        path = self.path / self.manifest.paths.sweeps
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        sql = f"SELECT * FROM read_parquet('{path}') WHERE timestamp >= ? AND timestamp <= ?"
        params: list[object] = [start, end]
        if groups:
            sql += " AND \"group\" IN (" + ",".join("?" for _ in groups) + ")"
            params.extend([int(g) for g in groups])
        sql += ' ORDER BY timestamp, "group"'
        return self.conn.execute(sql, params).pl()

    def region_stats(
        self,
        columns: list[str],
        t0: int | str | None = None,
        t1: int | str | None = None,
        groups: list[int] | None = None,
    ) -> pl.DataFrame:
        df = self.timeline(columns, t0=t0, t1=t1, groups=groups, level="raw")
        if df.is_empty():
            return pl.DataFrame()
        aggs: list[Any] = []
        for c in columns:
            aggs.extend([
                pl.col(c).mean().alias(f"{c}_mean"),
                pl.col(c).std().alias(f"{c}_std"),
                pl.col(c).min().alias(f"{c}_min"),
                pl.col(c).max().alias(f"{c}_max"),
                (pl.col(c).last() - pl.col(c).first()).alias(f"{c}_delta"),
            ])
        return df.group_by("group").agg(aggs).sort("group")

    def frequency_band(
        self,
        f0: float,
        f1: float,
        t0: int | str | None = None,
        t1: int | str | None = None,
        groups: list[int] | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        raw_path = self._parquet_glob("raw")
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        columns = columns or ["timestamp", "sequence", "group", "frequency", "conductance", "susceptance", "raw_i", "raw_q"]
        wanted = list(dict.fromkeys(columns))
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        sql = f"SELECT {col_sql} FROM read_parquet('{raw_path}') WHERE timestamp >= ? AND timestamp <= ? AND frequency >= ? AND frequency <= ?"
        params: list[object] = [start, end, float(f0), float(f1)]
        if groups:
            sql += " AND \"group\" IN (" + ",".join("?" for _ in groups) + ")"
            params.extend([int(g) for g in groups])
        sql += ' ORDER BY timestamp, "group", frequency'
        return self.conn.execute(sql, params).pl()

    def annotations(self, t0: int | str | None = None, t1: int | str | None = None, tags: list[str] | None = None) -> list[Annotation]:
        anns = load_annotations(self.path)
        if t0 is not None or t1 is not None:
            start = parse_time(t0, self.time_start)
            end = parse_time(t1, self.time_end)
            anns = [a for a in anns if a.t0 <= end and (a.t1 or a.t0) >= start]
        if tags:
            tagset = set(tags)
            anns = [a for a in anns if tagset.intersection(a.tags)]
        return anns

    def add_annotation(self, **kwargs) -> Annotation:
        return create_annotation(self.path, **kwargs)

    def remove_annotation(self, annotation_id: str) -> None:
        anns = [a for a in load_annotations(self.path) if a.id != annotation_id]
        save_annotations(self.path, anns)

    def derived(self, name: str, t0=None, t1=None, groups: list[int] | None = None, harmonic: int | None = None) -> pl.DataFrame:
        base = self.timeline(["fit_center", "fit_fwhm", "fit_gamma"], t0=t0, t1=t1, groups=groups, level="raw")
        if name == "sauerbrey_mass":
            return derived_mod.sauerbrey_mass(base, harmonic=harmonic)
        if name == "quality_factor":
            return derived_mod.quality_factor(base)
        if name == "dissipation":
            return derived_mod.dissipation(base)
        if name == "delta_f":
            return derived_mod.delta_f(base)
        raise ValueError(f"Unknown derived quantity: {name}")

    def export_data(self, output: str | Path, columns: list[str], t0=None, t1=None, groups: list[int] | None = None, fmt: str = "parquet") -> Path:
        df = self.timeline(columns, t0=t0, t1=t1, groups=groups, level="raw")
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv" or out.suffix == ".csv":
            df.write_csv(out)
        else:
            df.write_parquet(out)
        return out

    def save_view_state(self, state: dict[str, Any]) -> Path:
        out = self.path / "viewer_state.json"
        out.write_text(json.dumps(state, indent=2))
        return out

    def load_view_state(self) -> dict[str, Any]:
        path = self.path / "viewer_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def to_notebook(self, output: str | Path, columns: list[str] | None = None, t0=None, t1=None, groups: list[int] | None = None) -> Path:
        import nbformat as nbf
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        columns = columns or ["fit_center", "fit_fwhm"]
        t0p = parse_time(t0, self.time_start)
        t1p = parse_time(t1, self.time_end)
        nb = nbf.v4.new_notebook()
        code = f'''import qcm
run = qcm.open_run(r"{self.path}")

# Same time range and groups as the exported viewer state
data = run.timeline({columns!r}, t0={t0p!r}, t1={t1p!r}, groups={groups!r})
stats = run.region_stats({columns!r}, t0={t0p!r}, t1={t1p!r}, groups={groups!r})
annotations = run.annotations(t0={t0p!r}, t1={t1p!r})

data.head(), stats
'''
        nb.cells = [
            nbf.v4.new_markdown_cell(f"# QCM analysis: {self.id}"),
            nbf.v4.new_markdown_cell("Generated from QCM Viewer. The code below reproduces the selected view."),
            nbf.v4.new_code_cell(code),
        ]
        nbf.write(nb, out)
        return out


def open_run(path: str | Path) -> QCMRun:
    return QCMRun(path)
