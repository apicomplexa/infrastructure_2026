"""Build the four deliverable spreadsheets of the licence join.

    pixi run export-licences

Writes into `data/processed/deliverables/`:

* `v4_licences_alcohol_matched.xlsx` — alcohol rows holding a licence of their
  own (`licence_status` Active / Archived);
* `v4_licences_tobacco_matched.xlsx` — the same for the tobacco layer, which is
  matched against alcohol licences because no tobacco register exists;
* `v4_alcohol_no_licence.xlsx` — the alcohol rows with no licence of their own
  (Taken / Other chain / Other trade / Not in registry), carrying why, the
  Yandex Maps check and the best candidate the join refused;
* `v4_brand_aliases.xlsx` — the learned fascia -> holder pairs from
  `v4_brand_aliases.csv`, the pairs in use first, for a person to confirm or
  reject through `BRAND_REVIEW`.

The column plan and the legend are `arkhinfra.v4_export`; this script reads the
inputs, re-runs the join (`v4_egais.join()`) for the two fields the working
file does not keep, and guards the result.  **The guard is the point**: the re-run must reproduce
`data/processed/v4_licences/v4_licences.csv` row for row on the licence number and the
status, or nothing is written.  A deliverable that quietly disagrees with the
summary and the report is worse than no deliverable.

Needs `pixi run match-egais-v4` and `pixi run check-yandex` to have run first.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import v4_egais as mg  # noqa: E402
from arkhinfra import v4_export as ex  # noqa: E402
from arkhinfra.egais import load_egais  # noqa: E402
from arkhinfra.v4_common import load_v4  # noqa: E402

# The join is deterministic, so a re-run at the published settings must return
# what `match_egais_v4.py` wrote.  These two columns are the whole answer; if
# they agree, the fresh run may be trusted for the fields the CSV lacks.
GUARD = ["licence_status", "licence_no"]


def check(fresh: pd.DataFrame, stored: pd.DataFrame) -> None:
    if len(fresh) != len(stored):
        raise SystemExit(f"row count differs: re-run {len(fresh):,}, "
                         f"{ex.MATCHED_CSV.name} {len(stored):,} -- "
                         "re-run `pixi run match-egais-v4`")
    for col in GUARD:
        a = fresh[col].fillna("").astype(str).to_numpy()
        b = stored[col].fillna("").astype(str).to_numpy()
        bad = (a != b).sum()
        if bad:
            raise SystemExit(
                f"{bad:,} rows disagree with {ex.MATCHED_CSV.name} on {col!r}. "
                "The spreadsheets would not match the report -- re-run "
                "`pixi run match-egais-v4` first.")


def matched_file(d: pd.DataFrame, risk: str, path, title: str,
                 notes: list[str]) -> int:
    part = d[(d["risk"] == risk)
             & d["licence_status"].isin(mg.STATUS_OWN)].reset_index(drop=True)
    plan = ex.matched_plan()
    frame = ex.assemble(pd.concat([part, ex.derived(part)], axis=1), plan)
    frame = frame.sort_values(["Округ", "Объект: название", "Объект: адрес"])
    ex.write_sheet(path, frame, plan, title, notes)
    return len(frame)


def no_licence_file(d: pd.DataFrame, ya: pd.DataFrame, near: pd.DataFrame) -> int:
    keep = (d["risk"] == "Alcohol") & d["licence_status"].isin(mg.STATUS_NO_OWN)
    part = pd.concat([d[keep].reset_index(drop=True),
                      near[keep.to_numpy()].reset_index(drop=True)], axis=1)
    # The Yandex check is keyed on `site_key`; one answer per door, so a
    # duplicated key must not multiply the rows.
    ya = ya.drop_duplicates("site_key")
    n = len(part)
    part = part.merge(ya.drop(columns=[c for c in ya.columns
                                       if c in part.columns and c != "site_key"]),
                      on="site_key", how="left")
    assert len(part) == n, "the Yandex merge changed the row count"
    part = pd.concat([part, ex.derived(part), ex.derived_near(part)], axis=1)
    plan = ex.no_licence_plan()
    order = {v: i for i, v in enumerate(ex.OWN_STATUS_RU[s] for s in mg.STATUS_NO_OWN)}
    frame = ex.assemble(part, plan)
    frame = (frame.assign(_o=frame["Причина"].map(order))
             .sort_values(["_o", "Округ", "Название", "Адрес"]).drop(columns="_o"))
    ex.write_sheet(ex.OUT_NO_LICENCE, frame, plan,
                   "Алкоголь: объекты без собственной лицензии ФСРАР",
                   ex.NOTES_NO_LICENCE)
    return len(frame)


def brands_file() -> int:
    t = pd.read_csv(ex.BRANDS_CSV, sep=";", encoding="utf-8-sig",
                    dtype={"holder": str, "review": str, "review_reason": str})
    plan = ex.brands_plan()
    frame = ex.assemble(ex.brand_frame(t), plan)
    ex.write_sheet(ex.OUT_BRANDS, frame, plan,
                   "Пары «вывеска → держатель лицензии», выученные из данных",
                   ex.NOTES_BRANDS,
                   formats={"Доля (share)": "0.000", "Покрытие (cover)": "0.000",
                            "Базовая частота (base_rate)": "0.0000",
                            "Подъём (lift)": "0.00"})
    return len(frame)


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)

    stored = pd.read_csv(ex.MATCHED_CSV, sep=";", encoding="utf-8-sig",
                         low_memory=False)
    ya = pd.read_csv(ex.YANDEX_CSV, sep=";", encoding="utf-8-sig").fillna("")

    v4, eg = load_v4(), load_egais()
    extra = ex.rejoin(v4, eg)
    fresh = mg.enrich(v4, eg, result=extra["join"])
    check(fresh, stored)
    d = pd.concat([fresh, extra["accepted"]], axis=1)

    n_alc = matched_file(d, "Alcohol", ex.OUT_ALCOHOL,
                         "Алкоголь: объекты с найденной лицензией ФСРАР",
                         ex.NOTES_MATCHED)
    n_tob = matched_file(d, "Tobacco", ex.OUT_TOBACCO,
                         "Табак: объекты, по адресу которых найдена алкогольная лицензия",
                         ex.NOTES_TOBACCO_EXTRA + ex.NOTES_MATCHED)
    n_none = no_licence_file(d, ya, extra["near"])
    n_brand = brands_file()

    print(f"wrote {ex.OUT_ALCOHOL}  ({n_alc:,} rows)")
    print(f"wrote {ex.OUT_TOBACCO}  ({n_tob:,} rows)")
    print(f"wrote {ex.OUT_NO_LICENCE}  ({n_none:,} rows)")
    print(f"wrote {ex.OUT_BRANDS}  ({n_brand:,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
