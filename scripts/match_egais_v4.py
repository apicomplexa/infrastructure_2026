"""Attach FSRAR licence data to every fourth-delivery record.

Reads `data/raw_v4/` (both risk layers) and the licence extract
`data/processed/egais/egais_licences_arkhangelsk.tsv`, scores every
(v4 object x licence) pair with `arkhinfra.v4_egais`, and writes the v4 export
back out with the licence columns appended.

    pixi run match-egais-v4                       # both layers, one file
    pixi run match-egais-v4 --layer tobacco       # the tobacco layer alone
    pixi run match-egais-v4 --calibrate           # + the threshold ladder
    pixi run match-egais-v4 --no-exclusive        # switch one new rule off

Three rules decide which licence an object holds, beyond the score itself:
one licensed outlet goes to one shop (`Taken` for the others; records of one
shop share it), the licence must permit the object's trade unless the name
says the holder is the shop (`Other trade`), and the known brands must not
rule the pair out, in either direction (`Other chain`).  An archived licence is
quoted as the object's own only if the name agrees or nothing in force of its
trade stands at the address.  The brands are learned from the data
first and written to `v4_brand_aliases.csv` for review.

The registry licenses alcohol and has no tobacco class at all, so the tobacco
layer is matched against the same alcohol licences and the result is labelled
for what it is: `licence_evidence = probable`, indirect support resting on
alcohol and tobacco being sold across the same retail counter.  It is never
confirmation that the object sells tobacco.

Cyrillic on a Windows console is mangled, so every table goes to a UTF-8 report
file next to the CSV rather than to stdout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import v4_egais as m  # noqa: E402
from arkhinfra.egais import load_egais  # noqa: E402
from arkhinfra.paths import PROC_LICENCES  # noqa: E402
from arkhinfra.v4_common import load_v4  # noqa: E402

LAYERS = {"both": None, "alcohol": "Alcohol", "tobacco": "Tobacco"}
STEM = {"both": "v4_licences", "alcohol": "v4_alcohol_licences",
        "tobacco": "v4_tobacco_licences"}
BRANDS_CSV = PROC_LICENCES / "v4_brand_aliases.csv"

# Written first, so the licence answer is readable without scrolling past the
# 22 columns the delivery already had.
LEAD = ["risk", "evidence", "trade", "okrug_key", "category_2022",
        "name_orig", "adress_orig", "latitude", "longitude"]


def calibrate(v4: pd.DataFrame, eg: pd.DataFrame) -> list[str]:
    """The threshold ladder, and what a match looks like in each score band."""
    a, b = m.prepare_v4(v4), m.prepare_egais(eg)
    sc = m.score_all(a, b)
    score = np.nan_to_num(sc["score"], nan=-1.0)
    gated = np.where(sc["addr"] >= m.ADDR_MIN, score, -1.0)
    best_raw, best = score.max(axis=1), gated.max(axis=1)
    pick = gated.argmax(axis=1)

    out = ["", "=" * 72, "CALIBRATION", "=" * 72,
           f"pairs scored: {score.size:,}  "
           f"candidates admitted by the 100 m / address routes: "
           f"{int(np.isfinite(sc['score']).sum()):,}", "",
           "score floor | rows matched (unguarded) | rows matched (addr >= "
           f"{m.ADDR_MIN})"]
    for th in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.85):
        out.append(f"   >= {th:.2f}  |  {int((best_raw >= th).sum()):5d} "
                   f"({100 * (best_raw >= th).mean():4.1f} %)  |  "
                   f"{int((best >= th).sum()):5d} ({100 * (best >= th).mean():4.1f} %)")

    out += ["", "Best match per row, by score band (accepted rows only):"]
    rng = np.random.default_rng(0)
    for lo, hi in [(0.85, 1.01), (0.70, 0.85), (0.55, 0.70), (0.45, 0.55), (0.0, 0.45)]:
        idx = np.flatnonzero((best >= lo) & (best < hi))
        out.append(f"\n--- {lo:.2f}-{hi:.2f}  n = {len(idx)} ---")
        rows = []
        for i in rng.permutation(idx)[:10]:
            j = pick[i]
            rows.append({
                "score": round(float(sc["score"][i, j]), 3),
                "addr": round(float(sc["addr"][i, j]), 2),
                "street": round(float(sc["street"][i, j]), 2),
                "house": round(float(sc["house"][i, j]), 2),
                "name": round(float(sc["name"][i, j]), 2),
                "d_m": None if np.isnan(sc["distance"][i, j]) else int(sc["distance"][i, j]),
                "v4": f"{v4['name_orig'].iloc[i]} | {v4['adress_orig'].iloc[i]}",
                "licence": f"{m.norm_org_name(eg['org_name'].iloc[j])} | "
                           f"{eg['outlet_street'].iloc[j]} {eg['outlet_house'].iloc[j]}"
                           f" [{eg['status_en'].iloc[j]}]",
            })
        out.append(pd.DataFrame(rows).to_string(index=False) if rows else "  (none)")
    return out


def _layer_sections(out: pd.DataFrame, eg: pd.DataFrame) -> list[str]:
    """The per-layer tables, skipped when `--layer` left that layer out."""
    lines: list[str] = []
    alc = out[out["risk"] == "Alcohol"]
    tob = out[out["risk"] == "Tobacco"]

    if len(alc):
        lines += [
            "=" * 72,
            "ALCOHOL LAYER BY OKRUG (off-trade only, direct evidence)",
            "=" * 72,
            (alc[alc["trade"] == "off-trade"].groupby("okrug_key")["licence_status"]
             .value_counts().unstack(fill_value=0).to_string()),
            "",
        ]
    if len(tob):
        probable = tob["licence_evidence"] == m.EVIDENCE_PROBABLE
        lines += [
            "=" * 72,
            "TOBACCO LAYER -- PROBABLE CORROBORATION ONLY",
            "=" * 72,
            f"tobacco records: {len(tob):,}",
            f"probable (retail alcohol licence in force at the address): "
            f"{int(probable.sum()):,} ({100 * probable.mean():.1f} %)",
            f"weak (archived or non-retail licence only):               "
            f"{int((tob['licence_evidence'] == m.EVIDENCE_WEAK).sum()):,}",
            f"no licence of its own:                                    "
            f"{int((tob['licence_evidence'] == '').sum()):,}",
            "",
            "The inference: the registry has no tobacco class, so an object can",
            "only be reached through the alcohol licence at its address.  Where",
            "one is in force the outlet legally sells alcohol, and Russian retail",
            "sells alcohol and tobacco across the same counter -- which makes the",
            "tobacco tag likely, not verified.  Nothing in this repository can",
            "measure how often the two actually travel together, so the strength",
            "of the link is stated, never scored.",
            "",
            "by v4 evidence tier and okrug:",
            (tob.groupby(["evidence", "okrug_key"])["licence_evidence"]
             .apply(lambda s: s.replace("", "no match").value_counts())
             .unstack(fill_value=0).to_string()),
            "",
            "by type of tobacco object:",
            (tob.groupby("type_en")["licence_evidence"]
             .apply(lambda s: s.replace("", "no match").value_counts())
             .unstack(fill_value=0).to_string()),
            "",
        ]
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--accept", type=float, default=m.ACCEPT,
                    help=f"combined-score floor (default {m.ACCEPT})")
    ap.add_argument("--addr-min", type=float, default=m.ADDR_MIN,
                    help=f"address-term floor; 0 disables the toponym gate "
                         f"(default {m.ADDR_MIN})")
    ap.add_argument("--max-m", type=float, default=m.MAX_M,
                    help=f"distance cut in metres (default {m.MAX_M:.0f})")
    ap.add_argument("--weights", type=float, nargs=3,
                    metavar=("W_ADDR", "W_NAME", "W_DIST"),
                    default=[m.W_ADDR, m.W_NAME, m.W_DIST])
    ap.add_argument("--layer", choices=tuple(LAYERS), default="both",
                    help="which risk layer to write out (default both)")
    ap.add_argument("--calibrate", action="store_true",
                    help="append the threshold ladder and banded samples")
    ap.add_argument("--no-learn", action="store_true",
                    help="do not learn fascia -> holder pairs from the data")
    ap.add_argument("--no-exclusive", action="store_true",
                    help="let several objects quote one licensed outlet (the old rule)")
    ap.add_argument("--no-brand-rule", action="store_true",
                    help="let an object take a licence held by another known chain")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    out_csv = args.out or PROC_LICENCES / f"{STEM[args.layer]}.csv"
    out_txt = PROC_LICENCES / f"{STEM[args.layer]}_summary.txt"

    eg = load_egais()
    v4 = load_v4()
    # Both layers are always scored: the join is row-by-row, and scoring the
    # whole export keeps `--layer` a view of one result rather than a different
    # one.  The reverse-coverage table below then reads as "of the registry,
    # what this layer accounts for".
    joined = m.join(v4, eg, accept=args.accept, addr_min=args.addr_min,
                    max_m=args.max_m, w=tuple(args.weights),
                    learn=not args.no_learn, exclusive=not args.no_exclusive,
                    brand_rule=not args.no_brand_rule)
    out = m.enrich(v4, eg, result=joined)
    PROC_LICENCES.mkdir(parents=True, exist_ok=True)
    if joined.brands is not None and args.layer == "both":
        joined.brands.table.to_csv(BRANDS_CSV, sep=";", encoding="utf-8-sig", index=False)
    if LAYERS[args.layer]:
        out = out[out["risk"] == LAYERS[args.layer]].reset_index(drop=True)

    cols = LEAD + [c for c in v4.columns if c not in LEAD] + m.MATCH_FIELDS \
        + list(m.LICENCE_FIELDS)
    out = out[[c for c in dict.fromkeys(cols) if c in out.columns]]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, sep=";", encoding="utf-8-sig", index=False)

    n = len(out)
    matched = out["licence_status"].isin(m.STATUS_OWN)
    rules = [name for flag, name in ((args.no_learn, "brand learning"),
                                     (args.no_exclusive, "one outlet per object"),
                                     (args.no_brand_rule, "brand conflict rule"))
             if flag]
    lines = [
        "v4 x FSRAR licence registry",
        "=" * 72,
        f"weights: address {args.weights[0]:.2f} / name {args.weights[1]:.2f} / "
        f"distance {args.weights[2]:.2f};  radius {args.max_m:.0f} m;  "
        f"score >= {args.accept:.2f};  address >= {args.addr_min:.2f}",
        f"v4 records: {n:,}   licences in the extract: {len(eg):,} "
        f"({int(eg['is_active'].sum()):,} in force)",
        f"rules switched OFF for this run: {', '.join(rules)}" if rules
        else "all rules on: one outlet per object, trade compatibility, brand conflict",
        "",
        f"holding a licence of their own: {int(matched.sum()):,} ({100 * matched.mean():.1f} %)",
        f"a licence at the address at all:  "
        f"{int((out['licence_n_matched'] > 0).sum()):,} "
        f"({100 * (out['licence_n_matched'] > 0).mean():.1f} %)",
        "",
        # The headline is a count of alcohol licences whichever layer it covers.
        # Said once here, so no one reads it as a tobacco verification rate.
        *(["Tobacco rows are matched against alcohol licences -- the registry has",
           "no tobacco class -- so their match is PROBABLE corroboration only.",
           ""] if (out["risk"] == "Tobacco").any() else []),
        out["licence_status"].value_counts().reindex(m.STATUS_ORDER, fill_value=0)
           .to_string(),
        "",
        "Active / Archived  the object holds this licence itself",
        "Taken              a licence of its trade is at the address, but that outlet",
        "                   went to another shop with the stronger claim",
        "                   (licence_claimed_by); one outlet is one counter, and the",
        "                   records of one shop, in either file, share it",
        "Other chain        the known brands rule every licence here out: the object",
        "                   is a known chain and none is its own (a Бристоль where",
        "                   only Тандер holds one), or each licence is a known",
        "                   chain's and the object is not that chain",
        "Other trade        only licences of the other trade at the address (a shop",
        "                   licence where the object is a bar, or the reverse)",
        "Not in registry    no licence at the address at all",
        "",
        "where the chosen pair's name term came from (own licences only):",
        out.loc[matched, "licence_name_basis"].value_counts().to_string(),
        "",
        "by match route / address level:",
        out.loc[matched].groupby(["licence_match_method", "licence_match_level"])
           .size().to_string(),
        "",
        "=" * 72,
        "WHAT THE LICENCE IS EVIDENCE OF",
        "=" * 72,
        m.evidence_summary(out).to_string(),
        "",
        "direct    the registry licenses the very product the row is tagged with",
        "          -- alcohol rows only.",
        "probable  a retail alcohol licence is in force at the address and the",
        "          row is tagged tobacco.  There is no tobacco registry to match",
        "          against; alcohol and tobacco are sold across the same retail",
        "          counter, so this is indirect support for the tobacco tag and",
        "          never confirmation that the object sells tobacco.",
        "weak      matched, but only to an archived or non-retail licence, which",
        "          carries no co-sale inference at all.",
        "",
        "The two columns count different claims.  Do not add them together.",
        "",
        "=" * 72,
        "BY LAYER, EVIDENCE TIER AND TRADE TYPE",
        "=" * 72,
        m.summary(out).to_string(),
        "",
    ]
    lines += _layer_sections(out, eg)
    if joined.brands is not None:
        br = joined.brands
        t = br.table
        lines += [
            "=" * 72,
            "FASCIA -> HOLDER PAIRS LEARNED FROM THE DATA (alcohol layer)",
            "=" * 72,
            f"rounds: {br.iterations}  "
            + ("converged" if br.cycle == 0 else
               f"stopped on a two-round cycle; {br.oscillating} objects alternate "
               "and vote for nothing" if br.cycle == 2 else "stopped at max_iter"),
            f"pairs in use: {int(t['used'].sum())} over "
            f"{t.loc[t['used'], 'fascia'].nunique()} fascias "
            f"(accepted by the thresholds: {int(t['accepted'].sum())}; "
            f"overruled by BRAND_REVIEW: {int((t['review'] != '').sum())})",
            "",
            t[t["used"]][["fascia", "holder", "holder_name", "fascia_sites",
                          "sites_assigned", "share", "lift", "franchise"]]
             .to_string(index=False),
            "",
            "A learned pair is a hypothesis with a count behind it, not a fact:",
            f"the full table, near misses included, is {BRANDS_CSV.name}.",
            "",
        ]
    lines += [
        "=" * 72,
        "REVERSE: HOW MUCH OF THE REGISTRY THIS EXPORT ACCOUNTS FOR",
        "=" * 72,
        m.reverse_coverage(out, eg).to_string(index=False),
    ]
    if args.calibrate:
        lines += calibrate(v4, eg)

    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_csv}  ({n:,} rows x {out.shape[1]} columns)")
    print(f"wrote {out_txt}")
    print(f"matched: {int(matched.sum()):,} / {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
