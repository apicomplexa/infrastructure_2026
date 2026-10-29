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
RAW4 = DATA / "raw_v4"
PROC = DATA / "processed"
TILE_CACHE = DATA / "tile_cache"

# Derived files, one subdirectory per pipeline that writes them.  File names
# keep their pipeline prefix, so a file copied out of its folder still says
# where it came from.
PROC_EGAIS = PROC / "egais"                # parse-egais
PROC_MATCH_2022 = PROC / "match_2022"      # match-2022
PROC_TAXONOMY = PROC / "taxonomy_2022"     # build-taxonomy + its audit scripts
PROC_LICENCES = PROC / "v4_licences"       # match-egais-v4
PROC_YANDEX = PROC / "v4_yandex"           # check-yandex
PROC_DELIVER = PROC / "deliverables"       # export-licences: the XLSX handed on
PROC_ARCHIVE = PROC / "_archive"           # superseded outputs, kept for reference

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

# Fourth delivery (2026-09-03/04) -- two risk-layer extracts, not a new survey.
# One file per risk factor; both carry the v3 column schema and re-tag objects
# that are already in V3_CSV.
V4_TOBACCO = RAW4 / "infrastructure_архангельск_2026-09-03_quality_excel табачное изделие.csv"
V4_ALCOHOL = RAW4 / "infrastructure_архангельск_2026-09-04_quality_excel алкоголь.csv"

# Alternative source: FSRAR consolidated licence registry (2026-07-01 snapshot).
RAW_EGAIS = DATA / "raw_alter_egais"
EGAIS_XML = RAW_EGAIS / "data-20260701t0000-structure-20190918t0000.xml"
EGAIS_TSV = PROC_EGAIS / "egais_licences_arkhangelsk.tsv"

# Vendored packages that are not part of `arkhinfra` and must stay liftable out
# of this repository.  `packages/licmatch` is the address-level record-linkage
# rule; reports and scripts reach it through `ensure_licmatch_path()` rather
# than through a changed bootstrap, because every report's setup cell is kept
# byte-identical on purpose.
PACKAGES = ROOT / "packages"
LICMATCH_SRC = PACKAGES / "licmatch" / "src"


def ensure_licmatch_path() -> Path:
    """Put the vendored `licmatch` package on sys.path, once.

    A no-op where the package is installed into the environment instead (see
    packages/licmatch/README.md): an installed copy already imports, and this
    only ever appends a path, never shadows one.
    """
    import sys

    p = str(LICMATCH_SRC)
    if LICMATCH_SRC.is_dir() and p not in sys.path:
        sys.path.append(p)
    return LICMATCH_SRC


# The registry ships as a ZIP holding the one XML; `scripts/parse_egais.py`
# streams it from either, so the 10.9 GB file need never be unpacked.
EGAIS_ZIP = RAW_EGAIS / "data-20260701t0000-structure-20190918t0000.zip"
# The same 27 columns as EGAIS_TSV over the three cities of the final delivery
# (parse-egais-final).  A separate file, so the v4 join keeps its input.
EGAIS_FINAL_TSV = PROC_EGAIS / "egais_licences_final.tsv"
