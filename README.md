# Arkhangelsk Urban Infrastructure — 2026 stage

Source data and exploratory analysis for a study of **how urban infrastructure
objects are distributed across the city of Arkhangelsk**, with a focus on
health-supporting infrastructure and health risk factors.

This is the current stage of a Northern State Medical University (NSMU) research
project. Data is produced by the **ИнфраструктураРФ** program, which collects,
cross-checks, and enriches infrastructure objects from open sources (OpenStreetMap,
2GIS, Yandex, and others). See `docs/` for background extracted from the project
presentations.

## Repository layout

```
├── data/
│   ├── raw/                     # first delivery, 2026-06-28 (read-only)
│   │   ├── objects_arkhangelsk_2026-06-28_enriched.csv   # main export, 7,228 objects
│   │   ├── objects_arkhangelsk_2026-06-28_health.xlsx    # health/risk-filtered subset
│   │   └── objects_3_districts_2022.xlsx                 # previous-stage result (3 okrugs)
│   └── raw_v2/                  # second delivery, 2026-08-24 (read-only)
│       ├── сравнение_документов_2026-08-24_093901.xlsx   # 2022 <-> 2026 record comparison
│       ├── итоги_сравнения_3_округа.csv                  # per-okrug summary of that comparison
│       └── ARKTMED_Arkhangelsk_2021-2026_all_categories_20260824_082854.xlsx  # indicator panel
│   └── raw_v3/                  # third delivery, 2026-08-31 (read-only)
│       ├── infrastructure_архангельск_2026-08-31_quality_excel.csv  # city-wide export, 7,263 objects
│       ├── export_base_688669_zal6mp.xlsx                # commercial directory dump, 10,557 records
│       └── ARKTMED_Arkhangelsk_2021-2026_all_categories_20260831_172749.xlsx  # rebuilt indicator panel
│   └── raw_v4/                  # fourth delivery, 2026-09-03/04 (read-only)
│       ├── infrastructure_архангельск_2026-09-03_quality_excel табачное изделие.csv  # tobacco risk layer, 749 rows
│       └── infrastructure_архангельск_2026-09-04_quality_excel алкоголь.csv          # alcohol risk layer, 945 rows
├── docs/                        # English documentation extracted from the presentations
│   ├── infrastructure_rf.md         # the ИнфраструктураРФ program (current stage)
│   ├── report_arkhangelsk_2022.md   # 2022 report summary (previous stage)
│   ├── crosswalk_2022.md            # 2026 -> 2022 taxonomy crosswalk and its defects
│   ├── egais_source_notes.md        # the FSRAR licence registry, field by field
│   ├── v4_source_notes.md           # the fourth delivery: what it is and how to read it
│   └── v4_yandex_check.md           # the unlicensed alcohol objects, checked on Yandex Maps
├── references/                  # original presentations (binary, source of docs/)
│   ├── infrastructure_rf.pptx
│   └── report_arkhangelsk_2022.pptx
├── analysis/                    # report sources only — one directory per delivery
│   ├── v1/                      # first delivery (data/raw)
│   │   ├── eda.qmd              # Quarto EDA (parameterised: enriched | health)
│   │   └── eda-ru.qmd           # Russian version of the EDA (identical structure)
│   ├── v2/                      # second delivery (data/raw_v2) — withdrawn by v3
│   │   └── eda-v2.qmd
│   └── v3/                      # third delivery (data/raw_v3); *-ru.qmd are the
│       ├── eda-v3.qmd           #   Russian twins — prose only, tables stay English
│       ├── eda-v3-ru.qmd
│       ├── eda-v3-validation.qmd    # independent re-check against the 2022 benchmark
│       ├── eda-v3-validation-ru.qmd
│       ├── eda-v3-basecheck.qmd     # commercial directory profiled + re-matched
│       └── eda-v3-basecheck-ru.qmd
│   ├── v4/                      # fourth delivery (data/raw_v4)
│   │   ├── eda-v4.qmd           # risk layers vs the 2022 study and the licence registry
│   │   └── eda-v4-ru.qmd        #   Russian twin — prose only, tables stay English
│   └── egais/                   # the FSRAR licence registry (not a commissioned delivery)
│       └── eda-egais.qmd
├── reports/                     # rendered PDFs — git-ignored, rebuilt by pixi tasks
│   ├── v1/                      # eda.pdf, eda-health.pdf + their -ru twins
│   ├── v2/                      # eda-v2.pdf
│   ├── v3/                      # eda-v3.pdf, -validation.pdf, -basecheck.pdf + twins
│   ├── v4/                      # eda-v4.pdf + its -ru twin
│   └── egais/                   # eda-egais.pdf
├── src/arkhinfra/               # importable library, shared by reports and scripts
│   ├── paths.py                 # every path in the repo, resolved from its root
│   ├── v3_common.py             # shared loaders / recoding for the v3 reports
│   ├── match_2022.py            # independent 2022 <-> 2026 record matcher
│   ├── basecheck.py             # export_base matcher (stricter normalisers)
│   ├── egais.py                 # FSRAR licence-registry loader and okrug recovery
│   ├── v4_common.py             # fourth-delivery loaders, tiers, corrected recoder
│   ├── v4_egais.py              # adapter: the v4 export and the registry -> licmatch
│   ├── v4_yandex.py             # manual check of the unlicensed alcohol rows on Yandex Maps
│   ├── v4_export.py             # the three deliverable licence spreadsheets
│   └── taxonomy_2022.py         # the seven independent 2022-class flags
├── packages/licmatch/           # standalone record-linkage package (own tests & docs)
│   ├── src/licmatch/            # toponyms, the score, exclusive selection, brand learning
│   ├── docs/METHODOLOGY.md      # why each weight, floor and route is what it is (RU)
│   └── tests/                   # 130 unit tests — `pixi run licmatch-test`
├── scripts/                     # runnable entry points
│   ├── profile_data.py          # quick dataset profile
│   ├── match_2022.py            # CLI launcher for arkhinfra.match_2022
│   ├── build_ru_v3.py           # regenerate the Russian twin of eda-v3.qmd
│   ├── build_ru_basecheck.py    # regenerate the Russian twin of the basecheck report
│   ├── build_ru_v4.py           # regenerate the Russian twin of eda-v4.qmd
│   ├── parse_egais.py           # stream the FSRAR registry XML -> processed TSV
│   ├── match_egais_v4.py        # join the v4 export to the licence registry
│   ├── check_yandex_v4.py       # check the unlicensed alcohol objects on Yandex Maps
│   ├── export_licences_v4.py    # build the deliverable licence spreadsheets (XLSX)
│   └── ru_numfmt.py             # Russian number conventions in the twins
├── pixi.toml                    # environment & tasks (pixi / conda-forge)
└── pixi.lock
```

### Original file names

Files were renamed to short ASCII names for reliable tooling. Original names:

| Current | Original |
| --- | --- |
| `data/raw/objects_arkhangelsk_2026-06-28_enriched.csv` | `infrastructure_архангельск_2026-06-28_quality_excel_enriched_2026-06-29_135815_excel.csv` |
| `data/raw/objects_arkhangelsk_2026-06-28_health.xlsx` | `infrastructure_архангельск_2026-06-28_quality_excel_health_filter_2026-06-29_160031.xlsx` |
| `data/raw/objects_3_districts_2022.xlsx` | `220615 Все объекты_ 3 округа 1753.xlsx` |
| `references/report_arkhangelsk_2022.pptx` | `220524_Доклад_Отчет_Инфраструктура_Архангельск_final.pptx` |
| `references/infrastructure_rf.pptx` | `ИнфраструктураРФ.pptx` |

Files in `data/raw_v2/` keep their original (Russian) names, since two of the
three are referenced by name inside the delivery itself.

## Second delivery — `data/raw_v2/` (2026-08-24)

The second delivery is **not a refresh of the first**. It contains three
different artefacts, analysed in [`reports/v2/eda-v2.pdf`](reports/v2/eda-v2.pdf).

### 1. `сравнение_документов_2026-08-24_093901.xlsx` — record comparison

A record-level comparison of the **2022 stage document** (2,293 rows) against a
**new 2026 export restricted to the three okrugs the 2022 study covered**
(5,257 rows). Seven sheets:

| Sheet | Rows | Content |
| --- | --- | --- |
| `Сводка` | 15 | Run parameters and headline counts |
| `Документ 1 с результатом` | 2,293 | The 2022 document with match status, found counterpart and GPS corrections appended |
| `Совпадения` | 1,168 | Firm matches, both documents' columns side by side |
| `Вероятные совпадения` | 995 | Probable matches requiring manual review |
| `Только в документе 1` | 130 | 2022 objects not re-found in 2026 |
| `Только в документе 2` | 3,663 | 2026 objects absent from the 2022 document |
| `GPS-предупреждения` | 2 | Coordinate outliers detected |

Matching used a **60 m distance tolerance** and a **0.86 name-similarity
threshold**, with probable-match and GPS-correction modes enabled.

**The new 2026 export is not shipped as a sheet of its own**, but every one of
its 5,257 rows appears exactly once across `Совпадения`, `Вероятные совпадения`
and `Только в документе 2`, always carrying the full `Документ 2: *` column
block. Concatenating those blocks and de-duplicating on `Строка в документе 2`
reconstructs the export verbatim — this is how `analysis/v2/eda-v2.qmd` recovers
it. Its columns map onto the canonical schema of the first export
(`Категория` → `category_orig`, `Организация` → `name_orig`, …); see Appendix A
of the report for the full dictionary.

The 2022 document used here (2,293 rows) is a **larger, GPS-annotated variant**
of `data/raw/objects_3_districts_2022.xlsx` (1,753 rows). The difference is
concentrated in the risk classes — 483 tobacco outlets here against 46 in the
repository copy.

### 2. `итоги_сравнения_3_округа.csv` — comparison summary

Semicolon-delimited, UTF-8 with BOM, 4 rows (three okrugs + total). Columns:
`Округ`, `Строк в исходном документе`, `Совпадений`, `Вероятных совпадений`,
`Не найдено`, `Найдено всего`, `Доля найденных, %`. Headline: 94.3% of 2022
rows re-found overall, ranging from 89.5% (Mayskaya Gorka) to 95.7%
(Oktyabrsky).

### 3. `ARKTMED_Arkhangelsk_2021-2026_all_categories_...xlsx` — indicator panel

A **municipal indicator panel** for Arkhangelsk: 28 indicators × 6 years
(2021–2026) = 168 observations, in 7 sections (Демография, Здоровье, Медицина,
Экономика, Экология, Климат, Инфраструктура), plus a composite risk index with
five components. Sheets: `Описание`, `Показатели`, `Индекс риска`, `Сводка`,
`Карточки`. It carries **no object-level or okrug-level detail** — it describes
the city as a whole, and is unrelated to the object export.

> **Caveat — this panel is modelled, not observed.** 27 of the 28 indicators are
> *exactly* linear in time (second difference zero to floating-point precision),
> two of the six years lie in the future relative to the file's own date,
> population age bands carry fractional people, and sources are cited at domain
> level only. Every row is nevertheless stamped `Качество, % = 100`, which
> describes completeness of the generated table, not fidelity to a source. Treat
> the panel as a **schema**, not as data; re-source each series before citing it.

## Obtaining the data

`data/raw/` (first delivery) is in the repository. **`data/raw_v2/` and
`data/raw_v3/` and `data/raw_v4/` are not** — 8.6 MB of vendor spreadsheets, kept out of git for
bulk. Copy them from the project archive into those two directories before
rendering anything beyond the first-delivery reports; the file names the loaders
expect are listed in the layout tree above and in `src/arkhinfra/paths.py`.
Everything under `data/` is **read-only** — never modify a delivery in place.

## Getting started

The project uses [pixi](https://pixi.sh) for dependency management (conda-forge).

```bash
pixi install            # create the environment from pixi.lock
pixi run profile        # print a quick profile of the dataset
pixi run eda            # render the full enriched export  -> reports/v1/eda.pdf
pixi run eda-health     # render the health & risk subset  -> reports/v1/eda-health.pdf
pixi run eda-all        # render both reports
pixi run eda-ru         # Russian report, enriched export  -> reports/v1/eda-ru.pdf
pixi run eda-health-ru  # Russian report, health subset    -> reports/v1/eda-health-ru.pdf
pixi run eda-all-ru     # render both Russian reports
pixi run eda-v2         # render the second-delivery report -> reports/v2/eda-v2.pdf
pixi run eda-v3         # render the third-delivery report  -> reports/v3/eda-v3.pdf
pixi run eda-v3-val     # render the validation report      -> reports/v3/eda-v3-validation.pdf
pixi run eda-v3-all     # render both third-delivery reports
pixi run eda-v3-base    # commercial-directory source check -> reports/v3/eda-v3-basecheck.pdf
pixi run match-2022     # run the independent 2022 <-> 2026 matcher -> data/processed/
pixi run eda-v3-ru      # Russian third-delivery report -> reports/v3/eda-v3-ru.pdf
pixi run eda-v3-val-ru  # Russian validation report     -> reports/v3/eda-v3-validation-ru.pdf
pixi run eda-v3-all-ru  # render both Russian third-delivery reports
pixi run eda-v3-base-ru # Russian source check -> reports/v3/eda-v3-basecheck-ru.pdf
pixi run build-ru       # regenerate the Russian v3 twins from the English sources
```

`reports/` is **git-ignored**: the PDFs are deliverables, rebuilt on demand from
the sources, and keeping them out of history stops every re-render from adding
several MB of undiffable binary to the repository.

The EDA is **parameterised** (`dataset: enriched | health`) so the same document
produces a report for either the full city export or the health-filtered subset;
the health run additionally uses the export's native impact classification
(`Тип влияния`, `Полезные группы`, `Группы риска`).

The EDA renders to PDF via Quarto + XeLaTeX. A LaTeX distribution is required
(this repo was built with MiKTeX on Windows); Cyrillic in figures is handled by
matplotlib's DejaVu Sans, and Cyrillic in body text by the `Arial` main font.

## Main dataset (`objects_arkhangelsk_2026-06-28_enriched.csv`)

Semicolon-delimited, UTF-8 with BOM, 7,228 rows. Key columns:

| Column | Meaning |
| --- | --- |
| `verification_status` | Source confirmation tier: `only_osm`, `only_2gis`, `confirmed_by_2gis_and_osm` |
| `providers` / `provider_count` | Which sources found the object / how many |
| `filled_fields` / `missing_fields` | Attributes present / absent after enrichment |
| `match_distance_meters` / `match_name_similarity` | Cross-source match geometry / name score |
| `category_orig` / `type_orig` | Category and fine-grained type (Russian) |
| `name_orig` | Object name |
| `city_orig` / `district_orig` / `adress_orig` | Location text fields |
| `latitude` / `longitude` | Coordinates (WGS84) |
| `website_orig` / `phone_orig` / `opening_hours_orig` / `opening_date_orig` | Contact & schedule |

See `analysis/v1/eda.qmd` for the full dictionary and analysis.

## Key findings — first delivery (see `reports/v1/eda.pdf`)

- **7,228 objects**, 16 categories, 216 types — a general city inventory (retail
  dominates), much larger than the 2,528-object 2022 dataset.
- **Source confidence is thin:** only ~2.6% of objects are multi-source
  confirmed; ~89% are OSM-only. Absolute counts are lower bounds.
- **Geometry is complete** (100% coordinates, 98% addresses); *opening date* is
  unusable (<1%).
- **District assignment is broken:** ~71% of objects land in a single okrug
  (Oktyabrsky) — must be fixed before any district-level conclusions.
  **Fixed in the second delivery** — see below.
- A transparent heuristic already separates **health-supporting infrastructure
  from risk factors**, giving the next stage a concrete health-to-risk indicator.

### Recoding to the 2022 taxonomy

The 2022 stage used a focused 7-class health taxonomy (*Medical, Sport, Grocery
shops, Catering, Alcohol shops, Tobacco outlets, Industrial*), while the current
export uses a broader generic scheme (e.g. `Магазины` mixes groceries, clothing,
and alcohol). The EDA adds a derived column **`category_2022`** that recodes each
current object into the 2022 taxonomy (via `category_orig` + `type_orig` +
`name_orig`), enabling a like-for-like comparison of the two stages and a
frequency table / heatmap of the recoded classes by okrug. About **40%** of the
full export (and **~85%** of the health subset) maps into the 2022 scheme.

## Key findings — second delivery (see `reports/v2/eda-v2.pdf`)

- **The okrug defect is fixed.** The new export splits the three okrugs
  2,355 / 2,203 / 699 (Lomonosovsky / Oktyabrsky / Mayskaya Gorka) instead of the
  first export's 33 / 5,104 / 915, and agrees with the 2022 stage on **100%** of
  firmly matched records. District-level analysis is defensible again — for these
  three okrugs; the other five remain unvalidated.
- **Source diversity was lost in the process.** All 5,257 objects are OSM-only;
  the 2GIS provider is absent, so nothing in this delivery is independently
  corroborated.
- **Continuity with 2022 is 51%, not 94%.** 94.3% of 2022 objects are re-found,
  but 43.4% only as *probable* matches awaiting review. Probable matches are
  usually the right building with an uncertain tenant, so they can be triaged by
  name similarity.
- **The 2022 risk taxonomy does not survive the new category scheme.** Only 78%
  of matched objects keep their category; 483 tobacco outlets in 2022 correspond
  to 22 so-labelled objects in the 2026 export, because the export classifies the
  premises rather than the product sold there.
- **Sport facilities are the real coverage gap** — 22% not found, and 46 of the
  130 objects lost since 2022.
- **The health-to-risk ratio is now computable per okrug** on trustworthy labels
  — the first substantive project output this data supports.
- **The ARKTMED indicator panel is synthetic** (27/28 series exactly linear) and
  must be re-sourced before use.

## Third delivery — `data/raw_v3/` (2026-08-31)

The third delivery **replaces the second rather than extending it**: both
artefacts `eda-v2.qmd` is built on are withdrawn. It is a fresh city-wide export
plus two new files, analysed in two reports —
[`reports/v3/eda-v3.pdf`](reports/v3/eda-v3.pdf) (descriptive) and
[`reports/v3/eda-v3-validation.pdf`](reports/v3/eda-v3-validation.pdf) (independent
re-check against the 2022 benchmark).

| Artefact | 1st (`raw/`) | 2nd (`raw_v2/`) | 3rd (`raw_v3/`) |
| --- | --- | --- | --- |
| Main object export | 7,228 (city) | 5,257 (3 okrugs) | 7,263 (city) |
| Record comparison vs 2022 | — | 2,293 × 5,257 | — (withdrawn) |
| Per-okrug comparison summary | — | yes | — (withdrawn) |
| Commercial directory dump | — | — | 10,557 records |
| ARKTMED indicator panel | — | 28 ind. / 168 rows | 22 ind. / 65 rows |
| 2GIS provider present | yes | no | yes |

Files in `data/raw_v3/` keep their original names.

## Key findings — third delivery

- **The okrug defect is fixed city-wide**, not just for three okrugs. The largest
  okrug now holds 35% of objects (was 71%), and Isakogorsky / Tsiglomensky —
  merged into a single label in the first export — are separate.
- **2GIS is back**, but corroboration is still thin: 172 objects (2.4%) are
  confirmed by both providers and 6,504 (89.6%) rest on OSM alone. The export's
  own `match_distance_meters` / `match_name_similarity` fields are a
  *deduplication key, not independent verification* — 99.5% sit at exactly 0 m.
- **The export is a fresh census, not a revision:** 81% of its content in the
  three 2022 okrugs has no 2022 counterpart.
- **The contractor's 94.3% match rate does not survive independent re-checking.**
  Re-implementing the comparison from scratch gives a recall of **~64%**. Their
  *confirmed match* tier is sound (median name similarity 1.00), but their
  *probable match* tier is mostly coordinate proximity (median 0.51) — counting a
  2022 object as found whenever any 2026 object sits nearby. Reproducing that
  rule reproduces their number (95.1% vs their 94.3%, agreeing per okrug within
  ~1 pp). The finding is robust to thresholds: the most permissive setting tested
  (150 m, 0.75) still reaches only 70.9%.
- **Risk classes are covered worst**, confirmed independently: recall is 34.8%
  for tobacco outlets and 49.1% for alcohol shops, against 86.5% for medical
  organisations.
- **Most "missing" 2022 objects are tenant churn, not export failures.** Of 541
  records with a nearby 2026 object but a different name, 388 share the address —
  the same premises under a new occupant.
- **The ARKTMED panel is no longer synthetic** (0 of 11 testable series exactly
  linear, against 27 of 27 in the second delivery) and cites named Rosstat files.
  But every health-outcome indicator was removed, the risk-index sheet is empty,
  and outside climate it is a two- to three-year snapshot.
- **A recoding bug was found and fixed.** `recode_2022()` lowercased the type
  field but tested it against a capitalised grocery list, so the **`Grocery
  shops` class was empty in every previously delivered report** — 811 objects
  here, 854 in the first export, and 392 of the 1,753 records in the 2022
  benchmark (22%). The fix lives in `src/arkhinfra/v3_common.py`; `analysis/v1/eda.qmd`
  and `analysis/v2/eda-v2.qmd` still carry the defect, so their `Other` counts are
  inflated. See [`docs/crosswalk_2022.md`](docs/crosswalk_2022.md).
- **The commercial dump cannot serve as a primary source:** its okrug field is
  empty for all 10,557 records and its coordinates are rounded to ±55 m, coarser
  than the 50 m matching radius. As a *corroborating* source it is better than
  first reported — see below.
- **The 3.6% corroboration figure in `reports/v3/eda-v3-validation.pdf` is wrong.** It is a
  join artefact: `norm_address` strips the city with a word boundary that never
  matches "Архангельск**ая** область", so the administrative prefix on 45.8% of
  directory addresses survives normalisation; the join additionally used exact
  name equality and blocked on the address alone. Re-matched on distance with
  fuzzy names (≥ 0.90) the directory corroborates **≈ 32%** of the export — about
  nine times the published rate. See
  [`reports/v3/eda-v3-basecheck.pdf`](reports/v3/eda-v3-basecheck.pdf); the corrected
  normalisers live in `src/arkhinfra/basecheck.py`, kept separate from
  `src/arkhinfra/v3_common.py` so the earlier reports are unaffected.

## Fourth delivery — `data/raw_v4/` (2026-09-03 / 2026-09-04)

Two CSVs, one per risk factor, analysed in
[`reports/v4/eda-v4.pdf`](reports/v4/eda-v4.pdf) (`pixi run eda-v4`), with a
Russian twin at [`reports/v4/eda-v4-ru.pdf`](reports/v4/eda-v4-ru.pdf)
(`pixi run eda-v4-ru`). Full
field-level notes are in [`docs/v4_source_notes.md`](docs/v4_source_notes.md).

**It is not a fourth survey — it is a risk-attribution layer over the third.**
100% of the 749 tobacco rows and 99.8% of the 945 alcohol rows sit within 100 m
of an object `data/raw_v3/` already held, and 94–98% of their source ids are ids
v3 already cites. What the delivery adds is a judgement about which existing
objects plausibly sell alcohol or tobacco. The two files overlap on 359
coordinates, so the combined layer is **1,335 distinct sites**, not 1,694.

| Artefact | 3rd (`raw_v3/`) | 4th (`raw_v4/`) |
| --- | --- | --- |
| Column schema | 22 columns | identical, dtypes included |
| `category_orig` / `type_orig` vocabulary | third taxonomy | **fourth taxonomy**, no shared value |
| Alcohol outlets recognised | 110 | 945 (638 off-trade, 307 on-trade) |
| Tobacco outlets recognised | 60 | 749 |
| Evidence tier | — | 82% `Возможная …` (inferred), 18% direct |
| All nine okrugs separate | yes | yes |

## Key findings — fourth delivery

- **The schema promise holds as a container, not as a vocabulary.** Column
  names, order and dtypes are identical to the third delivery, so existing code
  reads the files unchanged. But `category_orig` / `type_orig` carry a fourth
  taxonomy, and **`recode_2022()` silently drops 698 of 749 tobacco rows on it**
  — the rule tests for the stem `табак`, every new label spells it `табач-`.
  Fixed in `v4_common.recode_2022_v4()`, deliberately not in `v3_common`.
- **Four rows in five are an inference, not an observation.** The `Возможная …`
  types mean "this object's type is compatible with selling it"; the
  contractor's own comment says the product's presence
  *требует отдельной проверки*. Report the direct and inferred tiers separately.
- **The fivefold alcohol undercount closes.** Off-trade objects rise from 110 to
  **638** against **442** licences in force in the FSRAR registry; the
  licences-per-object ratio moves from 4.0 to 0.69, and the okrug spread narrows
  from a factor of 4.2 to 1.6 (every okrug now between 0.57 and 0.92). The share
  of licensed outlets with a matching export object within 50 m rises from
  **18.9% to 73.6%** (90.8% at 100 m). **Okrug-level alcohol risk comparisons
  become defensible for the first time.**
- **No improvement against the 2022 benchmark.** Recall moves 49.1% → 50.0%
  (alcohol) and 34.8% → 32.6% (tobacco). Most of the shortfall is same-site
  rebranding — 83% of 2022 alcohol sites have *some* v4 risk object within 50 m
  — but that is an argument, not a measurement. The 2022 list is the wrong
  benchmark for a layer that is mostly inferred availability.
- **The alcohol layer is well calibrated without being verified:** 97.6% of it
  rests on OSM alone, worse than the third delivery. The tobacco layer is the
  best-corroborated file the project has received (37.7% 2GIS, 7.5% both) but
  **has no independent benchmark of any kind** — the licence registry holds no
  tobacco class.
- **27 pharmacies are false positives** in the combined layer, caught by the
  type rule; drop them before building any risk index.

### Russian twins of the third- and fourth-delivery reports

`analysis/v3/` holds a Russian twin (`*-ru.qmd`) beside each of the three English
v3 reports, and `analysis/v4/` holds one beside `eda-v4.qmd`. **Only the narrative prose and the figure/table captions are
translated** — every code cell is byte-identical to the English source, so the
rendered tables, axis labels and legends stay in English and the two language
versions are directly comparable figure by figure. `pixi run build-ru`
regenerates all four twins from the English sources and normalises their numbers
to Russian convention; re-run it after editing an English report rather than
patching a twin by hand. A new prose block or caption in an English source must
be added to that report's `scripts/build_ru_*.py` translation map, or the build
stops and names what it could not find.
