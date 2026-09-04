"""Loader and normalisers for the FSRAR licence registry extract.

`scripts/parse_egais.py` reduces the 10.9 GB registry XML to
`data/processed/egais_licences_arkhangelsk.tsv`; everything downstream of that
file lives here, so `analysis/egais/eda-egais.qmd` imports rather than copies.

Kept separate from `v3_common.py` deliberately.  This is a different source with
a different grain -- a row is an outlet-licence pair, not an object -- and the
v3 reports must keep producing what they produced before.  What is shared is
imported from v3_common (the palette, `norm_okrug`, `haversine_m`), never
duplicated.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .paths import EGAIS_TSV, V3_CSV  # noqa: F401
from .v3_common import ACCENT, GREEN, MIXED, OLD, PURPLE, RISK  # noqa: F401
from .v3_common import haversine_m, norm_okrug  # noqa: F401

# Registry dates are "05 дек 2012" -- a Russian three-letter month that no
# locale-independent parser recognises.
_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}
_DATE = re.compile(r"^\s*(\d{1,2})\s+([а-я]{3})[а-я]*\.?\s+(\d{4})\s*$", re.I)

# The registry writes the same expiry state two ways, and the same ministry ten.
STATUS_EN = {
    "действующая": "Active",
    "истекла": "Expired",
    "срок действия истек": "Expired",
    "прекращена": "Terminated",
    "переоформлена": "Reissued",
    "аннулирована": "Annulled",
}
STATUS_ORDER = ["Active", "Expired", "Terminated", "Reissued", "Annulled"]

# Licensed activity folded onto five classes.  Only the two retail classes put
# alcohol in front of a resident; the rest are logistics and production.
ACTIVITY_EN = {
    "retail": "Retail (off-trade)",
    "catering": "Retail + on-trade",
    "wholesale": "Wholesale & storage",
    "transport": "Ethanol transport",
    "production": "Production",
}
ACTIVITY_ORDER = ["Retail (off-trade)", "Retail + on-trade", "Wholesale & storage",
                  "Ethanol transport", "Production"]

# Belushya Guba and Rogachevo are on Novaya Zemlya, ~2,000 km north of the city,
# yet the registry files them under "Архангельск г".
NOVAYA_ZEMLYA = ("белушья", "рогачево")

# Street-type words, stripped so "Нагорная ул" and "Нагорная улица" fold onto
# one key.  Wider than the v3_common list because the registry spells types out.
_STREET_TYPES = (r"улица|ул|проспект|пр-кт|пр|переулок|пер|набережная|наб|шоссе|ш|"
                 r"площадь|пл|проезд|бульвар|б-р|тракт|аллея|линия|квартал|"
                 r"территория|тер|микрорайон|мкр|городок|поселок|посёлок")


def parse_ru_date(v) -> pd.Timestamp | pd.NaT:
    """"05 дек 2012" -> Timestamp. ISO strings pass through pandas unchanged."""
    if not isinstance(v, str) or not v.strip():
        return pd.NaT
    m = _DATE.match(v)
    if m:
        day, mon, year = m.group(1), m.group(2).lower(), m.group(3)
        if mon in _MONTHS:
            return pd.Timestamp(int(year), _MONTHS[mon], int(day))
    return pd.to_datetime(v, errors="coerce", dayfirst=True)


def norm_street(v) -> str:
    """Reduce a street label to a comparable key.

    Drops the type word wherever it sits, the city name, punctuation and bare
    initials -- "Тимме Я. Улица" and "улица Тимме" both become "тимме".
    """
    if not isinstance(v, str):
        return ""
    s = v.lower().replace(chr(0x451), "е")
    s = re.sub(r"\bархангельск\w*\b", " ", s)
    # Hyphenated abbreviations first: stripping punctuation ahead of the type
    # words turns "пр-кт" into "пр кт" and leaves the orphan "кт" behind, which
    # splits Троицкий пр-кт from Троицкий проспект into two keys.
    for abbr, full in (("пр-кт", "проспект"), ("б-р", "бульвар"), ("пр-д", "проезд")):
        s = s.replace(abbr, full)
    s = re.sub(r"[^0-9a-zа-я]+", " ", s)
    s = re.sub(r"\b(?:" + _STREET_TYPES + r")\b", " ", s)
    return " ".join(t for t in s.split() if len(t) > 1)


def classify_activity(v) -> str:
    s = str(v).lower()
    if "перевозк" in s:
        return ACTIVITY_EN["transport"]
    if "производств" in s:
        return ACTIVITY_EN["production"]
    if "закупка" in s or "поставки" in s:
        return ACTIVITY_EN["wholesale"]
    if "общепит" in s:
        return ACTIVITY_EN["catering"]
    return ACTIVITY_EN["retail"]


def load_egais(path=None) -> pd.DataFrame:
    """The Arkhangelsk licence extract, typed and normalised (2,100 rows)."""
    df = pd.read_csv(path or EGAIS_TSV, sep="\t", dtype=str).fillna("")

    for col in ("date_issued", "date_expires", "status_changed"):
        df[col] = df[col].map(parse_ru_date)

    df["status_en"] = df["status"].str.strip().str.lower().map(STATUS_EN).fillna("Other")
    df["is_active"] = df["status_en"] == "Active"
    df["activity_class"] = df["activity"].map(classify_activity)
    df["is_retail"] = df["activity_class"].isin(
        [ACTIVITY_EN["retail"], ACTIVITY_EN["catering"]])

    # Coordinates: keep only the ones inside the city box.  The rest are the
    # registry's own typos, and a map is the wrong place to argue with them.
    lat = pd.to_numeric(df["lat"], errors="coerce")
    lon = pd.to_numeric(df["lon"], errors="coerce")
    ok = df["coord_plausible"].eq("true")
    df["latitude"] = lat.where(ok)
    df["longitude"] = lon.where(ok)
    df["has_coords"] = df["latitude"].notna()

    sub = df["outlet_subsettlement"].str.lower()
    df["off_mainland"] = sub.str.contains("|".join(NOVAYA_ZEMLYA), na=False)
    df["street_key"] = df["outlet_street"].map(norm_street)
    df["issue_year"] = df["date_issued"].dt.year
    return df


def _v3_street_okrug(v3: pd.DataFrame) -> pd.Series:
    """street key -> the okrug most of that street's v3 objects sit in."""
    street = (v3["adress_orig"].fillna("").astype(str)
              .str.split(",").str[1].map(norm_street))
    t = pd.DataFrame({"street": street, "okrug": v3["okrug_key"]})
    t = t[(t["street"] != "") & (t["okrug"] != "Unknown")]
    return t.groupby("street")["okrug"].agg(lambda s: s.value_counts().idxmax())


def assign_okrug(eg: pd.DataFrame, v3: pd.DataFrame, max_m: float = 400.0):
    """Recover the okrug the registry does not record.

    Two routes, in order of trust: the nearest v3 object within ``max_m`` for
    rows with usable coordinates, then the modal okrug of the street for the
    rest.  Returns (okrug_key, okrug_source) so a report can always show how
    much of a result rests on the weaker route.
    """
    okrug = pd.Series("Unknown", index=eg.index, dtype=object)
    source = pd.Series("unassigned", index=eg.index, dtype=object)

    ref = v3.dropna(subset=["latitude", "longitude"])
    ref = ref[ref["okrug_key"] != "Unknown"]
    have = eg.index[eg["has_coords"]]
    if len(have) and len(ref):
        d = haversine_m(
            eg.loc[have, "latitude"].to_numpy()[:, None],
            eg.loc[have, "longitude"].to_numpy()[:, None],
            ref["latitude"].to_numpy()[None, :],
            ref["longitude"].to_numpy()[None, :],
        )
        near = d.argmin(axis=1)
        within = d[np.arange(len(have)), near] <= max_m
        hit = have[within]
        okrug.loc[hit] = ref["okrug_key"].to_numpy()[near[within]]
        source.loc[hit] = "coordinates"

    lookup = _v3_street_okrug(v3)
    todo = eg.index[(source == "unassigned") & (eg["street_key"] != "")]
    guess = eg.loc[todo, "street_key"].map(lookup)
    got = todo[guess.notna()]
    okrug.loc[got] = guess.loc[got]
    source.loc[got] = "street"

    return okrug, source
