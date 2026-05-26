from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from .demo import make_demo_data
from .ingest import ingest
from .run import open_run

app = typer.Typer(help="QCM parquet viewer CLI")
console = Console()


@app.command("demo-data")
def demo_data(out_dir: Path, groups: int = 3, sequences: int = 250, points_per_sweep: int = 500):
    path = make_demo_data(out_dir, groups=groups, sequences=sequences, points_per_sweep=points_per_sweep)
    console.print(f"Wrote demo parquet: {path}")


@app.command(name="ingest")
def ingest_cmd(source: Path, dest: Path, overwrite: bool = typer.Option(False, "--overwrite")):
    out = ingest(source, dest, overwrite=overwrite)
    console.print(f"Ingested run: {out}")



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
                import time
                tic = time.perf_counter()
                tic_df = run._read_parquet("raw", ["fit_center"], run.time_start, run.time_end, None)
                elapsed = (time.perf_counter() - tic) * 1000
                bench.add_row("raw frequency table", str(tic_df.height), f"{elapsed:.1f} ms", "OK")
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
