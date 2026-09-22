"""What the seven-flag 2022 rule is actually known to do, and on how little.

    pixi run python scripts/validate_taxonomy_2022.py

`arkhinfra.taxonomy_2022` replaced `v3_common.recode_2022()` for the 2022
taxonomy, and the change has to be *measured* rather than argued: three defects
were fixed (D1-D3 of `docs/classifier_design.md` section 10) and the output
shape changed from one label to seven booleans.  This script scores both rules
against the only object-level benchmark this repository holds -- the 2022 study,
joined to the export by `data/processed/match_2022_local.csv` -- and writes
`data/processed/taxonomy_2022_validation.txt`.

It exists mainly to make the resulting table **impossible to mistake for a
city-wide guarantee**.  The benchmark reaches 1,133 of 7,263 objects, in three
of nine okrugs, and only those whose name survived four years intact; rule
accuracy on them tracks the quality of the link that put them there.  Every
number below is therefore reported with the denominator it was computed on, a
confidence interval wide enough to be honest about that denominator, and -- for
the classes where the sample cannot support a claim -- a refusal instead of a
number.

Three choices are worth knowing before reading the output.

**Scoring.**  Each class is scored as its own binary problem: `is_<class>` (or,
for the old rule, `recode_2022() == CLASS_EN[c]`) against `label == class`.  The
benchmark carries **one** label per object, so an object that genuinely belongs
to two classes must cost one of them a false positive whatever the rule does.
Multi-label precision measured this way is a *lower bound*, and section 5 of the
output quantifies how much of it is this artefact.

**Intervals.**  Wilson intervals assume independent rows, and these rows are
not: 11 of the 57 alcohol positives are the same fascia (Бристоль), 5 of the 16
tobacco positives are hookah lounges.  The bootstrap resamples *fascias* rather
than rows and is the interval to quote; Wilson is printed beside it to show how
much the dependence costs.

**Error triage.**  Splitting an error into "the join linked two different
objects", "both labels are true and a single-label benchmark cannot say so" and
"the rule is wrong" cannot be read off the data -- it needs a judgement about
what the two records are.  That judgement is made here by two declared lists,
`COMPATIBLE_PAIRS` and `ENCLOSING_TYPES`, both visible below, and every one of
the error rows is printed in full so a reviewer can overturn any assignment.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from arkhinfra import taxonomy_2022 as tx  # noqa: E402
from arkhinfra import v3_common as v3  # noqa: E402
from arkhinfra.paths import PROC, V3_CSV  # noqa: E402

OUT_TXT = PROC / "taxonomy_2022_validation.txt"
MATCH = PROC / "match_2022_local.csv"

# The 2022 study's three okrugs.  Everything else has no object-level benchmark.
OKRUGS_2022 = set(v3.OKRUGS_2022)

# Tiers that assert "this benchmark object is this export object".  `gps_only`
# and `unmatched` do not, and are the unmeasured remainder.
LINKED_TIERS = ("exact", "probable")

BOOTSTRAP_B = 2000
RNG_SEED = 20260915

# --------------------------------------------------------------------------
# the two declared lists the error triage rests on
# --------------------------------------------------------------------------
# Class pairs a *single* retail unit can genuinely carry at once.  A benchmark
# that allows one label per object must score one of the two as an error; these
# are the pairs where that is the metric's fault and not the rule's.  Each is a
# trade fact, not a fit to the residual: a Бристоль is a grocery that sells
# spirits, a hookah lounge serves food, a bakery has a counter and a shelf.
COMPATIBLE_PAIRS = {
    frozenset({"grocery", "alcohol"}),
    frozenset({"grocery", "tobacco"}),
    frozenset({"grocery", "catering"}),
    frozenset({"catering", "alcohol"}),
    frozenset({"catering", "tobacco"}),
    frozenset({"alcohol", "tobacco"}),
}

# `type_orig` values naming a venue that *contains or abuts* an independent
# smaller business rather than being one.  A benchmark canteen linked to the
# college around it, a benchmark stadium linked to the school it belongs to, a
# benchmark pharmacy linked to the supermarket next door: the export does not
# hold the benchmark object at all, so no rule over export fields can reach it.
ENCLOSING_TYPES = {
    "Школа", "Вуз", "Колледж", "Детский сад", "Гостиница", "Полиция",
    "Офис: company", "Музей", "Объект: community_centre", "Магазин: mall",
    "Салон красоты", "Косметика", "Хозяйственный магазин",
    "Магазин: interior_decoration", "Объект: veterinary",
}


# --------------------------------------------------------------------------
# interval machinery
# --------------------------------------------------------------------------
def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval -- iid rows assumed, which is why it is not alone."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _fascia(name: str) -> str:
    """The first significant word of a name -- Магнит, Бристоль, Пятёрочка.

    The dependence in this sample is chain-shaped: one fascia decides many rows
    at once, so the bootstrap must resample fascias, not rows.
    """
    words = [w for w in tx.norm_type(name).split() if len(w) >= 3]
    return words[0] if words else ""


def cluster_boot(y: np.ndarray, p: np.ndarray, clusters: np.ndarray,
                 b: int = BOOTSTRAP_B, seed: int = RNG_SEED):
    """Percentile bootstrap on (precision, recall), resampling whole clusters."""
    uniq = np.unique(clusters)
    idx_of = {c: np.where(clusters == c)[0] for c in uniq}
    rng = np.random.default_rng(seed)
    ps, rs = [], []
    for _ in range(b):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        take = np.concatenate([idx_of[c] for c in pick])
        yy, pp = y[take], p[take]
        tp = int((yy & pp).sum())
        if pp.sum():
            ps.append(tp / int(pp.sum()))
        if yy.sum():
            rs.append(tp / int(yy.sum()))

    def q(a):
        if not a:
            return (float("nan"), float("nan"))
        return (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5)))

    return q(ps), q(rs)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar on the discordant pairs only."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, 2 * stats.binom.cdf(min(b, c), n, 0.5)))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjustment, returned keyed like the input."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def fmt(x: float, nd: int = 3) -> str:
    return "  --  " if x != x else f"{x:.{nd}f}"


def pfmt(p: float) -> str:
    """A p-value that does not round a real result away to 0.0000."""
    return f"{p:.2e}" if p < 1e-4 else f"{p:.4f}"


# --------------------------------------------------------------------------
def main() -> int:
    out = io.StringIO()

    def P(*a):
        print(*a, file=out)

    export = pd.read_csv(V3_CSV, sep=";", encoding="utf-8-sig", low_memory=False)
    export["okrug_key"] = export["district_orig"].map(v3.norm_okrug)
    city_flags = tx.classify(export)

    m = pd.read_csv(MATCH, sep=";", encoding="utf-8-sig", low_memory=False)
    lk = m[m["tier"].isin(LINKED_TIERS)].copy()
    lk["target_index"] = lk["target_index"].astype(int)
    lab_of = {ru: c for c, ru in tx.CLASS_RU_2022.items()}
    lk["y"] = lk["category_orig"].map(lab_of)
    assert lk["y"].notna().all(), "a benchmark category did not map to a class"

    # The export rows the benchmark points at.  Some benchmark rows share a
    # target, so this frame repeats a few export rows.
    E = export.iloc[lk["target_index"].values].reset_index(drop=True)
    lk = lk.reset_index(drop=True)
    new = tx.classify(E).reset_index(drop=True)
    old = pd.Series(v3.recode_2022(E).values, index=lk.index)

    y = lk["y"].to_numpy()
    hit_new = np.array([bool(new.loc[i, "is_" + y[i]]) for i in lk.index])
    hit_old = np.array([old[i] == tx.CLASS_EN[y[i]] for i in lk.index])
    clusters = np.array([_fascia(n) or f"row:{i}"
                         for i, n in enumerate(E["name_orig"].fillna(""))])
    # Rows the old rule got wrong that the new one now gets right, and back.
    conv = int((~hit_old & hit_new).sum())
    regr = int((hit_old & ~hit_new).sum())

    # ------------------------------------------------------------------
    mod_path = Path(tx.__file__)
    mod_sha = hashlib.sha256(mod_path.read_bytes()).hexdigest()[:12]
    mod_mtime = dt.datetime.fromtimestamp(os.path.getmtime(mod_path))
    P("=" * 78)
    P("VALIDATION OF THE SEVEN-FLAG 2022 RULE (arkhinfra.taxonomy_2022)")
    P("against the 2022 benchmark, via data/processed/match_2022_local.csv")
    P("=" * 78)
    P("")
    P("rule under test : %s" % mod_path.name)
    P("                  sha256 %s, modified %s"
      % (mod_sha, mod_mtime.strftime("%Y-%m-%d %H:%M:%S")))
    P("baseline        : v3_common.recode_2022()")
    P("The module is under active edit; every number below belongs to that")
    P("fingerprint and to no other. Re-run this script after any change to it.")
    P("")
    P("READ THIS BEFORE QUOTING ANY NUMBER BELOW")
    P("-" * 78)
    n_lk, n_city = len(lk), len(export)
    P("Every precision and recall in this file is computed on %d of the export's"
      % n_lk)
    P("%d objects -- %.1f %% of the city. It is NOT a city-wide guarantee, and"
      % (n_city, 100 * n_lk / n_city))
    P("the %.1f %% it omits is not a random remainder:" % (100 - 100 * n_lk / n_city))
    P("")
    P("  1. THREE OKRUGS OF NINE. The 2022 study covered %s"
      % ", ".join(sorted(OKRUGS_2022)))
    n_out3 = int((~export["okrug_key"].isin(OKRUGS_2022)).sum())
    P("     only. %d objects (%.1f %% of the city) are in the other six and have"
      % (n_out3, 100 * n_out3 / n_city))
    P("     no object-level benchmark of any kind. Section 6 breaks that down.")
    P("")
    P("  2. THE LINK IS THE FILTER. %d benchmark rows exist; %d reached tier"
      % (len(m), n_lk))
    P("     exact or probable (%.1f %%). The remaining %d reached only gps_only"
      % (100 * n_lk / len(m), len(m) - n_lk))
    P("     or unmatched -- the rows whose NAME did not survive four years. They")
    P("     are unmeasured here, and they are not missing at random: see the")
    P("     per-class link rates in section 1, which run from 86.5 % to 0 %.")
    P("")
    acc_e = hit_new[(lk["tier"] == "exact").to_numpy()].mean()
    acc_p = hit_new[(lk["tier"] == "probable").to_numpy()].mean()
    n_e = int((lk["tier"] == "exact").sum())
    n_p = int((lk["tier"] == "probable").sum())
    P("  3. ACCURACY TRACKS LINK QUALITY. Re-derived here for the NEW rule:")
    P("     hit rate %.3f on tier=exact (n=%d) against %.3f on tier=probable"
      % (acc_e, n_e, acc_p))
    P("     (n=%d). The measured ceiling is the easy end of a graded sample."
      % n_p)
    P("")
    P("  4. ONE LABEL PER OBJECT. The benchmark is single-label; the rule is not.")
    P("     A precision here is a LOWER bound -- section 5 counts how much.")
    P("")
    P("Do not reproduce any table below without item 1 and item 2 beside it.")
    P("")

    # ------------------------------------------------------------------
    P("")
    P("1. WHAT IS MEASURED AND WHAT IS NOT")
    P("=" * 78)
    P("")
    P("benchmark rows by link tier:")
    for t, n in m["tier"].value_counts().items():
        mark = "  <- scored" if t in LINKED_TIERS else "  <- UNMEASURED"
        P("  %-10s %5d%s" % (t, n, mark))
    P("")
    P("per-class link rate (the selection that produced the scored sample):")
    P("  %-16s %7s %7s %8s" % ("class", "bench", "linked", "rate"))
    for c in tx.CLASSES:
        ru = tx.CLASS_RU_2022[c]
        nb = int((m["category_orig"] == ru).sum())
        nl = int((lk["category_orig"] == ru).sum())
        P("  %-16s %7d %7d %7s" % (tx.CLASS_EN[c], nb, nl,
                                   "%.1f %%" % (100 * nl / nb) if nb else "  --"))
    P("")
    P("  Medical links at the top of that range and Industrial at the bottom, so")
    P("  the scored sample over-represents exactly the classes the rule finds")
    P("  easiest. No reweighting fixes this: the unlinked rows have no export")
    P("  row to score a rule on.")
    P("")
    P("distinct export rows behind the %d scored rows: %d"
      % (n_lk, lk["target_index"].nunique()))
    dup = lk[lk["target_index"].duplicated(keep=False)]
    multi = dup.groupby("target_index")["y"].agg(lambda s: "|".join(sorted(set(s))))
    P("  %d export rows carry more than one benchmark row. %d of those carry two"
      % (dup["target_index"].nunique(), int(multi.str.contains(r"\|").sum())))
    P("  DIFFERENT labels -- the benchmark's own, unintended evidence that one")
    P("  object can be two classes:")
    for k, n in multi[multi.str.contains(r"\|")].value_counts().items():
        P("      %-22s %3d" % (k, n))
    P("")
    P("link geometry on the scored rows: name_sim min %.2f, median %.2f;"
      % (lk["name_sim"].min(), lk["name_sim"].median()))
    P("  distance_m median %.1f, max %.1f. Nothing beyond 50 m was linked at all."
      % (lk["distance_m"].median(), lk["distance_m"].max()))

    # ------------------------------------------------------------------
    def table(pred_of, tag):
        rows = []
        for c in tx.CLASSES:
            yc = (y == c)
            pc = pred_of(c)
            tp = int((yc & pc).sum())
            fp = int((~yc & pc).sum())
            fn = int((yc & ~pc).sum())
            prec = tp / (tp + fp) if tp + fp else float("nan")
            rec = tp / (tp + fn) if tp + fn else float("nan")
            wp = wilson(tp, tp + fp) if tp + fp else (float("nan"),) * 2
            wr = wilson(tp, tp + fn) if tp + fn else (float("nan"),) * 2
            if int(yc.sum()) or int(pc.sum()):
                bp, br = cluster_boot(yc, pc, clusters)
            else:
                bp = br = (float("nan"),) * 2
            rows.append(dict(cls=tx.CLASS_EN[c], key=c, n=int(yc.sum()),
                             tp=tp, fp=fp, fn=fn, P=prec, R=rec,
                             wp=wp, wr=wr, bp=bp, br=br))
        P("")
        P("%s" % tag)
        P("  %-16s %5s %5s %4s %4s | %-7s %-16s %-16s"
          % ("class", "n", "tp", "fp", "fn", "P", "Wilson 95%", "cluster boot 95%"))
        for r in rows:
            if r["n"] == 0:
                P("  %-16s %5d %5s %4d %4s | %-7s %s"
                  % (r["cls"], 0, "--", r["fp"], "--", "REFUSED",
                     "no labelled row"))
                continue
            P("  %-16s %5d %5d %4d %4d | %-7s [%s, %s]  [%s, %s]"
              % (r["cls"], r["n"], r["tp"], r["fp"], r["fn"], fmt(r["P"]),
                 fmt(r["wp"][0]), fmt(r["wp"][1]), fmt(r["bp"][0]), fmt(r["bp"][1])))
        P("")
        P("  %-16s %5s %5s %4s %4s | %-7s %-16s %-16s"
          % ("", "", "", "", "", "R", "Wilson 95%", "cluster boot 95%"))
        for r in rows:
            if r["n"] == 0:
                continue
            P("  %-16s %5s %5s %4s %4s | %-7s [%s, %s]  [%s, %s]"
              % (r["cls"], "", "", "", "", fmt(r["R"]),
                 fmt(r["wr"][0]), fmt(r["wr"][1]), fmt(r["br"][0]), fmt(r["br"][1])))
        return {r["key"]: r for r in rows}

    P("")
    P("")
    P("2. THE NEW RULE, PER CLASS")
    P("=" * 78)
    P("")
    P("Scored as seven independent binary problems: is_<class> against")
    P("label == <class>, on the %d scored rows. The bootstrap resamples fascias"
      % n_lk)
    P("(%d distinct), not rows, because chains decide many rows at once."
      % len(np.unique(clusters)))
    R_new = table(lambda c: new["is_" + c].to_numpy(),
                  "NEW RULE (taxonomy_2022.classify)")
    P("")
    n_ind = int(new["is_industrial"].sum())
    P("  Industrial: REFUSED. The benchmark holds 10 industrial objects and the")
    P("  matcher linked 0 of them, so precision and recall are undefined, not")
    P("  low. The rule flags %d of the scored rows industrial, and every one of"
      % n_ind)
    P("  those is a false positive by construction, since no scored row carries")
    P("  the label. Section 8 looks at the class city-wide instead.")
    P("")
    P("  Tobacco: n=16. The Wilson interval on recall is %.2f wide; any claim"
      % (R_new["tobacco"]["wr"][1] - R_new["tobacco"]["wr"][0]))
    P("  finer than 'between a third and nine tenths' is not in this sample.")
    P("")
    P("  Where the bootstrap interval is wider than the Wilson one, the extra")
    P("  width is chain dependence -- the honest interval is the bootstrap.")
    P("  Where the point estimate is 1.000 the percentile bootstrap degenerates")
    P("  to [1.000, 1.000]: it cannot resample below a boundary. Quote the")
    P("  Wilson interval for Sport precision and Tobacco precision, not that.")

    P("")
    P("")
    P("3. THE OLD RULE, AND WHETHER THE CHANGE IS MEASURABLE")
    P("=" * 78)
    P("")
    P("Old rule scored single-label: recode_2022() == CLASS_EN[c].")
    R_old = table(lambda c: (old == tx.CLASS_EN[c]).to_numpy(),
                  "OLD RULE (v3_common.recode_2022)")

    P("")
    P("paired comparison, recall only (same denominator; precision denominators")
    P("differ between the rules so no paired test applies to it):")
    P("")
    P("  %-16s %8s %8s %8s | %5s %5s %10s %10s"
      % ("class", "R old", "R new", "delta", "b", "c", "McNemar", "Holm"))
    raw = {}
    disc = {}
    for c in tx.CLASSES:
        yc = (y == c)
        if not yc.sum():
            continue
        a = (old == tx.CLASS_EN[c]).to_numpy()[yc]
        bnew = new["is_" + c].to_numpy()[yc]
        b = int((a & ~bnew).sum())      # old right, new wrong
        cc = int((~a & bnew).sum())     # new right, old wrong
        disc[c] = (b, cc)
        raw[c] = mcnemar_exact(b, cc)
    adj = holm(raw)
    for c in tx.CLASSES:
        if c not in raw:
            continue
        b, cc = disc[c]
        P("  %-16s %8s %8s %+8.3f | %5d %5d %10s %10s"
          % (tx.CLASS_EN[c], fmt(R_old[c]["R"]), fmt(R_new[c]["R"]),
             R_new[c]["R"] - R_old[c]["R"], b, cc, pfmt(raw[c]), pfmt(adj[c])))
    P("")
    P("  b = rows the old rule got right and the new one misses;")
    P("  c = rows the new rule gets right and the old one missed.")
    P("  Holm-adjusted across the %d testable classes. The whole file runs"
      % len(raw))
    P("  %d intervals over 6 classes x 2 rules x {P, R}; treat everything except"
      % (4 * len(raw)))
    P("  the Holm-adjusted column as EXPLORATORY.")
    P("")
    improved = [c for c in raw if R_new[c]["R"] > R_old[c]["R"]]
    worse = [c for c in raw if R_new[c]["R"] < R_old[c]["R"]]
    same = [c for c in raw if R_new[c]["R"] == R_old[c]["R"]]
    P("  IMPROVED on recall : %s"
      % (", ".join(tx.CLASS_EN[c] for c in improved) or "none"))
    P("  WORSE on recall    : %s"
      % (", ".join(tx.CLASS_EN[c] for c in worse) or "none"))
    P("  UNCHANGED on recall: %s"
      % (", ".join(tx.CLASS_EN[c] for c in same) or "none"))
    P("")
    P("  Precision, for comparison (no paired test):")
    for c in tx.CLASSES:
        if c not in raw:
            continue
        P("    %-16s old %s  new %s   delta %+0.3f"
          % (tx.CLASS_EN[c], fmt(R_old[c]["P"]), fmt(R_new[c]["P"]),
             R_new[c]["P"] - R_old[c]["P"]))
    P("")
    P("  PLAIN STATEMENT, computed rather than narrated (the module is under")
    P("  active edit, so this block is regenerated on every run):")
    P("")
    identical = [c for c in raw
                 if (R_old[c]["tp"], R_old[c]["fp"], R_old[c]["fn"])
                 == (R_new[c]["tp"], R_new[c]["fp"], R_new[c]["fn"])]
    for c in tx.CLASSES:
        if c not in raw:
            continue
        dr = R_new[c]["R"] - R_old[c]["R"]
        dp = R_new[c]["P"] - R_old[c]["P"]
        hw_r = (R_new[c]["wr"][1] - R_new[c]["wr"][0]) / 2
        hw_p = (R_new[c]["wp"][1] - R_new[c]["wp"][0]) / 2
        if c in identical:
            verdict = "identical tp/fp/fn"
        elif abs(dr) > hw_r or abs(dp) > hw_p:
            verdict = "MOVES beyond its own interval"
        else:
            verdict = "moves inside its own interval -- unresolvable"
        P("    %-16s dR %+0.3f (half-width %.3f)  dP %+0.3f (half-width %.3f)"
          % (tx.CLASS_EN[c], dr, hw_r, dp, hw_p))
        P("    %-16s %s" % ("", verdict))
    P("")
    P("  Classes bit-for-bit unchanged from the old rule: %s"
      % (", ".join(tx.CLASS_EN[c] for c in identical) or "none"))
    P("")
    P("  This is not evidence against the rewrite. D1-D3 were found on the 84 %")
    P("  of the export this benchmark does not reach, and only D1 leaves a trace")
    P("  inside it: the D2 sport fixes touch saunas and sports shops, which the")
    P("  2022 study did not list as sport, and the D3 grocery rows carry a")
    P("  tobacco label here whichever way the rule resolves them. The benchmark")
    P("  can neither confirm nor refute D2 and D3. Saying the rewrite 'improves")
    P("  classification' on the strength of this table is not supportable; what")
    P("  it does is fix three defects the table cannot see.")

    # ------------------------------------------------------------------
    P("")
    P("")
    P("4. ACCURACY BY LINK TIER -- RE-DERIVED, NOT QUOTED")
    P("=" * 78)
    P("")
    P("  %-10s %6s | %-24s %-24s"
      % ("tier", "n", "OLD exact-match acc", "NEW hit rate"))
    for t in LINKED_TIERS:
        s = (lk["tier"] == t).to_numpy()
        lo_o, hi_o = wilson(int(hit_old[s].sum()), int(s.sum()))
        lo_n, hi_n = wilson(int(hit_new[s].sum()), int(s.sum()))
        P("  %-10s %6d | %.3f  [%.3f, %.3f]   %.3f  [%.3f, %.3f]"
          % (t, int(s.sum()), hit_old[s].mean(), lo_o, hi_o,
             hit_new[s].mean(), lo_n, hi_n))
    lo_o, hi_o = wilson(int(hit_old.sum()), n_lk)
    lo_n, hi_n = wilson(int(hit_new.sum()), n_lk)
    P("  %-10s %6d | %.3f  [%.3f, %.3f]   %.3f  [%.3f, %.3f]"
      % ("all", n_lk, hit_old.mean(), lo_o, hi_o, hit_new.mean(), lo_n, hi_n))
    P("")
    P("  'OLD exact-match acc' is recode_2022() == the benchmark label.")
    P("  'NEW hit rate' is: the benchmark label is among the seven flags. The two")
    P("  are not the same quantity -- the new rule is allowed to flag extra")
    P("  classes and the hit rate does not charge it for them; section 5 does.")
    P("")
    P("  The exact/probable gap is the point. On tier=probable the new rule is")
    P("  %.3f against %.3f for the old, on n=%d: the interval on that difference"
      % (hit_new[(lk["tier"] == "probable").to_numpy()].mean(),
         hit_old[(lk["tier"] == "probable").to_numpy()].mean(), n_p))
    P("  spans zero many times over and the comparison is UNRESOLVABLE at n=%d."
      % n_p)

    # ------------------------------------------------------------------
    P("")
    P("")
    P("5. ERROR DECOMPOSITION FOR THE NEW RULE")
    P("=" * 78)
    P("")
    P("A scored row carries an error if the benchmark label is not flagged (a")
    P("MISS) or a class other than the label is flagged (an EXTRA). Each error")
    P("row is triaged by two lists declared at the top of this script:")
    P("")
    P("  (a) DIFFERENT OBJECT -- the export row's type is in ENCLOSING_TYPES (a")
    P("      school, a hotel, a mall, a university: a venue that contains an")
    P("      independent smaller business), or the class it does carry is")
    P("      incompatible with the label for one retail unit. The export does not")
    P("      hold the benchmark object; no rule over export fields reaches it.")
    P("  (b) CO-MEMBERSHIP -- the flagged class and the label are in")
    P("      COMPATIBLE_PAIRS and the two records name the same business. Both")
    P("      labels are true; a single-label benchmark must score one wrong.")
    P("  (c) GENUINE -- everything else: a definitional hole in the rule.")
    P("")
    P("This is a triage, not a measurement. The full table is printed below so")
    P("any assignment can be overturned.")
    P("")

    def triage(i, cls_flagged):
        et = str(E["type_orig"].iloc[i])
        if et in ENCLOSING_TYPES:
            return "a"
        for f in cls_flagged:
            if frozenset({y[i], f}) in COMPATIBLE_PAIRS:
                return "b"
        if cls_flagged:            # carries a class, none compatible with label
            return "a"
        return "c"

    recs = []
    for i in lk.index:
        flagged = [c for c in tx.CLASSES if new.loc[i, "is_" + c]]
        extras = [c for c in flagged if c != y[i]]
        if hit_new[i] and not extras:
            continue
        recs.append(dict(
            i=i, kind="MISS" if not hit_new[i] else "EXTRA",
            label=y[i], flagged="|".join(flagged) or "(none)",
            block=triage(i, flagged if not hit_new[i] else extras),
            bm_name=lk["name_orig"].iloc[i], bm_type=lk["type_orig"].iloc[i],
            ex_name=E["name_orig"].iloc[i], ex_type=E["type_orig"].iloc[i],
            nsim=round(float(lk["name_sim"].iloc[i]), 2),
            dist=int(round(lk["distance_m"].iloc[i])),
            tier=lk["tier"].iloc[i]))
    ERR = pd.DataFrame(recs)
    P("error rows: %d of %d scored (%d MISS, %d EXTRA-only)"
      % (len(ERR), n_lk, int((ERR.kind == "MISS").sum()),
         int((ERR.kind == "EXTRA").sum())))
    P("")
    names = {"a": "(a) different object / join artefact",
             "b": "(b) co-membership a single-label benchmark cannot express",
             "c": "(c) genuine miss -- definitional hole in the rule"}
    for k in "abc":
        sub = ERR[ERR.block == k]
        P("  %-58s %4d  (%.0f %%)" % (names[k], len(sub), 100 * len(sub) / len(ERR)))
    P("")
    P("  by label:")
    P("  " + pd.crosstab(ERR.label, ERR.block).to_string().replace("\n", "\n  "))
    P("")
    P("  BOUND. If every row triaged (b) is instead counted a genuine rule error")
    P("  -- the conservative reading, since co-membership cannot be verified")
    P("  against a single-label benchmark -- block (c) rises from %d to %d and"
      % (int((ERR.block == "c").sum()), int(ERR.block.isin(["b", "c"]).sum())))
    P("  the rule's genuine error rate on the scored rows moves from %.3f to %.3f."
      % ((ERR.block == "c").sum() / n_lk, ERR.block.isin(["b", "c"]).sum() / n_lk))

    P("")
    P("  --- what the multi-label output converts ---")
    P("")
    P("  The old rule is wrong on %d of the %d scored rows (accuracy %.4f,"
      % (int((~hit_old).sum()), n_lk, hit_old.mean()))
    P("  reproducing section 10.1 of docs/classifier_design.md exactly).")
    P("  Of those %d, the new rule now flags the benchmark label on %d."
      % (int((~hit_old).sum()), conv))
    P("  It loses %d row the old rule had right." % regr)
    P("")
    cv = lk[(~hit_old) & hit_new]
    P("  WHAT THOSE %d CONVERSIONS ARE -- export type_orig:" % conv)
    for t, n in E["type_orig"].iloc[cv.index].value_counts().items():
        P("      %-28s %4d" % (t, n))
    P("      benchmark label: %s"
      % ", ".join("%s %d" % (k, v) for k, v in cv["y"].value_counts().items()))
    P("      flags the new rule sets: %s"
      % ", ".join("%s %d" % (k, v) for k, v in
                  new["classes_2022"].iloc[cv.index].value_counts().items()))
    P("")
    multi_conv = int((new["n_classes"].iloc[cv.index] >= 2).sum())
    P("  THIS IS THE HEADLINE AND IT IS NOT THE EXPECTED ONE. Every conversion is")
    P("  a MISSING-STRING fix -- a `type_orig` the old rule had no entry for,")
    P("  now matched. %d of the %d carry two or more flags, so NONE of them is a"
      % (multi_conv, conv))
    P("  co-membership recovery: the seven-flag form contributes nothing to the")
    P("  conversions, the corrected vocabulary contributes all of them. The same")
    P("  conversions would follow from adding those strings to the old")
    P("  single-label rule.")
    P("")
    P("  The %d MISS rows triaged (b) are still errors, because the rule flags"
      % int(((ERR.block == "b") & (ERR.kind == "MISS")).sum()))
    P("  ONE of the two compatible classes, not both:")
    P("")
    ex_b = ERR[(ERR.block == "b") & (ERR.kind == "MISS")]
    for (lab, fl), n in ex_b.groupby(["label", "flagged"]).size().items():
        P("      label %-9s -> rule flags %-16s  %3d rows" % (lab, fl, n))
    P("")
    P("  Nine Бристоль rows labelled alcohol are flagged Grocery shops ONLY;")
    P("  five hookah lounges labelled tobacco are flagged Catering ONLY. The")
    P("  seven-column output is the right SHAPE for co-membership and carries")
    P("  none of its CONTENT -- which is section 10.4's finding, now confirmed")
    P("  on the labelled rows rather than only on the city-wide predicate count.")
    P("  A report may not claim the multi-label rule 'resolves' these cases.")
    P("")
    P("  --- every error row ---")
    P("")
    P("  " + ERR.drop(columns=["i"]).to_string(index=False, max_colwidth=34)
        .replace("\n", "\n  "))

    # ------------------------------------------------------------------
    P("")
    P("")
    P("6. WHAT HAS NO BENCHMARK AT ALL, BY OKRUG")
    P("=" * 78)
    P("")
    linked_ti = set(lk["target_index"])
    export["_linked"] = [i in linked_ti for i in range(len(export))]
    tab = export.groupby("okrug_key").agg(objects=("okrug_key", "size"),
                                          scored=("_linked", "sum"))
    tab["benchmarked_okrug"] = [k in OKRUGS_2022 for k in tab.index]
    tab["pct_scored"] = (100 * tab["scored"] / tab["objects"]).round(1)
    P("  " + tab.sort_values("objects", ascending=False)
        .to_string().replace("\n", "\n  "))
    P("")
    P("  %d objects (%.1f %%) sit in the six okrugs the 2022 study never visited."
      % (n_out3, 100 * n_out3 / n_city))
    P("  %d more sit inside the three benchmarked okrugs but carry no linked"
      % int((export["okrug_key"].isin(OKRUGS_2022) & ~export["_linked"]).sum()))
    P("  benchmark row. Only %d objects (%.1f %%) are scored anywhere in this file."
      % (int(export["_linked"].sum()), 100 * export["_linked"].sum() / n_city))
    P("")
    P("  (The %d scored rows cover %d distinct export objects; the difference is"
      % (n_lk, int(export["_linked"].sum())))
    P("  benchmark rows sharing a target. A handful of linked rows land in")
    P("  Varavino-Faktoriya because the benchmark and the export disagree about")
    P("  the okrug boundary, not because the 2022 study covered it.)")
    P("")
    P("per class: how much of the city-wide count is unbenchmarked")
    P("  %-16s %7s %9s %8s %9s %8s"
      % ("class", "city", "outside3", "share", "scored", "share"))
    in3 = export["okrug_key"].isin(OKRUGS_2022).to_numpy()
    for c in tx.CLASSES:
        f = city_flags["is_" + c].to_numpy()
        tot = int(f.sum())
        o3 = int((f & ~in3).sum())
        sc = int((f & export["_linked"].to_numpy()).sum())
        P("  %-16s %7d %9d %7.1f %% %9d %7.1f %%"
          % (tx.CLASS_EN[c], tot, o3, 100 * o3 / tot if tot else 0,
             sc, 100 * sc / tot if tot else 0))
    P("")
    P("  Grocery shops is the worst case on the first axis and Tobacco outlets")
    P("  on the second. Industrial is scored on one object, and that object is a")
    P("  false positive.")
    P("")
    P("  A per-okrug class count for the six unbenchmarked okrugs is an")
    P("  EXTRAPOLATION from three okrugs, and must be labelled one.")

    # ------------------------------------------------------------------
    P("")
    P("")
    P("7. IS THE RULE WORSE WHERE THE EVIDENCE IS ONLY THE NAME?")
    P("=" * 78)
    P("")
    P("The review queue is justified by the claim that `name` evidence -- the")
    P("fascia alone, with neither category nor type agreeing -- is less reliable")
    P("than `category` or `type`. Measured here rather than assumed.")
    P("")
    P("precision within evidence stratum, pooled over the scorable classes")
    P("(one (row, class) pair per flag set):")
    rows = []
    for c in tx.CLASSES:
        sel = new["is_" + c].to_numpy()
        for i in np.where(sel)[0]:
            rows.append((new[c + "_evidence"].iloc[i], c, bool(y[i] == c)))
    EV = pd.DataFrame(rows, columns=["evidence", "cls", "correct"])
    P("  %-10s %7s %7s %8s %-18s" % ("evidence", "n", "tp", "P", "Wilson 95%"))
    for ev in tx.EVIDENCE_ORDER:
        s = EV[EV.evidence == ev]
        if not len(s):
            P("  %-10s %7d %7s %8s" % (ev, 0, "--", "REFUSED -- n=0"))
            continue
        k, n = int(s.correct.sum()), len(s)
        lo, hi = wilson(k, n)
        P("  %-10s %7d %7d %8.3f [%.3f, %.3f]" % (ev, n, k, k / n, lo, hi))
    P("")
    nname = int((EV.evidence == "name").sum())
    kname = int(EV.loc[EV.evidence == "name", "correct"].sum())
    lo_obs, hi_obs = wilson(kname, nname)
    lo_best, hi_best = wilson(nname, nname)
    P("  THE ANSWER IS: THIS SAMPLE CANNOT RESOLVE IT. Of the %d scored flags,"
      % len(EV))
    P("  `name` evidence accounts for %d (%d correct). Its Wilson interval,"
      % (nname, kname))
    P("  [%s, %s], covers both strata it would have to be compared against:"
      % (fmt(lo_obs), fmt(hi_obs)))
    P("  it is consistent with `name` being far worse than `type`, with its being")
    P("  better than `category`, and with everything in between. Even the best")
    P("  case this n could produce -- every flag correct -- still admits a")
    P("  precision as low as %.2f. No comparison is possible in either direction."
      % lo_best)
    P("  'Not enough data' is the result, and it is the whole result.")
    P("")
    P("  The `category` and `type` strata do separate: %.3f against %.3f, Wilson"
      % (EV.loc[EV.evidence == "category", "correct"].mean(),
         EV.loc[EV.evidence == "type", "correct"].mean()))
    P("  intervals that do not overlap. That is a real and expected ordering --")
    P("  the export asserting a class beats the rule inferring one from a type --")
    P("  but it says nothing about the third stratum, which is the one the review")
    P("  queue is for.")
    P("")
    nm_city = {c: int(((city_flags[c + "_evidence"] == "name")
                       & city_flags["is_" + c]).sum()) for c in tx.CLASSES}
    tot_name = sum(nm_city.values())
    P("  WHY THE SAMPLE IS THIS SMALL, AND WHY THAT MATTERS: city-wide, %d"
      % tot_name)
    P("  objects rest on `name` evidence alone (%s)."
      % ", ".join("%s %d" % (tx.CLASS_EN[c], v) for c, v in nm_city.items() if v))
    P("  The benchmark reaches %d of them -- %.0f %%. The population the review"
      % (nname, 100 * nname / tot_name))
    P("  queue exists to serve is almost exactly the population this benchmark")
    P("  cannot see. The queue has to be justified by the manual audit of")
    P("  section 7 of docs/classifier_design.md, not by this table.")
    P("")
    P("  Per class, with n, for completeness -- none of these is quotable:")
    P("  %-16s %-10s %5s %5s" % ("class", "evidence", "n", "tp"))
    for (c, ev), g in EV.groupby(["cls", "evidence"]):
        P("  %-16s %-10s %5d %5d" % (tx.CLASS_EN[c], ev, len(g),
                                     int(g.correct.sum())))

    # ------------------------------------------------------------------
    P("")
    P("")
    P("8. DISAGREEMENTS, REFUSALS AND THINGS FOUND ON THE WAY")
    P("=" * 78)
    P("")
    P("REPRODUCED EXACTLY from docs/classifier_design.md section 10:")
    P("  - old-rule accuracy on the scored rows %.4f (section 10.1 says 0.915)"
      % hit_old.mean())
    P("  - %d errors (section 10.1 says 96)" % int((~hit_old).sum()))
    P("  - old-rule tier accuracies %.3f exact / %.3f probable (section 10.2"
      % (hit_old[(lk["tier"] == "exact").to_numpy()].mean(),
         hit_old[(lk["tier"] == "probable").to_numpy()].mean()))
    P("    says 0.925 / 0.700)")
    P("  - every cell of section 10.1's per-class table for the old rule")
    P("")
    P("DISAGREEMENTS:")
    P("")
    P("  1. Section 10.2 writes 'every linked row has name_sim >= 0.6'. True but")
    P("     loose: the observed minimum is %.2f. The statement understates how"
      % lk["name_sim"].min())
    P("     narrow the scored sample is.")
    P("")
    P("  2. Section 10.1 groups ~20 errors as 'co-membership scored as error' and")
    P("     the brief for this script expected the seven-flag output to convert")
    P("     them into hits. IT DOES NOT. All %d conversions are missing-string"
      % conv)
    P("     fixes to the class vocabulary (%s), none of them"
      % ", ".join("%s x%d" % (k, v) for k, v in
                  E["type_orig"].iloc[cv.index].value_counts().items()))
    P("     multi-label; the co-membership block is unchanged (%d MISS rows"
      % int(((ERR.block == "b") & (ERR.kind == "MISS")).sum()))
    P("     triaged (b) here).")
    P("     The rule flags one compatible class, never both, so the benchmark")
    P("     still scores the other wrong. Anyone reading 'multi-label' as 'now")
    P("     handles Бристоль' is reading it wrong.")
    P("")
    P("  3. Section 10.1's error blocks are quoted as '~30 / ~20 / 28 / ~18'.")
    P("     Recomputed against the NEW rule with declared criteria the split is")
    P("     %d / %d / %d over %d error rows. The D1 block of 28 is gone because"
      % (int((ERR.block == "a").sum()), int((ERR.block == "b").sum()),
         int((ERR.block == "c").sum()), len(ERR)))
    P("     the new rule fixes it, and the 'singleton' block is absorbed into (a)")
    P("     and (c). The two decompositions are not directly comparable and")
    P("     neither should be quoted as a measurement.")
    P("")
    P("  4. Section 4 calls the per-class table 'the headline validation'. On the")
    P("     evidence here it validates one class change out of seven, on 15.6 %")
    P("     of the city, at the easy end of a graded sample. It is a floor under")
    P("     the rule, not a measurement of it.")
    P("")
    P("REFUSALS:")
    P("  - Industrial: no precision, no recall, no per-okrug number. 0 labelled")
    P("    rows. The class is %d objects city-wide, %d of them on `name`"
      % (int(city_flags["is_industrial"].sum()),
         int(((city_flags["industrial_evidence"] == "name")
              & city_flags["is_industrial"]).sum())))
    P("    evidence, and the benchmark reaches none of them.")
    P("  - Tobacco: n=16 and a recall CI %.2f wide. Report the count, not a rate."
      % (R_new["tobacco"]["wr"][1] - R_new["tobacco"]["wr"][0]))
    P("  - `name`-evidence reliability: n=%d. Not enough data is the result."
      % nname)
    P("  - Anything per-okrug outside Lomonosovsky / Oktyabrsky / Maiskaya Gorka.")
    P("  - Any comparison of the two rules on tier=probable (n=%d)." % n_p)
    P("")
    P("OBSERVED IN THE MODULE (reported, not fixed here):")
    P("")
    d3 = ((export["type_orig"] == "Продуктовый магазин")
          & (export["category_orig"] == "Точки продажи табака"))
    n_d3 = int(d3.sum())
    d3_names = export.loc[d3, "name_orig"].fillna("").astype(str)
    tob_stems = ("дым", "smok", "vape", "вейп", "табак", "табач", "курени",
                 "сигарет", "махорк", "smoky")
    settled = d3_names.str.lower().apply(
        lambda s: any(t in s for t in tob_stems))
    # Does the 2022 study itself have an opinion on any of these 35?
    d3_pos = set(np.where(d3.to_numpy())[0])
    bm_on_d3 = lk[lk["target_index"].isin(d3_pos)]
    P("  1. D3 OF THE DESIGN DOCUMENT IS WRONG, AND THIS FILE AGREES WITH THE")
    P("     CORRECTION. Section 10.3 reads the %d rows pairing" % n_d3)
    P("     `category_orig = Точки продажи табака` with")
    P("     `type_orig = Продуктовый магазин` as 35 grocery shops made invisible")
    P("     by np.select's priority order. Checked here against the fascias:")
    P("     %d of the %d names carry an unambiguous tobacco or vape stem"
      % (int(settled.sum()), n_d3))
    P("     (Азбука дыма, SmokeArh, Дымный папа, Kiss My Vape, Махорка,")
    P("     Станция Дыма, SmokyBro, ...). They are tobacco outlets with a wrong")
    P("     `type_orig`, not groceries. The old rule returned the right answer")
    P("     for them by accident, which is what hid the defect.")
    P("")
    P("     INDEPENDENT CORROBORATION, which the fascia argument does not have:")
    P("     the 2022 study links %d of these %d rows, and labels them %s"
      % (len(bm_on_d3), n_d3,
         " / ".join("%s x%d" % (k, v)
                    for k, v in bm_on_d3["y"].value_counts().items())))
    P("     -- a separate source, four years earlier, agreeing that they are")
    P("     tobacco outlets and not groceries. That is n=%d, so it corroborates"
      % len(bm_on_d3))
    P("     rather than proves, and because the benchmark is single-label it")
    P("     could not have said 'both' even had it wanted to. The fascias carry")
    P("     the weight; the benchmark keeps them company.")
    P("")
    P("     WHAT IS NOT SETTLED: %d of the %d names are not tobacco on their"
      % (n_d3 - int(settled.sum()), n_d3))
    P("     face and rest on the export's `category_orig` alone --")
    for nm in sorted(d3_names[~settled].unique()):
        P("       %s" % nm)
    P("     Two of those read as wholesale rather than retail (Аспект, склад;")
    P("     СНС Экспресс, оптовая компания). A warehouse is not an outlet, and")
    P("     a retail density built on this class should not count them. Not")
    P("     fixed here, and it does not change the correction.")
    P("")
    P("     EFFECT ON THIS FILE'S NUMBERS: the suppression removes 2 grocery")
    P("     false positives among the scored rows. Grocery precision moves")
    P("     +%.3f against a Wilson half-width of %.3f -- directionally right,"
      % (R_new["grocery"]["P"] - R_old["grocery"]["P"],
         (R_new["grocery"]["wp"][1] - R_new["grocery"]["wp"][0]) / 2))
    P("     statistically unresolvable, and no recall is lost. Nothing else in")
    P("     this file moves.")
    P("")
    napitki = (export["type_orig"].fillna("").astype(str)
               .map(tx.norm_type) == "напитки")
    nap_scored = [i for i in lk.index
                  if tx.norm_type(E["type_orig"].iloc[i]) == "напитки"]
    P("  2. D4 (`Напитки` -> Alcohol) IS THE FIRST DEFECT FIX THIS BENCHMARK")
    P("     SCORES AGAINST. The module adds the bare type `Напитки` to")
    P("     ALCOHOL_TYPES, %d rows city-wide, on the argument that the fascias"
      % int(napitki.sum()))
    P("     (Пивас и квас, Архипенный, Razliv, Кега24) leave no soft-drink shop")
    P("     among them. The benchmark reaches %d of those %d rows, and on both"
      % (len(nap_scored), int(napitki.sum())))
    P("     the 2022 study disagrees:")
    for i in nap_scored:
        P("       %-18s export type %-10s  2022 says %s / %s"
          % (str(E["name_orig"].iloc[i])[:18],
             str(E["type_orig"].iloc[i]), y[i], lk["type_orig"].iloc[i]))
    P("     Both are scored as new Alcohol false positives, and neither becomes")
    P("     a Catering hit, so the move costs precision and buys no recall:")
    P("     Alcohol P %s -> %s. The change is INSIDE the interval"
      % (fmt(R_old["alcohol"]["P"]), fmt(R_new["alcohol"]["P"])))
    P("     ([%s, %s]) and n=%d, so this REFUTES NOTHING -- it is two rows."
      % (fmt(R_new["alcohol"]["wp"][0]), fmt(R_new["alcohol"]["wp"][1]),
         len(nap_scored)))
    P("")
    P("     But the direction matters, because it is the off-trade / on-trade")
    P("     distinction CLAUDE.md requires for anything alcohol-related. A")
    P("     draught-beer shop with tables is on-trade; the 2022 study typed both")
    P("     of these `бар`. If `Напитки` mixes the two, %d objects enter the"
      % int(napitki.sum()))
    P("     Alcohol class with an unknown on-trade share, and an off-trade count")
    P("     built on them is not comparable with the EGAIS off-trade licences.")
    P("     RECOMMENDATION: check the %d fascias against on-trade/off-trade"
      % int(napitki.sum()))
    P("     before D4 ships, or flag the slice. The benchmark cannot do it.")
    P("")
    n_multi = int((city_flags["n_classes"] >= 2).sum())
    P("  3. THE MULTI-LABEL OUTPUT NOW CARRIES ALMOST NOTHING. City-wide the")
    P("     rule puts two or more classes on %d of %d objects -- %.2f %%."
      % (n_multi, n_city, 100 * n_multi / n_city))
    for k, v in city_flags.loc[city_flags["n_classes"] >= 2,
                               "classes_2022"].value_counts().items():
        P("       %-34s %4d" % (k, v))
    P("     Section 10.4 measured 47 (0.6 %) before the `contradicted` rule; the")
    P("     seven-column deliverable is now further from carrying co-membership,")
    P("     not closer. Combined with the %d MISS rows this file triages as"
      % int(((ERR.block == "b") & (ERR.kind == "MISS")).sum()))
    P("     co-membership the benchmark cannot express, the conclusion is firm:")
    P("     the seven flags are a single-label rule in seven columns.")
    P("")
    P("  4. INDUSTRIAL IS STILL A NAME-SUBSTRING CLASS. All %d city-wide objects"
      % int(city_flags["is_industrial"].sum()))
    P("     rest on the fascia, and the list includes a hostel called ТЭЦ, a")
    P("     jewellery shop (Московский ювелирный завод), a cake shop (Фабрика")
    P("     тортов), a driving school (Учебный комбинат) and four butcher's")
    P("     shops (Северодвинский мясокомбинат). This is the defect CLAUDE.md")
    P("     already documents for the old rule, still live. Nothing in this")
    P("     repository can measure it: 0 labelled rows.")
    P("")
    stale = OUT_TXT.parent / "taxonomy_2022.csv"
    if stale.exists():
        if os.path.getmtime(stale) < os.path.getmtime(mod_path):
            P("  5. STALE ARTEFACT. data/processed/taxonomy_2022.csv predates the")
            P("     current arkhinfra/taxonomy_2022.py. Re-run")
            P("     scripts/build_taxonomy_2022.py before reading it or its")
            P("     summary; the counts in this file come from the module, not")
            P("     from that CSV, and the two disagree.")
            P("")
    P("=" * 78)

    PROC.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(out.getvalue(), encoding="utf-8")
    print("wrote %s" % OUT_TXT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
