"""The FSRAR licence registry as an independent source for final-delivery catering.

The final delivery (`data/raw_final/`, three cities) marks an object
«Подтверждено» when two independent sources carry it.  A catering licence in
force is such a source -- the state registers it against a street address, for
a named holder, whatever OSM, 2GIS or Yandex say -- but only for the object it
actually belongs to.  `match_catering()` answers that object-level question and
nothing wider.

The matching rule is `packages/licmatch`, unchanged, at this study's calibrated
settings (`v4_egais.PARAMS`): the three-term score, both floors, both routes.
What this module adds is the decision that the licence is *this object's own*,
and it is deliberately stricter than the v4 join:

* **The licence must permit catering and be in force.**  A retail licence at a
  café's address says a shop sells alcohol there, not that the café exists.
* **The name must agree, always.**  Catering shares addresses -- a shopping
  centre or a hotel holds a food court's worth of venues and a handful of
  licences -- and the registry's coordinate cannot tell them apart.  The v4
  join lets the strongest claim at an address win; here an address alone never
  confirms anything.  The name may agree with the holder ("Жасмин" / ООО
  «Жасмин») or with the venue name the registry itself writes into the premises
  text of the outlet address («ресторан "Йоко"», «кафе Караван»), which is how
  a venue run by ООО «Бермуда» can still be recognised.
* **A generic fascia confirms nothing.**  "Кафе", "Столовая No 15": the name
  term is not scored for them, so no name can agree.
* **One outlet, one venue.**  If one licensed outlet (holder INN @ address)
  agrees with two objects of different brands, only the stronger keeps it.
  Records of one venue under several spellings ("Coffee Like" / "Coffee Like,
  кофе-бар") share it.

No brand is learned here.  Catering chains in these cities trade almost
entirely as franchises, each under its own local company, so a fascia -> holder
vote would learn one franchisee and wrongly extend it to the others; the manual
retail table (`licmatch.RU_RETAIL_ALIASES`) names no catering operator at all.

Every object that is not confirmed gets a short Russian `egais_note` naming the
nearest thing the registry *does* hold -- another holder's licence at the
address, the object's own licence that has lapsed, a retail-only licence, a
licence of the same name one building over -- so a reviewer sees why.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .egais import ACTIVITY_EN, load_egais
from .paths import EGAIS_FINAL_TSV, ensure_licmatch_path
from .v4_egais import PARAMS, egais_blocks, org_inn

ensure_licmatch_path()

import licmatch as lm  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402

# The final delivery's city label -> the registry's settlement name.  The
# registry side carries no city in its toponym (only a settlement *inside* the
# city), so the join is blocked by city here rather than scored.
CITIES = {"Архангельск": "архангельск", "Северодвинск": "северодвинск",
          "Новодвинск": "новодвинск"}
CITY_RE = lm.home_city_re(*CITIES)

CATERING = ACTIVITY_EN["catering"]
RETAIL = ACTIVITY_EN["retail"]

# When two name keys agree (`names_agree()`).  Not the licmatch name term:
# WRatio falls back on a partial ratio when one key is much shorter, which
# reads holder "миг" into a fascia "мигрант" at 0.90.  The rule works on whole
# words instead, and on a Latin transliteration as well as the keys themselves,
# because a fascia and its holder are often one name in two scripts ("El Fuego"
# / ООО «Эль Фуэго»).
NAME_RATIO_MIN = 85        # whole-string agreement, fuzz.ratio
NAME_SHARED_MIN_LEN = 5    # a shared word this long agrees on its own ("холмс")
# Keys this short carry too little to agree on by string ("бп", "кс").
NAME_MIN_LEN = 3
# Words that name a kind of venue or a product, not a venue.  A fascia made of
# nothing else is generic, and such a word never agrees on its own -- "Кофе" is
# not ООО «Кофе Хаус».
VENUE_WORDS = frozenset({
    "кофе", "coffee", "cafe", "пицца", "pizza", "пиццерия", "суши", "sushi",
    "роллы", "вок", "wok", "гриль", "grill", "шаурма", "шаверма", "шашлык",
    "шашлыки", "бургер", "бургерная", "хлеб", "пекарня", "кондитерская",
    "кафе-бар", "кафе-пекарня", "кафе-кондитерская", "ресторан-кафе",
    "кафе-ресторан", "кафе-столовая", "рестобар", "гастропаб", "гастробар",
    "лаундж", "лаундж-бар", "lounge", "bar", "pub", "грузинской", "японской",
    "кухни", "кухня", "семейное", "семейный", "быстрого", "питания",
    "предприятие", "служба", "доставки", "буфет", "столовая", "блюд",
    "фуд", "food", "групп", "group", "плюс", "сервис", "хаус", "house",
    "русской", "кофейня", "киоск", "автомат", "кофейный",
    "вкусно", "вкусная", "вкусный", "вкус", "точка", "экспресс", "бар-маркет",
})
# Place words: a venue may well be called "Двина" (and ООО «Двина» run it), so
# they do not make a name generic, but a shared place word alone is not a
# shared name -- "Северное сияние" is not ООО «Север Плюс».
PLACE_WORDS = frozenset({
    "архангельск", "северодвинск", "новодвинск", "поморье", "поморский",
    "поморская", "север", "северный", "северная", "двина", "двинская",
    "двинской", "беломорский", "беломорье",
})
COMMON_WORDS = VENUE_WORDS | PLACE_WORDS

# A venue named in the registry's premises text: quoted after the venue word or
# anywhere, or a capitalised name right after it («кафе Караван (пом. 4)»).
_VENUE = r"(?:лобби-бар|гастробар|кафе|ресторан|бар|паб|буфет|столовая|кофейня|пиццерия|закусочная|трактир)"
_QUOTED = re.compile(r"[\"«“]([^\"»”]{2,60})[\"»”]")
_BARE = re.compile(_VENUE + r"\s+([A-ZА-ЯЁ0-9][^,($)]{1,40})")
# Municipality boilerplate that trails a bare name: "... м.о. Город Северодвинск".
_TAIL_NOISE = re.compile(r"\s+(?:г\.?\s?о\.?|м\.?\s?о\.?|го|городской округ)\b.*$", re.I)

OUT_COLUMNS = ["egais_match", "egais_licence_no", "egais_holder", "egais_inn",
               "egais_status", "egais_activity", "egais_outlet_address",
               "egais_distance_m", "egais_score", "egais_note"]


def premises_text(addr: str) -> str:
    """The free-form tail of the registry's comma-packed outlet address (slot 10+)."""
    parts = str(addr).split(",")
    return ",".join(parts[10:]).replace("&quot$", '"').replace("&quot;", '"')


def _not_municipality(name: str) -> bool:
    return not re.match(r"(?:город|г\.|городской|м\.?о|г\.?о)\b", name.strip(), re.I)


def premises_venue(addr: str) -> str:
    """The venue name the registry writes into the premises text, or "".

    'часть пом. 22, 1 этаж, кафе Трактир' -> 'Трактир';
    'ресторан "Йоко" (пом. 9, 1 этаж)' -> 'Йоко'.  A quoted name wins over a
    bare one; neither is guessed when the text names only the room.
    """
    tail = premises_text(addr)
    # A quoted "Город Северодвинск" is the municipality, not a venue.
    quoted = [q.strip() for q in _QUOTED.findall(tail) if _not_municipality(q)]
    if quoted:
        return quoted[0]
    m = _BARE.search(tail)
    if m:
        return _TAIL_NOISE.sub("", m.group(1)).strip()
    return ""


def load_registry(path=None) -> pd.DataFrame:
    """The three-city extract (`parse-egais-final`), with its city and venue name."""
    eg = load_egais(path or EGAIS_FINAL_TSV)
    settle = eg["outlet_settlement"].map(lambda s: lm.fold(s).split()[0] if str(s).strip() else "")
    eg["city_key"] = settle.where(settle.isin(set(CITIES.values())), "")
    eg["venue"] = eg["outlet_address"].map(premises_venue)
    return eg.reset_index(drop=True)


def _registry_side(eg: pd.DataFrame, names) -> pd.DataFrame:
    blocks = egais_blocks(eg["outlet_address"])
    top = [lm.parse_address_fields(s, h, CITY_RE, sub, b) for s, h, sub, b in zip(
        eg["outlet_street"], eg["outlet_house"], eg["outlet_subsettlement"], blocks)]
    return lm.side(top, names, eg["latitude"], eg["longitude"], alias_keys=org_inn(eg))


_LATIN = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y",
    "ь": "", "э": "e", "ю": "yu", "я": "ya"})


def latin(key: str) -> str:
    """A folded key in Latin letters, so a name written in either script compares."""
    return key.translate(_LATIN)


def is_generic_name(key: str) -> bool:
    """No word of the key names this venue rather than a kind of venue."""
    toks = lm.brand_key(key).replace("-", " ").split()
    return (len(key) < NAME_MIN_LEN or lm.is_generic(key)
            or all(t in VENUE_WORDS or t.isdigit() or len(t) < 2 for t in toks))


def names_agree(x: str, y: str) -> bool:
    """Do two name keys say the same venue / company?

    Yes when the whole strings agree (fuzz.ratio >= NAME_RATIO_MIN), when every
    word of one is a word of the other ("мясо" / "гастробар мясо", "осень" /
    "золотая осень"), or when they share a distinctive word of at least
    NAME_SHARED_MIN_LEN letters ("холмс" / "холмс фуд") -- each tried on the
    keys and on their Latin transliteration.  A generic key (VENUE_WORDS only)
    never agrees, and neither the subset nor the shared word may consist of
    COMMON_WORDS alone.
    """
    if is_generic_name(x) or is_generic_name(y):
        return False
    for u, v in ((x, y), (latin(x), latin(y))):
        if fuzz.ratio(u, v) >= NAME_RATIO_MIN:
            return True
        tu = {t for t in lm.brand_key(u).split() if len(t) > 1}
        tv = {t for t in lm.brand_key(v).split() if len(t) > 1}
        common = {latin(t) for t in COMMON_WORDS} | COMMON_WORDS
        small = tu if len(tu) <= len(tv) else tv
        if small and small <= (tu & tv) and not small <= common:
            return True
        if any(len(t) >= NAME_SHARED_MIN_LEN and t not in common for t in tu & tv):
            return True
    return False


def _name_agrees(a_keys: np.ndarray, b_keys: np.ndarray) -> np.ndarray:
    """(objects x licences) mask of `names_agree()`, each distinct pair once."""
    ua, ia = np.unique(a_keys, return_inverse=True)
    ub, ib = np.unique(b_keys, return_inverse=True)
    ok = np.array([[names_agree(x, y) for y in ub] for x in ua], dtype=bool).reshape(len(ua), len(ub))
    return ok[ia][:, ib]


def _fmt_date(v) -> str:
    return v.strftime("%d.%m.%Y") if pd.notna(v) else ""


def _short_holder(v: str) -> str:
    """The charter's short form ('ООО "Престо"'), which is what a reader recognises."""
    s = str(v)
    i = s.lower().find(lm.SHORT_NAME_MARKER)
    return s[i + len(lm.SHORT_NAME_MARKER):].strip() if i >= 0 else s.strip()


_SECOND_ADDRESS = re.compile(r"/\s*(?=(?:" + "|".join(CITIES) + r")\b)")


def split_address(v: str) -> tuple[str, str]:
    """"Троицкий проспект, 17/Архангельск, набережная ..., 61" -> (first, second).

    Only a slash followed by a city name starts a second address; "37/1" and
    "Мира, 5/3" are one house.
    """
    parts = _SECOND_ADDRESS.split(str(v), maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def _pick(x: lm.Scores, y: lm.Scores, use_y: np.ndarray) -> lm.Scores:
    """`x` with `y`'s values wherever `use_y`."""
    return lm.Scores(**{k: (np.where(use_y, getattr(y, k), getattr(x, k))
                            if getattr(x, k) is not None else None)
                        for k in x.as_dict()})


def _rank(sc: lm.Scores) -> np.ndarray:
    """Admitted pairs first, then by score."""
    return lm.accepted(sc, PARAMS) * 10.0 + np.nan_to_num(sc.score, nan=-1.0)


def _empty(index: pd.Index) -> pd.DataFrame:
    """The result for objects the registry says nothing about."""
    out = pd.DataFrame({c: "" for c in OUT_COLUMNS}, index=index)
    out["egais_match"] = False
    out["egais_distance_m"] = np.nan
    out["egais_score"] = np.nan
    return out


def _match_city(ob: pd.DataFrame, eg: pd.DataFrame) -> pd.DataFrame:
    """`match_catering()` for one city's objects against that city's licences."""
    out = _empty(ob.index)
    if ob.empty or eg.empty:
        return out

    a_keys = np.array([lm.fascia_name(v) for v in ob["name"]], dtype=object)
    h_keys = np.array([lm.holder_name(v) for v in eg["org_name"]], dtype=object)
    v_keys = np.array([lm.fascia_name(v) for v in eg["venue"]], dtype=object)
    b_h, b_v = _registry_side(eg, h_keys), _registry_side(eg, v_keys)

    def score_for(addresses) -> lm.Scores:
        # Scored twice, once against the holder and once against the venue
        # name; the address and distance terms are the same, the pair keeps
        # the better name.
        a = lm.side([lm.parse_address_line(v, CITY_RE) for v in addresses],
                    a_keys, ob["lat"], ob["lon"])
        s_h, s_v = lm.score_matrix(a, b_h, PARAMS), lm.score_matrix(a, b_v, PARAMS)
        return _pick(s_h, s_v, np.nan_to_num(s_v.name) > np.nan_to_num(s_h.name))

    # A corner building is written as two addresses ("Троицкий проспект, 17/
    # Архангельск, набережная Северной Двины, 61"); each pair keeps the better.
    first, second = zip(*(split_address(v) for v in ob["address"]))
    sc = score_for(first)
    if any(second):
        sc2 = score_for([b or a for a, b in zip(first, second)])
        sc = _pick(sc, sc2, _rank(sc2) > _rank(sc))

    at_addr = lm.accepted(sc, PARAMS)
    near = sc.method == lm.ROUTE_GEO
    by_holder = _name_agrees(a_keys, h_keys)
    by_venue = _name_agrees(a_keys, v_keys)
    named = by_holder | by_venue
    act = eg["is_active"].to_numpy(bool)[None, :]
    cat = (eg["activity_class"].to_numpy() == CATERING)[None, :]
    ret = (eg["activity_class"].to_numpy() == RETAIL)[None, :]
    score = np.nan_to_num(sc.score, nan=-1.0)

    def best(mask: np.ndarray, i: int) -> int:
        row = np.where(mask[i], score[i], -np.inf)
        return int(np.argmax(row)) if np.isfinite(row).any() else -1

    own = at_addr & cat & act & named
    choice = np.array([best(own, i) for i in range(len(ob))])

    # One outlet, one venue: where an outlet agrees with objects whose names do
    # not agree with each other, the strongest claim keeps it and the others
    # lose it.  Records of one venue ("Престо" / "Престо, ресторан-кафе") share.
    # The outlet is the holder at one address *and* one named venue where the
    # registry names it: ООО «Луда-Старт» files "бар Луда" and "кафе Крона" at
    # Нагорная, 3 under one licence number, and they are two venues.
    units = (org_inn(eg) + "@" + eg["outlet_street"].astype(str) + "|"
             + eg["outlet_house"].astype(str) + "|" + v_keys).to_numpy(dtype=object)
    taken_by = np.full(len(ob), -1)
    claims = pd.DataFrame({"i": np.flatnonzero(choice >= 0)})
    if len(claims):
        claims["unit"] = units[choice[claims["i"]]]
        claims["score"] = score[claims["i"], choice[claims["i"]]]
        for _, g in claims.groupby("unit"):
            win = g.loc[g["score"].idxmax()]
            w = int(win["i"])
            lose = g[[not (i == w or a_keys[i] == a_keys[w] or names_agree(a_keys[i], a_keys[w]))
                      for i in g["i"]]]
            taken_by[lose["i"].to_numpy()] = int(win["i"])
            choice[lose["i"].to_numpy()] = -1

    holder = eg["org_name"].map(_short_holder).to_numpy(dtype=object)
    names = ob["name"].astype(str).to_numpy(dtype=object)
    generic = np.array([is_generic_name(k) for k in a_keys])
    rows = []
    for i in range(len(ob)):
        j, note = choice[i], ""
        if j >= 0:
            via = "владелец" if by_holder[i, j] else "название заведения в адресе лицензии"
            note = f"подтверждено: совпадает {via}"
        elif taken_by[i] >= 0:
            j = best(own, i)
            note = (f"лицензия общепита по адресу совпадает по названию, но закреплена "
                    f"за объектом «{names[taken_by[i]]}»")
        elif (j := best(at_addr & cat & act, i)) >= 0:
            note = ("действующая лицензия общепита по адресу есть, но название объекта "
                    "общее — владельца по нему не установить" if generic[i] else
                    f"действующая лицензия общепита по адресу есть, но другого владельца "
                    f"({holder[j]})")
        elif (j := best(at_addr & cat & named, i)) >= 0:
            when = _fmt_date(eg.at[j, "status_changed"])
            note = (f"лицензия общепита с тем же названием по адресу не действует "
                    f"({eg.at[j, 'status']}{', ' + when if when else ''})")
        elif (j := best(near & cat & act & named & ~at_addr, i)) >= 0:
            note = (f"действующая лицензия общепита с тем же названием в "
                    f"{sc.distance[i, j]:.0f} м, но по другому адресу")
        elif (j := best(at_addr & cat, i)) >= 0:
            note = f"по адресу только недействующие лицензии общепита другого владельца ({holder[j]})"
        elif (j := best(at_addr & ret & act, i)) >= 0:
            note = ("по адресу только розничная лицензия с тем же названием (не общепит)"
                    if named[i, j] else "по адресу только розничная лицензия (не общепит)")
        else:
            j = -1
        rows.append((j, note))

    for i, (j, note) in enumerate(rows):
        idx = ob.index[i]
        out.at[idx, "egais_note"] = note
        if j < 0:
            continue
        out.at[idx, "egais_match"] = bool(choice[i] >= 0)
        out.at[idx, "egais_licence_no"] = eg.at[j, "licence_no"]
        out.at[idx, "egais_holder"] = holder[j]
        out.at[idx, "egais_inn"] = org_inn(eg.iloc[[j]]).iloc[0]
        out.at[idx, "egais_status"] = eg.at[j, "status"]
        out.at[idx, "egais_activity"] = eg.at[j, "activity"]
        out.at[idx, "egais_outlet_address"] = eg.at[j, "outlet_address"]
        d = sc.distance[i, j]
        out.at[idx, "egais_distance_m"] = round(float(d), 1) if np.isfinite(d) else np.nan
        s = sc.score[i, j]
        out.at[idx, "egais_score"] = round(float(s), 3) if np.isfinite(s) else np.nan
    return out


def match_catering(ob: pd.DataFrame, eg: pd.DataFrame | None = None) -> pd.DataFrame:
    """Does an in-force catering licence of this object's own stand at its address?

    `ob` has columns city, name, address (street, house -- no city prefix, may
    be ''), lat, lon; its index is the object id.  Returns a frame indexed like
    `ob` with:

    egais_match           True only when an in-force licence permitting catering
                          clears both floors at the object's address *and* its
                          holder or registry venue name agrees with the object's
                          name (see the module docstring);
    egais_licence_no, egais_holder, egais_inn, egais_status, egais_activity,
    egais_outlet_address  the confirming licence, or for a near-miss the licence
                          the note talks about; '' when the registry holds
                          nothing relevant;
    egais_distance_m      object -> registry coordinate (NaN on the address-only
                          route, or when there is no licence);
    egais_score           the licmatch pair score;
    egais_note            a short Russian reason, '' when nothing is there.

    `eg` defaults to the three-city extract (`load_registry()`).
    """
    eg = load_registry() if eg is None else eg
    # A city the extract does not cover keeps the empty result.
    res = _empty(ob.index)
    city = ob["city"].astype(str).str.strip()
    for name, key in CITIES.items():
        sub = ob[city == name]
        if len(sub):
            res.loc[sub.index] = _match_city(sub, eg[eg["city_key"] == key]
                                             .reset_index(drop=True))
    res["egais_match"] = res["egais_match"].astype(bool)
    return res[OUT_COLUMNS]
