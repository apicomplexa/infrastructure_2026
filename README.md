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
│   └── raw/                     # original source data (read-only)
│       ├── objects_arkhangelsk_2026-06-28_enriched.csv   # main export, 7,228 objects
│       ├── objects_arkhangelsk_2026-06-28_health.xlsx    # health/risk-filtered subset
│       └── objects_3_districts_2022.xlsx                 # previous-stage result (3 okrugs)
├── docs/                        # English documentation extracted from the presentations
│   ├── infrastructure_rf.md         # the ИнфраструктураРФ program (current stage)
│   └── report_arkhangelsk_2022.md   # 2022 report summary (previous stage)
├── references/                  # original presentations (binary, source of docs/)
│   ├── infrastructure_rf.pptx
│   └── report_arkhangelsk_2022.pptx
├── analysis/
│   ├── eda.qmd                  # Quarto exploratory data analysis
│   └── eda.pdf                  # rendered report (deliverable)
├── scripts/
│   └── profile_data.py          # quick dataset profile
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

## Getting started

The project uses [pixi](https://pixi.sh) for dependency management (conda-forge).

```bash
pixi install            # create the environment from pixi.lock
pixi run profile        # print a quick profile of the dataset
pixi run eda            # render analysis/eda.qmd -> analysis/eda.pdf
```

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

See `analysis/eda.qmd` for the full dictionary and analysis.

## Key EDA findings (see `analysis/eda.pdf`)

- **7,228 objects**, 16 categories, 216 types — a general city inventory (retail
  dominates), much larger than the 2,528-object 2022 dataset.
- **Source confidence is thin:** only ~2.6% of objects are multi-source
  confirmed; ~89% are OSM-only. Absolute counts are lower bounds.
- **Geometry is complete** (100% coordinates, 98% addresses); *opening date* is
  unusable (<1%).
- **District assignment is broken:** ~71% of objects land in a single okrug
  (Oktyabrsky) — must be fixed before any district-level conclusions.
- A transparent heuristic already separates **health-supporting infrastructure
  from risk factors**, giving the next stage a concrete health-to-risk indicator.
