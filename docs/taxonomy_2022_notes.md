# The 2022 taxonomy as seven independent flags (`taxonomy_2022`)

`src/arkhinfra/taxonomy_2022.py`, run by `scripts/build_taxonomy_2022.py`
(`pixi run build-taxonomy`). Input is the third delivery's city-wide export
(`V3_CSV`, 7,263 objects). No model, no training, no probabilities — a rule,
rewritten.

`v3_common.recode_2022()` answers **"which one 2022 class is this object?"**: seven
predicates resolved through `np.select`, whose priority order silently discards
every further class the object belongs to. The 2022 commission asks the other
question — **"which of the seven lists would this object appear on?"** — so this
module emits seven booleans and never collapses them, and for each one an
`evidence` column naming the field that carried the object in.

Independent does not mean unarbitrated. Where `category_orig` **exactly names one
of the seven classes**, that is the export asserting what the object is, and it
outranks anything inferred from `type_orig` or the fascia: a `type`- or
`name`-level flag for a *different* class is suppressed. That is the evidence
hierarchy below applied to the export contradicting itself, and it is what keeps
the 35 mis-typed tobacco shops of D3 out of the grocery count.

Kept **separate from `v3_common.py`** on the precedent of `basecheck.py`,
`egais.py` and `v4_common.py`: three rendered v3 reports carry the numbers the old
rule produces, three defects fixed here move those numbers city-wide, and the two
rules must therefore coexist until those reports are re-rendered deliberately.
What is shared (`norm_okrug`, `V3_CSV`) is imported, never copied.

## The output

`data/processed/taxonomy_2022/taxonomy_2022.csv` — **7,263 rows × 40 columns**, semicolon-delimited,
UTF-8 with BOM like every other CSV here. The export's own 22 columns, then:

| column | meaning |
| --- | --- |
| `okrug_key` | `v3_common.norm_okrug(district_orig)` — the nine okrugs, normalised |
| `is_medical`, `is_sport`, `is_grocery`, `is_catering`, `is_alcohol`, `is_tobacco`, `is_industrial` | bool, seven **independent** flags; no priority, no mutual exclusion |
| `medical_evidence` … `industrial_evidence` | `category` \| `type` \| `name` \| `""` — the **strongest** field that fired for that class on that row |
| `is_sport_retail` | `Спортивный магазин` / `Магазин спорттоваров` — a shop, deliberately **not** `is_sport` |
| `n_classes` | 0–7, the number of flags set |
| `classes_2022` | the set as text, `Grocery shops\|Tobacco outlets`; `Other (outside 2022 scheme)` when empty |

`data/processed/taxonomy_2022/taxonomy_2022_summary.txt` carries the same run's tables — class
counts against the old rule, the evidence split, the multi-label pairs, the okrug
matrix and the guard's verdict. Cyrillic goes to that file rather than to the
Windows console. **Every number below comes from it or from the CSV; nothing is
quoted from an earlier document.**

## What moved, city-wide

| class | old (`recode_2022`) | new | delta |
| --- | ---: | ---: | ---: |
| Medical | 677 | 671 | −6 |
| Sport | 358 | **255** | **−103** |
| Grocery shops | 811 | **867** | **+56** |
| Catering | 625 | 633 | +8 |
| Alcohol shops | 110 | 109 | −1 |
| Tobacco outlets | 60 | 60 | 0 |
| Industrial | 25 | 28 | +3 |
| no class | 4,597 | 4,647 | +50 |
| sport retail | — | 20 | new flag |

2,616 objects carry at least one class; 4,647 carry none. The "no class" count
rises even though Grocery gains 56, because Sport loses 103 objects that carried
no other class.

### D1 — `Овощи и фрукты` recoded to `Other`, 51 objects

`GROCERY_TYPES` in `v3_common` holds `фрукты-овощи`, the 2022 study's spelling.
The 2026 export writes the same two words in the other order, and
`Series.isin` is exact equality. 51 greengrocers city-wide fell to
`Other (outside 2022 scheme)`.

This is the **third member of a family this repository already documents** — the
`GROCERY_TYPES` case mismatch (`type_orig` lowercased, tested against a capitalised
set) and `табак` vs `табач-` in the fourth delivery. All three are the same defect:
a closed list of literal strings compared exactly against a vocabulary nobody
controls.

Fixed generally rather than by adding the one string — see *Type normalisation*
below — and guarded so there is no fourth member.

### D2 — about 30 % of the `Sport` class was not a sport facility

The old rule searches a blob that **includes `category_orig`** for the stem `спорт`.
`Досуг и спорт` is a category, so everything filed under it entered the sport class.
What the 358 lost, by `type_orig`:

| dropped | n | why |
| --- | ---: | --- |
| `Досуг: sauna` | 63 | category `Досуг и спорт`; the 2022 benchmark labels a sauna `Общепит` |
| `Спортивный магазин` | 20 | retail, not a facility — moved to `is_sport_retail` |
| `Госучреждение` | 8 | fascia hits: *па-**спорт**-ный стол* |
| `Офис: company` | 5 | *тран-**спорт**-ная компания* |
| `Колледж`, `Полиция`, `Магазин: mall`, `Магазин: ticket`, `Магазин: lottery`, `Офис: ngo`, `Офис: foundation` | 1 each | ditto |

Nothing joins the class: *Архангельский центр лечебной физкультуры и спортивной
медицины* matches the sport stems on its name, but its `category_orig` is
`Медицинские организации`, so the contradiction rule suppresses the flag. Net
−103. One `Госучреждение` stays — *Управление физкультуры и спорта мэрии города
Архангельска*, whose category is `Государственные организации` and therefore
contradicts nothing — on `name` evidence; whether a sport administration belongs
on a facility list is a judgement for the review queue, not for the rule.

Three mechanisms do this work: stems run on `type_orig` / `name_orig` **only**,
categories are matched **exactly**, and stems match on a **word boundary**
(`STEM_MODE`, default `prefix`) instead of anywhere in the string.

`Sport` is a headline health-access class reported per okrug, so this is the change
that most affects published results.

### D3 — 35 rows of the export carry the wrong `type_orig`

Read first, in §10.3 of the design document, as *35 grocery shops made invisible
by `np.select` putting Tobacco first*. **That reading is wrong**, and building the
seven-flag rule is what exposed it.

The 35 rows pair `category_orig = Точки продажи табака` with
`type_orig = Продуктовый магазин`, and their names settle what they are: *Азбука
дыма*, *SmokeArh, табачная лавка*, *Дымный папа*, *Kiss My Vape*, *Oblako,
магазин дымной продукции*, *Станция Дыма*, *Махорка*, *SmokyBro, вейп-шоп*. They
are tobacco and vape shops whose type is wrong; they were never groceries.

So D3 is **not a defect in the recoder at all** — it is a defect in the export's
`type_orig` on a known 35-row slice. The old rule's priority order returned the
right answer for them **by accident**, and that accident is what kept the defect
hidden. Seven independent flags exposed it by counting the 35 as grocery shops as
well; the contradiction rule then removes them, because the category asserts a
class while the type only infers one.

Grocery city-wide is therefore **867**, not the 902 the uncorrected flags gave,
and the 35 rows are a *finding* rather than a silent correction: they are carried
in the manual-review queue as rows with a known-bad type.

Grocery's +56 against the old rule decomposes exactly: `Овощи и фрукты` 51 (D1),
`Магазин: dairy` 3 and `Мастерская: bakery` 2 (OSM-tag spellings the 2022 list
never anticipated). Nothing left the class.

## Type normalisation: a word bag, not a longer list

Adding `"овощи и фрукты"` to `GROCERY_TYPES` would have closed D1 and left the
defect. `norm_type()` applies NFC, lower-case, `ё → е`, punctuation → space,
whitespace collapse; `_type_key()` then reduces the label to the **frozen set of its
significant words** (`_STOPWORDS` drops `и`, `в`, `на`, …). Whole-label matching
compares those keys, so `Овощи и фрукты`, `фрукты-овощи`, `Фрукты/Овощи` and
`ОВОЩИ-ФРУКТЫ` are one key, and word order, separator, case and yo/ye stop being
things a maintainer has to anticipate.

Whole-label word-bag matching is used where the label *is* the class
(`GROCERY_TYPES_2022`, `ALCOHOL_TYPES`, `SPORT_RETAIL_TYPES`,
`SPORT_OPEN_SPACE_TYPES`). Stems (`TYPE_STEMS`) are used where a family of labels
is, and each stem carries a mode:

- **`prefix`** (default) — matches only at a word start. This is what stops
  *па-**спорт**-ный*, *тран-**спорт**-ная*, *лом-**бар**-д*, *био-лаборатория* and
  *био-медицина*.
- **`infix`** — `завод`, `фабрика`, `комбинат`, which genuinely appear mid-word
  (*мясо-комбинат*, *лесо-завод*).
- **`word`** — `бар`, `паб`, `суши`, `тэц`, `гэс`, `оптика`, `vape`, which must not
  fire on *Барс* or *Баренц*.

Two further lists, each entry a demonstrated false positive rather than a guess:
`TYPE_VETO` (a veterinary clinic is not human health infrastructure; *автопарк* and
*парковка* are not parks; *барбершоп* is not a bar) and `NAME_ONLY_FORBIDDEN`
(a lottery kiosk does not become a sport facility because its fascia says
*Спорт-лото*).

**Word boundaries are not a solved problem.** Two live false positives remain, both
found in the output and both `name` evidence: the stem `кафе` fires on *Кафедра
иностранных языков СГМУ* and *Кафедра кожных и венерических болезней СГМУ*, two
university departments now flagged `Catering`. They are in the queue, not in the
rule.

## The evidence column, and what a count rests on

| class | total | `category` | `type` | `name` |
| --- | ---: | ---: | ---: | ---: |
| Medical | 671 | 594 | 58 | 19 |
| Sport | 255 | 250 | 0 | 5 |
| Grocery shops | 867 | 0 | 867 | 0 |
| Catering | 633 | 626 | 0 | 7 |
| Alcohol shops | 109 | 0 | 109 | 0 |
| Tobacco outlets | 60 | 60 | 0 | 0 |
| Industrial | 28 | 0 | 0 | **28** |

Read down the columns, not across the totals — **a count resting on `category` is a
different kind of claim from one resting on `name`**:

- **`category`** — the export's own `category_orig` says so. The contractor
  classified the object; the rule only reads the label. 60 of 60 Tobacco, 626 of
  633 Catering, 594 of 671 Medical.
- **`type`** — the object's kind implies the class: `Супермаркет`, `Алкогольный
  магазин`, `Оптика`. Grocery is 867 of 867 `type`, because the export has no
  grocery *category* at all (`CATEGORY_OF["grocery"]` is deliberately empty).
- **`name`** — only the fascia string suggests it. This is a **hypothesis about an
  object**, not a classification of it, and it is where every false positive in the
  output lives.

The three are ranked, not merely labelled. `category` outranks the other two
**across classes as well as within a row**: where `category_orig` exactly names
one of the seven classes, a `type`- or `name`-level flag for a *different* class
is suppressed (`contradicted` in `classify()`). It fires on the 35 mis-typed
tobacco shops of D3 at type level, and on a handful of fascia hits — the
`Больница` named *центр лечебной физкультуры и спортивной медицины* (Sport
suppressed by `Медицинские организации`), the `Бар` named *Алкомаркет* (Alcohol
suppressed by `Общепит`, which is why Alcohol is 109 and not 110), and five
Industrial fascia hits under a catering or medical category. An object whose
category is **outside** the seven — `Магазины`, `Образование`, `Организации` —
contradicts nothing, so its `type` and `name` flags stand.

`Industrial` is the extreme case and should be read as a warning label: **28 of 28
objects rest on `name` alone**, and the list contains a hostel called *ТЭЦ*, a
jeweller called *Московский ювелирный завод*, a photo shop called *Фабрика*, a
cake shop (*Фабрика тортов*), a cosmetics shop (*Архангельский водорослевый
комбинат*) and three ferry terminals named after the sawmills they serve
(*Лесозавод No 14 / 22 / 23*). The class is a string search over shop signs. **Do
not report it per okrug**; the caveat predates this module and this module does not
fix it — it only makes it visible in the data instead of in a footnote.

The practical rule: a headline count may be quoted from `category` + `type`
evidence; `name` evidence belongs in a manual-review queue (`pixi run
review-queue`), and any figure that mixes the two must say so.

## The guard

`missed_types()` lists every `type_orig` that landed in **no class at all** while
containing one of `AUDIT_STEMS` (`продукт`, `овощ`, `фрукт`, `аптек`, `спорт`,
`табач`, `алкогол`, `кафе`, …). `assert_no_missed_types()` raises on a non-empty
result, and `build_taxonomy_2022.py` calls it on every run and exits non-zero if it
fires. The current run prints `PASS`.

It exists because D1 was invisible for two deliveries: a spelling hole produces no
error, only a smaller number.

**When it fires**, the type it names is either

- a spelling the class definition misses — add the label to the relevant
  `*_TYPES` set (the word-bag key absorbs most variants already, so check whether
  the label is genuinely a new *word*), or a stem to `TYPE_STEMS`; or
- genuinely outside the taxonomy despite carrying the stem — add its key to
  `GUARD_EXEMPT_TYPES` **with a reason in the comment beside it**. The only two
  entries today are the sport-retail types, exempted because `is_sport_retail`
  carries them.

Never silence it by trimming `AUDIT_STEMS`.

## Multi-label: 7 objects, of which 2 are real

| pair | n | what it is |
| --- | ---: | --- |
| Grocery shops \| Catering | 2 | genuine — *Ларец, магазин-бистро* and *Бонус, магазин-кафе*, a grocery with a counter, typed `Продуктовый магазин` and named as both |
| Grocery shops \| Industrial | 5 | not genuine — four `Мясной магазин` named *Северодвинский мясокомбинат* and one *Хладокомбинат No 2*: shops named after a plant, `name`-level Industrial off `комбинат` |

No object carries three; 2,609 carry exactly one; 4,647 carry none.

So the export's own fields put two 2022 classes on **2 objects out of 7,263**, and
five more are a fascia artefact of the class that is a fascia artefact throughout.
**The export encodes essentially no co-membership.** Nothing in `category_orig`,
`type_orig` or `name_orig` states that a supermarket sells tobacco — the v4 layers
imply on the order of 560 grocery × tobacco sites (§10.4 of
`docs/classifier_design.md`), and only those layers and the FSRAR licence registry
state it at all. The seven flags are independent *predicates* over three text
fields, not a co-membership model, and a multi-label deliverable cannot be built
from this input at any label count.

Before the contradiction rule the count was 49, inflated by the 35 mis-typed
tobacco shops of D3 — which are the strongest illustration of the point: what
looked like co-membership was a wrong `type_orig`.

## What this does **not** do

- **No probabilities, no scores, no model.** The output is seven booleans and their
  provenance. There is nothing to calibrate and no confidence to quote. Anything a
  report says about uncertainty here has to come from the audit sample, not from
  this file.
- **No co-membership.** See above: 2 objects in 7,263. A grocery that sells tobacco
  is invisible to these fields; use `data/raw_v4/` and
  `data/processed/v4_licences/v4_licences.csv` for that question, with the evidence tiers those
  carry.
- **No new objects, and no repair of `type_orig`.** It reclassifies the 7,263 rows
  of the third delivery and nothing else. D3 is *detected*, not fixed: the 35 rows
  still carry `Продуктовый магазин` in the CSV, and the review queue is where they
  go. It does not touch alcohol coverage either, which the v3 export understates
  fivefold — **`Alcohol shops` is 109, and it is still the wrong number to use**;
  `data/raw_v4/` remains the alcohol source.
- **No validation beyond 15.6 % of the city.** The only labelled rows are the 1,133
  that link to the 2022 benchmark (§10.2 of `docs/classifier_design.md`), and that
  sample is drawn at the easy end: accuracy tracks link quality, 0.925 on `exact`
  links against 0.700 on `probable` ones, and every linked row has name similarity
  ≥ 0.6. The 620 benchmark rows that reached only `gps_only` or `unmatched` are
  precisely the ones whose names did not survive four years, and they are
  unmeasured. D1–D3 were all found on the unmeasured 84 %. **Any per-class accuracy
  table must be reported as covering 15.6 % of the city, at its easy end.**
- **No okrug validation outside three okrugs.** The 2022 benchmark covers
  Lomonosovsky, Oktyabrsky and Maiskaya Gorka. The okrug matrix in the summary is
  produced for all nine; six of them have nothing to check against.
- **It does not re-render anything.** The v3 reports still carry the old rule's
  numbers, on purpose.
