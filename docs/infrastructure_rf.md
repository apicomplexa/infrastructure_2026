# ИнфраструктураРФ — Program Overview

> English documentation extracted from the presentation
> `references/infrastructure_rf.pptx` (current project stage, 2026).
> Original slides are in Russian; this is a structured English summary.

## What it is

**ИнфраструктураРФ** ("InfrastructureRF") is a program for municipal analytics —
collection, verification, and visualization of data about urban infrastructure.
It monitors the key categories of the city environment: shops, pharmacies,
medicine, sport, catering, recreation areas, government institutions, and health
**risk factors**.

Pipeline: **Data sources → Data cleaning → Cross-check verification → Excel/CSV table → Dashboard.**

## Why the program exists

- **Infrastructure monitoring** — collect and keep up to date all city objects in one tool.
- **Accessibility analysis** — assess how evenly objects are distributed across city districts and *okrugs*.
- **Data for Excel and GIS** — ready structured tables for import into analytical and mapping systems.
- **Health and risks** — identify useful infrastructure and health risk factors for the population.
- **Municipal analytics** — support research and management activity at the municipal level.

## Data sources

The program combines several sources and cross-checks them against each other:

| Source | Role |
| --- | --- |
| OSM Overpass | OpenStreetMap geodata and objects |
| 2GIS Places API | Organizations and places (2GIS catalog) |
| 2GIS Geocoder | Address geocoding via 2GIS |
| Yandex Geocoder | Coordinates from addresses (Yandex) |
| Yandex Search API | Organization search (Yandex) |
| Google Places | Google Places and Geocoder API |
| Maps.co Geocoder | Alternative geocoding |

**Cross-check:** data from each source is compared with the others. If an object is
found in several sources, its confidence is higher. Contradictions are detected
and resolved automatically.

## Core features

- Collection of organizations by city or region from many sources.
- Automatic detection of territory boundaries by city name.
- Collection by *okrug* (supports Arkhangelsk okrugs and other cities).
- User-defined categories from a YAML configuration.
- Deduplication of objects coming from different sources.
- Cross-check across multiple sources simultaneously.
- Automatic backfilling of missing addresses and coordinates.
- Export to CSV, Excel, JSON, GeoJSON, and an HTML dashboard.

Export formats are compatible with Excel, Google Sheets, QGIS, ArcGIS, Tableau, and Power BI.

## "Health + risks" preset

**Useful infrastructure**

- Medicine — hospitals and clinics
- Pharmacies — pharmacies and pharmacy points
- Dentistry — dental clinics
- Diagnostics — laboratories and diagnostics
- Sport — fitness, pools, sections
- Parks and recreation — parks, squares, embankments

**Risk factors**

- Alcohol — wine shops, liquor stores
- Tobacco and vapes — tobacco shops, vape shops
- Fast food — fast food and snacks
- Bars — bars and pubs
- Hookah lounges — hookah and lounge bars
- Nightlife — nightclubs and entertainment

**Strict verification:** multi-level checks exclude false matches — cross-check
across sources, keyword filtering, and geo-verification of coordinates. Each object
passes strict selection before entering the final table.

## Export format

Each attribute is stored in a separate Excel cell; data is ready for GIS and
analytics. Representative columns:

`category_orig`, `type_orig`, `name_orig`, `city_orig`, `district_orig`,
`adress_orig`, `latitude`, `longitude`.

The enriched export additionally carries verification metadata (see the dataset
dictionary in [`../README.md`](../README.md)).

## Dashboard capabilities

- Total objects in the database
- Number of categories
- Share of objects with addresses
- Share of objects with okrugs
- Share of objects with coordinates
- Risk factors
- Charts by category
- Charts by okrug
- Searchable table

## Working with existing documents

The program works both with data collected from external sources and with
user-uploaded tables. All operations can be applied to any dataset:

- **Compare documents** — match two tables to find differences and additions.
- **Backfill addresses** — restore missing addresses and coordinates automatically.
- **Health filter** — extract health objects and risk factors from a general set.
- **HTML dashboard** — build an interactive web dashboard from an existing document.

Processing flow: **CSV / XLSX → processing (cleaning, verification, backfill,
filtering) → Excel report or HTML dashboard.**
