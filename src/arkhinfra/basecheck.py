"""Matching of export_base_688669 against the 2026 export and the 2022 benchmark.

Kept deliberately separate from arkhinfra/v3_common.py.  The normalisers here are
stricter than the ones the earlier reports use, and importing them into
v3_common would silently change what analysis/v3/eda-v3.qmd and
analysis/v3/eda-v3-validation.qmd produce on their next render.  Nothing in this
module is used by those two reports; only analysis/v3/eda-v3-basecheck.qmd imports
it.

Why the stricter normalisers exist -- three defects make a naive join understate
the overlap by roughly an order of magnitude:

1.  45.8% of export_base addresses carry a long administrative prefix
    ("Архангельская область, Архангельск городской округ, Архангельск, ...").
    v3_common.norm_address strips the bare word "Архангельск" with a word
    boundary, which does not match "Архангельская", so the prefix survives
    normalisation and those rows can never join.
2.  Exact string equality on names fails on the directory's habit of appending a
    trade descriptor -- "Фудзи" against "Фудзи, торговый центр".
3.  Blocking on the address alone drops every object the two sources address
    differently, even when they sit metres apart.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from . import v3_common as c

RADIUS_M = 100.0        # export_base coordinates are 3-decimal (approx +-55 m)
STRONG = 0.90           # defensible name-similarity floor, see the report
WEAK = 0.85             # retained only to show where false positives start

# Settlement / administrative words that carry no street-level information.
_SETTLE = (r"(?:пос|поселок|мкр|м-н|микрорайон|дер|деревня|село|ст-ца|"
           r"лесной порт|городской округ)")

# Trade descriptors the directory appends to a business name.  Dropping them
# stops "Апрель, аптека" and "Аптечный огород, аптека" scoring 0.85 on the
# shared suffix alone.
_GENERIC = {
    "аптека", "аптечный", "кафе", "бар", "ресторан", "салон", "красоты",
    "центр", "клиника", "стоматология", "детский", "сад", "школа", "магазин",
    "маркет", "студия", "мини", "отель", "торговый", "продуктовый",
    "спортивный", "клуб", "кофейня", "пекарня", "парикмахерская", "компания",
    "сеть", "служба", "доставки", "оптово", "розничная",
}


def norm_address(v) -> str:
    """As v3_common.norm_address, but also removes the administrative prefix."""
    if pd.isna(v):
        return ""
    s = str(v).lower().replace(chr(0x451), "е")
    s = re.sub(r"^\s*\d{6}\s*", " ", s)
    s = re.sub(r"\bархангельская\s+область\b", " ", s)
    s = re.sub(r"\bархангельск\w*\s+городской\s+округ\b", " ", s)
    s = re.sub(r"\bархангельск\b,?", " ", s)
    s = re.sub("[" + chr(0xAB) + chr(0xBB) + chr(0x22) + chr(0x27) + chr(0x60) + "]", " ", s)
    s = re.sub(r"\b" + _SETTLE + r"\b\.?", " ", s)
    s = re.sub(r"\b(?:улица|ул|проспект|пр|пр-кт|переулок|пер|набережная|наб|"
               r"шоссе|ш|площадь|пл|проезд|бульвар|б-р|тракт)\b\.?", " ", s)
    s = re.sub(r"\b(?:дом|д|корпус|корп|к|строение|стр|ст|литера|лит)\b\.?", " ", s)
    return " ".join(re.sub(r"[^0-9a-zа-я]+", " ", s).split()).strip()


def norm_name(v) -> str:
    """As v3_common.norm_name, with trade descriptors removed as well."""
    base = c.norm_name(v)
    kept = [t for t in base.split() if t not in _GENERIC]
    return " ".join(kept) if kept else base


def prepare_base() -> pd.DataFrame:
    eb = c.load_export_base()
    eb["_name"] = eb["Название компании"].map(norm_name)
    eb["_addr"] = eb["Адрес компании"].map(norm_address)
    return eb


def prepare_target(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_name"] = out["name_orig"].map(norm_name)
    out["_addr"] = out["adress_orig"].map(norm_address)
    return out


def match_geo(target: pd.DataFrame, eb: pd.DataFrame,
              radius_m: float = RADIUS_M, chunk: int = 400) -> pd.DataFrame:
    """Best export_base counterpart for each target row, blocked on distance.

    One row per target record: the similarity of the best-scoring directory
    entry within the radius, that entry's index, and how far away it is.
    """
    ebc = eb.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    elat = ebc["latitude"].to_numpy(float)
    elon = ebc["longitude"].to_numpy(float)
    enames = ebc["_name"].tolist()

    tlat = target["latitude"].to_numpy(float)
    tlon = target["longitude"].to_numpy(float)
    tnames = target["_name"].tolist()

    score = np.full(len(target), np.nan)
    who = np.full(len(target), -1, dtype=int)
    dist = np.full(len(target), np.nan)
    near = np.zeros(len(target), dtype=bool)

    for i in range(0, len(target), chunk):
        block = slice(i, i + chunk)
        d = c.haversine_m(tlat[block][:, None], tlon[block][:, None],
                          elat[None, :], elon[None, :])
        for j in range(d.shape[0]):
            idx = i + j
            cand = np.flatnonzero(d[j] <= radius_m)
            near[idx] = cand.size > 0
            name = tnames[idx]
            if not cand.size or not name:
                continue
            best = max(((fuzz.WRatio(name, enames[k]) / 100.0, k, d[j][k])
                        for k in cand if enames[k]), default=None)
            if best is not None:
                score[idx], who[idx], dist[idx] = best

    return pd.DataFrame({"near": near, "name_sim": score,
                         "eb_row": who, "distance_m": dist},
                        index=target.index)


def method_ladder(target: pd.DataFrame, eb: pd.DataFrame, geo: pd.DataFrame) -> pd.DataFrame:
    """The same question asked six ways, from the naive join to the geo one."""
    n = len(target)

    eb_old_keys = set(zip(eb["Название компании"].map(c.norm_name),
                          eb["Адрес компании"].map(c.norm_address)))
    t_old_keys = list(zip(target["name_orig"].map(c.norm_name),
                          target["adress_orig"].map(c.norm_address)))
    naive = sum(k in eb_old_keys for k in t_old_keys)

    eb_fix_keys = set(zip(eb["Название компании"].map(c.norm_name), eb["_addr"]))
    t_fix_keys = list(zip(target["name_orig"].map(c.norm_name),
                          target["adress_orig"].map(norm_address)))
    fixed_addr = sum(k in eb_fix_keys for k in t_fix_keys)

    by_addr = eb[eb["_addr"] != ""].groupby("_addr")["_name"].apply(list).to_dict()
    addr_fuzzy = 0
    for name, addr in zip(target["_name"], target["_addr"]):
        cands = by_addr.get(addr)
        if cands and name:
            if max((fuzz.WRatio(name, x) / 100.0 for x in cands if x), default=0) >= STRONG:
                addr_fuzzy += 1

    rows = [
        ("1. Exact name + address, normalisers as shipped", naive),
        ("2. Exact name + address, administrative prefix removed", fixed_addr),
        (f"3. Address block, fuzzy name >= {STRONG:.2f}", addr_fuzzy),
        (f"4. Distance block {RADIUS_M:.0f} m, exact name", int((geo["name_sim"] >= 1.0).sum())),
        (f"5. Distance block {RADIUS_M:.0f} m, fuzzy name >= {STRONG:.2f}", int((geo["name_sim"] >= STRONG).sum())),
        (f"6. Distance block {RADIUS_M:.0f} m, fuzzy name >= {WEAK:.2f}", int((geo["name_sim"] >= WEAK).sum())),
    ]
    out = pd.DataFrame(rows, columns=["Method", "Corroborated"])
    out["% of target"] = (100 * out["Corroborated"] / n).map("{:.1f}".format)
    out["Corroborated"] = out["Corroborated"].map("{:,}".format)
    return out


def main() -> None:
    eb = prepare_base()
    v3 = c.load_v3()
    three = prepare_target(v3[v3["okrug_key"].isin(c.OKRUGS_2022)])
    geo = match_geo(three, eb)
    print(method_ladder(three, eb, geo).to_string(index=False))


if __name__ == "__main__":
    main()
