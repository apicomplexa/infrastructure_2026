# Fourth delivery: the risk-layer extracts (`data/raw_v4/`)

Two CSVs, received **2026-09-03** (tobacco) and **2026-09-04** (alcohol), each
carrying the column schema of the third delivery.

| file | rows | columns |
| --- | ---: | ---: |
| `infrastructure_архангельск_2026-09-03_quality_excel табачное изделие.csv` | 749 | 22 |
| `infrastructure_архангельск_2026-09-04_quality_excel алкоголь.csv` | 945 | 22 |

Read either exactly like the main CSV — semicolon-delimited, UTF-8 with BOM:

```python
pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)
```

or, preferably, through `arkhinfra.v4_common.load_v4_tobacco()` /
`load_v4_alcohol()` / `load_v4()`, which add the derived columns everything
below is phrased in.

## What this actually is

**Not a fourth survey — a risk-attribution layer over the third.** The
contractor did not go and find new objects. They took the same 7,263-object
pool that `data/raw_v3/…quality_excel.csv` already contains and re-tagged the
subset that plausibly sells alcohol or tobacco:

- **100 %** of the 749 tobacco rows and **99.8 %** of the 945 alcohol rows sit
  within 100 m of an object already in the v3 export; 86 % sit on a *byte-identical*
  coordinate pair.
- **94 %** of the tobacco file's `matched_source_ids` and **98 %** of the
  alcohol file's are ids that already appear in v3.

So the delivery adds no geographic coverage. What it adds is a **judgement**,
and that judgement is the reason to care about it: v3 recognised 110 alcohol
shops and 60 tobacco outlets city-wide, and the v3 report's own conclusion was
that this undercounted alcohol retail roughly fivefold. This delivery is the
contractor's answer to that.

The two files overlap. 359 coordinates carry both an alcohol and a tobacco row,
so the combined layer is **1,335 distinct sites**, not 1,694 — 18.4 % of the
v3 object pool. Dedupe on the coordinate before counting.

## Is it the same schema? Yes as a container, no as a vocabulary

The 22 column names, their order, and their pandas dtypes are **identical** to
`data/raw_v3/…quality_excel.csv`. Anything reading v3 positionally or by name
will read these files without modification. That part of the contractor's
promise holds.

What changed is what the columns *say*. `category_orig` and `type_orig` carry a
**fourth taxonomy**, sharing no value with the first three deliveries:

| `category_orig` | file | rows |
| --- | --- | ---: |
| Табачная и никотинсодержащая продукция | tobacco | 749 |
| Алкогольная продукция | alcohol | 945 |

| `type_orig` | file | rows | tier |
| --- | --- | ---: | --- |
| Возможная продажа табачной продукции | tobacco | 619 | inferred |
| Специализированная продажа табачной продукции | tobacco | 100 | direct |
| Вейпы и никотинсодержащая продукция | tobacco | 20 | direct |
| Кальянные | tobacco | 10 | direct |
| Возможная продажа алкоголя в магазинах | alcohol | 471 | inferred, off-trade |
| Возможная подача алкоголя в общепите | alcohol | 295 | inferred, on-trade |
| Специализированная продажа алкоголя | alcohol | 167 | direct, off-trade |
| Подача алкоголя в барах и пабах | alcohol | 12 | direct, on-trade |

### The "возможная" tier is most of the file, and it is an inference

**82.6 %** of the tobacco file and **81.1 %** of the alcohol file are
`Возможная …` rows. The contractor's own `verification_comment` says what that
means:

> тип объекта подходит, но наличие табачной или никотинсодержащей продукции
> **требует отдельной проверки**

These are not observed sales. They are "this is a grocery shop, groceries sell
beer and cigarettes". The remaining rows say
`Источник содержит прямой признак …` — the source record itself named the
product. Treat the two tiers separately in every count;
`v4_common` exposes them as `evidence ∈ {Direct, Inferred}`.

The inference is mostly drawn over shops and catering. Matching each v4 record
to its nearest v3 object within 50 m, here is what v3 had called it:

| v3 class | tobacco rows | alcohol rows |
| --- | ---: | ---: |
| Grocery shops | 556 | 372 |
| Catering | 22 | 387 |
| Tobacco outlets / Alcohol shops | 61 | 111 |
| Other | 88 | 57 |
| Medical | 13 | 14 |

The 13/14 medical hits are pharmacies picked up by the type rule; they are
false positives for both risk factors and should be dropped before any risk
index is built.

## `recode_2022()` silently drops 93 % of the tobacco file

`v3_common.recode_2022()` tests the category/type/name blob for the substring
**`табак`**. Every label in the fourth delivery spells the stem **`табач-`**
(`Табачная`, `табачной`), which does not contain `табак`. The tobacco rule
therefore never fires on this vocabulary, and **698 of 749 rows land in
`Other (outside 2022 scheme)`** — only the 50 rows saying `вейп` or `кальян`
survive.

This is the same class of defect as the `GROCERY_TYPES` case-mismatch already
recorded in `CLAUDE.md`, and it is silent in exactly the same way.

The fix is one stem, and it lives in **`v4_common.recode_2022_v4()`**, kept out
of `v3_common` deliberately so the three already-rendered v3 reports keep
producing the numbers they were signed off on. The alcohol file is unaffected —
`алкогол` matches its labels — and recodes 945/945 correctly.

## Column-level notes

- **`district_orig` is good.** All nine okrugs are present and separate, with
  no Isakogorsky/Tsiglomensky merge and no 71 %-in-one-okrug skew. This is the
  v3 fix carried forward.
- **`opening_hours_orig` holds two incompatible encodings in one column.**
  2GIS-sourced rows carry a JSON object keyed by weekday
  (`{"Mon": {"working_hours": [...]}, "is_24x7": true}`); OSM-sourced rows carry
  an OSM `opening_hours` string (`Mo-Su 08:00-22:00`). The split is 42 % JSON in
  the tobacco file but only 2 % in the alcohol file. Parse with
  `v4_common.parse_hours()`, which reports which encoding it found. This trap
  exists in v3 too (10.7 % JSON), just less visibly.
- **`website_check_status` is empty for all 1,694 rows** — the same dead column
  as in v3.
- **`opening_date_orig`** is populated for 22 rows (1.3 %), so opening-date work
  remains impossible.
- **`match_distance_meters` / `match_name_similarity` are still a dedup key,
  not verification** — 82 % / 89 % of non-null values sit at exactly 0 m and
  exactly 1.00. They are also **null for 18.3 % (tobacco) and 10.1 % (alcohol)**
  of rows, up from 6.6 % in v3.
- **No duplicate rows** and no repeats on (name, lat, lon) within either file.

### Provider mix diverges sharply between the two files

| | v3 (all) | v4 tobacco | v4 alcohol |
| --- | ---: | ---: | ---: |
| OSM only | 89.5 % | 54.9 % | **97.6 %** |
| 2GIS only | 8.1 % | 37.7 % | 1.9 % |
| Confirmed by both | 2.4 % | 7.5 % | 0.5 % |

The tobacco layer is substantially 2GIS-backed and is the best-corroborated
file the project has received. The alcohol layer is **worse than v3** — 97.6 %
of it rests on OSM alone, and only five records are confirmed by both
providers. Any claim that the alcohol layer is "verified" is not supported by
its own `verification_status` column.

## How it compares to the two benchmarks

Both comparisons are worked through in `reports/v4/eda-v4.pdf`; the headline is
that the delivery does well against the licence registry and adds nothing
against the 2022 list.

**Against the FSRAR licence registry — the fivefold alcohol gap closes.**

| | count |
| --- | ---: |
| v3 `Alcohol shops` | 110 |
| v4 alcohol, off-trade | **638** |
| EGAIS active off-trade licences | 442 |
| EGAIS active off-trade distinct outlets | 379 |
| v4 alcohol, on-trade | 307 |
| EGAIS active on-trade licences | 135 |

Per okrug the licence-to-export ratio was 2.9–12.0 against v3 (worst in the
outlying okrugs, which is what biased okrug risk comparisons toward the centre)
and is **0.57–0.92 against v4**. Spatial corroboration moves the same way:
the share of active licensed outlets with a matching object within 50 m rises
from **18.9 %** (v3 `Alcohol shops`) to **73.6 %** (v4 off-trade), and to
90.8 % at 100 m. The okrug-level bias the EGAIS report identified is substantially
repaired.

**Against the 2022 benchmark — no improvement.** Recall of the 2022 risk
objects in the three okrugs it covers is essentially unchanged:

| 2022 class | n | v3 export | v4 layer |
| --- | ---: | ---: | ---: |
| Alcohol shops | 116 | 49.1 % | 50.0 % |
| Tobacco outlets | 46 | 34.8 % | 32.6 % |

Most of the shortfall is name churn rather than absence: 83 % of 2022 alcohol
sites and 74 % of tobacco sites have *some* v4 risk object within 50 m, under a
different name. Four years is long enough for a small alcohol shop to rebrand,
so this is expected — but it does mean the fourth delivery cannot be presented
as improving agreement with 2022.

Conversely, **92 % of the v4 alcohol rows and 97 % of the tobacco rows in those
three okrugs have no 2022 counterpart at all.** They are mostly the inferred
tier, which the 2022 study never attempted to enumerate.

## How to use it

- Report the **direct** and **inferred** tiers separately. A single headline
  count mixing them is not defensible.
- For alcohol availability, use **off-trade** and compare against active EGAIS
  off-trade licences. Do not compare a total that includes catering against a
  shop count.
- Drop the pharmacy false positives (`category_2022 == "Medical"` on the
  nearest v3 object) before building any risk index.
- **Tobacco has no independent benchmark.** The licence registry holds alcohol
  only, and the 2022 tobacco list is 46 objects in three okrugs. The 749-row
  tobacco layer rests on the contractor's inference and 2GIS category labels,
  and nothing in this repository can check it.
- Five okrugs still have no benchmark of any kind, as before.
