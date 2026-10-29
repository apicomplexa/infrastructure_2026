# Fourth delivery x FSRAR licence registry: the object-level join

`pixi run match-egais-v4` writes `data/processed/v4_licences/v4_licences.csv` — the whole
fourth delivery (1,694 rows, both risk layers) with the licence answer appended
to every record: is there a real alcohol licence at this address, is it in
force, which one, and whose.

**The matching rule itself is `packages/licmatch`** — a standalone package that
knows nothing about this study: toponym parsing, the three-term score, the two
floors, the two routes, selection and the distinct-key tallies. Its methodology
write-up is `packages/licmatch/docs/METHODOLOGY.md` (in Russian) and its tests
run with `pixi run licmatch-test`. What stays in `src/arkhinfra/v4_egais.py` is
this study's half: the two adapters, the licence columns, the evidence tiers and
the summary tables. The runner is `scripts/match_egais_v4.py`.

The split changed no number: the three files the runner writes are byte-identical
to the ones it wrote before. Nothing here changes `v4_common.py`, `egais.py` or
any rendered report — `v4_common.corroboration()` still answers the aggregate
question (what share of the layer sits near *some* licensed outlet) and stops at
a nearest-neighbour distance.

The sections below describe the join as it is *used* here; for why each number
is what it is, and for what may not be claimed on this result, read the
methodology document.

## Which licence an object holds (revision of 2026-09-23)

A review of the first result found the same licence against many objects and
almost every name score low. Three different things were behind it:

1. **A licence number is the organisation's, not the shop's.** Тандер holds one
   number for over a hundred Arkhangelsk outlets. So one number against many
   objects is right, and "the same licence" has to mean the same **outlet**: the
   holder's INN at one parsed address (`outlet_units()`).
2. **Several objects at one address took the same outlet.** Each object chose
   its best licence independently, so a Бристоль, a beer bar and two cafés in one
   building all quoted the one licence filed there. Before the revision, 158 alcohol
   outlets were quoted by 2–5 rows each (383 rows in all). The tobacco layer
   had 161 such outlets.
3. **The registry names the holder, the export the fascia.** ООО «Ритейл» is
   «Союз» on the street; only nine national chains were mapped by hand.

The join now applies these rules on top of the score. Admission (both floors) is
unchanged, and so is the per-address tally:

* **One outlet, one shop** (`licmatch.select(units=…, entities=…)`). An outlet
  goes to the strongest claim, and the next claim takes what is left. The rule
  is greedy rather than an optimal assignment, so every decision can be checked
  by eye. A **shop** is not a record. The two risk files carry one store twice,
  and the tobacco file often twice over («Пятёрочка» and «Пятёрочка,
  супермаркет» at one coordinate). Records within 50 m that name the same brand
  are one entity (`entities()`) and share the outlet: 1,694 records reduce to
  1,197 entities. Different shops compete across both files, so a tobacco kiosk
  loses the outlet to the supermarket it stands in even when the supermarket is
  only in the alcohol file. A shop that lost its outlet is `Taken`;
  `licence_claimed_by` names the winner and `licence_claim_margin` says by how
  much. 15 of 98 were lost by under 0.02, which is close to a coin toss.
* **The licence must permit the trade** (`trade_eligible()`). An off-trade object
  needs a retail licence, an on-trade one a catering licence («Розничная
  продажа, общепит»); hookah lounges count as on-trade. Before the revision, 89 bars and
  cafés quoted a shop's licence, and 4 shops a wholesale or production one. The
  rule gives way where the name says the holder *is* the shop (an alias, or a
  string score ≥ 0.80: «Луда» / ООО «Луда-Старт»). The contractor's inferred type
  is not trusted against that. `licence_trade_match = no` marks the 4 rows this
  frees. An object whose address holds only the other kind is `Other trade`.
* **The known brands rule pairs out, in both directions** (`brand_conflict()`).
  - A known chain holds only its own holders' licences: a Пятёрочка is never
    licensed by ООО «Южанка». A franchise is exempt, since not all its
    operators are known.
  - A known chain's licence goes only to that chain, or to an object whose name
    matches the holder's outright: a «Пивная лавка» next door does not hold
    Агроторг's licence.

  An object left with only such licences is `Other chain`. 50 of the 114 alcohol
  rows with this status are marked closed on Yandex Maps.
* **An archived licence is the object's own only if the name agrees.** This
  applies where an in-force licence of its trade stands at the address. The
  name agrees through an alias, a string score ≥ 0.60, or a known holder of the
  fascia. Otherwise the archived licence is the premises' previous tenant. The
  first run of this revision quoted 36 chain objects with an unrelated company's
  old licence (Пятёрочка → ВинТорг, 2014).

Fascia → holder pairs are **learned from the data** (`learn_brands()`, rule in
`licmatch.brands`, table in `data/processed/v4_licences/v4_brand_aliases.csv`). The alcohol
layer is scored on the address and distance terms only. The outlets are then handed out
one object each, and every fascia's assignments are fed back as a prior on the
next round. That prior never counts the fascia's own address. A pair is kept when
the holder took ≥ 3 of the fascia's addresses, ≥ 30 % of them (≥ 10 % for a fascia no holder
dominates — a franchise), and stands there ≥ 3× more often than at addresses in
general. A pair admitted on the franchise share must also pass a test from
the holder's side: at least half of the holder's outlets stand at the fascia's
addresses. The franchise rule was introduced for Петровский, and this test is
what keeps it from admitting a neighbour (Кедр / Фасоль: 2 of 20). The run keeps
**19 pairs over 12 fascias**:

* the national chains again, found without being told;
* **Союз → Ритейл**, **Афанасий → Кедр**, **Алко Shop → Долина Алко / Долина**
  (three spellings of one fascia, folded by `FASCIA_SPELLINGS`), **Макси → Макси**,
  **Дисма → Конус**;
* the second Красное&Белое operator **Авангард**;
* **five operators of the Петровский franchise** (СЦ Розничные продажи, Селект-Б,
  Солнышко, Встреча, Морион).

A learned pair scores the name term 1.0, with two guards against it confirming
itself:

* A pair that passes only with every one of its voting addresses
  (`loo_accepted = False`: the five pairs at exactly 3 addresses) does not score
  the name term at those addresses.
* A pair resting only on archived licences (`active_sites = 0`: Дисма → Конус,
  both Долина pairs — every outlet expired by 2016) names a history and bars
  nobody (`feeds_conflict = False`).

Each pair is a hypothesis with a count behind it. `BRAND_REVIEW` in `v4_egais.py` is where a
person overrules one; it is empty as of this run. Why clustering objects in
"holder space" does not find these pairs — an object's vector describes its
neighbours, not its brand — is §12 of the methodology.

A generic fascia («Продукты», or «Кафе», which reduces to nothing) has its name
term dropped, with its weight handed to the other two terms, rather than scored as
a 0. Its `licence_name_score` is empty and `licence_name_basis = generic`.

`--no-learn`, `--no-exclusive` and `--no-brand-rule` switch the rules off one at a
time.

## The score

For every (v4 object, licence) pair,

```
score = 0.50 * address_score + 0.20 * name_score + 0.30 * distance_score
distance_score = 1 - d / 100 m,   candidates cut at d <= 100 m
```

Weights are `--weights W_ADDR W_NAME W_DIST`, the radius `--max-m`.

Why the address carries half the weight and the name a fifth: the registry
licenses **an address**, and it names the licence **holder**, not the shop. The
biggest holders in the city are `АО "Тандер"`, `ООО "Агроторг"`,
`ООО "Альбион-2002"`, `ООО "Альфа-М"` — Магнит, Пятёрочка, Бристоль and
Красное&Белое on the street. No fuzzy metric bridges that, so the nine
unambiguous operator→fascia pairs are mapped explicitly in `BRAND_ALIASES`, a
further set is learned from the data (see above), and everything else scores
on the plain string comparison. The name is a tie-breaker
between licences at one address, never the evidence that the address is right.

### The address term compares toponyms, not strings

The two sources write the same address in incompatible orders, abbreviations and
inflections:

| v4 export | registry |
| --- | --- |
| `Архангельск, набережная Северной Двины, 55` | `Северной Двины Набережная, 55` |
| `Архангельск, улица Тимме, 2 к5` | `Тимме Я. Улица, 2, 5` |
| `Архангельск, Ленинградский проспект, 356 к4` | `Ленинградский пр-кт, 356, 4` |
| `Лесная речка, Лахтинское шоссе, 17` | `Лахтинское ш, 17` + `Лесная речка` |

Edit distance over those strings is noise. Each side is parsed into a `Toponym`
— settlement, street type, street name, house, block — and the fields are
compared one at a time:

* **street type** (`ул` / `пр` / `наб` / `ш` / …) is folded onto one key from
  either position, spelt out or abbreviated. A conflict between two written
  types multiplies the street similarity by 0.6.
* **street name** is stripped of the type word and of bare initials
  (`Тимме Я.` → `тимме`), then each token is **light-stemmed** — one
  inflectional ending trimmed, never below four characters — so
  `Северной Двины` meets `Северная Двина` and `Воскресенская` meets
  `Воскресенской` without a morphological analyser. Similarity is
  `0.6 * token_sort_ratio + 0.4 * token_set_ratio`: `token_set` alone scores a
  subset 1.00 (`Победы` inside `40-летия Великой Победы`), `token_sort` alone
  punishes the word order the two sources disagree on.
* **house** is exact: same number and same block → 1.0, same number with the
  block written on one side only → 0.85, same number and conflicting blocks →
  0.6, different numbers → **0.0**. `356 к4`, `45/3`, `13 с1`, `4 к1с3` and the
  registry's own corpus slot all reduce to (number, block).
* **settlement** — a mismatch between two named settlements multiplies the whole
  address score by 0.4; the city itself is not a toponym and is dropped in all
  its spellings (`г Архангельск`, `Архангельск город`,
  `городской округ Архангельск`).

`address = 0.6 * street + 0.4 * house`.

### Two floors, not one

```
score >= 0.45   (--accept)      and     address_score >= 0.72   (--addr-min)
```

The second floor is the one that does the work, and it is an addition to the
formula as commissioned. Inside 100 m the **neighbouring building** is a
candidate too: same street, different house number, `address = 0.60`, and at
30 m with any name resemblance it clears any score floor low enough to keep the
true matches whose coordinates are poor. Distance cannot arbitrate between
neighbours here — the registry's coordinates are converted from
degrees-minutes-seconds, so one arcsecond of rounding is already ~31 m of
latitude — but the house number can. 0.72 is the score of "same street, house
number written on one side only"; an explicit house mismatch scores 0.60 and is
refused. `--addr-min 0` gives the unguarded weighted sum.

`licence_match_level` says which of the two admitted a row: `house` (both sides
name the same building) or `street` (one side writes no house number — weaker,
52 of the 870 licences objects hold).

### The address-only route

Only 53 % of registry rows carry a plausible coordinate, so the 100 m rule alone
can never reach the rest. Those rows are matched on toponyms alone
(`licence_match_method = address`), under a deliberately stricter bar —
street ≥ 0.90 **and** house ≥ 0.85 — with the distance term dropped rather than
scored as a zero. The coverage gap is concentrated in the archive: 98 % of
*active retail* licences do have coordinates.

## The output

`data/processed/v4_licences/v4_licences.csv` — semicolon-delimited, UTF-8 with BOM, like
every other CSV in this project. All 22 delivery columns and the `v4_common`
derived ones, then:

| column | meaning |
| --- | --- |
| `licence_status` | the licence **this object** holds. **`Active`** / **`Archived`** — its own licence, in force / not; **`Taken`** — a licence of its trade is at the address, but that outlet went to another object; **`Other chain`** — only another known chain's licences of its trade; **`Other trade`** — only licences of the other trade; **`Not in registry`** — no licence at the address at all |
| `licence_claimed_by` | for `Taken`: the object that holds the outlet, name and address |
| `licence_name_basis` | where the name term came from: `manual` (the hand-kept chain table), `learned` (a pair from `v4_brand_aliases.csv`), `fuzzy` (the two names compared as strings), `generic` (not scored) |
| `licence_evidence` | what the licence is evidence **of**: `direct` (alcohol rows), `probable` / `weak` (tobacco rows) — see below |
| `licence_evidence_note` | the same in one Russian sentence, so the file cannot be read without it |
| `licence_n_active_retail` | of `licence_n_active`, how many are **retail** classes — the count the tobacco inference rests on |
| `licence_match_method` | `geo` (100 m route) or `address` (toponyms only) |
| `licence_match_level` | `house` or `street`, see above |
| `licence_score`, `licence_addr_score`, `licence_name_score`, `licence_distance_m` | the score and its three parts, for the chosen licence |
| `licence_n_matched`, `licence_n_active` | **distinct licence numbers** at this address (a prolonged licence appears once per status change, so 20 registry rows can be 9 licences) |
| `licence_all_nos`, `licence_active_nos` | those numbers, `; `-separated |
| `licence_no`, `licence_prev_no`, `licence_status_raw`, `licence_status_registry`, `licence_status_reason`, `licence_date_issued`, `licence_date_expires`, `licence_status_changed`, `licence_activity`, `licence_activity_class`, `licence_products`, `licence_org_name`, `licence_org_inn`, `licence_outlet_address`, `licence_issuing_body` | the chosen licence itself |

The **chosen** licence is the best-scoring *active* one among those the object
may hold — eligible for its trade, not another chain's, its outlet not taken by
a stronger claim — and the best-scoring one otherwise. `licence_n_*` and
`licence_all_nos` still count **every** licence admitted at the address, so they
describe the building, while `licence_status` and the licence columns describe
the object. `licence_status` is a text value on purpose: the bare string `None`
is read back as `NaN` by pandas.

`data/processed/v4_licences/v4_licences_summary.txt` carries the same run's tables (Cyrillic
is written to a UTF-8 file rather than to the Windows console). `--calibrate`
appends the threshold ladder and ten sampled matches per score band.

## What the run says

Two headlines, which answer different questions:

* **A licence at the address**: 1,366 of 1,694 v4 records (80.6 %). This is
  unchanged by the 2026-09-23 revision, because admission is unchanged.
* **A licence of its own**: 870 (51.4 %) — 640 in force, 230 archived. Of the
  rest, 98 are `Taken`, 279 `Other chain`, 119 `Other trade` and 328
  `Not in registry`.

| | Active | Archived | Taken | Other chain | Other trade | Not in registry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Alcohol, before | 616 | 150 | — | — | — | 179 |
| Alcohol, now | 350 | 155 | 64 | 114 | 83 | 179 |
| Tobacco, before | 504 | 96 | — | — | — | 149 |
| Tobacco, now | 290 | 75 | 34 | 165 | 36 | 149 |

An outlet is now held by more than one row only where those rows are records of
one shop: 3 alcohol outlets and 57 tobacco ones, two records each. Before, 158
alcohol outlets were quoted by 2–5 rows of different shops. The fall in `Active` is
mostly shops that had been quoting a neighbour's licence: a chain's (now
`Other chain`) or another independent's (now `Taken`). Split by what the match is
evidence of: 505 of the 945 alcohol rows are `direct`, and 290 of the 749 tobacco
rows are `probable`.

Among the licences objects now hold, the name term is `manual` for 336, `learned`
for 119, `generic` (not scored) for 60, and a plain string comparison for 355.
The comparison has barely improved where it is still a comparison: 271 of those
355 are below 0.5, against 292 on the same rows in the old join. What changed is that
455 licences are now matched by a known pair rather than by a string, and 60 are
no longer scored at all. The low scores that remain are single shops whose legal
name shares nothing with the fascia, which no directory resolves. For them the
address decides, as it always did.

The reverse direction is the stronger result: **97.7 % of the 442 active
off-trade retail licences** and 88.1 % of the 135 active on-trade ones have a v4
object at their address. Counting only outlets actually **held** by an object
(`Held` in `reverse_coverage()`), the share for off-trade is 71.9 %. The gap is
buildings where the licensed shop and the tagged object are not the same unit.
The fourth delivery does account for licensed alcohol retail in the city, which
is what the fivefold undercount in `reports/egais/eda-egais.pdf` said the third
delivery did not.

## The tobacco layer: probable corroboration, not corroboration

The registry has no tobacco class — the regulator covers tobacco, the published
data does not. The tobacco layer is therefore matched against **the same alcohol
licences, by the same scorer**, and the result is labelled for what it actually
is:

| `licence_evidence` | when | what it claims |
| --- | --- | --- |
| `direct` | alcohol row, any match | the registry licenses the very product the row is tagged with |
| `probable` | tobacco row, a **retail** alcohol licence in force at the address | the outlet legally sells alcohol, and Russian retail sells alcohol and tobacco across the same counter — so the tobacco tag is *likely* |
| `weak` | tobacco row, only an archived or non-retail licence | matched, but the co-sale argument does not apply |
| *(empty)* | no licence at the address | — |

The inference is one-directional and unquantified. Nothing in this repository
can measure how often alcohol and tobacco actually travel together in one outlet
— the 2022 benchmark holds 46 tobacco objects in three okrugs, and there is no
tobacco register to check against (retail tobacco licensing in Russia only opens
2026-10-01 and becomes mandatory 2027-03-01). So the column **states** the
strength of the link and never scores it: `probable` is a flag, not a
probability, and it must not be reported as a tobacco verification rate.

Run of 2026-09-23: of 749 tobacco records, **290 (38.7 %) are `probable`**, 75
`weak`, 384 hold no licence of their own. The 2026-09-07 run said 503. The
difference sits where the old figure looked strongest: **80 of the 100
specialised tobacco shops were `probable`, now 4.** Every one of them was quoting
the alcohol licence of the supermarket or liquor chain it stands in or beside
(Бристоль, Красное&Белое, Пятёрочка). The one-shop rule gives that outlet to the
supermarket, and the brand rule keeps a chain's licence with the chain. A
specialised tobacco shop selling alcohol over its own counter was never the
likely reading. The 4 that remain (Пармаркет ×3, Архидымный) hold a
non-chain licence at their own address and should be checked by hand. Vape shops:
1 of 20 (was 16); hookah lounges, now matched against catering licences: 1 of 10.

`pixi run python scripts/match_egais_v4.py --layer tobacco` writes the tobacco
layer alone to `data/processed/v4_licences/v4_tobacco_licences.csv`; `--layer alcohol` does
the same for the other. Both layers are always scored — the flag selects a view
of one result, not a different one.

## Three things the join cannot do

* **A `probable` tobacco row is an alcohol fact.** See above; the two evidence
  kinds count different claims and must never be summed into one "corroborated"
  headline.
* **An assigned outlet is a best reading, not an identification.** One outlet
  now goes to one object, but between two unknown fascias in one building the
  stronger claim is decided by distance and string noise. `Taken` says "a
  licence of your trade is here and someone else has the better claim to it",
  never "you have no licence". The per-address columns (`licence_n_*`,
  `licence_all_nos`) keep the whole set for review.
* **`Not in registry` is not "sells no alcohol".** It is the union of "the
  object genuinely holds no licence" (most of the on-trade inferred tier),
  "the licence is filed under an address neither route could reach", and the
  export's own address errors. The same applies to all four "no own licence"
  statuses.

## The deliverable spreadsheets

`pixi run export-licences` (`src/arkhinfra/v4_export.py`) turns the working CSV
into four XLSX files in `data/processed/deliverables/`, for a reader who has to check the
join rather than query it:

| File | Rows | What it holds |
| --- | ---: | --- |
| `v4_licences_alcohol_matched.xlsx` | 505 | alcohol objects holding a licence of their own |
| `v4_licences_tobacco_matched.xlsx` | 365 | the tobacco layer against the same alcohol licences |
| `v4_alcohol_no_licence.xlsx` | 440 | alcohol rows with no licence of their own (Taken / Other chain / Other trade / Not in registry), plus the Yandex check and the refused candidate |
| `v4_brand_aliases.xlsx` | 328 | every candidate fascia → holder pair with its evidence; the 19 in use first; the review column is where a person confirms or rejects one |

The column plan pairs the two sides of every comparison — object name beside
licence holder, object address beside outlet address, object coordinate beside
the registry's — and puts the term each pair scored immediately after it, then
the total. Every file carries a «Как читать» sheet naming each column and
restating what the result may not be read as.

The no-licence file's distinguishing column is **«Почему не принята»**. For the
179 `Not in registry` rows it names the floor the best-scoring candidate failed,
which turns "no licence at this address" from a verdict into a reviewable
statement:

* 78 had no candidate in range at all;
* 52 failed only the address floor, meaning a licence stands nearby under a
  house number that does not agree;
* 48 failed both floors, and 1 the score floor alone.

For the other 261 it says the floors were not the reason and names the rule
that was: the outlet went to another shop (64), the licences are another
chain's (114), or of another trade (83).

The script re-runs the join and **refuses to write if the re-run disagrees**
with `v4_licences.csv` on `licence_status` or `licence_no`. The re-run exists
only to reach the registry's own coordinate and the losing candidate, neither
of which the working file keeps; the guard is what keeps these files and the
rendered report the same numbers.
