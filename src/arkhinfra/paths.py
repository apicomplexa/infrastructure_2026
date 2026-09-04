"""Every path the repository knows about, resolved from the repository root.

Nothing here depends on the current working directory, so a report may be moved
between directories without touching its code.  ROOT is found by walking up from
this file until a directory holding pixi.toml appears; that also survives the
package itself being moved.
"""
from __future__ import annotations

from pathlib import Path


def _find_root(start: Path) -> Path:
    for p in (start, *start.parents):
        if (p / "pixi.toml").exists():
            return p
    raise RuntimeError(f"no pixi.toml above {start} -- is this a checkout?")


ROOT = _find_root(Path(__file__).resolve())

DATA = ROOT / "data"
RAW = DATA / "raw"
RAW2 = DATA / "raw_v2"
RAW3 = DATA / "raw_v3"
PROC = DATA / "processed"
TILE_CACHE = DATA / "tile_cache"

DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"

# First delivery (2026-06-28).
V1_CSV = RAW / "objects_arkhangelsk_2026-06-28_enriched.csv"
V1_HEALTH = RAW / "objects_arkhangelsk_2026-06-28_health.xlsx"
REF_2022 = RAW / "objects_3_districts_2022.xlsx"

# Second delivery (2026-08-24), withdrawn by the third.
V2_ARK = RAW2 / "ARKTMED_Arkhangelsk_2021-2026_all_categories_20260824_082854.xlsx"
V2_CMP = RAW2 / "сравнение_документов_2026-08-24_093901.xlsx"
V2_SUM = RAW2 / "итоги_сравнения_3_округа.csv"

# Third delivery (2026-08-31).
V3_CSV = RAW3 / "infrastructure_архангельск_2026-08-31_quality_excel.csv"
V3_BASE = RAW3 / "export_base_688669_zal6mp.xlsx"
V3_ARK = RAW3 / "ARKTMED_Arkhangelsk_2021-2026_all_categories_20260831_172749.xlsx"

# Alternative source: FSRAR consolidated licence registry (2026-07-01 snapshot).
RAW_EGAIS = DATA / "raw_alter_egais"
EGAIS_XML = RAW_EGAIS / "data-20260701t0000-structure-20190918t0000.xml"
EGAIS_TSV = PROC / "egais_licences_arkhangelsk.tsv"
