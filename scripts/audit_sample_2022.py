"""Draw the approved 600-object manual audit sample over the 2022 taxonomy.

    pixi run python scripts/audit_sample_2022.py

Writes `data/processed/taxonomy_2022_audit_sample.csv` (600 rows, one per
object, seven empty `true_<class>` columns for the labeller) and
`taxonomy_2022_audit_sample_summary.txt` beside it.  The labelling rules live in
`docs/taxonomy_2022_audit_protocol.md` and must be read before labelling starts;
this script refuses to run if that file does not record the same seed.

**Why an audit at all.**  `docs/classifier_design.md` §10.2 establishes that the
rule over the 2022 taxonomy has only ever been scored on the 1,133 export rows
that link to the 2022 benchmark -- 15.6 % of the city, and its easy end (rule
accuracy 0.925 on `exact` links against 0.700 on `probable`).  §10.3 then shows
that where the rule fails it fails on the other 84 %, and definitionally rather
than statistically: a spelling hole (D1), a category test that swept in 63
saunas (D2), a priority order that hid 35 groceries (D3).  No benchmark in this
repository reaches those rows.  A manual audit is the only instrument that does.

**Why these strata, and not §7's.**  §7 stratified on model probabilities
(`p_grocery >= 0.5` and so on).  There is no model -- §9 and §10.4 conclude one
cannot be built on these inputs -- so §10.5 replaces that stratification with one
over the *rule's* output on the whole city.  The six cells below are the places
the rule's evidence is weakest or its definitions most contested, plus the city
sample that makes the rest reweightable.

**Why stratum 6 is not optional.**  Cells A-E are purposive: they oversample the
rule's weak points by factors of 1 to 25, so a rate measured inside them is a
rate for that cell and nothing more.  Only a sample drawn with known, uniform
inclusion probability over all 7,263 objects turns those cell rates back into
city numbers, and only an okrug-proportional draw puts a guaranteed share of it
(~23 of 100) into the six okrugs no benchmark covers.  Without it the audit
would produce six unconnected numbers and no city-level statement at all.

**How the two designs compose.**  The city sample is drawn first, from all 7,263
objects.  Each purposive cell is then topped up from what the city sample did not
already take.  The union of (city-sample rows landing in cell *h*) and (fresh
draws from cell *h*) is an exactly uniform sample of cell *h* of the realised
size -- the conditional argument is in the summary file -- so one weight suffices:

    weight = cell_N / cell_n

over all 600 rows.  The six cells partition the city, so these weights sum to
7,263 exactly and a city rate is a weighted mean over the whole file.  The 100
city-sample rows additionally carry `srs_weight` (N_okrug / n_okrug, also summing
to 7,263), which estimates the same city rate on its own, from a design with no
purposive component.  The two estimates disagreeing is itself a finding.

Cell F is reached only through the city sample -- it is the part of the city
where the rule's evidence is strongest (a `category_orig` or `type_orig` value
says the class outright, one class only, in an okrug the 2022 benchmark covers),
which is precisely the slice §10.1 already scores at P 0.89-1.00.  Spending
purposive effort there would buy the least.

**Why cell B is the export's self-contradiction and not the multi-label cell.**
§7 and the first cut of this script stratified on co-membership.  The rule no
longer produces enough of it to stratify on: `classify()` lets an exact
`category_orig` match outrank a class inferred from `type_orig` or the fascia,
and the shipped multi-label count is **7 objects in 7,263** -- five of them
spurious `Industrial` fascia hits on «мясокомбинат» and «Хладокомбинат».  Seven
objects are a census, not a stratum, and they are all picked up by cell A.

What the override exposed instead is a defect class nobody has measured: the
export's two descriptive fields disagree with each other.  Cell B is a **census
of all 115 such objects**, in two kinds:

- **42 `conflict_class`** -- `category_orig` names one 2022 class while
  `type_orig` or the fascia implies a different one.  35 are the
  `Точки продажи табака` × `Продуктовый магазин` rows; the rest are
  Общепит×Industrial (3), Общепит×Alcohol (1), Медицинские×Industrial (1),
  Медицинские×Sport (1), Спортивные×Industrial (1).
- **73 `conflict_uncorroborated`** -- `category_orig` asserts a class and nothing
  else in the record supports it: 60 rows whose `type_orig` merely repeats
  `Общепит`, and 13 `Социально-оздоровительный объект` under
  `Реабилитация и профилактика`, which may be care homes rather than medical
  organisations.

A census means the whole defect class is measured exactly, with no sampling
error, and the audit answers the question the override answered by assertion:
**when the two fields disagree, which one is right?**  Every sampled row carries
`conflict_kind` and `conflict_note` saying what disagrees with what.
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from arkhinfra import taxonomy_2022 as tx  # noqa: E402
from arkhinfra import v3_common as v3  # noqa: E402
from arkhinfra.paths import DOCS, PROC  # noqa: E402

OUT_CSV = PROC / "taxonomy_2022_audit_sample.csv"
OUT_TXT = PROC / "taxonomy_2022_audit_sample_summary.txt"
PROTOCOL = DOCS / "taxonomy_2022_audit_protocol.md"

# Fixed once.  Changing it redraws the sample and invalidates any labelling
# already done against the old draw, so it is also written into the protocol and
# checked below.
SEED = 20260915

N_TOTAL = 600          # §7's approved budget, ~20 h at 2 min/object
N_SRS = 100            # stratum 6, drawn proportionally to okrug
N_SPORT = 100          # cell C -- ±9 pp at p = 0.5 on a cell of 352
N_UNBENCH = 120        # cell D -- the six okrugs no benchmark reaches
DOUBLE_LABEL_FRAC = 0.10   # §7: 60 objects for Cohen's kappa

# The three okrugs the 2022 study covers.  Everything else has no object-level
# benchmark of any kind (CLAUDE.md, "Known data caveats").
BENCHMARKED = ("Lomonosovsky", "Oktyabrsky", "Maiskaya Gorka")

CELLS = ["A_name_evidence", "B_category_type_conflict", "C_sport",
         "D_unbenchmarked_okrug", "E_no_class_benchmarked",
         "F_residual_classified"]

CELL_WHY = {
    "A_name_evidence":
        "the class rests on the fascia string alone -- the whole Industrial "
        "class is here, documented to contain a hostel and a jewellery shop, "
        "and so are all 7 objects the rule gives two classes",
    "B_category_type_conflict":
        "the export's own two descriptive fields disagree, or only one of them "
        "speaks -- a demonstrated defect class of 115 objects whose size nobody "
        "has measured; censused, so the audit decides which field is right",
    "C_sport":
        "Sport before and after the D2 correction, sport retail included -- a "
        "headline health-access class, reported per okrug, whose definition "
        "§8.1 leaves open",
    "D_unbenchmarked_okrug":
        "the six okrugs no benchmark covers, 1,649 objects with no held-out "
        "evidence of any kind",
    "E_no_class_benchmarked":
        "the pool §2.5 calls genuinely outside the 2022 scheme; the audit tests "
        "whether it is that, or a spelling hole of the D1 family",
    "F_residual_classified":
        "single-class, carried by category_orig or type_orig, in a benchmarked "
        "okrug -- the slice §10.1 already scores; reached by the city sample only",
}

STRATUM_OF_CELL = {
    "A_name_evidence": "1_name_evidence",
    "B_category_type_conflict": "2_category_type_conflict",
    "C_sport": "3_sport",
    "D_unbenchmarked_okrug": "4_unbenchmarked_okrug",
    "E_no_class_benchmarked": "5_no_class_benchmarked",
    "F_residual_classified": "6_srs_city",   # never drawn purposively
}
SRS_STRATUM = "6_srs_city"

TRUE_COLS = ["true_" + c for c in tx.CLASSES] + ["true_sport_retail"]
BLANK_COLS = TRUE_COLS + ["label_confidence", "label_source", "labeller", "note"]


# --------------------------------------------------------------------------
# a stable object id
# --------------------------------------------------------------------------
def object_ids(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """`v3-NNNN` by row position, plus a content hash that survives reordering.

    The export is read-only, so row position is stable in practice; the hash is
    what lets a later run prove it.  Verified unique over all 7,263 rows.
    """
    pos = pd.Series([f"v3-{i:04d}" for i in range(len(df))], index=df.index)
    key = (df.name_orig.fillna("").astype(str) + "|"
           + df.adress_orig.fillna("").astype(str) + "|"
           + df.latitude.astype(str) + "|" + df.longitude.astype(str) + "|"
           + df.type_orig.fillna("").astype(str))
    h = key.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()[:12])
    if h.nunique() != len(df):
        raise AssertionError("row hash is not unique -- the id scheme is broken")
    return pos, h


# --------------------------------------------------------------------------
# where the export's two descriptive fields disagree
# --------------------------------------------------------------------------
def conflict_view(d: pd.DataFrame) -> pd.DataFrame:
    """Rows where `category_orig` and `type_orig`/`name_orig` do not agree.

    `classify()` resolves the disagreement in favour of the category, which is
    almost certainly right on the 35 vape shops that carry
    `type_orig = Продуктовый магазин` -- and is an assertion nobody has tested
    anywhere else.  Isolating it needs to know what the record says *without*
    the category, which is `classify()` run a second time over a copy with
    `category_orig` blanked: the module's own entry point, so this follows
    further edits to the rule instead of restating them.

    Returns `conflict_kind` (`class` | `uncorroborated` | `""`) and a
    `conflict_note` naming what disagrees with what.
    """
    blanked = d.copy()
    blanked["category_orig"] = ""
    free = tx.classify(blanked)

    cat_class = d["category_orig"].fillna("").map(
        {v: c for c, vals in tx.CATEGORY_OF.items() for v in vals})
    has_cat = cat_class.notna()

    kind = pd.Series("", index=d.index)
    note = pd.Series("", index=d.index)

    # The category names class X; the type or the fascia says class Y instead.
    # The mask is the module's own `overridden()`, so this cell and the module's
    # `assert_override_is_narrow()` guard cannot drift apart; the loop below only
    # recovers *which* class disagreed, for the note.
    other = tx.overridden(d)
    said = pd.Series("", index=d.index)
    derived = pd.Series(False, index=d.index)
    for c in tx.CLASSES:
        m = has_cat & (cat_class != c) & free[f"is_{c}"]
        derived |= m
        said[m] = said[m] + tx.CLASS_EN[c] + "|"
    if not derived.eq(other).all():
        raise AssertionError(
            "the conflict note disagrees with taxonomy_2022.overridden() on "
            f"{int((derived != other).sum())} rows -- one of the two is stale")

    # The category names class X and nothing else in the record supports it.
    corroborated = pd.Series(False, index=d.index)
    for c in tx.CLASSES:
        corroborated |= has_cat & (cat_class == c) & free[f"is_{c}"]
    uncorroborated = has_cat & ~corroborated & ~other

    kind[other] = "class"
    note[other] = ("category_orig says "
                   + cat_class[other].map(tx.CLASS_EN)
                   + ", type/name say " + said[other].str.rstrip("|"))
    kind[uncorroborated] = "uncorroborated"
    note[uncorroborated] = ("category_orig says "
                            + cat_class[uncorroborated].map(tx.CLASS_EN)
                            + " and nothing else in the record supports it")
    return pd.DataFrame({"conflict_kind": kind, "conflict_note": note},
                        index=d.index)


# --------------------------------------------------------------------------
# the cell partition
# --------------------------------------------------------------------------
def assign_cells(d: pd.DataFrame, old: pd.Series, conflict: pd.DataFrame,
                 name_only: pd.Series) -> pd.Series:
    """Every object into exactly one of the six cells, by the priority below.

    The order matters: it decides which cell an object that qualifies for
    several lands in, and it is chosen so that the smallest, most contested
    cells keep their objects.  `D` sits before `E` deliberately -- putting the
    six unbenchmarked okrugs first means the no-class claim is tested separately
    inside and outside benchmark coverage, and both halves stay reweightable.
    """
    conflicting = conflict["conflict_kind"] != ""
    # Both directions of the D2 correction: what Sport lost (83 rows, 63 of them
    # saunas) and what it kept.  Auditing only the survivors would confirm the
    # correction rather than test it.
    sport_all = d["is_sport"] | d["is_sport_retail"] | (old == "Sport")
    unbench = ~d["okrug_key"].isin(BENCHMARKED)
    no_class = d["n_classes"] == 0

    cell = pd.Series("F_residual_classified", index=d.index)
    for name, mask in [("E_no_class_benchmarked", no_class),
                       ("D_unbenchmarked_okrug", unbench),
                       ("C_sport", sport_all),
                       ("B_category_type_conflict", conflicting),
                       ("A_name_evidence", name_only)]:
        cell[mask] = name
    return cell


# --------------------------------------------------------------------------
# drawing
# --------------------------------------------------------------------------
def _take(rng: np.random.Generator, pool: np.ndarray, n: int) -> np.ndarray:
    """`n` positions from `pool` without replacement, order-stable."""
    n = int(min(n, len(pool)))
    if n <= 0:
        return np.array([], dtype=pool.dtype)
    return np.sort(rng.choice(np.sort(pool), size=n, replace=False))


def proportional_allocation(sizes: pd.Series, total: int) -> pd.Series:
    """Largest-remainder allocation of `total` across `sizes`.

    Proportional allocation makes the city sample self-weighting: every object
    has inclusion probability total/N up to the rounding this resolves, so the
    draw is uniform over the city and therefore uniform inside every cell.
    """
    exact = sizes / sizes.sum() * total
    base = np.floor(exact).astype(int)
    short = total - int(base.sum())
    if short:
        order = (exact - base).sort_values(ascending=False).index[:short]
        base.loc[order] += 1
    return base


def main() -> int:
    seed_in_protocol(SEED)

    d = tx.load_export().reset_index(drop=True)
    if len(d) != 7263:
        raise AssertionError(f"expected 7,263 export rows, got {len(d)}")
    old = v3.recode_2022(d)
    d["old_class_2022"] = old
    d["object_id"], d["row_hash"] = object_ids(d)
    conflict = conflict_view(d)
    d = pd.concat([d, conflict], axis=1)
    ev = [c + "_evidence" for c in tx.CLASSES]
    name_only = (d[ev] == "name").any(axis=1)
    d["cell"] = assign_cells(d, old, conflict, name_only)

    # The seven multi-label objects are too few to be a stratum but must not be
    # lost: they are the whole of what the rule says about co-membership.
    multi = d["n_classes"] >= 2
    if not d.loc[multi, "cell"].isin(["A_name_evidence",
                                      "B_category_type_conflict"]).all():
        raise AssertionError(
            "a multi-label object fell outside the two census cells and would "
            "be sampled rather than labelled")

    rng = np.random.default_rng(SEED)
    pos = np.arange(len(d))

    # --- stratum 6: the city sample, proportional to okrug -----------------
    okr_sizes = d.groupby("okrug_key").size().sort_index()
    alloc = proportional_allocation(okr_sizes, N_SRS)
    srs_pos, srs_weight = [], {}
    for okrug in okr_sizes.index:
        pool = pos[d["okrug_key"].values == okrug]
        picked = _take(rng, pool, int(alloc[okrug]))
        srs_pos.extend(picked.tolist())
        for p in picked:
            srs_weight[p] = okr_sizes[okrug] / int(alloc[okrug])
    srs_pos = np.sort(np.array(srs_pos, dtype=int))

    # --- strata 1-5: top up each purposive cell ---------------------------
    in_srs = np.zeros(len(d), dtype=bool)
    in_srs[srs_pos] = True

    sizes = d["cell"].value_counts()
    targets = {
        "A_name_evidence": int(sizes.get("A_name_evidence", 0)),           # census
        "B_category_type_conflict":
            int(sizes.get("B_category_type_conflict", 0)),                 # census
        "C_sport": N_SPORT,
        "D_unbenchmarked_okrug": N_UNBENCH,
    }
    fresh_so_far = 0
    fresh_pos: dict[str, np.ndarray] = {}
    for cell in ["A_name_evidence", "B_category_type_conflict", "C_sport",
                 "D_unbenchmarked_okrug"]:
        pool = pos[(d["cell"].values == cell) & ~in_srs]
        already = int(((d["cell"].values == cell) & in_srs).sum())
        picked = _take(rng, pool, targets[cell] - already)
        fresh_pos[cell] = picked
        fresh_so_far += len(picked)

    # Cell E absorbs the remainder of the budget.  It is the largest cell
    # (3,652 objects, half the city) and carries the strongest claim in §2.5, so
    # it is the right place for whatever the fixed targets leave.
    pool = pos[(d["cell"].values == "E_no_class_benchmarked") & ~in_srs]
    fresh_pos["E_no_class_benchmarked"] = _take(
        rng, pool, N_TOTAL - len(srs_pos) - fresh_so_far)

    chosen = np.sort(np.concatenate(
        [srs_pos] + [v for v in fresh_pos.values() if len(v)]))
    if len(chosen) != N_TOTAL:
        raise AssertionError(f"drew {len(chosen)} objects, expected {N_TOTAL}")

    s = d.iloc[chosen].copy()
    s["stratum"] = np.where(in_srs[chosen], SRS_STRATUM,
                            s["cell"].map(STRATUM_OF_CELL))
    s["srs_weight"] = [round(srs_weight[p], 4) if p in srs_weight else ""
                       for p in chosen]

    # One weight system over the whole file: the six cells partition the city and
    # every cell's rows in this file are a uniform sample of it.
    cell_n = s["cell"].value_counts()
    s["cell_N"] = s["cell"].map(sizes).astype(int)
    s["cell_n"] = s["cell"].map(cell_n).astype(int)
    s["weight"] = (s["cell_N"] / s["cell_n"]).round(4)
    s["cell_why"] = s["cell"].map(CELL_WHY)

    # --- the 10 % double-labelled subset, stratified by cell ---------------
    dbl = np.zeros(len(s), dtype=bool)
    for cell, idx in s.reset_index(drop=True).groupby("cell").groups.items():
        idx = np.sort(np.asarray(list(idx)))
        k = int(round(len(idx) * DOUBLE_LABEL_FRAC))
        if k:
            dbl[_take(rng, idx, k)] = True
    s["double_label"] = dbl

    for c in BLANK_COLS:
        s[c] = ""

    cols = (["object_id", "row_hash", "stratum", "cell", "cell_N", "cell_n",
             "weight", "srs_weight", "double_label", "okrug_key",
             "district_orig", "name_orig", "adress_orig", "latitude",
             "longitude", "category_orig", "type_orig", "old_class_2022"]
            + [f"is_{c}" for c in tx.CLASSES]
            + [f"{c}_evidence" for c in tx.CLASSES]
            + ["is_sport_retail", "n_classes", "classes_2022",
               "conflict_kind", "conflict_note"]
            + BLANK_COLS + ["cell_why"])
    s = s[cols].sort_values(["stratum", "okrug_key", "adress_orig", "object_id"])

    txt = summary(d, s, sizes, alloc, okr_sizes)
    write_csv(s, txt)
    OUT_TXT.write_text(txt, encoding="utf-8")
    print(f"wrote {OUT_CSV.name} ({len(s)} rows) and {OUT_TXT.name}")
    return 0


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
def write_csv(s: pd.DataFrame, txt: str) -> None:
    """The sample, behind a `#`-commented preamble carrying its own provenance.

    A reader takes it with

        pd.read_csv(path, sep=";", encoding="utf-8-sig", comment="#")

    which is only safe while no emitted cell contains a `#`; asserted here so
    that whoever adds a column finds out rather than losing a row silently.
    """
    body = s.astype(str)
    bad = body.apply(lambda col: col.str.contains("#", regex=False)).any().any()
    if bad:
        raise AssertionError(
            "a cell contains '#', which the comment-prefixed preamble would eat")

    pre = [
        "audit sample over the 2022 taxonomy -- 600 objects, 6 strata",
        f"seed: {SEED}  (also recorded in docs/taxonomy_2022_audit_protocol.md)",
        "read with: pd.read_csv(path, sep=';', encoding='utf-8-sig', comment='#')",
        "",
        "LABELLING RULES ARE IN docs/taxonomy_2022_audit_protocol.md.  Read them",
        "before filling anything in.  Fill true_<class> with 1, 0 or ? -- '?' is",
        "a permitted answer and forcing a 0 instead manufactures precision.",
        "",
        "weight      = cell_N / cell_n.  The six cells partition all 7,263",
        "              objects and each cell's rows here are a uniform sample of",
        "              it, so these weights sum to 7,263 and a city-level rate is",
        "              a weighted mean over the whole file.",
        "srs_weight  = N_okrug / n_okrug, on the 100 stratum-6 rows only.  Those",
        "              rows are a self-weighting sample of the whole city drawn",
        "              proportionally to okrug; they also sum to 7,263 and give",
        "              the same city rate from a design with no purposive part.",
        "",
        "Stratum 6 is not optional.  Strata 1-5 oversample the rule's weak points",
        "by factors of 1 to 25, so a rate measured inside one of them is a rate",
        "for that cell alone.  Only a draw with known, uniform inclusion",
        "probability over all 7,263 objects converts cell rates into city",
        "numbers, and only an okrug-proportional draw guarantees a share of it",
        "(23 of 100) in the six okrugs no benchmark covers.",
        "",
        "Full stratum table, effort and limits: taxonomy_2022_audit_sample_summary.txt",
    ]
    buf = io.StringIO()
    for line in pre:
        buf.write(("# " + line).rstrip() + "\n")
    s.to_csv(buf, sep=";", index=False, lineterminator="\n")
    PROC.mkdir(parents=True, exist_ok=True)
    OUT_CSV.write_text(buf.getvalue(), encoding="utf-8-sig")


def summary(d, s, sizes, alloc, okr_sizes) -> str:
    out = io.StringIO()

    def P(*a):
        print(*a, file=out)

    P("audit sample over the 2022 taxonomy")
    P("seed   : %d" % SEED)
    P("source : %s (%d objects)" % (tx.V3_CSV.name, len(d)))
    P("output : %s" % OUT_CSV.name)
    P("rules  : docs/taxonomy_2022_audit_protocol.md")
    P("")
    P("=== the six strata ===")
    P("%-24s %7s %6s %6s %8s %8s" %
      ("stratum", "cell_N", "srs", "fresh", "cell_n", "weight"))
    for cell in CELLS:
        sub = s[s["cell"] == cell]
        if not len(sub):
            continue
        n_srs = int((sub["stratum"] == SRS_STRATUM).sum())
        P("%-24s %7d %6d %6d %8d %8.2f" %
          (STRATUM_OF_CELL[cell] if cell != "F_residual_classified"
           else "6_srs_city (cell F)",
           int(sizes[cell]), n_srs, len(sub) - n_srs, len(sub),
           float(sub["weight"].iloc[0])))
    P("%-24s %7d %6s %6s %8d %8.2f" %
      ("total", int(sizes.sum()), int((s["stratum"] == SRS_STRATUM).sum()),
       int((s["stratum"] != SRS_STRATUM).sum()), len(s), s["weight"].sum()))
    P("")
    P("`srs` counts rows the city sample had already taken from that cell;")
    P("`fresh` counts the purposive top-up.  Their union is an exactly uniform")
    P("sample of the cell: conditional on the city sample having taken m of the")
    P("cell's N objects, the union of those m and a uniform (n-m) draw from the")
    P("remaining N-m is uniform over the C(N, n) subsets of size n, since")
    P("C(n,m) / (C(N,m) * C(N-m,n-m)) = 1 / C(N,n).  One weight therefore")
    P("suffices, and it is cell_N / cell_n.")
    P("")
    P("weights sum to %.1f (city: %d)" % (s["weight"].sum(), len(d)))
    srsw = pd.to_numeric(s["srs_weight"], errors="coerce")
    P("srs_weight sums to %.1f over %d rows" % (srsw.sum(), int(srsw.notna().sum())))
    P("")
    P("=== what each stratum tests ===")
    for cell in CELLS:
        P("  %-24s %s" % (cell, CELL_WHY[cell]))
    P("")
    P("=== city sample: okrug allocation ===")
    P("%-22s %7s %5s %8s" % ("okrug", "N", "n", "weight"))
    for okrug in okr_sizes.index:
        P("%-22s %7d %5d %8.1f" %
          (okrug, okr_sizes[okrug], int(alloc[okrug]),
           okr_sizes[okrug] / int(alloc[okrug])))
    unb = [o for o in okr_sizes.index if o not in BENCHMARKED]
    P("  of which in the six unbenchmarked okrugs: %d of %d"
      % (int(alloc[unb].sum()), N_SRS))
    P("")
    P("=== precision each cell buys ===")
    P("95 % half-width at the worst case p = 0.5, with the finite-population")
    P("correction; a rate nearer 0 or 1 is tighter.")
    P("%-24s %6s %6s %9s" % ("stratum", "N", "n", "+/- pp"))
    for cell in CELLS:
        sub = s[s["cell"] == cell]
        if not len(sub):
            continue
        N, n = int(sizes[cell]), len(sub)
        fpc = np.sqrt((N - n) / (N - 1)) if N > 1 else 0.0
        P("%-24s %6d %6d %9.1f" % (cell, N, n, 100 * 1.96 * 0.5 / np.sqrt(n) * fpc))
    P("")
    P("A census (half-width 0) measures its cell exactly and says nothing about")
    P("any other cell.")
    P("")
    P("=== the no-class claim, and what n buys on it ===")
    nE = len(s[s["cell"] == "E_no_class_benchmarked"])
    nD = len(s[s["cell"] == "D_unbenchmarked_okrug"])
    P("Cell E is the test of §2.5: that the 4,647 objects in no class are")
    P("genuinely outside the 2022 scheme rather than a spelling hole of the D1")
    P("family.  With n = %d and zero misclassifications found, the 95 %% upper" % nE)
    P("bound on the miss rate in that cell is 3/n = %.1f %%, i.e. at most about"
      % (300.0 / nE))
    P("%d objects city-wide in cell E.  One miss found moves the bound to about"
      % round(sizes["E_no_class_benchmarked"] * 3.0 / nE))
    P("%.1f %%.  Cell D (n = %d) carries the same test outside benchmark coverage."
      % (100 * 4.74 / nE, nD))
    P("")
    P("=== cell B: where the export contradicts itself ===")
    P("classify() resolves the disagreement in favour of category_orig.  That is")
    P("almost certainly right on the 35 vape shops typed `Продуктовый магазин`,")
    P("and it is an assertion untested anywhere else.  Cell B censuses all %d"
      % int((d.conflict_kind != "").sum()))
    P("such objects, so the audit answers it for every one.")
    P("")
    for k, v in d.loc[d.conflict_kind != "", "conflict_kind"].value_counts().items():
        P("  %-16s %4d" % (k, v))
    P("")
    P("  %-58s %5s" % ("what disagrees with what", "n"))
    for k, v in d.loc[d.conflict_kind != "", "conflict_note"].value_counts().items():
        P("  %-58s %5d" % (k[:58], v))
    P("")
    P("Where the human marks the category's class and not the other, the")
    P("override is right and type_orig is simply bad on that slice.  Where both")
    P("are marked, the object is genuinely two things and the override is")
    P("suppressing a true class.  Where neither, the category is wrong too.")
    P("")
    P("=== co-membership: what this sample can and cannot settle ===")
    n_multi = int((d.n_classes >= 2).sum())
    P("The rule puts two 2022 classes on %d objects in %d -- %.2f %% -- and five"
      % (n_multi, len(d), 100 * n_multi / len(d)))
    P("of those are spurious Industrial fascia hits on «мясокомбинат» and")
    P("«Хладокомбинат».  So the export's own fields carry essentially no")
    P("co-membership, which §10.4 already concluded: only the v4 risk layers and")
    P("the licence registry carry it, and they imply on the order of 560")
    P("grocery x tobacco sites (7.7 % of the city).")
    P("")
    P("The audit cannot estimate co-membership *from the export's fields* -- they")
    P("do not encode it.  It can estimate it *from the objects*, which is the")
    P("point of labelling by hand, and the two candidate answers are far enough")
    P("apart that 600 objects separate them decisively: at the fields' rate of")
    P("%.2f %% the 100-row city sample expects %.2f hits, at 7.7 %% it expects 7.7,"
      % (100 * n_multi / len(d), 100.0 * n_multi / len(d)))
    P("so three or more grocery-and-tobacco objects in that sample rule out the")
    P("fields' answer at p < 0.001.  What it will not do is pin the rate finely")
    P("-- the city sample alone gives roughly +/- 5 pp, the weighted 600 rather")
    P("better.  Report a direction and an interval, never a point estimate.")
    P("")
    P("=== double-labelled subset ===")
    n_dbl = int(s["double_label"].sum())
    P("%d objects (%.0f %%), drawn within each stratum, marked `double_label`."
      % (n_dbl, 100 * n_dbl / len(s)))
    P("Second labeller works independently; Cohen's kappa is computed per class.")
    P("At n = %d the standard error on kappa is about 0.10, so kappa must be" % n_dbl)
    P("reported to ONE decimal.  It can show kappa < 0.6; it cannot separate 0.8")
    P("from 0.9, and quoting two decimals would claim a resolution the sample")
    P("does not have.")
    P("")
    P("=== effort ===")
    P("%d objects x 2 min = %.1f h" % (len(s), len(s) * 2 / 60))
    P("%d double-labelled x 2 min = %.1f h" % (n_dbl, n_dbl * 2 / 60))
    P("total %.1f h" % ((len(s) + n_dbl) * 2 / 60))
    P("")
    P("=== what this sample cannot buy ===")
    ind = int(d["is_industrial"].sum())
    ind_s = int(s["is_industrial"].sum())
    P("- Nothing about Industrial city-wide.  The rule finds %d objects (%.1f %% of"
      % (ind, 100 * ind / len(d)))
    P("  the city) and the 2022 class holds 10.  All %d are in this sample --" % ind_s)
    P("  cell A is a census -- so their precision is measured exactly, but a")
    P("  prevalence for the class is not estimable from 600 draws and the 2022")
    P("  meaning of `Пром. Объекты` is itself an open question (§8.1).")
    P("- No per-okrug number for the six unbenchmarked okrugs.  Cell D gives %d"
      % nD)
    P("  objects across six okrugs -- enough for a pooled rate, not for six.")
    P("- No improvement to training.  These labels are a measurement, not a")
    P("  training set; §10.4 shows the export's features do not encode")
    P("  co-membership at all, so more labels do not make the seven-column")
    P("  deliverable reachable.")
    P("- No rate for cell F beyond what the city sample's %d rows in it support."
      % int((s["cell"] == "F_residual_classified").sum()))
    P("- Nothing about objects the export does not hold.  §10.1 traces ~30 of")
    P("  the 96 known rule errors to join artefacts -- a stadium linked to its")
    P("  school, a canteen to the university around it.  An audit of export rows")
    P("  cannot see an object that is not one.")
    P("")
    P("=== class counts under audit, for reference ===")
    P("%-16s %8s %8s" % ("class", "city", "in sample"))
    for c in tx.CLASSES:
        P("%-16s %8d %8d" % (tx.CLASS_EN[c], int(d["is_" + c].sum()),
                             int(s["is_" + c].sum())))
    P("%-16s %8d %8d" % ("no class", int((d.n_classes == 0).sum()),
                         int((s.n_classes == 0).sum())))
    return out.getvalue()


def seed_in_protocol(seed: int) -> None:
    """Refuse to draw unless the written protocol records the same seed.

    The protocol states the labelling rules the sample is drawn for; a sample
    drawn under a seed the protocol does not name is a sample nobody agreed to.
    """
    if not PROTOCOL.exists():
        raise SystemExit(
            f"{PROTOCOL} is missing -- the labelling rules must be written down "
            "before the sample is drawn, not after")
    text = PROTOCOL.read_text(encoding="utf-8")
    m = re.search(r"^\s*-?\s*\*{0,2}[Ss]eed\*{0,2}\s*[:=]\s*`?(\d+)`?",
                  text, re.MULTILINE)
    if m is None or int(m.group(1)) != seed:
        raise SystemExit(
            f"{PROTOCOL.name} records seed {m.group(1) if m else 'none'}, this "
            f"script uses {seed} -- they must agree or the labelled rows belong "
            "to a different draw")


if __name__ == "__main__":
    raise SystemExit(main())
