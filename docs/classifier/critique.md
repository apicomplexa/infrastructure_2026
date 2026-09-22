# Critique of the two-half design document

Reviewer's probes are in `scratchpad/probe/p1..pd.{py,txt}`; every number below was
re-derived in this session through `pixi run python`, not taken from either half.

---

## 0. Verification results — what I re-checked and what stands

The team lead asked me to re-check the load-bearing claims. **Almost all of them are
exactly right.** Do not re-litigate these:

| claim | source | verdict |
|---|---|---|
| `…_all.csv` and `V3_CSV` are byte-identical | ML §0.1 | ✅ md5 `949c075672028e13f212c9aa4c57d5c6` on both |
| `Пром. Объекты`: 0 linked rows | ML §1.4, stats §0 | ✅ all 10 rows are `gps_only` (6) or `unmatched` (4) |
| 45 % of the export has an unseen `type_orig` | ML §3.6 | ✅ 3,271 / 7,263 = 45.0 %; 49 of 218 types seen |
| lookup baseline 96.5 % over 55 % of the city | ML §4.1 | ✅ 96.5 % over 1,133 linked rows; 3,992 / 7,263 = 55.0 % coverage |
| the whole §0 link-rate table (per class) | stats §0 | ✅ every cell reproduces exactly |
| the §6 link-rate table by `type_orig` | stats §6 | ✅ every cell reproduces exactly |
| 1,133 benchmark rows → 1,072 export rows, 61 collisions, 14 multi-class | ML §1.1, §1.5 | ✅ |
| name_sim ≥ 0.99 in 78.9 % / ≥ 0.95 in 82.4 % of training | ML §3.1 | ✅ |
| `gps_only` median name_sim 0.444, addr_sim 0.95 | stats §1 | ✅ |
| 5,614 / 1,649 okrug split; 7 training rows in Varavino-Faktoriya | ML §1.3, stats §0 | ✅ |
| 78 null `adress_orig`, all `Спортивные объекты` | ML §1.2 | ✅ |
| sensitivity ladder: 70.9 % at 150 m, +110 rows | stats §1 | ✅ |
| field coverage (0 % / 0.6 % / 27.2 % / 44.0 % / 93.4 % / 75.7 %, 590 JSON) | ML §2.2 | ✅ |
| `match_distance_meters` 99.5 % at 0, similarity 99.8 % at 1.00 | ML §2.2 | ✅ |
| multi-tenant link rate 0.703 vs ~0.36 | stats §6 | ✅ (I get 0.350 on 118 coords vs their 0.362 on 120 — coordinate rounding, immaterial) |
| the whole §8 multi-label table: 2,611 sites, 1,652/633/323/3, 959 = 36.7 %, tobacco×grocery 560 | stats §8 | ✅ every cell; and **not** contaminated by the junk in §S1 below (0 junk coordinates are multi-layer) |
| grocery layer coordinate overlap ≈ 58 % | both | ✅ 985/1,711 rows = 57.6 % (ML's number), 955/1,640 distinct = 58.2 % (stats' number) — two different denominators, both correct |

**The statistician's half is, numerically, clean.** Every table in §0, §5, §6, §7 and §8
reproduces. Where I disagree with that half it is about inference, not arithmetic, and
there is only one such place (§B4). Effort below is concentrated on the modelling half
and on the two halves' mutual incompatibility.

---

# BLOCKING

## B1. The ML half's grouping key collapses. Its own bound is exceeded eightfold, and its own fallback makes things worse.

ML §3.5 defines the split group as connected components of
(`norm_name` equal) ∪ (`norm_address` equal), and sets a build-time check:
*"largest component ≤ 8 % of rows."*

Measured on the 1,072 training export rows:

| grouping | components | largest | share |
|---|---:|---:|---:|
| **ML §3.5: name OR address** | 278 | **682** | **63.6 %** |
| ML §3.5 fallback: name edge only where count ≥ 3 | 307 | 651 | **60.7 %** |
| name edge only where count < 3, OR address | 558 | 35 | 3.3 % |
| address only | 597 | 16 | 1.5 % |
| **stats §2: address OR coords ≤ 25 m** | 537 | 38 | 3.5 % |
| chain (`norm_name`) only | 651 | 47 | 4.4 % |

The closure runs `Магнит` (47 rows) → every building a Магнит occupies → every other
business in those buildings → their chains → their buildings. 682 of 1,072 rows fuse into
one component.

**Failure scenario.** `StratifiedGroupKFold(5)` on this key cannot produce five usable
folds: one fold holds 682 rows and the other four hold ~97 each. Four of the five outer
"training" sets are ~390 rows. The nested calibration loop of ML §5.3 then fits a
calibrator on ~300 inner-held-out scores for the Alcohol head, which carries 57 positives
total. The metrics will be garbage, and — this is the dangerous part — they will be
*plausible* garbage: PR-AUC will simply look poor, and the team will spend the budget
tuning a model when the splitter is what is broken.

**The stated fallback is backwards.** Restricting the name edge to names occurring ≥ 3
times keeps exactly the chain edges that cause the closure and drops only the harmless
coincidental collisions: 63.6 % → 60.7 %. The correct direction is the opposite
(name edge only for rare names → 3.3 %), which is to say: *do not put chain edges in the
component key at all.*

**Test that settles it.** `probe/p7.py`, already run — the table above. Re-run after any
change to the key and print the largest-component share into `clf2022_metrics.json`, as
ML §3.5 already correctly requires.

**Resolution required before code.** Adopt the statistician's building key
(address ∪ coords ≤ 25 m, 3.5 %) as the split, and handle chains as a *separate
evaluation* rather than an edge — which is what stats §2 says, and which brings us to B2.

---

## B2. The two halves specify different primary splitters, for opposite reasons, and both call their own choice the headline.

* **ML §3.2 / §3.5:** chain membership is *"the worst kind"* of leak, *"because it makes
  the model look ready"*; the chain edge is therefore mandatory in the headline split.
* **Stats §2:** *"Chain is deliberately **not** a grouping key for the headline"*, because
  the same chains are present at inference in the six unbenchmarked okrugs, so chain-level
  generalisation is not required; chain grouping is a *secondary* "unseen-fascia
  robustness" run.

These are not reconcilable by averaging. They are different estimands. 48.1 % of training
export rows share a normalised name with another row (51.4 % on the benchmark side), so the
two protocols will report materially different numbers for the same model, and each half
labels its own number "the headline".

**Failure scenario for the paper.** A reviewer asks what the reported PR-AUC estimates.
Under the ML protocol it is "performance on a chain never seen in training" — which is not
the deployment condition, since Магнит, Пятёрочка and Бристоль are everywhere in all nine
okrugs. Under the stats protocol it is "performance on a new door", which *is* the
deployment condition but is inflated by brand memorisation. Neither half acknowledges that
the other reading exists, so whichever number reaches the client will be defended with the
other half's argument at some point, and the inconsistency is visible in the same document.

**My recommendation** (the design must state one): the statistician is right about the
estimand. Chains genuinely are available at inference, and the deliverable is scoring
*this* city, not a held-out city. Headline = building groups. But ML §3.2's evidence must
survive into the report, because it is real and it is quantified: the chains are not clean
— `магнит` is 53 `Магазины` **and 6 `Медицинские организации`** (Магнит Аптека),
`бристоль` 29 alcohol and 2 shops [verified]. So the chain-grouped run is mandatory, not
optional, and the gap between the two is a reported number.

**Test that settles it.** Run both; if chain-grouped PR-AUC collapses relative to
building-grouped, the model is a brand lookup table and must be described as one
(stats §2 already says this — adopt that sentence).

---

## B3. The negative set's label noise is not "of unknown size". It is measurable with a free rule, and for three of the six modelled classes it is larger than the positive set.

ML §1.3 concedes *"label noise of unknown but non-trivial size"* and moves on. Stats §6
addresses linkage bias on the *positives* (IPW, bounds) but treats the negative pool as
given. Neither measures it. It is cheap to measure: run the corrected
`v3_common.recode_2022()` over the 5,614 export rows inside the three benchmark okrugs and
count how many rule-identified objects of class *k* are about to be trained as negatives
for class *k*.

| class | rule says class *k* (3 okrugs) | labelled positive | **rule-positive, trained as NEGATIVE** |
|---|---:|---:|---:|
| Grocery | 455 | 243 | **254** |
| Medical | 536 | 310 | **234** |
| Catering | 526 | 388 | **160** |
| Sport | 266 | 76 | **200** |
| Alcohol | 83 | 53 | **40** |
| Tobacco | 50 | 15 | **42** |
| Industrial | 13 | 0 | 13 |

Inspected, these are not rule artefacts in the classes that matter:

* **Alcohol** — 36 of the 40 have `type_orig = Алкогольный магазин`, and they include
  **Бристоль**, the chain that supplies 29 of the 57 alcohol positives. The same fascia
  will be labelled 1 on some rows and 0 on others.
* **Tobacco** — 9 × `Табачный магазин` and 7 × `Вейп-магазин` among 42 negatives, against
  **15** positives. The negative set contains roughly as many unambiguous tobacco outlets
  as the positive set contains positives.
* **Grocery** — 148 × `Продуктовый магазин`, 51 × `Булочная`, 20 × `Супермаркет`, plus
  Бристоль / Светофор / Союз.
* **Sport** — 98 × `Спортивная площадка` (a genuine 2022 class, and by stats §6 the
  worst-linked type in the benchmark at 20 %), plus 42 × `Досуг: sauna`, which *is* the
  rule over-firing on the `бассейн` stem. So call it ~130 genuine of 200.

**Failure scenario.** A one-vs-rest L2 logistic regression on char n-grams is being asked
to learn that the string `алкогольный магазин` predicts class Alcohol, while 36 rows
carrying that exact string are labelled 0 against 53 labelled 1. The model will shrink the
coefficient on the single most informative n-gram in the class. Concretely: the model will
be **worse than the free rule on Alcohol, Tobacco and Sport**, and the CV will not reveal
why, because the CV's negatives carry the same noise as the training negatives. This is
also the mechanism that will make stats §9.1 fail — for the right outcome but the wrong
reason, so the team will misdiagnose it.

**Test that settles it.** `probe/p8.py` / `p9.py`, already run. Before any modelling:
publish this table, and decide the policy. The only defensible options are
(a) mask rule-positive-unlabelled cells out of the loss for that head, exactly as ML §1.2
masks `gps_only` — which is the same argument applied to a much larger set; or
(b) accept them as negatives and state in the report that every head's recall is measured
against a negative pool known to contain 40–254 true positives.

Option (a) is consistent with the design's own logic and I recommend it. Note it makes the
effective negative pool smaller and the closed-world assumption weaker, which is honest.

---

## B4. The single most important stopping rule cannot fire. Its stated premise is false on this data, and it compares incommensurable objects.

Stats §9.1: *"If the model does not beat the recoder — and specifically, if it does not
beat it on Alcohol and Sport, **the two classes where string rules are known to be
weak** — the project has failed."*

I ran the recoder against the 2022 truth on the 1,072 training export rows:

| class | precision | recall |
|---|---|---|
| Medical | 0.997 (303/304) | 0.993 (303/305) |
| Catering | 0.995 (367/369) | 0.948 (367/387) |
| **Sport** | **0.985** (66/67) | **0.880** (66/75) |
| Grocery | 0.940 (203/216) | 0.839 (203/242) |
| **Alcohol** | **0.915** (43/47) | **0.811** (43/53) |
| Tobacco | 1.000 (9/9) | 1.000 (9/9) |

Overall agreement 92.5 %.

**String rules are not weak on Alcohol and Sport here — they are the second- and
third-best classes the rule has.** The gate's premise is factually wrong, and the gate as
written will be read as "beat 0.5-ish", when the real bar is P 0.92 / R 0.81 on 53
positives and P 0.99 / R 0.88 on 75.

**Failure scenario.** By the statistician's own §5 table, the 95 % half-width on Alcohol
recall at n = 57 is **± 12.4 pp** and on Sport at n = 79 is **± 11.1 pp**. So the gate
asks whether the model beats 0.811 ± 0.124. Any realistic model lands inside that interval.
The gate therefore cannot fire in either direction: it will neither cleanly pass nor
cleanly fail, and the decision will be made on a point estimate the same document says is
not resolvable. A gate that cannot fire is not a gate.

**Second defect, independent of the first.** `v3_common.recode_2022()` is a single-label
`np.select` with a fixed priority order — tobacco > alcohol > medical > sport > catering >
grocery > industrial. Every object gets exactly one class. The model emits seven
independent probabilities. Comparing them per class systematically penalises the rule on
whichever class sits lower in the priority order (a grocery shop whose name contains
`кафе` is assigned Catering and scores as a grocery false negative), so the baseline's
measured recall is biased **down** for Grocery and Industrial and the gate is
correspondingly **too easy** exactly where the model is weakest. The comparison must be
made against a *multi-label* version of the rule — each of the seven boolean masks
evaluated independently, before `np.select` collapses them — or it is not a comparison.

**Test that settles it.** Rewrite §9.1 as: build the seven boolean masks from
`recode_2022`'s internals, evaluate each as its own binary classifier on the pooled
out-of-fold rows, publish the table above as the bar, and state the gate in terms the CI
can resolve — e.g. *"the model must beat the rule's F1 by more than the grouped-bootstrap
half-width on at least one of Alcohol, Sport, Grocery"*. As written the gate is decorative.

---

## B5. The central premise: the deliverable as specified is not achievable, and the reason is narrower and harder than either half says.

Both halves circle this. Neither states it. Here it is.

The design's case for a learned model rests on ML §3.6 / §4.4: *"45.0 % of export objects
(3,271 of 7,263) have a `type_orig` that never appears in the training block… That is the
single number that decides whether the embedding model in §4.4 earns its dependencies."*
The number is right. **The inference from it is wrong.** I looked at what is in that
slice:

Top unseen types: `Магазин одежды` 307, `Парикмахерская` 226, `Магазин: outpost` 217,
`Автосервис` 151, `Мебельный магазин` 124, `Цветочный магазин` 117, `Госучреждение` 84,
`Почтовое отделение` 77, `Банк` 75, `Автозапчасти` 67, `Зоомагазин` 65, `Магазин обуви` 63,
`Туристическое агентство` 60, `Магазин электроники` 56, `Салон связи` 56…

Applying the free rule to the unseen slice: **3,195 of 3,271 (97.7 %) are `Other`**. Only
76 rows land in any 2022 class, and inspecting those 76, most are the rule over-firing —
`Спортивный магазин` → Sport (20), `Медицинские товары` → Medical (16), `Ювелирный
магазин` and `Хостел` → Industrial, which are the exact false positives CLAUDE.md already
names.

**The 45 % is not a frontier the model can conquer. It is the city's clothing, hairdressing
and car-repair trade, which is genuinely outside the 2022 taxonomy.** There is no hidden
mass of corner shops there — `Продуктовый магазин` is a *seen* type and sits in the other
55 %.

So the model's addressable universe is the 3,992 seen-type rows, and on those the free
`type_orig` lookup already scores 96.5 % and the free keyword rule scores P 0.91–1.00 /
R 0.81–0.99 per class (B4). Put the two facts together:

> **The model's only possible contribution is to correct the rule's errors inside the
> seen-type slice — and those are precisely the rows for which no label exists. Every row
> that carries a label is a row the free rule already gets right.**

That is the honest statement of the problem, and it is worse than "we cannot calibrate
Tobacco". It means the CV metric the whole evaluation half is built around measures the
one thing that does not need measuring.

Three further limits, each individually sufficient to block the deliverable **as specified**:

1. **Multi-label.** The client's stated use case is "a grocery that also sells alcohol and
   tobacco". Training holds **7** genuine co-membership examples (ML §1.5, verified); the
   city holds ~560 grocery × tobacco sites (stats §8, verified). Seven independently fitted
   marginals carry zero information about dependence. No amount of calibration fixes this,
   and stats §8's refusal list is correct and complete.
2. **Two of seven heads are not models.** Industrial has 0 trainable examples; Tobacco has
   16, bound width 65 pp. Both halves agree; they disagree only on whether to emit the
   columns (see S5).
3. **Calibration target.** Stats §1 is right: what is estimated is
   `P(the 2022 survey put this on list k | 2026 features)`, on the subset that survived
   four years under a recognisable name, at 2022 prevalence, in three okrugs. ML §5.5 says
   the same thing in different words. This is defensible in a paper only if it is the
   sentence in the abstract, not a limitation in §6.

**The honest substitute.** The client has accepted the label constraint and I am not
reopening that. But the *shape* of the deliverable can change without touching it:

* Ship the **corrected multi-label rule as the primary product**, with its per-class
  precision/recall table (B4) as the headline validation. It is free, auditable, and
  already at the measurable ceiling.
* Ship the learned model as a **screening score over the rule's residual** — a ranked
  manual-review queue for the objects where rule and model disagree — validated by the
  600-object audit of stats §8, not by CV. This reframes the model as producing *work*
  rather than *numbers*, and the audit sample is the only thing that can measure it.
* For **Alcohol**, use EGAIS directly, as this repository already concludes
  (CLAUDE.md: "Use `data/raw_v4/` for anything alcohol-related"; stats §9.6 says the same).
  The registry covers all nine okrugs and is a primary source; a 57-positive model is
  strictly worse.
* For **Tobacco**, ship the contractor's tag with its provenance and no number, per
  stats §9.5.

If the client insists on seven probability columns, they can be produced — but the
document must say that four of them are a restatement of a keyword rule, one is a rule
with a probability painted on it, one is unvalidatable, and one does not exist.

---

# SERIOUS

## S1. The grocery layer is contaminated with rubbish bins, and the ML half's numbers about it are wrong in the direction that raises a false alarm.

ML §0.2: *"725 of its 1,711 coordinates are **not** in `_all.csv`, concentrated in
`Стационарные рынки и ярмарки` (406) and `Торговые центры` (230)."*
ML §8.5 escalates this to a client question: *"a genuine coverage extension the city export
missed, or artefacts of a different geocoding pass? If the former, the 7,263-object universe
is itself incomplete and the denominator of every rate in this study moves."*

Two errors. First, **406 and 230 are the full type counts, not the absent counts.** The
actual composition of the rows absent from `_all.csv` is
`рынки и ярмарки` 375, `Торговые центры` 113, `Продуктовые магазины и супермаркеты` 106,
`Специализированные` 100, `овощи-фрукты` 73 — so 279 of them are ordinary food retail, not
markets and malls.

Second, and worse: `Стационарные рынки и ярмарки` is **not a market class**. Its top names
are `Мусорная площадка` 109, `Контейнер для вторсырья` 32, `Контейнер для мусора` 22,
`Мусорный контейнер` 11, then `Лукойл` 8, `Белорусская ярмарка` 6, `Акварель, киоск` 6,
`Татнефть` 5, `Автостоянка` 4, `Роснефть` 3, a beach, a hospital, two ATMs and a computer
club. **184 of the 1,711 grocery rows (10.8 %) are waste containers**, and of the 375
distinct `рынки и ярмарки` coordinates only 31 are in `_all.csv`. Every grocery row more
than 100 m from any export object (145 of them) is in this type.

The contractor appears to have swept an OSM `amenity=waste_disposal` / `recycling` layer
into a "markets and fairs" class.

**Failure scenario.** ML §8.5 sends the client a question implying their 7,263-object
universe may be incomplete and every rate in the study may need a new denominator. The
answer is that the missing objects are bins. The client loses confidence in the analysis
for no reason, and a week goes to a contractor round-trip.

**Test that settles it.** `probe/p3.py`. Fix: filter the grocery layer to the three usable
types before any use, drop `Стационарные рынки и ярмарки` entirely or treat it as
unusable, and restate §0.2 and §8.5. The client question worth asking is narrower and
sharper: *"the `Стационарные рынки и ярмарки` class is 75 % waste containers — what was it
built from?"*

**Good news, and it should be stated so the statistician does not have to re-check:** none
of the junk coordinates is multi-layer and none is in `_all.csv`, so **stats §8 is
unaffected** — the 2,611 sites, the 959 multi-layer, and the 560 grocery × tobacco pairs
(519 of which land on an `_all.csv` object) all stand.

## S2. Both halves join the v4 layers to the export by exact float coordinate equality. That is this repository's signature failure mode.

All the layer-coverage numbers in both documents — ML §0.2's 86.1 / 85.5 / 95.6 / 57.6 %,
ML §2.5's "24.1 % of the export carries any flag", stats §2's 86 / 86 / 96 / 58 % — come
from `set(zip(lat.round(6), lon.round(6)))` intersections. At a 25 m tolerance:

| layer | exact coord | ≤ 10 m | ≤ 25 m | ≤ 100 m |
|---|---:|---:|---:|---:|
| tobacco | 86.1 % | 94.1 % | **98.1 %** | 100.0 % |
| alcohol | 85.5 % | 95.6 % | **99.5 %** | 99.8 % |
| catering | 95.6 % | 98.6 % | **99.6 %** | 99.6 % |
| grocery | 57.6 % | 74.9 % | **81.4 %** | 90.4 % |

CLAUDE.md already records the true figure ("100 % of the 749 tobacco rows and 99.8 % of the
945 alcohol rows sit within 100 m of an existing v3 object"), and both halves silently
contradict it without noticing.

**Failure scenario.** ML §2.5's `f_v4_in_tobacco` / `f_v4_in_alcohol` flags are built on
`site_key` exact-coordinate equality (that is what `v4_common.load_v4()` does). Roughly
12–14 pp of the tobacco and alcohol layers would then be encoded as `0` — "not in the
layer" — when they *are* in the layer at a coordinate written 3 m away. And the false
zeros are not random: they concentrate where the two providers disagree on the coordinate,
which correlates with `verification_status`, which is itself a feature. Model B then
learns a spurious interaction between provider agreement and risk tagging. ML §6.3
carefully adds `f_v4_any_layer` to separate "tagged not-alcohol" from "never examined" —
and then undermines it with a join that manufactures a third, invisible category,
"examined but joined away".

**Test that settles it.** `probe/p2.py`. Fix: join the layers by `matched_source_ids`
(present on 100 % of rows in all five files) with a distance fallback at ~25 m, and report
the residual. This also lets §0.2's "24 % of the city is tagged" be restated correctly.

## S3. An unnamed leakage channel: the licence registry carries the label year.

ML §6.2 puts EGAIS in **both** Model A and Model B on the ground that *"it is a state
registry, not the contractor's opinion, so it is exogenous by construction"*. Exogenous to
the *contractor*, yes. Not exogenous to the *label*.

The registry is consolidated and historic: `date_issued` runs 2006-05-25 → 2026-06-16,
`date_expires` 2009-10-05 → 2031-08-22. **709 of the 2,100 city rows (33.8 %) have a
validity window overlapping calendar 2022**, and 225 of those are now archived.

So `f_lic_status = Archived` at an address is, for a third of the registry, a direct
documentary record that *this address held an alcohol retail licence in the label year*.
The 2022 survey's `Спецмагазины алкоголя` list was, in substance, a list of licensed
alcohol retail. The feature and the label are two records of the same fact.

**Failure scenario.** This is not CV leakage — the feature is available at inference for
all 7,263 objects, so field performance is not overstated. It is worse for a paper: the
Alcohol head's skill will be real and will be almost entirely the registry restating the
2022 survey through a second channel. "Our classifier identifies alcohol shops at PR-AUC
0.8" would then mean "we joined to the licence registry", which the repository can already
do without a model, and which stats §9.6 already names as the better route. A reviewer who
notices this sinks the alcohol result.

**Test that settles it.** Add a **licence ablation** alongside the name ablation (ML §3.1)
and the v4 ablation (ML §6.2): fit the Alcohol head with and without the `f_lic_*` block
and report the gap. If the gap is most of the head's skill, say so and ship the registry
join instead of the head. Additionally, restrict the licence features to licences
*in force at export date*, excluding archived ones whose window covers 2022 — or accept
the archived ones and report the design as registry-assisted, not registry-validated.

## S4. The two halves target different variables, and the stats half's target is circular with the stats half's own baseline.

* ML §1.4 targets raw `category_orig` — seven classes, `Магазины` 258.
* Stats §0, §3, §4 target `recode_2022()` output — Catering 402, Medical 321,
  **Grocery 256**, Sport 79, Alcohol 57, Tobacco 16, **`Other` 2**.

I cross-tabulated the two on the 1,133 linked rows: they agree on **1,131 of 1,133**, the
two disagreements being `Магазины` → `Other`. So the numbers are compatible and this is
not a blocking arithmetic problem. But two things follow that must be fixed in text:

1. The stats half's target has an **eighth class** (`Other`) that the ML half's target
   does not have and that the deliverable does not contain. Two rows, but the schema
   question is real: what does the pipeline do with a benchmark row that recodes to
   `Other`?
2. **Circularity.** If the target is `recode_2022(benchmark)`, then stats §9.1's baseline
   — `recode_2022(export)` — is the same function applied to a different year. The gate
   measures the rule against itself, and agreement is inflated wherever the 2022 and 2026
   blobs happen to use the same Russian stems. The ML half's §3.4 warning
   (*"`recode_2022` as a feature… a reader would reasonably mistake it for a label"*) is
   exactly right and the stats half walks into it from the other side.

**Test that settles it.** Adopt raw `category_orig` as the target (the ML half's choice —
it is what the client asked for, and it breaks the circularity), map the 2 `Other` rows
explicitly, and restate stats §0's prevalence table on that basis. The prevalences move by
at most 2/1,133.

## S5. The two halves specify different output contracts for the two dead classes.

| | ML §7.3 | stats §9.5 |
|---|---|---|
| Industrial | emit `p_industrial_a`, `p_industrial_b`, `p_industrial_delta` (all `NA`) + `rule_industrial` | **"do not produce it. Omit the column."** |
| Tobacco | emit `p_tobacco` with `calibration = "not estimated"` | "produce it, bound it, **never point-estimate it**" |

The statistician's reasoning on Industrial is the stronger one and it is explicitly about
foreseeable misuse: *"Emitting an untrained, unevaluated `p_industrial` column guarantees
someone will use it."* ML's own §1.4 concedes the rule is dominated by name-substring false
positives (verified: 25 city-wide, and 13 of them inside the benchmark okrugs with 0
labelled positives).

For Tobacco the two are nearly compatible — ML's `calibration = "not estimated"` column is
a weaker version of the statistician's bound — but a CSV column named `p_tobacco` carrying
a float *is* a point estimate whatever the neighbouring column says, and the deliverable is
a CSV that will outlive the report.

**Failure scenario.** The client opens `clf2022_predictions.csv` in Excel, sorts by
`p_industrial_a`, and finds a hostel. Or aggregates `p_tobacco ≥ 0.5` per okrug and puts it
in a table. Both are one click away and neither is prevented by a `calibration` column.

**Resolution required.** One contract, in one place. I recommend the statistician's: no
`p_industrial` column at all (ship `rule_industrial` if anything, named as a rule), and
`p_tobacco` renamed to `tobacco_rank_score` with the §6 bound `[0.26, 0.91]` printed beside
it.

## S6. ML §8.1 calls a question "the single most consequential unanswered question in the design". The data answers it.

*"Is `Магазины` 'grocery shops' or 'shops of any kind'?"* — the 400 benchmark `Магазины`
rows break down as `Продуктовый магазин` 204, `Супермаркет` 147, `Фрукты-овощи` 35,
`Кулинария` 6, `Ярмарка` 4, `Рынок` 3, `Сыроварни` 1. **There is no non-food retail in the
class at all.** `recode_2022()` maps 392 of the 400 to `Grocery shops`.

So the 2022 `Магазины` class *is* grocery, and the ML half's own §1.4 already builds the
head from it. Sending this to the client as the top open question delays the design for an
answer the repository already holds (and which `docs/crosswalk_2022.md` presumably
records).

Worth keeping as a *note* rather than a question: the export's `Магазины` is a different
animal — 3,637 of 7,263 rows, dominated by clothing, furniture and electronics — so the
`category_orig = Магазины` feature means something quite different on the two sides of the
join, and that asymmetry is worth a sentence in the report.

## S7. The `gps_only` mask is specified at the wrong unit and its size is overstated.

ML §1.2: *"541 masked (row, class) cells against ~7,500 usable cells."* But the design's
training unit is the export row (§1.1), and the 541 `gps_only` benchmark rows point at only
**487 distinct export rows** — of which **114 are already labelled positives** from a
different benchmark row that matched `exact`/`probable` at the same door.

**Failure scenario.** Built naively at the benchmark-row unit and then collapsed, the mask
either (a) zeroes the sample weight on 114 rows that carry a genuine positive label for
some head, silently deleting real positives from the smallest heads, or (b) is applied
before the collapse and then partially overwritten, with the result depending on row order.
Either way it is a silent few-percent change to the positive counts of Alcohol and Sport,
the two heads that cannot afford it.

**Test that settles it.** Build the mask at the `(export_row_id, class)` unit *after* the
§1.1 collapse, assert that no masked cell coincides with a positive, and print the realised
mask size (it will be ≤ 487 cells, not 541) into `clf2022_metrics.json`.

## S8. The statistician's prior-shift argument imports the inference it elsewhere forbids.

Stats §1: *"In the target, the v4 layers imply roughly 749/7,263 = 10.3 % [tobacco] and
945/7,263 = 13.0 % [alcohol]… a model calibrated on `S` is miscalibrated on `U` by a factor
of ~4 on the tobacco prior."*

But 82 % of those layers is the `Возможная …` tier, which the contractor's own
`verification_comment` says *требует отдельной проверки*, and CLAUDE.md forbids reporting a
merged headline count (verified: tobacco is `Возможная продажа` 619 of 749; alcohol
`Возможная …` 766 of 945). Using that number as the target prior is the same move the
design refuses when it keeps the layers out of training, and the same move that would make
Model A silently become Model B.

Nothing else in §1 depends on it, so the fix is a sentence: state the tobacco prior as
*unknown, bounded below by the 100 `Специализированная` rows and above by the 749-row
layer*, and note that the ~4× is an upper-bound scenario resting on the contractor's
unverified tier. Otherwise the report's own headline prevalence is a number the report
elsewhere says must never be quoted.

## S9. Spatial autocorrelation crosses every fold, under both proposed splitters.

Both halves group at the building scale (~25 m, or shared address). ML §2.3 then computes
`f_nbr_share_cat{c}_{250,500}m`, `f_nbr_count_{100,250,500}m` and
`f_nbr_dist_nearest_cat{c}` — features with a 250–500 m support.

These are export-side features, not labels, so this is **not** label leakage and ML §2.3's
self-exclusion note is the right countermeasure for the one real leak in the block. But a
test-fold object's neighbourhood statistics are computed over its train-fold neighbours,
and objects 200 m apart in Arkhangelsk's centre are strongly dependent. The CV estimate is
therefore optimistic by an unquantified amount for any head whose signal is spatial —
which, given that the licence and neighbourhood blocks are the entire case for Candidate 3,
is the head that matters.

**Test that settles it.** Add a spatially-blocked CV as a diagnostic (grid blocks of ~500 m
as the group key) and report the gap against the building-grouped number. If the gap is
large, the neighbourhood block is memorising the map, and the leave-one-okrug-out run of
stats §2 becomes the only trustworthy transportability evidence.

---

# WORTH NOTING

**W1.** Stats §9.1 names `v4_common.recode_2022_v4()` as the baseline recoder. On
`_all.csv` it is **identical** to `v3_common.recode_2022()` — I ran both, `differ: 0`. The
`табач` stem correction only bites on the v4 layer vocabulary, which is not what is being
scored. Numerically harmless; an implementer following the text will reach for the wrong
module and conclude the fix did nothing.

**W2.** ML §7.2 writes the pixi task as `scripts/match_egais_v4.py --input all`. That flag
does not exist — the script has `--layer {both,alcohol,tobacco}`. The good news is that the
ML half's claim that this is "a runner-level change" is correct: `v4_egais.prepare_v4()`
needs only `adress_orig`, `name_orig`, `latitude`, `longitude`, all present in `_all.csv`.
But the script's report path (`LEAD = ["risk", "evidence", "trade", …]`) comes from
`load_v4()`, which has no `_all.csv` equivalent, so budget a little more than a flag.

**W3.** `matched_source_ids` is populated on 100 % of rows and is never mentioned in
ML §2.2's keep/drop list. It is a deterministic restatement of `verification_status`
(prefix counts: `osm` 6,504, `2gis` 759 = 587 + 172) plus high-cardinality provider ids. Not
a leak, but it should be in the explicit drop list with that reason, so the next reader does
not have to re-derive it.

**W4.** The grocery overlap is quoted as 57.6 % (ML, row-level 985/1,711) and 58 % (stats,
coordinate-level 955/1,640). Both are right; they are different quantities presented as the
same one. Pick one denominator across the document.

**W5.** ML §2.3 requires the okrug one-hot to be *"an explicit ablation, not a silent
one"*. Six of the nine levels are identically zero across all 1,072 training rows, so their
coefficients are structurally zero and ablating them changes nothing. The ablation as
specified is a no-op. What is worth reporting instead is that 1,649 inference rows have an
all-zero okrug block — genuinely out of support — which is the §3.6 point stated properly.

**W6.** ML §1.4's per-head counts are stated as `category_orig` totals (Магазины 258) while
stats §3's prevalence baselines use the recoded counts (Grocery 256, baseline 0.226). After
S4 is resolved, one of these tables needs a one-line edit; flagging it so it is not
forgotten.

**W7.** ML §4.4's adoption rule for sentence embeddings — *"adopt only if it improves the
held-out metric on the unseen-`type_orig` slice"* — is unevaluable: the unseen slice
contains **zero labelled rows** by construction (the slice is defined as types absent from
training). The rule as written can never be checked. Given B5 it should simply be struck,
along with Candidate 4: the 1.2–6 GB dependency is being justified by a slice that is 97.7 %
clothing shops and hairdressers.

**W8.** ML §4.5's refusal of the RTX 5090 is correct and well argued; no change. Likewise
the dependency solves (scikit-learn 1.9.1 / lightgbm 4.7.0 on python 3.14 / pandas 3.0) were
verified by actually solving an environment, which is the right standard and I did not
re-run them.

**W9.** Stats §8's manual-labelling exercise (600 objects, 6 strata, ~20 hours, stratum 6
non-optional) is the strongest single section in either half. Under B5 it stops being a
nice-to-have and becomes the project's only real validation instrument, so it should move
out of §8 and into the design's critical path, with the budget conversation held now rather
than after the gates fail.

---

# Verdict

**Fit to implement with named changes — but the changes are structural, not editorial, and
four of them must land before any code is written.**

The statistician's half is, on its own, sound: every number reproduces, the estimand is
stated correctly, the bounds table in §6 is the right headline, and §8's refusal list and
audit design are publishable as they stand. Its two defects are B4 (the headline gate rests
on a false premise about string rules and compares a single-label rule to a multi-label
model) and S8 (the prior-shift figure borrows the contractor's unverified tier).

The modelling half is careful and well-instrumented — the leakage inventory, the
self-exclusion note, the cross-fitting protocol and the "may not be claimed" list are all
correct — but it has one mechanical failure that stops the pipeline (B1: the splitter
produces a 63.6 % component against its own 8 % bound, and its fallback moves the wrong
way), one measurement it declares unknown that is knowable and large (B3), and one framing
error that misdirects the whole justification for a learned model (B5 / W7: the 45 %
unseen-type slice is 97.7 % outside the taxonomy).

Before code:

1. **B1** — adopt the building group key (3.5 %), drop the chain edge, keep the
   largest-component assertion.
2. **B2** — one primary splitter, named once, with the chain-grouped run as a mandatory
   companion; delete whichever half's contrary argument does not survive.
3. **B3** — publish the negative-noise table and decide the masking policy.
4. **B4** — rewrite §9.1 against a multi-label rule baseline, with the measured
   P/R table as the bar and a gate width the CI can resolve.

Before the client sees it:

5. **B5** — state plainly that the labelled rows are the rows the free rule already gets
   right, and reshape the deliverable accordingly (rule as product, model as review queue,
   EGAIS for alcohol, no number for tobacco).
6. **S1–S5** — fix the grocery-layer contamination and its client question, replace the
   exact-coordinate joins, add the licence ablation, settle the target variable, and settle
   the output contract for Industrial and Tobacco.

S6–S9 and W1–W9 are report-quality items and can be folded in during implementation.

Not fit to ship as *"seven calibrated multi-label probabilities for 7,263 objects"*. Fit to
ship as *"a validated rule over the 2022 taxonomy, a bounded assessment of what a learned
model adds, and a prioritised review queue"* — which is the deliverable the evidence
supports and, per stats §9.6, the one this repository has been pointing at all along.
