"""licmatch -- address-level record linkage between an object export and a register.

The problem this package solves is narrow and recurring: two sources describe
the same door in different words, one of them names a *holder* rather than a
*shop*, half of one side carries no usable coordinate, and the result must be
defensible line by line rather than merely plausible in aggregate.

It knows nothing about any particular source.  An adapter parses whatever the
source delivers into `Toponym`s and name keys, hands both sides to `side()`,
and reads the result back; `score_matrix()` and `select()` never learn which
register they were given.  That is the whole interface, and it is what lets the
rule be reviewed, tested and re-used on its own.

    from licmatch import (DEFAULTS, home_city_re, parse_address_line,
                          parse_address_fields, side, score_matrix, select)

    city = home_city_re("Архангельск")
    a = side([parse_address_line(v, city) for v in export["address"]],
             [fascia_name(v) for v in export["name"]],
             export["lat"], export["lon"])
    b = side([parse_address_fields(s, h, city) for s, h in registry[["street", "house"]].values],
             [holder_name(v) for v in registry["holder"]],
             registry["lat"], registry["lon"])
    sel = select(score_matrix(a, b, DEFAULTS), DEFAULTS,
                 prefer=registry["in_force"].to_numpy(bool),
                 keys=registry["licence_no"], groups={"matched": None})

The methodology -- why the address term carries half the weight, why there are
two floors rather than one, and what the result may and may not be read as -- is
`docs/METHODOLOGY.md`, in Russian.
"""
from __future__ import annotations

from .geo import EARTH_R_M, haversine_m
from .names import (RU_RETAIL_ALIASES, SHORT_NAME_MARKER, TRADE_AND_LEGAL_NOISE,
                    fascia_name, holder_name, name_key)
from .scoring import (DEFAULTS, ROUTE_ADDR, ROUTE_GEO, ROUTE_NAMES, ROUTE_NONE,
                      SIDE_COLUMNS, MatchParams, Scores, accepted, pair_score,
                      score_matrix, side)
from .select import PREFER_LIFT, Selection, claimed_keys, select
from .text import fold, stem, stem_all, words
from .toponym import (TYPE_TABLE, Toponym, address_score, home_city_re,
                      house_parts, house_similarity, parse_address_fields,
                      parse_address_line, settlement_name, street_similarity,
                      street_toponym)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # parameters
    "MatchParams", "DEFAULTS",
    # addresses
    "Toponym", "home_city_re", "parse_address_line", "parse_address_fields",
    "street_toponym", "settlement_name", "house_parts", "TYPE_TABLE",
    "address_score", "street_similarity", "house_similarity",
    # names
    "name_key", "holder_name", "fascia_name", "RU_RETAIL_ALIASES",
    "TRADE_AND_LEGAL_NOISE", "SHORT_NAME_MARKER",
    # scoring and selection
    "side", "SIDE_COLUMNS", "pair_score", "score_matrix", "accepted", "Scores",
    "select", "Selection", "claimed_keys", "PREFER_LIFT",
    "ROUTE_GEO", "ROUTE_ADDR", "ROUTE_NONE", "ROUTE_NAMES",
    # primitives
    "haversine_m", "EARTH_R_M", "fold", "stem", "stem_all", "words",
]
