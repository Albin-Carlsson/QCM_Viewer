"""Shared test fixtures for the QCM viewer."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Keep test-built viewers from overwriting the user's real remembered session,
# saved experiment-parameter presets, or persistent run store.
_TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="qcm_test_"))
os.environ.setdefault("QCM_SESSION_FILE", str(_TEST_STATE_DIR / "session.json"))
os.environ.setdefault("QCM_PRESETS_FILE", str(_TEST_STATE_DIR / "presets.json"))
os.environ.setdefault("QCM_RUNS_DIR", str(_TEST_STATE_DIR / "runs"))

_ECHEM_RUN = Path("/tmp/real-echem-run")


def _synthesize_cp_run(dest: Path) -> None:
    """Build a small CP cycling run at ``dest`` from synthetic instrument files.

    Mirrors the real fixture's shape (standardized Time_N/Fr_N/D_N CSV + a
    UTF-16 PSTrace CP export with the ``s, µC, s, µA, s, V`` header) so every
    test that needs an EQCM run works on a fresh machine / CI runner. When a
    real import already sits at ``dest`` it is left untouched.
    """
    import numpy as np

    from qcm.profiles import import_run

    rng = np.random.default_rng(42)
    n = 3000
    dt = 1.0
    t = np.arange(n) * dt
    # ~26 plating/stripping cycles: 60 s at −1 mA, 55 s at +1 mA.
    period = 115.0
    phase = np.mod(t, period)
    current_a = np.where(phase < 60.0, -1e-3, 1e-3)
    charge_c = np.cumsum(current_a * dt)
    potential_v = np.where(current_a < 0, -1.05, -0.45) + rng.normal(0, 0.004, n)

    # QCM response obeying Faraday for Zn (M=65.38, z=2) at C = 17.7 ng/Hz/cm².
    mass_ng_cm2 = -charge_c * 65.38 / (2 * 96485.0) / 1.131 * 1e9
    cols: dict[str, np.ndarray] = {}
    for order in (1, 3, 5):
        df_n = -mass_ng_cm2 / 17.7 + rng.normal(0, 0.4, n)
        cols[f"Time_{order}"] = t
        cols[f"Fr_{order}"] = 5e6 * order + df_n * order
        cols[f"D_{order}"] = 1e-6 * order + np.abs(mass_ng_cm2) * 1e-11

    workdir = Path(tempfile.mkdtemp(prefix="qcm_fixture_"))
    qcm_csv = workdir / "synthetic_cp.csv"
    header = ",".join(cols)
    rows = "\n".join(
        ",".join(f"{cols[c][i]:.6f}" for c in cols) for i in range(n)
    )
    qcm_csv.write_text(f"{header}\n{rows}\n")

    ps_csv = workdir / "synthetic_cp_PS.csv"
    ps_lines = ["Synthetic PSTrace export", "", "Measurement", "", ""]
    ps_lines.append("s,µC,s,µA,s,V")
    for i in range(n):
        ps_lines.append(
            f"{t[i]:.3f},{charge_c[i] * 1e6:.4f},{t[i]:.3f},"
            f"{current_a[i] * 1e6:.4f},{t[i]:.3f},{potential_v[i]:.4f}"
        )
    ps_csv.write_bytes(("\n".join(ps_lines) + "\n").encode("utf-16"))

    import_run(qcm_csv, dest, ps_source=ps_csv, overwrite=True)


@pytest.fixture(scope="session", autouse=True)
def real_echem_run() -> Path:
    """Guarantee an EQCM CP run at /tmp/real-echem-run (synthesizing if absent)."""
    if not (_ECHEM_RUN / "manifest.json").exists():
        _synthesize_cp_run(_ECHEM_RUN)
    return _ECHEM_RUN

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_RUN = _REPO_ROOT / "view-run"


@pytest.fixture(scope="session")
def demo_run_path() -> Path:
    """Path to the ingested demo run used by composition smoke tests."""
    if not (_DEMO_RUN / "manifest.json").exists():
        pytest.skip("view-run/manifest.json missing; run the ingest demo first")
    return _DEMO_RUN
