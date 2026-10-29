# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Data + exploratory analysis for a study of urban-infrastructure distribution in
Arkhangelsk (health-supporting infrastructure vs. health risk factors). Not an
application — a small analysis repo. Background is in `docs/` and `README.md`.

## Layout

Four top-level directories carry the work, split by *kind*, and the analysis and
report trees are split again by *delivery*:

- `analysis/v1|v2|v3|v4|egais|final/` — report **sources** only (`.qmd`). The Russian
  twin of a report sits beside its English original as `*-ru.qmd`.
- `reports/v1|v2|v3|v4|egais|final/` — rendered **PDFs**, written by the pixi tasks via
  `--output-dir`. **Git-ignored**: they are deliverables, rebuilt on demand.
  Never hand-edit anything here, and do not add them to the index.
- `src/arkhinfra/` — the importable **library**: `paths.py`, `v3_common.py`,
  `basecheck.py`, `match_2022.py`, `egais.py`, `v4_common.py`, `v4_egais.py`,
  `taxonomy_2022.py`.
- `packages/licmatch/` — a **standalone package**, not part of `arkhinfra`: the
  address-level record-linkage rule (toponyms, the three-term score, the two
  floors, selection), with its own `pyproject.toml`, tests and methodology
  write-up. It knows nothing about this study; `arkhinfra.v4_egais` adapts the
  two sources to it. Reach it with `arkhinfra.paths.ensure_licmatch_path()`,
  never by changing a report's setup-cell bootstrap.
- `scripts/` — **runnable** entry points only. `scripts/match_2022.py` is a thin
  launcher around `arkhinfra.match_2022`, which is a library module because a
  report imports it.

Nothing knows how deeply it is nested. `arkhinfra.paths` finds the repository
root by walking up for `pixi.toml` and defines every path from there; each report
opens its setup cell with the same four-line bootstrap that puts `src/` on
`sys.path`. **Keep that bootstrap byte-identical across reports** — it is what
lets a report move between directories, and what lets the Russian twins share
their code cells verbatim with the English sources. A report that needs a data
file should take it from `arkhinfra.paths`, never build a `../..` path by hand.

## Environment & commands

Dependencies are managed with **pixi** (conda-forge). There is no system Python —
always run tools through pixi:

- `pixi install` — create the env from `pixi.lock`
- `pixi run eda` — render the enriched report → `reports/v1/eda.pdf` (Quarto + XeLaTeX)
- `pixi run eda-health` — render the health-subset report → `reports/v1/eda-health.pdf`
- `pixi run eda-all` — render both
- `pixi run eda-ru` / `eda-health-ru` / `eda-all-ru` — same reports in Russian
  (`analysis/v1/eda-ru.qmd` → `eda-ru.pdf` / `eda-health-ru.pdf`)
- `pixi run eda-v2` — render the second-delivery report → `reports/v2/eda-v2.pdf`
- `pixi run build-ru` — regenerate the Russian v3 and v4 twins from the English
  sources and normalise their numbers (the `build_ru_*` → `ru_numfmt` sequence
  in one go)
- `pixi run parse-egais` — stream the 10.9 GB FSRAR licence registry into
  `data/processed/egais/egais_licences_arkhangelsk.tsv` (~6 min)
- `pixi run eda-egais` — render the licence-registry report → `reports/egais/eda-egais.pdf`
- `pixi run match-egais-v4` — join `data/raw_v4/` to the licence registry →
  `data/processed/v4_licences/v4_licences.csv` (+ `_summary.txt`); `--calibrate` appends the
  threshold ladder
- `pixi run check-yandex` — check the unlicensed v4 alcohol objects against
  Yandex Maps → `data/processed/v4_yandex/v4_alcohol_none_yandex.csv`; cached per object,
  so a re-run is free (`--limit N` for a trial, `--refresh` to re-read)
- `pixi run export-licences` — build the four deliverable spreadsheets of the
  join → `data/processed/deliverables/v4_licences_{alcohol,tobacco}_matched.xlsx`,
  `v4_alcohol_no_licence.xlsx` and `v4_brand_aliases.xlsx`; refuses to write if
  the re-run disagrees with `v4_licences.csv`
- `pixi run eda-v4` / `eda-v4-ru` — render the fourth-delivery risk-layer report
  → `reports/v4/eda-v4.pdf` (and its Russian twin)
- `pixi run build-taxonomy` — re-cut the v3 export into seven independent 2022
  classes → `data/processed/taxonomy_2022/taxonomy_2022.csv` (+ `_summary.txt`)
- `pixi run licmatch-test` — run the 130 unit tests of the record-linkage package
  (stdlib unittest; no data needed)
- `pixi run profile` — quick dataset profile
- `pixi run parse-egais-final` — the same streaming pass over the registry for
  the three final-delivery cities → `data/processed/egais/egais_licences_final.tsv`
  (3,420 rows, same 27 columns; its Arkhangelsk rows equal the city TSV). The
  parser reads the ZIP directly (`EGAIS_ZIP`)
- `pixi run match-egais-final` — final-delivery catering objects vs in-force
  catering licences → `data/processed/final_egais/final_egais.csv` (+ `_summary.txt`)
- `pixi run fetch-overture` — Overture Places snapshot for the three cities →
  `data/raw_alter_overture/overture_places_<release>.parquet`
- `pixi run fetch-foursquare` — FSQ OS Places snapshot for the three cities →
  `data/raw_alter_foursquare/fsq_places_<release>.parquet` (needs a saved
  Hugging Face token; the dataset is gated)
- `pixi run validation-final-ru` — render the Russian report on the final
  delivery's data quality and the confirmation method →
  `reports/final/validation-final-ru.pdf`; reads `data/processed/final_confirm/`,
  re-runs nothing. Its flowcharts are `{mermaid}` blocks, so the PDF build also
  needs a Chrome/Chromium Quarto can find (`quarto install chromium` on Linux)
- `pixi run confirm-final` — add «Подтверждено» / «Основания» to the final
  delivery → `data/processed/final_confirm/*_подтверждено.xlsx`; offline by
  default, `--yandex` queries Yandex Maps for the undecided objects (cached)

The EDA is parameterised (`dataset: enriched | health`, a `parameters`-tagged
cell) and needs **papermill** for `-P` injection. The health export has a
different (Russian) column schema — the `load_dataset()` loader in
`analysis/v1/eda.qmd` normalizes both to one canonical schema. `category_2022` is a derived column that
recodes objects into the 2022 seven-class health taxonomy (see `recode_2022()`).
- `pixi run python <script>` — run any Python in the env

PDF rendering needs a system LaTeX install (built with MiKTeX on Windows).
The workspace declares `win-64` and `linux-64`; the lock covers both.

## Data conventions

- Source data lives in `data/raw/` (first delivery, 2026-06-28), `data/raw_v2/`
  (second delivery, 2026-08-24), `data/raw_v3/` (third, 2026-08-31) and
  `data/raw_v4/` (fourth, 2026-09-03/04) and `data/raw_final/` (final, 2026-10-22…27), and is **read-only** — never modify it in place;
  write derived files elsewhere (e.g. a `data/processed/` you create).
- `data/processed/` (git-ignored) has **one subdirectory per pipeline**, each
  with a constant in `arkhinfra.paths` — take paths from there, never write
  into `PROC` itself:
  `egais/` (`PROC_EGAIS`, parse-egais), `match_2022/` (`PROC_MATCH_2022`),
  `taxonomy_2022/` (`PROC_TAXONOMY`, build-taxonomy and its audit / review /
  validation scripts), `v4_licences/` (`PROC_LICENCES`, match-egais-v4: the
  join, its summary, the learned brand pairs, the frozen `_before_rules` copy),
  `v4_yandex/` (`PROC_YANDEX`, check-yandex and its cache), `deliverables/`
  (`PROC_DELIVER`, the four XLSX of export-licences — the files handed on),
  `final_confirm/` (`PROC_CONFIRM`, confirm-final and its Yandex cache),
  `final_egais/` (`PROC_FINAL_EGAIS`, match-egais-final) and
  `_archive/` (`PROC_ARCHIVE`, superseded outputs nothing reads: the
  pre-2026-09-23 `--layer` files). File names keep their pipeline prefix.
- Only `data/raw/` is in git. `data/raw_v2/`, `data/raw_v3/` and `data/raw_v4/`
  are **git-ignored** for bulk, so a fresh clone renders the first-delivery
  reports and nothing else until those directories are restored from the project
  archive. A missing
  delivery surfaces as a `FileNotFoundError` from an `arkhinfra.paths` constant,
  not as a bug in the report.
- The main CSV is **semicolon-delimited, UTF-8 with BOM**. Read it as:
  `pd.read_csv(path, sep=";", encoding="utf-8-sig", low_memory=False)`.
- Category/type/district values are in **Russian**. The Windows console mangles
  Cyrillic on stdout — write Cyrillic output to a UTF-8 file and read it back
  rather than trusting terminal echo.
- Deliverable reports come in **English and Russian** (`analysis/v1/eda.qmd` /
  `analysis/v1/eda-ru.qmd` — parallel documents, keep them in sync). The English one
  maps Russian category/district names via the dicts in `eda.qmd`.

## Analysis / plotting notes

- Charts embed in the PDF as images, so keep Cyrillic figure labels in a font
  with Cyrillic coverage — **DejaVu Sans** (matplotlib default) works.
- Body text and LaTeX tables use the `Arial` main font (set in the qmd front
  matter) for Cyrillic. Titles/headings use the **sans** font (KOMA class), which
  by default lacks Cyrillic — for Cyrillic titles also set `sansfont: "Arial"`
  (done in `eda-ru.qmd`); with the default sans, keep `title`/`subtitle`
  ASCII-only.
- Figures are pinned with `fig-pos: "H"`: floating figures corrupt `longtable`
  page-breaking (rows silently clipped past the page bottom).
- Wide tables (many columns) must be emitted as **markdown** (`to_markdown()`,
  needs `tabulate`) — a pandas `Styler` becomes a fixed-width LaTeX table whose
  header row overflows the page. Keep ≤ ~10 short-headed columns; put long names
  (districts) in rows, not column headers.
- The district map draws a **contextily** basemap (CartoDB Positron,
  `crs="EPSG:4326"`). Tiles cache to `data/tile_cache/` (gitignored), so the
  first render needs internet; offline the code falls back to a plain scatter.

## Second delivery (`data/raw_v2/`)

Three artefacts, all analysed by `analysis/v2/eda-v2.qmd` (English only — there is
deliberately no Russian twin for this report):

- `сравнение_документов_*.xlsx` — record comparison of the 2022 document (2,293
  rows) against a new 2026 export limited to the three 2022 okrugs (5,257 rows).
  **The 2026 export is not a sheet of its own**: rebuild it by concatenating the
  `Документ 2: *` column block from `Совпадения` + `Вероятные совпадения` +
  `Только в документе 2` and de-duplicating on `Строка в документе 2`.
- `итоги_сравнения_3_округа.csv` — per-okrug summary. **Semicolon-delimited**,
  UTF-8 with BOM, like the main CSV.
- `ARKTMED_*.xlsx` — municipal indicator panel, 28 indicators × 6 years. City
  level only, no okrug detail.

`eda-v2.qmd` reuses `recode_2022()` verbatim from `eda.qmd` — **keep the two
copies in sync** so the reports stay comparable.

Cyrillic in inline code/verbatim needs `monofont: "Consolas"` in the front
matter; without it the default mono font silently drops Cyrillic glyphs.
Pandoc pipe tables cannot hold line breaks (`
ewline` and `<br>` are both
dropped on the way to LaTeX) — use a list instead.

## Third delivery (`data/raw_v3/`, 2026-08-31)

**Replaces the second delivery rather than extending it** — both artefacts
`eda-v2.qmd` is built on (the comparison workbook and the per-okrug summary) are
withdrawn. Three files, analysed by two English-only reports:

- `infrastructure_архангельск_*_quality_excel.csv` — the city-wide export, 7,263
  objects × 22 columns. Same schema as `raw/…enriched.csv` minus
  `enrichment_comment`. Semicolon-delimited, UTF-8 with BOM.
- `export_base_*.xlsx` — commercial directory dump, 10,557 records × 25 fields in
  a **third taxonomy** (`Рубрика`/`Подрубрика`/`Тип подрубрики`). See the loader
  caveats below.
- `ARKTMED_*.xlsx` — rebuilt indicator panel, 22 indicators / 65 rows.

Reports and helpers:

- `analysis/v3/eda-v3.qmd` → `reports/v3/eda-v3.pdf` (`pixi run eda-v3`) — descriptive EDA:
  provenance, raw groups, 2022 recoding, maps, the commercial dump, ARKTMED.
- `analysis/v3/eda-v3-validation.qmd` → `reports/v3/eda-v3-validation.pdf`
  (`pixi run eda-v3-val`) — independent re-check against the 2022 benchmark.
- `src/arkhinfra/v3_common.py` — **shared** loaders, normalisers and `recode_2022()`
  for both reports. Import it rather than copying code.
- `src/arkhinfra/match_2022.py` (`pixi run match-2022`, via the
  `scripts/match_2022.py` launcher) — the independent matcher; writes to
  `data/processed/match_2022/`. `eda-v3-validation.qmd` imports it, so edits to it change
  that report as well as the CLI output.
- `docs/crosswalk_2022.md` — the 2026 → 2022 taxonomy crosswalk and its defects.
- `analysis/v3/eda-v3-basecheck.qmd` → `reports/v3/eda-v3-basecheck.pdf` (`pixi run eda-v3-base`)
  — the commercial directory profiled and re-matched. It exists because
  `eda-v3-validation.qmd` reports the directory corroborating only **3.6 %** of
  the export, which is a **join artefact**: `v3_common.norm_address` strips the
  city with `\bархангельск\b`, whose word boundary never matches "Архангельск**ая** область",
  so the administrative prefix on 45.8 % of directory addresses survives
  normalisation; on top of that the join used exact name equality and blocked on
  the address alone. Re-matched (distance block, fuzzy name ≥ 0.90) the real rate
  is **≈ 32 %**. The corrected normalisers live in `src/arkhinfra/basecheck.py`, kept
  **deliberately separate** from `v3_common.py` so the older reports keep
  producing what they produced before — do not merge them without re-rendering
  and re-checking every v3 report. `scripts/build_ru_basecheck.py` builds its
  Russian twin. The 3.6 % figure still stands in
  `reports/v3/eda-v3-validation.pdf`; treat it as superseded.
- `analysis/v3/eda-v3-ru.qmd` / `eda-v3-validation-ru.qmd` → the Russian twins
  (`pixi run eda-v3-ru` / `eda-v3-val-ru` / `eda-v3-all-ru`). **Only the prose
  and the figure/table captions are translated** — every `{python}` cell is
  byte-identical to the English source, so the rendered tables and charts stay in
  English. Their front matter needs `sansfont: "Arial"` (KOMA sans has no
  Cyrillic); their code cells need no adjustment at all, since the setup-cell
  bootstrap locates the repository root on its own.
  All three v3 reports have a Russian twin, the basecheck one included
  (`pixi run eda-v3-base-ru`), as does the v4 report.
  `scripts/build_ru_v3.py` regenerates `eda-v3-ru.qmd` from the English source:
  after editing `analysis/v3/eda-v3.qmd`, re-run it rather than hand-patching the
  twin, and add any new prose block to its translation map. Follow it with
  `scripts/ru_numfmt.py`, which puts prose numbers into Russian convention
  (decimal comma, space for thousands) in all three twins — it is idempotent, and it
  deliberately skips the YAML front matter, where `fig-width: 7.2` must keep its
  decimal point.

### Loader gotchas for the third delivery

- `export_base_*.xlsx` **cannot be opened by openpyxl** — its `styles.xml` has a
  fill entry that fails openpyxl's type check. `load_export_base()` re-zips the
  file in memory with a minimal stylesheet first.
- Its first data row **repeats the header labels**; drop it (10,557 real records,
  not 10,558).
- One of its header cells (`Район города`) is stored **decomposed** — `и` plus a
  combining breve instead of `й` — so indexing that column by its printed name
  raises `KeyError` until the header is NFC-normalised. Data cells are NFC.
- Its `Координаты (широта, долгота)` column is **space-separated despite the
  name**, and rounded to 3 decimals (≈ ±55 m at this latitude).

## Fourth delivery (`data/raw_v4/`, 2026-09-03 / 2026-09-04)

**Not a fourth survey — a risk-attribution layer over the third.** Two CSVs, one
per risk factor, that re-tag objects already in `V3_CSV`: 100 % of the 749
tobacco rows and 99.8 % of the 945 alcohol rows sit within 100 m of an existing
v3 object, and 94-98 % of their `matched_source_ids` are v3 ids. It adds no
geographic coverage, only a judgement about which existing objects plausibly
sell alcohol or tobacco. It does **not** withdraw the third delivery — the two
are used together, and `eda-v4.qmd` loads both.

- `analysis/v4/eda-v4.qmd` → `reports/v4/eda-v4.pdf` (`pixi run eda-v4`), with
  the Russian twin `eda-v4-ru.qmd` → `eda-v4-ru.pdf` (`pixi run eda-v4-ru`).
  Same rule as the v3 twins: **prose and captions only** are translated, every
  `{python}` cell is byte-identical, and the front matter needs
  `sansfont: "Arial"`. `scripts/build_ru_v4.py` regenerates it — after editing
  the English source, re-run `pixi run build-ru` rather than hand-patching the
  twin, and add any new prose block to its translation map.
- `src/arkhinfra/v4_common.py` — loaders, evidence/trade tiers, the corrected
  recoder, `parse_hours()`, and the two-way `corroboration()` against EGAIS.
  Kept **separate from `v3_common.py`** on the same principle as `basecheck.py`
  and `egais.py`; what is shared is imported, not copied.
- `docs/v4_source_notes.md` — the field-level write-up.

The schema claim holds as a **container** and fails as a **vocabulary**: the 22
column names, their order and their dtypes are identical to v3, but
`category_orig` / `type_orig` carry a **fourth taxonomy** sharing no value with
any earlier delivery. Two consequences:

- **`recode_2022()` silently drops 698 of the 749 tobacco rows.** It tests the
  blob for the stem `табак`; every new label spells it `табач-` (`Табачная и
  никотинсодержащая продукция`, `Возможная продажа табачной продукции`), which
  does not contain `табак`. Same class of defect as the `GROCERY_TYPES` case
  mismatch, and just as silent. Fixed in `v4_common.recode_2022_v4()` **only** —
  do not port it into `v3_common` without re-rendering and re-checking every v3
  report.
- **82 % of the delivery is the `Возможная …` (inferred) tier** — the object's
  type is compatible with selling the product, which the contractor's own
  `verification_comment` says *требует отдельной проверки*. Always report the
  `Direct` and `Inferred` tiers separately; a merged headline count is not
  defensible.

Other traps:

- The two files **overlap on 359 coordinates**, so a site count must dedupe
  (`load_v4()` / `sites()`): 1,694 rows → **1,335 distinct sites**.
- `opening_hours_orig` holds **two incompatible encodings in one column** — a
  2GIS JSON object and an OSM `opening_hours` string. 42 % JSON in the tobacco
  file, 2 % in the alcohol file. Use `v4_common.parse_hours()`. The trap exists
  in v3 too (10.7 % JSON).
- For alcohol, split **off-trade** from **on-trade** before any comparison: the
  licence registry licenses them separately, and only off-trade is comparable
  with a shop count.
- **27 records match a pharmacy** and are false positives for both risk factors.

## Alternative source: the FSRAR licence registry (`data/raw_alter_egais/`)

Not a commissioned delivery — the state consolidated register of licences,
downloaded as open data (2026-07-01 snapshot). One **10.9 GB XML**, 1,660,448
records nationwide, kept as its 308 MB ZIP (the parser streams out of it), git-ignored for bulk like the v2/v3 payloads.

- `scripts/parse_egais.py` (`pixi run parse-egais`) reduces it to
  `data/processed/egais/egais_licences_arkhangelsk.tsv` — 2,100 rows × 27 columns.
  It **streams**: 16 MiB chunks cut on `</row>`, and only segments whose raw
  bytes already contain "Архангельск" reach the XML parser. Never load this
  file whole. A full pass takes ~6 minutes.
- `src/arkhinfra/egais.py` — loader, Russian-date parser, street normaliser and
  the okrug recovery. Kept **separate from `v3_common.py`** (different source,
  different grain); what is shared is imported from `v3_common`, not copied.
- `analysis/egais/eda-egais.qmd` → `reports/egais/eda-egais.pdf`
  (`pixi run eda-egais`). English only; no Russian twin yet.
- `docs/egais_source_notes.md` — the full field-level write-up.

Two things about this source govern how it may be used:

- **It holds alcohol licences, not tobacco.** The regulator covers both, the
  data has no tobacco class at all. It is a risk-factor layer, not a tobacco
  source.
- **It is a register, not a list of open outlets.** Only 585 of 2,100 city rows
  are in force. Always filter `status` / `is_active` before counting.

### Joining the registry to the fourth delivery

`src/arkhinfra/v4_egais.py` (`pixi run match-egais-v4`) answers the object-level
question `v4_common.corroboration()` deliberately stops short of: *which* licence
sits at this object's address, and is it in force. **The rule that does the
matching lives in `packages/licmatch/`**, a standalone package with no knowledge
of this study — `v4_egais.py` is its adapter: two `prepare_*()` functions, the
licence columns, the evidence tiers and the summary tables. Change the rule
there and re-run `pixi run licmatch-test`; change what a match *means* here.
The methodology (weights, both floors, both routes, the calibration and the
forbidden readings) is `packages/licmatch/docs/METHODOLOGY.md`. It writes
`data/processed/v4_licences/v4_licences.csv` — the whole v4 export plus `licence_status`
(`Active` / `Archived` / `Taken` / `Other chain` / `Other trade` / `Not in registry`), the chosen licence's number, dates,
activity class, holder and INN, the three score components, and the count of
distinct licences at the address. `docs/v4_egais_match.md` is the write-up.

`analysis/v4/licences-v4-ru.qmd` → `reports/v4/licences-v4-ru.pdf`
(`pixi run licences-v4-ru`) presents that result: the match summaries as
formatted tables, the full list of alcohol objects with no licence at their
address, and the tobacco no-licence counts by object class. **Russian-only, and
it re-runs nothing** — it reads `data/processed/v4_licences/v4_licences.csv`, so its numbers
are by construction the ones in `v4_licences_summary.txt`; re-run
`pixi run match-egais-v4` first if the join parameters change. It has no English
twin and is not generated by `scripts/build_ru_v4.py` — do not add it there.

- Pairs are scored `0.50 * address + 0.20 * name + 0.30 * distance`, cut at
  100 m, and the **address term compares parsed toponyms, not strings** — the
  two sources write "Северной Двины Набережная, 55" and "набережная Северной
  Двины, 55" for the same door. Street type, light-stemmed street name, house
  and block are compared field by field.
- Acceptance carries a **second floor, `addr_min = 0.72`**, on the address term
  alone. Without it the neighbouring building matches: inside 100 m it differs
  only in the house number, and the registry's DMS-rounded coordinates (~31 m of
  latitude per arcsecond) cannot tell the two apart. `--addr-min 0` restores the
  plain weighted sum.
- The registry names the licence **holder**, the export the **shop**, so the
  name term is a tie-breaker only; the nine unambiguous chains (Тандер→Магнит,
  Агроторг→Пятёрочка, Альбион-2002→Бристоль, …) are mapped in `BRAND_ALIASES`,
  and further fascia → holder-INN pairs are **learned from the data**
  (`learn_brands()` → `data/processed/v4_licences/v4_brand_aliases.csv`; rule in
  `licmatch.brands`): a vote over addresses with the name term off, lift over
  the holder's base rate, competition for the outlet, a leave-one-site-out
  prior, and a franchise rule guarded by a holder-side test (≥ half the
  holder's outlets at the fascia's addresses — the rule was introduced for
  Петровский). Run of 2026-09-23: 19 pairs over 12 fascias — Союз→Ритейл,
  Афанасий→Кедр, five Петровский operators among them. A pair that passes only
  with all its voting addresses (`loo_accepted` False) does not score the name
  term at them; a pair resting on archived licences only (`feeds_conflict`
  False: Дисма→Конус, the Долина pairs) bars nobody. Export spellings of one
  fascia are folded in `FASCIA_SPELLINGS`. A learned pair is a hypothesis;
  `BRAND_REVIEW` in `v4_egais.py` is where a person overrules one (empty so far). **Clustering objects in "holder space" was
  tried and fails** — an object's vector describes its neighbours (median 2
  non-zero of ~480), chains split into dozens of clusters; aggregate by fascia.
  A generic fascia («Продукты») has its name term dropped, not scored 0.
- 47 % of registry rows have no usable coordinate and are reached by a stricter
  address-only route, labelled `licence_match_method = address`.
- **A licence number belongs to the organisation, not the shop** (Тандер: one
  number, 100+ outlets), so the unit is the **outlet** — holder INN @ parsed
  address (`outlet_units()`). Rules on top of unchanged admission decide which
  licence an object holds (`join()`):
  - **One outlet per shop**, greedy, strongest claim first, across both risk
    files. A **shop** is an entity (`entities()`): records within 50 m naming
    the same brand. 1,694 records make 1,197 entities, and records of one shop
    share its outlet. The loser is `Taken`; `licence_claimed_by` names the
    winner and `licence_claim_margin` says by how much.
  - **The licence must permit the trade**: off-trade ↔ retail, on-trade ↔
    catering, hookah lounges on-trade. The rule gives way where the name says
    the holder is the shop (alias or string ≥ 0.80); `licence_trade_match`
    marks those rows. Otherwise the object is `Other trade`.
  - **The known brands rule pairs out both ways**: a known chain holds only its
    own holders' licences (franchises exempt), and a known chain's licence goes
    only to that chain or to a name matching it at ≥ 0.80. Otherwise the object
    is `Other chain`.
  - **An archived licence is the object's own only if the name agrees**, where
    an in-force licence of its trade stands at the address. Otherwise it
    belongs to the previous tenant.

  Before 2026-09-23 each object chose on its own and 158 alcohol outlets were
  quoted by 2–5 rows of different shops. The first version of these rules still
  quoted 36 chain objects with an unrelated company's old licence, until the
  project critic caught it. `licence_status` describes
  the object's own licence; `licence_n_*` / `licence_all_nos` still describe the
  whole address. `--no-learn` / `--no-exclusive` / `--no-brand-rule` switch the
  rules off one at a time.
- Result: **80.6 % of v4 records** have a licence *at their address* (unchanged),
  **51.4 % (870) hold one of their own** — alcohol 350 Active / 155 Archived /
  64 Taken / 114 Other chain / 83 Other trade / 179 Not in registry. **97.7 % of
  the 442 active off-trade retail licences** have a v4 object at their address
  (71.9 % are *held* by one) — the fourth delivery does account for licensed
  alcohol retail. Quote which headline you mean.
- **The tobacco layer is matched against the same alcohol licences**, because
  the registry has no tobacco class to match against, and every such row is
  labelled `licence_evidence = probable`: the object itself holds a retail
  alcohol licence in force, alcohol and tobacco are sold across the same
  counter, so the tobacco tag is *likely* — never verified. `weak` marks a
  tobacco row whose own licence is archived or non-retail, `direct` is alcohol
  rows only.
  `licence_evidence_note` repeats this in one Russian sentence in the file
  itself. 290 of 749 tobacco rows are `probable` (503 before 2026-09-23:
  specialised tobacco shops fell from 80 to 4 of 100, because every one had been
  quoting the alcohol licence of the supermarket or liquor chain beside it);
  **do not report that as a tobacco verification rate, and never sum `direct`
  and `probable`.**
- `--layer tobacco` / `--layer alcohol` writes one layer to its own CSV
  (`v4_tobacco_licences.csv`); both are always scored, the flag only selects
  the view.

The published **XSD does not describe the published file** — it declares
`Details/Detail` with attributes, the file delivers `data/row` with child
elements, and names differ (the registry's own `выезного` typo included). A
parser written from the documentation returns nothing.

### The manual check of the unlicensed alcohol rows (`v4_yandex`)

No licence of its own is not "sells no alcohol", so the 440 alcohol rows in
`STATUS_NO_OWN` (179 `Not in registry`, 64 `Taken`, 114 `Other chain`, 83
`Other trade`) are a queue for manual checking. `src/arkhinfra/v4_yandex.py`
(`pixi run check-yandex`) works that queue against **a third directory**: for
each object it issues the query a person would type — name, then address, map
centred on the object's coordinate — and reads the organisations off the page
Yandex Maps renders server-side. Result:
`data/processed/v4_yandex/v4_alcohol_none_yandex.csv`, one row per object, with the mark,
the search URL it came from, and what Yandex actually returned.

- Marks are `present` / `closed` / `ambiguous` / `absent` / `error`, never a
  bare yes-no. `closed` is Yandex's own "Больше не работает" and explains a
  missing licence rather than contradicting the tag; `ambiguous` is an object
  whose fascia *is* a trade descriptor ("Столовая", "Кафе") standing at an
  occupied address, where no name can decide anything.
- A candidate is accepted within 150 m (60 m for a generic fascia such as
  "Продукты") at name similarity ≥ 72 over `licmatch.fascia_name` keys.
  `token_sort_ratio`, **not** `token_set_ratio`: the set variant scores a
  subset 100 and reads "Бакарица" into "МУК ИЦКЦ филиал Бакарица" 12 m away.
- The query repeats "Архангельск" although the URL path and `ll` already carry
  the city — without it Yandex answers "Елена, улица Адмирала Макарова, 38"
  with a garden plot near Kirov, and an address with no house number with a
  street in Baku.
- Every answer is cached in `data/processed/v4_yandex/v4_yandex_cache.jsonl`, keyed by
  `site_key`, so a re-run costs no requests, an interrupted run resumes, and
  the report never reaches the network. Delete a line to re-check that row;
  `--refresh` re-reads everything. **The cache is a snapshot**, and every row
  carries the date it was read.
- `licences-v4-ru.qmd` reads that CSV and prints the mark as a hyperlink in the
  object list — the mark *is* the link to the query it came from.
- **A Yandex hit is not a licence.** The directory carries no licences at all:
  `present` says the door exists, never that alcohol is sold legally behind it.
  The check runs on the alcohol layer only — the tobacco layer has no registry
  to fail against, so "no licence" is not a signal there.
- Runs of 2026-09-22/23, all 440 pages read: **155 `present`, 127 `closed`,
  13 `ambiguous`, 145 `absent`.** Over a quarter of the queue has simply closed,
  which is the commonest reason a licence search comes back empty — those rows
  are stale, not mis-tagged. `Other chain` is 44 % closed (50 of 114): mostly
  independents a chain has since replaced at the same door. **`absent` is
  inflated by transliteration** (Millstream / Мильстрим 4 m away) — read
  `yandex_nearby` first. `docs/v4_yandex_check.md` is the write-up.

### The deliverable spreadsheets (`v4_export`)

`v4_licences.csv` is the working file — 64 English columns in source order, one
row per v4 record matched or not. `src/arkhinfra/v4_export.py`
(`pixi run export-licences`) turns it into four XLSX files a reader can *check
by eye*, in `data/processed/deliverables/`:

- `v4_licences_alcohol_matched.xlsx` — 505 rows, alcohol objects holding a
  licence of their own;
- `v4_licences_tobacco_matched.xlsx` — 365 rows, the tobacco layer against the
  same alcohol licences (290 `probable`, 75 `weak`);
- `v4_alcohol_no_licence.xlsx` — the 440 alcohol rows with no licence of their
  own, with their status, who took the outlet, the Yandex check **and the best
  candidate the join refused**;
- `v4_brand_aliases.xlsx` — every candidate fascia → holder pair (328) with its
  evidence, the 19 in use first; its review column is for a person.

- **Columns are paired, not blocked**: the object's name sits beside the licence
  holder's, its address beside the outlet address, its coordinate beside the
  registry's, and each pair is followed by the term it scored — then the three
  terms, then the total. Checking a row needs no horizontal scrolling.
- Each file carries a **«Как читать» sheet**: every column whose meaning is not
  its name, the formula with its weights, both floors, and what may not be
  claimed (`direct` + `probable` never sum; a matched address is not a matched
  object; a Yandex hit is not a licence).
- The no-licence file's **«Почему не принята»** names the floor the best
  candidate failed for `Not in registry` (of 179: 78 no candidate, 48 both
  floors, 52 the address floor alone — a licence is *there*, the house number
  disagrees — 1 the score floor alone), and for the other statuses says the
  floors were not the reason and names the rule that was.
- The near-miss selection **does not prefer active licences** the way the
  accepted one does: its question is how close the row came, so the plain
  best-scoring candidate is the honest answer.
- **The script re-runs the join and refuses to write if it disagrees** with
  `v4_licences.csv` on `licence_status` or `licence_no`. The re-run exists only
  to reach two things the CSV does not keep — the registry's own coordinate and
  the losing candidate — and the guard is what keeps the deliverable and the
  report the same numbers.
- `licence_products` is deliberately absent: the registry publishes the element
  empty in all 2,100 Arkhangelsk rows, and the legend says so.

## Final delivery (`data/raw_final/`, 2026-10-22 … 27)

The project's closing export: **one XLSX per city and object class**, three
cities — Архангельск, **Северодвинск**, **Новодвинск** — and so far catering
(`*_общепит.xlsx`) only. Listed by `arkhinfra.paths.final_files()`, never named,
so a class added later is picked up. Git-ignored like the other payloads.
Sheets: `data` (the deliverable: `OSM`, `GIS`, `Яндекс: найдено`,
`Arkh_admin` source flags, then the object, then the contractor's Yandex
check), `original_data`, `quality`, and summaries.

- **A row is not an object.** One sign at one point is repeated under every
  type it might be (кафе / ресторан / столовая / кулинария): Arkhangelsk 2,500
  rows → 1,141 objects, Severodvinsk 905 → 467, Novodvinsk 195 → 80. Count
  objects (`final_confirm.load()` → `entity`), not rows.
- **`quality` is not row-aligned with `data`** — same counts, different order;
  joined by position its `providers` disagree with OSM/GIS on most rows. It
  joins exactly through `original_data` (row-aligned with `data`) on
  `type_orig, name_orig, adress_orig, latitude, longitude`; `load()` checks
  the join is 1:1 and agrees with OSM/GIS on every row.
- **The contractor's Yandex «Найдено» confirms an address + category, not the
  object** — the name matched in 190 of 407 Arkhangelsk rows («Tupperware»
  found because «Йоко суши» shares the building). Re-judged by name from
  `Яндекс: название`; never count the raw flag. Severodvinsk also has 238
  rows «Не проверено».
- The contractor's merge **missed OSM↔2GIS pairs** («1234» / «1234, кофейня»
  14 m apart); `relink()` lends a provider across ≤ 50 m (20 m for a nameless
  fascia) when the names agree, and says which record lent it.
- The catering class holds **non-catering objects** (a construction firm, Fix
  Price, «Магазин овощей и фруктов»). Confirmation says the object *exists*,
  not that it is catering.

`src/arkhinfra/final_confirm.py` (`pixi run confirm-final`) writes, per file, a
copy with **«Подтверждено»** (1 = ≥ 2 independent sources among OSM, 2GIS,
Yandex, Overture Places, Foursquare, the city register `Arkh_admin`, and an own FSRAR
catering licence when `final_egais` has run) and **«Основания»** (per source: the OSM/2GIS record URL,
the Yandex card, the lending record, the licence; after « || » what was looked
for and not found) in front, the evidence columns appended, and a
«Подтверждение» sheet with the legend and counts. Raw files are never touched;
the contractor's own columns are left as delivered. Yandex is one source
however reached; a card marked «Больше не работает» is never counted. Our
Yandex check reuses `v4_yandex` (city-aware `search_url`, `generic=` override
in `judge`); its cache is `data/processed/final_confirm/final_yandex_cache.jsonl`.
Severodvinsk needs Yandex region path `10849/severodvinsk`; `/maps/search/`
without a region answers 404; Novodvinsk resolves through Arkhangelsk's path.
Run of 2026-10-29 (all 1,004 undecided objects read, 0 errors, then rebuilt
offline with every source, Foursquare included): **Архангельск 803 / 1,141
objects confirmed (70 %), Северодвинск 373 / 467 (80 %), Новодвинск 50 / 80
(63 %)**; our
Yandex marks 500 present / 130 closed / 25 ambiguous / 349 absent. Read the
summary file for numbers. ~17 % of objects are non-catering by name
(«магазин», «компания», …) and are confirmed *more* often (87 % vs 69 %).

**The licence registry as a source** (`src/arkhinfra/final_egais.py`,
`match_catering()`): an in-force **catering** licence of the object's **own** at
its address. Stricter than the v4 join — the name must always agree, with the
holder or with the venue name the registry writes into the premises text of
`outlet_address` («ресторан "Йоко"»); an address alone never confirms (malls,
hotels, food courts). Word-level names with transliteration (`names_agree`),
generic venue words excluded, one outlet (INN @ address @ venue) per venue, no
brand learning (catering chains are franchises). Run of 2026-10-29: 58 of
1,688 objects (Архангельск 34, Северодвинск 18, Новодвинск 6). Read
`egais_match`, never a non-empty `egais_licence_no`: near-misses carry the
licence their `egais_note` talks about.

**Overture Places** (`pixi run fetch-overture` →
`data/raw_alter_overture/overture_places_<release>.parquet`, read-only after
download; release 2026-10-21.0: 2,214 places in the three cities' box — Meta
1,523, AllThePlaces 480, Foursquare 200) is the one open POI layer independent
of all three directories: its places theme has **no OSM**. All places are
matched, not only catering (existence does not need Overture to agree on the
kind): ≤ 150 m (60 m generic), confidence ≥ 0.5, name ≥ **85** — stricter than
Yandex's 72 because AllThePlaces is chains and a same-brand branch is often
nearest. Meta rows are Facebook pages, unmaintained from Russia since 2022 —
the weaker kind; the dataset is named in «Основания». The env has no pyarrow,
so parquet is read with duckdb. The Yandex organisation-search API is not an
independent source and forbids storing answers.

**Foursquare OS Places** direct (`pixi run fetch-foursquare` →
`data/raw_alter_foursquare/fsq_places_<release>.parquet`; release 2026-10-15:
15,788 places in the box against Overture's 200 FSQ rows). Since 2025-10 a
**gated** Hugging Face dataset — the public S3 bucket is empty; the run needs
an account that accepted the terms and a token saved by `hf auth login`
(DuckDB's `credential_chain`), never one in the repo. The files are sorted
spatially, so the box reads 2 of 776 row groups (~30 MB of 11.6 GB) — probe
with `parquet_metadata` before pointing it at a new box. **The layer is
stale here**: most records were last refreshed 2013–2016, so only a record
refreshed since `FSQ_FRESH` (2022) and without `date_closed` counts; older
matches are listed after « || », not counted. An Overture place built from
Foursquare alone counts as Foursquare, never as a second source.
`exclusive()` gives one Overture / FSQ record to the nearest claiming object
and those within 50 m of it (the export's own unmerged duplicates), never to
a same-name branch farther off (Hindi, Троицкий 61 vs 67). Run of 2026-10-29:
261 objects counted, 184 found but stale/closed.

**«Общепит?» — is the object catering at all** (`final_confirm.profile()`),
the third front column. Four descriptions of the object's kind, none of them
the contractor's class: the 2GIS descriptor after the comma in the name (or
the bare name), Yandex's rubric for the very card our check matched (from the
cached page title), the FSQ category of the found record (stale ones too — a
kind does not go stale) and Overture's. `да` / `нет` / `противоречие` /
`автомат` / `нет данных`, reasons in «Общепит: основания». Regex order is the
rule: vending first, then `PROFILE_NOT_PLACE` (опт, оборудование, кафедра —
«кафедра» starts with «кафе»), then catering words, then shop/company words.
«Служба доставки» is neutral (in this class it is sushi and pizza). Run of
2026-10-29 over 1,688 objects: 996 да, 351 нет, 33 противоречие, 79 автомат,
229 нет данных; 294 of the 351 «нет» are *confirmed* — they exist, as shops.
A flag for review, never a filter applied to the deliverable.

**ФГИС Меркурий / Цербер is not reachable without an account**: the public
parts are a VSD check by code and a site lookup by GUID; the other public
Cerberus registers (export, pesticides, transit) hold no catering. Searching
other enterprises needs a Mercury.ХС login of a registered business.

## The 2022 taxonomy re-cut (`taxonomy_2022`)

**A rule, not a model** — no probabilities, no training, nothing to calibrate.
`v3_common.recode_2022()` asks "which *one* 2022 class is this?" and resolves it
through `np.select`, whose priority order discards every further class. The 2022
commission asks "which of the seven lists would this object appear on", so
`src/arkhinfra/taxonomy_2022.py` emits **seven independent booleans** over the
7,263-row v3 export plus, for each, an `evidence` column naming the field that
carried the object in (`category` / `type` / `name`). The three are **ranked**:
where `category_orig` exactly names one of the seven classes, that assertion
outranks anything inferred from `type_orig` or the fascia, and a `type`- or
`name`-level flag for a *different* class is suppressed.

- `pixi run build-taxonomy` → `data/processed/taxonomy_2022/taxonomy_2022.csv` (7,263 × 40)
  and `taxonomy_2022_summary.txt`. Read the summary for numbers; do not quote
  them from anywhere else.
- `docs/taxonomy_2022_notes.md` — the field-level write-up.
  `docs/classifier_design.md` §10 is the analysis it implements.
- Kept **separate from `v3_common.py`** on the same principle as `basecheck.py`,
  `egais.py` and `v4_common.py`. What is shared is imported, never copied. **Do
  not merge the two rules**, and do not port these fixes into `v3_common`.

Three defects, all found on the 84 % of the export that no evaluation in the
design document reaches. Each moves published numbers city-wide:

- **D1 — `Овощи и фрукты` → `Other`, 51 objects.** `GROCERY_TYPES` holds the 2022
  spelling `фрукты-овощи` and `Series.isin` is exact. Fixed generally, by a
  word-bag type key (`norm_type` / `_type_key`), not by adding the one string.
- **D2 — ~30 % of `Sport` was not a sport facility.** The old rule searches a blob
  *including* `category_orig` for the stem `спорт`, so the category `Досуг и
  спорт` carried **63 saunas** in (the 2022 benchmark labels a sauna `Общепит`);
  plain substring search also took 8 passport offices (па-*спорт*-ный) and
  5 haulage firms (тран-*спорт*-ная). Now stems match on word boundaries over
  `type_orig` / `name_orig` only, categories match exactly, and sport retail
  (20 objects) has its own flag `is_sport_retail` — a shop is not a facility.
- **D3 — 35 rows of the export carry the wrong `type_orig`.** They pair
  `category_orig = Точки продажи табака` with `type_orig = Продуктовый магазин`,
  and their names settle it — *Азбука дыма*, *SmokeArh, табачная лавка*, *Дымный
  папа*, *Kiss My Vape*, *Oblako, магазин дымной продукции*. They are tobacco and
  vape shops, never groceries. **This is not a defect in the recoder** — the old
  rule's priority order returned the right answer for them *by accident*, which is
  what kept the defect hidden; the seven flags exposed it, and the evidence
  hierarchy then keeps them out of Grocery. Read §10.3 of
  `docs/classifier_design.md`, not the earlier "35 invisible grocery shops"
  reading, which is withdrawn.

Effect: **Sport 358 → 255**, **Grocery shops 811 → 867**, Medical 677 → 671,
Catering 625 → 633, Industrial 25 → 28, Alcohol 110 → 109, Tobacco unchanged at
60, no class 4,597 → 4,647. Only 7 objects carry two classes (none carries
three). **The three rendered v3 reports still carry the old rule's numbers, and
that is deliberate — do not re-render them silently.** Sport and Grocery are
reported per okrug there; both move.

Two rules for using the output:

- **Never sum evidence kinds into one headline.** `category` means the export
  itself says so, `type` that the object's kind implies it, `name` that only the
  fascia string suggests it. Grocery is 867/867 `type`, Tobacco 60/60 `category`,
  **Industrial 28/28 `name`**. `name` evidence is a hypothesis and belongs in the
  review queue.
- **The export encodes essentially no co-membership.** Its own fields put two 2022
  classes on **2 objects out of 7,263** (*Ларец, магазин-бистро* and *Бонус,
  магазин-кафе*); the other five duals are a grocery wrongly flagged Industrial
  off a fascia match on *мясокомбинат* / *Хладокомбинат*. Nothing in
  `category_orig`, `type_orig` or `name_orig` states that a grocery sells tobacco
  — only `data/raw_v4/` and the licence registry do, and they imply ~560 such
  sites. A multi-label deliverable is unreachable from this input.

`assert_no_missed_types()` fails the build if a `type_orig` carrying an
in-taxonomy stem lands in no class — the guard against a fourth member of the D1
family. It currently passes. When it fires, either the class definition has a
spelling hole or the type needs an entry in `GUARD_EXEMPT_TYPES` **with a
reason**; never trim `AUDIT_STEMS`.

Validation covers **15.6 % of the city** (1,133 linked benchmark rows) at its
easy end — accuracy 0.925 on `exact` links against 0.700 on `probable` ones.
Any per-class accuracy table must say so.

## Known data caveats

- District (`district_orig`) assignment in the **first** export is skewed — ~71%
  of objects fall into one okrug (Oktyabrsky), and Isakogorsky/Tsiglomensky are
  merged into one label. Treat district-level results from `data/raw/` as
  provisional. **The third delivery fixes this city-wide** (largest okrug 35%,
  all nine okrugs separate); the second delivery had fixed it for its three
  okrugs only.
- The second-delivery export is **OSM-only**. **The third delivery restores
  2GIS** — but corroboration is still rare: 172 objects (2.4%) are confirmed by
  both providers, 6,504 (89.6%) rest on OSM alone.
- The third export's `match_distance_meters` / `match_name_similarity` are a
  **deduplication key, not independent verification** — 99.5% sit at exactly 0 m
  and 99.8% at similarity exactly 1.00.
- `website_check_status` is **empty for every record** in the third export, and
  `opening_date_orig` is populated for 0.6%.
- **`recode_2022()` fails a second way on the fourth delivery's vocabulary** —
  the tobacco rule tests for `табак` while `data/raw_v4/` spells the stem
  `табач-`, so 698 of 749 tobacco rows fall through to `Other`. Fixed in
  `src/arkhinfra/v4_common.py` only.
- **`recode_2022()` has a live bug in `analysis/v1/eda.qmd` and `analysis/v2/eda-v2.qmd`**:
  it lowercases `type_orig`, then tests it against a *capitalised* `GROCERY_TYPES`,
  so the test never fires and the **`Grocery shops` class is always empty** — its
  objects fall through to `Other (outside 2022 scheme)`. Fixed in
  `src/arkhinfra/v3_common.py` only. Scale: 811 objects in the third export, 854 in the
  first, and 392 of the 1,753 records in the 2022 benchmark (22%). Any published
  `Other` count from the first- or second-delivery reports is inflated. Port the
  fix before re-rendering those reports, and keep all three copies in sync.
- **`recode_2022()` fails a third way, on the third delivery's own vocabulary** —
  `GROCERY_TYPES` holds the 2022 spelling `фрукты-овощи`, the 2026 export writes
  `Овощи и фрукты`, and `Series.isin` is exact equality, so **51 greengrocers
  fall through to `Other`**. Same family as the two caveats above (a closed list
  of literal strings against a vocabulary nobody controls). Fixed in
  `src/arkhinfra/taxonomy_2022.py` only — generally, via a word-bag type key, and
  guarded by `assert_no_missed_types()`.
- The `Industrial` class is **nothing but a string search over shop signs** — in
  `taxonomy_2022` all **28** objects carry `industrial_evidence = "name"`, and
  the list holds a hostel called *ТЭЦ*, a jeweller (*Московский ювелирный
  завод*), a photo shop and a cake shop called *Фабрика* / *Фабрика тортов*, and
  three ferry terminals named after sawmills. (The old rule's count is 25; the
  `завод`/`фабрика`/`комбинат` infix stems add 3 more of the same kind.) Do not
  report it per okrug.
- **The ARKTMED panel is no longer synthetic.** The second-delivery panel had
  27 of 27 testable series exactly linear in time (R² ≥ 0.999); the third has
  **0 of 11**, median R² 0.43, and cites named Rosstat files rather than portal
  home pages. Its numbers are citable — but every **health-outcome indicator was
  removed** (morbidity, mortality, life expectancy, air pollution, emissions),
  the risk-index sheet is empty, and outside the climate series it is a two- to
  three-year snapshot with provisional 2026 values.
- The commercial dump's **`Район города` is empty for all 10,557 records**, so
  okrug can only be recovered spatially; with coordinates rounded to ±55 m it
  cannot support record-level matching.
- **The contractor's reported 94.3% match rate against 2022 does not survive
  independent re-checking.** Their "confirmed match" tier is sound, but their
  "probable match" tier is mostly coordinate proximity (median name similarity
  0.51). Independent recall is ~64%; see `reports/v3/eda-v3-validation.pdf`.
- **The fivefold alcohol undercount was a third-delivery problem, and the
  fourth delivery closes it.** The licence registry lists 442 off-trade alcohol
  retail licences in force city-wide (577 including on-trade) against the third
  export's 110 `Alcohol shops` — a gap that was structural (chains sell under a
  grocery licence), worst in the outlying okrugs and mildest in the centre, so
  okrug comparisons built on v3 `Alcohol shops` are biased toward the centre.
  The fourth delivery's 638 off-trade objects bring the licences-per-object
  ratio from 4.0 to 0.69 and narrow the okrug spread from a factor of 4.2 to
  1.6. **Use `data/raw_v4/` for anything alcohol-related, not the v3
  `Alcohol shops` class.** See `reports/egais/eda-egais.pdf` for the problem and
  `reports/v4/eda-v4.pdf` for the fix.
- **The tobacco layer has no independent benchmark.** The licence registry holds
  no tobacco class, and the 2022 tobacco list is 46 objects in three okrugs. The
  749-object tobacco layer rests on the contractor's inference and 2GIS labels;
  nothing in this repository can check it.
- **Five okrugs remain unvalidated against any object-level benchmark** — the
  2022 study covers Lomonosovsky, Oktyabrsky and Maiskaya Gorka only. The
  licence registry now covers all nine for alcohol; for tobacco they stay dark.
