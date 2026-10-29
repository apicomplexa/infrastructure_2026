"""Check every alcohol object of the fourth delivery that holds no licence of its own on Yandex Maps.

Reads `data/processed/v4_licences/v4_licences.csv` (written by `pixi run match-egais-v4`),
takes the alcohol rows whose `licence_status` is in `v4_egais.STATUS_NO_OWN` --
`Taken`, `Other chain`, `Other trade` and `Not in registry` -- and asks Yandex
Maps whether an organisation of that name stands at that address.  The status
travels into the output, because the four ask different questions of the
answer: for `Not in registry` a closed or absent door explains the empty
search, for `Taken` it may mean the stronger claimant is the only shop there.

    pixi run check-yandex                 # resume: only rows not yet cached
    pixi run check-yandex --limit 10      # a short trial run
    pixi run check-yandex --refresh       # re-read every row from Yandex

The cache holds the pages' *answers*, so a run with nothing left to read still
re-judges the whole queue: move a threshold in `v4_yandex`, run this again, and
the list is decided anew without a request.

The rule is `arkhinfra.v4_yandex`, and the why is in its docstring.  This is a
*third directory*, not a second registry: it says whether the door is on the
map, never whether alcohol is sold behind it.  A row that comes back `absent`
is a row whose evidence has thinned -- neither FSRAR nor Yandex knows it -- and
one that comes back `closed` is very likely to be a shop that has simply gone,
which is exactly why the licence search found nothing.

Yandex is asked once per object with a courtesy pause in between, and every
answer is cached, so a re-run is free and an interrupted run resumes.  Cyrillic
on a Windows console is mangled, so the tables go to a UTF-8 file beside the
CSV and stdout carries counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import v4_egais as mg  # noqa: E402
from arkhinfra import v4_yandex as y  # noqa: E402
from arkhinfra.paths import PROC_LICENCES  # noqa: E402

MATCHED = PROC_LICENCES / "v4_licences.csv"

# What the object was, then what Yandex said, then how it was decided.  The
# order is the reading order of a manual reviewer: the row, the verdict, the
# link, and only then the numbers that produced the verdict.
COLUMNS = ["site_key", "licence_status", "licence_claimed_by", "district_orig",
           "name_orig", "adress_orig", "type_orig",
           "latitude", "longitude", "providers",
           "yandex_status", "yandex_status_ru", "search_url",
           "yandex_name", "yandex_address", "yandex_url",
           "yandex_distance_m", "yandex_name_sim", "yandex_nearby",
           "address_found", "n_candidates", "og_title", "canonical",
           "checked", "note"]


def targets() -> pd.DataFrame:
    """The alcohol rows that hold no licence of their own -- and nothing else."""
    d = pd.read_csv(MATCHED, sep=";", encoding="utf-8-sig", low_memory=False)
    return d[(d["risk"] == "Alcohol")
             & d["licence_status"].isin(mg.STATUS_NO_OWN)].copy()


def summary(out: pd.DataFrame) -> str:
    by_status = out["yandex_status"].value_counts().reindex(
        y.STATUS_ORDER).fillna(0).astype(int)
    absent = out[out["yandex_status"] == y.STATUS_ABSENT]
    return "\n".join([
        "v4 alcohol rows with no FSRAR licence of their own, checked against Yandex Maps",
        "=" * 72,
        f"objects in the queue: {len(out):,}   pages read: "
        f"{int((out['checked'].astype(str) != '').sum()):,}   read on: "
        f"{', '.join(sorted({v for v in out['checked'].astype(str) if v})) or '--'}",
        f"accepted within {y.NEAR_M:.0f} m (generic fascia: {y.GENERIC_M:.0f} m) "
        f"and name similarity >= {y.NAME_MIN:.0f}",
        "",
        "present    an organisation of that name stands at that address",
        "closed     found, but Yandex marks it closed or temporarily shut",
        "ambiguous  the door is occupied, the export's own name is a trade",
        "           descriptor whole and cannot say whose door it is",
        "absent     nothing of that name at that door",
        "error      Yandex did not answer; the row claims nothing",
        "",
        by_status.to_string(),
        "",
        "by licence status (why the object holds no licence of its own):",
        pd.crosstab(out["licence_status"], out["yandex_status"], margins=True)
        .reindex(index=[s for s in mg.STATUS_NO_OWN if s in set(out["licence_status"])]
                 + ["All"], columns=[c for c in y.STATUS_ORDER if c in
                                     set(out["yandex_status"])] + ["All"])
        .fillna(0).astype(int).to_string(),
        "",
        "Taken        a licence of its trade is at the address, but that outlet",
        "             went to another object (licence_claimed_by)",
        "Other chain  only another known chain's licences at the address",
        "Other trade  only licences of the other trade at the address",
        "Not in registry  no licence at the address at all",
        "",
        "by object class:",
        pd.crosstab(out["type_orig"], out["yandex_status"]).to_string(),
        "",
        "by okrug:",
        pd.crosstab(out["district_orig"], out["yandex_status"]).to_string(),
        "",
        "=" * 72,
        "ABSENT ROWS, AND WHAT STANDS THERE INSTEAD",
        "=" * 72,
        (absent[["name_orig", "adress_orig", "yandex_nearby"]]
         .to_string(index=False) if len(absent) else "(none)"),
        "",
        "A Yandex hit is not a licence and a miss is not proof of absence: this",
        "is a third directory, read on one day, and it says only whether the",
        "door is on the map.",
        "",
    ])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--limit", type=int, default=0,
                   help="check at most N uncached rows (a trial run)")
    p.add_argument("--refresh", action="store_true",
                   help="ignore the cache and re-read every row")
    p.add_argument("--rejudge", action="store_true",
                   help="read nothing; re-decide the cached answers and rewrite "
                        "the CSV (use after moving a threshold)")
    p.add_argument("--sleep", type=float, nargs=2, default=(2.5, 4.5),
                   metavar=("MIN", "MAX"), help="courtesy pause between requests")
    args = p.parse_args(argv)

    rows = targets()
    cache = {} if args.refresh else y.load_cache()
    # One read per site: a site_key repeated in the queue is one door.
    todo = [] if args.rejudge else [
        r for _, r in rows.drop_duplicates("site_key").iterrows()
        if r["site_key"] not in cache]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(rows):,} alcohol rows with no licence of their own; "
          f"{int(rows['site_key'].isin(cache).sum()):,} cached, "
          f"{len(todo):,} to read now")

    for i, r in enumerate(todo, 1):
        try:
            rec = y.read(r["name_orig"], r["adress_orig"],
                         float(r["latitude"]), float(r["longitude"]),
                         sleep=tuple(args.sleep))
        except Exception as e:  # noqa: BLE001 -- one row must not end the run
            # A two-hour run over a throttling host meets failures `read()`
            # does not know to expect.
            rec = {"candidates": [], "note": f"{type(e).__name__}: {e}"}
        rec["site_key"] = r["site_key"]
        if rec["note"]:
            # Not cached: a failure is not an answer, and the next run should
            # ask again rather than inherit it.
            print(f"  [{i:>3}/{len(todo)}]  -- failed  {r['site_key']}  "
                  f"{rec['note']}", flush=True)
            continue
        y.append_cache(rec)
        cache[r["site_key"]] = rec
        print(f"  [{i:>3}/{len(todo)}] {len(rec['candidates']):>2} found  "
              f"{r['site_key']}", flush=True)

    # Every row is judged here, from the cache -- including the ones read on an
    # earlier run.  Moving a threshold re-decides the whole list for free.
    out = rows[["site_key", "licence_status", "licence_claimed_by", "district_orig",
                "name_orig", "adress_orig", "type_orig", "latitude", "longitude",
                "providers"]].copy()
    out["licence_claimed_by"] = out["licence_claimed_by"].fillna("")
    judged = []
    for _, r in rows.iterrows():
        rec = cache.get(r["site_key"], {})
        v = (y.verdict(rec, r["name_orig"], float(r["latitude"]),
                       float(r["longitude"])) if rec
             else {"status": y.STATUS_ERROR})
        judged.append({
            # The link stands even for a row never read: it is the query, and
            # a reader following it sees what this check would have seen.
            "search_url": y.search_url(r["name_orig"], r["adress_orig"],
                                       float(r["latitude"]), float(r["longitude"])),
            **rec, **v, "n_candidates": len(rec.get("candidates", []))})
    for col in ["status", "search_url", "yandex_name", "yandex_address",
                "yandex_url", "yandex_distance_m", "yandex_name_sim",
                "yandex_nearby", "address_found", "n_candidates", "og_title",
                "canonical", "checked", "note"]:
        out["yandex_status" if col == "status" else col] = [
            rec.get(col, "") for rec in judged]
    out["yandex_status_ru"] = out["yandex_status"].map(y.STATUS_RU).fillna("")
    out = out[COLUMNS]

    y.OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(y.OUT_CSV, sep=";", encoding="utf-8-sig", index=False)
    y.OUT_TXT.write_text(summary(out), encoding="utf-8")
    print(f"wrote {y.OUT_CSV}  ({len(out):,} rows x {out.shape[1]} columns)")
    print(f"wrote {y.OUT_TXT}")
    print(out["yandex_status"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
