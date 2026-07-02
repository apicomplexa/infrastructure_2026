# Arkhangelsk Infrastructure Assessment (2022) — Report Summary

> English documentation extracted from the presentation
> `references/report_arkhangelsk_2022.pptx` (previous project stage, dated 24 May 2022).
> Original slides are in Russian; this is a structured English summary.

## Study

**"Assessment of municipal infrastructure from open-source data in the city of
Arkhangelsk."**

Part of the R&D project: *"Analysis and assessment of infrastructure for health
promotion and healthy-lifestyle support at the municipal level in Arkhangelsk
Oblast."*

- **Performer:** Northern State Medical University (NSMU), Arkhangelsk.
- **Customer:** National Medical Research Center for Therapy and Preventive
  Medicine, Moscow.
- **Authors:** A.V. Kudryavtsev, PhD (Head of the International Center for
  Scientific Competencies, NSMU; Associate Professor, Arctic health research
  group, UiT The Arctic University of Norway, Tromsø); N.A. Mitkin (Junior
  Researcher, International Center for Scientific Competencies, NSMU).

## Goal

Analyze and assess infrastructure that supports population health and healthy
lifestyles at the municipal level, using open data sources, to inform research
and management decisions.

## Choice of municipalities (okrugs)

1,815 residents of Arkhangelsk Oblast took part in the **ESSE-RF3** study in 2021
(1,643 in Arkhangelsk; 172 in three villages — Kholmogory, Uyma, Zaostrovye).
The **three territorial okrugs** of Arkhangelsk with the most study participants
were selected as the municipalities for infrastructure assessment:

- **Oktyabrsky**
- **Lomonosovsky**
- **Mayskaya Gorka**

Participant addresses were assigned to okrugs in three stages: (1) manual
assignment by two independent staff against the city map, (2) an automated
Python + Google Maps API script for geocoding and okrug assignment with Excel
output, and (3) reconciliation of manual vs. automated results using the Stata
statistical package, followed by manual correction of discrepancies.

## Data collection

Data on urban infrastructure were collected in **September–November 2021** from
open sources, complemented by official requests to three organizations. Seven
categories of infrastructure objects were mapped for each of the three okrugs:

1. **Medical organizations** (including private) — clinics, vascular centers,
   health centers, medical-prevention offices, multidisciplinary
   clinical-diagnostic centers, medical laboratories, pharmacies.
2. **Sport facilities** — workout areas, sports-and-fitness complexes, pools,
   stadiums, squares and park zones for running/walking/cycling, basketball and
   volleyball courts, fitness clubs, gyms, bike rentals.
3. **Grocery shops** — grocery stores, markets/fairs with fresh produce.
4. **Alcohol shops** — stores specializing in alcohol sales.
5. **Tobacco outlets** — tobacco and tobacco-product points, including hookah and
   hookah products, hookah lounges.
6. **Catering** — fast food / street food, restaurants, cafes, canteens.
7. **Industrial enterprises** — factories, energy complexes (hydro/thermal plants).

### Sources used

OSM (OpenStreetMap), 2GIS, Yandex.Maps, DvinaLand, city administration data, and
the Ministry of Agro-Industrial Complex and Trade of Arkhangelsk Oblast
(*Minagropromtorg AO*). Not every category used every source.

## Key results

### Table 1 — Object categories by okrug (2,528 objects total)

| Category | Oktyabrsky N (%) | Lomonosovsky N (%) | Mayskaya Gorka N (%) | Total N (%) |
| --- | --- | --- | --- | --- |
| Total | 1,078 (100) | 1,058 (100) | 392 (100) | 2,528 (100) |
| Medical organizations | 195 (18) | 158 (15) | 38 (10) | 391 (15) |
| Sport facilities | 142 (13) | 163 (15) | 97 (25) | 402 (16) |
| Shops | 189 (18) | 171 (16) | 73 (19) | 433 (17) |
| Alcohol shops | 65 (6) | 42 (4) | 18 (5) | 125 (5) |
| Tobacco outlets | 213 (20) | 197 (19) | 86 (22) | 496 (20) |
| Catering | 265 (25) | 326 (31) | 79 (20) | 670 (27) |
| Industrial enterprises | 9 (1) | 1 (0) | 1 (0) | 11 (0) |

### Table 2 — Objects by data source

**64% of all objects were found in OpenStreetMap.** Coverage by source (share of
the 2,528 objects): OpenStreetMap 1,626 (64%), 2GIS 1,404 (56%), city
administration 571 (23%), Minagropromtorg 576 (23%), Yandex.Maps 529 (21%),
DvinaLand 192 (8%). Cross-source coverage varied strongly by category — medical
and sport objects had high OSM/2GIS agreement, while alcohol and tobacco relied
more on administrative and ministry data.

## Relevance to the current stage

This 2022 stage established the **question** (how health-relevant infrastructure
and risk factors are distributed across Arkhangelsk okrugs) and a **manual/semi-
automated methodology** limited to three okrugs and 2,528 objects. The current
stage (see [`infrastructure_rf.md`](infrastructure_rf.md)) automates collection
and cross-check across 7+ sources and scales to the full-city 2026 export
(~7,228 objects) analyzed in `analysis/eda.qmd`.
