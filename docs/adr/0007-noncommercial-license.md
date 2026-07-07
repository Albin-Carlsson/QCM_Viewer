# 0007 — PolyForm Noncommercial license

Status: Accepted

## Context

The project should be freely usable by the research community — other academic
groups, students, public research institutions — while preventing for-profit
companies from commercialising the author's work without permission. The author
remains credited as the original author. Standard permissive licenses
(MIT/BSD/Apache) and even copyleft (GPL) all **permit commercial use**, so none
of them express this intent.

## Decision

License under **PolyForm Noncommercial License 1.0.0** (`LICENSE`), a
well-drafted, software-specific source-available license that:

- permits any **noncommercial** purpose, explicitly including use by educational
  institutions and public research organisations (covers the target audience);
- reserves commercial use to the licensor (a company needs a separate grant);
- requires the `Required Notice` (copyright) to travel with copies.

Copyright holder: **Albin Carlsson and Uppsala University**. Metadata is wired
through `pyproject.toml` (`license`, `classifiers: License :: Other/Proprietary
License`) and `CITATION.cff` (`LicenseRef-PolyForm-Noncommercial-1.0.0`).

## Consequences

- **Good:** matches the author's intent exactly; academics can use, modify, and
  share; commercialisation requires permission; attribution is enforced.
- **Cost / caveat:** this is **source-available, not OSI "open source"** (OSI
  forbids field-of-use restrictions). Practical implications:
  - It is **not eligible for JOSS** and similar venues that require an
    OSI-approved license. If an academic software paper is later desired, that
    venue choice (or a relicensing decision) must account for this.
  - Some users/CI assume "open source"; the README/marketing must say
    "noncommercial / source-available", not "open source".
- **Caveat:** with Uppsala University named as a copyright holder, the
  university's IP policy may govern relicensing or commercial grants — confirm
  institutional ownership before issuing any commercial license.
- **Reversible:** the copyright holders can always relicense (e.g. dual-license,
  or move to a permissive license) since they hold the rights.
