"""Join the fourth-delivery risk layer (data/raw_v4) to the FSRAR licence registry.

The question this module answers is object-level rather than aggregate: for each
v4 record, *is there a real alcohol licence at this address*, is it in force, and
what does the registry say about it.  `v4_common.corroboration()` already answers
the aggregate version (what share of the layer sits near a licensed outlet); it
deliberately stops at a nearest-neighbour distance and never names a licence.

Kept separate from `v4_common.py` and `egais.py` on the same principle those two
follow: the rendered reports must keep producing what they produced before.  What
is shared is imported, never copied.

Scoring
-------
A candidate pair (v4 object, licence) is scored

    score = W_ADDR * address_score + W_NAME * name_score + W_DIST * distance_score

with ``distance_score = 1 - d / MAX_M`` and a hard cut at ``d <= MAX_M`` (100 m).

The address term is **not** a string comparison.  The two sources write the same
address in incompatible orders and inflections -- "Северной Двины наб, 55" against
"Архангельск, набережная Северной Двины, 55", "Тимме Я. Улица, 2, 5" against
"улица Тимме, 2 к5" -- so each side is first parsed into toponyms (settlement,
street type, street name, house, block) and the toponyms are compared field by
field.  See `parse_v4_address()` / `parse_egais_address()` and `address_score()`.

Two things about the registry govern the join:

* **It licenses alcohol, not tobacco.**  A licence found against a tobacco row
  means the object also holds an alcohol licence -- never that the tobacco tag is
  corroborated.  `enrich()` fills the licence columns for both layers; reading
  them as tobacco evidence is a mistake the data cannot stop.
* **It is a register, not a list of open outlets.**  Only 585 of the 2,100 city
  rows are in force, and coordinates are plausible on 53 % of rows overall but on
  98 % of the *active retail* ones.  Rows without coordinates can therefore never
  be reached by the 100 m rule, and are matched by a second, deliberately strict
  address-only route (`METHOD_ADDR`) whose matches stay labelled as such.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from . import v3_common as c
from .egais import load_egais  # noqa: F401
from .paths import PROC  # noqa: F401
from .v4_common import load_v4  # noqa: F401

# --------------------------------------------------------------------------
# tunables
# --------------------------------------------------------------------------
W_ADDR, W_NAME, W_DIST = 0.50, 0.20, 0.30
MAX_M = 100.0            # the distance cut the whole join is built on

# Acceptance floor for the combined score.  Calibrated with
# `pixi run match-egais-v4 --calibrate`: below it a best match is a licence
# further than ~80 m away whose name says nothing, which is not evidence.
ACCEPT = 0.45
STRONG = 0.75            # reported separately, the tier that needs no argument

# A floor on the address term alone, and the reason the join does not rest on
# the combined score by itself.  Inside 100 m the neighbouring building is a
# candidate too: same street, different house number, addr = 0.60, and at 30 m
# with any name resemblance that clears any score floor low enough to keep the
# true matches whose coordinates are poor.  The registry's coordinates come from
# degrees-minutes-seconds, so one arcsecond of rounding is already ~31 m of
# latitude -- distance cannot arbitrate between neighbours here, and the house
# number can.  0.72 is the score of "same street, house number written on one
# side only"; an explicit house mismatch scores 0.60 and is refused.
# Set `addr_min=0.0` for the unguarded weighted sum.
ADDR_MIN = 0.72

# The address-only route, for the 47 % of registry rows that carry no usable
# coordinate.  No distance evidence exists there, so the bar on the two remaining
# terms is raised instead of the weights being quietly renormalised downward.
ADDR_ROUTE_STREET = 0.90
ADDR_ROUTE_HOUSE = 0.85

METHOD_GEO = "geo"
METHOD_ADDR = "address"

STATUS_ACTIVE = "Active"          # a licence in force at this address
STATUS_ARCHIVED = "Archived"      # only expired / terminated / annulled ones
# Never the bare string "None": pandas reads that back as NaN, and this column
# is meant to survive a round trip through the CSV it is written to.
STATUS_NONE = "Not in registry"

# --------------------------------------------------------------------------
# toponyms
# --------------------------------------------------------------------------
# Street-type words folded onto one key each.  Both sources write the type in
# either position -- "Троицкий пр-кт" and "проспект Ломоносова" -- and either
# spelt out or abbreviated.
_TYPE_TABLE = {
    "улица": "ул", "ул": "ул",
    "проспект": "пр", "просп": "пр", "пр-кт": "пр", "пркт": "пр", "пр-т": "пр", "пр": "пр",
    "переулок": "пер", "пер": "пер",
    "набережная": "наб", "наб": "наб",
    "шоссе": "ш", "ш": "ш",
    "площадь": "пл", "пл": "пл",
    "проезд": "проезд", "пр-д": "проезд",
    "бульвар": "бул", "б-р": "бул",
    "тракт": "тракт", "аллея": "аллея",
    "квартал": "кв-л", "тупик": "туп",
    "территория": "тер", "тер": "тер",
    "микрорайон": "мкр", "мкр": "мкр", "м-н": "мкр",
    "городок": "городок",
}
# "линия" is deliberately absent: the registry writes "3-я линия ул", where the
# type word is "ул" and "линия" belongs to the name, while the export writes
# "3-я линия" with no type at all.  Treating it as a type would strip it on one
# side only and turn a perfect match into a type conflict.

# Settlement types, so "Рогачево п" and "п. Талаги" both reduce to their name.
_SETTLE_TYPES = r"город|г|пгт|рп|поселок|пос|п|село|с|деревня|дер|д|станция|ст|снт"
_SETTLE_RE = re.compile(
    r"^(?:(?:" + _SETTLE_TYPES + r")\.?\s+(?P<n1>.+)"
    r"|(?P<n2>.+?)\s+(?:" + _SETTLE_TYPES + r")\.?)$", re.I)

# Russian inflectional endings, longest first.  Light stemming is what lets
# "Северной Двины" meet "Северная Двина" and "Воскресенская" meet "Воскресенской"
# without a morphological analyser; a token is never cut below four characters.
_ENDINGS = ("ыми", "ими", "ого", "его", "ому", "ему", "ая", "яя", "ое", "ее",
            "ые", "ие", "ый", "ий", "ой", "ым", "им", "ом", "ых", "их", "ую",
            "юю", "ей", "ов", "ев", "а", "я", "у", "ю", "е", "и", "ы", "о")

_QUOTES = "[" + chr(0xAB) + chr(0xBB) + chr(0x22) + chr(0x27) + chr(0x60) + "]"
# "г Архангельск", "Архангельск город", "городской округ Архангельск" -- all the
# same place, and none of it is a toponym worth comparing.
_CITY_RE = re.compile(
    r"^(?:(?:городской\s+округ|г\.?о\.?|г)\.?\s*)?архангельск(?:\s*(?:г(?:ород)?|"
    r"городской\s+округ)\.?)?$", re.I)
_REGION_RE = re.compile(r"(?:^|\s)(?:обл|область|край|респ|республика)\b|^россия$", re.I)
_HOUSE_RE = re.compile(r"(?:д(?:ом)?\.?\s*)?(\d+)([а-я])?", re.I)
# The keyword must stand as its own token, and what follows it must be a number
# or a single lettered block: without the leading \b the "с" of "49 киоск" reads
# as строение and invents a corpus out of the trailing "к", and without the
# digit-run alternative "4 к1с3" yields nothing at all.
_BLOCK_RE = re.compile(
    r"\b(?:корпус|корп|строение|стр|литера|литер|лит|ст|к|с)\.?\s*"
    r"(\d+[а-я]?(?![0-9])|[а-я]\b)", re.I)
_SLASH_RE = re.compile(r"^\s*/\s*(\d+[а-я]?)")
_NUM_START = re.compile(r"^(?:д(?:ом)?\.?\s*)?\d")


def _words(s: str) -> list[str]:
    return re.sub(r"[^0-9a-zа-я\- ]+", " ", s).split()


def _fold(v) -> str:
    """Lowercase, drop the yo, strip quotes, collapse whitespace."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).lower().replace(chr(0x451), "е")
    return " ".join(re.sub(_QUOTES, " ", s).split())


def stem(token: str) -> str:
    """Trim one inflectional ending, never cutting the token below four chars."""
    if len(token) <= 4 or token.isdigit():
        return token
    for e in _ENDINGS:
        if token.endswith(e) and len(token) - len(e) >= 4:
            return token[: -len(e)]
    return token


@dataclass(frozen=True)
class Toponym:
    """One address as comparable toponyms rather than as a string."""
    settlement: str = ""     # "" means the city itself
    street_type: str = ""    # canonical key from _TYPE_TABLE, "" if unwritten
    street: str = ""         # stemmed street-name tokens, original order
    house: str = ""          # digits only
    suffix: str = ""         # house letter + block (корпус / строение)


def _street_toponym(text: str) -> tuple[str, str]:
    """"Тимме Я. Улица" -> ("ул", "тимм"); "проспект Ломоносова" -> ("пр", "ломоносов")."""
    s = _fold(text)
    s = re.sub(r"[^0-9a-zа-я\- ]+", " ", s)
    tokens = [t for t in s.split() if t]
    stype = ""
    for pos in (-1, 0):
        if len(tokens) < 2:
            break
        key = _TYPE_TABLE.get(tokens[pos])
        if key:
            stype = key
            tokens.pop(pos)
            break
    # Bare initials ("Тимме Я.") and hyphen leftovers carry no signal.
    tokens = [t for t in (t.strip("-") for t in tokens) if len(t) > 1 or t.isdigit()]
    return stype, " ".join(stem(t) for t in tokens)


def _settlement_name(text: str) -> str:
    s = _fold(text)
    if not s or _CITY_RE.match(s) or _REGION_RE.search(s):
        return ""
    m = _SETTLE_RE.match(s)
    name = (m.group("n1") or m.group("n2")) if m else s
    return " ".join(stem(t) for t in re.sub(r"[^0-9a-zа-я ]+", " ", name).split())


def _house_parts(house_text: str, block_text: str = "") -> tuple[str, str]:
    """("356 к4", "") -> ("356", "4"); ("2", "5") -> ("2", "5"); ("45/3", "") -> ("45", "3")."""
    s = _fold(house_text)
    num, letter, rest = "", "", s
    m = _HOUSE_RE.search(s)
    if m:
        num, letter = m.group(1), (m.group(2) or "")
        rest = s[m.end():]
    block = ""
    mb = _BLOCK_RE.search(rest)
    if mb:
        block = mb.group(1)
    else:
        ms = _SLASH_RE.match(rest)
        if ms:
            block = ms.group(1)
    if not block and block_text:
        b = _fold(block_text)
        mb2 = _BLOCK_RE.search(b)
        block = mb2.group(1) if mb2 else re.sub(r"[^0-9а-я]+", "", b)
    return num, (letter + block)


def parse_v4_address(v) -> Toponym:
    """"Архангельск, Ленинградский проспект, 356 к4" -> Toponym.

    The v4 layer writes "city, street, house" with the city always present and
    the house sometimes absent; a settlement, where one appears, takes the slot
    between the two ("Лесная речка, Лахтинское шоссе, 17").  The street is found
    by its type word rather than by position, which is what keeps a settlement
    that carries no type word of its own out of the street slot.
    """
    parts = [p for p in (_fold(p) for p in str(v).split(",")) if p]
    parts = [p for p in parts if not _CITY_RE.match(p) and not _REGION_RE.search(p)]
    street_i = next((i for i, p in enumerate(parts)
                     if _TYPE_TABLE.keys() & set(_words(p))), None)
    if street_i is None:
        # No type word anywhere ("Тимме Я., 29", "3-я линия, 51 с1"): the street
        # is the first part carrying a word, which is not the same as the first
        # part that does not start with a digit.
        street_i = next((i for i, p in enumerate(parts)
                         if any(len(w) >= 3 and w.isalpha() for w in _words(p))), None)
    if street_i is None:
        return Toponym()
    settlement = _settlement_name(" ".join(parts[:street_i]))
    tail = [p for p in parts[street_i + 1:]]
    house = " ".join(tail[:1] + [p for p in tail[1:] if _NUM_START.match(p)])
    stype, sname = _street_toponym(parts[street_i])
    num, suffix = _house_parts(house)
    return Toponym(settlement, stype, sname, num, suffix)


def parse_egais_address(street: str, house: str, subsettlement: str = "",
                        block: str = "") -> Toponym:
    """The registry's own address fields as toponyms.

    `outlet_street` / `outlet_house` come out of `scripts/parse_egais.py`; the
    corpus sits one slot further along the comma-packed `outlet_address`, which
    `egais_blocks()` recovers.
    """
    stype, sname = _street_toponym(street)
    num, suffix = _house_parts(house, block)
    return Toponym(_settlement_name(subsettlement), stype, sname, num, suffix)


def egais_blocks(addr: pd.Series) -> pd.Series:
    """The corpus slot (position 8) of the registry's comma-packed address."""
    return addr.fillna("").astype(str).str.split(",").map(
        lambda p: p[8].strip() if len(p) > 8 else "")


# --------------------------------------------------------------------------
# names
# --------------------------------------------------------------------------
# The registry names the licence *holder*, the export names the *shop*.  For the
# chains that carry most of the city's licences the two never resemble each
# other, and no fuzzy metric can bridge them, so the handful that matter are
# mapped explicitly.  Only unambiguous, publicly known operator -> fascia pairs
# are listed; anything uncertain is left out and simply scores low on the name
# term, which is why that term carries the smallest weight of the three.
BRAND_ALIASES = {
    "тандер": "магнит",
    "агроторг": "пятерочка",
    "альбион 2002": "бристоль",
    "альфа м": "красное&белое",
    "винлаб запад": "винлаб",
    "винлаб северо запад": "винлаб",
    "новабев архангельск": "винлаб",
    "бэст прайс": "fix price",
    "торгсервис 29": "светофор",
}

# Words a directory appends to a fascia ("Пятёрочка, супермаркет") and legal
# boilerplate the registry prepends.  Both are noise on the name term.
_NAME_DROP = {
    "магазин", "супермаркет", "гипермаркет", "минимаркет", "маркет", "киоск",
    "павильон", "кафе", "бар", "ресторан", "паб", "столовая", "кулинария",
    "пекарня", "кофейня", "продуктовый", "торговая", "торговый", "компания",
    "фирма", "сеть", "отдел", "точка", "продажи", "розничные", "сервисный",
    "центр", "дом", "ооо", "оао", "зао", "ао", "ип", "пао", "тс", "тд", "по",
    "общество", "ограниченной", "ответственностью", "акционерное",
    "закрытое", "открытое", "публичное", "потребительское",
}


def _name_key(text: str) -> str:
    s = re.sub(r"[^0-9a-zа-я&\- ]+", " ", text)
    toks = [t for t in s.split() if t not in _NAME_DROP and len(t) > 1]
    out = " ".join(toks).strip()
    # The alias table is keyed on the hyphenless form, so "Альбион-2002" and
    # "Альбион 2002" reach the same fascia.
    return BRAND_ALIASES.get(out.replace("-", " "), out)


def norm_org_name(v) -> str:
    """The registry's holder name reduced to its distinctive part.

    'Общество с ограниченной ответственностью «ЛОЙ» Сокращенно: ООО "ЛОЙ"' -> "лой".
    """
    return _name_key(_fold(v).split("сокращенно:")[-1])


def norm_shop_name(v) -> str:
    """The export's fascia reduced the same way, trade descriptor removed."""
    return _name_key(_fold(v))


# --------------------------------------------------------------------------
# pairwise scores -- the readable definition
# --------------------------------------------------------------------------
def street_similarity(a: str, b: str) -> float:
    """Toponym similarity of two stemmed street names, 0..1.

    A blend rather than a single ratio: `token_set` alone scores a subset 1.00
    ("Победы" against "40-летия Великой Победы"), `token_sort` alone punishes the
    word order the two sources disagree on.
    """
    if not a or not b:
        return 0.0
    return (0.6 * fuzz.token_sort_ratio(a, b) + 0.4 * fuzz.token_set_ratio(a, b)) / 100.0


def house_similarity(a: Toponym, b: Toponym) -> float:
    """1.0 same building, 0.6 same number with a different corpus, 0.0 different."""
    if not a.house and not b.house:
        return 0.5
    if not a.house or not b.house:
        return 0.3
    if a.house != b.house:
        return 0.0
    if a.suffix == b.suffix:
        return 1.0
    return 0.85 if not a.suffix or not b.suffix else 0.6


def address_score(a: Toponym, b: Toponym) -> float:
    """Field-by-field toponym agreement, 0..1."""
    s = street_similarity(a.street, b.street)
    if a.street_type and b.street_type and a.street_type != b.street_type:
        s *= 0.6
    score = 0.6 * s + 0.4 * house_similarity(a, b)
    if a.settlement and b.settlement and a.settlement != b.settlement:
        score *= 0.4
    elif bool(a.settlement) != bool(b.settlement):
        score *= 0.8
    return score


def pair_score(a: Toponym, b: Toponym, name_a: str, name_b: str,
               distance_m: float | None) -> float:
    """The published formula for one pair; `score_all()` vectorises exactly this."""
    adr = address_score(a, b)
    nam = fuzz.WRatio(name_a, name_b) / 100.0 if (name_a and name_b) else 0.0
    if distance_m is None:
        return (W_ADDR * adr + W_NAME * nam) / (W_ADDR + W_NAME)
    return (W_ADDR * adr + W_NAME * nam
            + W_DIST * max(0.0, 1.0 - float(distance_m) / MAX_M))


# --------------------------------------------------------------------------
# vectorised join
# --------------------------------------------------------------------------
def prepare_v4(df: pd.DataFrame) -> pd.DataFrame:
    top = [parse_v4_address(v) for v in df["adress_orig"]]
    return pd.DataFrame({
        "settlement": [t.settlement for t in top],
        "street_type": [t.street_type for t in top],
        "street": [t.street for t in top],
        "house": [t.house for t in top],
        "suffix": [t.suffix for t in top],
        "name_key": [norm_shop_name(v) for v in df["name_orig"]],
        "latitude": pd.to_numeric(df["latitude"], errors="coerce").to_numpy(),
        "longitude": pd.to_numeric(df["longitude"], errors="coerce").to_numpy(),
    })


def prepare_egais(eg: pd.DataFrame) -> pd.DataFrame:
    blocks = egais_blocks(eg["outlet_address"])
    top = [parse_egais_address(s, h, sub, b) for s, h, sub, b in zip(
        eg["outlet_street"], eg["outlet_house"], eg["outlet_subsettlement"], blocks)]
    return pd.DataFrame({
        "settlement": [t.settlement for t in top],
        "street_type": [t.street_type for t in top],
        "street": [t.street for t in top],
        "house": [t.house for t in top],
        "suffix": [t.suffix for t in top],
        "name_key": [norm_org_name(v) for v in eg["org_name"]],
        "latitude": eg["latitude"].to_numpy(),
        "longitude": eg["longitude"].to_numpy(),
    })


def _sim_matrix(left: pd.Series, right: pd.Series, scorer):
    """(matrix over the distinct strings, left codes, right codes).

    The pairs number 3.5 M and the distinct strings a few hundred, so every
    comparison is done once and then gathered.
    """
    lu, li = np.unique(left.to_numpy(dtype=object), return_inverse=True)
    ru, ri = np.unique(right.to_numpy(dtype=object), return_inverse=True)
    m = process.cdist(list(lu), list(ru), scorer=scorer, workers=-1)
    return np.asarray(m, dtype=np.float32) / 100.0, li, ri


def _codes(left: pd.Series, right: pd.Series):
    """Shared integer coding of two categorical columns; "" gets code -1."""
    vals = pd.Index(pd.unique(pd.concat([left, right], ignore_index=True)))
    lc = vals.get_indexer(pd.Index(left)).astype(np.int32)
    rc = vals.get_indexer(pd.Index(right)).astype(np.int32)
    empty = vals.get_indexer(pd.Index([""]))[0]
    if empty >= 0:
        lc = np.where(lc == empty, -1, lc)
        rc = np.where(rc == empty, -1, rc)
    return lc, rc


def score_all(a: pd.DataFrame, b: pd.DataFrame,
              w=(W_ADDR, W_NAME, W_DIST), max_m: float = MAX_M) -> dict:
    """Every (v4 x licence) pair scored, as dense float32 matrices.

    1,694 x 2,100 is 3.5 M pairs -- small enough to keep dense, which keeps the
    code the same shape as the formula it implements.  `score` is NaN for every
    pair that neither route admits.
    """
    w_addr, w_name, w_dist = w

    sort_m, li, ri = _sim_matrix(a["street"], b["street"], fuzz.token_sort_ratio)
    set_m, _, _ = _sim_matrix(a["street"], b["street"], fuzz.token_set_ratio)
    street = 0.6 * sort_m[li][:, ri] + 0.4 * set_m[li][:, ri]
    street[a["street"].to_numpy() == "", :] = 0.0
    street[:, b["street"].to_numpy() == ""] = 0.0

    ta, tb = _codes(a["street_type"], b["street_type"])
    street *= np.where((ta[:, None] >= 0) & (tb[None, :] >= 0)
                       & (ta[:, None] != tb[None, :]), 0.6, 1.0).astype(np.float32)

    hn_a = pd.to_numeric(a["house"], errors="coerce").to_numpy(dtype=np.float64)
    hn_b = pd.to_numeric(b["house"], errors="coerce").to_numpy(dtype=np.float64)
    sa, sb = _codes(a["suffix"], b["suffix"])
    miss_a, miss_b = np.isnan(hn_a)[:, None], np.isnan(hn_b)[None, :]
    same_num = hn_a[:, None] == hn_b[None, :]
    same_suf = sa[:, None] == sb[None, :]
    one_suf = (sa[:, None] < 0) ^ (sb[None, :] < 0)
    house = np.where(
        miss_a & miss_b, 0.5,
        np.where(miss_a | miss_b, 0.3,
                 np.where(~same_num, 0.0,
                          np.where(same_suf, 1.0, np.where(one_suf, 0.85, 0.6))))
    ).astype(np.float32)

    addr = 0.6 * street + 0.4 * house
    ga, gb = _codes(a["settlement"], b["settlement"])
    addr *= np.where((ga[:, None] >= 0) & (gb[None, :] >= 0) & (ga[:, None] != gb[None, :]), 0.4,
                     np.where((ga[:, None] >= 0) ^ (gb[None, :] >= 0), 0.8, 1.0)).astype(np.float32)

    name_m, ni, nj = _sim_matrix(a["name_key"], b["name_key"], fuzz.WRatio)
    name = name_m[ni][:, nj]
    name[a["name_key"].to_numpy() == "", :] = 0.0
    name[:, b["name_key"].to_numpy() == ""] = 0.0

    dist = c.haversine_m(
        np.asarray(a["latitude"], dtype=float)[:, None],
        np.asarray(a["longitude"], dtype=float)[:, None],
        np.asarray(b["latitude"], dtype=float)[None, :],
        np.asarray(b["longitude"], dtype=float)[None, :],
    ).astype(np.float32)
    near = dist <= max_m
    dscore = np.where(near, 1.0 - dist / max_m, 0.0).astype(np.float32)

    total = w_addr * addr + w_name * name + w_dist * dscore
    # The address-only route: no coordinate exists, so the distance term is
    # dropped rather than scored as a zero, and the two remaining terms must
    # clear a higher bar on their own.
    no_coord = np.isnan(dist)
    addr_route = no_coord & (street >= ADDR_ROUTE_STREET) & (house >= ADDR_ROUTE_HOUSE)
    total = np.where(addr_route, (w_addr * addr + w_name * name) / (w_addr + w_name), total)
    total = np.where(near | addr_route, total, np.nan).astype(np.float32)

    return {"score": total, "addr": addr, "name": name, "street": street,
            "house": house,
            "distance": np.where(near, dist, np.nan).astype(np.float32),
            "method": np.where(near, 0, np.where(addr_route, 1, -1)).astype(np.int8)}


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
    in-force licence sits at the same address.

    `licence_status` says what the registry holds at the address; the pair
    `licence_evidence` / `licence_evidence_note` says what that is evidence *of*,
    which is not the same question for the two risk layers.  A tobacco row can
    never be more than `probable` here -- see `licence_evidence()`.
    """
    a, b = prepare_v4(v4), prepare_egais(eg)
    m = score_all(a, b, w=w, max_m=max_m)
    score = m["score"]
    ok = (np.nan_to_num(score, nan=-1.0) >= accept) & (m["addr"] >= addr_min)

    active = eg["is_active"].to_numpy(bool)
    ranked = np.where(ok, np.nan_to_num(score, nan=0.0), -1.0)
    # +2 keeps any accepted active licence ahead of every archived one whatever
    # their scores, so the row reports the licence that is actually in force.
    pick = np.argmax(np.where(ok & active[None, :], ranked + 2.0, ranked), axis=1)
    rows = np.arange(len(v4))
    hit = ok[rows, pick]

    # Counted over distinct licence numbers, not registry rows: a licence that
    # was prolonged appears once per status change, and 20 rows at one address
    # can be 9 licences.
    nos = eg["licence_no"].to_numpy(dtype=object)
    retail = eg["is_retail"].to_numpy(bool)
    accepted = [set(nos[np.flatnonzero(r)]) for r in ok]
    accepted_active = [set(nos[np.flatnonzero(r & active)]) for r in ok]
    n_matched = np.array([len(s) for s in accepted])
    n_active = np.array([len(s) for s in accepted_active])
    # Retail alone carries the tobacco inference; see `licence_evidence()`.
    n_active_retail = np.array([len(set(nos[np.flatnonzero(r & active & retail)]))
                                for r in ok])

    out = v4.reset_index(drop=True).copy()
    methods = np.array(["", METHOD_GEO, METHOD_ADDR], dtype=object)
    out["licence_status"] = np.where(~hit, STATUS_NONE,
                                     np.where(n_active > 0, STATUS_ACTIVE, STATUS_ARCHIVED))
    out["licence_match_method"] = np.where(hit, methods[m["method"][rows, pick] + 1], "")
    out["licence_match_level"] = np.where(
        hit, np.where(m["house"][rows, pick] >= 0.85, LEVEL_HOUSE, LEVEL_STREET), "")
    out["licence_score"] = np.where(hit, score[rows, pick], np.nan).round(3)
    out["licence_addr_score"] = np.where(hit, m["addr"][rows, pick], np.nan).round(3)
    out["licence_name_score"] = np.where(hit, m["name"][rows, pick], np.nan).round(3)
    out["licence_distance_m"] = np.where(hit, m["distance"][rows, pick], np.nan).round(1)
    out["licence_n_matched"] = n_matched
    out["licence_n_active"] = n_active
    out["licence_n_active_retail"] = n_active_retail

    kind = licence_evidence(out["risk"], hit, n_active_retail) \
        if "risk" in out.columns else pd.Series(np.where(hit, EVIDENCE_DIRECT, ""))
    out["licence_evidence"] = kind.to_numpy()
    out["licence_evidence_note"] = kind.map(EVIDENCE_NOTE).to_numpy()

    out["licence_all_nos"] = ["; ".join(sorted(s)) for s in accepted]
    out["licence_active_nos"] = ["; ".join(sorted(s)) for s in accepted_active]

    for col, src in LICENCE_FIELDS.items():
        vals = eg[src].to_numpy(dtype=object)
        out[col] = np.where(hit, vals[pick], "")
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
    """
    claimed = set()
    for v in out["licence_all_nos"]:
        claimed.update(t.strip() for t in str(v).split(";") if t.strip())
    eg = eg.assign(matched=eg["licence_no"].isin(claimed))
    g = eg.groupby(["status_en", "activity_class"])["matched"].agg(["sum", "size"])
    g.columns = ["Matched", "Licences"]
    g["% matched"] = (100 * g["Matched"] / g["Licences"]).round(1)
    return g.reset_index()
