# The alcohol objects with no licence of their own, checked on Yandex Maps

`pixi run check-yandex` works the queue the licence join leaves behind. Of the
945 alcohol records in the fourth delivery, **440 hold no FSRAR licence of their
own** — every alcohol row whose `licence_status` is in `STATUS_NO_OWN`. Since
the join gives one licensed outlet to at most one object and checks the
licence's trade and chain, "no licence of its own" has four causes, and
`docs/v4_egais_match.md` spells each out:

| Status | Rows | What the address holds |
| --- | ---: | --- |
| `Not in registry` | 179 | Nothing: no licence clears both floors. |
| `Taken` | 64 | A licence of the right trade, but its outlet went to another shop with the stronger claim (`licence_claimed_by`). |
| `Other chain` | 114 | The known brands rule every licence here out: the object is a known chain and none is its own, or each licence is a known chain's and the object is not that chain. |
| `Other trade` | 83 | Only licences of the other trade — a shop licence at a bar, a catering one at a shop, or a wholesale one. |

`Not in registry` is itself the union of "this object genuinely holds no
licence", "the licence is filed under an address neither route could reach" and
"the export's address is wrong". The registry cannot separate the three. It is
one register, asked one question. The other three statuses are not "no licence
at this address" at all — a licence is there, and the join decided it is not
this object's.

A directory can answer a different question, and a simpler one: **is there an
organisation of that name at that address at all?** If neither FSRAR nor Yandex
Maps knows the object, the row's evidence has thinned to the vendor's own tag,
and that is a fact worth writing next to it. The result is
`data/processed/v4_alcohol_none_yandex.csv` — one row per object, with its
`licence_status` (and `licence_claimed_by` for a `Taken` row), the mark, the URL
the mark came from, and what Yandex actually returned.

The rule is `src/arkhinfra/v4_yandex.py`; the runner is
`scripts/check_yandex_v4.py`; the Russian report
`analysis/v4/licences-v4-ru.qmd` prints the mark as a hyperlink beside every
object in its list.

## What is asked, and how

One request per object, the same one a person would type into Yandex Maps: the
object's name, then its address, with the map centred on the object's own
coordinate.

```
https://yandex.ru/maps/20/arkhangelsk/search/<name>, Архангельск, <address>/?ll=<lon>,<lat>&z=17
```

Yandex renders that page server-side, so the answer is in the HTML: either one
business card (`data-object="search-result"`, carrying `data-coordinates`, the
`itemProp="name"` heading and an `itemProp="address"` meta) or a list of
snippets (`data-object="search-list-item"`), or neither, and the `canonical`
link says which — `/maps/org/…` for a card, `/house/…` when only the address
resolved, the search URL itself for a list. Both shapes are parsed into the
same list of candidates.

Three details are load-bearing:

* **The city is repeated inside the query text** although the URL path
  (`/20/arkhangelsk/`) and `ll` already carry it. Neither binds a query Yandex
  cannot place locally: "Елена, улица Адмирала Макарова, 38" alone answers with
  a garden plot near Kirov, and an address with no house number answers with a
  street in Baku. With the city in the text, both fall back to the object's own
  neighbourhood or to nothing.
* **The heading is read to its closing tag**, not to the first `</`. The title
  opens with an empty hidden `<span>`; stopping at that span's end yields a
  name of `""` and turns every match into a miss.
* **Yandex throttles.** A refused request comes back as a page whose entire
  body is the word `limited` — HTTP 200, no error to catch. `fetch()` treats a
  short page as a refusal and waits it out, 20 s, then 40 s, then 60 s.

## When a candidate counts as the object

| Term | Value | Why |
| --- | --- | --- |
| radius | 150 m | The export's coordinates (2GIS, OSM) agree with Yandex's to a few metres on the same shop. 150 m is a building and its yard, not a block. |
| radius, generic fascia | 60 m | "Продукты" is a handful of objects in the queue and a hundred more in the city; distance is then the only real evidence. |
| name similarity | ≥ 72 of 100 | Over `licmatch.fascia_name` keys — the same normaliser the licence join uses, so "Казацкая слобода, кафе" and "Казацкая слобода" are one name. |

Before any of that, **plain addresses are dropped from the candidates**. A
result list mixes organisations with the toponym itself — "улица Зеньковича, 8"
arrives with a coordinate and no address of its own — and a street is never the
object. A business may also arrive without an address ("Штаб" does), so the
test requires both: no address *and* a street word in the name. The word list
is written out rather than taken from `licmatch.TYPE_TABLE` wholesale, because
that table holds "городок" and one of the objects in the queue is called exactly that.

The name term is the whole of the judgement once distance is spent, and two
shapes of the same name have to pass where one must not:

* **The delivery writes "fascia, trade": "Штаб, ресто-кафе".** `fascia_name`
  drops the trade words it knows — `кафе`, `магазин`, `бар` — but not the
  hyphenated compound `ресто-кафе`, and the leftover sinks a perfect match
  against Yandex's plain "Штаб" to 57. What survives the comma is therefore
  compared as well as the whole name, best form wins.
* **A subset is not free.** `token_set_ratio` scores any subset 100, which
  correctly reads "Beer & Honey" into "Beer & Honey Brewery" 17 m away — and
  just as happily reads "Бакарица" into "МУК ИЦКЦ филиал Бакарица" 12 m away,
  which is a culture centre in the same building, not the shop. The subset
  match is therefore allowed only where the shorter key is at least **half** of
  the longer: 56 % for the brewery, 33 % for the culture centre.

## The four marks

| Mark | Meaning |
| --- | --- |
| `present` (есть) | An organisation of that name stands at that address. |
| `closed` (закрыт) | Found, and Yandex marks it "Больше не работает" or "Временно не работает". |
| `ambiguous` (не опознан) | The address is occupied, but the export's name is a trade descriptor whole — "Столовая", "Кафе" — so no name can decide whose door it is. |
| `absent` (нет) | Nothing of that name there. The nearest organisation found is recorded in `yandex_nearby`, because what *does* stand there is the next thing a reader asks. |
| `error` | Yandex did not answer after four tries. The row claims nothing. |

`closed` is deliberately kept apart from both yes and no: a shop that has gone
**explains** a missing licence rather than contradicting the tag, and folding it
into "absent" would lose exactly the finding that matters.

## What the mark is not

* **A Yandex hit is not a licence.** The directory carries no licences at all.
  `present` says the door exists and someone trades there, never that alcohol is
  sold legally behind it. The FSRAR answer for every one of these rows is still
  "no licence of its own" — and for `Not in registry`, "no licence at this
  address".
* **A `Taken` row that is `present` is not a second licensed counter.** It says
  two doors exist where the registry has one outlet; which of them trades under
  the licence — or whether both are one business under two names — is exactly
  what the mark cannot decide.
* **A miss is not proof of absence.** A commercial directory is incomplete, the
  snapshot was taken on one day, and a small shop with no signage may simply
  never have been added.
* **`ambiguous` is not a soft no.** It is a statement that the export's own name
  cannot identify the object, which is a defect of the delivery, not of Yandex.
* **The check runs on the alcohol layer only.** The tobacco layer has no
  registry to fail against — there is no tobacco licence register in Russia
  before 2027 (see `docs/egais_source_notes.md`) — so "no licence" is not a
  signal there and this check would answer a question nobody asked.

## The runs of 2026-09-22 and 2026-09-23

The first run read the 179 `Not in registry` rows, when that was the whole
queue. The later runs of 2026-09-23 followed the join as it gained its choice
rules and read only rows new to the queue. The cache is keyed by `site_key`, and
every `Not in registry` row of the first run is `Not in registry` still. All 440
pages were read, none refused, no `error`.

| Mark | Objects | % of the queue |
| --- | ---: | ---: |
| present | 155 | 35.2 |
| closed | 127 | 28.9 |
| ambiguous | 13 | 3.0 |
| absent | 145 | 33.0 |

By the reason the object holds no licence of its own:

| Status | present | closed | ambiguous | absent | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Not in registry | 64 | 44 | 7 | 64 | 179 |
| Taken | 28 | 11 | 0 | 25 | 64 |
| Other chain | 31 | 50 | 6 | 27 | 114 |
| Other trade | 32 | 22 | 0 | 29 | 83 |

**Over a quarter of the queue is shops that have closed.** That is the single
most common answer to "why does this object hold no licence": the outlet is
gone. Such a row is not a mis-tagged object; it is a stale one, and it should not
be counted as live city infrastructure. The 440 rows are not 440 open questions
about licensing.

`Other chain` stands out: 50 of its 114 rows are closed (44 %, against 25 % of
`Not in registry`). That fits independent shops, since replaced by the chain
whose licence stands at their door, that the delivery still lists. It fits
less well the reading that a chain's licence was wrongly withheld from them.

The `present` share is flat — 27–44 % in each status — so the mark does
not separate the join's new statuses from the old one; what a `present` row
means does differ (see "What the mark is not").

The 158 rows that are `absent` or `ambiguous` are the queue for an actual site
visit: neither the registry nor the directory knows them. For every `absent`
row the summary file lists the nearest organisation Yandex does have at that
door, which frequently answers the question on its own — "Автошкола Топ драйв,
6 m" at the address of an object tagged as an alcohol shop.

**`absent` is inflated by transliteration.** The name key compares the two
spellings as written, and the delivery often writes a fascia in Latin where
Yandex writes it in Cyrillic, or the reverse: "Millstream" is `absent` with
"Мильстрим" 4 m away, and so are "Polina" / "Полина" (16 m), "Edison" / "Бар
Эдисон" (3 m), "Charlie" / "Чарли" (13 m), "Karlz" / "Карлз бар" (8 m),
"Hati-sushi" / "Хати-суши" (16 m), "Тепло" / "Teplo" (2 m) and "GoodWines-GoodTimes"
/ "Гудвайнс гудтаймс". Read `yandex_nearby` before counting an `absent` row as
a door nobody knows; the rule itself has not been changed.

## The cache

Every answer is stored in `data/processed/v4_yandex_cache.jsonl`, one line per
object keyed by `site_key` (the `lat|lon` pair, unique across the queue), and what
is stored is the **page's answer, not the verdict**: every candidate with its
name, address and coordinate.

That matters more than it looks. Judging happens on the way out of the cache, so
moving a threshold re-decides the whole queue with no requests at all — which is
how the name rule above was fixed after it marked "Штаб" absent. It also means
an interrupted run resumes, the report never reaches the network, and a single
row is re-read by deleting its line. `--refresh` re-reads everything.

The cache is a **snapshot**. Every row carries `checked`, the date its page was
read, and Yandex is a living directory: a re-run months later will not reproduce
it exactly, and should not be expected to.
