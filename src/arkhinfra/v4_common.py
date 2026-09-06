"""Loaders and tier logic for the fourth delivery (data/raw_v4).

The fourth delivery is not a new survey.  It is a **risk-attribution layer** over
the third: two CSVs, one per risk factor, that re-tag objects already present in
`V3_CSV` with a judgement about whether they plausibly sell alcohol or tobacco.
100 % of the tobacco rows and 99.8 % of the alcohol rows sit within 100 m of an
existing v3 object, and 94-98 % of their `matched_source_ids` are v3 ids.

Kept separate from `v3_common.py` on the same principle as `basecheck.py` and
`egais.py`: the v3 reports must keep producing what they produced before.  What
is shared is imported from `v3_common`, never copied.

The one rule this module does *not* import is `recode_2022()`.  The fourth
delivery introduces a fourth category vocabulary, and the v3 rule silently drops
93 % of the tobacco file on it -- see `recode_2022_v4()` below.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .paths import RAW4, V4_ALCOHOL, V4_TOBACCO  # noqa: F401
from .v3_common import ACCENT, GREEN, MIXED, OLD, PURPLE, RISK  # noqa: F401
from .v3_common import haversine_m, norm_address, norm_name, norm_okrug  # noqa: F401
from .v3_common import recode_2022  # noqa: F401

# --------------------------------------------------------------------------
# the fourth vocabulary
# --------------------------------------------------------------------------
# `category_orig` carries exactly one value per file, and `type_orig` four.
# Neither vocabulary appears in the first three deliveries.
CATEGORY_TOBACCO = "Табачная и никотинсодержащая продукция"
CATEGORY_ALCOHOL = "Алкогольная продукция"

# tobacco
T_POSSIBLE = "Возможная продажа табачной продукции"
T_SPECIALISED = "Специализированная продажа табачной продукции"
T_VAPE = "Вейпы и никотинсодержащая продукция"
T_HOOKAH = "Кальянные"
# alcohol
A_SHOP = "Возможная продажа алкоголя в магазинах"
A_CATERING = "Возможная подача алкоголя в общепите"
A_SPECIALISED = "Специализированная продажа алкоголя"
A_BAR = "Подача алкоголя в барах и пабах"

TYPE_EN = {
    T_POSSIBLE: "Possible tobacco sale",
    T_SPECIALISED: "Specialised tobacco shop",
    T_VAPE: "Vape & nicotine products",
    T_HOOKAH: "Hookah lounges",
    A_SHOP: "Possible alcohol sale (shops)",
    A_CATERING: "Possible alcohol service (catering)",
    A_SPECIALISED: "Specialised alcohol shop",
    A_BAR: "Alcohol service in bars & pubs",
}

# The two tiers that matter for every count in the report.  "Direct" types name
# the product; "inferred" types only say the object *could* sell it -- the
# contractor's own verification_comment calls these
# "требует отдельной проверки" (needs separate checking).
INFERRED_TYPES = {T_POSSIBLE, A_SHOP, A_CATERING}

# On-trade: alcohol served for consumption on the premises.  Kept apart from
# off-trade because the licence registry licenses the two separately, and only
# the off-trade count is comparable with a shop count.
ON_TRADE_TYPES = {A_CATERING, A_BAR}

EVIDENCE_ORDER = ["Direct", "Inferred"]
TRADE_ORDER = ["off-trade", "on-trade"]


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------
def _load_one(path, risk: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)
    df["risk"] = risk
    df["okrug_key"] = df["district_orig"].map(norm_okrug)
    df["type_en"] = df["type_orig"].map(TYPE_EN).fillna(df["type_orig"])
    df["evidence"] = np.where(df["type_orig"].isin(INFERRED_TYPES), "Inferred", "Direct")
    df["trade"] = np.where(df["type_orig"].isin(ON_TRADE_TYPES), "on-trade", "off-trade")
    df["category_2022"] = recode_2022_v4(df)
    return df


def load_v4_tobacco() -> pd.DataFrame:
    """The tobacco risk layer (749 x 22 + derived)."""
    return _load_one(V4_TOBACCO, "Tobacco")


def load_v4_alcohol() -> pd.DataFrame:
    """The alcohol risk layer (945 x 22 + derived)."""
    return _load_one(V4_ALCOHOL, "Alcohol")


def load_v4() -> pd.DataFrame:
    """Both layers stacked, with a ``dual`` flag.

    The two files overlap: 359 coordinates carry both an alcohol and a tobacco
    row, so a distinct-site count must dedupe on the coordinate rather than sum
    the two file lengths (1,694 rows -> 1,335 sites).
    """
    df = pd.concat([load_v4_tobacco(), load_v4_alcohol()], ignore_index=True)
    df["site_key"] = (df["latitude"].round(6).astype(str) + "|"
                      + df["longitude"].round(6).astype(str))
    df["dual"] = df["site_key"].duplicated(keep=False)
    return df


def sites(df: pd.DataFrame) -> pd.DataFrame:
    """One row per distinct site from a stacked v4 frame."""
    return df.loc[~df["site_key"].duplicated()].reset_index(drop=True)


# --------------------------------------------------------------------------
# the recoding defect
# --------------------------------------------------------------------------
# v3_common.recode_2022() tests the category/type/name blob for the substring
# "табак".  Every one of the fourth delivery's own labels spells the stem
# "табач-" ("Табачная и никотинсодержащая продукция", "Возможная продажа
# табачной продукции"), which does not contain "табак", so the tobacco rule
# never fires on this vocabulary: 698 of 749 tobacco rows land in "Other".
# Only the 50 rows whose type says "вейп" or "кальян" survive.
#
# The fix is one stem.  It is applied here rather than in v3_common for the same
# reason basecheck.py keeps its own normalisers: changing the shared rule would
# silently move numbers in three already-rendered v3 reports.
_TOBACCO_STEM = "табач"


def recode_2022_v4(df: pd.DataFrame) -> pd.Series:
    """`recode_2022()` with the tobacco stem the fourth vocabulary needs.

    Runs the shared rule first, then promotes anything the fourth delivery
    itself labels tobacco.  Everything the shared rule already classified as
    tobacco keeps that class, so the two agree wherever both fire.
    """
    base = recode_2022(df)
    blob = (df["category_orig"].fillna("").astype(str).str.lower() + " | "
            + df["type_orig"].fillna("").astype(str).str.lower())
    return base.mask(blob.str.contains(_TOBACCO_STEM, na=False), "Tobacco outlets")


# --------------------------------------------------------------------------
# opening hours
# --------------------------------------------------------------------------
def parse_hours(v):
    """`opening_hours_orig` holds two incompatible encodings in one column.

    2GIS-sourced rows carry a JSON object keyed by weekday; OSM-sourced rows
    carry an OSM opening_hours string ("Mo-Su 08:00-22:00").  Returns
    ("json" | "osm" | "none", is_24x7 or None) so a report can say how much of
    the column it could actually read.
    """
    if not isinstance(v, str) or not v.strip():
        return "none", None
    s = v.strip()
    if s.startswith("{"):
        try:
            return "json", bool(json.loads(s).get("is_24x7"))
        except (ValueError, AttributeError):
            return "json", None
    return "osm", ("24/7" in s)


def hours_frame(df: pd.DataFrame) -> pd.DataFrame:
    """encoding + is_24x7 columns for a v4 frame."""
    parsed = df["opening_hours_orig"].map(parse_hours)
    return pd.DataFrame({
        "hours_encoding": [p[0] for p in parsed],
        "is_24x7": [p[1] for p in parsed],
    }, index=df.index)


# --------------------------------------------------------------------------
# provenance: how much of v4 is already in v3
# --------------------------------------------------------------------------
def nearest_v3(df: pd.DataFrame, v3: pd.DataFrame) -> pd.DataFrame:
    """Distance from each v4 record to the nearest v3 object, and its class.

    The fourth delivery claims to be a new export; this is what decides whether
    it carries new objects or re-tags old ones.
    """
    ref = v3.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    d = haversine_m(
        df["latitude"].to_numpy(float)[:, None],
        df["longitude"].to_numpy(float)[:, None],
        ref["latitude"].to_numpy(float)[None, :],
        ref["longitude"].to_numpy(float)[None, :],
    )
    j = d.argmin(axis=1)
    return pd.DataFrame({
        "v3_distance_m": d[np.arange(len(df)), j],
        "v3_category_2022": ref["category_2022"].to_numpy()[j],
        "v3_category_orig": ref["category_orig"].to_numpy()[j],
        "v3_name": ref["name_orig"].to_numpy()[j],
    }, index=df.index)


def source_id_overlap(df: pd.DataFrame, v3: pd.DataFrame) -> tuple[int, int]:
    """(v4 source ids also present in v3, total v4 source ids)."""
    def ids(s):
        out = set()
        for v in s.dropna().astype(str):
            out.update(t.strip() for t in v.split(";") if t.strip())
        return out
    i4 = ids(df["matched_source_ids"])
    return len(i4 & ids(v3["matched_source_ids"])), len(i4)


# --------------------------------------------------------------------------
# the licence-registry comparison
# --------------------------------------------------------------------------
def corroboration(df: pd.DataFrame, eg: pd.DataFrame,
                  radii=(25, 50, 100, 200)) -> pd.DataFrame:
    """Two-way spatial agreement between a v4 layer and licensed outlets.

    Forward: the share of v4 objects with a licensed outlet nearby.  Reverse:
    the share of licensed outlets with a v4 object nearby -- the direction that
    answers "does the export miss licensed shops?", which is what the fivefold
    undercount in reports/egais/eda-egais.pdf was about.
    """
    a = df.dropna(subset=["latitude", "longitude"])
    b = eg.dropna(subset=["latitude", "longitude"])
    d = haversine_m(
        a["latitude"].to_numpy(float)[:, None], a["longitude"].to_numpy(float)[:, None],
        b["latitude"].to_numpy(float)[None, :], b["longitude"].to_numpy(float)[None, :],
    )
    fwd, rev = d.min(axis=1), d.min(axis=0)
    return pd.DataFrame([
        {"radius_m": r,
         "v4_near_licence_pct": round(100 * float((fwd <= r).mean()), 1),
         "licence_near_v4_pct": round(100 * float((rev <= r).mean()), 1)}
        for r in radii
    ])
