# Fourth delivery x FSRAR licence registry: the object-level join

`pixi run match-egais-v4` writes `data/processed/v4_licences.csv` — the whole
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
unambiguous operator→fascia pairs are mapped explicitly in `BRAND_ALIASES` and
everything else simply scores low on the name term. The name is a tie-breaker
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
124 of 1,366 matches).

### The address-only route

Only 53 % of registry rows carry a plausible coordinate, so the 100 m rule alone
can never reach the rest. Those rows are matched on toponyms alone
(`licence_match_method = address`), under a deliberately stricter bar —
street ≥ 0.90 **and** house ≥ 0.85 — with the distance term dropped rather than
scored as a zero. The coverage gap is concentrated in the archive: 98 % of
*active retail* licences do have coordinates.

## The output

`data/processed/v4_licences.csv` — semicolon-delimited, UTF-8 with BOM, like
every other CSV in this project. All 22 delivery columns and the `v4_common`
derived ones, then:

| column | meaning |
| --- | --- |
| `licence_status` | **`Active`** — a licence in force at this address; **`Archived`** — only expired / terminated / annulled / reissued ones; **`Not in registry`** — no licence matched |
| `licence_evidence` | what the licence is evidence **of**: `direct` (alcohol rows), `probable` / `weak` (tobacco rows) — see below |
| `licence_evidence_note` | the same in one Russian sentence, so the file cannot be read without it |
| `licence_n_active_retail` | of `licence_n_active`, how many are **retail** classes — the count the tobacco inference rests on |
| `licence_match_method` | `geo` (100 m route) or `address` (toponyms only) |
| `licence_match_level` | `house` or `street`, see above |
| `licence_score`, `licence_addr_score`, `licence_name_score`, `licence_distance_m` | the score and its three parts, for the chosen licence |
| `licence_n_matched`, `licence_n_active` | **distinct licence numbers** at this address (a prolonged licence appears once per status change, so 20 registry rows can be 9 licences) |
| `licence_all_nos`, `licence_active_nos` | those numbers, `; `-separated |
| `licence_no`, `licence_prev_no`, `licence_status_raw`, `licence_status_registry`, `licence_status_reason`, `licence_date_issued`, `licence_date_expires`, `licence_status_changed`, `licence_activity`, `licence_activity_class`, `licence_products`, `licence_org_name`, `licence_org_inn`, `licence_outlet_address`, `licence_issuing_body` | the chosen licence itself |

The **chosen** licence is the best-scoring *active* one wherever any is active,
and the best-scoring one otherwise — so `licence_status` never reads `Archived`
while an in-force licence sits at the same address. `licence_status` is a text
value on purpose: the bare string `None` is read back as `NaN` by pandas.

`data/processed/v4_licences_summary.txt` carries the same run's tables (Cyrillic
is written to a UTF-8 file rather than to the Windows console). `--calibrate`
appends the threshold ladder and ten sampled matches per score band.

## What the run says

At the defaults, **1,366 of 1,694 v4 records (80.6 %)** match at least one
licence; 1,120 have one in force, 246 only an archived one, 328 none. Split by
what the match is evidence of: 766 of the 945 alcohol rows are `direct`, and 503
of the 749 tobacco rows are `probable` — a different claim, counted separately
(see below).

The reverse direction is the stronger result: **97.7 % of the 442 active
off-trade retail licences** and 88.1 % of the 135 active on-trade ones have a v4
object at their address. The fourth delivery does account for licensed alcohol
retail in the city, which is what the fivefold undercount in
`reports/egais/eda-egais.pdf` said the third delivery did not.

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

Run of 2026-09-07: of 749 tobacco records, **503 (67.2 %) are `probable`**, 97
`weak`, 149 have no licence at their address. By object type the split is sharp —
80 of the 100 specialised tobacco shops are `probable`, but only 2 of 10 hookah
lounges and 16 of 20 vape shops.

`pixi run python scripts/match_egais_v4.py --layer tobacco` writes the tobacco
layer alone to `data/processed/v4_tobacco_licences.csv`; `--layer alcohol` does
the same for the other. Both layers are always scored — the flag selects a view
of one result, not a different one.

## Three things the join cannot do

* **A `probable` tobacco row is an alcohol fact.** See above; the two evidence
  kinds count different claims and must never be summed into one "corroborated"
  headline.
* **A licence is not a shop.** The registry is a register: an `Active` row means
  someone holds a licence at that address, not that this particular object is
  the licence holder. Where several licences sit in one building — a mall, a
  ground floor of five units — every object in it gets the same set.
* **`Not in registry` is not "sells no alcohol".** It is the union of "the
  object genuinely holds no licence" (most of the on-trade inferred tier),
  "the licence is filed under an address neither route could reach", and the
  export's own address errors.
