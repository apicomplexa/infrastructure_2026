# Manual audit of the 2022 taxonomy: labelling protocol

**Read this before labelling anything.** It is written first on purpose: rules
settled after the labeller has seen the data are rules fitted to the data.

- **Sample**: `data/processed/taxonomy_2022/taxonomy_2022_audit_sample.csv`, 600 objects.
- **Drawn by**: `scripts/audit_sample_2022.py`
- **Seed**: 20260915
- **Numbers, weights and precision**: `data/processed/taxonomy_2022/taxonomy_2022_audit_sample_summary.txt`
- **Background**: `docs/classifier_design.md`, §7 (the approved audit) and §10
  (why it is stratified over the rule rather than over a model).

Changing the seed redraws the sample and voids any labelling already done. The
sampler refuses to run unless the seed above matches its own.

---

## 1. What is being measured, and what is not

The rule in `src/arkhinfra/taxonomy_2022.py` puts each of the city's 7,263
objects on none, one or several of the seven 2022 lists. It has only ever been
scored against the 2022 benchmark on the 1,133 export rows that link to it —
15.6 % of the city, and its easy end (accuracy 0.925 on `exact` links against
0.700 on `probable`). The errors that remain live on the other 84 % and are
**definitional**: a spelling hole, a category test that swept in 63 saunas, a
priority order that hid 35 groceries. No benchmark in this repository reaches
them. This audit is the only instrument that does.

So the question each label answers is:

> **Would the 2022 survey have put this object on list *k*?**

It is *not* "does the rule's output look reasonable", and it is *not* "what does
2GIS call this". The labeller is reconstructing the 2022 authors' judgement.
Where that judgement is genuinely unknown, §3 marks the rule **provisional** and
the label records what was applied, so it can be re-scored if the 2022 authors
answer (`docs/classifier_design.md` §8.1).

**Not measured by this audit**: Industrial prevalence city-wide; any per-okrug
number for the six unbenchmarked okrugs; anything about objects the export does
not contain; any improvement to a model (there is no model, and §10.4 shows the
export's fields do not encode co-membership at all).

---

## 2. Mechanics

**Fill seven columns per object**, plus `true_sport_retail`:

| column | meaning |
|---|---|
| `true_medical` | Медицинские организации |
| `true_sport` | Спортивные объекты |
| `true_grocery` | Магазины |
| `true_catering` | Общепит |
| `true_alcohol` | Спецмагазины алкоголя |
| `true_tobacco` | Точки продажи табака |
| `true_industrial` | Пром. Объекты |
| `true_sport_retail` | sells sports goods (a shop, not a facility) |

**Permitted values: `1`, `0`, `?`.**

`?` means *could not be determined inside the time box*. It is a real answer and
must be used. Forcing a `0` because nothing was found manufactures precision —
an unresolved object and an object confirmed absent are different facts, and the
analysis treats them differently (a `?` rate above ~10 % in a cell is itself
reportable, and rates are computed both excluding and counting `?` as `0`).

The seven are **independent**. An object can be several things; there is no
priority and no "best" class. A hookah lounge is `true_catering = 1` **and**
`true_tobacco = 1`.

**Also fill**:

- `label_confidence` — `high` / `medium` / `low`. `low` on any object where the
  evidence was a single ambiguous source.
- `label_source` — the field that settled it: `export` / `2gis` / `osm` /
  `web` / `streetview` / `none`.
- `labeller` — your initials.
- `note` — free text, required whenever any value is `?`, whenever
  `label_confidence = low`, and whenever you disagree with the rule's output for
  a reason worth recording. Keep it to one line. Do not use the `#` character.

**Do not edit any other column.** The `is_*`, `*_evidence`, `weight`, `cell` and
`stratum` columns are the design; changing them breaks the reweighting.

**Procedure, ~2 minutes per object**, stopping as soon as the answer is certain:

1. Read `name_orig`, `type_orig`, `category_orig`, `adress_orig` in the file.
2. Look the object up in 2GIS by name and address.
3. If 2GIS does not have it, try OSM, then a web search on name + "Архангельск".
4. If still unresolved, `?`.

Do not spend more than about four minutes on any one object; log it as `?` and
move on. The budget is 20 hours for 600 objects and an hour spent on one hard
case is forty objects not labelled.

**Label the object at its address as it is now.** Where a business has clearly
been replaced since the 2026 export, label what the export describes and say so
in `note` — the rule is being audited, not the city.

---

## 3. Class definitions

Each class gives what counts, what does not, and whether the rule is settled or
**provisional**. Provisional rules are applied as written and flagged so they can
be re-scored later.

### 3.1 `true_medical` — Медицинские организации

**Include**: pharmacies; polyclinics and hospitals; dental practices; private
clinics and single-specialty practices; diagnostic and laboratory points;
dispensaries; maternity units; opticians; hearing-aid shops; medical-supply and
orthopaedic shops; rehabilitation and sanatorium facilities; feldsher points.

**Exclude**: **veterinary** practices of any kind — the class is human health
infrastructure. Beauty salons, cosmetics shops, nail and massage salons, spas,
tanning studios. Medical-insurance offices and health-authority administration
with no clinical service on site. Drugstore-format shops that sell cosmetics and
household goods and no medicines (`Магнит Косметик` is **not** medical).

**Edge case**: a pharmacy counter inside a supermarket → `true_medical = 1` and
`true_grocery = 1` both. This is exactly the co-membership under test, and
§10.1 shows the 2022 survey recorded some such objects on both lists.

### 3.2 `true_sport` — Спортивные объекты — **PROVISIONAL**

**Include**: a place where physical activity happens. Sports halls and
complexes, gyms and fitness clubs, swimming pools, stadiums, ice rinks, indoor
arenas, outdoor pitches and sports grounds, workout areas, yoga and martial-arts
studios, sports schools and sections. Parks, squares, embankments and beaches,
which the 2022 benchmark lists as sport objects.

**Exclude — provisionally**:

- **Saunas and bath-houses.** The 2022 benchmark labels a sauna `Общепит`, not a
  sport object. The audit tests this: a sauna gets `true_sport = 0` and
  `true_catering = 1` under the provisional rule, and `note` should say
  `sauna — provisional rule applied`. 63 such objects exist and they are the bulk
  of what the D2 correction removed from the class.
- **Sports shops.** A shop is not a facility. `true_sport = 0`,
  `true_sport_retail = 1`.

**Exclude outright**: car parks and `автопарк`/`технопарк`; passport offices
(`паспортный стол`) and haulage firms, which reach the class only through the
substring `спорт`; lottery kiosks, ticket offices and shopping centres named
after a sports object; police stations.

**Why provisional**: `docs/classifier_design.md` §8.1 records both questions —
whether `Спортивные объекты` includes sports shops and saunas — as open for the
2022 authors. The benchmark's own evidence excludes saunas; it says nothing
about shops. If the authors answer differently, `true_sport_retail` and the
sauna notes let every affected label be re-scored without relabelling.

### 3.3 `true_grocery` — Магазины — **PROVISIONAL**

**The provisional rule is: food retail.** 392 of the 400 objects in the 2022
class are food shops and the class contains no non-food retail at all, so the
data reads as a grocery class with a general name (§8.1).

**Include**: convenience shops and `Продуктовый магазин`; supermarkets and
hypermarkets; greengrocers (`Овощи и фрукты`, `Фрукты-овощи`); bakeries and
pastry shops selling bread and baked goods to take away; butchers; fishmongers;
dairy shops; delicatessens and `Кулинария`; confectionery and chocolate shops;
tea, coffee, water and honey shops; drinks shops (`Напитки`); food markets and
fairs; kiosks whose assortment is food or drink.

**Exclude**: all non-food retail — clothing, shoes, furniture, hardware,
stationery, electronics, pet shops, flower shops, jewellers, pharmacies (they are
`true_medical`), chemists and drugstores selling no food.

**Edge cases**: a shopping centre is `0` unless it is itself a food market. A
petrol-station shop with a food counter is `1`. A café that also sells bread
over the counter is `true_catering = 1` and `true_grocery = 1`.

**Why provisional**: if the 2022 authors answer that `Магазины` means shops of
any kind, every `0` given to a non-food shop flips. Record nothing extra — the
`type_orig` column already distinguishes them, so the re-scoring is mechanical.

### 3.4 `true_catering` — Общепит

**Include**: cafés, restaurants, bars, pubs, canteens (`Столовая`), fast food,
coffee shops, pizzerias, sushi bars, snack bars, bistros, confectionery cafés
with seating, hookah lounges, and any place selling prepared food or drink for
consumption on site or immediately.

**Exclude**: food shops with no prepared food (they are `true_grocery`);
catering firms with an office and no outlet; barbershops, pressure chambers and
pawnshops, which reach the class only through the substring `бар`.

**Provisional**: **saunas** — see §3.2. The 2022 benchmark labels a sauna
`Общепит`, so the provisional rule is `true_catering = 1` with a note. If this
looks wrong on the object in front of you, still apply the rule and say so in
`note`; the audit is measuring the rule, and a note is how it gets overturned.

### 3.5 `true_alcohol` — Спецмагазины алкоголя

**The class is a specialised alcohol shop, not "anywhere alcohol is sold".**

**Include**: a shop whose **primary assortment is alcohol** — alcohol markets,
wine shops, beer shops, draught-beer outlets (`Разливное`, `Пивас и квас`), the
specialist chains. This is decided by the **assortment, not by `type_orig`**:
§10.1 shows the 2022 survey put nine `Бристоль` outlets on the alcohol list even
though the export types them `Продуктовый магазин`. A `Бристоль`, `Красное &
Белое` or `Ароматный мир` is `true_alcohol = 1` whatever its type says, and
`true_grocery` is judged separately on its food assortment.

**Exclude**: a supermarket or convenience shop with an alcohol shelf under a
general licence. That is `true_grocery = 1`, `true_alcohol = 0`. Restaurants and
bars — on-trade sale is `true_catering`, not this class. The 2022 class is
off-trade specialist retail and the licence registry licenses the two separately
(`CLAUDE.md`, fourth delivery).

**If in doubt between "specialist" and "shelf"**: `?`, with a note. Do not guess
— the alcohol count is the number this repository has already had to correct
once (the fivefold undercount).

### 3.6 `true_tobacco` — Точки продажи табака

**"Sells tobacco" means the outlet is a place a person goes to buy tobacco or
nicotine products, evidenced — not assumed.**

**Mark `1` when** any of these holds:

1. The fascia, name or assortment is specialised in tobacco, cigarettes, cigars,
   vapes, e-cigarettes, hookah or smoking accessories (`Табак`, `Дымный папа`,
   `SmokeArh`, `Вейп-шоп`, `Кальянная`).
2. 2GIS or OSM carries an explicit tobacco/e-cigarette tag or rubric for it.
3. It is a hookah lounge (also `true_catering = 1`).

**Mark `0` when** the only ground for marking it would be *"a shop of this kind
usually sells tobacco"*. A supermarket, a convenience shop, a petrol station or
a kiosk is `0` unless 1–3 above hold for that specific object.

**This is the whole point of the column.** The fourth delivery's 82 % `Возможная`
tier is an inference of exactly that shape, which the contractor's own comment
calls *требует отдельной проверки*, and the repository has no tobacco benchmark
anywhere to settle it (there is no EGAIS analogue for tobacco). An audit that
adopted the same inference would reproduce the contractor's number rather than
test it. If you believe an object sells tobacco but cannot evidence it, mark `0`
and write `probable, unevidenced` in `note` — those notes are counted separately
and reported as a bound, never folded into the rate.

### 3.7 `true_industrial` — Пром. Объекты — **PROVISIONAL**

**Include**: a production or energy facility — plant, factory, combine, mill,
sawmill, power station, heating plant, industrial depot or workshop at
industrial scale.

**Exclude**: offices and sales rooms of an industrial company; shops, hostels,
hotels and cafés whose *name* contains a plant's name (`Завод`, `Фабрика`); bus
and tram depots; warehouses and logistics centres that only store.

**Why provisional**: the 2022 class holds 10 objects, none of which links to the
export, and §8.1 records "what `Пром. Объекты` was meant to capture" as an open
question. Every object the rule puts in this class rests on the fascia string
alone, and the class is documented to contain a hostel and a jewellery shop. The
audit measures that precision exactly (the name-evidence cell is a census); it
cannot produce a city-wide prevalence.

---

## 4. The two contested cells, in one paragraph each

**Co-membership.** The rule lets an exact `category_orig` value override a class
inferred from `type_orig` or the fascia. On 42 objects that removes a second
class — mostly rows whose category says `Точки продажи табака` and whose type
says `Продуктовый магазин`, taking the multi-label count from 49 to 7. Label
both classes on their own merits, ignoring what the rule shipped. Where you mark
both present, the override is wrong and the co-membership is real; where only the
category's class is present, the override is right and the type field is simply
bad. `latent_classes_2022` and `category_override_removed` in the sample file
show what was removed.

**The no-class pool.** 4,647 objects carry no class. The claim under test
(§2.5) is that they are genuinely outside the 2022 scheme — the city's clothing,
hairdressing and car-repair trade — rather than a spelling hole of the kind that
has already been found three times. Label them like any other object: if a
`Магазин: confectionery` is a food shop, it is `true_grocery = 1` and the rule
has a hole. Do not let a blank `classes_2022` anchor the answer.

---

## 5. The double-labelled subset

60 objects (10 %) carry `double_label = TRUE`, drawn within each stratum.

- A **second labeller** labels them **independently**, from the original file,
  without seeing the first labeller's values. Copy the sample file, blank the
  label columns, and label into the copy.
- Cohen's κ is computed **per class** over those 60.
- **Report κ to one decimal.** At n = 60 the standard error on κ is about 0.10.
  That resolves κ < 0.6 — which is the finding that would matter — but cannot
  separate 0.8 from 0.9. Two decimals would claim a resolution the sample does
  not have.
- κ is undefined or unstable for a class with almost no positives in 60 draws
  (Industrial, Alcohol, Tobacco are all likely). Report the raw agreement count
  and the positive count for those, and say κ is not estimable. Do not report a
  κ computed on two positives.
- Disagreements are **reconciled after κ is computed**, never before, and the
  reconciled value is what enters the rate estimates.

---

## 6. Reweighting, in one line each

- `weight = cell_N / cell_n`, on **every** row. The six cells partition all
  7,263 objects, so these weights sum to 7,263 and a city rate is
  `sum(weight * label) / sum(weight)` over the whole file.
- `srs_weight`, on the 100 `6_srs_city` rows only. Those are a self-weighting
  okrug-proportional sample of the whole city and give the same city rate on
  their own, from a design with no purposive component. **Compute both.** If
  they disagree beyond their intervals, the cell definitions do not partition
  the city the way the file says, and that is a finding, not a rounding error.
- A rate measured inside one purposive cell is a rate **for that cell**. Cells
  are oversampled by factors of 1 to 25; quoting a cell rate as a city rate is
  the single easiest way to get this audit wrong.
