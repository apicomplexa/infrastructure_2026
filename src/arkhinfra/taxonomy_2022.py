"""Seven independent 2022-taxonomy flags over the city-wide export.

`v3_common.recode_2022()` answers "which *one* 2022 class is this object?" by
resolving seven predicates through `np.select`, whose priority order silently
discards every further class an object belongs to.  The 2022 commission asks the
other question -- *which of the seven lists would this object appear on* -- so
this module emits seven booleans and never collapses them.

Kept **separate from `v3_common.py`** on the same principle as `basecheck.py`,
`egais.py` and `v4_common.py`: three rendered v3 reports carry the numbers the
old rule produces, and three defects fixed here move those numbers city-wide.
What is shared is imported, never copied.

The three defects, all found on the 84 % of the export that no evaluation in
`docs/classifier_design.md` reaches (see its section 10):

**D1 -- `Овощи и фрукты` recoded to `Other`, 51 objects.**  `GROCERY_TYPES` holds
the 2022 spelling `фрукты-овощи`; the 2026 export writes the same two words in
the other order, and `Series.isin` is exact equality.  Fixed generally rather
than by adding the one string: a type is matched on its *bag of significant
words* (`_type_key`), so word order, separator, case and yo/ye stop mattering.
This is the third member of the family the repository already documents -- the
`GROCERY_TYPES` case mismatch and `табак` vs `табач-` are the other two -- and
`assert_no_missed_types()` exists so there is no fourth.

**D2 -- roughly 30 % of the `Sport` class was not a sport facility.**  The old
rule searches a blob that *includes `category_orig`* for the stem `спорт`, and
the category `Досуг и спорт` therefore carried 63 saunas into the sport class;
the 2022 benchmark itself labels a sauna `Общепит`.  Here every stem test runs
on `type_orig` and `name_orig` only, categories are matched exactly, and sport
retail (`Спортивный магазин`) gets its own flag -- a shop is not a facility.

**D3 -- 35 rows of the export carry the wrong `type_orig`.**  These were first
read, in section 10 of the design document, as 35 grocery shops made invisible by
`np.select` putting Tobacco first.  That reading is wrong and is corrected here.
The 35 rows pair `category_orig = Точки продажи табака` with
`type_orig = Продуктовый магазин`, and their names settle it -- Азбука дыма,
SmokeArh, Дымный папа, Kiss My Vape.  They are tobacco and vape shops with a
wrong type, never groceries.  The old rule's priority order returned the right
answer for them by accident, which is what kept the defect hidden; seven
independent flags exposed it by making them grocery shops as well.

The fix is the hierarchy this module already declares: when `category_orig`
exactly names one of the seven classes, that assertion outranks anything inferred
from `type_orig` or the fascia, so a `type`- or `name`-level flag for a
*different* class is suppressed.  Exactly 35 rows are affected at type level.
What the case really shows is that `type_orig` is unreliable on a known slice of
the export, and the review queue carries those rows.

Every flag ships with an **evidence** column naming the field that carried the
object into the class -- `category` (the export says so), `type` (the object's
kind implies it) or `name` (only the fascia suggests it).  Nothing else in this
repository lets a report say what a class count rests on, and `name` evidence is
what the manual-review queue is built from: `Industrial` is almost entirely
`name`, which is why its objects include a hostel and a jewellery shop.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from .paths import V3_CSV  # noqa: F401
from .v3_common import norm_okrug

# --------------------------------------------------------------------------
# the seven classes
# --------------------------------------------------------------------------
CLASSES = ["medical", "sport", "grocery", "catering",
           "alcohol", "tobacco", "industrial"]

CLASS_EN = {
    "medical": "Medical", "sport": "Sport", "grocery": "Grocery shops",
    "catering": "Catering", "alcohol": "Alcohol shops",
    "tobacco": "Tobacco outlets", "industrial": "Industrial",
}
CLASS_RU_2022 = {
    "medical": "Медицинские организации", "sport": "Спортивные объекты",
    "grocery": "Магазины", "catering": "Общепит",
    "alcohol": "Спецмагазины алкоголя", "tobacco": "Точки продажи табака",
    "industrial": "Пром. Объекты",
}

# Strongest first.  A row's evidence is the strongest field that fired.
EVIDENCE_ORDER = ["category", "type", "name"]

# --------------------------------------------------------------------------
# type normalisation -- the general form of D1
# --------------------------------------------------------------------------
# Words that carry no discriminating power inside a type label, so that
# "Овощи и фрукты" and "фрукты-овощи" reduce to the same key.
_STOPWORDS = {"и", "в", "на", "с", "для", "по", "the", "of"}
_WORD_RE = re.compile(r"[^0-9a-zа-я]+")


def norm_type(value) -> str:
    """Lower-case, NFC, yo -> ye, punctuation -> space, whitespace collapsed."""
    text = "" if value is None or value != value else str(value)
    s = unicodedata.normalize("NFC", text).lower().replace("ё", "е")
    return " ".join(_WORD_RE.sub(" ", s).split())


def _type_key(value) -> frozenset:
    """A type as its bag of significant words, so word order stops mattering."""
    return frozenset(w for w in norm_type(value).split() if w not in _STOPWORDS)


def _keys(labels) -> set:
    return {_type_key(x) for x in labels}


# --------------------------------------------------------------------------
# class definitions
# --------------------------------------------------------------------------
# Exact `category_orig` values.  Matched exactly, never by stem: the stem test
# is what pulled `Досуг и спорт` into sport (D2).
CATEGORY_OF = {
    "medical": {"Медицинские организации", "Реабилитация и профилактика"},
    "sport": {"Спортивные объекты"},
    "catering": {"Общепит", "фастфуд"},
    "tobacco": {"Точки продажи табака"},
    "alcohol": {"Спецмагазины алкоголя"},
    "grocery": set(),      # the export has no grocery category of its own
    "industrial": {"Пром. Объекты"},
}

# Types matched as whole labels (word-bag equality), so spelling variants of the
# same type collapse together.
GROCERY_TYPES_2022 = {
    "продуктовый магазин", "супермаркет", "фрукты-овощи", "овощи и фрукты",
    "булочная", "кулинария", "мясной магазин", "рыбный магазин",
    "молочный магазин", "гипермаркет", "продукты", "гастроном", "минимаркет",
    "универсам", "магазин: dairy", "мастерская: bakery",
    "рынок", "ярмарка", "объект: marketplace", "сыроварня",
}
SPORT_RETAIL_TYPES = {"спортивный магазин", "магазин спорттоваров"}
ALCOHOL_TYPES = {"алкогольный магазин", "винный магазин", "пивной магазин",
                 "магазин разливных напитков", "магазин: alcohol",
                 "магазин: wine", "магазин: beverages",
                 # D4.  The 2022 vocabulary spells this "магазин разливных
                 # напитков"; the export writes the bare word "Напитки", which
                 # shares no word with it, so all 53 rows were unclassified.
                 # Their names settle what they are and leave no soft-drink
                 # shop among them: Пивас и квас (14), Архипенный (12), Razliv,
                 # Beer & Honey, Кега24, Живое разливное, Пивной барон,
                 # Алко Shop.  Alcohol goes 109 -> 162 -- still far under the
                 # 442 off-trade licences in force, which is the structural
                 # undercount this repository already documents.
                 "напитки"}

# Latin-tagged types reached through an exact 2022 counterpart.  The line is
# deliberately narrow: a Latin type joins a class only where the 2022 list holds
# that same kind of shop.  `молочный магазин` and `булочная` are in it, so
# `Магазин: dairy` and `Мастерская: bakery` join grocery; `Рынок` is in it, so
# `Объект: marketplace` does; `оптика` is a 2022 medical object, so the direct
# analogue `Магазин: hearing_aids` joins medical.  Everything else Latin and
# food-shaped -- confectionery, pastry, tea, coffee, water, chocolate, honey --
# has no 2022 counterpart and stays out, listed in GUARD_EXEMPT_TYPES with its
# reason, because whether `Магазины` means food retail or retail at large is an
# open question for the authors of the 2022 study (design document, section 8.1).
MEDICAL_TYPES = {"магазин: hearing_aids"}

# `Парк`/`Сквер`/`Набережная`/`Спортивная площадка` are sport objects in the
# 2022 scheme (the benchmark lists them), reached by type rather than by stem.
SPORT_OPEN_SPACE_TYPES = {"парк", "сквер", "набережная", "пляж",
                          "спортивная площадка", "объект: park"}

# Stems matched inside `type_orig` and `name_orig` -- never inside
# `category_orig`, which is what D2 was.
TYPE_STEMS = {
    "medical": ("аптек", "поликлин", "больниц", "стоматолог", "клиник", "врач",
                "диагност", "лаборатор", "диспансер", "госпит", "медиц",
                "оптика", "реабилит", "санатор", "профилакт", "роддом",
                "родильн", "фельдшер"),
    "sport": ("спорт", "фитнес", "бассейн", "стадион", "тренаж", "воркаут",
              "каток", "манеж", "йога"),
    "catering": ("кафе", "фастфуд", "ресторан", "паб", "кофейн", "столов",
                 "закусочн", "пиццери", "суши", "бистро", "бар"),
    "alcohol": ("алкогол", "алкомаркет", "винотек"),
    "tobacco": ("табак", "табач", "вейп", "сигарет", "кальян", "vape"),
    "industrial": ("завод", "энергокомплекс", "тэц", "гэс", "фабрика",
                   "промышл", "комбинат"),
    # Deliberately empty.  Grocery is decided by the *kind* of shop and never by
    # the fascia: keying on the name would cost more than it buys.  Measured on
    # the 4,647 unclassified rows, a name-level grocery test recovers three
    # genuine objects (a kiosk named "Продукты", a "Фруктово-овощной оптовый
    # рынок", one "Пятёрочка" typed `Магазин: yes`) while a chain-name test
    # would wrongly admit 26 "Магнит Косметик", which is a drugstore. The three
    # are reachable through the review queue instead.
    "grocery": (),
}

# How each stem is matched.  The default is **word-prefix**: a stem matches only
# at the start of a word, because plain substring search is how the old rule put
# nine passport offices (па-спорт-ный стол) and seven haulage firms
# (тран-спорт-ная компания) into the sport class, and three pawnshops
# (лом-бар-д) into catering.
#
#   "infix"  -- match anywhere: Северодвинский мясо-комбинат, 29 лесо-завода.
#   "word"   -- match a whole word: "бар" must not fire on Барс or Баренц.
STEM_MODE = {
    "завод": "infix", "комбинат": "infix", "фабрика": "infix",
    "бар": "word", "паб": "word", "суши": "word", "тэц": "word",
    "гэс": "word", "vape": "word", "оптика": "word",
}
_LETTER = "а-яa-z"


def _stem_pattern(stem: str) -> str:
    mode = STEM_MODE.get(stem, "prefix")
    if mode == "infix":
        return re.escape(stem)
    if mode == "word":
        return rf"(?<![{_LETTER}]){re.escape(stem)}(?![{_LETTER}])"
    return rf"(?<![{_LETTER}]){re.escape(stem)}"


# Stems that look like a class but cannot be one.  Each entry is a demonstrated
# false positive, not a guess.
TYPE_VETO = {
    # "парк" is a substring of "автопарк" and "парковка"; a car park is not a
    # sport object.
    "sport": ("автопарк", "парковка", "технопарк", "автостоянка",
              # "бассейновое водное управление" is a river-basin authority
              "бассейнов"),
    # "бар" is a substring of "барбершоп" and "барокамера"; "кафе" is a word
    # prefix of "кафедра", which put two university departments of the medical
    # school into catering.
    "catering": ("барбершоп", "барокамер", "барахолк", "кафедр"),
    # a veterinary clinic is not human health infrastructure.
    "medical": ("ветеринар", "veterinary"),
}

# `type_orig` values that can never be a facility of the class, whatever the
# fascia says.  These are the types the old rule's name-substring hits landed on.
NAME_ONLY_FORBIDDEN = {
    "sport": {"магазин: lottery", "магазин: ticket", "магазин: mall",
              "полиция", "магазин: newsagent"},
}


def _has(series: pd.Series, *subs: str) -> pd.Series:
    """True where any stem matches, each under its own mode from STEM_MODE."""
    out = pd.Series(False, index=series.index)
    for sub in subs:
        out |= series.str.contains(_stem_pattern(sub), na=False, regex=True)
    return out


def _has_literal(series: pd.Series, *subs: str) -> pd.Series:
    out = pd.Series(False, index=series.index)
    for sub in subs:
        out |= series.str.contains(sub, na=False, regex=False)
    return out


# --------------------------------------------------------------------------
# the rule
# --------------------------------------------------------------------------
def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Seven flags and seven evidence columns for every row of `df`.

    Returns a frame indexed like `df` carrying `is_<class>` (bool) and
    `<class>_evidence` (`category` | `type` | `name` | `""`) for each class,
    plus `n_classes`, `is_sport_retail` and `classes_2022`.
    """
    cat = df["category_orig"].fillna("").astype(str)
    typ_raw = df["type_orig"].fillna("").astype(str)
    typ = typ_raw.map(norm_type)
    name = df["name_orig"].fillna("").astype(str).map(norm_type)
    tkey = typ_raw.map(_type_key)

    grocery_keys = _keys(GROCERY_TYPES_2022)
    retail_keys = _keys(SPORT_RETAIL_TYPES)
    open_keys = _keys(SPORT_OPEN_SPACE_TYPES)
    alcohol_keys = _keys(ALCOHOL_TYPES)
    medical_keys = _keys(MEDICAL_TYPES)

    is_sport_retail = tkey.map(lambda k: k in retail_keys)

    # When `category_orig` exactly names one of the seven 2022 classes, that is
    # the export asserting what the object is, and it outranks anything inferred
    # from `type_orig` or the fascia.  Without this, 35 tobacco and vape shops
    # (Азбука дыма, SmokeArh, Дымный папа) also count as grocery shops, because
    # the export gives each of them `type_orig = Продуктовый магазин` while its
    # category says `Точки продажи табака`.  They are not groceries with a
    # tobacco counter; their type is simply wrong.
    #
    # Measured cost of the rule: 42 flags suppressed in the whole export, and no
    # object loses its only class.  35 are that tobacco case; 5 are a fascia hit
    # on `Industrial` (ПиццаФабрика, «Амбулатория посёлка 29 лесозавода»),
    # which is right.  Two are arguable and are in the review queue: the
    # «Архангельский центр лечебной физкультуры и спортивной медицины», which
    # loses `sport` while keeping `medical`, and a bar named «Алкомаркет», which
    # loses `alcohol` while keeping `catering`.
    named_class = cat.map({v: c for c, vals in CATEGORY_OF.items() for v in vals})

    out = {}
    for c in CLASSES:
        by_cat = cat.isin(CATEGORY_OF[c])

        stems = TYPE_STEMS[c]
        by_type = _has(typ, *stems) if stems else pd.Series(False, index=df.index)
        by_name = _has(name, *stems) if stems else pd.Series(False, index=df.index)

        if c == "grocery":
            by_type = by_type | tkey.map(lambda k: k in grocery_keys)
        if c == "alcohol":
            by_type = by_type | tkey.map(lambda k: k in alcohol_keys)
        if c == "medical":
            by_type = by_type | tkey.map(lambda k: k in medical_keys)
        if c == "sport":
            # a sports shop is retail, not a facility
            by_type = (by_type | tkey.map(lambda k: k in open_keys)) & ~is_sport_retail
            by_name = by_name & ~is_sport_retail

        for veto in TYPE_VETO.get(c, ()):
            bad = _has_literal(typ, veto) | _has_literal(name, veto)
            by_type &= ~bad
            by_name &= ~bad

        forbidden = NAME_ONLY_FORBIDDEN.get(c)
        if forbidden:
            bad = typ.isin({norm_type(x) for x in forbidden})
            by_name &= ~bad

        # The export contradicting itself: category names another class.
        contradicted = named_class.notna() & (named_class != c)
        by_type &= ~contradicted
        by_name &= ~contradicted

        ev = np.select([by_cat, by_type, by_name],
                       ["category", "type", "name"], default="")
        out[f"is_{c}"] = by_cat | by_type | by_name
        out[f"{c}_evidence"] = ev

    res = pd.DataFrame(out, index=df.index)
    res["is_sport_retail"] = is_sport_retail
    flags = res[[f"is_{c}" for c in CLASSES]]
    res["n_classes"] = flags.sum(axis=1).astype(int)
    res["classes_2022"] = flags.apply(
        lambda r: "|".join(CLASS_EN[c] for c in CLASSES if r[f"is_{c}"]), axis=1)
    res["classes_2022"] = res["classes_2022"].replace(
        "", "Other (outside 2022 scheme)")
    return res


def load_export() -> pd.DataFrame:
    """The city-wide export (7,263 x 22) with the seven flags attached."""
    df = pd.read_csv(V3_CSV, sep=";", encoding="utf-8-sig", low_memory=False)
    df["okrug_key"] = df["district_orig"].map(norm_okrug)
    return pd.concat([df, classify(df)], axis=1)


# --------------------------------------------------------------------------
# guards -- so there is no fourth member of the D1 family
# --------------------------------------------------------------------------
# Stems that, appearing in a `type_orig` that ended up in no class at all, mean
# a class definition has a spelling hole rather than the object being genuinely
# outside the taxonomy.
AUDIT_STEMS = (
    # Cyrillic
    "продукт", "овощ", "фрукт", "хлеб", "пекарн", "мясн", "рыбн",
    "молоч", "гастроном", "минимаркет", "универсам", "бакале", "рынок",
    "ярмарк", "аптек", "медиц", "поликлин", "стоматолог", "спорт", "стадион",
    "бассейн", "фитнес", "табач", "табак", "вейп", "алкогол", "винотек",
    "кафе", "ресторан", "столов", "кофейн",
    # D4 was invisible to this guard because none of the stems above appears in
    # the type `Напитки`.  These close that hole.
    "напит", "пив", "разлив", "квас",
    # The guard was also blind by construction to the other half of the
    # vocabulary: 1,889 rows carry a Latin OSM tag in `type_orig`, and every
    # stem above is Cyrillic.
    "confectionery", "pastry", "bakery", "dairy", "greengrocer", "supermarket",
    "convenience", "marketplace", "butcher", "seafood", "deli", "food",
    "alcohol", "wine", "beverages", "beer", "tobacco", "cigarette", "vape",
    "pharmacy", "chemist", "optician", "hearing_aids", "doctors", "clinic",
    "hospital", "sports", "fitness", "swimming", "stadium",
    "cafe", "restaurant", "fast_food", "pub",
    "tea", "coffee", "water", "chocolate", "honey")


# Types that carry an in-taxonomy stem yet belong in no class *by decision*, so
# the guard must not report them.  Each one needs a reason in this comment.
GUARD_EXEMPT_TYPES = _keys({
    "спортивный магазин",        # retail, carried by is_sport_retail (D2)
    "магазин спорттоваров",      # ditto
    "досуг: sauna",              # a sauna is not a sport facility (D2)
    # Latin food-shaped types with no counterpart in the 2022 list.  Kept out
    # deliberately, not by oversight: `Магазины` holds Продуктовый магазин,
    # Супермаркет, Фрукты-овощи, Кулинария, Рынок, Ярмарка and Сыроварня, and a
    # tea or chocolate boutique is none of those.  Whether the class means food
    # retail or retail at large is the open question in section 8.1 of the
    # design document; until its authors answer, these stay out and sit in the
    # review queue.  Together they are 63 objects.
    "магазин: confectionery", "мастерская: confectionery", "магазин: pastry",
    "магазин: tea", "магазин: coffee", "магазин: water",
    "магазин: chocolate", "магазин: honey",
})


def missed_types(df: pd.DataFrame, flags: pd.DataFrame | None = None) -> pd.Series:
    """`type_orig` values in no class whose spelling suggests they belong in one."""
    flags = classify(df) if flags is None else flags
    unclassified = df.loc[flags["n_classes"] == 0, "type_orig"].fillna("")
    keep = unclassified.map(
        lambda t: any(s in norm_type(t) for s in AUDIT_STEMS)
        and _type_key(t) not in GUARD_EXEMPT_TYPES)
    return unclassified[keep].value_counts()


# The `category_orig` override reverses D3, so its reach is pinned the way
# `assert_no_missed_types()` pins D1: it is a narrow correction of a known defect,
# and if it ever starts suppressing a materially larger share of the export, that
# is a change of behaviour and not a silent one.
OVERRIDE_MAX_SHARE = 0.01


def overridden(df: pd.DataFrame) -> pd.Series:
    """Rows where `category_orig` names a class and outranks a weaker signal."""
    cat = df["category_orig"].fillna("").astype(str)
    named = cat.map({v: c for c, vals in CATEGORY_OF.items() for v in vals})
    typ = df["type_orig"].fillna("").astype(str)
    name = df["name_orig"].fillna("").astype(str).map(norm_type)
    tkey = typ.map(_type_key)
    typn = typ.map(norm_type)
    hit = pd.Series(False, index=df.index)
    for c in CLASSES:
        stems = TYPE_STEMS[c]
        by = _has(typn, *stems) | _has(name, *stems) if stems else pd.Series(False, index=df.index)
        if c == "grocery":
            by |= tkey.map(lambda k: k in _keys(GROCERY_TYPES_2022))
        if c == "alcohol":
            by |= tkey.map(lambda k: k in _keys(ALCOHOL_TYPES))
        hit |= by & named.notna() & (named != c)
    return hit


def assert_override_is_narrow(df: pd.DataFrame) -> None:
    n = int(overridden(df).sum())
    if n > OVERRIDE_MAX_SHARE * len(df):
        raise AssertionError(
            f"the category_orig override now suppresses {n} of {len(df)} rows "
            f"({n / len(df):.1%}), above the {OVERRIDE_MAX_SHARE:.0%} this "
            "correction was sized for -- re-check it against the 35 mistyped "
            "tobacco rows it exists for before raising the bound")


def assert_no_missed_types(df: pd.DataFrame,
                           flags: pd.DataFrame | None = None) -> None:
    miss = missed_types(df, flags)
    if len(miss):
        raise AssertionError(
            "type_orig values fell outside every class but carry an in-taxonomy "
            f"stem -- a class definition has a spelling hole:\n{miss.to_string()}")
