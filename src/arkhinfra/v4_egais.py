"""Join the fourth-delivery risk layer (data/raw_v4) to the FSRAR licence registry.

The question this module answers is object-level rather than aggregate: for each
v4 record, *is there a real alcohol licence at this address*, is it in force, and
what does the registry say about it.  `v4_common.corroboration()` already answers
the aggregate version (what share of the layer sits near a licensed outlet); it
deliberately stops at a nearest-neighbour distance and never names a licence.

**The matching rule itself no longer lives here.**  It is `packages/licmatch`, a
standalone package with no knowledge of this study, its paths or its column
names -- toponym parsing, the three-term score, the two floors, the two routes,
selection and the distinct-key tallies.  Its methodology write-up is
`packages/licmatch/docs/METHODOLOGY.md` and its tests run with
`pixi run licmatch-test`.

What is left here is everything that *is* about this study, and only that:

* the two adapters that turn the v4 export and the registry extract into the
  package's canonical sides (`prepare_v4()` / `prepare_egais()`);
* the licence columns written onto the export (`LICENCE_FIELDS`, `enrich()`);
* what a matched licence is evidence *of*, which is a question about alcohol,
  tobacco and Russian retail counters, not about record linkage
  (`licence_evidence()`);
* the summary tables the runner and the report read.

Kept separate from `v4_common.py` and `egais.py` on the same principle those two
follow: the rendered reports must keep producing what they produced before.  What
is shared is imported, never copied.

Two things about the registry govern the join:

* **It licenses alcohol, not tobacco.**  A licence found against a tobacco row
  means the object also holds an alcohol licence -- never that the tobacco tag is
  corroborated.  `enrich()` fills the licence columns for both layers; reading
  them as tobacco evidence is a mistake the data cannot stop.
* **It is a register, not a list of open outlets.**  Only 585 of the 2,100 city
  rows are in force, and coordinates are plausible on 53 % of rows overall but on
  98 % of the *active retail* ones.  Rows without coordinates can therefore never
  be reached by the 100 m rule, and are matched by the package's deliberately
  strict address-only route (`METHOD_ADDR`), whose matches stay labelled as such.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .egais import ACTIVITY_EN, load_egais  # noqa: F401
from .paths import PROC, ensure_licmatch_path  # noqa: F401
from .v4_common import load_v4  # noqa: F401

ensure_licmatch_path()

import licmatch as lm  # noqa: E402
from licmatch import (Toponym, address_score, house_similarity,  # noqa: E402,F401
                      street_similarity)

# The city every address in this study shares; the package drops it in all its
# spellings rather than scoring it.
CITY = lm.home_city_re("Архангельск")

# --------------------------------------------------------------------------
# tunables -- this study's settings of the package's parameters
# --------------------------------------------------------------------------
# The calibrated defaults are the package's own (see its METHODOLOGY §13); they
# are restated as module constants because the runner's --help, the Russian
# report and docs/v4_egais_match.md all quote them by name.
PARAMS = lm.DEFAULTS

W_ADDR, W_NAME, W_DIST = PARAMS.weights
MAX_M = PARAMS.max_m           # the distance cut the whole join is built on
ACCEPT = PARAMS.accept         # combined-score floor
STRONG = PARAMS.strong         # reported separately, the tier that needs no argument
ADDR_MIN = PARAMS.addr_min     # floor on the address term alone
ADDR_ROUTE_STREET = PARAMS.addr_route_street
ADDR_ROUTE_HOUSE = PARAMS.addr_route_house

METHOD_GEO = lm.ROUTE_NAMES[lm.ROUTE_GEO]
METHOD_ADDR = lm.ROUTE_NAMES[lm.ROUTE_ADDR]

# `licence_status` describes the licence *this object* was given, never merely
# what the address holds -- the per-address tallies (`licence_n_*`) do that.
STATUS_ACTIVE = "Active"          # its own licence, in force
STATUS_ARCHIVED = "Archived"      # its own licence, expired / terminated / annulled
# A licence of the right kind sits at the address, but its outlet went to
# another object with the stronger claim (`licence_claimed_by` names it).  One
# licensed outlet is one counter; five shops in a building cannot all hold it.
STATUS_TAKEN = "Taken"
# The address holds only licences of the other trade -- a shop licence where
# the object is a bar, or the reverse, or a wholesale / production one.  Such a
# licence does not permit what the object is tagged with.
STATUS_OTHER_TRADE = "Other trade"
# The address holds licences of the right trade, but each belongs to a known
# chain other than the object's own -- a Бристоль standing where only Тандер
# holds a licence (`brand_conflict`).
STATUS_OTHER_CHAIN = "Other chain"
# Never the bare string "None": pandas reads that back as NaN, and this column
# is meant to survive a round trip through the CSV it is written to.
STATUS_NONE = "Not in registry"

STATUS_ORDER = [STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_TAKEN, STATUS_OTHER_CHAIN,
                STATUS_OTHER_TRADE, STATUS_NONE]
# The object holds a licence of its own.
STATUS_OWN = (STATUS_ACTIVE, STATUS_ARCHIVED)
# It does not, whatever the address holds -- the queue for manual checking.
STATUS_NO_OWN = (STATUS_TAKEN, STATUS_OTHER_CHAIN, STATUS_OTHER_TRADE, STATUS_NONE)

# The operator -> fascia table the name term needs.  It ships with the package
# (`licmatch.RU_RETAIL_ALIASES`) because it is a property of Russian retail, not
# of this study; re-exported under the name the reports and docs already use.
BRAND_ALIASES = lm.RU_RETAIL_ALIASES

# Fascia spellings that name one brand.  `brand_key()` folds only the "&";
# these are the export's own variants of one fascia, found in the data, which
# no general rule reaches: a stylised "Петр&скй" beside "Петровский", three
# spellings of Алко Shop, a chain's sub-format ("Пятёрочка Кафе с собой",
# "Магнит Опт").  Applied to the brand key only; the name term is untouched.
FASCIA_SPELLINGS = {
    "петр скй": "петровский",
    "алко shop": "алкоshop",
    "алко shoo": "алкоshop",
    "винлаб напитков": "винлаб",
    "пятерочка собой": "пятерочка",
    "магнит-опт": "магнит",
    "магнит моя цена": "магнит",
}


def fascia_brand(name_key: str) -> str:
    """A fascia's brand key: `lm.brand_key` plus the spellings above."""
    k = lm.brand_key(name_key)
    return FASCIA_SPELLINGS.get(k, k)


# A name comparison this strong says the holder *is* the shop ("Луда" /
# ООО «Луда-Старт», 0.90) -- enough to let a pair past the trade rule, and to
# let a licence of a known chain go to an object that names that chain
# without matching its fascia key.
STRONG_NAME = 0.80
# The least name agreement at which an archived licence may be quoted as an
# object's own when an in-force licence of its trade stands at the address:
# below it the archived one is the premises' previous tenant (Пятёрочка quoting
# ООО «Южанка», 2014), not the object's.
ARCHIVED_NAME_MIN = 0.60
# Records of one shop: within this distance and naming the same brand.
ENTITY_M = 50.0
ENTITY_NAME_MIN = 80.0
# Identical names this close are one record written twice, generic or not.
ENTITY_SAME_NAME_M = 5.0

# Where the name term of the chosen pair came from -- `licence_name_basis`.
NAME_MANUAL = "manual"      # the hand-kept chain table above
NAME_LEARNED = "learned"    # a pair learned from the data (`learn_brands()`)
NAME_FUZZY = "fuzzy"        # the two names compared as strings
NAME_GENERIC = "generic"    # a generic fascia; the name term is not scored

# Which licence activity permits what an object is tagged with.  An off-trade
# object needs a retail licence, an on-trade one a catering licence ("при
# оказании услуг общественного питания"); wholesale, production and transport
# licences permit neither.  The registry's own activity text decides the class
# (`egais.classify_activity`).
HOOKAH_TYPE = "Hookah lounges"

TRADE_ACTIVITY = {
    "off-trade": {ACTIVITY_EN["retail"]},
    "on-trade": {ACTIVITY_EN["catering"]},
}


def params(accept: float = ACCEPT, addr_min: float = ADDR_MIN,
           max_m: float = MAX_M, w=(W_ADDR, W_NAME, W_DIST)) -> lm.MatchParams:
    """This study's `MatchParams`, with any of the four knobs overridden."""
    return lm.MatchParams(w_addr=w[0], w_name=w[1], w_dist=w[2],
                          max_m=max_m, accept=accept, addr_min=addr_min)


# --------------------------------------------------------------------------
# the two adapters -- the only code that knows what these sources look like
# --------------------------------------------------------------------------
def parse_v4_address(v) -> Toponym:
    """"Архангельск, Ленинградский проспект, 356 к4" -> Toponym.

    The v4 layer writes the whole address on one comma-packed line.
    """
    return lm.parse_address_line(v, CITY)


def parse_egais_address(street: str, house: str, subsettlement: str = "",
                        block: str = "") -> Toponym:
    """The registry's own address fields as a Toponym.

    `outlet_street` / `outlet_house` come out of `scripts/parse_egais.py`; the
    corpus sits one slot further along the comma-packed `outlet_address`, which
    `egais_blocks()` recovers.
    """
    return lm.parse_address_fields(street, house, CITY, subsettlement, block)


def egais_blocks(addr: pd.Series) -> pd.Series:
    """The corpus slot (position 8) of the registry's comma-packed address."""
    return addr.fillna("").astype(str).str.split(",").map(
        lambda p: p[8].strip() if len(p) > 8 else "")


def norm_org_name(v) -> str:
    """The registry's holder name reduced to its distinctive part.

    'Общество с ограниченной ответственностью «ЛОЙ» Сокращенно: ООО "ЛОЙ"' -> "лой".
    """
    return lm.holder_name(v)


def norm_shop_name(v) -> str:
    """The export's fascia reduced the same way, trade descriptor removed."""
    return lm.fascia_name(v)


def prepare_v4(df: pd.DataFrame) -> pd.DataFrame:
    """The v4 export as the package's canonical side.

    A learned (fascia, holder) pair is looked up by the fascia's brand key, which
    folds the "Красное&Белое" / "Красное & Белое" spellings into one.
    """
    names = [norm_shop_name(v) for v in df["name_orig"]]
    return lm.side([parse_v4_address(v) for v in df["adress_orig"]], names,
                   df["latitude"], df["longitude"],
                   alias_keys=[fascia_brand(k) for k in names])


def org_inn(eg: pd.DataFrame) -> pd.Series:
    """The holder's tax number as text -- the identity a learned pair names."""
    return (eg["org_inn"].astype(str).str.replace(r"\.0$", "", regex=True)
            .replace({"nan": "", "<NA>": ""}))


def prepare_egais(eg: pd.DataFrame) -> pd.DataFrame:
    """The registry extract as the package's canonical side.

    Its alias key is the holder's INN rather than its name: two unrelated
    companies can both be ООО "Ритейл", and only the INN tells them apart.
    """
    blocks = egais_blocks(eg["outlet_address"])
    top = [parse_egais_address(s, h, sub, b) for s, h, sub, b in zip(
        eg["outlet_street"], eg["outlet_house"], eg["outlet_subsettlement"], blocks)]
    return lm.side(top, [norm_org_name(v) for v in eg["org_name"]],
                   eg["latitude"], eg["longitude"], alias_keys=org_inn(eg))


def _address_key(side: pd.DataFrame) -> pd.Series:
    """settlement|street|house|suffix from a prepared side; "" when unparsed."""
    key = (side["settlement"].astype(str) + "|" + side["street"].astype(str) + "|"
           + side["house"].astype(str) + "|" + side["suffix"].astype(str))
    return key.where(side["street"].astype(str) != "", "")


def outlet_units(eg: pd.DataFrame, b: pd.DataFrame | None = None) -> np.ndarray:
    """One label per licensed outlet: the holder's INN at one parsed address.

    The register files one licence at one address once per status change, and
    a chain's single licence number covers dozens of addresses; neither the row
    nor the number is the outlet.  Where the address did not parse, the raw
    outlet address stands in, so an unparsed row is still one unit, not all of
    them.
    """
    b = prepare_egais(eg) if b is None else b
    addr = _address_key(b).to_numpy(dtype=object)
    raw = eg["outlet_address"].fillna("").astype(str).to_numpy(dtype=object)
    addr = np.where(addr != "", addr, raw)
    return org_inn(eg).to_numpy(dtype=object) + "@" + addr


def site_keys(v4: pd.DataFrame, a: pd.DataFrame | None = None) -> np.ndarray:
    """One label per physical address on the export side.

    Votes for a brand are counted over distinct addresses, so two records of
    one shop (or one shop in both risk files) vote once.  The parsed address
    decides; an unparsed one falls back to the coordinate.
    """
    a = prepare_v4(v4) if a is None else a
    addr = _address_key(a).to_numpy(dtype=object)
    lat = pd.to_numeric(v4["latitude"], errors="coerce").round(5).astype(str).to_numpy(dtype=object)
    lon = pd.to_numeric(v4["longitude"], errors="coerce").round(5).astype(str).to_numpy(dtype=object)
    return np.where(addr != "", addr, lat + "," + lon)


def entities(v4: pd.DataFrame, a: pd.DataFrame | None = None) -> np.ndarray:
    """One label per shop, however many records the export gives it.

    The two risk files carry one store twice, and the tobacco file often twice
    over ("Пятёрочка" and "Пятёрочка, супермаркет" at one coordinate).  Without
    this the one-outlet rule makes a shop compete with itself.  Two records are
    one shop when they stand within ENTITY_M and name the same brand (same brand
    key, or token-set similarity >= ENTITY_NAME_MIN on non-generic keys), or
    within ENTITY_SAME_NAME_M under an identical name, generic or not.
    """
    from rapidfuzz import fuzz, process

    a = prepare_v4(v4) if a is None else a
    n = len(a)
    lat = pd.to_numeric(v4["latitude"], errors="coerce").to_numpy(float)
    lon = pd.to_numeric(v4["longitude"], errors="coerce").to_numpy(float)
    d = lm.haversine_m(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    key = a["alias_key"].to_numpy(dtype=object)
    raw = np.array([lm.fold(v) for v in v4["name_orig"]], dtype=object)
    gen = np.array([lm.is_generic(k) or len(k) < 3 for k in key], dtype=bool)
    uk, inv = np.unique(key, return_inverse=True)
    sim = np.asarray(process.cdist(list(uk), list(uk), scorer=fuzz.token_set_ratio,
                                   workers=-1))[inv][:, inv]
    same_brand = ((key[:, None] == key[None, :]) | (sim >= ENTITY_NAME_MIN)) \
        & ~gen[:, None] & ~gen[None, :]
    link = ((d <= ENTITY_M) & same_brand) | ((d <= ENTITY_SAME_NAME_M)
                                             & (raw[:, None] == raw[None, :]))
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in zip(*np.nonzero(np.triu(link, 1))):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    return np.array([find(i) for i in range(n)])


def trade_eligible(v4: pd.DataFrame, eg: pd.DataFrame) -> np.ndarray:
    """(objects x licences) mask: the licence permits what the object is tagged with."""
    trade = (v4["trade"].astype(str).to_numpy() if "trade" in v4.columns
             else np.full(len(v4), "off-trade", dtype=object)).copy()
    # A hookah lounge serves on the premises; `v4_common` types every tobacco
    # row off-trade, which would match it against shop licences.
    if "type_en" in v4.columns:
        trade = np.where(v4["type_en"].astype(str).to_numpy() == HOOKAH_TYPE,
                         "on-trade", trade)
    act = eg["activity_class"].astype(str).to_numpy()
    out = np.zeros((len(v4), len(eg)), dtype=bool)
    for t, allowed in TRADE_ACTIVITY.items():
        out[trade == t, :] = np.isin(act, list(allowed))[None, :]
    return out


def pair_score(a: Toponym, b: Toponym, name_a: str, name_b: str,
               distance_m: float | None) -> float:
    """The published formula for one pair, at this study's settings."""
    return lm.pair_score(a, b, name_a, name_b, distance_m, PARAMS)


def score_all(a: pd.DataFrame, b: pd.DataFrame,
              w=(W_ADDR, W_NAME, W_DIST), max_m: float = MAX_M) -> lm.Scores:
    """Every (v4 x licence) pair scored.

    Returns the package's `Scores`, which is subscriptable, so callers reading
    `sc["score"]` / `sc["addr"]` keep working unchanged.
    """
    return lm.score_matrix(a, b, params(max_m=max_m, w=w))


# --------------------------------------------------------------------------
# the enriched export
# --------------------------------------------------------------------------
LICENCE_FIELDS = {
    "licence_no": "licence_no",
    "licence_prev_no": "licence_prev_no",
    "licence_status_raw": "status_en",
    "licence_status_registry": "status",
    "licence_status_reason": "status_reason",
    "licence_date_issued": "date_issued",
    "licence_date_expires": "date_expires",
    "licence_status_changed": "status_changed",
    "licence_activity": "activity",
    "licence_activity_class": "activity_class",
    "licence_products": "products",
    "licence_org_name": "org_name",
    "licence_org_inn": "org_inn",
    "licence_outlet_address": "outlet_address",
    "licence_issuing_body": "issuing_body",
}

_DATE_COLS = ("licence_date_issued", "licence_date_expires", "licence_status_changed")

MATCH_FIELDS = ["licence_status", "licence_evidence", "licence_evidence_note",
                "licence_match_method", "licence_match_level",
                "licence_score", "licence_addr_score", "licence_name_score",
                "licence_name_basis", "licence_claimed_by", "licence_claim_margin",
                "licence_trade_match", "licence_outlet_id",
                "licence_distance_m", "licence_n_matched", "licence_n_active",
                "licence_n_active_retail", "licence_all_nos", "licence_active_nos"]

LEVEL_HOUSE = "house"     # both sides name the same building
LEVEL_STREET = "street"   # same street, one side writes no house number
LEVEL_HOUSE_MIN = 0.85    # the house term at which "same building" is claimed

# The tallies asked of the package, named as they appear in the output.
GROUP_MATCHED, GROUP_ACTIVE, GROUP_ACTIVE_RETAIL = "matched", "active", "active_retail"

# --------------------------------------------------------------------------
# what a matched licence is evidence *of*
# --------------------------------------------------------------------------
# The registry licenses alcohol and nothing else, so the same match means two
# different things depending on which risk layer the row came from.  For an
# alcohol row it is the licence for the very product the row is tagged with.
# For a tobacco row there is no tobacco registry to match against at all: the
# licence says the address legally sells alcohol, and Russian retail sells
# alcohol and tobacco through the same counters, so it is indirect support for
# the tobacco tag -- a probability, not a confirmation.  Nothing in this
# repository can measure how strong that co-sale link is (see the tobacco entry
# in "Known data caveats"), so the column states the inference rather than
# scoring it.
EVIDENCE_DIRECT = "direct"
EVIDENCE_PROBABLE = "probable"
EVIDENCE_WEAK = "weak"

EVIDENCE_ORDER = [EVIDENCE_DIRECT, EVIDENCE_PROBABLE, EVIDENCE_WEAK]

EVIDENCE_NOTE = {
    EVIDENCE_DIRECT:
        "Прямое подтверждение: ЕГАИС лицензирует именно алкоголь — тот "
        "продукт, которым размечен объект. Статус лицензии см. в licence_status.",
    EVIDENCE_PROBABLE:
        "Вероятное подтверждение (косвенное): табачного реестра в ЕГАИС не "
        "существует. Объект сам держит действующую розничную алкогольную "
        "лицензию, а алкоголь и табак в рознице продаются через один и тот же прилавок, "
        "поэтому лицензия косвенно поддерживает табачную метку, но не "
        "подтверждает продажу табака.",
    EVIDENCE_WEAK:
        "Слабое подтверждение: собственная лицензия объекта архивная или "
        "нерозничная (действующие лицензии по адресу, если есть, закреплены за "
        "другими объектами), поэтому даже косвенный довод в пользу продажи "
        "табака здесь не работает.",
    "": "",
}

# The layer whose product the registry actually licenses.
DIRECT_RISK = "Alcohol"


def licence_evidence(risk: pd.Series, matched: np.ndarray,
                     n_active_retail: np.ndarray) -> pd.Series:
    """`direct` / `probable` / `weak` per row -- see the note above.

    A tobacco row is `probable` only while the object itself holds a *retail*
    alcohol licence in force: an archived one, or a wholesale/production/
    transport one, says nothing about a counter selling cigarettes today, and
    one held by the shop next door says nothing about this counter.
    """
    risk = risk.reset_index(drop=True).astype(str)
    kind = np.where(risk.eq(DIRECT_RISK), EVIDENCE_DIRECT,
                    np.where(n_active_retail > 0, EVIDENCE_PROBABLE, EVIDENCE_WEAK))
    return pd.Series(np.where(matched, kind, ""), dtype=object)


# --------------------------------------------------------------------------
# brands learned from the data
# --------------------------------------------------------------------------
# The layer brands are learned from.  Tobacco rows are left out on purpose: a
# tobacco kiosk inside a supermarket stands at the supermarket's licence every
# time, which is exactly the co-location the vote must not mistake for
# ownership, and the tobacco layer is full of such kiosks.
BRAND_LEARN_RISK = "Alcohol"

# Decisions on learned pairs that the counts alone cannot make, keyed by
# (brand key, INN).  "reject" drops an accepted pair, "accept" admits one the
# thresholds refused; the reason is carried into the brand table.  Every entry
# must say why -- this is the one place a learned pair is overruled by hand.
BRAND_REVIEW: dict[tuple[str, str], tuple[str, str]] = {}

REVIEW_ACCEPT, REVIEW_REJECT = "accept", "reject"


def learn_brands(v4: pd.DataFrame, eg: pd.DataFrame, max_m: float = MAX_M,
                 brand_params: lm.BrandParams = lm.BRAND_DEFAULTS) -> lm.BrandResult:
    """(fascia, holder INN) pairs learned from the alcohol layer.

    Scored on the address and distance terms only, reweighted to keep their
    ratio -- the name term would bring the answer in with it.  Only pairs whose
    licence permits the object's trade take part, so a bar never votes for the
    shop licence in its building.  The package does the learning
    (`licmatch.learn_brands`); `BRAND_REVIEW` is then applied, and the table
    gains:

    * `active_sites` -- at how many of the addresses that voted for the pair the
      holder's licence is in force.  A pair resting on archived licences alone
      (Дисма -> Конус: every one of Конус's outlets expired by 2016) says who
      traded there once; it may name the pair but must not bar anyone from an
      in-force licence today, so `feeds_conflict` is False for it.
    * `review` / `review_reason` / `used`.
    """
    mask = (v4["risk"].astype(str) == BRAND_LEARN_RISK).to_numpy() \
        if "risk" in v4.columns else np.ones(len(v4), dtype=bool)
    sub = v4.loc[mask].reset_index(drop=True)
    a, b = prepare_v4(sub), prepare_egais(eg)
    w_sum = W_ADDR + W_DIST
    p = params(max_m=max_m, w=(W_ADDR / w_sum, 0.0, W_DIST / w_sum))
    sc = lm.score_matrix(a, b, p)
    ok = lm.accepted(sc, p) & trade_eligible(sub, eg)
    strength = np.where(ok, np.nan_to_num(sc.score, nan=0.0), 0.0)
    sites = site_keys(sub, a)
    inn = org_inn(eg).to_numpy(dtype=object)
    res = lm.learn_brands(strength, a["alias_key"], inn,
                          sites=sites, units=outlet_units(eg, b),
                          holder_names=[lm.holder_name(v, aliases={}) for v in eg["org_name"]],
                          params=brand_params)

    t = res.table.copy()
    active = eg["is_active"].to_numpy(bool)
    fk = a["alias_key"].to_numpy(dtype=object)
    votes = res.site_votes or {}
    act_sites = []
    for f, h in zip(t["fascia"], t["holder"]):
        voted = votes.get((f, h), frozenset())
        rows = np.flatnonzero((fk == f) & np.isin(sites, list(voted)))
        cols = (inn == h) & active
        hit = ok[np.ix_(rows, np.flatnonzero(cols))].any(axis=1) if len(rows) and cols.any() \
            else np.zeros(len(rows), dtype=bool)
        act_sites.append(len(set(sites[rows[hit]])))
    t["active_sites"] = act_sites
    keys = list(zip(t["fascia"], t["holder"]))
    t["review"] = [BRAND_REVIEW.get(k, ("", ""))[0] for k in keys]
    t["review_reason"] = [BRAND_REVIEW.get(k, ("", ""))[1] for k in keys]
    t["used"] = np.where(t["review"] == REVIEW_REJECT, False,
                         np.where(t["review"] == REVIEW_ACCEPT, True, t["accepted"]))
    t["feeds_conflict"] = t["used"] & (t["active_sites"] > 0)
    pairs = frozenset((f, h) for f, h, u in zip(t["fascia"], t["holder"], t["used"]) if u)
    return lm.BrandResult(table=t, pairs=pairs, iterations=res.iterations,
                          converged=res.converged, assignment=res.assignment,
                          cycle=res.cycle, oscillating=res.oscillating,
                          site_votes=res.site_votes)


# --------------------------------------------------------------------------
# the join itself
# --------------------------------------------------------------------------
def known_holders(eg: pd.DataFrame, brands: lm.BrandResult | None
                  ) -> tuple[dict[str, set], set]:
    """(brand key -> INNs known to trade under it, franchise brand keys).

    The hand-kept chain table (`BRAND_ALIASES`, matched through the holder's
    own name) plus the learned pairs whose evidence includes an in-force
    licence (`feeds_conflict`).
    """
    out: dict[str, set] = {}
    raw = [lm.holder_name(v, aliases={}).replace("-", " ") for v in eg["org_name"]]
    for key, inn in zip(raw, org_inn(eg)):
        fascia = BRAND_ALIASES.get(key)
        if fascia and inn:
            out.setdefault(fascia_brand(fascia), set()).add(inn)
    franchise: set = set()
    if brands is not None:
        t = brands.table
        for f, h, fr in t.loc[t["feeds_conflict"], ["fascia", "holder", "franchise"]].itertuples(index=False):
            out.setdefault(f, set()).add(h)
            if fr:
                franchise.add(f)
    return out, franchise


def brand_conflict(a: pd.DataFrame, eg: pd.DataFrame, known: dict[str, set],
                   franchise: set, name: np.ndarray) -> np.ndarray:
    """(objects x licences) mask of pairs the known brands rule out, both ways.

    * **The object is a known brand**: it holds only its own holders' licences.
      A Пятёрочка is never licensed by ООО «Южанка».  A franchise (several
      operators, not all of them necessarily learned) is exempt here.
    * **The licence is a known brand's**: it goes only to an object of one of
      that holder's fascias, or to one whose name matches the holder's
      outright (`STRONG_NAME`).  A «Пивная лавка» next door does not hold
      Агроторг's licence.

    An object whose fascia is unknown meeting a licence whose holder is unknown
    is never in conflict -- the rule applies only what is already known.
    """
    inn = org_inn(eg).to_numpy(dtype=object)
    fk = a["alias_key"].to_numpy(dtype=object)
    fascias_of: dict[str, set] = {}
    for f, hs in known.items():
        for h in hs:
            fascias_of.setdefault(h, set()).add(f)
    out = np.zeros((len(a), len(eg)), dtype=bool)
    # forward: a known, non-franchise fascia takes only its own holders
    for f in pd.unique(fk):
        own = known.get(f)
        if own and f not in franchise:
            out[fk == f, :] |= ~np.isin(inn, list(own))[None, :]
    # reverse: a known holder's licence goes only to its own fascias
    for h, fs in fascias_of.items():
        cols = np.flatnonzero(inn == h)
        if not len(cols):
            continue
        foreign = ~np.isin(fk, list(fs))
        out[np.ix_(foreign, cols)] |= name[np.ix_(foreign, cols)] < STRONG_NAME
    return out


def self_vote_mask(v4: pd.DataFrame, a: pd.DataFrame, eg: pd.DataFrame,
                   brands: lm.BrandResult) -> np.ndarray:
    """(objects x licences): where a learned pair may not score its own name term.

    A pair that passes the thresholds only with every one of its voting
    addresses (`loo_accepted` False) would confirm itself at those addresses;
    there the name term falls back to the plain string comparison.  A pair a
    person accepted in `BRAND_REVIEW` is exempt.
    """
    t = brands.table
    shaky = t[t["used"] & ~t["loo_accepted"] & (t["review"] != REVIEW_ACCEPT)]
    out = np.zeros((len(a), len(eg)), dtype=bool)
    if shaky.empty:
        return out
    sites = site_keys(v4, a)
    fk = a["alias_key"].to_numpy(dtype=object)
    inn = org_inn(eg).to_numpy(dtype=object)
    votes = brands.site_votes or {}
    for f, h in zip(shaky["fascia"], shaky["holder"]):
        rows = (fk == f) & np.isin(sites, list(votes.get((f, h), ())))
        out[np.ix_(rows, inn == h)] = True
    return out


def _merge_scores(x: lm.Scores, y: lm.Scores, use_y: np.ndarray) -> lm.Scores:
    """`x` with `y`'s values wherever `use_y`."""
    f = {k: (np.where(use_y, getattr(y, k), getattr(x, k)) if getattr(x, k) is not None
             else None) for k in x.as_dict()}
    return lm.Scores(**f)


@dataclass(frozen=True)
class Join:
    """Everything one run of the join produced -- `enrich()` writes it out,
    `v4_export` reads the parts the CSV does not keep."""
    scores: lm.Scores
    sel: lm.Selection
    params: lm.MatchParams
    brands: lm.BrandResult | None
    units: np.ndarray
    trade_ok: np.ndarray          # (objects x licences) the licence permits the trade
    conflict: np.ndarray          # (objects x licences) the known brands rule it out
    eligible: np.ndarray          # (objects x licences) what may be chosen
    entities: np.ndarray          # (objects,) one label per shop


def join(v4: pd.DataFrame, eg: pd.DataFrame, accept: float = ACCEPT,
         addr_min: float = ADDR_MIN, max_m: float = MAX_M,
         w=(W_ADDR, W_NAME, W_DIST), learn: bool = True,
         exclusive: bool = True, brand_rule: bool = True) -> Join:
    """Score every pair and choose one licence per object.

    The rules, in the order they bite:

    * admission -- both floors, as before; every admitted licence counts toward
      the per-address tallies;
    * eligibility --
      - the licence permits the object's trade (`trade_eligible`), unless the
        name says the holder is the shop (alias, or string >= STRONG_NAME);
      - the known brands do not rule the pair out, either way (`brand_conflict`);
      - an archived licence is the object's own only if the name agrees
        (alias, string >= ARCHIVED_NAME_MIN, or a known holder of its fascia)
        or no in-force licence of its trade stands at the address at all;
      an object left with nothing is `Other chain` or `Other trade`;
    * preference -- a licence of the object's own trade, then one in force;
    * exclusivity -- one outlet (`outlet_units`) per shop, strongest claim
      first, across both risk layers; the records of one shop (`entities`)
      share it.  A shop that lost its outlet is `Taken`.

    `learn=False` / `exclusive=False` / `brand_rule=False` switch the three new
    rules off one at a time, which is how their effect is measured.
    """
    p = params(accept=accept, addr_min=addr_min, max_m=max_m, w=w)
    brands = learn_brands(v4, eg, max_m=max_m) if learn else None
    a, b = prepare_v4(v4), prepare_egais(eg)
    plain = lm.score_matrix(a, b, p)
    scores = plain
    if brands is not None and brands.pairs:
        aliased = lm.score_matrix(a, b, p, aliases=brands.pairs)
        scores = _merge_scores(aliased, plain, self_vote_mask(v4, a, eg, brands))

    active = eg["is_active"].to_numpy(bool)
    retail = eg["is_retail"].to_numpy(bool)
    units = outlet_units(eg, b)
    ok = lm.accepted(scores, p)
    alias = scores.name_kind == lm.NAME_ALIAS
    trade_ok = trade_eligible(v4, eg)
    trade_allowed = trade_ok | alias | (plain.name >= STRONG_NAME)

    known, franchise = known_holders(eg, brands)
    conflict = (brand_conflict(a, eg, known, franchise, plain.name) if brand_rule
                else np.zeros_like(trade_ok))
    inn = org_inn(eg).to_numpy(dtype=object)
    fk = a["alias_key"].to_numpy(dtype=object)
    own_holder = np.zeros_like(trade_ok)
    for f, hs in known.items():
        own_holder[np.ix_(fk == f, np.isin(inn, list(hs)))] = True
    live_here = (ok & active[None, :] & trade_ok).any(axis=1)
    name_agrees = alias | (plain.name >= ARCHIVED_NAME_MIN) | own_holder
    archived_ok = active[None, :] | name_agrees | ~live_here[:, None]
    eligible = trade_allowed & ~conflict & archived_ok

    ents = entities(v4, a)
    # Counted over distinct licence numbers, not registry rows: a licence that
    # was prolonged appears once per status change, and 20 rows at one address
    # can be 9 licences.
    sel = lm.select(scores, p, prefer=(trade_ok, active), keys=eg["licence_no"],
                    groups={GROUP_MATCHED: None,
                            GROUP_ACTIVE: active,
                            GROUP_ACTIVE_RETAIL: active & retail},
                    eligible=eligible,
                    units=units if exclusive else None, entities=ents)
    return Join(scores=scores, sel=sel, params=p, brands=brands, units=units,
                trade_ok=trade_ok, conflict=conflict, eligible=eligible, entities=ents)


def name_basis(sel: lm.Selection, a_names: pd.Series, eg: pd.DataFrame) -> np.ndarray:
    """`licence_name_basis` per object -- where the chosen pair's name term came from."""
    kind = sel.name_kind if sel.name_kind is not None else np.full(len(sel.hit), "")
    raw_holder = np.array([lm.holder_name(v, aliases={}).replace("-", " ")
                           for v in eg["org_name"]], dtype=object)
    manual = np.array([BRAND_ALIASES.get(h, None) for h in raw_holder], dtype=object)
    chosen_manual = np.where(sel.hit, manual[sel.pick], None)
    fascia = a_names.to_numpy(dtype=object)
    is_manual = np.array([m is not None and m == f for m, f in zip(chosen_manual, fascia)])
    return np.where(~sel.hit, "",
                    np.where(is_manual, NAME_MANUAL,
                             np.where(kind == "alias", NAME_LEARNED,
                                      np.where(kind == "generic", NAME_GENERIC, NAME_FUZZY))))


def enrich(v4: pd.DataFrame, eg: pd.DataFrame, accept: float = ACCEPT,
           addr_min: float = ADDR_MIN, max_m: float = MAX_M,
           w=(W_ADDR, W_NAME, W_DIST), learn: bool = True,
           exclusive: bool = True, brand_rule: bool = True,
           result: Join | None = None) -> pd.DataFrame:
    """`v4` with the licence columns appended, at most one licence per row.

    The choice is `join()`'s; what this function adds is which registry columns
    travel with the chosen licence.  Every licence clearing both floors counts
    toward `licence_n_matched` / `licence_n_active` / `licence_all_nos` whether
    or not this object got it -- those columns describe the *address*.
    `licence_status` and the licence columns describe the licence *this object*
    holds.

    `licence_status` says which licence the object has; the pair
    `licence_evidence` / `licence_evidence_note` says what that is evidence *of*,
    which is not the same question for the two risk layers.  A tobacco row can
    never be more than `probable` here -- see `licence_evidence()`.
    """
    j = result or join(v4, eg, accept=accept, addr_min=addr_min, max_m=max_m, w=w,
                       learn=learn, exclusive=exclusive, brand_rule=brand_rule)
    sel = j.sel
    hit = sel.hit
    active = eg["is_active"].to_numpy(bool)
    retail = eg["is_retail"].to_numpy(bool)
    own_active = hit & active[sel.pick]
    own_active_retail = own_active & retail[sel.pick]

    out = v4.reset_index(drop=True).copy()
    # A blocked object had admitted licences and none it may hold: if any of
    # them permits its trade, a known brand ruled it out; otherwise the trade did.
    trade_any = (sel.accepted & j.trade_ok).any(axis=1)
    rows = np.arange(len(hit))
    out["licence_status"] = np.select(
        [own_active, hit, sel.taken, sel.blocked & trade_any, sel.blocked],
        [STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_TAKEN, STATUS_OTHER_CHAIN,
         STATUS_OTHER_TRADE],
        default=STATUS_NONE)
    out["licence_match_method"] = sel.method
    out["licence_match_level"] = np.where(
        hit, np.where(sel.house >= LEVEL_HOUSE_MIN, LEVEL_HOUSE, LEVEL_STREET), "")
    out["licence_score"] = sel.score.round(3)
    out["licence_addr_score"] = sel.addr.round(3)
    basis = name_basis(sel, prepare_v4(v4)["name_key"], eg)
    # A generic fascia's name was never scored; a 0 there would read as
    # "the names disagree", which nobody claimed.
    out["licence_name_score"] = np.where(basis == NAME_GENERIC, np.nan, sel.name.round(3))
    out["licence_name_basis"] = basis
    out["licence_distance_m"] = sel.distance.round(1)
    out["licence_trade_match"] = np.where(hit, np.where(j.trade_ok[rows, sel.pick], "yes", "no"), "")
    out["licence_outlet_id"] = np.where(hit, j.units[sel.pick], "")
    out["licence_n_matched"] = sel.counts[GROUP_MATCHED]
    out["licence_n_active"] = sel.counts[GROUP_ACTIVE]
    out["licence_n_active_retail"] = sel.counts[GROUP_ACTIVE_RETAIL]

    rival = sel.rival if sel.rival is not None else np.full(len(out), -1)
    names = out["name_orig"].fillna("").astype(str).to_numpy()
    addrs = out["adress_orig"].fillna("").astype(str).to_numpy()
    out["licence_claimed_by"] = [f"{names[r]} ({addrs[r]})" if t and r >= 0 else ""
                                 for t, r in zip(sel.taken, rival)]
    if (sel.taken & (rival < 0)).any():
        raise AssertionError("a Taken row with no rival -- the assignment is inconsistent")
    # How narrowly the outlet was lost: the winner's score on it minus this
    # object's best eligible score.  Under 0.02, with no name signal on either
    # side, the choice is close to a coin toss and should be read as such.
    sc = np.nan_to_num(j.scores.score, nan=-1.0)
    best = np.argmax(np.where(sel.accepted & j.eligible, sc, -np.inf), axis=1)
    margin = np.full(len(hit), np.nan)
    tk = np.flatnonzero(sel.taken)
    margin[tk] = sc[rival[tk], sel.pick[rival[tk]]] - sc[tk, best[tk]]
    out["licence_claim_margin"] = np.round(margin, 3)

    kind = licence_evidence(out["risk"], hit, own_active_retail) \
        if "risk" in out.columns else pd.Series(np.where(hit, EVIDENCE_DIRECT, ""))
    out["licence_evidence"] = kind.to_numpy()
    out["licence_evidence_note"] = kind.map(EVIDENCE_NOTE).to_numpy()

    out["licence_all_nos"] = sel.joined(GROUP_MATCHED)
    out["licence_active_nos"] = sel.joined(GROUP_ACTIVE)

    for col, src in LICENCE_FIELDS.items():
        out[col] = sel.take(eg[src].to_numpy(dtype=object))
    for col in _DATE_COLS:
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    return out


def summary(out: pd.DataFrame) -> pd.DataFrame:
    """Match outcome by risk layer, evidence tier and trade type."""
    g = (out.groupby(["risk", "evidence", "trade"])["licence_status"]
         .value_counts().unstack("licence_status").fillna(0).astype(int))
    for col in STATUS_ORDER:
        if col not in g.columns:
            g[col] = 0
    g = g[STATUS_ORDER]
    g["Total"] = g.sum(axis=1)
    g["% active"] = (100 * g[STATUS_ACTIVE] / g["Total"]).round(1)
    return g


def evidence_summary(out: pd.DataFrame) -> pd.DataFrame:
    """What a matched licence is evidence of, per risk layer.

    The whole point of the table is that the `probable` column exists only for
    tobacco and the `direct` column only for alcohol; a reader who sums the two
    is counting two different claims as one.
    """
    g = pd.crosstab(out["risk"], out["licence_evidence"].replace("", "no own licence"))
    g = g[[c for c in EVIDENCE_ORDER + ["no own licence"] if c in g.columns]]
    g["Total"] = g.sum(axis=1)
    for col in g.columns.drop("Total"):
        g[f"% {col}"] = (100 * g[col] / g["Total"]).round(1)
    return g


def reverse_coverage(out: pd.DataFrame, eg: pd.DataFrame) -> pd.DataFrame:
    """How much of the registry the export accounts for, by status and activity.

    The direction that matters for the undercount question: a licensed outlet
    with no v4 object at its address is either closed or missing from the export.

    Read from the written column rather than from a `Selection`, so the table a
    report prints is the one its CSV carries even when the join was run days ago.
    """
    claimed = set()
    for v in out["licence_all_nos"]:
        claimed.update(t.strip() for t in str(v).split(";") if t.strip())
    # "Held": the outlet itself went to an object, not merely an object stands
    # at an address the licence number appears at -- the same outlet identity
    # the join assigns by (`outlet_units`, written as `licence_outlet_id`).
    own = out[out["licence_status"].isin(STATUS_OWN)]
    held = set(own["licence_outlet_id"].astype(str))
    eg = eg.assign(matched=eg["licence_no"].isin(claimed),
                   held=pd.Series(outlet_units(eg)).isin(held).to_numpy())
    g = eg.groupby(["status_en", "activity_class"])[["matched", "held"]].agg(["sum", "size"])
    g = pd.DataFrame({"Matched": g[("matched", "sum")], "Held": g[("held", "sum")],
                      "Licences": g[("matched", "size")]})
    g["% matched"] = (100 * g["Matched"] / g["Licences"]).round(1)
    g["% held"] = (100 * g["Held"] / g["Licences"]).round(1)
    return g.reset_index()
