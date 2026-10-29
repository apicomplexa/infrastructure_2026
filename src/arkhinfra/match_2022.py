"""Independent 2022 <-> 2026(v3) record matcher.

This is a re-implementation, not a re-reading of the contractor's comparison
workbook.  It takes the 2022 object list as the benchmark and asks how much of
it the third-delivery export reproduces, so that the numbers in
analysis/v3/eda-v3-validation.qmd stand on their own.

Method (settled with the analyst, see the report's "Method" section):

    block   candidate v3 records within RADIUS_M metres (haversine)
    score   fuzzy name similarity over normalised names
    rank    (name similarity, address similarity, -distance)
    tier    >= EXACT_THR            -> exact
            >= PROBABLE_THR         -> probable
            candidates but no name  -> gps_only
            no candidate in radius  -> unmatched

Name similarity uses rapidfuzz's WRatio rather than token_set_ratio.
token_set_ratio returns 1.0 whenever one name's token set is a subset of the
other's, so "Magnit" and "Magnit Cosmetic" score a perfect match; WRatio blends
exact, partial and token comparisons with a length penalty and does not.
token_set_ratio is still computed and stored so the choice can be audited.

Run standalone with `pixi run match-2022`; writes to data/processed/match_2022/.
"""
from __future__ import annotations


import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from . import v3_common as c

RADIUS_M = 50.0
EXACT_THR = 0.90
PROBABLE_THR = 0.75

# Generous bounding box for the city; used only to flag broken coordinates.
BBOX_LAT = (64.30, 64.80)
BBOX_LON = (40.25, 40.95)

TIER_ORDER = ["exact", "probable", "gps_only", "unmatched"]

# The contractor's own settings, recorded in the v2 workbook's Сводка sheet.
VENDOR_RADIUS_M = 60.0
VENDOR_NAME_THR = 0.86


def normalise_vendor(d: pd.DataFrame) -> pd.DataFrame:
    """Put the contractor's 'Документ 1' on the canonical column schema.

    The original (pre-correction) coordinates are used deliberately: the
    contractor overwrote one record's coordinates with those of the object it
    matched, and matching on a coordinate derived from the match would be
    circular.  Only one row is affected, but the principle costs nothing.
    """
    ren = {
        "Категория": "category_orig",
        "Тип": "type_orig",
        "Организация": "name_orig",
        "Город": "city_orig",
        "Округ/район": "district_orig",
        "Адрес": "adress_orig",
        "Исходная широта": "latitude",
        "Исходная долгота": "longitude",
    }
    out = d.rename(columns=ren).copy()
    out["okrug_key"] = out["district_orig"].map(c.norm_okrug)
    out["category_2022"] = c.recode_2022(out)
    return out


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_name"] = out["name_orig"].map(c.norm_name)
    out["_addr"] = out["adress_orig"].map(c.norm_address)
    out["_gps_ok"] = (out["latitude"].between(*BBOX_LAT)
                      & out["longitude"].between(*BBOX_LON))
    return out


def match(etalon: pd.DataFrame,
          target: pd.DataFrame,
          radius_m: float = RADIUS_M,
          exact_thr: float = EXACT_THR,
          probable_thr: float = PROBABLE_THR,
          chunk: int = 256) -> pd.DataFrame:
    """One row per etalon record, describing its best target match."""
    e = _prep(etalon)
    t = _prep(target)

    t_lat = t["latitude"].to_numpy(float)
    t_lon = t["longitude"].to_numpy(float)
    t_name = t["_name"].tolist()
    t_addr = t["_addr"].tolist()

    rows = []
    for start in range(0, len(e), chunk):
        block = e.iloc[start:start + chunk]
        dist = c.haversine_m(
            block["latitude"].to_numpy(float)[:, None],
            block["longitude"].to_numpy(float)[:, None],
            t_lat[None, :], t_lon[None, :],
        )
        for local_i, (idx, rec) in enumerate(block.iterrows()):
            d_row = dist[local_i]
            cand = np.flatnonzero(d_row <= radius_m) if rec["_gps_ok"] else np.array([], dtype=int)
            base = {
                "etalon_index": idx,
                "n_candidates": int(cand.size),
                "gps_ok": bool(rec["_gps_ok"]),
            }
            if cand.size == 0:
                rows.append({**base, "tier": "unmatched", "name_sim": np.nan,
                             "name_sim_tokenset": np.nan, "addr_sim": np.nan,
                             "distance_m": np.nan, "target_index": pd.NA})
                continue

            nm = rec["_name"]
            ad = rec["_addr"]
            best = None
            for j in cand:
                ns = fuzz.WRatio(nm, t_name[j]) / 100.0 if nm and t_name[j] else 0.0
                as_ = fuzz.WRatio(ad, t_addr[j]) / 100.0 if ad and t_addr[j] else 0.0
                key = (ns, as_, -d_row[j])
                if best is None or key > best[0]:
                    best = (key, j, ns, as_)
            _, j, ns, as_ = best
            tier = ("exact" if ns >= exact_thr
                    else "probable" if ns >= probable_thr
                    else "gps_only")
            rows.append({
                **base, "tier": tier, "name_sim": ns,
                "name_sim_tokenset": (fuzz.token_set_ratio(nm, t_name[j]) / 100.0
                                      if nm and t_name[j] else np.nan),
                "addr_sim": as_, "distance_m": float(d_row[j]),
                "target_index": t.index[j],
            })

    res = pd.DataFrame(rows).set_index("etalon_index")
    res["tier"] = pd.Categorical(res["tier"], categories=TIER_ORDER, ordered=True)
    return res


def attach(etalon: pd.DataFrame, res: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    """Etalon record + its match outcome + the matched target's key fields."""
    out = etalon.join(res)
    tgt = target[["name_orig", "adress_orig", "okrug_key", "verification_status"]]
    tgt = tgt.rename(columns=lambda s: "v3_" + s)
    return out.join(tgt, on="target_index")


def recall(res: pd.DataFrame) -> dict:
    n = len(res)
    counts = res["tier"].value_counts().reindex(TIER_ORDER, fill_value=0)
    found = int(counts["exact"] + counts["probable"])
    return {
        "n": n,
        "exact": int(counts["exact"]),
        "probable": int(counts["probable"]),
        "gps_only": int(counts["gps_only"]),
        "unmatched": int(counts["unmatched"]),
        "found": found,
        "recall_pct": round(100 * found / n, 1) if n else np.nan,
    }


def sensitivity(etalon: pd.DataFrame, target: pd.DataFrame,
                radii=(50, 100, 150), thresholds=(0.75, 0.85, 0.90)) -> pd.DataFrame:
    """Headline recall across the radius x name-threshold grid.

    The matcher runs once per radius; the thresholds are then applied to the
    stored name similarities, which is equivalent and far cheaper than a full
    re-run per cell.
    """
    out = []
    for r in radii:
        res = match(etalon, target, radius_m=float(r), exact_thr=0.0, probable_thr=0.0)
        ns = res["name_sim"]
        for thr in thresholds:
            found = int((ns >= thr).sum())
            out.append({"radius_m": r, "name_threshold": thr,
                        "found": found, "n": len(res),
                        "recall_pct": round(100 * found / len(res), 1)})
    return pd.DataFrame(out)


def reverse_coverage(target: pd.DataFrame, res: pd.DataFrame) -> pd.Series:
    """Label each target record as reproduced-from-2022 or new."""
    hit = res.loc[res["tier"].isin(["exact", "probable"]), "target_index"].dropna()
    lab = pd.Series("New in v3", index=target.index, dtype=object)
    lab.loc[lab.index.isin(set(hit))] = "Reproduced from 2022"
    return lab


def main() -> None:
    c.PROC_MATCH_2022.mkdir(parents=True, exist_ok=True)
    v3 = c.load_v3()

    local = c.load_ref_2022_local()
    vendor = normalise_vendor(c.load_ref_2022_vendor())

    res_local = match(local, v3)
    res_vendor = match(vendor, v3)

    attach(local, res_local, v3).to_csv(
        c.PROC_MATCH_2022 / "match_2022_local.csv", sep=";", encoding="utf-8-sig", index=False)
    attach(vendor, res_vendor, v3).to_csv(
        c.PROC_MATCH_2022 / "match_2022_vendor.csv", sep=";", encoding="utf-8-sig", index=False)
    sensitivity(local, v3).to_csv(
        c.PROC_MATCH_2022 / "match_2022_sensitivity.csv", sep=";", encoding="utf-8-sig", index=False)

    lines = [
        f"radius={RADIUS_M} m, exact>={EXACT_THR}, probable>={PROBABLE_THR}",
        f"local etalon  : {recall(res_local)}",
        f"vendor etalon : {recall(res_vendor)}",
    ]
    (c.PROC_MATCH_2022 / "match_2022_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
