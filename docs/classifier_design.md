# A classifier over the 2022 taxonomy: design, findings, and what the evidence supports

**Status: design only. No code has been written, and none should be until the changes in
§6 land.** Dated 2026-09-11; re-checked 2026-09-15.

**Read §10 before acting on anything below.** The verdict of §9 survived an adversarial
re-check against the data, but 2.4, §3.1 and §4 did not survive in the wording they carry
here, and three live defects in the rule itself (D1-D3, §10.3) were found on the 84 % of the
city that no evaluation in this document reaches.

The commission was: build a classifier that, for every object in the later exports, returns
the probability that it belongs to each of the seven classes of the 2022 taxonomy —
multi-label, because one object can be several things at once (a grocery that also sells
alcohol and tobacco).

This document is the answer to whether that can be built, and what should be built instead.
It was produced by three reviewers working from the same brief: an ML engineer (label
construction, features, models, calibration), a statistician (estimand, validation,
uncertainty, bias) and a critic (adversarial re-check of both). Their full documents are
preserved in `docs/classifier/`:

- `docs/classifier/design_ml.md` — the modelling half, 936 lines.
- `docs/classifier/design_stats.md` — the evaluation half, 837 lines.
- `docs/classifier/critique.md` — the critique, 636 lines, with the verification results.
- `docs/classifier/probes/*.py` — the critic's reproducible probes.

Everything below marked **[verified]** was checked against the repository, in most cases
twice: once by its author and once independently by the critic, who re-ran every
load-bearing number and confirmed it. Where the two halves disagreed, the disagreement is
recorded rather than smoothed over.

---

## 1. The client's fixed decisions

These were settled before the work started and are not reopened here.

1. **Training labels come from the 2022 benchmark as it stands.** No manual labelling for
   training, no LLM labelling, and the v4 risk layers are not a label source. Multi-label
   output was to emerge from calibrated one-vs-rest probabilities.
2. **Scope is the whole city, all nine okrugs** (7,263 objects).
3. **Stack is the team's call**, with GPU available (local RTX 3050 6 GB; remote RTX 5090
   during working hours).
4. **The first deliverable is a design document, not code.**

Two decisions were taken during this review:

5. **A manual audit of 200–600 objects is approved** (§7).
6. **The meaning of the 2022 class `Магазины` goes back to the authors of the 2022 study**
   (§8.1). Until they answer, both target variants stay on the table.

---

## 2. Five facts that decide everything else

**2.1 `data/raw_v4/…_all.csv` and `V3_CSV` are the same file.** [verified — identical MD5
`949c075672028e13f212c9aa4c57d5c6`] "The later export" is one object table of 7,263 rows,
and `data/processed/match_2022_local.csv` already is the benchmark-to-export join this task
needs. No new matcher is required.

**2.2 There are five files in `data/raw_v4/`, not the two `v4_common.load_v4()` knows
about.** [verified] Two layers arrived on 2026-09-05 — catering (566 rows) and grocery
(1,711) — after `CLAUDE.md` and `v4_common.py` were written. Four of the five layers
correspond to four of the seven 2022 classes.

**2.3 Linkage to the benchmark is systematically class-dependent, and biased against
exactly the classes the study exists to measure.** [verified, re-checked cell by cell]

| 2022 class | n | linked (exact+probable) | link rate |
|---|---:|---:|---:|
| Медицинские организации | 371 | 321 | **86.5 %** |
| Общепит | 622 | 402 | 64.6 % |
| Магазины | 400 | 258 | 64.5 % |
| Спецмагазины алкоголя | 116 | 57 | **49.1 %** |
| Спортивные объекты | 188 | 79 | **42.0 %** |
| Точки продажи табака | 46 | 16 | **34.8 %** |
| Пром. Объекты | 10 | **0** | **0 %** |
| total | 1,753 | 1,133 | 64.6 % |

The distortion runs inside classes too: `Супермаркет` links at 86.4 % against
`Продуктовый магазин` at 48.5 %; `Спорткомплекс` at 84.2 % against `Спортивная площадка`
at **20.0 %**. A sport model would be trained on indoor commercial facilities and applied
to a city where outdoor pitches, stadiums and sections are 112 of the benchmark's 188 sport
objects. Multi-tenant sites — malls and market halls, where an object most plausibly carries
two classes — link at 0.362 against 0.703 for single-occupancy coordinates.

The one axis that is **not** distorted is okrug (44.3/41.6/14.1 → 43.9/42.5/13.6). No okrug
reweighting is needed.

**2.4 The free rule is already at the measurable ceiling.** [verified; the band is corrected in §10.1 — alcohol precision is 0.887 and tobacco recall 0.625, both outside the range stated here] The corrected string
recoder scores per-class precision 0.91–1.00 at recall 0.81–0.99 on the linked rows —
including Alcohol at P 0.915 / R 0.811 and Sport at P 0.985 / R 0.880, the two classes the
evaluation half had assumed string rules were weak on. A plain `type_orig` → modal-class
lookup scores 96.5 % in-sample.

**2.5 The 45 % of the city with an unseen `type_orig` is not a frontier — it is outside the
taxonomy.** [verified, independently reproduced] 3,271 of 7,263 objects carry a `type_orig`
that never appears in training, and **97.7 % of them recode to `Other`**. The slice is
`Магазин одежды` (307), `Парикмахерская` (226), `Автосервис` (151), `Мебельный магазин`
(124), `Банк` (75) — the city's clothing, hairdressing and car-repair trade. Applied to the
whole export the rule puts **4,597 of 7,263 objects (63 %) outside the 2022 scheme
entirely**. There is no hidden mass of corner shops there: `Продуктовый магазин` is a *seen*
type, in the other 55 %.

---

## 3. Why the deliverable cannot be built in the shape specified

Three findings, each independently sufficient.

### 3.1 The labelled rows are the rows the free rule already gets right

Combine 2.4 and 2.5. The model's addressable universe is the 3,992 seen-type rows; on those
the free rule is already at P 0.91–1.00. So:

> The model's only possible contribution is to correct the rule's errors inside the
> seen-type slice — and those are precisely the rows for which no label exists. Every row
> that carries a label is a row the free rule already gets right.

**Superseded in its wording by §10.1:** 96 of the 1,133 labelled rows are rows the rule gets
wrong. The conclusion holds — all 96 are join artefacts, single-label mis-scoring of true
co-membership, or one missing constant — but the sentence above, as written, is false.

The cross-validation metric around which the entire evaluation half was built therefore
measures the one thing that does not need measuring.

### 3.2 The negative set contains more true positives than the positive set, for the classes that matter

Both halves called this "label noise of unknown size". It is free to measure: run the rule
over the 5,614 export rows inside the three benchmark okrugs and count objects the rule
identifies as class *k* that training labels 0 for class *k*. [verified]

| class | rule says class *k* | labelled positive | **rule-positive, trained as NEGATIVE** |
|---|---:|---:|---:|
| Grocery | 455 | 243 | **254** |
| Medical | 536 | 310 | **234** |
| Sport | 266 | 76 | **200** |
| Catering | 526 | 388 | 160 |
| Tobacco | 50 | 15 | **42** |
| Alcohol | 83 | 53 | **40** |

These are not rule artefacts. 36 of the 40 alcohol negatives carry
`type_orig = Алкогольный магазин`, and they include **Бристоль** — the chain supplying 29 of
the 57 alcohol positives. The same fascia would be labelled 1 on some rows and 0 on others.
Tobacco's negative pool holds 9 × `Табачный магазин` and 7 × `Вейп-магазин` against 15
positives in total.

**Failure scenario.** A one-vs-rest model is asked to learn that `алкогольный магазин`
predicts Alcohol while 36 rows carrying that exact string are labelled 0 against 53 labelled
1. It shrinks the coefficient on the most informative n-gram in the class. The model ends up
worse than the free rule on Alcohol, Tobacco and Sport, and cross-validation does not reveal
why, because its negatives carry the same noise.

### 3.3 Nothing can validate the multi-label output

Training holds **7** genuine co-membership examples [verified]; the city holds roughly **560**
grocery × tobacco sites. **§10.4 sharpens this into the decisive argument:** the export's
features do not encode co-membership at all — the rule's own predicates find 47 two-class
objects city-wide (0.6 %) — so the seven-column deliverable fails on the inputs, not on the
sample size, and no amount of labelling or compute reaches it. Seven independently fitted marginals carry no information about
dependence, and no calibration method creates it. Two of the seven heads are not models at
all: Industrial has zero trainable examples, Tobacco has 16 (bound width 65 pp).

And what the probabilities would estimate is not what the name suggests. It is
`P(the 2022 survey placed this object on list k | 2026 features)` — conditional on the object
surviving four years under a recognisable name, at 2022 prevalence, in three okrugs. That is
defensible in a paper only as a sentence in the abstract, not as a limitation in §6.

---

## 4. What the evidence does support

The shape of the deliverable can change without touching the client's label decision:

- **The corrected multi-label rule as the primary product**, with its per-class
  precision/recall table as the headline validation. Free, auditable, already at the ceiling.
  **Not yet a product - see §10.3 and §10.5:** three live defects (51 greengrocers lost,
  ~30 % of the `Sport` class not sport facilities, 35 groceries suppressed by class priority)
  must be fixed in a new module first, and this table covers 15.6 % of the city at its easy
  end, which the report must say.
- **The learned model as a screening score over the rule's residual** — a ranked manual-review
  queue covering the objects where rule and model disagree, validated by the audit of §7
  rather than by cross-validation. This makes the model produce *work* rather than *numbers*,
  and the audit is the only thing that can measure it.
- **Alcohol from EGAIS directly**, as this repository already concludes. The registry covers
  all nine okrugs and is a primary source; a 57-positive model is strictly worse.
- **Tobacco as the contractor's tag with its provenance and no number.** No benchmark exists
  anywhere: the registry has no tobacco class, and the 2022 tobacco list is 46 objects in
  three okrugs.

If seven probability columns are required anyway, they can be produced — but the document
must say that four of them restate a keyword rule, one is a rule with a probability painted
on it, one is unvalidatable, and one does not exist.

---

## 5. What was sound

The statistician's half is numerically clean — every figure reproduced under independent
re-checking. Its estimand statement, its bias bounds and its refusal list are publishable as
they stand. Its defects are the baseline gate (§6, B4) and one prior-shift figure that
borrows the contractor's unverified tier.

The modelling half's leakage inventory, cross-fitting protocol and "may not be claimed" list
are correct. Its dependency audit was done by actually solving pixi environments under
python 3.14 / pandas 3.0 / numpy 2.5 rather than reading compatibility tables:
`scikit-learn 1.9.1`, `lightgbm 4.7.0`, `scipy 1.18.0` all solve; so do `pytorch 2.13.0`
(CPU and CUDA 12.8), `transformers 5.16.1`, `sentence-transformers 6.0.1` — note transformers
**5.x**, not 4.x. **No GPU is needed for this task**: 7,263 short strings embed in seconds
even on the 3050, and the RTX 5090 should not be reserved for it.

---

## 6. Required before any code is written

**Blocking, must land first:**

- **B1 — the grouping key collapses.** The proposed "shared name ∪ shared address" key
  produces a connected component holding **63.6 %** of the data against its own stated 8 %
  bound, and its fallback makes it worse (60.7 %). Drop the chain edges (3.3 %) or adopt the
  building key (3.5 %), and keep the largest-component assertion as a guard.
- **B2 — the two halves specify different primary splitters** with opposite justifications,
  each calling its own the headline. They are different estimands. Name one, with the other
  as a mandatory companion run.
- **B3 — publish the negative-noise table of §3.2 and decide the masking policy** before
  modelling. The defensible options are to mask rule-positive-unlabelled cells out of the
  loss (recommended — it is the same argument the design already applies to `gps_only`), or
  to accept them and state in the report that every recall is measured against a negative
  pool known to contain 40–254 true positives.
- **B4 — the headline stopping rule cannot fire.** Its premise ("string rules are weak on
  Alcohol and Sport") is false on this data (2.4), and it compares a single-label rule with a
  multi-label model. Rewrite it against a multi-label rule baseline with a gate width the
  confidence interval can actually resolve (±12.4 pp on alcohol recall, ±11.1 on sport).

**Before anything goes to the client:**

- **S1 — the grocery layer is contaminated.** Its `Стационарные рынки и ярмарки` type is
  about 75 % **rubbish collection points** (`Мусорная площадка` 109, `Контейнер для вторсырья`
  32) — 184 rows, 10.8 % of the layer. The alarm raised about this layer shifting the study's
  denominator was misdirected.
- **S2 — both halves join the layers to the export by exact float coordinate equality.** At a
  25 m tolerance the match rises from 86 % to **98.1 %** (grocery 57.6 → 81.4 %). Exact float
  equality on coordinates is this repository's signature failure mode.
- **S3 — an unnamed leakage channel.** 709 licences (33.8 %) overlap the 2022 year, 225 of
  them archived: the registry carries the label's year. The licence feature block needs an
  ablation.
- **S4/S5 — settle the target variable** (`category_orig` vs the recoder, and the 8th `Other`
  class) **and the output contract for Industrial and Tobacco**; the two halves specify
  opposite things.
- **The EGAIS feature block must be rebuilt.** `v4_licences.csv` covers only the risk layers,
  so "no licence" is confounded with "the contractor never considered this object" — which
  smuggles the contractor's selection into a supposedly independent external signal. Re-join
  across all 7,263 objects into a **new** file; do not overwrite `v4_licences.csv`, which
  carries the numbers of a rendered report.

---

## 7. The audit (approved)

**600 objects, 6 strata × 100**, all seven classes marked present/absent per object from
name + address + 2GIS/OSM tags + a short web check:

| # | stratum | what it tests |
|---|---|---|
| 1 | p_grocery ≥ 0.5 **and** p_tobacco ≥ 0.5 | precision of the commonest co-label |
| 2 | p_grocery ≥ 0.5 **and** p_tobacco < 0.2 | is the model missing grocery+tobacco |
| 3 | p_alcohol ≥ 0.5 **and** p_catering ≥ 0.5 | on-trade co-label |
| 4 | p_alcohol ≥ 0.5 **and** p_catering < 0.2 | off/on-trade separation |
| 5 | p_medical ≥ 0.5 **or** p_sport ≥ 0.5 | single-label control |
| 6 | **simple random sample of all 7,263** | anchors prevalence |

Stratum 6 is not optional: without it no stratified cell can be reweighted back to the city
and no city-level multi-label rate can be stated. Draw it proportionally to okrug, which puts
~23 of the 100 in the six unbenchmarked okrugs.

Write the labelling rules down **before** starting, including what counts as "sells tobacco".
Double-label 10 % (60 objects) for Cohen's κ per class — at n = 60 the SE on κ is ≈ 0.10,
which detects κ < 0.6 but cannot separate 0.8 from 0.9, so do not quote κ to two decimals.

**Effort: ~20 hours at 2 min/object, plus ~2 hours for the double-labelled subset.**
**Buys:** per-cell rates to ±10 pp; city-level multi-label prevalence for common combinations
to roughly ±4 pp after reweighting; the first real evidence the joint output means anything.
**Does not buy:** anything about Industrial (~10 objects city-wide → 0–1 in sample); any
per-okrug number for the six unbenchmarked okrugs; any improvement to *training*.

**Cheaper variant:** 200 objects, strata 1, 2 and 6 only — ±14 pp per cell, tests exactly one
combination (grocery × tobacco), ~7 hours.

---

## 8. Open questions

### 8.1 For the authors of the 2022 study

**Is `Магазины` "grocery shops" or "shops of any kind"?** The class holds 400 rows whose
`type_orig` is `Продуктовый магазин` (204), `Супермаркет` (147), `Фрукты-овощи` (35),
`Кулинария` (6), `Рынок` (3), `Ярмарка` (4), `Сыроварня` (1) — 392 of 400 are food retail,
and there is no non-food retail in the class at all. So the data reads as a grocery class
with a general name, but the answer changes the target, the positives, the negatives and
every downstream comparison. Until they answer, both variants stay open.

Worth asking at the same time: **what `Пром. Объекты` was meant to capture** (10 objects,
none linkable, and the existing rule for it is dominated by name-substring false positives —
a hostel and a jewellery shop), and **whether the survey recorded list membership or object
identity** — the two rows carrying `category_orig = Точки продажи табака` with
`type_orig = Магазин алкоголя` suggest the former, which is what makes seven binary targets
the right shape on the data's own terms.

### 8.2 For the contractor

**What is the grocery layer?** 725 of its 1,711 coordinates are absent from the city export,
concentrated in the types that turned out to be partly rubbish bins (S1). Is the remainder a
genuine coverage extension the export missed, or an artefact of a different geocoding pass?
And **are more layers coming?** Two arrived on 2026-09-05, after the library was written.

### 8.3 For the client, when the work resumes

- **Which error is worse, per class?** Health-infrastructure accessibility wants recall (a
  missed pharmacy is a hole in the map); risk-factor density wants precision (a false alcohol
  shop inflates a risk index). The two cannot be optimised together across seven heads.
- **Do the six unbenchmarked okrugs get numbers?** 1,649 objects, 22.7 % of the city, with no
  held-out evidence of any kind. Ship with `extrapolated=True`, suppress, or aggregate only.

---

## 9. Verdict

**Not fit to ship as "seven calibrated multi-label probabilities for 7,263 objects."**

**Fit to ship as "a validated rule over the 2022 taxonomy, a bounded assessment of what a
learned model adds, and a prioritised review queue"** — which is what the evidence supports,
and what this repository has been pointing at all along: alcohol is better served by the
FSRAR registry across all nine okrugs, and tobacco has no benchmark anywhere.

If the quality gates of §6 fail for Alcohol and Tobacco while passing for Medical, Catering
and Grocery, that is a legitimate deliverable and the remaining effort should go into the
report rather than into further modelling.

---

## 10. Re-check, 2026-09-15: the verdict challenged

The verdict of §9 was re-tested against the data rather than against this document. **It
survives.** Three of the statements supporting it do not, and §4's proposed replacement
deliverable is not shippable as written. Probes: `docs/classifier/probes/q1.py` … `q6.py`.

### 10.1 "Every labelled row is a row the free rule already gets right" is false

[verified, `q1.py`] The rule applied to *export* features and scored against the 2022 label
on the 1,133 linked rows (`tier ∈ {exact, probable}`) is right on 1,037 and **wrong on 96** —
accuracy 0.915.

| class | n labelled | tp | fp | fn | P | R |
|---|---:|---:|---:|---:|---:|---:|
| Medical | 321 | 315 | 1 | 6 | 0.997 | 0.981 |
| Catering | 402 | 381 | 8 | 21 | 0.979 | 0.948 |
| Grocery shops | 258 | 215 | 17 | 43 | 0.927 | 0.833 |
| Sport | 79 | 69 | 1 | 10 | 0.986 | 0.873 |
| Alcohol shops | 57 | 47 | 6 | 10 | 0.887 | 0.825 |
| Tobacco outlets | 16 | 10 | 0 | 6 | **1.000** | **0.625** |
| Industrial | 0 | — | — | — | — | — |

Two corrections to §2.4, which quoted "P 0.91–1.00 at recall 0.81–0.99": alcohol precision is
**0.887**, below the stated floor, and **tobacco recall is 0.625** (10 of 16), far below it.
The band was read off the classes with enough rows to have one.

The residual is real but not learnable. All 96 errors decompose:

| block | n | what it is |
|---|---:|---|
| join artefacts | ~30 | Medical→Grocery ×5 is five `Магнит` rows — the benchmark's *аптека* was linked to the supermarket next door. Sport→Other ×10 is a stadium linked to its school, a `Спорткомплекс` linked to a hotel. Catering→Other ×15 is a `столовая` linked to the university, college or hotel containing it. The export does not hold these objects at all; no classifier reaches them. |
| co-membership scored as error | ~20 | Alcohol→Grocery ×9 is nine `Бристоль` rows typed `Продуктовый магазин`; Tobacco→Catering ×5 is five hookah lounges typed `Кафе`. Both labels are true on both. A single-label metric must call one wrong. |
| one missing string | 28 | `Овощи и фрукты` — see D1 below. |
| singletons | ~18 | one each, no pattern. |

§3.1's conclusion therefore stands on a better argument than the one it gives: the residual is
not rows a model could win, it is rows the join lost, the metric mis-scores, or a constant
misses.

### 10.2 The ceiling is measured on 15.6 % of the data, at its easy end

[verified, `q1.py`] 1,133 of 7,263 rows carry a label, and rule accuracy tracks link quality:
**0.925 on `exact` (n = 1,083) against 0.700 on `probable` (n = 50)**. Every linked row has
`name_sim ≥ 0.6`; the 620 benchmark rows that reached only `gps_only` or `unmatched` are
unmeasured, and they are precisely the rows whose names did not survive four years.

§4 proposes this per-class table as "the headline validation". As written it will be read as a
city-wide guarantee. It is a 15.6 % sample drawn by a procedure whose selection correlates
with the outcome being measured.

### 10.3 Where the rule does fail, it fails on the unmeasured 84 %, and definitionally

2.5 is confirmed first: all 185 `type_orig` values landing in `Other` and all 1,889 rows
carrying a Latin OSM tag were enumerated [`q3.py`, `q4.py`]. There is no hidden alcohol,
tobacco, supermarket or pharmacy mass there — the slice is genuinely outside the taxonomy.
One exception, and two definitional defects:

**D1 — `Овощи и фрукты` recodes to `Other`, 51 objects.** [verified] `GROCERY_TYPES` holds
`фрукты-овощи`, the 2022 spelling; the 2026 export writes the two words in the other order,
and `t.isin(GROCERY_TYPES)` is exact equality. Grocery city-wide **811 → 862**. This is the
third member of the family `CLAUDE.md` already documents — the `GROCERY_TYPES` case mismatch
and `табак` vs `табач-` — and the only one still live.

**D2 — about 30 % of the `Sport` class is not a sport facility.** [verified, `q5.py`] Of 358
objects: **63 saunas** (`type_orig = Досуг: sauna`), which enter only because their
`category_orig` is `Досуг и спорт` and the rule tests the blob for the stem `спорт` — the 2022
benchmark labels a sauna `Общепит`; **20 `Спортивный магазин`**, shops rather than facilities;
and ~25 name-substring hits (`Госучреждение` 9, `Офис: company` 5, `Школа` 3, `Полиция` 1, a
mall, a ticket office, a lottery kiosk). Same defect as the documented `Industrial` one, but
`Sport` is a headline health-access class and is reported per okrug.

**D3 — 35 rows of the export carry the wrong `type_orig`.** [verified, `q6.py`;
**corrected 2026-09-15 — see below**] `np.select` resolves in priority order with Tobacco
first, so every `Продуктовый магазин` carrying `category_orig = Точки продажи табака` left the
Grocery count. Grocery's boolean marginal is 846; its post-priority count is 811.

**Correction.** The reading above — 35 grocery shops made invisible by the priority order
— is wrong, and building the seven-flag rule is what exposed it. The 35 rows' names settle
what they are: Азбука дыма, SmokeArh (табачная лавка), Дымный папа, Kiss My Vape,
Oblako (магазин дымной продукции). They are tobacco and vape shops whose `type_orig` is
wrong, never groceries. The old rule's priority order returned the right answer for them
**by accident**, and that is exactly what kept the defect hidden: it is a defect in the
export's `type_orig`, not in the recoder.

`taxonomy_2022.py` restores the right answer through the evidence hierarchy it already
declares — where `category_orig` exactly names one of the seven classes, that assertion
outranks anything inferred from `type_orig` or the fascia. Grocery city-wide is therefore
**867**, not the 902 the uncorrected flags gave, and the defect is now visible rather than
masked: 35 export rows are known to carry a wrong type, and the review queue holds them.

None of these is statistical. A model trained on the 1,133 labelled rows inherits all three,
because the labels encode the same definitions.

### 10.4 The multi-label deliverable fails on the input, not on the sample size

[verified, `q6.py`] Evaluated as seven independent booleans rather than through `np.select`,
the rule's own predicates put two or more classes on **47 objects in the whole city — 0.6 %** — and once the evidence hierarchy of D3 is applied, on **2 objects in 7,263**, both a grocery that is also a snack bar:
Tobacco × Grocery 35, Grocery × Industrial 5, Catering × Industrial 3, four singletons. The v4
layers imply on the order of 560 grocery × tobacco sites.

The export's features do not encode co-membership at all. Nothing in `category_orig`,
`type_orig` or `name_orig` states that a `Продуктовый магазин` sells tobacco; only the
contractor's risk layers and the licence registry state it, and decision 1 excludes the former
while the latter covers alcohol only.

This is a stronger claim than §3.3. The seven-column deliverable is unreachable regardless of
label count, model class or calibration method, **because the information is not in the
inputs**. More labelling would not fix it, and a GPU certainly would not.

### 10.5 What this changes

- **2.4 and §3.1 keep their conclusion and lose their wording.** The rule is not error-free on
  the labelled rows, and its quoted P/R band is wrong at the bottom; its errors are simply not
  of a kind a model can win.
- **§4's first bullet is not yet a product.** The corrected rule needs D1–D3 fixed, and its
  validation restated as covering 15.6 % of the city at the easy end, before it can be the
  headline.
- **§7's audit no longer depends on a model.** Stratify by the rule's output over the
  unlabelled 84 % instead of by model probability and it is runnable immediately — and it is
  the only instrument in this repository that reaches the definitional errors of §10.3, which
  are now the main open risk, ahead of classifier accuracy.
- **§8.1 gains a second question for the 2022 authors:** does `Спортивные объекты` include
  sports shops and saunas? On the benchmark's own evidence it excludes at least saunas.
- **The fix must not land in `v3_common.py`.** D1–D3 move `Grocery shops`, `Sport` and
  `Industrial` city-wide, and three rendered v3 reports carry the current numbers. Follow the
  precedent of `basecheck.py`, `v4_common.py` and `egais.py`: a new module, the old one
  untouched, both re-rendered deliberately.
