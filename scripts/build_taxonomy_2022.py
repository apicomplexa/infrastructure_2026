"""Write the seven 2022-taxonomy flags for the whole city export.

    pixi run build-taxonomy

Produces `data/processed/taxonomy_2022/taxonomy_2022.csv` (7,263 rows: the export's own columns
plus seven `is_<class>` flags, seven `<class>_evidence` columns, `is_sport_retail`,
`n_classes` and `classes_2022`) and `taxonomy_2022_summary.txt` beside it.

The rule lives in `arkhinfra.taxonomy_2022`; this script only runs it, checks the
guard and reports what moved against `v3_common.recode_2022()`.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from arkhinfra import taxonomy_2022 as tx  # noqa: E402
from arkhinfra import v3_common as v3  # noqa: E402
from arkhinfra.paths import PROC_TAXONOMY  # noqa: E402

OUT_CSV = PROC_TAXONOMY / "taxonomy_2022.csv"
OUT_TXT = PROC_TAXONOMY / "taxonomy_2022_summary.txt"


def main() -> int:
    out = io.StringIO()

    def P(*a):
        print(*a, file=out)

    d = tx.load_export()
    old = v3.recode_2022(d)

    P("taxonomy_2022 -- seven independent 2022-class flags")
    P("source : %s" % tx.V3_CSV.name)
    P("rows   : %d" % len(d))
    P("")
    P("=== class counts, against the old single-label rule ===")
    P("%-14s %7s %7s %7s" % ("class", "old", "new", "delta"))
    for c in tx.CLASSES:
        new = int(d["is_" + c].sum())
        o = int((old == tx.CLASS_EN[c]).sum())
        P("%-14s %7d %7d %+7d" % (tx.CLASS_EN[c], o, new, new - o))
    P("%-14s %7d %7d" % ("no class", int((old == "Other (outside 2022 scheme)").sum()),
                         int((d.n_classes == 0).sum())))
    P("%-14s %7s %7d" % ("sport retail", "--", int(d.is_sport_retail.sum())))

    P("")
    P("=== what each class count rests on ===")
    P("%-14s %9s %7s %7s %7s" % ("class", "total", "category", "type", "name"))
    for c in tx.CLASSES:
        ev = d.loc[d["is_" + c], c + "_evidence"].value_counts()
        P("%-14s %9d %7d %7d %7d" % (
            tx.CLASS_EN[c], int(d["is_" + c].sum()),
            int(ev.get("category", 0)), int(ev.get("type", 0)), int(ev.get("name", 0))))
    P("")
    P("`name` evidence is the fascia alone -- the review queue is built from it.")

    P("")
    P("=== multi-label ===")
    vc = d.n_classes.value_counts().sort_index()
    for k, v in vc.items():
        P("  %d class(es): %5d" % (k, v))
    P("")
    for k, v in d.loc[d.n_classes >= 2, "classes_2022"].value_counts().items():
        P("  %-34s %4d" % (k, v))

    P("")
    P("=== by okrug (objects carrying the class; an object may carry several) ===")
    tab = pd.DataFrame({tx.CLASS_EN[c]: d.groupby("okrug_key")["is_" + c].sum()
                        for c in tx.CLASSES}).astype(int)
    tab["n_objects"] = d.groupby("okrug_key").size()
    P(tab.sort_values("n_objects", ascending=False).to_string())

    P("")
    P("=== guard ===")
    ok = True
    for name, check in (("assert_no_missed_types", lambda: tx.assert_no_missed_types(d, d)),
                        ("assert_override_is_narrow", lambda: tx.assert_override_is_narrow(d))):
        try:
            check()
            P("  %s: PASS" % name)
        except AssertionError as exc:
            P("  %s: FAIL" % name)
            P(str(exc))
            ok = False
    P("  category_orig override suppresses %d of %d rows (%.2f %%)"
      % (int(tx.overridden(d).sum()), len(d), 100 * tx.overridden(d).mean()))

    PROC_TAXONOMY.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT_CSV, sep=";", encoding="utf-8-sig", index=False)
    OUT_TXT.write_text(out.getvalue(), encoding="utf-8")
    print("wrote %s (%d rows) and %s" % (OUT_CSV.name, len(d), OUT_TXT.name))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
