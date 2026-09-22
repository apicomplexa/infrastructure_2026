# Design: a calibrated 7-class membership model over the 2022 taxonomy — modelling half

Scope: label construction, features, leakage control, model candidates, calibration,
the v4-layer question, artefacts. Evaluation protocol and reporting are the other half
of the document; this half names the splitter and the metrics it hands over.

Everything marked **[verified]** was checked in this session against the repository.
Everything marked **[estimate]** is a judgement call with its basis stated.

---

## 0. Three facts that shape the whole design

**0.1 `data/raw_v4/…_all.csv` and `V3_CSV` are the same file.** [verified]
Both are 7,263 rows and their MD5 is identical
(`949c075672028e13f212c9aa4c57d5c6`). So "the modern export" is one object table, and
`data/processed/match_2022_local.csv` — produced by `pixi run match-2022` against
`V3_CSV` — **already is the benchmark-to-export join this model needs.** No new matcher.
`arkhinfra.paths` should gain `V4_ALL` as an alias pointing at the `raw_v4` copy with a
comment recording the identity, and everything else should keep using `V3_CSV`.

**0.2 There are five files in `data/raw_v4/`, not two.** [verified]
`v4_common.load_v4()` knows only tobacco and alcohol. The two 2026-09-05 layers exist:

| layer | rows | `category_orig` | coords also in `_all.csv` |
|---|---|---|---|
| tobacco | 749 | Табачная и никотинсодержащая продукция | 86.1 % |
| alcohol | 945 | Алкогольная продукция | 85.5 % |
| catering (`…общепит.csv`) | 566 | Общественное питание | 95.6 % |
| grocery (`…продуктовые магазины.csv`) | 1,711 | Продуктовые магазины | **57.6 %** |

The grocery layer is the odd one: 725 of its 1,711 coordinates are **not** in `_all.csv`,
concentrated in `Стационарные рынки и ярмарки` (406) and `Торговые центры` (230). It is
not purely a re-tagging layer. Union of the four layers: 2,611 distinct coordinates, of
which 1,747 land on an `_all.csv` object — **24 % of the city export carries any
contractor risk/trade tag at all.**

**0.3 The 2022 `category_orig` is list membership, not a mutually exclusive class.**
[verified] The two anomalous rows are the proof: `Красное & Белое, Воскресенская 104`
and `Гудвайнс Гудтаймс, наб. Северной Двины 71` carry
`category_orig = Точки продажи табака` with `type_orig = Магазин алкоголя`. A 2022
surveyor recorded *which survey list the object was found on*; `type_orig` records *what
the object is*. That reading is what makes the client's "7 binary targets, not a softmax"
decision correct on the data's own terms, and it decides how the anomalies are handled
(§1.6).

---

## 1. Label construction

### 1.1 The training unit is an export row, not a benchmark row

Features live on the export side. 1,133 usable benchmark rows collapse onto **1,072
distinct export rows** (61 collisions) [verified], because the 2022 list frequently holds
two rows — e.g. `Магнит` and `Магнит Аптека` at one address — that the 2026 export carries
as one object. Keeping the benchmark row as the unit would duplicate identical feature
vectors with conflicting labels. So:

```
training row  := one row of _all.csv (indexed by its 0-based position, `export_row_id`)
y[k]          := 1 if any benchmark row matched onto it carries category_orig == k
```

This also produces the only genuine multi-label examples in the data, for free (§1.5).

### 1.2 Which match tiers are usable

`match_2022_local.csv` tiers [verified]:

| tier | n | name_sim (median) | use |
|---|---|---|---|
| `exact` (≥0.90) | 1,083 | 1.00 | **positive labels** |
| `probable` (0.75–0.90) | 50 | 0.855 | **positive labels** |
| `gps_only` | 541 | 0.44 | **mask, never a negative** |
| `unmatched` | 79 | — | dropped; counts against coverage |

`exact` and `probable` are usable because in both the name agrees enough that the export
row is the same business. `probable` is only 50 rows but it is the *only* part of the
training set where the name is not near-identical (§3.1), so it is disproportionately
valuable and must not be discarded for tidiness.

`gps_only` is **not** usable as a positive: median name similarity 0.44 means the object
standing at that coordinate in the export is a different business from the one the 2022
survey recorded. It is also **not** usable as a negative, and this is the part that is
easy to get wrong. A `gps_only` match says "in 2022 there was an object of class *k*
within 50 m of this export row"; the export object may well be its successor under a new
name. Marking it 0 for class *k* injects exactly the false negatives that would teach the
model to suppress the class. Rule:

```
for each gps_only benchmark row with class k and target export row r:
      sample_weight[r, k] := 0        # masked out of the loss for head k only
      y[r, k']  for k' != k           # unaffected, normal negative
```

541 masked (row, class) cells against ~7,500 usable cells in the labelled block — a ~7 %
mask on the negatives of the affected heads, with the mask concentrated in Sport (79
gps_only) and Catering (209).

The 79 `unmatched` rows have no export row and therefore no features. They are dropped
from training and **reported as a coverage limit, not a model error**: 32 of them are
`Спортивные объекты` and 21 `Магазины`. Related [verified]: **78 of the 188 benchmark
sport rows have a null `adress_orig`** (all 78 are `Спортивные объекты` — outdoor
площадки), which is most of why Sport matches worst.

### 1.3 The negative set, and the assumption under it

Negatives are the closed-world assumption: an export row inside the three benchmark
okrugs with no benchmark match is a negative for all seven classes. The assumption is
that the 2022 survey enumerated those okrugs completely. It did not — independent recall
is 64.6 % [verified, `match_2022_summary.txt`], so some of that shortfall is benchmark
incompleteness rather than export novelty. Consequences to state in the report, not to
paper over:

* the negative set carries label noise of unknown but non-trivial size;
* every head's estimated precision is therefore a **lower bound** and its recall an
  upper bound;
* the masking rule in §1.2 removes the one part of that noise we can locate.

**Which export rows are eligible to be negatives at all.** Only rows whose
`okrug_key` is one of `Lomonosovsky`, `Oktyabrsky`, `Maiskaya Gorka` — 5,614 of 7,263.
7 training rows fall in `Varavino-Faktoriya` [verified], boundary spillover; keep them as
positives, but do not admit that okrug's other 433 rows as negatives.

### 1.4 Seven binary targets, and the one that cannot be trained

Positives by class, at `exact`+`probable` [verified]:

| 2022 `category_orig` | benchmark rows | trainable? |
|---|---|---|
| Общепит | 402 | yes |
| Медицинские организации | 321 | yes |
| Магазины | 258 | yes (but see §8.1) |
| Спортивные объекты | 79 | marginal |
| Спецмагазины алкоголя | 57 | marginal |
| Точки продажи табака | 16 | **no** |
| Пром. Объекты | **0** | **no** |

(1,133 labels over 1,072 rows; per-head counts after the collapse are 1–10 lower each,
computed exactly at build time.)

`Пром. Объекты` has **zero** positives at any usable tier — all 10 benchmark rows are
`gps_only` (6) or `unmatched` (4). There is no supervised signal for it whatsoever. The
design must not pretend otherwise:

> **Head 7 (Industrial) is not a model.** It ships as the `v3_common.recode_2022()`
> keyword rule, emitting `{0, 1}` and a `p_industrial = NA`, with
> `industrial_source = "rule"` in the output. The repo already records that this rule is
> dominated by name-substring false positives (25 objects including a hostel and a
> jewellery shop), so the rule's output is flagged `unreliable` and excluded from every
> aggregate.

`Точки продажи табака` at 16 positives is not calibratable (a probability estimated from
16 events has a bootstrap CI roughly ±0.25 at the middle of the range [estimate]). Ship it
as a **rule + evidence channel**: the corrected tobacco stem (`табач`, per
`v4_common.recode_2022_v4()`), plus the v4 tobacco layer flag, plus
`licence_evidence = probable` from the EGAIS join — with `p_tobacco` present but carrying
`calibration = "not estimated"` and a widened interval. The repo already states there is
no independent tobacco benchmark anywhere; the model does not change that.

This leaves **four trained heads with honest probabilities (Catering, Medical, Shops,
Sport), one marginal (Alcohol, 57), and two non-modelled (Tobacco, Industrial)** —
which should be the design document's headline, because it is the thing a client is most
likely to be surprised by later.

### 1.5 Multi-label content of the training data

14 of the 1,072 labelled export rows (1.3 %) carry more than one class; none carries three
[verified]. Inspected, they split into two kinds:

*Artefacts of the collapse* (7 rows): `Магнит` + `Магнит Аптека` at one address →
`Магазины` + `Медицинские организации` on one export row. These are two businesses the
export failed to separate, not one dual-purpose object.

*Genuine co-membership* (7 rows): `ГлавПивБар` (Общепит + Спецмагазины алкоголя),
`Красное & Белое` (Спецмагазины алкоголя + Точки продажи табака), `Мята Lounge`,
`Aura Lounge`, `Come in` (Общепит + Точки продажи табака — hookah lounges),
`Кулинария "Грядка"` (Магазины + Общепит).

Keep both kinds — the artefacts are *correct as labels for that export row*, since the
export row genuinely covers both businesses — but record the distinction in a
`multilabel_kind` column so §5's honesty section can quote the real number: **seven
genuine co-membership examples.** Seven is not a training signal for co-occurrence. It is
just enough to spot-check that the independent heads do not contradict reality on the
handful of cases where reality is known.

### 1.6 `type_orig` vs `category_orig`, and the two anomalies

`category_orig` is the deliverable (the client asked for the 7 classes) and stays the
target. `type_orig` (55 values in the benchmark, 45 present in the training block
[verified]) is used three ways, none of them as the primary target:

1. **As the lookup baseline's target** (§4.1) — it is the level at which the taxonomy is
   actually crisp.
2. **As an auxiliary head** in the classical model: a 45-class multinomial trained on the
   same features, whose out-of-fold predicted distribution becomes 45 extra features for
   the 7 binary heads. This is cheap regularisation that transfers the fine-grained
   structure into the coarse heads — worth trying, ablate it.
3. **As the arbiter of the anomalies.** The two rows labelled `Точки продажи табака` /
   `Магазин алкоголя` get **both** bits set: `tobacco = 1` (the survey's statement that
   this shop was on the tobacco list) **and** `alcohol = 1` (`type_orig`'s statement that
   it is an alcohol shop). That is the most defensible reading given §0.3, it adds two
   real multi-label examples, and it is two rows — the sensitivity is nil. Record the
   decision in the code comment, not only here.

Making `type_orig` the target instead of `category_orig` would be a worse design for this
deliverable: 45 classes over 1,072 rows averages 24 examples per class, with a long tail
in single digits, and the client's requirement is stated at the 7-class level. Recommend
against; keep it as (1)–(3).

### 1.7 Duplicates

* 3 rows are exact duplicates across all columns → drop [verified].
* 1,753 rows → 1,692 distinct (name, address) pairs; 11 pairs carry >1 `category_orig`,
  15 carry >1 `type_orig` [verified]. The §1.1 collapse onto export rows absorbs all of
  this; no separate de-duplication step is needed, and none should be added, because
  de-duplicating the benchmark first would discard exactly the co-membership evidence of
  §1.5.
* 147 benchmark rows repeat a coordinate. Handled by the same collapse.

---

## 2. Feature schema

Naming convention: `f_<group>_<name>`. Availability is over all 7,263 export rows
[verified from `_all.csv`].

### 2.1 Text — 100 % available

| feature | source | note |
|---|---|---|
| `f_txt_name` | `name_orig` | 100 %; normalised with `v3_common.norm_name` for the grouping key but fed **raw-cased-folded** to the vectoriser (the legal-form stripping in `norm_name` removes signal the model can use) |
| `f_txt_category` | `category_orig` | 18 values |
| `f_txt_type` | `type_orig` | 218 values |
| `f_txt_blob` | `category + " | " + type + " | " + name` | the same blob `recode_2022()` reads, so the learned model and the rule see the same string |
| `f_txt_comment` | `verification_comment` | 100 %, but near-constant boilerplate; include only as a few regex flags (`mentions 2gis`, `mentions osm`, `дата открытия не найдена`) |

Encoding: char n-grams, `analyzer="char_wb"`, `ngram_range=(3,5)`, `min_df=2`,
sublinear TF, L2. Char n-grams over word tokens because Russian is inflectional and the
vocabulary is small; `аптек-` / `аптеч-` and `табак` / `табач-` — the exact pair of stems
that has silently broken two rules in this repo — are one n-gram apart under `char_wb`
and unrelated tokens under a word analyser. That is the concrete argument for char
n-grams here, not a generic preference.

**Missing at inference:** cannot be missing; `name_orig`, `category_orig`, `type_orig`
are 100 % populated. An empty name yields an all-zero text block, which the model handles
as "no name evidence" and which is exactly right.

### 2.2 Structured — mixed availability

| feature | availability | at inference when missing |
|---|---|---|
| `f_str_verification_status` | 100 % (only_osm 6,504 / only_2gis 587 / confirmed 172) | n/a |
| `f_str_provider_count` | 100 % (1: 7,091; 2: 172) | n/a |
| `f_str_providers` | 100 %; one-hot of the 3 realised combinations | n/a |
| `f_str_has_website` | 27.2 % populated → **boolean presence, not the value** | presence is the feature; never missing |
| `f_str_has_phone` | 44.0 % → boolean presence | never missing |
| `f_str_hours_encoding` | 75.7 % populated: osm 4,909 / json 590 / none 1,764 | `none` is a valid level |
| `f_str_is_24x7` | via `v4_common.parse_hours`; defined only where hours parse | explicit `NaN` + `f_str_hours_known` indicator |
| `f_str_n_filled_fields` | derived from `filled_fields` / `missing_fields` | never missing |

**Dropped deliberately, with reasons:**
`website_check_status` — empty for every record. `opening_date_orig` — 0.6 %.
`match_distance_meters` / `match_name_similarity` — 93.4 % populated but they are the
contractor's *deduplication* key (99.5 % exactly 0 m, 99.8 % exactly 1.00 similarity per
`CLAUDE.md`); they carry no independent information and they sit uncomfortably close to
the join that produced the labels (§3.4). `city_orig` — constant.

### 2.3 Spatial

| feature | availability | note |
|---|---|---|
| `f_geo_okrug` | 100 %, 9 levels | one-hot. **Six levels never appear as a training negative** (§1.3) — this is the extrapolation boundary and must be an explicit ablation, not a silent one |
| `f_geo_lat`, `f_geo_lon` | 100 % | **not used as raw features.** Raw coordinates in a tree model over 1,072 points in three contiguous okrugs are a memorisation channel for the okrug boundary and nothing else |
| `f_nbr_count_{100,250,500}m` | 100 % | number of export objects within r, log1p |
| `f_nbr_share_cat{c}_{250,500}m` | 100 % | share of neighbours within r whose `category_orig` is *c*, for the 18 categories → 36 features. This is the "neighbourhood composition" signal: a unit inside a shopping centre sits among 30 `Магазины` neighbours |
| `f_nbr_dist_nearest_cat{c}` | 100 % | log distance to the nearest object of each of 18 categories, capped at 1 km |
| `f_nbr_same_address_n` | 100 % | rows sharing `norm_address` — the mall/market indicator |

All neighbourhood features are computed over the **whole 7,263-row export**, not over the
training block, so they have identical meaning in the three benchmark okrugs and the six
extrapolation okrugs. Use a `scipy.spatial.cKDTree` on the equirectangular projection at
64.5 °N (`x = lon·cos(64.5°)·111320`, `y = lat·111320`); at these radii the error against
`haversine_m` is under 0.5 m [estimate], and the whole build is one pass over 7,263 points.

**Self-exclusion:** the object itself must be removed from its own neighbourhood counts,
otherwise `f_nbr_share_catC` is a leaky re-encoding of the object's own `category_orig`.
This is a one-line bug that would be invisible in the metrics because it *helps*.

### 2.4 External — EGAIS licences

`data/processed/v4_licences.csv` has 59 columns, 1,694 rows, 1,335 distinct coordinates,
85.8 % of which land on an `_all.csv` object [verified]. Usable columns:
`licence_status` (Active 1,120 / Archived 246 / Not in registry 328),
`licence_n_active_retail`, `licence_activity_class`, `licence_addr_score`,
`licence_distance_m`, `licence_match_level` (house 1,242 / street 124),
`licence_match_method` (geo 1,174 / address 192).

**The file as it stands cannot be used as a feature source.** It was computed only over
the v4 risk layers, so "no licence row" conflates *no licence at this address* with *the
contractor never nominated this object*. That missingness pattern re-imports the entire
v4 selection into what is supposed to be the independent external signal (§6).

**Required change (pipeline, not modelling):** re-run `src/arkhinfra/v4_egais.py` with
`_all.csv` as its input so all 7,263 objects receive a licence verdict. The module's
matcher is address+distance based and does not depend on the v4 vocabulary, so this is a
runner-level change (`scripts/match_egais_v4.py --input all`), and it must produce a new
output file rather than overwriting `v4_licences.csv`, whose numbers back a rendered
report:

```
data/processed/all_licences.csv        # 7,263 rows, same 37 licence_* columns
```

Cost [estimate]: the existing join runs 1,694 × ~2,100 pairs; 7,263 × 2,100 is ~4× that,
so single-digit minutes.

Features derived: `f_lic_status` (3 levels + `Not matched`), `f_lic_n_active_retail`,
`f_lic_is_retail_class`, `f_lic_addr_score`, `f_lic_distance_m`,
`f_lic_match_level`. **At inference nothing is missing** once the join is city-wide;
`Not in registry` is a meaningful level, and for Alcohol it is the single strongest
non-contractor feature available.

### 2.5 The v4 layer membership flags — Model B only

`f_v4_in_tobacco`, `f_v4_in_alcohol`, `f_v4_in_catering`, `f_v4_in_grocery` (boolean, by
`site_key` coordinate join), plus `f_v4_tier_tobacco` / `f_v4_tier_alcohol`
(`Direct` / `Inferred` / absent) and `f_v4_type` per layer. Coverage: 1,747 of 7,263
objects carry at least one flag (24.1 %) [verified]. See §6 for why these are in a
separate model and not in the main one.

### 2.6 Feature-block sizes

[estimate] text ≈ 15–25 k sparse columns at `min_df=2`; structured ≈ 25; spatial ≈ 60;
licence ≈ 10; v4 ≈ 10. Total dense block ≈ 105 columns, plus the sparse text block.

---

## 3. Leakage — named, sized, and countered

### 3.1 Channel 1: the training set is selected on name agreement

**78.9 % of training rows have `name_sim ≥ 0.99`** [verified]; 82.4 % ≥ 0.95. This is
structural, not accidental: the label attaches only where the matcher found name
agreement, so *by construction* the training block is the subset of the city whose name
is stable, informative, and identically spelled across four years.

It is not label leakage in the textbook sense — the label is not recoverable from the
name in the test fold. It is **selection bias on the most important feature**, and its
effect is the same: cross-validated performance will overstate field performance, because
in the field the model meets objects whose names are generic (`Продукты`, `Магазин`),
missing, or changed since the export was built.

Countermeasures, all three:

1. **Report metrics separately on the `probable` tier** (n = 50, name_sim 0.75–0.90).
   That slice is the only in-sample window onto "same business, different name", and it
   is the honest, if small, estimate of the penalty.
2. **Ship a name-ablated variant.** Identical pipeline with `f_txt_name` zeroed. The gap
   between the full and ablated models per head is the size of the name dependence, and
   it belongs in the report as a number rather than a caveat.
3. **Report coverage of the generic-name stratum**: export rows whose `norm_name` is one
   of the top generic strings (`продукты`, `продуктовый`, `магазин`, `продовольственный`
   — 61 benchmark rows between them [verified]) get their own metric line.

### 3.2 Channel 2: chain names in both train and test

**52.7 % of benchmark rows share a normalised name with at least one other row**
[verified]: `магнит` 65, `бристоль` 58, `пятерочка` 41, `продукты` 30, `вита норд` 24,
`coffee like` 24, `спортивная площадка` 24, `петровский` 22, `винлаб` 19.

Under a random split, `Магнит` appears in train and test; the model memorises
`магнит → Магазины` and cross-validation scores it as generalisation. It is not: it is a
brand lookup table, and the deliverable is applied to six okrugs the benchmark never
visited, where the *same* chains dominate. So the leak inflates CV without inflating
field performance — the worst kind, because it makes the model look ready.

Note the chains are not even clean: `магнит` covers 59 `Магазины` **and 6
`Медицинские организации`** (Магнит Аптека), `бристоль` 56 `Спецмагазины алкоголя` and 2
`Магазины`, `красное` 9 alcohol and 1 tobacco [verified]. A memorised brand lookup is
wrong ~10 % of the time on the biggest brands.

### 3.3 Channel 3: co-location

1,072 training rows sit at **597 distinct normalised export addresses**, largest group 16,
237 rows in groups of ≥5 [verified]. Two units in one shopping centre share every
neighbourhood feature and usually most of the name. A random split puts one in train and
the other in test.

### 3.4 Channel 4: join artefacts must never become features

* Nothing from `match_2022_local.csv` (`name_sim`, `addr_sim`, `distance_m`, `tier`,
  `n_candidates`) may be a feature. They are computed **from the label join** and are
  label-side quantities.
* The export's own `match_distance_meters` / `match_name_similarity` are dropped (§2.2),
  partly on their own merits and partly to keep the boundary unambiguous.
* `v3_common.recode_2022(df)` as a feature is *permitted* — it is a deterministic
  function of `category_orig`/`type_orig`/`name_orig`, all of which are already features,
  so it adds no information — but it should **not** be one, because a reader would
  reasonably mistake it for a label. It is the baseline instead (§4.1).

### 3.5 The countermeasure: one grouping key that blocks 3.2 and 3.3 together

A row can leak through its name *or* through its building, so blocking one is not enough
and using two separate splitters is not possible in one CV. Use a **connected-component
group key**:

```
nodes  = the 1,072 labelled export rows
edge   if norm_name(a) == norm_name(b)     and norm_name(a) != ""
edge   if norm_address(a) == norm_address(b) and norm_address(a) != ""
group  = connected component (union-find)
split  = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
```

Both empty-string guards are load-bearing. The benchmark has **78 rows with a null
address** [verified] and the export has generic names; without the guards the union-find
fuses them into one giant component and the splitter degenerates into a 2-fold split.

Two properties to verify at build time and print into `clf2022_metrics.json`, because
this construction can silently produce a useless split:

* **largest component ≤ 8 % of rows.** The `магнит` + shared-address closure is the risk:
  65 Магнит rows plus every other business in every building a Магнит occupies. If it
  exceeds the bound, weaken the name edge to exact-match on names occurring ≥3 times only
  (i.e. block chains, let coincidental one-off name collisions through).
* **every head has ≥1 positive in every fold.** With Alcohol at 57 and Tobacco at 16 this
  is not guaranteed; `StratifiedGroupKFold` stratifies on one label, so stratify on the
  **most constrained head that is still trained** (Alcohol) and check the rest. If a fold
  loses a class, reduce to 4 folds rather than abandoning the grouping.

Repeated CV: 5 folds × 5 repeats with different `random_state`, averaged, reporting the
across-repeat standard deviation. At n = 1,072 a single 5-fold estimate has enough
variance to reverse a model ranking.

### 3.6 What no splitter fixes

The six unvalidated okrugs. Every number produced by this CV describes Lomonosovsky,
Oktyabrsky and Maiskaya Gorka. Solombalsky (567 objects), Varavino-Faktoriya (440),
Isakogorsky (237), Severny (192), Maimaksansky (144), Tsiglomensky (69) — 1,649 objects,
23 % of the city — are extrapolation with no held-out evidence of any kind. The output
carries `extrapolated = True` for every one of them, and the report states it in the
summary, not a footnote. A **leave-one-okrug-out** run over the three benchmark okrugs is
the only available proxy for the size of the transfer penalty and should be reported
alongside the CV number.

Related and quantified [verified]: **45.0 % of export objects (3,271 of 7,263) have a
`type_orig` that never appears in the training block** — only 49 of the export's 218 types
are represented. That is the single number that decides whether the embedding model in
§4.4 earns its dependencies.

---

## 4. Model candidates, ranked

All dependency claims below were **verified by actually solving the environment**, not by
reading version tables: a scratch pixi workspace pinned to `python >=3.14.6,<3.15`,
`pandas >=3.0.3,<4`, `numpy >=2.5.0,<3`, channel `conda-forge`, platform `win-64`, solved
with `pixi lock`. Resolved builds are quoted.

### 4.1 Candidate 1 — rules / lexicon baseline (the floor)

**What:** `v3_common.recode_2022()` with the two known defects fixed (the `GROCERY_TYPES`
case mismatch and the `табак`/`табач` stem), extended into a per-class lexicon, plus a
`type_orig → modal 2022 category` lookup table learned from the training block.

**Measured, in-sample** [verified]: the lookup table reaches **96.5 % accuracy over the
49 `type_orig` values present in training** — but those 49 types cover only **55 % of the
export**. On the other 45 % it abstains entirely. That is the floor and the shape of its
failure: near-perfect where it fires, silent elsewhere. Any learned model that does not
clearly beat "96.5 % on 55 % of the city, nothing on the rest" is not worth its
dependencies.

**Cost:** zero new dependencies, ~1 day. **Output:** hard 0/1, no probability.

**It ships regardless** — as the baseline column in the output CSV and as the Industrial
and Tobacco channels (§1.4).

### 4.2 Candidate 2 — linear one-vs-rest on char n-grams **[recommended core]**

**What:** `LogisticRegression(penalty="l2", solver="liblinear", class_weight="balanced")`
per head, on the horizontally stacked sparse text block (§2.1) + scaled dense block
(§2.2–2.4). `C` tuned per head by nested grouped CV over `{0.1, 0.3, 1, 3, 10}`.

**Why linear and not gradient boosting on this block:** 1,072 rows against ~20 k sparse
text columns. A GBDT needs each split to be supported by enough rows to be meaningful;
with 57 positives in the Alcohol head, tree splits on individual n-grams are noise. L2
logistic regression on TF-IDF is the standard answer at this n and it produces monotone,
inspectable coefficients — which matters here, because the report has to explain *why*
the model calls an object an alcohol shop, to a client who has already been burned by a
contractor's unexplained 94.3 %.

**Dependencies** [verified — solved]:

```
scikit-learn  1.9.1  np2py314h1b5b07a_0   (conda-forge/win-64)
scipy         1.18.0 py314h221f224_0
     with     python 3.14.7  •  numpy 2.5.3  •  pandas 3.0.5  •  rapidfuzz 3.14.6
```

The full solve succeeds. Added closure is small (`joblib`, `threadpoolctl`, `narwhals`,
`tbb`). Env growth [estimate] ≈ 120 MB.

**Training time** [estimate]: a single fit is well under a second; 7 heads × 5 folds ×
5 repeats × 5 `C` values ≈ 875 fits ≈ **2–4 minutes on CPU**, single-threaded. No GPU.

### 4.3 Candidate 3 — LightGBM on the dense block, stacked **[recommended companion]**

**What:** the text model's **out-of-fold** score for each head becomes one feature
(7 features) in a `LGBMClassifier` over the dense structured + spatial + licence block
(~105 columns). `num_leaves=15`, `min_child_samples=20`, `n_estimators` by early stopping
on the inner fold, `is_unbalance=True`.

**Why stack rather than choose:** the two feature families want different inductive
biases. Text is high-dimensional and sparse, where linear wins at n = 1,072. Neighbourhood
composition and licence status are low-dimensional, interacting and non-monotone
(`f_lic_status == Active` matters only in combination with `f_lic_is_retail_class`;
`f_nbr_share_Магазины` matters differently inside a mall), which is exactly what a small
GBDT is for. The out-of-fold stacking must use the **same grouped folds** as the outer CV
or the stack leaks its own training labels.

**Dependencies** [verified — solved]:

```
lightgbm      4.7.0  cpu_py_h6f8b580_8   (conda-forge/noarch)
liblightgbm   4.7.0  cpu_h66f53fe_8      (conda-forge/win-64)
```

Solves together with scikit-learn 1.9.1 / python 3.14.7 / numpy 2.5.3 / pandas 3.0.5.
Note this is the **CPU** build; conda-forge's CUDA LightGBM builds were last published for
older Python and are not needed here. Env growth [estimate] ≈ 40 MB.

**Training time** [estimate]: ~0.3 s per fit on 1,072 × 105; the full nested protocol is
**under 2 minutes on CPU**.

**xgboost** is also available (3.4.0, `cuda129_pyh5c66634_0` and CPU builds) and would do
the same job; lightgbm is preferred only for its smaller closure and native NaN handling,
which §2.2's `f_str_is_24x7` needs.

### 4.4 Candidate 4 — frozen Russian sentence embeddings + logistic head

**What:** embed `f_txt_blob` with a Russian/multilingual sentence encoder, freeze, and use
the vectors (optionally reduced to 128 dims by PCA) as an additional dense block for the
§4.2 head. **No fine-tuning** — 1,072 examples is far too few to fine-tune a transformer
without overfitting, and the leakage structure of §3 would be memorised faster than the
task.

**Model choice, smallest defensible first:**

| model | params | dim | why |
|---|---|---|---|
| `sergeyzh/rubert-tiny-turbo` | 29 M | 312 | Russian-specific, embeds 7,263 short strings on CPU in well under a minute [estimate]; the right first try |
| `intfloat/multilingual-e5-base` | 278 M | 768 | stronger, still CPU-feasible (~5–8 min for the corpus [estimate]); needs the `query:`/`passage:` prefix convention |
| `ai-forever/ru-en-RoSBERTa` | 404 M | 1024 | best Russian retrieval quality; only worth it if `e5-base` shows a real gain |

**What it buys over char n-grams — the honest answer:** on the 55 % of the city whose
`type_orig` the training block has seen, essentially nothing; char n-grams already
separate `Аптека` from `Кафе` at 96.5 %. The entire case is the **45 % of export objects
(3,271) with an unseen `type_orig`** and the generic-name stratum. An embedding places
`Стоматологический кабинет` near `Стоматология` without having seen it; a char n-gram
model gets partial credit from the shared stem and no credit for
`Медицинский центр "Здоровье"`. So the decision rule is explicit:

> Adopt Candidate 4 **only if** it improves the held-out metric on the
> unseen-`type_orig` slice by more than one across-repeat standard deviation. Improvement
> on the overall CV number is not sufficient, because the overall number is dominated by
> the seen-type majority.

**Dependencies** [verified — solved, both CPU and CUDA]:

```
CPU :  pytorch 2.13.0 cpu_mkl_py314_h9066ed4_102  •  libtorch 2.13.0 cpu_mkl_hb008cf6_102
CUDA:  pytorch 2.13.0 cuda128_mkl_py314_ha8fd4c2_302 • libtorch cuda128_mkl_hffeedd6_302
       (cuda-version 12.8, under [system-requirements] cuda = "12.8")
both:  transformers 5.16.1 (noarch) • sentence-transformers 6.0.1 (noarch)
       tokenizers 0.23.1 py314h8101fc5_0 • safetensors 0.8.0 py314h9f07db2_1
       huggingface_hub 1.31.0 (noarch)
```

All solve against python 3.14.7 / numpy 2.5.3 / pandas 3.0.5. Note `transformers` is
**5.x** — the 4.x API this repo's authors may remember has changed; `sentence-transformers`
6.0.1 is built against it and is the safe entry point.

Env growth [estimate]: CPU ≈ 1.2 GB unpacked; **CUDA ≈ 4–6 GB unpacked** (cuDNN and the
CUDA runtime dominate). Plus model weights: 60 MB (rubert-tiny-turbo) to 1.6 GB
(RoSBERTa), downloaded at first run — which also means **the pipeline stops being
offline-reproducible** unless the weights are vendored or cached, and this repo already
has one such dependency (contextily tiles) that it handles by falling back.

**On the hardware.** The corpus is 7,263 short strings. Inference is **seconds** even on
the 6 GB RTX 3050, and there is no training pass. **The RTX 5090 is irrelevant to this
task and should not be provisioned for it** — say so to the client rather than accepting
the offer, and note that if it ever becomes relevant (fine-tuning, a much larger corpus),
sm_120 requires the CUDA 12.8+ build, which is exactly the one that solves above.

### 4.5 Ranking and recommendation

1. **Candidate 1** — ships always, as baseline + the two non-modelled heads. Not optional.
2. **Candidate 2 + Candidate 3 as a stack** — **the recommended deliverable.** Two small,
   auditable, CPU-only dependencies (`scikit-learn`, `lightgbm`, `scipy`), both verified
   to solve on python 3.14 / pandas 3.0, total env growth ~160 MB, full nested CV under
   ten minutes, and every coefficient inspectable.
3. **Candidate 4** — a bounded, time-boxed experiment with a pre-committed adoption rule
   (§4.4), starting with `rubert-tiny-turbo` on CPU. The 45 %-unseen-type figure makes it
   a genuine question rather than a fashion; the 1.2–6 GB dependency makes it one worth
   answering before adopting.

Rejected without experiment: fine-tuning any transformer (n = 1,072); any deep model
trained from scratch; an LLM labeller (the client excluded it, and it would re-introduce
the unverifiable-inference problem the v4 layers already have).

---

## 5. Calibration

### 5.1 The problem, precisely

Seven one-vs-rest scores are seven independent quantities on incomparable scales. Each
head is trained with `class_weight="balanced"`, which deliberately distorts the implied
prior, so raw `predict_proba` outputs are not probabilities of anything. And the positive
counts differ by a factor of 25 (402 vs 16), so one calibration method cannot serve all
seven.

### 5.2 Method, per head, by positive count

| head | positives | calibrator | why |
|---|---|---|---|
| Общепит (402), Медицинские (321), Магазины (258) | ≥250 | **isotonic** | enough events to support a non-parametric fit without collapsing into a step function |
| Спортивные (79), Спецмагазины алкоголя (57) | 50–100 | **beta calibration** | 3 parameters; unlike Platt it can correct the base-rate shift that `class_weight="balanced"` introduces, and unlike isotonic it does not produce 4 distinct output values from 57 events |
| Точки продажи табака (16) | <50 | **none** | emit the rule score with `calibration = "not estimated"`; see §1.4 |
| Пром. Объекты (0) | — | **none** | `p = NA`, rule flag only |

Beta calibration is a logistic regression on the two features
`[log p, −log(1−p)]` — about ten lines, no dependency. There is no `betacal` package on
conda-forge, so implement it in `src/arkhinfra/clf2022.py` with the citation in the
docstring rather than adding a PyPI-only dependency to a conda-forge-only environment.

### 5.3 Fitting it without spending the benchmark twice

`CalibratedClassifierCV(cv=…)` refits the base estimator inside each calibration fold,
which at n = 1,072 wastes data and — critically — does not accept the §3.5 group key
through its own splitter cleanly. Use explicit **cross-fitting** instead:

```
outer:  StratifiedGroupKFold(5) over the 1,072 rows, groups = §3.5 components
  for each outer fold f:
      inner: StratifiedGroupKFold(4) on outer-train
        -> fit base model on 3 inner folds, score the 4th
        -> the 4 inner-held-out score sets are the CALIBRATION set for fold f
      fit the calibrator on those inner out-of-fold scores
      refit the base model on ALL of outer-train
      apply base model + calibrator to outer-test  -> the only scored predictions
```

Each row is used for exactly one purpose per outer fold: either to fit the base model, or
to fit the calibrator, or to be scored — never two. The calibrator sees ~800 scored rows
per fold, which is enough for isotonic on the big heads and comfortable for beta on the
small ones. Repeat the whole thing 5× with different seeds and average the reliability
curves.

The **shipped** model is a final refit on all 1,072 rows with a calibrator fitted on the
full set of outer out-of-fold scores. That is the standard construction and its one
honest caveat — the shipped calibrator is fitted on scores from models trained on 80 % of
the data while the shipped base model saw 100 % — is small at this ratio and should be
stated once.

### 5.4 Prior shift

Training negatives come from three central okrugs. `Maiskaya Gorka`'s object mix already
differs from `Oktyabrsky`'s, and Maimaksansky (144 objects) differs from both. Calibrated
probabilities are calibrated **for the benchmark okrugs' base rates**.

Offer, but do not apply by default, per-okrug prior correction by the
Saerens–Latinne–Decaestecker EM procedure: it re-estimates the target-domain prior from
the unlabelled predictions and rescales. It is an *assumption* (that the class-conditional
feature distributions are stable across okrugs) which nothing in this repository can
check, so it ships as an optional column `p_*_prior_adj` with the assumption named, never
as the headline number.

### 5.5 What the numbers may and may not be claimed to mean

**May be claimed:**
> `p_medical = 0.87` means: among export objects that this model scores 0.87, about 87 %
> were on the 2022 survey's *Медицинские организации* list, as estimated inside
> Lomonosovsky / Oktyabrsky / Maiskaya Gorka, at 2022's survey practice.

**May not be claimed:**

* **Not ground truth.** The target is *the 2022 survey's inclusion decision*, which is
  itself incomplete — independent recall against the export is 64.6 %. Every probability
  inherits that.
* **Not a joint distribution.** The seven numbers do not sum to 1 and their sum carries no
  meaning. `p_grocery × p_alcohol` is **not** P(grocery and alcohol): the training data
  contains **seven genuine co-membership examples** (§1.5), so class dependence is not
  estimated, it is assumed away. Any downstream use that combines two heads must be
  flagged as resting on an independence assumption the data cannot support — and this is
  precisely the use case the client described (a grocery that also sells alcohol and
  tobacco), so it must be said in the deliverable, not in an appendix.
* **Not calibrated outside three okrugs.** 1,649 objects (23 %) carry `extrapolated=True`.
* **Not calibrated for Tobacco or Industrial at all.**
* **Not a 2026 statement.** Both the label semantics and the export's own provenance
  (89.6 % OSM-only, 2.4 % dual-sourced) limit it to "what a 2022-style survey would have
  recorded about the object the export describes".

Report per head: reliability diagram (10 quantile bins), **ECE** and **MCE**, Brier score
decomposed into reliability/resolution/uncertainty, and bootstrap CIs over the 5×5 repeats.
Refuse to print ECE for Tobacco (n = 16) — print the count instead.

---

## 6. The v4 layers: position and design

### 6.1 Position

**Include them — but never in the model whose numbers are the headline.** Ship two models
from one pipeline.

The argument for inclusion: the layers are not labels and not a restatement of the 2022
survey. The contractor built them from 2GIS category tags, OSM tags and its own inference
over a different vocabulary and a different date. For `Спецмагазины алкоголя`, where the
model has 57 positives, discarding the single best available covariate to preserve an
abstract independence is not rigour, it is self-harm.

The argument against: 82 % of the tobacco/alcohol layers are the
`Возможная …` (inferred) tier, which the contractor's own `verification_comment` calls
*требует отдельной проверки*. Feeding an unverified judgement about "does this object sell
alcohol" into a model that predicts "is this object an alcohol shop" makes the model, in
that head, largely an echo. A report that then says "the model confirms 638 off-trade
alcohol objects" would be circular, and this client has already been shown one circular
number (the 94.3 % that came back at 64 %).

Both arguments are right about different uses, which is why the answer is two models, not
a compromise feature set.

### 6.2 The design

| | **Model A — exogenous** | **Model B — with contractor tags** |
|---|---|---|
| text | yes | yes |
| structured | yes | yes |
| spatial / neighbourhood | yes | yes |
| EGAIS licences (city-wide, §2.4) | yes | yes |
| v4 layer flags & tiers | **no** | yes |
| role | **every headline number** | "what the contractor's tags add" |

Identical folds, identical calibration protocol, identical hyperparameter grid. The
deliverable CSV carries both: `p_<class>_a`, `p_<class>_b`, and `p_<class>_delta`.

**The delta is itself a finding, and should be reported as one.** Per head it measures how
much the contractor's risk judgement adds over what the export alone supports. A large
positive delta on Alcohol says the tags carry real information the export lacks — which is
consistent with the fivefold-undercount story already in the repo. A near-zero delta says
the tags restate `category_orig`/`type_orig`, and the client has paid for a re-labelling of
what they already had. Either outcome is worth knowing and neither is available from a
single model.

Note that EGAIS sits in **both** models deliberately: it is a state registry, not the
contractor's opinion, so it is exogenous by construction — **provided** §2.4's city-wide
re-join is done. Without it, "has a licence row" is a proxy for "the contractor nominated
this object", and Model A silently becomes Model B. That re-join is a hard prerequisite,
not a nice-to-have.

### 6.3 Two secondary points

* **Coverage flag.** Only 24.1 % of the export carries any layer tag, and the absence is
  the result of a targeted search, so absence ≠ negative. Model B gets an explicit
  `f_v4_any_layer` flag so the model can distinguish "tagged as not-alcohol" (impossible —
  the layers have no negatives) from "never examined". Without it, `f_v4_in_alcohol = 0`
  silently means "not examined" for 76 % of the city.
* **The grocery layer is not a pure re-tagging layer** (§0.2): 42 % of its coordinates are
  absent from `_all.csv`. Those rows cannot be features of an export object that does not
  exist. They should be reported as a coverage extension and flagged for the client
  (§8.5), not quietly joined away.

---

## 7. Artefacts and pipeline

Following the repo's conventions: importable code in `src/arkhinfra/`, runnable entry
points in `scripts/`, derived data in `data/processed/`, every path from
`arkhinfra.paths`, nothing built with `../..`.

### 7.1 Code

```
src/arkhinfra/clf2022.py     # the whole model: labels, features, splitter,
                             # calibration, train/predict. One module, on the
                             # scale of v4_egais.py.
scripts/train_clf2022.py     # thin launcher -> clf2022.train()
scripts/predict_clf2022.py   # thin launcher -> clf2022.predict()
```

One module rather than three, matching `v4_egais.py` / `basecheck.py`: the label builder,
the splitter and the calibrator are meaningless apart from each other, and splitting them
invites the copy-drift this repo has already been bitten by twice. It **imports** from
`v3_common` (`norm_name`, `norm_address`, `norm_okrug`, `haversine_m`, `CATEGORY_EN`) and
`v4_common` (`parse_hours`, `recode_2022_v4`, the layer constants) and copies nothing —
the rule the repo states for `basecheck.py`, `egais.py` and `v4_common.py`.

Additions to `arkhinfra/paths.py`:

```python
V4_ALL      = RAW4 / "infrastructure_архангельск_2026-08-31_quality_excel_all.csv"
            # byte-identical to V3_CSV (md5 949c0756…); kept as its own constant
            # so v4 code need not reach into RAW3
V4_CATERING = RAW4 / "infrastructure_архангельск_2026-09-05_quality_excelобщепит.csv"
V4_GROCERY  = RAW4 / "infrastructure_архангельск_2026-09-05_quality_excelпродуктовые магазины.csv"
ALL_LICENCES = PROC / "all_licences.csv"
CLF_DIR      = PROC / "clf2022"
```

(Note the two 2026-09-05 filenames have **no space** before `общепит` / `продуктовые` —
unlike the tobacco and alcohol files. Verified against the directory listing; a
hand-written path will be wrong.)

### 7.2 Pixi tasks

```toml
match-egais-all = { cmd = "python scripts/match_egais_v4.py --input all --out data/processed/all_licences.csv",
                    description = "Join the whole city export to the licence registry -> data/processed/all_licences.csv" }
train-clf2022   = { cmd = "python scripts/train_clf2022.py",
                    description = "Train + calibrate the 2022-taxonomy classifier; writes data/processed/clf2022/" }
predict-clf2022 = { cmd = "python scripts/predict_clf2022.py",
                    description = "Score all 7,263 export objects -> data/processed/clf2022/clf2022_predictions.csv" }
clf2022         = { depends-on = ["match-egais-all", "train-clf2022", "predict-clf2022"] }
```

`train_clf2022.py` flags: `--model {a,b,both}` (default `both`), `--folds 5`,
`--repeats 5`, `--seed 0`, `--embeddings {none,rubert-tiny-turbo,e5-base}`
(default `none`), `--no-cache`.

### 7.3 Outputs, all under `data/processed/clf2022/`

`clf2022_predictions.csv` — semicolon-delimited, UTF-8 with BOM, like every other CSV
here. One row per export object, **7,263 rows**:

| column | note |
|---|---|
| `export_row_id` | 0-based position in `_all.csv` — the join key back to the export |
| `name_orig`, `adress_orig`, `okrug_key`, `latitude`, `longitude` | identity, copied |
| `category_orig`, `type_orig` | the export's own labels, for eyeballing |
| `p_catering_a` … `p_industrial_a` | Model A, 7 columns, calibrated; `NA` for Industrial |
| `p_catering_b` … `p_industrial_b` | Model B, 7 columns |
| `p_*_delta` | B − A, 7 columns |
| `calibration_<class>` | `isotonic` / `beta` / `not estimated` / `rule only` |
| `rule_<class>` | the Candidate-1 baseline's 0/1, 7 columns |
| `top_class`, `top_p` | argmax over the 7 (A), for convenience only — **not** a decision |
| `n_classes_ge_050` | how many heads exceed 0.5 |
| `extrapolated` | `True` for the 6 non-benchmark okrugs (1,649 rows) |
| `in_training` | `True` for the 1,072 labelled rows — so no reader mistakes a fitted value for a prediction |
| `type_seen_in_training` | `False` for the 3,271 unseen-`type_orig` rows |
| `layer_coverage` | which v4 layers tagged this object; empty for 5,516 rows |
| `licence_status`, `licence_n_active_retail` | from `all_licences.csv` |
| `model_version`, `built_at` | provenance |

Also written:

```
clf2022_metrics.json        per head x model: PR-AUC, ROC-AUC, F1@best-threshold,
                            ECE, MCE, Brier decomposition, mean +- sd over 5x5 repeats;
                            plus the split diagnostics of §3.5 (largest component share,
                            per-fold positive counts)
clf2022_calibration.csv     reliability-diagram bins, per head x model
clf2022_slices.csv          metrics on the named slices: probable-tier, generic-name,
                            unseen-type, per-okrug, leave-one-okrug-out
clf2022_model.joblib        the shipped estimators + calibrators + the fitted vectoriser
clf2022_summary.txt         the human-readable digest, in the style of
                            v4_licences_summary.txt
```

`clf2022_model.joblib` is git-ignored along with the rest of `data/processed/`; it is a
rebuildable artefact, and a pickled scikit-learn estimator is version-bound anyway.

### 7.4 Report hook

A `analysis/v5/clf-2022.qmd` reading `clf2022_*` and re-running nothing — the pattern
`analysis/v4/licences-v4-ru.qmd` already establishes. Out of scope for this half of the
document; the artefact names above are chosen so the report can be written against them
without re-deriving anything.

---

## 8. Open questions for the client

Only questions whose answer changes the design. Ordered by how much.

**8.1 Is `Магазины` "grocery shops" or "shops of any kind"?** *(changes label
construction)*
The 2022 class holds 400 rows whose `type_orig` is dominated by
`Продуктовый магазин` (204) and `Супермаркет` (147) — it reads as a grocery class with a
general name. If the deliverable class is *grocery*, the target must be built from
`type_orig ∈ GROCERY_TYPES` rather than from `category_orig == "Магазины"`, which changes
the positives, the negatives and the class's meaning in every downstream comparison. If it
is *retail of any kind*, then a clothing shop is a positive and the class is nearly
uninformative for a health study. **This is the single most consequential unanswered
question in the design.**

**8.2 `Пром. Объекты` has zero trainable examples. Six classes or seven?** *(changes the
deliverable's shape)*
Options: (a) ship 6 probabilities + 1 rule flag marked unreliable — the recommendation;
(b) drop the class; (c) fund labelling for it. The class has 10 benchmark rows total, all
unmatched or gps-only, and the existing rule is dominated by name-substring false
positives. Continuing to report it as if it were modelled is the one option that is not
available.

**8.3 Calibrated to *the 2022 survey's decision*, or to *ground truth*?** *(changes what
is deliverable at all)*
§5.5 can only support the former. If the client needs the latter — "the probability this
object really sells alcohol" — the only route is an audit sample: ~200 objects, stratified
by predicted probability and okrug, field- or phone-verified, used solely to re-calibrate.
Nothing in this repository can substitute for it, and the difference is not presentational.

**8.4 Do the six unvalidated okrugs get numbers?** *(changes the output contract)*
1,649 objects, 23 % of the city, with no held-out evidence of any kind. Ship the
probabilities with `extrapolated=True` (recommended), or suppress them below a confidence
band, or ship them only as aggregates. This is a decision about what the client will be
comfortable defending, not a technical one.

**8.5 Are the v4 layers final, and what is the grocery layer?** *(changes Model B and the
schedule)*
Two layers arrived on 2026-09-05, after `CLAUDE.md` and `v4_common.py` were written. If
more are coming, Model B is a moving target and should be versioned by layer set. And the
grocery layer's 725 coordinates absent from `_all.csv` (42 %, mostly
`Стационарные рынки и ярмарки` and `Торговые центры`) need an answer from the contractor:
a genuine coverage extension the city export missed, or artefacts of a different
geocoding pass? If the former, the 7,263-object universe is itself incomplete and the
denominator of every rate in this study moves.

**8.6 Two conflicting quality bars, and one of them must give.** *(affects hyperparameter
choice, not architecture)*
Is a false positive or a false negative worse for the study? A health-infrastructure
accessibility measure wants recall (a missed pharmacy is a gap in a map); a risk-factor
density measure wants precision (a false alcohol shop inflates a risk index). The two
cannot be optimised together across the seven heads, and the answer sets the operating
threshold per head. If the client's answer is "it depends on the class", that is a fine
answer and it simply needs to be given class by class.
