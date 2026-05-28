"""Shared test fixtures for the QCM viewer."""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_RUN = _REPO_ROOT / "view-run"


@pytest.fixture(scope="session")
def demo_run_path() -> Path:
    """Path to the ingested demo run used by composition smoke tests."""
    if not (_DEMO_RUN / "manifest.json").exists():
        pytest.skip("view-run/manifest.json missing; run the ingest demo first")
    return _DEMO_RUN
