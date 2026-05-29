from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from .demo import PRESETS, make_demo_data
from .ingest import ingest
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
        except Exception as exc:
            bench.add_row(level, "-", "-", f"FAILED: {exc}")
    console.print(bench)

    console.print("\n[green]Note:[/green] fit_center/fit_fwhm/fit_gamma raw-resolution timelines should use the sweep index, not the raw frequency table, because those values are repeated for every frequency point.")


@app.command()
def notebook(run_path: Path, output: Path = Path("qcm_view.ipynb")):
    run = open_run(run_path)
    out = run.to_notebook(output)
    console.print(f"Wrote notebook: {out}")


@app.command("export-data")
def export_data(run_path: Path, output: Path, columns: list[str] = typer.Option(["fit_center", "fit_fwhm"]), fmt: str = "parquet"):
    run = open_run(run_path)
    out = run.export_data(output, columns=columns, fmt=fmt)
    console.print(f"Exported: {out}")


@app.command()
def serve(run_path: Path, port: int = 5006, show: bool = True):
    cmd = [sys.executable, "-m", "panel", "serve", str(Path(__file__).parent / "panel_app.py"), "--port", str(port), "--args", str(run_path)]
    if show:
        cmd.insert(-2, "--show")
    raise typer.Exit(subprocess.call(cmd))


if __name__ == "__main__":
    app()
