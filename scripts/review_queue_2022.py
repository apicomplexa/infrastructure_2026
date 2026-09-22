"""Rank every object whose 2022 class rests on weak evidence, worst first.

    pixi run python scripts/review_queue_2022.py

Writes `data/processed/taxonomy_2022_review_queue.csv` and
`taxonomy_2022_review_queue_summary.txt` beside it.

**What this is for.**  The audit sample (`scripts/audit_sample_2022.py`) measures
the rule; this queue *repairs* it.  They are different instruments and must not
be confused: the sample is drawn with known inclusion probabilities and its rates
reweight to the city, while this queue is a purposive worklist with no
probability attached to anything.  Nothing measured off the queue is an estimate
of a city rate -- the queue is, by construction, the tail of the distribution.

`docs/classifier_design.md` §4 asks for "a prioritised review queue" as part of
what the evidence actually supports, and §10.5 makes it the instrument that
reaches the definitional defects (D1-D3), which it calls the main open risk,
ahead of classifier accuracy.

**The score is an ordering device, not a probability.**  There are no labels, so
no calibration is possible and none is claimed.  It is a plain sum of the weights
in `ENTRY_REASONS` and `MODIFIERS` below, each of which is a stated concern about
one row; a row carrying three concerns outranks a row carrying one.  A reviewer
works down the list until the budget runs out, and the ordering is the only thing
the score asserts.

**The two near-miss detectors are where the new defects are.**  `missed_types()`
in the module is a guard against a *known* list of Russian stems (`AUDIT_STEMS`).
It cannot find a hole it was not told to look for, and two kinds exist:

- **`near_miss_type_stem`** compares an unclassified type against the class
  vocabulary itself -- the constants the rule ships with plus every type that
  actually carries a class -- on lightly stemmed content words, generic heads
  (`магазин`, `мастерская`, `центр`, ...) removed.  This is the general form of
  the guard: it derives the stems to look for instead of being handed them.
- **`near_miss_type_latin`** tests the Latin half of the export, where 1,889 rows
  carry an OSM tag in `type_orig`.  `AUDIT_STEMS` covered none of it when this
  was written and covers much of it now; what stays here is what the guard still
  does not reach, either because the tag is outside its list or because the type
  is exempted from it.  The vocabulary below is deliberately a list of
  *hypotheses for a human*, not a rule change -- each hit is a question, and the
  answer belongs in the module only after a person has looked at the object.
  The summary file reports how much of `AUDIT_STEMS` is Latin, computed rather
  than asserted, so this paragraph cannot quietly go stale.
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from arkhinfra import taxonomy_2022 as tx  # noqa: E402
from arkhinfra import v3_common as v3  # noqa: E402
from arkhinfra.paths import PROC  # noqa: E402

OUT_CSV = PROC / "taxonomy_2022_review_queue.csv"
OUT_TXT = PROC / "taxonomy_2022_review_queue_summary.txt"

BENCHMARKED = ("Lomonosovsky", "Oktyabrsky", "Maiskaya Gorka")

# Words that carry no discriminating power inside a type label, so that
# `Магазин: dairy` and `Магазин: tea` do not count as near neighbours merely for
# both being shops.  Without this the detector returns 1,328 rows of noise.
GENERIC_TYPE_WORDS = {"магазин", "мастерская", "объект", "центр", "салон",
                      "офис", "точка", "торговый", "досуг", "услуги", "пункт",
                      "отделение", "товаров", "shop"}

# OSM tag values that name food, drink, health, sport or tobacco retail.  Each is
# a hypothesis that an object typed with it belongs to a 2022 class and did not
# reach one.  The list is from the enumeration of every Latin token appearing in
# an unclassified `type_orig`, not from imagination.
LATIN_CLASS_VOCAB = {
    # food and drink -- candidates for Grocery
    "pastry", "confectionery", "chocolate", "tea", "coffee", "water", "honey",
    "greengrocer", "butcher", "seafood", "deli", "convenience", "supermarket",
    "kiosk", "newsagent", "marketplace", "bakery", "dairy", "cheese", "spices",
    "nuts", "frozen", "food", "farm",
    # drink under licence -- candidates for Alcohol
    "alcohol", "wine", "beverages", "brewery",
    # nicotine -- candidates for Tobacco
    "tobacco", "ecigarette", "vape", "hookah",
    # health -- candidates for Medical
    "chemist", "herbalist", "optician", "hearing", "medical", "pharmacy",
    "doctors", "dentist", "clinic", "hospital", "massage",
    # physical activity -- candidates for Sport
    "sports", "fitness", "swimming", "stadium", "pitch", "gym",
}

# reason -> (weight, one-line explanation that goes into `queue_why`)
#
# Entry reasons put a row on the queue.  The weights order the concerns by how
# badly a wrong answer would land in the report, not by how likely it is.
ENTRY_REASONS = {
    "near_miss_type_stem": (
        0.95,
        "the type shares a content stem with a class vocabulary entry but no "
        "class fired -- the D1 family has three known members and this is how a "
        "fourth would look"),
    "near_miss_type_latin": (
        0.90,
        "the type's OSM tag names food, drink, health, sport or tobacco retail "
        "and no class fired -- either outside AUDIT_STEMS or exempted from the "
        "guard, so nothing in the module flags it"),
    "category_type_conflict": (
        0.85,
        "the export contradicts itself -- category_orig names one 2022 class "
        "while type_orig or the fascia implies a different one, and the rule "
        "resolves it in favour of the category without anything having tested "
        "that; 35 of these are the vape shops typed `Продуктовый магазин`"),
    "name_only_evidence": (
        0.80,
        "the class rests on the fascia string alone -- the class built entirely "
        "this way is documented to contain a hostel and a jewellery shop"),
    "sport_correction_drop": (
        0.60,
        "was Sport under the old rule and is neither Sport nor sport retail now "
        "-- the D2 correction, which §8.1 has not yet put to the 2022 authors"),
    "sport_retail": (
        0.55,
        "a sports shop, held out of Sport by a provisional rule -- §8.1 records "
        "whether Спортивные объекты includes shops as an open question"),
    "category_uncorroborated": (
        0.50,
        "category_orig asserts a class and nothing else in the record supports "
        "it -- the type field either repeats the category or says something "
        "unrelated, so the class rests on a single unchecked assertion"),
    "multi_label": (
        0.50,
        "two classes on one object, and §10.4 shows the export encodes "
        "co-membership nowhere, so the second class is the rule's inference"),
    "veto_suppressed": (
        0.45,
        "a class stem fired and a curated veto removed it -- the veto list is a "
        "judgement, not a measurement"),
    "name_forbidden_suppressed": (
        0.45,
        "the fascia implied a class and NAME_ONLY_FORBIDDEN removed it on the "
        "strength of the type label alone"),
}

# Modifiers never put a row on the queue; they move a queued row up.
MODIFIERS = {
    "industrial_class": (
        0.20,
        "Industrial, the class documented as dominated by name-substring false "
        "positives and whose 2022 meaning is an open question"),
    "unbenchmarked_okrug": (
        0.10,
        "in one of the six okrugs no object-level benchmark reaches, so nothing "
        "else in this repository will catch the error"),
}
ALL_REASONS = {**ENTRY_REASONS, **MODIFIERS}


# --------------------------------------------------------------------------
# near-miss detection
# --------------------------------------------------------------------------
def _content_stems(label) -> set[str]:
    """A type's discriminating words, truncated to five characters.

    Truncation is the whole point: `Напитки` and `магазин разливных напитков`
    share no word and the same stem, which is the shape every member of the D1
    family has had so far.
    """
    return {w[:5] for w in tx._type_key(label)
            if w not in GENERIC_TYPE_WORDS and len(w) > 2}


def class_vocabulary(d: pd.DataFrame) -> dict[str, set[tuple[str, str]]]:
    """stem -> {(class, the vocabulary entry it came from)}.

    Built from the rule's own constants *and* from every type that actually
    carries a class in this export, so it tracks edits to the module instead of
    restating them.
    """
    vocab: dict[str, set[tuple[str, str]]] = {}

    def add(label: str, cls: str) -> None:
        for s in _content_stems(label):
            vocab.setdefault(s, set()).add((cls, tx.norm_type(label)))

    for label in tx.GROCERY_TYPES_2022:
        add(label, "grocery")
    for label in tx.ALCOHOL_TYPES:
        add(label, "alcohol")
    for label in tx.SPORT_OPEN_SPACE_TYPES:
        add(label, "sport")
    for label in tx.SPORT_RETAIL_TYPES:
        add(label, "sport_retail")
    for cls, stems in tx.TYPE_STEMS.items():
        for stem in stems:
            vocab.setdefault(stem[:5], set()).add((cls, stem))
    for cls in tx.CLASSES:
        carried = d[f"is_{cls}"] & d[f"{cls}_evidence"].isin(["type", "category"])
        for label in d.loc[carried, "type_orig"].dropna().unique():
            add(label, cls)
    return vocab


def near_miss(d: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """`(stem hit, latin hit, what it resembles)` over the unclassified rows."""
    vocab = class_vocabulary(d)
    unclassified = d["n_classes"] == 0
    typ = d["type_orig"].fillna("").map(tx.norm_type)

    stem_hit = pd.Series(False, index=d.index)
    latin_hit = pd.Series(False, index=d.index)
    note = pd.Series("", index=d.index)

    for label in typ[unclassified].unique():
        if not label:
            continue
        rows = unclassified & (typ == label)
        hits: dict[str, set[str]] = {}
        for stem in _content_stems(label):
            for cls, src in vocab.get(stem, ()):
                hits.setdefault(cls, set()).add(src)
        if hits:
            stem_hit |= rows
            note[rows] = "type resembles " + "; ".join(
                f"{c} ({', '.join(sorted(v)[:2])})" for c, v in sorted(hits.items()))
            continue
        latin = set(re.findall(r"[a-z]+", label)) & LATIN_CLASS_VOCAB
        if latin:
            latin_hit |= rows
            note[rows] = "OSM tag in the class vocabulary: " + ", ".join(sorted(latin))
    return stem_hit, latin_hit, note


# --------------------------------------------------------------------------
# suppressed classes
# --------------------------------------------------------------------------
def suppressed(d: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Rows where a class predicate fired and the rule then removed the class.

    Re-runs the two suppression steps of `classify()` -- `TYPE_VETO` and
    `NAME_ONLY_FORBIDDEN` -- against the module's live constants, so an entry
    added to either list shows up here without this script being touched.
    """
    typ = d["type_orig"].fillna("").astype(str).map(tx.norm_type)
    name = d["name_orig"].fillna("").astype(str).map(tx.norm_type)

    veto = pd.Series(False, index=d.index)
    for cls, vetos in tx.TYPE_VETO.items():
        stems = tx.TYPE_STEMS[cls]
        if not stems:
            continue
        fired = tx._has(typ, *stems) | tx._has(name, *stems)
        bad = pd.Series(False, index=d.index)
        for v in vetos:
            bad |= tx._has_literal(typ, v) | tx._has_literal(name, v)
        veto |= fired & bad & ~d[f"is_{cls}"]

    forbidden = pd.Series(False, index=d.index)
    for cls, labels in tx.NAME_ONLY_FORBIDDEN.items():
        stems = tx.TYPE_STEMS[cls]
        if not stems:
            continue
        by_name = tx._has(name, *stems)
        bad = typ.isin({tx.norm_type(x) for x in labels})
        forbidden |= by_name & bad & ~d[f"is_{cls}"]
    return veto, forbidden


def conflict_view(d: pd.DataFrame) -> pd.DataFrame:
    """Rows where `category_orig` and `type_orig`/`name_orig` do not agree.

    Same device as in `scripts/audit_sample_2022.py`: `classify()` re-run over a
    copy with `category_orig` blanked shows what the record says without the
    category, and the two are then compared.  Uses the module's public entry
    point so it follows further edits to the rule.
    """
    blanked = d.copy()
    blanked["category_orig"] = ""
    free = tx.classify(blanked)

    cat_class = d["category_orig"].fillna("").map(
        {v: c for c, vals in tx.CATEGORY_OF.items() for v in vals})
    has_cat = cat_class.notna()

    # The mask is the module's own `overridden()`, so this reason and the
    # module's `assert_override_is_narrow()` guard cannot drift apart; the loop
    # only recovers *which* class disagreed, for the note.
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

    corroborated = pd.Series(False, index=d.index)
    for c in tx.CLASSES:
        corroborated |= has_cat & (cat_class == c) & free[f"is_{c}"]
    uncorroborated = has_cat & ~corroborated & ~other

    note = pd.Series("", index=d.index)
    note[other] = ("category_orig says " + cat_class[other].map(tx.CLASS_EN)
                   + ", type/name say " + said[other].str.rstrip("|"))
    note[uncorroborated] = (
        "category_orig says " + cat_class[uncorroborated].map(tx.CLASS_EN)
        + " and nothing else in the record supports it")
    return pd.DataFrame({"conflict_class": other,
                         "conflict_uncorroborated": uncorroborated,
                         "conflict_note": note}, index=d.index)


# --------------------------------------------------------------------------
def build(d: pd.DataFrame) -> pd.DataFrame:
    old = v3.recode_2022(d)
    conflict = conflict_view(d)
    ev = [f"{c}_evidence" for c in tx.CLASSES]

    stem_hit, latin_hit, near_note = near_miss(d)
    veto, forbidden = suppressed(d)

    flags = {
        "near_miss_type_stem": stem_hit,
        "near_miss_type_latin": latin_hit,
        "category_type_conflict": conflict["conflict_class"],
        "name_only_evidence": (d[ev] == "name").any(axis=1),
        "sport_correction_drop": ((old == "Sport") & ~d["is_sport"]
                                  & ~d["is_sport_retail"]),
        "sport_retail": d["is_sport_retail"],
        "category_uncorroborated": conflict["conflict_uncorroborated"],
        "multi_label": d["n_classes"] >= 2,
        "veto_suppressed": veto,
        "name_forbidden_suppressed": forbidden,
    }
    queued = pd.Series(False, index=d.index)
    for m in flags.values():
        queued |= m

    flags["industrial_class"] = d["is_industrial"] & queued
    flags["unbenchmarked_okrug"] = ~d["okrug_key"].isin(BENCHMARKED) & queued

    score = pd.Series(0.0, index=d.index)
    reasons = pd.Series("", index=d.index)
    why = pd.Series("", index=d.index)
    for name, mask in flags.items():
        w, text = ALL_REASONS[name]
        score += mask * w
        reasons = reasons.where(~mask, reasons + name + "|")
        why = why.where(~mask, why + text + ". ")

    q = d.loc[queued].copy()
    q["queue_score"] = score[queued].round(2)
    q["queue_reasons"] = reasons[queued].str.rstrip("|")
    q["queue_why"] = why[queued].str.strip()
    q["near_miss_note"] = near_note[queued]
    q["conflict_note"] = conflict.loc[queued, "conflict_note"]
    q["old_class_2022"] = old[queued]

    key = (q.name_orig.fillna("").astype(str) + "|"
           + q.adress_orig.fillna("").astype(str) + "|"
           + q.latitude.astype(str) + "|" + q.longitude.astype(str) + "|"
           + q.type_orig.fillna("").astype(str))
    q["object_id"] = [f"v3-{i:04d}" for i in q.index]
    q["row_hash"] = key.map(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()[:12])

    for c in ["reviewed_by", "verdict", "correct_classes", "note"]:
        q[c] = ""

    cols = (["object_id", "row_hash", "queue_score", "queue_reasons",
             "queue_why", "near_miss_note", "conflict_note", "okrug_key",
             "name_orig", "adress_orig", "latitude", "longitude",
             "category_orig", "type_orig", "old_class_2022"]
            + [f"is_{c}" for c in tx.CLASSES] + ev
            + ["is_sport_retail", "n_classes", "classes_2022",
               "reviewed_by", "verdict", "correct_classes", "note"])
    return q[cols].sort_values(
        ["queue_score", "n_classes", "okrug_key", "name_orig"],
        ascending=[False, False, True, True])


def write_csv(q: pd.DataFrame) -> None:
    body = q.astype(str)
    if body.apply(lambda col: col.str.contains("#", regex=False)).any().any():
        raise AssertionError(
            "a cell contains '#', which the comment-prefixed preamble would eat")

    pre = ["2022-taxonomy review queue -- weak-evidence objects, worst first",
           "read with: pd.read_csv(path, sep=';', encoding='utf-8-sig', comment='#')",
           "",
           "queue_score is the SUM of the weights below, over the reasons a row",
           "carries.  It is an ordering device, not a probability: there are no",
           "labels here, so nothing is calibrated and nothing is claimed to be.",
           "Work down the list; `queue_why` says why each row is on it.",
           "",
           "This queue is NOT a sample.  It is the tail of the distribution by",
           "construction, so no rate computed on it estimates anything about the",
           "city.  For that use data/processed/taxonomy_2022_audit_sample.csv.",
           "",
           "entry reasons (any one puts a row on the queue):"]
    for name, (w, text) in ENTRY_REASONS.items():
        pre.append("  %-28s %.2f  %s" % (name, w, text))
    pre += ["", "modifiers (raise a queued row, never queue one):"]
    for name, (w, text) in MODIFIERS.items():
        pre.append("  %-28s %.2f  %s" % (name, w, text))
    pre += ["",
            "verdict: fill in `keep`, `drop`, `add` or `?`, put the classes you",
            "judge correct in `correct_classes` (pipe-separated, English names as",
            "in classes_2022), and say why in `note`.  Do not use the character",
            "that starts these lines."]

    buf = io.StringIO()
    for line in pre:
        buf.write(("# " + line).rstrip() + "\n")
    q.to_csv(buf, sep=";", index=False, lineterminator="\n")
    PROC.mkdir(parents=True, exist_ok=True)
    OUT_CSV.write_text(buf.getvalue(), encoding="utf-8-sig")


def summary(d: pd.DataFrame, q: pd.DataFrame) -> str:
    out = io.StringIO()

    def P(*a):
        print(*a, file=out)

    P("2022-taxonomy review queue")
    P("source : %s (%d objects)" % (tx.V3_CSV.name, len(d)))
    P("queued : %d objects (%.1f %% of the city)" % (len(q), 100 * len(q) / len(d)))
    P("output : %s" % OUT_CSV.name)
    P("")
    P("=== reasons, by how many rows carry them ===")
    P("%-28s %6s %6s  %s" % ("reason", "weight", "rows", "kind"))
    for name, (w, _) in ALL_REASONS.items():
        n = int(q["queue_reasons"].str.split("|").map(lambda r: name in r).sum())
        P("%-28s %6.2f %6d  %s"
          % (name, w, n, "entry" if name in ENTRY_REASONS else "modifier"))
    P("")
    P("=== score distribution ===")
    for score, n in q["queue_score"].value_counts().sort_index(ascending=False).items():
        P("  %.2f  %4d" % (score, n))
    P("")
    P("=== the near-miss types, which is where a new defect would be ===")
    nm = q[q["queue_reasons"].str.contains("near_miss")]
    P("%d objects over %d distinct type labels."
      % (len(nm), nm["type_orig"].nunique()))
    P("%-34s %6s  %s" % ("type_orig", "rows", "resembles"))
    for t, n in nm["type_orig"].value_counts().items():
        note = nm.loc[nm["type_orig"] == t, "near_miss_note"].iloc[0]
        P("%-34s %6d  %s" % (str(t)[:34], n, note[:80]))
    P("")
    latin_stems = [s for s in tx.AUDIT_STEMS if re.search(r"[a-z]", s)]
    n_latin_rows = int(
        d.type_orig.fillna("").str.contains(r"[A-Za-z]", regex=True).sum())
    P("`AUDIT_STEMS` holds %d stems, %d of them Latin, against %d export rows"
      % (len(tx.AUDIT_STEMS), len(latin_stems), n_latin_rows))
    P("carrying a Latin OSM tag in `type_orig`.  Splitting the rows above by why")
    P("the module's guard does not raise them:")
    P("")
    exempt, unseen = 0, 0
    ex_labels, un_labels = [], []
    for t, n in nm["type_orig"].value_counts().items():
        norm = tx.norm_type(t)
        if tx._type_key(t) in tx.GUARD_EXEMPT_TYPES:
            exempt += n
            ex_labels.append((str(t), n))
        elif not any(s in norm for s in tx.AUDIT_STEMS):
            unseen += n
            un_labels.append((str(t), n))
    P("  exempted by decision (GUARD_EXEMPT_TYPES) : %4d rows" % exempt)
    for t, n in ex_labels:
        P("      %-34s %4d" % (t[:34], n))
    P("  carry no AUDIT_STEMS stem at all          : %4d rows" % unseen)
    for t, n in un_labels:
        P("      %-34s %4d" % (t[:34], n))
    P("")
    P("The first group is not a defect: the module holds those types out")
    P("deliberately, pending the §8.1 question of whether `Магазины` means food")
    P("retail or retail at large, and sends them here.  They are the rows that")
    P("flip if the 2022 authors answer `retail at large`.")
    P("The second group is the residual gap -- a tag no stem in the module")
    P("describes.  That is where a further defect of the D1 family would sit.")
    P("")
    P("=== top of the queue ===")
    P(q.head(20)[["object_id", "queue_score", "okrug_key", "name_orig",
                  "type_orig", "classes_2022"]].to_string(index=False))
    P("")
    P("=== by okrug ===")
    tab = pd.DataFrame({"queued": q.groupby("okrug_key").size(),
                        "objects": d.groupby("okrug_key").size()})
    tab["share_%"] = (100 * tab["queued"] / tab["objects"]).round(1)
    P(tab.sort_values("queued", ascending=False).to_string())
    P("")
    P("=== effort ===")
    P("%d objects x 2 min = %.1f h to clear the whole queue." % (len(q), len(q) * 2 / 60))
    for cut in (0.95, 0.80, 0.55):
        n = int((q["queue_score"] >= cut).sum())
        P("  score >= %.2f : %4d objects, %.1f h" % (cut, n, n * 2 / 60))
    P("")
    P("=== what this queue is not ===")
    P("- Not a sample.  It is the weak-evidence tail, selected on the outcome")
    P("  being reviewed, so no rate computed on it estimates a city rate.")
    P("- Not a measurement of the rule.  That is the audit sample's job;")
    P("  see docs/taxonomy_2022_audit_protocol.md.")
    P("- Not a fix.  A verdict recorded here changes nothing until someone")
    P("  carries it into src/arkhinfra/taxonomy_2022.py and re-runs the build.")
    return out.getvalue()


def main() -> int:
    d = tx.load_export().reset_index(drop=True)
    if len(d) != 7263:
        raise AssertionError(f"expected 7,263 export rows, got {len(d)}")
    q = build(d)
    write_csv(q)
    txt = summary(d, q)
    OUT_TXT.write_text(txt, encoding="utf-8")
    print(f"wrote {OUT_CSV.name} ({len(q)} rows) and {OUT_TXT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
