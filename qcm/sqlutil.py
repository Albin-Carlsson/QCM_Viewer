"""Small shared helpers for building DuckDB SQL safely.

DuckDB has no parameter binding for the path inside ``read_parquet('…')``, so
every query that embeds a filesystem path must escape it as a SQL string
literal — a run living under a folder like ``viktor's data`` would otherwise
break every query with a parser error.
"""
from __future__ import annotations

from pathlib import Path


def sql_path(path: str | Path) -> str:
    """Escape a filesystem path/glob for use inside a SQL string literal."""
    return str(path).replace("'", "''")
