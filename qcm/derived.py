from __future__ import annotations

import polars as pl

SAUERBREY_DEFAULT = 17.7  # ng cm^-2 Hz^-1, configurable approximation


def delta_f(df: pl.DataFrame, column: str = "fit_center", group_col: str = "group") -> pl.DataFrame:
    base = df.group_by(group_col).agg(pl.col(column).first().alias("baseline"))
    return df.join(base, on=group_col).with_columns((pl.col(column) - pl.col("baseline")).alias("delta_f"))


def sauerbrey_mass(df: pl.DataFrame, harmonic: int | None = None, constant: float = SAUERBREY_DEFAULT) -> pl.DataFrame:
    out = delta_f(df)
    n = harmonic if harmonic else 1
    return out.with_columns((-constant * pl.col("delta_f") / n).alias("sauerbrey_mass"))


def quality_factor(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns((pl.col("fit_center") / pl.col("fit_fwhm")).alias("quality_factor"))


def dissipation(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns((pl.col("fit_fwhm") / pl.col("fit_center")).alias("dissipation"))
