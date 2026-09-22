"""Russian street addresses as comparable toponyms, and their agreement score.

Two registers write the same door in incompatible orders, abbreviations and
inflections -- "Северной Двины Набережная, 55" against "набережная Северной
Двины, 55", "Тимме Я. Улица, 2, 5" against "улица Тимме, 2 к5".  Edit distance
over those strings is noise, so each side is parsed into a `Toponym`
(settlement, street type, street name, house, block) and the fields are compared
one at a time.

Two entry points, one per shape the sources come in:

* `parse_address_line()`   -- a single comma-packed line ("city, street, house");
* `parse_address_fields()` -- separate street / house / settlement / block fields.

Both produce the same `Toponym`, which is the point: after parsing, neither
`address_score()` nor anything downstream can tell which source a side came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from .text import fold, stem, words

# --------------------------------------------------------------------------
# vocabularies
# --------------------------------------------------------------------------
# Street-type words folded onto one key each.  Sources write the type in either
# position -- "Троицкий пр-кт" and "проспект Ломоносова" -- and either spelt out
# or abbreviated.
TYPE_TABLE = {
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
# "линия" is deliberately absent: one register writes "3-я линия ул", where the
# type word is "ул" and "линия" belongs to the name, while the other writes
# "3-я линия" with no type at all.  Treating it as a type would strip it on one
# side only and turn a perfect match into a type conflict.

# Settlement types, so "Рогачево п" and "п. Талаги" both reduce to their name.
_SETTLE_TYPES = r"город|г|пгт|рп|поселок|пос|п|село|с|деревня|дер|д|станция|ст|снт"
_SETTLE_RE = re.compile(
    r"^(?:(?:" + _SETTLE_TYPES + r")\.?\s+(?P<n1>.+)"
    r"|(?P<n2>.+?)\s+(?:" + _SETTLE_TYPES + r")\.?)$", re.I)

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


@lru_cache(maxsize=32)
def home_city_re(*names: str) -> re.Pattern:
    """Matcher for the city every address in the study shares.

    The city is not a toponym worth comparing -- both sides always carry it, in
    whatever spelling ("г Архангельск", "Архангельск город", "городской округ
    Архангельск") -- so it is dropped rather than scored.  A settlement *inside*
    the municipality is a real toponym and is kept; see `settlement_name()`.
    """
    alt = "|".join(re.escape(fold(n)) for n in names if fold(n)) or r"(?!)"
    return re.compile(
        r"^(?:(?:городской\s+округ|г\.?о\.?|г)\.?\s*)?(?:" + alt + r")"
        r"(?:\s*(?:г(?:ород)?|городской\s+округ)\.?)?$", re.I)


# --------------------------------------------------------------------------
# the parsed address
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Toponym:
    """One address as comparable toponyms rather than as a string."""
    settlement: str = ""     # "" means the home city itself
    street_type: str = ""    # canonical key from TYPE_TABLE, "" if unwritten
    street: str = ""         # stemmed street-name tokens, original order
    house: str = ""          # digits only
    suffix: str = ""         # house letter + block (корпус / строение)

    def __bool__(self) -> bool:
        return bool(self.street or self.house)


def street_toponym(text: str) -> tuple[str, str]:
    """"Тимме Я. Улица" -> ("ул", "тимм"); "проспект Ломоносова" -> ("пр", "ломоносов")."""
    s = fold(text)
    s = re.sub(r"[^0-9a-zа-я\- ]+", " ", s)
    tokens = [t for t in s.split() if t]
    stype = ""
    for pos in (-1, 0):
        if len(tokens) < 2:
            break
        key = TYPE_TABLE.get(tokens[pos])
        if key:
            stype = key
            tokens.pop(pos)
            break
    # Bare initials ("Тимме Я.") and hyphen leftovers carry no signal.
    tokens = [t for t in (t.strip("-") for t in tokens) if len(t) > 1 or t.isdigit()]
    return stype, " ".join(stem(t) for t in tokens)


def settlement_name(text: str, city: re.Pattern) -> str:
    """The settlement's bare name, or "" for the home city and for a region."""
    s = fold(text)
    if not s or city.match(s) or _REGION_RE.search(s):
        return ""
    m = _SETTLE_RE.match(s)
    name = (m.group("n1") or m.group("n2")) if m else s
    return " ".join(stem(t) for t in re.sub(r"[^0-9a-zа-я ]+", " ", name).split())


def house_parts(house_text: str, block_text: str = "") -> tuple[str, str]:
    """("356 к4", "") -> ("356", "4"); ("2", "5") -> ("2", "5"); ("45/3", "") -> ("45", "3")."""
    s = fold(house_text)
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
        b = fold(block_text)
        mb2 = _BLOCK_RE.search(b)
        block = mb2.group(1) if mb2 else re.sub(r"[^0-9а-я]+", "", b)
    return num, (letter + block)


def parse_address_line(v, city: re.Pattern) -> Toponym:
    """"Архангельск, Ленинградский проспект, 356 к4" -> Toponym.

    The line is "city, street, house" with the city always present and the house
    sometimes absent; a settlement, where one appears, takes the slot between the
    two ("Лесная речка, Лахтинское шоссе, 17").  The street is found by its type
    word rather than by position, which is what keeps a settlement carrying no
    type word of its own out of the street slot.
    """
    parts = [p for p in (fold(p) for p in str(v).split(",")) if p]
    parts = [p for p in parts if not city.match(p) and not _REGION_RE.search(p)]
    street_i = next((i for i, p in enumerate(parts)
                     if TYPE_TABLE.keys() & set(words(p))), None)
    if street_i is None:
        # No type word anywhere ("Тимме Я., 29", "3-я линия, 51 с1"): the street
        # is the first part carrying a word, which is not the same as the first
        # part that does not start with a digit.
        street_i = next((i for i, p in enumerate(parts)
                         if any(len(w) >= 3 and w.isalpha() for w in words(p))), None)
    if street_i is None:
        return Toponym()
    settlement = settlement_name(" ".join(parts[:street_i]), city)
    tail = [p for p in parts[street_i + 1:]]
    house = " ".join(tail[:1] + [p for p in tail[1:] if _NUM_START.match(p)])
    stype, sname = street_toponym(parts[street_i])
    num, suffix = house_parts(house)
    return Toponym(settlement, stype, sname, num, suffix)


def parse_address_fields(street: str, house: str, city: re.Pattern,
                         settlement: str = "", block: str = "") -> Toponym:
    """The same Toponym from a source that keeps its address in separate fields."""
    stype, sname = street_toponym(street)
    num, suffix = house_parts(house, block)
    return Toponym(settlement_name(settlement, city), stype, sname, num, suffix)


# --------------------------------------------------------------------------
# agreement between two toponyms -- the readable definition
# --------------------------------------------------------------------------
# `scoring.score_matrix()` vectorises exactly these three functions; the tests
# check the two implementations against each other on real pairs.
STREET_SORT_W, STREET_SET_W = 0.6, 0.4
ADDR_STREET_W, ADDR_HOUSE_W = 0.6, 0.4
TYPE_CONFLICT = 0.6          # written street types disagree
SETTLEMENT_CONFLICT = 0.4    # two different named settlements
SETTLEMENT_ONE_SIDED = 0.8   # one side names a settlement, the other does not

HOUSE_BOTH_SILENT = 0.5
HOUSE_ONE_SILENT = 0.3
HOUSE_SAME_BLOCK = 1.0
HOUSE_BLOCK_ONE_SIDED = 0.85
HOUSE_BLOCK_CONFLICT = 0.6


def street_similarity(a: str, b: str) -> float:
    """Toponym similarity of two stemmed street names, 0..1.

    A blend rather than a single ratio: `token_set` alone scores a subset 1.00
    ("Победы" against "40-летия Великой Победы"), `token_sort` alone punishes the
    word order the two sources disagree on.
    """
    if not a or not b:
        return 0.0
    return (STREET_SORT_W * fuzz.token_sort_ratio(a, b)
            + STREET_SET_W * fuzz.token_set_ratio(a, b)) / 100.0


def house_similarity(a: Toponym, b: Toponym) -> float:
    """1.0 same building, 0.6 same number with a different corpus, 0.0 different."""
    if not a.house and not b.house:
        return HOUSE_BOTH_SILENT
    if not a.house or not b.house:
        return HOUSE_ONE_SILENT
    if a.house != b.house:
        return 0.0
    if a.suffix == b.suffix:
        return HOUSE_SAME_BLOCK
    return HOUSE_BLOCK_ONE_SIDED if not a.suffix or not b.suffix else HOUSE_BLOCK_CONFLICT


def address_score(a: Toponym, b: Toponym) -> float:
    """Field-by-field toponym agreement, 0..1."""
    s = street_similarity(a.street, b.street)
    if a.street_type and b.street_type and a.street_type != b.street_type:
        s *= TYPE_CONFLICT
    score = ADDR_STREET_W * s + ADDR_HOUSE_W * house_similarity(a, b)
    if a.settlement and b.settlement and a.settlement != b.settlement:
        score *= SETTLEMENT_CONFLICT
    elif bool(a.settlement) != bool(b.settlement):
        score *= SETTLEMENT_ONE_SIDED
    return score
