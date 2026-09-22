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

import numpy as np
import pandas as pd

from .egais import load_egais  # noqa: F401
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
# The calibrated defaults are the package's own (see its METHODOLOGY §5); they
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

STATUS_ACTIVE = "Active"          # a licence in force at this address
STATUS_ARCHIVED = "Archived"      # only expired / terminated / annulled ones
# Never the bare string "None": pandas reads that back as NaN, and this column
# is meant to survive a round trip through the CSV it is written to.
STATUS_NONE = "Not in registry"

# The operator -> fascia table the name term needs.  It ships with the package
# (`licmatch.RU_RETAIL_ALIASES`) because it is a property of Russian retail, not
# of this study; re-exported under the name the reports and docs already use.
BRAND_ALIASES = lm.RU_RETAIL_ALIASES


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
    """The v4 export as the package's canonical side."""
    return lm.side([parse_v4_address(v) for v in df["adress_orig"]],
                   [norm_shop_name(v) for v in df["name_orig"]],
                   df["latitude"], df["longitude"])


def prepare_egais(eg: pd.DataFrame) -> pd.DataFrame:
    """The registry extract as the package's canonical side."""
    blocks = egais_blocks(eg["outlet_address"])
    top = [parse_egais_address(s, h, sub, b) for s, h, sub, b in zip(
        eg["outlet_street"], eg["outlet_house"], eg["outlet_subsettlement"], blocks)]
    return lm.side(top, [norm_org_name(v) for v in eg["org_name"]],
                   eg["latitude"], eg["longitude"])


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
        "существует. По этому адресу действует розничная алкогольная лицензия, "
        "а алкоголь и табак в рознице продаются через один и тот же прилавок, "
        "поэтому лицензия косвенно поддерживает табачную метку, но не "
        "подтверждает продажу табака.",
    EVIDENCE_WEAK:
        "Слабое подтверждение: по адресу найдена только архивная или "
        "нерозничная алкогольная лицензия, поэтому даже косвенный довод в "
        "пользу продажи табака здесь не работает.",
    "": "",
}

# The layer whose product the registry actually licenses.
DIRECT_RISK = "Alcohol"


def licence_evidence(risk: pd.Series, matched: np.ndarray,
                     n_active_retail: np.ndarray) -> pd.Series:
    """`direct` / `probable` / `weak` per row -- see the note above.

    A tobacco row is `probable` only while a *retail* alcohol licence is in
    force at its address: an archived one, or a wholesale/production/transport
    one, says nothing about a counter selling cigarettes today.
    """
    risk = risk.reset_index(drop=True).astype(str)
    kind = np.where(risk.eq(DIRECT_RISK), EVIDENCE_DIRECT,
                    np.where(n_active_retail > 0, EVIDENCE_PROBABLE, EVIDENCE_WEAK))
    return pd.Series(np.where(matched, kind, ""), dtype=object)


def enrich(v4: pd.DataFrame, eg: pd.DataFrame, accept: float = ACCEPT,
           addr_min: float = ADDR_MIN, max_m: float = MAX_M,
           w=(W_ADDR, W_NAME, W_DIST)) -> pd.DataFrame:
    """`v4` with the licence columns appended, one chosen licence per row.

    Every licence clearing both floors counts toward `licence_n_matched` /
    `licence_n_active` / `licence_all_nos`; the licence whose fields are copied
    out is the best-scoring **active** one where any is active and the
    best-scoring one otherwise, so `licence_status` never reads Archived while an
    in-force licence sits at the same address.  Both rules are the package's
    (`licmatch.select`, `prefer=` and the distinct-key groups); what this
    function adds is which registry columns travel with the chosen licence.

    `licence_status` says what the registry holds at the address; the pair
    `licence_evidence` / `licence_evidence_note` says what that is evidence *of*,
    which is not the same question for the two risk layers.  A tobacco row can
    never be more than `probable` here -- see `licence_evidence()`.
    """
    p = params(accept=accept, addr_min=addr_min, max_m=max_m, w=w)
    scores = lm.score_matrix(prepare_v4(v4), prepare_egais(eg), p)

    active = eg["is_active"].to_numpy(bool)
    retail = eg["is_retail"].to_numpy(bool)
    # Counted over distinct licence numbers, not registry rows: a licence that
    # was prolonged appears once per status change, and 20 rows at one address
    # can be 9 licences.  Retail alone carries the tobacco inference; see
    # `licence_evidence()`.
    sel = lm.select(scores, p, prefer=active, keys=eg["licence_no"],
                    groups={GROUP_MATCHED: None,
                            GROUP_ACTIVE: active,
                            GROUP_ACTIVE_RETAIL: active & retail})

    hit = sel.hit
    n_active = sel.counts[GROUP_ACTIVE]
    n_active_retail = sel.counts[GROUP_ACTIVE_RETAIL]

    out = v4.reset_index(drop=True).copy()
    out["licence_status"] = np.where(~hit, STATUS_NONE,
                                     np.where(n_active > 0, STATUS_ACTIVE, STATUS_ARCHIVED))
    out["licence_match_method"] = sel.method
    out["licence_match_level"] = np.where(
        hit, np.where(sel.house >= LEVEL_HOUSE_MIN, LEVEL_HOUSE, LEVEL_STREET), "")
    out["licence_score"] = sel.score.round(3)
    out["licence_addr_score"] = sel.addr.round(3)
    out["licence_name_score"] = sel.name.round(3)
    out["licence_distance_m"] = sel.distance.round(1)
    out["licence_n_matched"] = sel.counts[GROUP_MATCHED]
    out["licence_n_active"] = n_active
    out["licence_n_active_retail"] = n_active_retail

    kind = licence_evidence(out["risk"], hit, n_active_retail) \
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
    for col in (STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_NONE):
        if col not in g.columns:
            g[col] = 0
    g = g[[STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_NONE]]
    g["Total"] = g.sum(axis=1)
    g["% active"] = (100 * g[STATUS_ACTIVE] / g["Total"]).round(1)
    return g


def evidence_summary(out: pd.DataFrame) -> pd.DataFrame:
    """What a matched licence is evidence of, per risk layer.

    The whole point of the table is that the `probable` column exists only for
    tobacco and the `direct` column only for alcohol; a reader who sums the two
    is counting two different claims as one.
    """
    g = pd.crosstab(out["risk"], out["licence_evidence"].replace("", "no match"))
    g = g[[c for c in EVIDENCE_ORDER + ["no match"] if c in g.columns]]
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
    eg = eg.assign(matched=eg["licence_no"].isin(claimed))
    g = eg.groupby(["status_en", "activity_class"])["matched"].agg(["sum", "size"])
    g.columns = ["Matched", "Licences"]
    g["% matched"] = (100 * g["Matched"] / g["Licences"]).round(1)
    return g.reset_index()
