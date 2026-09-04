# Alternative source: the FSRAR consolidated licence registry

`data/raw_alter_egais/` (git-ignored for bulk), snapshot **2026-07-01**, published
by Росалкогольтабакконтроль at <https://fsrar.gov.ru/opendata/7710747640-reestr>.

- `data-20260701t0000-structure-20190918t0000.xml` — 10.9 GB, 1,660,448 records
- `structure-20190918t0000.xsd.xml` — the declared schema
- `data-...zip` — the 309 MB download the XML came out of

Reduced to `data/processed/egais_licences_arkhangelsk.tsv` — **2,100 rows ×
27 columns, 2.0 MB** — by `scripts/parse_egais.py` (`pixi run parse-egais`).
Of the 12,311 records that mention Arkhangelsk anywhere, those 2,100 are the
ones whose *outlet* address names the city itself.

## What the source actually contains

**Alcohol, not tobacco.** Despite the regulator's remit covering both, every
record in the Arkhangelsk extract is an alcohol or ethanol licence:

| `activity` | rows |
| --- | ---: |
| Розничная продажа алкоголя | 1,196 |
| Розничная продажа, общепит | 819 |
| Закупка, хранение и поставки алкогольной продукции | 61 |
| Перевозки этилового спирта | 12 |
| Производство спиртных напитков | 8 |
| Розничная продажа алкоголя, общепит (слитно) | 2 |
| Закупка спиртосодержащей непищевой продукции | 2 |

There is no tobacco-licence class in the dataset. For the study this is a
**risk-factor** layer (alcohol retail outlets), not a health-supporting one.

**It is a registry, not a snapshot of live outlets.** Of the 2,100 city rows
only **585 are `действующая`**:

| `status` | rows |
| --- | ---: |
| истекла | 1,146 |
| действующая | 585 |
| прекращена | 253 |
| переоформлена | 65 |
| аннулирована | 47 |
| срок действия истек | 4 |

Any outlet-density work must filter on `status` first, and note that expired
rows still carry their historic address. Note also the two spellings of the
same expiry state (`истекла` / `срок действия истек`).

Issue dates run 2006–2026 and peak sharply in **2012 (489 licences)**, which is
a licensing-regime artefact rather than a wave of openings.

## Format traps

- The file **does not follow its own XSD**. The schema declares
  `Details/Detail` with attributes; the file delivers `data/row` with child
  elements, and several element names differ — including the registry's own
  typo `Дата__время_и_место_выезного_обслуживания`. Trust the file.
- Records are flat and independent, so the file can be cut on `</row>` and
  parsed one record at a time. `parse_egais.py` never holds more than a 16 MiB
  chunk plus the matched rows; the whole pass takes about six minutes.
- A few elements **repeat inside one row** (`Номер_ранее_выданной_лицензии`
  appears twice); the first non-empty value wins.

## Data caveats

- **`outlet_region_code` is wrong on 4.2 % of Arkhangelsk rows** — 88 of 2,100
  carry codes 76, 23, 77, 78, 50, 53 or 83 while holding a plain Arkhangelsk
  city address. Never filter on it; filter on the address.
- The address is positional —
  `country,,region,,settlement,subsettlement,street,house,...` — with a
  free-form premises tail from field 8. The settlement slot is written seven
  ways (`Архангельск г`, `Архангельск Город`, `г. Архангельск`, bare
  `Архангельск`, …), and the bare form is why the splitter is positional
  rather than type-word driven.
- Some rows put a **Novaya Zemlya** settlement (`Белушья Губа рп` 6,
  `Рогачево п` 2) in the subsettlement slot **under** `Архангельск г` — those
  are ~2,000 km away and must be excluded. `Талажский авиагородок` (25),
  `Лесная речка` (6) and `Турдеевск` (5) are genuine city territory.
- **Coordinates cover 54 %** of rows (1,134 of 2,100) and are given as DMS
  strings (`Широта - 64° 33' 24''; Долгота - 40° 32' 44''`). 1,116 parse,
  and 8 of those are registry typos — a dropped leading digit puts an outlet
  at longitude 10.55° — so the parser emits `coord_plausible` against a box
  around the city rather than silently trusting them. **1,108 usable points.**
- `Виды_продукции` is **empty for every record**, as is the blank-form number.
- `issuing_body` is free text with **ten spellings** of the same ministry, one
  of them corrupted (`и1908202 торговли`).
- 2,100 rows are **1,038 licences over 1,788 addresses** for 646 organisations:
  one licence covers many outlets, so a row is an outlet-licence pair, not a
  licence.
- The registry carries **no okrug field**. Okrug has to be recovered — see
  `src/arkhinfra/egais.py`, which assigns it spatially where coordinates are
  usable and by street name otherwise.
