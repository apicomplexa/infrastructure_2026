# Crosswalk: 2026 export → 2022 health taxonomy

Reference material for the third-delivery reports (`analysis/v3/eda-v3.qmd`,
`analysis/v3/eda-v3-validation.qmd`). It documents how objects in the 2026 export
are recoded into the seven-class taxonomy the 2022 study used, and what that
recoding gets wrong.

The rule lives in `recode_2022()` in `src/arkhinfra/v3_common.py`. Counts below are for
the third delivery (`data/raw_v3/infrastructure_архангельск_2026-08-31_quality_excel.csv`,
7,263 objects).

## How the rule works

Each object is matched against three fields:

- `category_orig` — the export's coarse category (18 values)
- `type_orig` — the export's object type (218 values), lowercased
- `name_orig` — the object name, lowercased

The three are concatenated into one search blob for the substring tests. Class
assignment is a **priority chain**, not a set of independent tests: the first
rule that fires wins, in this order.

| # | Class | Fires on |
|---|-------|----------|
| 1 | Tobacco outlets | category = `Точки продажи табака`, or blob contains `табак`, `вейп`, `сигарет`, `кальян`, `vape` |
| 2 | Alcohol shops | type contains `алкогол`; or blob contains `алкомаркет`, `винотек`; or type contains both `винный` and `магазин` |
| 3 | Medical | category = `Медицинские организации`, or blob contains `аптек`, `поликлин`, `больниц`, `стоматолог`, `клиник`, `врач`, `диагност`, `лаборатор`, `диспансер`, `госпит`, `медиц`, `оптика`, `реабилит`, `санатор`, `профилакт`, `роддом`, `родильн`, `фельдшер` |
| 4 | Sport | category = `Спортивные объекты`; or blob contains `спорт`, `фитнес`, `бассейн`, `стадион`, `тренаж`, `воркаут`, `каток`, `манеж`, `йога`; or type contains `парк`, `сквер`, `набережн` |
| 5 | Catering | category in {`Общепит`, `фастфуд`}; or type contains `кафе`, `фастфуд`, `бар`, `ресторан`, `паб`, `кофейн`, `столов`, `закусочн`, `пиццери`, `суши`, `бистро` |
| 6 | Grocery shops | type is one of the ten grocery types listed below |
| 7 | Industrial | blob contains `завод`, `энергокомплекс`, `тэц`, `гэс`, `фабрика`, `промышл`, `комбинат` |
| — | Other (outside 2022 scheme) | default |

Grocery types (exact match on the lowercased type): `продуктовый магазин`,
`супермаркет`, `фрукты-овощи`, `булочная`, `кулинария`, `мясной магазин`,
`рыбный магазин`, `молочный магазин`, `гипермаркет`, `продукты`.

Priority matters in practice. 35 objects typed `Продуктовый магазин` land in
**Tobacco outlets** rather than Grocery shops because rule 1 fires first on their
category — grocery stores registered as tobacco retail points. That is the
intended behaviour: the risk classification takes precedence over the retail
format.

## Class totals

| Class | 2026 export | 1st delivery | 2022 benchmark |
|---|---:|---:|---:|
| Medical | 677 | 638 | 371 |
| Sport | 358 | 371 | 190 |
| Grocery shops | 811 | 854 | 392 |
| Catering | 625 | 610 | 621 |
| Alcohol shops | 110 | 94 | 116 |
| Tobacco outlets | 60 | 60 | 46 |
| Industrial | 25 | 22 | 10 |
| Other (outside 2022 scheme) | 4,597 | 4,579 | 7 |
| **Total** | **7,263** | **7,228** | **1,753** |

The 2022 benchmark was assembled *to* this taxonomy, so only 7 of its records
fall outside it. The 2026 export is a general-purpose census in which 63 % of
objects are outside the 2022 scheme. Compare the two class by class, never on
totals.

## Source categories and types feeding each class

### Medical — 677

| Source category | Type | n |
|---|---|---:|
| Медицинские организации | Аптека | 251 |
| Медицинские организации | аптека | 104 |
| Медицинские организации | Стоматология | 72 |
| Медицинские организации | Врачебная практика | 66 |
| Медицинские организации | Клиника | 43 |
| Магазины | Оптика | 42 |
| Медицинские организации | Больница | 39 |
| Магазины | Медицинские товары | 16 |
| Реабилитация и профилактика | Социально-оздоровительный объект | 13 |
| Организации | Офис: insurance | 7 |
| Медицинские организации | Лаборатория | 5 |
| — | 12 further pairs, 1–3 objects each | 19 |

Note `Аптека` and `аптека` are two distinct type values in the source data — the
export is inconsistent in its own casing.

### Sport — 358

| Source category | Type | n |
|---|---|---:|
| Спортивные объекты | Спортивная площадка | 160 |
| Спортивные объекты | Спортивный центр | 71 |
| Досуг и спорт | Досуг: sauna | 63 |
| Магазины | Спортивный магазин | 20 |
| Спортивные объекты | Фитнес-центр | 13 |
| Государственные организации | Госучреждение | 9 |
| Спортивные объекты | Стадион | 5 |
| Организации | Офис: company | 5 |
| — | 10 further pairs, 1–3 objects each | 12 |

Two entries deserve scrutiny. **Saunas (63)** enter Sport through the
`Досуг и спорт` category, which is a defensible reading of the 2022 scheme but
worth a decision — they are a sixth of the class. **Sport shops (20)** are retail,
not sport infrastructure, and arguably belong in Other.

### Grocery shops — 811

| Source category | Type | n |
|---|---|---:|
| Магазины | Продуктовый магазин | 532 |
| Магазины | Супермаркет | 143 |
| Магазины | Булочная | 93 |
| Магазины | Мясной магазин | 25 |
| Магазины | Рыбный магазин | 18 |

The cleanest class: one source category, five types, exact matches only.

### Catering — 625

| Source category | Type | n |
|---|---|---:|
| Общепит | Кафе | 224 |
| Общепит | Фастфуд | 146 |
| фастфуд | Общепит | 117 |
| Общепит | Бар | 96 |
| Общепит | Ресторан | 34 |
| Общепит | Паб | 8 |

Note the third row: the export has both a `фастфуд` category and a `Фастфуд`
type, and they cross over. Both land in Catering, so the inconsistency is
harmless here.

### Alcohol shops — 110

| Source category | Type | n |
|---|---|---:|
| Магазины | Алкогольный магазин | 108 |
| Магазины | Винный магазин | 1 |
| Общепит | Бар | 1 |

### Tobacco outlets — 60

| Source category | Type | n |
|---|---|---:|
| Точки продажи табака | Продуктовый магазин | 35 |
| Точки продажи табака | Табачный магазин | 15 |
| Точки продажи табака | Вейп-магазин | 10 |

Every member comes from the dedicated source category; no object is recruited
into this class by a name substring alone.

### Industrial — 25 (unreliable, see below)

| Source category | Type | n |
|---|---|---:|
| Организации | Офис: company | 7 |
| Магазины | Косметика | 3 |
| Организации | Объект: ferry_terminal | 3 |
| Магазины | Хозяйственный магазин | 2 |
| Организации | landuse: industrial | 1 |
| — | 9 further pairs, 1 object each (hostel, jewellery shop, laundry, photo shop, driving school, college, NGO office, confectionery, drinks shop) | 9 |

### Other (outside 2022 scheme) — 4,597, top types

| Source category | Type | n |
|---|---|---:|
| Организации | Офис: company | 312 |
| Магазины | Магазин одежды | 307 |
| Услуги | Парикмахерская | 226 |
| Магазины | Магазин: outpost | 217 |
| Услуги | Салон красоты | 185 |
| Магазины | Автосервис | 151 |
| Магазины | Хозяйственный магазин | 148 |
| Образование | Детский сад | 126 |
| Магазины | Мебельный магазин | 124 |
| Магазины | Цветочный магазин | 117 |

Education (kindergartens 126, schools 101) is the largest coherent block sitting
in Other. The 2022 taxonomy has no education class; if the study wants one, this
is where it would come from.

## Known defects

**1. `Grocery shops` was empty in every previously delivered report.**
`recode_2022()` lowercases `type_orig` before the membership test, but the copies
of `GROCERY_TYPES` in `analysis/v1/eda.qmd` and `analysis/v2/eda-v2.qmd` are
capitalised (`"Продуктовый магазин"`). The test can never succeed, so the class
was always empty and its objects fell through to `Other`. Corrected in
`src/arkhinfra/v3_common.py`; the two older reports still carry the defect. Scale:
811 objects in this export, 854 in the first, and **392 of the 1,753 records in
the 2022 benchmark — 22 % of it**. Any published `Other` count from the first- or
second-delivery reports is inflated by roughly 800 objects.

**2. `Industrial` is dominated by false positives.** The rule fires on substrings
like `завод`, `фабрика` and `комбинат` anywhere in the blob, including the object
name. A hostel, a jewellery shop, a laundry and a driving school are currently
classed as industrial because those tokens appear in their names. Of 25 members
only one (`landuse: industrial`) is unambiguous. Do not report okrug-level
industrial counts; the 2022 benchmark's own industrial class holds just 10
records, so the pair is too small for comparison either way.

**3. Sport absorbs recreation and retail.** Saunas (63) and sport shops (20) make
up 23 % of the class. Both are arguable readings; neither is infrastructure in
the sense the 2022 study used.

**4. The recoding is name-sensitive and therefore unstable across deliveries.**
Rules 1, 3, 4, 5 and 7 test the object name, so an object renamed between exports
can change class without moving or changing function. This is a floor on how
reproducible the class counts can be between the first and third deliveries.

## Keeping copies in sync

`recode_2022()` exists in three places: `analysis/v1/eda.qmd`, `analysis/v2/eda-v2.qmd`
and `src/arkhinfra/v3_common.py`. The v3 copy is the corrected one. If the older
reports are ever re-rendered, port the grocery fix across first, or their class
counts will not be comparable with the third delivery's.
