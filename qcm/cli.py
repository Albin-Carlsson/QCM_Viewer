from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from .demo import PRESETS, make_demo_data
from .ingest import ingest
from .profiles import import_run, resolve_import_target
from .run import open_run

app = typer.Typer(help="QCM parquet viewer CLI")
console = Console()


@app.command("demo-data")
def demo_data(
    out_dir: Path,
    preset: str = typer.Option(
        "small",
        "--preset",
        "-p",
        help="Demo size preset: small for quick testing, long for a ~500 MB stress-test stream.",
    ),
    technique: str = typer.Option(
        "cv",
        "--technique",
        "-t",
        help="Electrochemistry technique: cv (cyclic voltammetry) or cp (chronopotentiometry).",
    ),
    target_mb: int | None = typer.Option(
        None,
        "--target-mb",
        help="Approximate parquet file size target. Defaults to 500 MB for --preset long.",
    ),
    groups: int | None = typer.Option(None, help="Override number of overtones/groups."),
    sequences: int | None = typer.Option(None, help="Override number of sweeps. Long preset usually stops by --target-mb first."),
    points_per_sweep: int | None = typer.Option(None, help="Override number of frequency points per sweep."),
    compression: str | None = typer.Option(
        None,
        help="Parquet compression: zstd, snappy, or none. Long preset defaults to none for predictable size.",
    ),
):
    if preset not in PRESETS:
        valid = ", ".join(PRESETS)
        raise typer.BadParameter(f"Unknown preset {preset!r}. Choose one of: {valid}")
    if technique not in ("cv", "cp"):
        raise typer.BadParameter(f"Unknown technique {technique!r}. Choose 'cv' or 'cp'.")
    path = make_demo_data(
        out_dir,
        preset=preset,
        technique=technique,
        groups=groups,
        sequences=sequences,
        points_per_sweep=points_per_sweep,
        target_mb=target_mb,
        compression=compression,
    )
    size_mb = path.stat().st_size / (1024 * 1024)
    console.print(f"Wrote {preset} {technique.upper()} demo parquet: {path} ({size_mb:.1f} MB)")


@app.command(name="ingest")
def ingest_cmd(
    source: Path,
    dest: Path,
    overwrite: bool = typer.Option(False, "--overwrite"),
    raw_part_rows: int = typer.Option(
        1_000_000,
        "--raw-part-rows",
        help="Rows per raw parquet part written during ingest. Lower this if memory is tight.",
    ),
    memory_limit: str = typer.Option(
        "4GB",
        "--memory-limit",
        help="DuckDB memory limit during index/pyramid build, e.g. 2GB, 4GB, 8GB.",
    ),
):
    out = ingest(
        source,
        dest,
        overwrite=overwrite,
        raw_part_rows=raw_part_rows,
        memory_limit=memory_limit,
    )
    console.print(f"Ingested optimized run: {out}")



@app.command(name="import")
def import_cmd(
    source: Path,
    dest: Path,
    ps: Path | None = typer.Option(
        None,
        "--ps",
        help="PSTrace potentiostat csv to merge (potential/current/charge), aligned to the QCM timestamps. Standardized QCM csv source only.",
    ),
    ps_offset: float = typer.Option(
        0.0,
        "--ps-offset",
        help="Seconds to shift the PS stream before interpolation (positive = PS later).",
    ),
    cv_scan_rate: float | None = typer.Option(
        None,
        "--cv-scan-rate",
        help="CV scan rate in V/s for a cyclic-voltammetry PS export (overrides the filename-parsed value).",
    ),
    overwrite: bool = typer.Option(False, "--overwrite"),
    raw_part_rows: int = typer.Option(
        1_000_000,
        "--raw-part-rows",
        help="Rows per raw parquet part written during ingest. Lower this if memory is tight.",
    ),
    memory_limit: str = typer.Option(
        "4GB",
        "--memory-limit",
        help="DuckDB memory limit during index/pyramid build, e.g. 2GB, 4GB, 8GB.",
    ),
):
    """Import a run from any supported source.

    Accepts a raw QCM parquet (file or directory) or a standardized QCM csv
    (Time_N/Fr_N/D_N), producing the same kind of run directory. Pass --ps with
    a standardized csv source to merge a PSTrace potentiostat export.
    """
    out = import_run(
        source,
        dest,
        ps_source=ps,
        ps_offset_s=ps_offset,
        cv_scan_rate=cv_scan_rate,
        overwrite=overwrite,
        raw_part_rows=raw_part_rows,
        memory_limit=memory_limit,
    )
    with open_run(out) as run:
        kind = "raw" if run.has_raw else "fit-only"
        echem = " + echem" if "echem" in run.capabilities else ""
        console.print(f"Imported {kind}{echem} run: {out} ({len(run.groups)} overtone channels)")


@app.command()
def diagnose(run_path: Path):
    run = open_run(run_path)

    table = Table("Field", "Value")
    table.add_row("run_id", run.id)
    table.add_row("time_start", str(run.time_start))
    table.add_row("time_end", str(run.time_end))
    table.add_row("groups", str(run.groups))
    table.add_row("columns", ", ".join(run.columns))
    console.print(table)

    console.print("\n[bold]Timeline router test[/bold]")
    df, meta = run.timeline(["fit_center"], include_meta=True)
    console.print(f"Default fit_center timeline: {df.height} rows via {meta.level} in {meta.elapsed_ms:.1f} ms")

    bench = Table("Level", "Rows", "Elapsed", "Status")
    for level in ["sweeps", *run.manifest.pyramid_levels, "raw"]:
        try:
            if level == "sweeps":
                tic_df, tic_meta = run.timeline(["fit_center"], level="raw", include_meta=True)
            elif level == "raw":
                bench.add_row(
                    "raw frequency table",
                    str(run.manifest.metadata.get("rows", "?")),
                    "skipped",
                    "OK: raw full scan intentionally avoided",
                )
                continue
            else:
                tic_df, tic_meta = run.timeline(["fit_center"], level=level, include_meta=True)
            bench.add_row(level, str(tic_df.height), f"{tic_meta.elapsed_ms:.1f} ms", "OK")
        except Exception as exc:  # noqa: BLE001 — diagnose reports failures, it doesn't crash on them
            bench.add_row(level, "-", "-", f"FAILED: {exc}")
    console.print(bench)

    console.print("\n[green]Note:[/green] fit_center/fit_fwhm/fit_gamma raw-resolution timelines should use the sweep index, not the raw frequency table, because those values are repeated for every frequency point.")


@app.command()
def notebook(run_path: Path, output: Path = Path("qcm_view.ipynb")):
    with open_run(run_path) as run:
        out = run.to_notebook(output)
    console.print(f"Wrote notebook: {out}")


@app.command()
def standardize(
    source: Path = typer.Argument(..., help="A QCM instrument export, e.g. a Qsoft .txt."),
    output: Path | None = typer.Argument(
        None, help="Output csv path. Defaults to the source path with a .csv suffix."
    ),
):
    """Convert an instrument export to the lab's standardized csv.

    Reads any supported QCM source (Qsoft .txt, variant csv) and writes the
    wide ``Time_N, Fr_N, D_N`` exchange format next to it — the notebook's
    data-standardization step, for tooling that expects that shape. The viewer
    itself does not need this: it imports instrument files directly.
    """
    from .profiles import detect_profile, profile_kind
    from .profiles.qsoft_txt import read_qsoft_txt
    from .profiles.standardized_csv import read_standardized_csv, write_standardized_csv

    name = detect_profile(source)
    if name is None or profile_kind(name) != "qcm":
        raise typer.BadParameter(
            f"{source} is not a recognized QCM export. Supported: Qsoft .txt "
            f"(f{{n}}_/D{{n}}_ columns) and standardized csv (Time_N/Fr_N/D_N)."
        )
    out = output or source.with_suffix(".csv")
    if out.resolve() == source.resolve():
        raise typer.BadParameter(
            f"{source} is already a csv; pass an explicit output path to rewrite it."
        )
    frame = read_qsoft_txt(source) if name == "qsoft_txt" else read_standardized_csv(source)
    write_standardized_csv(frame, out)
    console.print(f"Standardized csv: {out}")


@app.command("export-data")
def export_data(run_path: Path, output: Path, columns: list[str] = typer.Option(["fit_center", "fit_fwhm"]), fmt: str = "parquet"):
    with open_run(run_path) as run:
        out = run.export_data(output, columns=columns, fmt=fmt)
    console.print(f"Exported: {out}")


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _resolve_port(requested: int) -> int:
    """The requested port if free, otherwise a free one (with a notice).

    ``--port 0`` is passed through unchanged — Panel then picks a free port and
    opens the browser there. Any other busy port falls back gracefully instead
    of crashing with 'address already in use'.
    """
    import socket

    if requested == 0:
        return 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", requested))
            return requested
        except OSError:
            pass
    chosen = _free_port()
    console.print(f"Port {requested} is in use — starting on {chosen} instead.")
    return chosen


def _serve_runs(run_dirs: list[Path], port: int, show: bool) -> None:
    cmd = [sys.executable, "-m", "panel", "serve", str(Path(__file__).parent / "panel_app.py"),
           "--port", str(_resolve_port(port))]
    if show:
        cmd.append("--show")
    if run_dirs:
        cmd += ["--args", *[str(p) for p in run_dirs]]
    raise typer.Exit(subprocess.call(cmd))


@app.command()
def view(
    source: list[Path] = typer.Argument(None, help="Run folders, experiment folders, or instrument files."),
    cv_scan_rate: float | None = typer.Option(
        None, "--cv-scan-rate",
        help="CV scan rate in V/s. Overrides the value parsed from the filename for cyclic-voltammetry runs.",
    ),
    port: int = 5006,
    show: bool = True,
):
    """Open the viewer on anything — the easy one-step command.

    Point it at an experiment folder, a QCM instrument file, a parquet, or an
    already-ingested run. A sibling potentiostat ``*_PS.csv`` is paired
    automatically, raw files are imported to a temporary run, and run folders
    open directly. Pass several sources to overlay them; the browser opens.
    With no source at all, a picker page opens (offering to resume the last
    session when one is remembered).
    """
    if not source:
        _serve_runs([], port, show)
        return
    from .store import import_or_reuse

    run_dirs: list[Path] = []
    for src in source:
        qcm_src, ps_src = resolve_import_target(src)
        if qcm_src.is_dir() and (qcm_src / "manifest.json").exists():
            run_dirs.append(qcm_src)
            continue
        paired = f" + {ps_src.name}" if ps_src else ""
        dest, reused = import_or_reuse(qcm_src, ps_source=ps_src, cv_scan_rate=cv_scan_rate)
        console.print(
            f"{'Reusing saved' if reused else 'Importing'} {qcm_src.name}{paired} → {dest}"
        )
        run_dirs.append(dest)
    _serve_runs(run_dirs, port, show)


@app.command()
def serve(run_path: list[Path] = typer.Argument(...), port: int = 5006, show: bool = True):
    """Serve the viewer on already-ingested run directories (overlay if 2+)."""
    _serve_runs(list(run_path), port, show)


if __name__ == "__main__":
    app()
