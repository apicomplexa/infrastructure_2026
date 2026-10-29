# Design document — evaluation half

Companion to the modelling half. Scope: what is estimated, how it is split, which
numbers are reported, what they can and cannot support, and when the project
should be declared a negative result.

Every number below is either cited from the briefing or computed in this session
from `data/processed/match_2022/match_2022_local.csv`, `data/raw_v4/*.csv`,
`data/processed/egais/egais_licences_arkhangelsk.tsv` and `data/processed/v4_licences/v4_licences.csv`.

---

## 0. The numbers this document is built on

Linkage of the 2022 benchmark (1,753 rows) to a modern export, at 50 m / name ≥ 0.75:

| 2022 class | n | exact | probable | gps_only | unmatched | **linked** | **link rate** |
|---|---:|---:|---:|---:|---:|---:|---:|
| Общепит | 622 | 389 | 13 | 210 | 10 | **402** | **64.6 %** |
| Магазины | 400 | 254 | 4 | 121 | 21 | **258** | **64.5 %** |
| Медицинские организации | 371 | 300 | 21 | 41 | 9 | **321** | **86.5 %** |
| Спортивные объекты | 188 | 67 | 12 | 77 | 32 | **79** | **42.0 %** |
| Спецмагазины алкоголя | 116 | 57 | 0 | 56 | 3 | **57** | **49.1 %** |
| Точки продажи табака | 46 | 16 | 0 | 30 | 0 | **16** | **34.8 %** |
| Пром. Объекты | 10 | 0 | 0 | 6 | 4 | **0** | **0.0 %** |
| **total** | **1,753** | 1,083 | 50 | 541 | 79 | **1,133** | **64.6 %** |

After `recode_2022()` the linked subset is Catering 402, Medical 321,
Grocery 256, Sport 79, Alcohol 57, Tobacco 16, Other 2.

Target population, `..._all.csv`, 7,263 objects by okrug:
Ломоносовский 2,509 · Октябрьский 2,340 · Майская Горка 765 ·
Соломбальский 567 · Варавино-Фактория 440 · Исакогорский 237 ·
Северный 192 · Маймаксанский 144 · Цигломенский 69.
The three benchmarked okrugs hold **5,614 / 7,263 = 77.3 %** of the city's
objects; the six unbenchmarked ones hold **1,649 = 22.7 %**.

---

## 1. The evaluation question, stated precisely

### Estimand

Let `U` be the target population: the 7,263 objects of
`infrastructure_архангельск_2026-08-31_quality_excel_all.csv`.
Let `K` be the seven classes of the 2022 taxonomy. For object *i* and class *k*
let `Y_ik ∈ {0,1}` be the unobserved truth "object *i* belongs to class *k*
today". The deliverable is

> p̂_ik  ≈  P(Y_ik = 1 | X_i),   i ∈ U,  k ∈ K,

seven **marginal** probabilities per object, not a distribution over seven
classes. The quantity to be evaluated is therefore not an accuracy but the
quality of a conditional probability: its **discrimination** (does it order
objects correctly within a class) and its **calibration** (does p̂ = 0.7 mean
70 %).

### What can actually be measured

The measurable sample is `S` = the 1,133 benchmark rows that linked to a modern
export. Three gaps separate `S` from `U`, and they are of different kinds.

**Gap 1 — coverage.** |S| / |U| = 1,133 / 7,263 = **15.6 %**, and `S` lies
entirely inside 3 of 9 okrugs. The okrugs are not the main problem: those three
okrugs contain 77.3 % of the target, and the linked subset's okrug mix is
undistorted (Ломоносовский 44.3 % of the benchmark → 43.9 % of the linked subset;
Октябрьский 41.6 % → 42.5 %; Майская Горка 14.1 % → 13.6 %). The problem is the
class mix — see Gap 3.

**Gap 2 — the label is four years old and was transported by a match.** `Y` is
not observed. What is observed is `L_ik` = "the 2022 study assigned class *k* to
an object that a 50 m / name ≥ 0.75 match associates with modern object *i*".
So the model estimates `P(L = k | X)`, and every number in this document is
about `L`, not `Y`. Between the two sit (a) four years of business turnover and
(b) the match itself, whose own error rate is unmeasured. The evidence that this
gap is large rather than academic is in Gap 3's mechanism.

**Gap 3 — the non-linkage is not random.** Of the 620 non-linked rows, only
**79** have no candidate within 50 m and only **2** have broken coordinates.
The other **541** are `gps_only`: a modern object *is* at that door —
median `addr_sim` **0.95** — but its name does not agree, median `name_sim`
**0.444** (IQR 0.35–0.49). These are not geocoding failures. They are addresses
where the 2022 occupant is no longer the 2026 occupant, or where the 2026
export never carried that occupant. Loosening the match does not recover them:
the existing sensitivity ladder moves recall from 64.6 % (50 m / 0.75) only to
**70.9 %** (150 m / 0.75) — tripling the radius buys 110 rows out of 620. The
loss is structural.

**Prevalence shift.** Benchmark prevalence of Tobacco is 46/1,753 = 2.6 % and of
Alcohol 116/1,753 = 6.6 %. In the target, the v4 layers imply roughly
749/7,263 = **10.3 %** and 945/7,263 = **13.0 %**. A one-vs-rest probability is
prevalence-dependent by construction, so a model calibrated on `S` is
**miscalibrated on `U` by a factor of ~4 on the tobacco prior** before any
modelling error. Either prior-correct explicitly (and say what prior was assumed)
or state that the probabilities are calibrated to the 2022 benchmark's
prevalence and not to the city's.

### Consequence to write on the first page of the report

The project can estimate `P(2022 label = k | 2026 features)` on objects that
survived 2022→2026 as recognisably the same business, in three okrugs, for five
classes. Everything beyond that — today's truth, the six other okrugs, the
tobacco class, the industrial class, and any joint statement about two classes at
once — is extrapolation and must carry that word.

---

## 2. Splitting protocol

### Group key

Rows are not independent. Three candidate dependencies, measured on the 1,133
linked rows:

| grouping | groups | largest group | note |
|---|---:|---:|---|
| normalised address (`norm_address`) | 687 | 17 | mean 1.65 rows/group |
| building (coords at 4 dp ≈ 11 m) | 1,089 | 3 | too fine — splits one mall's units |
| chain (`norm_name`) | 659 | 59 | 374 rows sit in chains of ≥ 5 |
| okrug | 3 | 497 | see below |

**Decision: group by building**, defined as the connected components of
(same normalised address) ∪ (coordinates within 25 m). This is between the two
geometric keys above and lands near **700 groups, mean 1.6 rows, max ~17**. It is
the leakage that matters: two units behind one door share address tokens,
coordinates, every neighbourhood feature, and usually part of the name.

**Chain is deliberately *not* a grouping key for the headline.** The target
population contains the same chains as the benchmark (Магнит, Пятёрочка,
Бристоль …), so chain-level generalisation is not required for the deliverable,
and grouping on chain would remove the model's ability to learn a chain effect
that is genuinely available at inference time. Instead run **one secondary
evaluation grouped by chain**, restricted to the 374 rows in chains of ≥ 5, and
report it separately as "unseen-fascia robustness". If that number collapses
relative to the headline, the model is a chain lookup table and should be
described as one.

### Number of folds and per-fold sizes

**5-fold `StratifiedGroupKFold`, repeated 5 times with different seeds (25 fits).**
At n = 1,133 every fit is seconds; the repeats are the cheapest available
variance reduction for the small classes. Report the mean over repeats and the
seed-to-seed spread as a separate variance component (§5).

Expected positives per fold:

| class | linked positives | per fold (5-fold) | evaluable per fold? |
|---|---:|---:|---|
| Catering | 402 | 80.4 | yes |
| Medical | 321 | 64.2 | yes |
| Grocery | 256 | 51.2 | yes |
| Sport | 79 | 15.8 | pooled out-of-fold only |
| Alcohol | 57 | 11.4 | pooled out-of-fold only |
| Tobacco | 16 | **3.2** | **no** — pooled only, and barely |
| Industrial | **0** | **0** | **no — the class cannot be evaluated at all** |

Two rules follow directly.

- **No per-fold metric is ever reported.** Fold-level PR-AUC with 3 positives is
  noise. All metrics are computed **once on the pooled out-of-fold predictions**
  over all 1,133 rows; folds exist only to keep the predictions honest.
- **`Пром. Объекты` is dead on arrival.** 10 objects in the benchmark, **0 of
  them linkable**, no external source. There are no training rows and no
  evaluation rows. See §9.5 — the recommendation is not to emit the column.

### Held-out okrug split

Mechanically feasible — 497 / 482 / 154 linked rows — but not usable as the
primary protocol. Leave-one-okrug-out fold sizes by class (linked rows):

| class | Ломоносовский | Октябрьский | Майская Горка |
|---|---:|---:|---:|
| Общепит | 215 | 147 | 40 |
| Медицинские | 131 | 158 | 32 |
| Магазины | 92 | 110 | 56 |
| Спортивные | 27 | 35 | 17 |
| Спецмагазины алкоголя | 23 | 27 | **7** |
| Точки продажи табака | **9** | **5** | **2** |

**Decision: run leave-one-okrug-out once, as a transportability diagnostic, and
report it only for Catering, Medical and Grocery.** Held out on Майская Горка,
the alcohol class has 7 positives and tobacco 2; any metric there is
uninterpretable. This diagnostic is the only direct evidence available about
spatial transportability, so it must be run — but it answers "does the model
survive a change of okrug for the three common classes", nothing more.

### Nested loop for calibration + model selection

On ~1,133 rows a three-way split (train / calibrate / test) wastes too much data.
The protocol:

```
outer: 5-fold grouped (StratifiedGroupKFold on building groups)
  outer-train ≈ 906 rows, outer-test ≈ 227 rows
  inner: 4-fold grouped on the outer-train only
    (a) hyperparameter search — select by mean inner PR-AUC
    (b) with the selected hyperparameters, collect inner out-of-fold
        scores over all 906 outer-train rows
    (c) fit the calibrator (isotonic or Platt) on those 906 OOF scores
    (d) refit the base model on all 906 outer-train rows
  apply (d) then (c) to the 227 outer-test rows -> store calibrated OOF probs
pool the 1,133 calibrated out-of-fold probabilities -> all metrics
```

This is `CalibratedClassifierCV(..., cv=inner, ensemble=False)` semantics. The
calibrator never sees the outer-test fold; the hyperparameter search never sees
it either. Cost: 5 × 4 × |grid| fits per repeat. Keep |grid| ≤ 12 — with 906 rows
and 6 evaluable classes, a larger grid buys selection noise, not accuracy.

**Isotonic vs Platt by class size.** Isotonic needs roughly ≥ 100 positives to
avoid fitting steps into noise. Use **isotonic for Catering / Medical /
Grocery**, **Platt (sigmoid) for Sport / Alcohol**, and for **Tobacco fit
nothing meaningful** — apply the Platt fit but report that it rests on 16
positives and is not evidence of calibration (§4).

### Leakage specific to this repository

The `общепит` and `продуктовые магазины` layers arrived after
`v4_common.load_v4()` was written, and membership in a typed layer is a
near-perfect predictor of the corresponding 2022 class. If layer membership is a
feature, the evaluation measures agreement between the contractor's labels and
the 2022 study, not model generalisation.

**Decision: build two feature sets and evaluate both.**
(A) with layer-membership features, (B) without. **The headline uses (B).**
Reason beyond leakage: the layers do not join cleanly onto `_all.csv`. Exact
coordinate agreement with `_all.csv` is tobacco 644/748 = 86 %, alcohol
808/945 = 86 %, catering 541/566 = 96 %, **grocery 955/1,640 = 58 %** — so a
layer-membership feature is itself a noisy, radius-dependent join, and its value
differs systematically between the benchmark region and the rest of the city.
Report (A) − (B) as the measured size of the contractor-label shortcut.

---

## 3. Metrics

### Primary

**Per-class PR-AUC (average precision) on the pooled out-of-fold probabilities,
macro-averaged over the five evaluable classes** (Catering, Medical, Grocery,
Sport, Alcohol) — with a hard calibration gate (§4) that a class must pass
before its probability ships as a probability.

Two numbers, one score and one gate, because the deliverable is a probability:
discrimination alone would let a well-ordering but badly-scaled model pass, and
calibration alone would let a model that predicts the base rate for everything
pass with a perfect reliability curve.

### Why PR-AUC and not ROC-AUC

At these prevalences ROC-AUC is not informative. Tobacco is 16/1,133 = 1.4 %
positive and Alcohol 57/1,133 = 5.0 %; ROC-AUC integrates over a false-positive
axis whose denominator is 1,117 and 1,076 negatives respectively, so a model can
show ROC-AUC 0.92 while precision at every usable threshold is under 0.2.
PR-AUC's baseline is the prevalence itself, which makes the useful report:

| class | positives | prevalence = PR-AUC baseline |
|---|---:|---:|
| Catering | 402 | 0.355 |
| Medical | 321 | 0.283 |
| Grocery | 256 | 0.226 |
| Sport | 79 | 0.070 |
| Alcohol | 57 | 0.050 |
| Tobacco | 16 | 0.014 |

Always report **PR-AUC and PR-AUC / baseline (the lift)** side by side. A
tobacco PR-AUC of 0.20 is a 14× lift and a catering PR-AUC of 0.60 is a 1.7×
lift; the raw numbers invert the ranking.

ROC-AUC is still worth computing once, for the three common classes only, as a
prevalence-independent comparison against the leave-one-okrug-out diagnostic
where prevalence differs between folds.

### Macro vs micro

**Macro, over the five evaluable classes, and per class always shown.** Micro
averaging is dominated by Catering + Medical + Grocery, which are 979 of the
1,133 linked rows (**86.4 %**) — exactly the classes the study is not worried
about. Report micro once, explicitly labelled "not the target", so a reader who
computes it independently gets the same number.

Also report an **unweighted per-class table**. The macro number is a summary for
a contract; every substantive claim in the report should cite a per-class row.

### Threshold-free evaluation, and the threshold the client will apply anyway

The deliverable is a probability, so no threshold is baked into the artefact and
no F1 is reported as a headline — F1 silently fixes a threshold at 0.5, which
is arbitrary under a 4× prevalence shift between benchmark and target.

But the client will threshold it. So ship, per class, a **threshold–yield
table** computed on the pooled out-of-fold predictions:

| p ≥ | precision | recall | n selected in S | implied n selected in U (7,263) |
|---|---|---|---|---|
| 0.3 / 0.5 / 0.7 / 0.9 | … | … | … | … |

The last column is the one the client reads, and it must carry the §1 prevalence
caveat: the implied count assumes the target's class prior equals the benchmark's,
which for tobacco it does not.

---

## 4. Calibration assessment

### Reliability curves

**Quantile (equal-count) bins, never equal-width.** Equal-width bins put 95 % of
the tobacco predictions in the first bin and leave the rest empty.

Bin counts, driven by n = 1,133 and the positive count:

| class | positives | bins | rows/bin | positives/bin | a bin readable to |
|---|---:|---:|---:|---:|---|
| Catering | 402 | 10 | 113 | ~40 | ± 9 pp |
| Medical | 321 | 10 | 113 | ~32 | ± 9 pp |
| Grocery | 256 | 10 | 113 | ~26 | ± 8 pp |
| Sport | 79 | 5 | 227 | ~16 | ± 3 pp |
| Alcohol | 57 | 5 | 227 | ~11 | ± 3 pp |
| Tobacco | 16 | — | — | — | **not assessable** |

(The last column is 1.96·√(p̄(1−p̄)/n_bin) at the bin's own observed rate — the
resolution of a single point on the curve, before any multiple-testing
correction across bins.)

For Sport and Alcohol, five bins is the floor: with four the curve cannot show
non-monotonicity, and with ten the per-bin standard error (~± 5 pp at p̄ = 0.07)
exceeds the miscalibration worth detecting.

### Brier score with the Murphy decomposition

Report per class: **BS = reliability − resolution + uncertainty**, and the skill
score 1 − BS/uncertainty, where uncertainty = p̄(1−p̄) is the score of the
"always predict the base rate" model:

| class | p̄ | uncertainty = BS of the trivial model |
|---|---:|---:|
| Catering | 0.3548 | 0.2289 |
| Medical | 0.2833 | 0.2031 |
| Grocery | 0.2260 | 0.1749 |
| Sport | 0.0697 | 0.0649 |
| Alcohol | 0.0503 | 0.0478 |
| Tobacco | 0.0141 | 0.0139 |

This table is why a raw Brier score must never be quoted alone: a tobacco model
that predicts 0.0141 for every object scores BS = 0.0139 and looks superb. The
**skill score** and the **resolution term** are the informative quantities; the
reliability term is what the calibrator is supposed to drive to zero.

### ECE, and its bias

ECE with 10 equal-count bins is **positively biased at n = 1,133** — a perfectly
calibrated model still scores roughly 0.02–0.03 purely from binning noise, and
the bias grows with bins/n, so a rare class's ECE is biased worst.

**Do not report a bare ECE.** Report ECE against a simulated null:

1. take the model's predicted probabilities p̂_i on the 1,133 rows;
2. simulate labels ỹ_i ~ Bernoulli(p̂_i), 1,000 times — this is a perfectly
   calibrated world by construction;
3. compute ECE each time; the 95th percentile is the "no evidence of
   miscalibration" threshold for this n, this binning and this score
   distribution.

Report ECE and that threshold together. This costs seconds and removes the
single commonest way to over- or under-claim calibration.

### What cannot be assessed at these sample sizes — state it in the report

- **Tobacco calibration.** 16 positives. No binning yields a bin whose observed
  frequency has a standard error under ~5 pp. Report the tobacco score
  distribution and the §6 bound; report no reliability curve, no ECE, no Brier
  skill.
- **Industrial, anything.** 0 linked positives.
- **The upper tail, p̂ > 0.9, for any class with < 100 positives.** There will not
  be enough high-scoring examples to populate a top bin, and the top bin is
  exactly where a client acting on the output will threshold.
- **Calibration in the six unbenchmarked okrugs.** No labels exist there at all;
  §7 covers what can substitute, and it is much weaker than calibration.
- **Joint (multi-label) calibration.** No multi-label training data — §8.

---

## 5. Uncertainty

### Which bootstrap

**Cluster (grouped) bootstrap over the building groups of §2 — resample groups
with replacement, not rows.** Rows inside a building are dependent (shared
address, coordinates, neighbourhood features, often name tokens); a row-level
bootstrap would understate every interval. Resample the ~700 building groups,
take all rows of each drawn group, recompute the metric on the pooled
out-of-fold predictions.

**No stratification on the label.** Stratifying the resample so that each replicate
contains exactly 16 tobacco positives would suppress precisely the variance that
makes the tobacco estimate untrustworthy. The interval must show it. (Empty-class
replicates are not a practical risk: the 16 tobacco positives sit in ~16 distinct
groups, so a replicate containing none is vanishingly unlikely; the count will
nevertheless swing roughly 8–25 across replicates, which is the honest picture.)

**B = 2,000 resamples**, percentile interval. B = 1,000 is defensible; 2,000
costs nothing here and halves the Monte-Carlo error on the 2.5 % quantile.

### What the interval does and does not contain

Bootstrapping the pooled out-of-fold predictions captures **sampling variance of
the evaluation set**. It does not capture **model-fitting variance** (which rows
landed in which fold, which hyperparameters were selected). Re-running the full
nested CV inside each of 2,000 resamples is 2,000 × 25 fits and is not worth it.

**Decision: report two components.**
1. the grouped bootstrap percentile CI (evaluation-set variance), and
2. the **min–max spread of the metric across the 5 CV repeats** (fitting
   variance), quoted as a separate "± seed spread" figure.

If (2) is comparable to (1), the model is unstable and the headline must say so.

### Reporting format

Per class, one line:

> `Alcohol: PR-AUC 0.41 (95 % CI 0.29–0.54, grouped bootstrap over ~700 building
> groups, B = 2,000); baseline 0.050; lift 8.2×; seed spread ±0.03; n = 57
> positives of 116 in the benchmark class (§6 bound: …).`

### A-priori interval widths

The design effect from clustering is DE ≈ 1 + (m̄ − 1)·ρ with mean cluster size
m̄ = 1,133/687 = **1.65**; at a plausible intra-building correlation ρ ≈ 0.3 that
is DE ≈ 1.20, i.e. the SE is ~10 % wider than a naive binomial. Half-widths of
the 95 % interval on **recall**, computed as 1.96·√(r(1−r)/n_pos)·√DE:

| class | positives used | assumed recall | ± half-width |
|---|---:|---:|---:|
| Medical | 321 | 0.90 | **± 3.6 pp** |
| Catering | 402 | 0.85 | **± 3.8 pp** |
| Grocery | 256 | 0.80 | **± 5.4 pp** |
| Sport | 79 | 0.70 | **± 11.1 pp** |
| Alcohol | 57 | 0.75 | **± 12.4 pp** |
| *a class with 46 positives* | 46 | 0.75 | **± 13.8 pp** |
| *the same at r = 0.90* | 46 | 0.90 | **± 9.5 pp** |
| Tobacco, as actually available | **16** | 0.75 | **± 23.2 pp** |

**Answering the question directly**: a class with 46 positives resolves recall to
about **± 14 pp**. That distinguishes "recall 0.75" from "recall 0.95" and
nothing finer — it cannot separate 0.75 from 0.85. And the tobacco class does not
in fact have 46 usable positives: it has 46 in the benchmark and **16 that link
to a modern export**, so the achievable precision is **± 23 pp** — an interval
running roughly 0.52–0.98, which supports no claim whatever.

For scale: reaching ± 5 pp on tobacco recall would need
n = r(1−r)·(1.96/0.05)² ≈ **288 positives**. There are 16.

---

## 6. Sampling bias, quantified

### The measured distortion

Linkage is strongly class-dependent (§0): Medical **86.5 %**, Catering 64.6 %,
Магазины 64.5 %, Alcohol **49.1 %**, Sport **42.0 %**, Tobacco **34.8 %**,
Industrial **0 %**. The training set is therefore enriched in exactly the classes
nobody is worried about and depleted in every risk class the study exists to
measure.

The distortion also runs **inside** classes, which is the more damaging half.
Link rate by `type_orig` (types with n ≥ 15):

| best-linked types | rate | worst-linked types | rate |
|---|---:|---|---:|
| многопрофильные КДЦ (27) | 96.3 % | Спортивная площадка (50) | **20.0 %** |
| аптека (168) | 91.7 % | Спортивные секции (35) | 25.7 % |
| Супермаркет (147) | 86.4 % | Стадион (27) | 25.9 % |
| Спорткомплекс (38) | 84.2 % | столовая (43) | 27.9 % |
| Фрукты-овощи (35) | 80.0 % | Магазины табака (44) | **34.1 %** |
| стоматологическая клиника (81) | 79.0 % | Продуктовый магазин (204) | **48.5 %** |
| фастфуд (126) | 77.0 % | Магазин алкоголя (118) | **49.2 %** |

Read the Sport column: the model will be trained on **indoor commercial sport**
(Спорткомплекс 84 %, Фитнес-центр 71 %) and applied to a city where outdoor
pitches, stadiums and sections — 112 of the 188 benchmark sport objects — are
almost entirely absent from training (20–26 % linked). Read the Grocery column:
`Супермаркет` links at 86 % and `Продуктовый магазин` at 49 %, so the grocery
model learns "supermarket" far better than "corner shop".

A third axis: **multi-tenant sites are under-represented.** Link rate at
coordinates carrying a single benchmark row is **0.703**; at coordinates shared
by more than one benchmark row it is **0.362** (120 such coordinates). Malls,
market halls and business centres — where an object most plausibly carries two
classes at once — are the least likely to be in training. This is the same
population §8 is about.

The one axis that is **not** distorted is okrug (44.3/41.6/14.1 → 43.9/42.5/13.6).
No okrug reweighting is needed.

### What this does to every number computed on the matched subset

Each per-class metric is conditional on linkage, and linkage correlates with
label and with type-within-label. A recall of 0.80 for Sport means "0.80 among
indoor commercial sport facilities that survived to 2026 under the same name",
not "0.80 among sport objects".

### Correction 1 — inverse-linkage-propensity weighting

Fit a linkage-propensity model π̂_i = P(linked | Z_i) on **all 1,753** benchmark
rows, using only covariates available for linked and unlinked rows alike:
2022 `category_orig`, 2022 `type_orig`, okrug, number of benchmark rows at the
same coordinate, local object density, name length and a generic-name flag.
Train and evaluate with weights 1/π̂_i. Class-level weights implied by §0:

| class | link rate | weight 1/π̂ |
|---|---:|---:|
| Medical | 0.865 | 1.16 |
| Catering | 0.646 | 1.55 |
| Магазины | 0.645 | 1.55 |
| Alcohol | 0.491 | 2.04 |
| Sport | 0.420 | 2.38 |
| Tobacco | 0.348 | 2.87 |

Weights top out near 2.9 — mild enough to be stable, and with `type_orig` in the
model the spread widens to roughly 1.0–5.0 (Спортивная площадка at 20 % → 5.0),
which is still tolerable. Cap at 5 and report the effective sample size
n_eff = (Σw)²/Σw² alongside every weighted metric.

**Report weighted and unweighted side by side.** A gap larger than the bootstrap
half-width is itself a finding about the data, and triggers gate §9.4.

**IPW's limit, stated in the report:** it is valid only if linkage is independent
of the label given the covariates. Here linkage failure is substantially driven
by *turnover*, which is unobserved. IPW corrects the composition of the training
set; it cannot correct the fact that surviving businesses differ from
non-surviving ones. Do not present a weighted number as unbiased.

### Correction 2 — worst/best-case bounds (this is the honest headline)

For each class, bound the recall over the **full 2022 class**, not the linked
subset, by assuming the unlinked rows are all wrong (worst) or all right (best):

`worst = n_linked·r / n_total`,  `best = (n_linked·r + n_unlinked) / n_total`.

The width of the bound is exactly `1 − link rate` and does not depend on `r`:

| class | linked/total | assumed r | bound on class recall | **bound width** |
|---|---:|---:|---|---:|
| Medical | 321/371 | 0.90 | **[0.78, 0.91]** | 13.5 pp |
| Catering | 402/622 | 0.85 | [0.55, 0.90] | 35.4 pp |
| Магазины/Grocery | 258/400 | 0.80 | [0.52, 0.87] | 35.5 pp |
| Alcohol | 57/116 | 0.75 | [0.37, 0.88] | 50.9 pp |
| Sport | 79/188 | 0.70 | [0.29, 0.87] | 58.0 pp |
| **Tobacco** | 16/46 | 0.75 | **[0.26, 0.91]** | **65.2 pp** |
| Industrial | 0/10 | — | **[0.00, 1.00]** | 100 pp |

**This table should appear in the client report before any point estimate.** It
says, without any modelling assumption, that Medical is measurable, Catering and
Grocery are roughly measurable, and Alcohol, Sport and Tobacco are bounded so
loosely that a point estimate for them is a presentation choice, not a finding.

---

## 7. Extrapolation to the six unbenchmarked okrugs

### What is actually at stake

1,649 objects, 22.7 % of the target: Соломбальский 567, Варавино-Фактория 440,
Исакогорский 237, Северный 192, Маймаксанский 144, Цигломенский 69. This is
smaller than the phrase "six of nine okrugs" suggests, and saying so is part of
an honest report.

### What EGAIS can bound — precisely one thing

The FSRAR registry covers all nine okrugs. Active licences, by class and okrug
(okrug recovered by `egais.assign_okrug`):

| okrug | active off-trade | active retail incl. on-trade |
|---|---:|---:|
| Октябрьский | 127 | 172 |
| Ломоносовский | 106 | 179 |
| Майская Горка | 50 | 56 |
| Соломбальский | 46 | 51 |
| Варавино-Фактория | 33 | 39 |
| Исакогорский | 27 | 27 |
| Северный | 23 | 23 |
| Маймаксанский | 18 | 18 |
| Цигломенский | 12 | 12 |
| **total** | **442** | **577** |

In the six unbenchmarked okrugs there are **159 active off-trade licences**.

**The bound EGAIS supports:** *recall of the Alcohol class, off-trade only,
restricted to licensed premises, measurable separately in each of the nine
okrugs.*

Concretely — the indirect validation to run:

1. Score all 7,263 objects; keep `p_alcohol`.
2. Use the existing join (`src/arkhinfra/v4_egais.py`, already validated —
   97.7 % of the 442 active off-trade licences have a v4 object at their address)
   to attach each active off-trade licence to the object at its door.
3. On that label-complete subpopulation, compute **recall at a fixed threshold,
   per okrug**: of the licensed objects in okrug *o*, what share does the model
   score above τ.
4. Compare the three benchmarked okrugs (283 licences) against the six others
   (159 licences). Report both the difference and a grouped bootstrap CI on it.
   At n = 159 with r ≈ 0.8, the half-width is ± 6.2 pp, so a drop of 10 pp or
   more is detectable and a drop of 5 pp is not.

If step 4 shows no material gap, that is **real, external, all-okrug evidence**
that the alcohol model transports — the only such evidence this project can
obtain.

### What EGAIS cannot bound — say each of these explicitly

- **Precision, for any class.** The registry lists licensed premises; an object
  with no licence at its address is *not* a proven negative. 47 % of registry rows
  have no usable coordinate and are reached by an address-only route, and chains
  register licences at legal rather than trading addresses. Recall on licensed
  premises only.
- **On-trade alcohol.** 135 active licences city-wide with a different denominator.
  Split off-trade from on-trade before any comparison, as CLAUDE.md requires.
- **Tobacco — nothing at all.** The registry has no tobacco class. The 503
  `probable` tobacco rows in `v4_licences.csv` are *alcohol* licences at
  tobacco-tagged addresses; CLAUDE.md already forbids reporting that as a tobacco
  verification rate. Tobacco is barely validatable in the three benchmarked okrugs
  (16 positives) and wholly unvalidatable in the other six. There is no substitute
  source: retail tobacco licensing begins 2026-10-01 and is mandatory only from
  2027-03-01.
- **Medical, Sport, Catering, Grocery, Industrial.** EGAIS is silent.
- **Per-okrug licence counts as exact.** Okrug was recovered for 1,103 of 2,100
  registry rows from coordinates, 866 from the street's modal okrug, 131 not at
  all. A street crossing an okrug boundary is misassigned wholesale. Treat the
  table above as ±1 okrug at the margins.

### A second, weaker check available for all classes and all okrugs

A **covariate-shift diagnostic**, which is a warning light, not a bound. Train a
discriminator to separate the 5,614 benchmarked-okrug objects from the 1,649
others using the model's own feature representation, grouped-CV, and report its
AUC.

- AUC ≈ 0.5–0.6: the six okrugs lie inside the training manifold. Necessary,
  **not sufficient** — it licenses no performance claim, only removes one reason
  to refuse.
- AUC ≥ 0.75: the six okrugs are out-of-distribution in the model's own features;
  the okrug-level claim must be withheld (gate §9.4).

Pair it with a per-okrug report of **mean predicted probability per class**, next
to the same quantity in the benchmarked okrugs. A large shift with no licence-side
confirmation is a red flag, not a result — publish it as a caveat, never as an
estimate.

---

## 8. The multi-label problem

### The size of the hole

Training data is effectively single-label: of 1,656 distinct (name, address)
pairs in the benchmark, **7** carry more than one `category_orig`.

The target is not. Taking the four typed v4 layers and deduplicating on exact
coordinate — 2,611 distinct sites across tobacco, alcohol, catering and grocery:

| appears in … layers | sites |
|---|---:|
| 1 | 1,652 |
| 2 | 633 |
| 3 | 323 |
| 4 | 3 |

**959 of 2,611 typed sites — 36.7 % — are multi-layer.** Pairwise:
tobacco × grocery **560**, alcohol × grocery 329, tobacco × alcohol 358,
alcohol × catering 275, catering × grocery 95, tobacco × catering 3.

So the single commonest real combination in the city, grocery + tobacco, has
roughly 560 instances in the target and **zero** in training. The model has no
information about the dependence between classes; it has seven independently
fitted marginals.

### What would count as evidence the multi-label output is meaningful

Three tests, in increasing cost. The first two need no new labelling.

**Test 1 — non-suppression.** Single-label training teaches a one-vs-rest model
that grocery examples are tobacco-negative. The failure signature is that a high
`p_grocery` *depresses* `p_tobacco`. Test: on the 560 coordinates in both the
grocery and tobacco layers, compare `p_tobacco` against matched controls that are
in the grocery layer only (matched on okrug, chain and object density). If
`p_tobacco` is not elevated on the overlap set, or is *lower*, the multi-label
output is falsified and must not be shipped as multi-label. **This is decisive
and costs an afternoon.** It requires the client to accept using the v4 layers
as an *evaluation* signal while keeping them out of training — a distinction the
client has not yet been asked about, and should be.

**Test 2 — licence co-elevation.** Of the 442 active off-trade licences, most are
held by grocery operators (Тандер, Агроторг, Альбион-2002, Альфа-М). For objects
that are both at an active off-trade licence address and in the grocery layer,
both `p_alcohol` and `p_grocery` should be high simultaneously. External,
independent of the contractor, and covers all nine okrugs.

**Test 3 — the manual exercise**, below, which is the only thing that can produce
an actual multi-label *rate* rather than a consistency check.

### What the team must refuse to claim

- **Any joint probability.** `p̂_alcohol · p̂_grocery` is not P(alcohol ∧ grocery).
  The seven marginals carry no information about their dependence, and the
  dependence is the whole content of a multi-label claim.
- **Any multi-label metric** — subset/exact-match accuracy, Hamming loss,
  multi-label F1, label-ranking average precision. All of them require
  multi-label ground truth; there is none.
- **That the seven numbers form a distribution.** They do not sum to 1 and must
  never be presented as though they might.
- **That the multi-label output is validated** on the strength of Tests 1–2 alone.
  Those tests can falsify it; passing them shows only that the marginals are not
  mutually suppressive.

### The smallest manual labelling exercise that makes the claim testable

**Target precision: ± 10 pp on a per-cell rate** → n = 0.25·(1.96/0.10)² ≈ **96**,
round to 100 per stratum.

**600 objects, 6 strata × 100**, sampled from the 7,263:

| # | stratum | what it tests |
|---|---|---|
| 1 | p_grocery ≥ 0.5 **and** p_tobacco ≥ 0.5 | precision of the commonest co-label |
| 2 | p_grocery ≥ 0.5 **and** p_tobacco < 0.2 | is the model missing grocery+tobacco |
| 3 | p_alcohol ≥ 0.5 **and** p_catering ≥ 0.5 | on-trade co-label |
| 4 | p_alcohol ≥ 0.5 **and** p_catering < 0.2 | off/on-trade separation |
| 5 | p_medical ≥ 0.5 **or** p_sport ≥ 0.5 | single-label control |
| 6 | **simple random sample of all 7,263** | anchors prevalence; without it no stratified cell can be reweighted back to the city, and no city-level multi-label rate can be stated |

Stratum 6 is not optional. Draw it proportionally to okrug, which puts ~23 of the
100 in the six unbenchmarked okrugs — enough to check that nothing is grossly
wrong there, not enough for a per-okrug number.

**Protocol.** All 7 classes marked present/absent per object, from name + address
+ the object's 2GIS/OSM tags + a short web check. One labeller. **10 % (60
objects) double-labelled** for Cohen's κ per class — at n = 60 the SE on κ is
≈ 0.10, which detects κ < 0.6 but cannot separate 0.8 from 0.9; say so rather
than quoting κ to two decimals. Write the labelling rules down *before* starting,
including what counts as "sells tobacco".

**Effort: ~20 hours at 2 min/object, plus ~2 hours for the double-labelled
subset.**

**What 600 buys:** per-cell rates to ± 10 pp; a city-level multi-label prevalence
for the common combinations to roughly ± 4 pp after reweighting; and the first
real evidence that the joint output means anything.

**What 600 does not buy:** anything about Industrial (expected ~10 objects
city-wide → 0–1 in the sample); any per-okrug number for the six unbenchmarked
okrugs; any improvement to *training* — it makes the claim testable, it does not
make the model better.

**Cheaper variant if the client balks:** 200 objects, strata 1, 2 and 6 only.
± 14 pp per cell, tests exactly one combination (grocery × tobacco), ~7 hours.
Present both and let the client choose; a multi-label deliverable with neither is
an untested claim and should be labelled one.

---

## 9. Stopping rules

Each gate is a number and a decision. Evaluate them in this order.

### 9.1 The baseline gate — check this first, before anything else

The repository already contains a free classifier: the corrected string recoder
(`v4_common.recode_2022_v4()` applied to `category_orig` / `type_orig`). Run it on
the 1,133 linked rows and compute its per-class precision and recall.

**If the model does not beat the recoder — and specifically, if it does not beat
it on Alcohol and Sport, the two classes where string rules are known to be weak
— the project has failed and must be reported as a negative result.** A model
that matches a lookup table has produced a more expensive lookup table with worse
provenance. This is the single most important gate, and it is cheap.

### 9.2 Usefulness gate, per class

For each class, find the out-of-fold threshold at which precision reaches 0.70.

- **No threshold reaches precision 0.70** → the class does not ship.
- **Precision 0.70 is reached but recall there is < 0.50** (or its lower CI bound
  < 0.35) → the class ships as a flag for manual review, described as such, not
  as a probability.

A probability nobody can threshold usefully is not a deliverable, and PR-AUC
alone will not reveal this.

### 9.3 Calibration gate, per class

- **ECE after calibration exceeds the simulated null 95th percentile by more than
  2×**, or the reliability curve is non-monotone across its quantile bins →
  the class ships as a **rank score**, renamed accordingly, with the reliability
  curve published. It does not ship as a probability.
- **Brier skill score ≤ 0** (the model is no better than predicting the base rate)
  → the class does not ship at all.

### 9.4 Bias and transportability gates

- **IPW-weighted metric differs from unweighted by more than the bootstrap
  half-width** → that class's headline is the §6 bound, not a point estimate.
- **Covariate-shift AUC between benchmarked and unbenchmarked okrugs ≥ 0.75**, or
  **alcohol licence-side recall in the six okrugs more than 10 pp below the
  three** → the six-okrug output is withheld and reported as unvalidated. The
  three-okrug output may still ship.

### 9.5 Classes to declare dead before modelling starts

- **`Пром. Объекты` — do not produce it.** 10 benchmark objects, **0 linkable**,
  no external source, and CLAUDE.md already records that the class is dominated
  by name-substring false positives (a hostel and a jewellery shop among 25
  objects). Emitting an untrained, unevaluated `p_industrial` column guarantees
  someone will use it. Omit the column; state why in the report.
- **Tobacco — produce it, bound it, never point-estimate it.** 16 linkable
  positives, bound width 65 pp, no external benchmark now or before 2027-03-01.
  Report the §6 bound `[0.26, 0.91]` and the score distribution. Put in writing
  that nothing in this project can verify the tobacco output.

### 9.6 What a negative result looks like, and why it is a legitimate deliverable

If 9.2 and 9.3 pass for Medical, Catering and Grocery and fail for Alcohol and
Tobacco, the correct report is:

> A classifier over the 2022 taxonomy can be built and validated for the three
> high-prevalence health classes, in the three benchmarked okrugs, with the
> bounds of §6. It cannot be validated for the risk classes: alcohol is better
> served directly by the FSRAR licence registry, which covers all nine okrugs
> and is a primary source; tobacco has no benchmark of any kind and should be
> reported as the contractor's inference, not as a measurement.

That conclusion is consistent with what this repository has already established
(the fivefold alcohol undercount, the absent tobacco registry) and is worth more
to the client than seven numbers of unknown quality. Budget for it: if the gates
fail, the remaining effort goes into the report, not into further modelling.
