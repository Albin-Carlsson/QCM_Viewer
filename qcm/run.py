from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Any

import duckdb
import polars as pl

from .log import get_logger
from .models import Manifest, TimelineResult, Annotation
from .sqlutil import sql_path
from .timeutil import parse_time, choose_level
from .annotations import load_annotations, create_annotation, save_annotations

SWEEP_TIMELINE_COLUMNS = {"fit_center", "fit_gamma", "fit_fwhm"}

_log = get_logger("run")


class QCMRun:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.manifest = Manifest.load(self.path)
        self.id = self.manifest.run_id
        self.conn = duckdb.connect(database=":memory:")
        # Read-side tuning: parallel parquet scans and no insertion-order bookkeeping.
        # Our queries carry explicit ORDER BY where order matters, so dropping
        # insertion-order tracking is safe and cuts per-query overhead.
        self.conn.execute("PRAGMA threads=4")
        self.conn.execute("SET preserve_insertion_order=false")
        # The sweep index is static for a run; cache the unfiltered read so the
        # app's repeated calls (init, tap-to-jump, readouts) hit memory.
        self._sweep_index_full: pl.DataFrame | None = None
        self._echem_stream: pl.DataFrame | None = None

    def close(self) -> None:
        """Release the DuckDB connection and cached frames.

        Safe to call more than once. Runs opened for a quick read (CLI exports,
        temp-dir imports) and runs removed from a live run set should be closed
        so connections don't accumulate until garbage collection.
        """
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001 — double-close/teardown must never raise
            pass
        self._sweep_index_full = None
        self._echem_stream = None

    def __enter__(self) -> "QCMRun":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def time_start(self) -> int:
        return self.manifest.time.start

    @property
    def time_end(self) -> int:
        return self.manifest.time.end

    @property
    def columns(self) -> list[str]:
        """Columns the run can serve, including echem channels held in the
        sidecar stream (derived on read). Listing the stream's roles here means
        capability checks (has_echem, available axes/quantities) and the echem
        read path all see the cell channels without special-casing."""
        cols = list(self.manifest.columns)
        for role in self.echem_stream_roles:
            if role not in cols:
                cols.append(role)
        return cols

    # --- echem stream (retained raw potentiostat channels) ----------------
    @property
    def _echem_path(self) -> Path:
        return self.path / self.manifest.paths.echem

    @property
    def has_echem_stream(self) -> bool:
        return self._echem_path.exists()

    def echem_stream(self) -> pl.DataFrame:
        """The retained raw cell stream ``[time_s, <roles>]`` (empty if none).

        ``time_s`` is elapsed seconds zeroed at the stream's first sample; the
        data layer interpolates the roles onto the QCM clock at
        ``time_s + ps_offset_s``."""
        if not self.has_echem_stream:
            return pl.DataFrame()
        if self._echem_stream is None:
            self._echem_stream = pl.read_parquet(self._echem_path)
        return self._echem_stream

    @property
    def echem_stream_roles(self) -> tuple[str, ...]:
        if not self.has_echem_stream:
            return ()
        return tuple(c for c in self.echem_stream().columns if c != "time_s")

    @property
    def ps_offset_s(self) -> float:
        return float(getattr(self.manifest, "ps_offset_s", 0.0) or 0.0)

    def set_ps_offset(self, seconds: float) -> None:
        """Persist the PS↔QCM alignment offset to the manifest (re-applied on read)."""
        self.manifest.ps_offset_s = float(seconds)
        self.manifest.save(self.path)

    @property
    def groups(self) -> list[int]:
        return self.manifest.groups

    @property
    def capabilities(self) -> list[str]:
        """Explicit capability flags ("raw", "echem", "temperature")."""
        return list(self.manifest.capabilities)

    @property
    def has_raw(self) -> bool:
        """Whether the run carries raw frequency-point sweep data.

        Fit-only runs (e.g. imported Qsoft Fr/D exports) have no raw sweeps, so
        the sweep inspector and waterfall are unavailable.
        """
        return "raw" in self.manifest.capabilities

    def overtone_orders(self) -> dict[int, int]:
        """Infer the overtone order n for each group from resonance frequencies.

        QCM overtones sit at odd multiples of the fundamental (n = 1, 3, 5, ...).
        We derive n per group by rounding ``fit_center(group) / fit_center(base)``
        where ``base`` is the lowest-frequency group. Channels that are not true
        overtones collapse to n = 1, which makes Δf/n normalization a safe no-op.
        """
        try:
            idx = self.sweep_index()
        except Exception:  # noqa: BLE001 — a missing/corrupt index degrades to n=1
            _log.exception("overtone_orders: sweep index unreadable for %s", self.path)
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

    @staticmethod
    def _read_from(path: str | Path) -> str:
        """``read_parquet('…')`` with the path escaped as a SQL literal.

        DuckDB cannot bind the path as a parameter, so every embedded path must
        go through :func:`qcm.sqlutil.sql_path` — folder names with quotes
        (``viktor's data``) are routine and would otherwise break every query.
        """
        return f"read_parquet('{sql_path(path)}')"

    @staticmethod
    def _where_time_groups(t0: int, t1: int, groups: list[int] | None) -> tuple[str, list[object]]:
        """Shared ``WHERE timestamp BETWEEN … [AND group IN …]`` clause + params."""
        sql = " WHERE timestamp >= ? AND timestamp <= ?"
        params: list[object] = [int(t0), int(t1)]
        if groups:
            sql += ' AND "group" IN (' + ",".join("?" for _ in groups) + ")"
            params.extend(int(g) for g in groups)
        return sql, params

    def _read_timeline_from(
        self,
        path: str | Path,
        columns: list[str],
        t0: int,
        t1: int,
        groups: list[int] | None,
    ) -> pl.DataFrame:
        """Timeline read shared by the pyramid/raw and sweep-index paths."""
        wanted = ["timestamp"] + (["group"] if "group" not in columns else []) + columns
        wanted = list(dict.fromkeys(wanted))
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        where, params = self._where_time_groups(t0, t1, groups)
        sql = f"SELECT {col_sql} FROM {self._read_from(path)}{where} ORDER BY timestamp, \"group\""
        return self.conn.execute(sql, params).pl()

    def _read_parquet(
        self,
        level: str,
        columns: list[str],
        t0: int,
        t1: int,
        groups: list[int] | None,
    ) -> pl.DataFrame:
        return self._read_timeline_from(self._parquet_glob(level), columns, t0, t1, groups)

    def _read_sweep_timeline(self, columns: list[str], t0: int, t1: int, groups: list[int] | None) -> pl.DataFrame:
        return self._read_timeline_from(self.path / self.manifest.paths.sweeps, columns, t0, t1, groups)

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

    def _resolve_sequence(self, sequence: int | None, timestamp: int | str | None) -> int:
        """The given sequence, or the last sequence at/before ``timestamp``."""
        if sequence is not None:
            return int(sequence)
        if timestamp is None:
            raise ValueError("Provide sequence or timestamp")
        t = parse_time(timestamp)
        sql = (
            f"SELECT sequence FROM {self._read_from(self._parquet_glob('raw'))} "
            "WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1"
        )
        row = self.conn.execute(sql, [t]).fetchone()
        if row is None:
            raise ValueError("No sweep found near timestamp")
        return int(row[0])

    def sweep(self, sequence: int | None = None, timestamp: int | str | None = None, group: int | None = None) -> pl.DataFrame:
        return self.sweeps_at(sequence, timestamp, [int(group)] if group is not None else None)

    def sweeps_at(self, sequence: int | None = None, timestamp: int | str | None = None, groups: list[int] | None = None) -> pl.DataFrame:
        """Return all selected group curves for one sequence/timestamp."""
        sequence = self._resolve_sequence(sequence, timestamp)
        sql = f"SELECT * FROM {self._read_from(self._parquet_glob('raw'))} WHERE sequence = ?"
        params: list[object] = [int(sequence)]
        if groups:
            sql += " AND \"group\" IN (" + ",".join("?" for _ in groups) + ")"
            params.extend([int(g) for g in groups])
        sql += ' ORDER BY "group", frequency'
        return self.conn.execute(sql, params).pl()

    def sweep_index(self, t0: int | str | None = None, t1: int | str | None = None, groups: list[int] | None = None) -> pl.DataFrame:
        is_full = t0 is None and t1 is None and not groups
        if is_full and self._sweep_index_full is not None:
            return self._sweep_index_full
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        where, params = self._where_time_groups(start, end, groups)
        sql = (
            f"SELECT * FROM {self._read_from(self.path / self.manifest.paths.sweeps)}{where}"
            ' ORDER BY timestamp, "group"'
        )
        df = self.conn.execute(sql, params).pl()
        if is_full:
            self._sweep_index_full = df
        return df

    def baseline_mean(
        self,
        value_expr: str,
        t0: int | str | None = None,
        t1: int | str | None = None,
        groups: list[int] | None = None,
    ) -> pl.DataFrame:
        """Per-group mean of a raw value expression over a time window, in SQL.

        ``value_expr`` is a DuckDB scalar expression over the raw fit columns
        (e.g. ``fit_center`` or ``fit_fwhm / fit_center * 1e6``). It is
        interpolated into the SQL, so it must come from trusted code — pass only
        the internal expressions built by :func:`qcm.science.transforms.raw_value_sql`,
        never user input. DuckDB prunes row groups by the ``timestamp`` predicate
        and only the per-group average crosses into Python, so a referenced
        quantity no longer materializes the whole baseline window. Returns
        ``[group, baseline]`` — the exact mean, identical to averaging the
        per-row values in Polars.
        """
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        where, params = self._where_time_groups(start, end, groups)
        sql = (
            f'SELECT "group", avg({value_expr})::DOUBLE AS baseline '
            f"FROM {self._read_from(self._parquet_glob('raw'))}{where}"
            ' GROUP BY "group" ORDER BY "group"'
        )
        return self.conn.execute(sql, params).pl()

    def frequency_band(
        self,
        f0: float,
        f1: float,
        t0: int | str | None = None,
        t1: int | str | None = None,
        groups: list[int] | None = None,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        start = parse_time(t0, self.time_start)
        end = parse_time(t1, self.time_end)
        columns = columns or ["timestamp", "sequence", "group", "frequency", "conductance", "susceptance", "raw_i", "raw_q"]
        wanted = list(dict.fromkeys(columns))
        col_sql = ", ".join(f'"{c}"' for c in wanted)
        where, params = self._where_time_groups(start, end, groups)
        sql = (
            f"SELECT {col_sql} FROM {self._read_from(self._parquet_glob('raw'))}{where}"
            " AND frequency >= ? AND frequency <= ?"
            ' ORDER BY timestamp, "group", frequency'
        )
        params.extend([float(f0), float(f1)])
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
        from .fileio import write_text_atomic

        return write_text_atomic(self.path / "viewer_state.json", json.dumps(state, indent=2))

    def load_view_state(self) -> dict[str, Any]:
        path = self.path / "viewer_state.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            _log.warning("Ignoring unreadable viewer state at %s: %s", path, exc)
            return {}

    def to_notebook(
        self,
        output: str | Path,
        columns: list[str] | None = None,
        t0=None,
        t1=None,
        groups: list[int] | None = None,
        region_label: str = "current range",
        quantity_key: str = "sauerbrey_mass",
        params: dict | None = None,
    ) -> Path:
        from .notebooks import write_analysis_notebook

        return write_analysis_notebook(
            self,
            output,
            columns=columns,
            t0=t0,
            t1=t1,
            groups=groups,
            region_label=region_label,
            quantity_key=quantity_key,
            params=params,
        )


def open_run(path: str | Path) -> QCMRun:
    return QCMRun(path)
