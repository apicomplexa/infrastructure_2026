"""Add «Подтверждено» (two independent sources or more) to every final-delivery XLSX.

Reads each `data/raw_final/infrastructure_*.xlsx`, counts the sources of every
*object* -- OSM, 2GIS, Yandex Maps, the city administration's register when
`Arkh_admin` is filled -- and writes a copy of the workbook to
`data/processed/final_confirm/` with «Подтверждено» as column A, the evidence
appended after the contractor's columns, and a «Подтверждение» sheet saying how
to read it.  The raw files are never touched.

    pixi run confirm-final                     # offline: cached Yandex answers only
    pixi run confirm-final --yandex --limit 20 # a short trial of our own Yandex check
    pixi run confirm-final --yandex            # query every object Yandex could still decide
    pixi run confirm-final --yandex --all      # ... and every other object too (third opinion)
    pixi run confirm-final --yandex --city Новодвинск   # query one city only

Network use is opt-in (`--yandex`).  Without it the run re-judges the cache
and the contractor's own Yandex columns, so thresholds can be moved for free.
By default only objects whose verdict Yandex can still change are queried --
the ones with fewer than two sources besides Yandex and no name-matched
contractor hit.  The rule and its reasons are `arkhinfra.final_confirm`.

Cyrillic on a Windows console is mangled, so the tables go to a UTF-8 summary
beside the outputs and stdout carries counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import final_confirm as fc  # noqa: E402
from arkhinfra import v4_yandex as y  # noqa: E402
from arkhinfra import final_egais as fe  # noqa: E402
from arkhinfra.paths import EGAIS_FINAL_TSV, PROC_CONFIRM, final_files  # noqa: E402


def query_yandex(ob: pd.DataFrame, cache: dict, *, limit: int, sleep, everything: bool) -> None:
    """Read the pages still missing from the cache, appending as it goes."""
    want = ob if everything else ob[fc.needs_yandex(ob)]
    todo = [r for _, r in want.iterrows() if r["site_key"] not in cache]
    if limit:
        todo = todo[:limit]
    print(f"  Yandex: {len(want):,} objects in scope, "
          f"{int(want['site_key'].isin(cache).sum()):,} cached, {len(todo):,} to read now")
    for i, r in enumerate(todo, 1):
        try:
            rec = y.read(r["name"], r["address"], float(r["lat"]), float(r["lon"]),
                         sleep=tuple(sleep), city=r["city"])
        except Exception as e:  # noqa: BLE001 -- one row must not end the run
            rec = {"candidates": [], "note": f"{type(e).__name__}: {e}"}
        rec["site_key"] = r["site_key"]
        if rec["note"]:
            # A failure is not an answer: not cached, asked again next run.
            print(f"    [{i:>4}/{len(todo)}] -- failed  {rec['note']}", flush=True)
            continue
        y.append_cache(rec, fc.CACHE)
        cache[r["site_key"]] = rec
        print(f"    [{i:>4}/{len(todo)}] {len(rec['candidates']):>2} found", flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--yandex", action="store_true", help="query Yandex Maps for uncached objects")
    p.add_argument("--all", action="store_true",
                   help="with --yandex: query every object, not only the undecided ones")
    p.add_argument("--limit", type=int, default=0, help="read at most N pages per file")
    p.add_argument("--refresh", action="store_true", help="ignore the cache (with --yandex)")
    p.add_argument("--city", default="",
                   help="query Yandex for this city only (every file is still written)")
    p.add_argument("--sleep", type=float, nargs=2, default=(2.5, 4.5),
                   metavar=("MIN", "MAX"), help="courtesy pause between requests")
    args = p.parse_args(argv)

    cache = {} if args.refresh else y.load_cache(fc.CACHE)
    places = fc.load_overture()
    registry = fe.load_registry() if EGAIS_FINAL_TSV.exists() else None
    print("ЕГАИС: " + (f"{len(registry):,} licences" if registry is not None
                       else "no extract (pixi run parse-egais-final) -- source skipped"))
    print("Overture: " + (f"{len(places):,} places" if places is not None
                          else "no snapshot (pixi run fetch-overture) -- source skipped"))
    report, all_obj = [], []
    for path in final_files():
        df = fc.load(path)
        city = str(df["city"].iloc[0])
        print(f"{path.name}: {len(df):,} rows")
        ob = fc.overture(fc.relink(fc.objects(df)), places)
        if registry is not None:
            ob = ob.join(fe.match_catering(ob[["city", "name", "address", "lat", "lon"]], registry))
        if args.yandex and (not args.city or city == args.city):
            query_yandex(ob, cache, limit=args.limit, sleep=args.sleep, everything=args.all)
        ob = fc.decide(fc.own_yandex(ob, cache))
        rows = fc.to_rows(df, ob)
        summary = fc.summarise(ob, rows)
        dst = PROC_CONFIRM / path.name.replace(".xlsx", "_подтверждено.xlsx")
        fc.write_xlsx(path, dst, rows, summary)
        print(f"  wrote {dst.name}: {int(ob['confirmed'].sum()):,} of {len(ob):,} objects confirmed")
        report.append(f"== {path.name}\n" + "\n".join(f"{k}: {v}" for k, v in summary)
                      + "\n\nИсточники объекта (комбинации):\n"
                      + ob["sources"].replace("", "—").value_counts().to_string() + "\n")
        all_obj.append(ob.assign(file=path.name))

    if not all_obj:
        print("nothing matched")
        return 1
    obj = pd.concat(all_obj, ignore_index=True)
    obj.to_csv(fc.OBJECTS_CSV, sep=";", encoding="utf-8-sig", index=False)
    fc.SUMMARY_TXT.write_text("\n".join(report), encoding="utf-8")
    print(f"wrote {fc.OBJECTS_CSV}\nwrote {fc.SUMMARY_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
