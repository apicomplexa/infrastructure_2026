"""Ask Yandex Maps whether an object of the fourth delivery is actually there.

The licence join leaves 440 alcohol rows holding no licence of their own
(`v4_egais.STATUS_NO_OWN`), 179 of them with no licence at their address at
all, and `licences-v4-ru.qmd` calls them what they are: candidates for manual
checking, not proven mistakes.  Three readings fit an empty result -- the tag is wrong,
the licence sits at another address, or the object is catering with no licence
of its own -- and the registry cannot tell them apart.  A third directory can:
if Yandex Maps has no organisation at that door either, the row is far more
likely to be stale than to be a licensing question.

This is that check, done once and written down.  For every object it issues the
*same query a person would type* -- name, then address, with the map centred on
the object's own coordinate -- and reads the answer off the page Yandex renders
server-side: a business card carrying `data-coordinates`, or a list of
snippets, or neither.  A candidate is accepted only when it stands within
`NEAR_M` of the object and its name key matches; everything else is recorded
and left for the reader to judge.  Yandex marks dead organisations "Больше не
работает", and that flag is kept apart from both "found" and "not found": a
closed shop explains a missing licence rather than contradicting the tag.

What the cache holds is the page's *answer*, not the verdict: every
organisation Yandex put on the page, with its name, address and coordinate, one
JSONL line per object keyed by `site_key`.  Judging happens on the way out, so
a threshold can be moved and the whole list re-decided without a single
request; the report never reaches the network, and a row is re-read only by
deleting its line.  The cache is a *snapshot*: Yandex is a living directory,
and every row carries the date it was read.

Nothing here knows about tobacco.  The tobacco layer has no registry to fail
against, so "no licence" is not a signal there and this check would answer a
question nobody asked.
"""
from __future__ import annotations

import html as _html
import http.client
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz

from .paths import PROC_YANDEX, ensure_licmatch_path

ensure_licmatch_path()

from licmatch import fascia_name, fold, haversine_m  # noqa: E402

CACHE = PROC_YANDEX / "v4_yandex_cache.jsonl"
OUT_CSV = PROC_YANDEX / "v4_alcohol_none_yandex.csv"
OUT_TXT = PROC_YANDEX / "v4_alcohol_none_yandex_summary.txt"

# Arkhangelsk is region 20 in Yandex's own URL space; the city prefix keeps an
# unanchored query inside the city, and the URL is the one a person's browser
# would show, so a reader can paste it and see what was read.
CITY_PATH = "https://yandex.ru/maps/20/arkhangelsk/search/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# A hit must stand at the object's own door, not merely in its quarter: the
# export's coordinates come from 2GIS and OSM and agree with Yandex's to a few
# metres where both describe the same shop.  150 m is a building, not a street.
NEAR_M = 150.0
# The name term decides alone once distance is spent, so it is set higher than
# the licence join's tie-breaker: "Продукты" must not claim the "Пятёрочка"
# next door.  Ratio over `fascia_name` keys, which drop the trade descriptor
# the export appends ("Казацкая слобода, кафе" -> "казацкая слобода").  How the
# two keys are compared, and why a subset is not free, is `name_similarity`.
NAME_MIN = 72.0
# How much of the *directory's* name the export's has to be before a subset
# match is allowed.  "beer honey" is 56 % of "beer honey brewery"; "бакарица"
# is 33 % of "мук ицкц филиал бакарица".  The other direction -- the directory
# named inside a longer export name -- needs no such floor, only a name long
# enough not to be a fragment.
CONTAIN_MIN = 0.5
CONTAIN_MIN_CHARS = 4
# A generic fascia matches any other generic fascia, so those rows are accepted
# only at arm's length -- one building's depth, not the block's.
GENERIC = frozenset({"продукты", "продукты 24", "продуктовый", "минимаркет",
                     "вино", "разливное", "разливные напитки", "пиво",
                     "живое пиво", "пивной", "табак", "алкоголь", "универсам",
                     "food", "еда", "24 часа", "круглосуточно"})
GENERIC_M = 60.0

# A result list mixes organisations with plain addresses -- "улица Зеньковича,
# 8" arrives with a coordinate and no address of its own.  Those are not
# businesses and must not stand in for one, least of all as the "something is
# open at this door" that turns `absent` into `ambiguous`.  Written out rather
# than taken from `licmatch.TYPE_TABLE` wholesale: that table also holds
# "городок", and one of the objects in the queue is called exactly that.
TOPONYM_WORD = re.compile(
    r"\b(улиц\w*|проспект\w*|переул\w*|набережн\w*|шоссе|площад\w*|проезд\w*"
    r"|бульвар\w*|тракт|алле\w*|тупик|микрорайон\w*)\b", re.I)

CLOSED_MARK = "Больше не работает"
PAUSED_MARK = "Временно не работает"

STATUS_PRESENT = "present"      # organisation found at the address, open
STATUS_CLOSED = "closed"        # found, but Yandex marks it closed
STATUS_AMBIGUOUS = "ambiguous"  # the door is occupied, the export's name is generic
STATUS_ABSENT = "absent"        # nothing of that name at that door
STATUS_ERROR = "error"          # Yandex did not answer; nothing is claimed

STATUS_RU = {STATUS_PRESENT: "есть", STATUS_CLOSED: "закрыт",
             STATUS_AMBIGUOUS: "не опознан", STATUS_ABSENT: "нет",
             STATUS_ERROR: "не пров."}
STATUS_ORDER = [STATUS_PRESENT, STATUS_CLOSED, STATUS_AMBIGUOUS,
                STATUS_ABSENT, STATUS_ERROR]

# Yandex answers an automated burst with a one-word body; it is not an HTTP
# error, so it has to be recognised by sight and waited out.
LIMITED = re.compile(r"^\s*(?:<[^>]*>)*\s*limited\s*(?:<[^>]*>)*\s*$", re.I)


def strip_city(address: str) -> str:
    """Drop the repeated city prefix: "Архангельск, улица Дрейера, 49" -> the rest."""
    return re.sub(r"^\s*Архангельск,\s*", "", str(address)).strip()


def search_url(name: str, address: str, lat: float, lon: float) -> str:
    """The URL this check reads -- and the one to paste into a browser.

    Query and viewport both: the text is what a person would type, `ll` centres
    the map on the object so the answer is its neighbourhood's, not the city's.
    The city is repeated inside the query although the path already carries it,
    because neither the path nor `ll` binds a query Yandex cannot place: "Елена,
    улица Адмирала Макарова, 38" alone answers with a garden plot near Kirov.
    """
    q = f"{name}, Архангельск, {strip_city(address)}".strip(" ,")
    return (CITY_PATH + urllib.parse.quote(q, safe="")
            + f"/?ll={lon:.6f}%2C{lat:.6f}&z=17")


@dataclass
class Candidate:
    """One organisation Yandex put on the page, as the page states it."""

    oid: str = ""
    name: str = ""
    address: str = ""
    lat: float | None = None
    lon: float | None = None
    closed: bool = False
    paused: bool = False

    @property
    def url(self) -> str:
        return f"https://yandex.ru/maps/org/{self.oid}/" if self.oid else ""


@dataclass
class Answer:
    """What one page said, before any judgement is passed on it.

    This is what goes into the cache, so that moving a threshold re-decides the
    list instead of re-reading it.
    """

    url: str = ""
    canonical: str = ""
    og_title: str = ""
    candidates: list[Candidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"search_url": self.url, "canonical": self.canonical,
                "og_title": self.og_title,
                "candidates": [vars(c) for c in self.candidates]}

    @classmethod
    def from_dict(cls, rec: dict) -> "Answer":
        return cls(url=rec.get("search_url", ""),
                   canonical=rec.get("canonical", ""),
                   og_title=rec.get("og_title", ""),
                   candidates=[Candidate(**c) for c in rec.get("candidates", [])])


def _text(chunk: str) -> str:
    return _html.unescape(re.sub(r"<[^>]*>", " ", chunk)).strip()


def _first(pattern: str, chunk: str, group: int = 1) -> str:
    m = re.search(pattern, chunk, re.S)
    return _html.unescape(m.group(group)) if m else ""


def _coord(chunk: str, group: int) -> float | None:
    m = re.search(r'data-coordinates="([-0-9.]+),([-0-9.]+)"', chunk[:400])
    return float(m.group(group)) if m else None


def _card(chunk: str) -> Candidate:
    """A single resolved organisation: the page's own business card.

    The title is read to its closing tag rather than to the first `</`: the
    heading opens with an empty hidden span, and stopping at that span's end
    yields a name of "".
    """
    return Candidate(
        oid=_first(r'data-id="([^"]*)"', chunk[:400]),
        name=_text(_first(r'itemProp="name"[^>]*>(.*?)</h1>', chunk)),
        address=_first(r'itemProp="address" content="([^"]*)"', chunk),
        lat=_coord(chunk, 2), lon=_coord(chunk, 1),
        closed=CLOSED_MARK in chunk, paused=PAUSED_MARK in chunk,
    )


def _snippet(chunk: str) -> Candidate:
    """One row of a result list, whose markup differs from the single card."""
    return Candidate(
        oid=_first(r'data-id="([^"]*)"', chunk[:400]),
        name=_text(_first(r'search-business-snippet-view__title[^>]*>(.*?)</', chunk)),
        address=_text(_first(r'search-business-snippet-view__address[^>]*>(.*?)</div', chunk)),
        lat=_coord(chunk, 2), lon=_coord(chunk, 1),
        closed=CLOSED_MARK in chunk, paused=PAUSED_MARK in chunk,
    )


def parse(page: str, url: str = "") -> Answer:
    """Read the organisations off a rendered search page.

    Yandex serves two shapes for the same question -- one card when the query
    resolves to a single place, a list of snippets when it does not -- and the
    difference is markup only, so both are collected into one list.  The
    canonical link says which shape it was: `/maps/org/...` for a card,
    `/house/...` when only the address resolved, the search URL for a list.
    """
    a = Answer(url=url,
               canonical=_first(r'<link rel="canonical" href="([^"]*)"', page),
               og_title=_first(r'<meta property="og:title" content="([^"]*)"', page))
    for chunk in _blocks(page, 'data-object="search-result"'):
        a.candidates.append(_card(chunk))
    for chunk in _blocks(page, 'data-object="search-list-item"'):
        a.candidates.append(_snippet(chunk))
    return a


# Result-list items sit about 5,000 characters apart, so a block cut to a fixed
# length swallows the three that follow it -- and with them their "Больше не
# работает", which would then be read as this one's.  Every block therefore
# ends where the next result begins.
BLOCK_MAX = 20000


def _blocks(page: str, marker: str):
    """The page's result blocks, each ending where the next result starts."""
    for part in page.split(marker)[1:]:
        cut = part.find('data-object="')
        yield part[:cut if cut != -1 else BLOCK_MAX]


def fetch(url: str, *, tries: int = 5, pause: float = 5.0) -> str:
    """One page, retried patiently: a refusal here is a rate limit, not a 404.

    The backoff doubles from five seconds rather than starting at twenty: a
    throttled run spends most of its wall clock in this function, and Yandex
    lets the next request through far sooner than a flat long pause assumes.
    """
    last = ""
    for i in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9",
            "Accept": "text/html,application/xhtml+xml"})
        try:
            page = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
            if not LIMITED.match(page) and len(page) > 5000:
                return page
            last = "rate-limited" if LIMITED.match(page) else f"short page ({len(page)} b)"
        # `IncompleteRead` is an `HTTPException`, not an `OSError`: a throttled
        # connection is as likely to be cut mid-body as refused outright, and
        # leaving it uncaught ends a two-hour run at row 118.
        except (urllib.error.URLError, http.client.HTTPException,
                TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(pause * 2 ** i)
    raise RuntimeError(last or "no answer")


def _keys(name: str) -> list[str]:
    """The forms of one export name worth comparing, best first.

    The delivery writes a fascia and then its trade: "Штаб, ресто-кафе".
    `fascia_name` drops the words it knows -- "кафе", "магазин" -- but not
    "ресто-кафе", and the leftover is enough to sink a perfect match against
    Yandex's plain "Штаб".  What survives the comma is therefore compared as
    well as the whole, and whichever form scores better wins.
    """
    forms = [fascia_name(name.split(",")[0]), fascia_name(name)]
    return [f for f in dict.fromkeys(forms) if f]


def name_similarity(export: str, directory: str) -> float:
    """How alike two fascias are, on the distinctive part where there is one.

    The two sides are *not* symmetric, and the rule says so.  The delivery
    writes a sign with words around it -- "Кафе-бар «Флайт»", "Банкетный зал
    «Прованс Hall»", "Дом пивовара на Гайдара" -- where Yandex writes the sign
    alone; when the directory's whole name sits inside the export's, that is
    the same business described at two lengths.  The other direction is not
    safe: the export's bare "Бакарица" also sits inside "МУК ИЦКЦ филиал
    Бакарица" 12 m away, which is a culture centre, not the shop.  A name the
    *directory* extends is therefore accepted only where the export's name is
    most of it -- 56 % of "Beer & Honey Brewery", against 33 % of the culture
    centre -- and the cut is half.

    Short of containment, two spellings of one name are compared twice.
    `ratio` handles a name split differently on each side ("АлкоShop" against
    "Алко shop"); `token_sort_ratio` handles reordered words.  The first is
    needed because sorting turns "алкоshop" into itself and "алко shop" into
    "shop алко", which then agree on almost nothing.

    Where `fascia_name` empties a side -- an object called "Столовая" -- the
    written names are compared instead, and `is_generic()` tells the caller
    that nothing distinctive was left to compare.
    """
    ka_list, kb = _keys(export), fascia_name(directory)
    if not ka_list or not kb:
        ka_list, kb = [fold(export)], fold(directory)
    if not kb or not any(ka_list):
        return 0.0
    return max(_pair_similarity(ka, kb) for ka in ka_list if ka)


def _pair_similarity(ka: str, kb: str) -> float:
    """`ka` is the export's key, `kb` the directory's.  Order matters."""
    sim = max(float(fuzz.ratio(ka, kb)), float(fuzz.token_sort_ratio(ka, kb)))
    ta, tb = set(ka.split()), set(kb.split())
    if tb < ta and len(kb) >= CONTAIN_MIN_CHARS:
        return max(sim, 100.0)
    if ta <= tb and len(kb) and len(ka) / len(kb) >= CONTAIN_MIN:
        return max(sim, float(fuzz.token_set_ratio(ka, kb)))
    return sim


def is_generic(name: str) -> bool:
    """True where the fascia names a trade rather than a business.

    "Столовая" and "Продукты" identify nothing: the first reduces to an empty
    key, the second is shared by seven objects of this list alone.  Both are
    held to the tighter radius, and the first cannot be confirmed by name at
    all.
    """
    key = fascia_name(name)
    return key == "" or key in GENERIC


def is_toponym(cand: Candidate) -> bool:
    """True where the result is an address, not a business.

    Yandex answers an address query with the address itself alongside whatever
    stands at it.  Such a result carries a coordinate but no address of its own
    and is named for the street; a business named "Штаб" may also arrive
    without an address, which is why both conditions are required.
    """
    return not cand.address and bool(TOPONYM_WORD.search(cand.name))


def _score(cand: Candidate, name: str, lat: float, lon: float) -> tuple[float, float]:
    """(metres from the object, name similarity) for one candidate."""
    if cand.lat is None or cand.lon is None:
        return float("inf"), 0.0
    return (float(haversine_m(lat, lon, cand.lat, cand.lon)),
            name_similarity(name, cand.name))


def judge(answer: Answer, name: str, lat: float, lon: float) -> dict:
    """Decide what the page says about *this* object.

    A candidate is taken only when it is both near enough and named alike; a
    generic fascia has to be nearer still, because "Продукты" matches every
    other "Продукты" in town and distance is then the only real evidence.

    Where the export's name is a trade descriptor and something *is* open at
    that door, the answer is neither yes nor no and is not forced into one:
    `ambiguous` says the address is occupied and the name cannot decide whose
    it is.  The nearest rejected candidate is kept in every negative case --
    for a row that comes out `absent`, what *does* stand there is the next
    thing a reader asks.
    """
    orgs = [c for c in answer.candidates if not is_toponym(c)]
    scored = [(*_score(c, name, lat, lon), c) for c in orgs]
    scored.sort(key=lambda t: (t[0], -t[1]))
    generic = is_generic(name)
    limit = GENERIC_M if generic else NEAR_M

    best = next((t for t in scored if t[0] <= limit and t[1] >= NAME_MIN), None)
    if best is None:
        near = scored[0] if scored and scored[0][0] <= NEAR_M else None
        occupied = near is not None and near[0] <= GENERIC_M
        return {
            "status": (STATUS_AMBIGUOUS if generic and occupied else STATUS_ABSENT),
            "yandex_name": "", "yandex_address": "", "yandex_url": "",
            "yandex_distance_m": "", "yandex_name_sim": "",
            "yandex_nearby": (f"{near[2].name} — {near[0]:.0f} м, {near[2].address}"
                              if near else ""),
            "address_found": occupied or "/house/" in answer.canonical,
        }
    d, sim, c = best
    return {
        "status": STATUS_CLOSED if (c.closed or c.paused) else STATUS_PRESENT,
        "yandex_name": c.name, "yandex_address": c.address, "yandex_url": c.url,
        "yandex_distance_m": round(d, 1), "yandex_name_sim": round(sim, 1),
        "yandex_nearby": "", "address_found": True,
    }


def read(name: str, address: str, lat: float, lon: float, *,
         sleep: tuple[float, float] = (2.5, 4.5)) -> dict:
    """Read one object's page and return what it said -- no verdict, no opinion.

    This is the only function that touches the network, and its result is what
    the cache stores.
    """
    url = search_url(name, address, lat, lon)
    try:
        page = fetch(url)
    except RuntimeError as e:
        return {"search_url": url, "canonical": "", "og_title": "",
                "candidates": [], "note": str(e),
                "checked": date.today().isoformat()}
    answer = parse(page, url)
    time.sleep(random.uniform(*sleep))
    return {**answer.to_dict(), "note": "",
            "checked": date.today().isoformat()}


def verdict(rec: dict, name: str, lat: float, lon: float) -> dict:
    """Judge one cached answer.  Costs nothing, so thresholds stay movable."""
    if rec.get("note"):
        return {"status": STATUS_ERROR, "yandex_name": "", "yandex_address": "",
                "yandex_url": "", "yandex_distance_m": "", "yandex_name_sim": "",
                "yandex_nearby": "", "address_found": False}
    return judge(Answer.from_dict(rec), name, lat, lon)


def load_cache(path=CACHE) -> dict[str, dict]:
    """Everything checked so far, keyed by `site_key`; later lines win."""
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["site_key"]] = rec
    return out


def append_cache(rec: dict, path=CACHE) -> None:
    """One line per object, appended as it is read -- a long run is resumable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
