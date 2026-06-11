"""The import-profile plugin contract.

A *profile* adapts one on-disk export format to the canonical run frame. This
module defines the contract so profiles are uniform, confidence-ranked, and
discoverable — in-tree or shipped as a separate pip package via the
``qcm.profiles`` entry-point group (see ``docs/add-a-data-source.md``).

Two kinds:

- ``"qcm"`` — a resonance source that *becomes* the run. Its :meth:`Profile.read`
  returns a :class:`ProfileResult` (canonical frame + provenance metadata +
  non-fatal warnings).
- ``"ps"`` — a potentiostat export *merged onto* a QCM source. It implements
  :meth:`Profile.detect` only (for classification); the pairing/interpolation is
  owned by :func:`qcm.profiles.import_run`, because it is an overlay, not a run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, runtime_checkable

import polars as pl

ProfileKind = Literal["qcm", "ps"]


@dataclass
class ProfileResult:
    """What a qcm-source profile produces from one file.

    ``frame`` is the canonical long-form run frame; ``metadata`` is provenance
    folded into the run manifest; ``warnings`` are non-fatal notes (dropped rows,
    assumed defaults) the UI/CLI can surface without failing the import.
    """
    frame: pl.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class Profile(Protocol):
    """A pluggable import adapter for one export format."""

    name: str
    kind: ProfileKind

    def detect(self, path: Path) -> float:
        """Confidence in ``[0, 1]`` that this profile can read ``path`` (0 = no)."""
        ...

    def read(self, path: Path, *, rename: dict[str, str] | None = None) -> ProfileResult:
        """Read a ``"qcm"`` source into a :class:`ProfileResult` (``"ps"`` may raise)."""
        ...


@dataclass
class FunctionProfile:
    """Adapter that turns a module's predicate + reader into a :class:`Profile`.

    Lets the existing per-format functions register without being rewritten. A
    boolean predicate is mapped to a ``1.0`` / ``0.0`` confidence; a profile that
    wants graded scoring can pass a ``detect`` that already returns a float. For
    ``"ps"`` profiles ``read_fn`` is ``None`` (the pairing lives in import_run).
    """
    name: str
    kind: ProfileKind
    detect_fn: Callable[[Path], bool | float]
    read_fn: Callable[..., Any] | None = None

    def detect(self, path: Path) -> float:
        try:
            return float(self.detect_fn(path))  # bool -> 1.0/0.0; float passes through
        except Exception:
            return 0.0

    def read(self, path: Path, *, rename: dict[str, str] | None = None) -> ProfileResult:
        if self.read_fn is None:
            raise NotImplementedError(
                f"Profile '{self.name}' is a potentiostat (ps) profile; it is paired "
                f"onto a QCM source by import_run, not read as a run."
            )
        result = self.read_fn(path, rename=rename)
        if isinstance(result, ProfileResult):
            return result
        return ProfileResult(frame=result)
