"""Build the Russian twin of analysis/v3/eda-v3.qmd -> analysis/v3/eda-v3-ru.qmd.

Run from the repo root:  pixi run python scripts/build_ru_v3.py

Only prose, captions and the front matter are translated.  Every {python} cell is
copied byte-for-byte -- the twin needs no code edits at all, because the setup
cell finds the repository root itself -- so the rendered tables and figures stay
in English exactly as in the source document.
"""
import io
import re
import sys

SRC = "analysis/v3/eda-v3.qmd"
DST = "analysis/v3/eda-v3-ru.qmd"

src = io.open(SRC, encoding="utf-8").read()

# ---------------------------------------------------------------- front matter
FRONT_OLD = '''title: "Arkhangelsk Urban Infrastructure — EDA of the third delivery"
subtitle: "City-wide 2026 export, 2022 taxonomy crosswalk, commercial directory dump, ARKTMED indicator panel (2026-08-31)"
author: "Northern State Medical University — Infrastructure project"
date: today
lang: en
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''
FRONT_NEW = '''title: "Городская инфраструктура Архангельска — РАД третьей поставки"
subtitle: "Общегородская выгрузка 2026, перекодировка в таксономию 2022, коммерческий справочник, панель показателей ARKTMED (2026-08-31)"
author: "СГМУ — проект по городской инфраструктуре"
date: today
lang: ru
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''

# ------------------------------------------------------- captions (fig / tbl)
CAPTIONS = {
    "What each delivery shipped. The third delivery replaces rather than extends the second.":
        "Состав поставок. Третья поставка заменяет вторую, а не дополняет её.",
    "Source provenance of the third-delivery export. Independent corroboration remains the exception.":
        "Происхождение записей третьей поставки. Независимое подтверждение остаётся исключением.",
    "Provenance by okrug. Confirmation rates are uniformly low; no okrug is systematically better covered.":
        "Происхождение записей по округам. Доля подтверждённых объектов везде низкая; ни один округ не покрыт систематически лучше.",
    "2GIS reach by 2022-taxonomy class. Tobacco outlets and sport objects depend most on 2GIS; alcohol shops and industrial objects are OSM-only throughout.":
        "Охват 2ГИС по классам таксономии 2022. Сильнее всего от 2ГИС зависят точки продажи табака и спортивные объекты; алкогольные магазины и промышленные объекты целиком держатся на OSM.",
    "The export's own cross-source agreement. Where the two providers meet, they agree almost exactly.":
        "Внутренняя сверка источников в самой выгрузке. Там, где два поставщика пересекаются, они совпадают почти точно.",
    "Attribute completeness, third delivery against the first. Completeness is unchanged; the export improved its okrugs, not its attributes.":
        "Полнота атрибутов, третья поставка против первой. Полнота не изменилась: выгрузка улучшила округа, но не атрибуты.",
    "Objects by source category (English labels; source values are Russian).":
        "Объекты по исходным категориям (подписи английские; исходные значения — русские).",
    "Top 20 object types (type_orig, original Russian labels).":
        "20 самых частых типов объектов (type_orig, исходные русские значения).",
    "Objects per okrug: the first export (grey) against the third (blue). The first export's concentration in Oktyabrsky is gone, and the merged Isakogorsky/Tsiglomensky label is resolved into two okrugs.":
        "Объекты по округам: первая выгрузка (серым) против третьей (синим). Перекос первой выгрузки в сторону Октябрьского округа исчез, а слитая метка «Исакогорский и Цигломенский» разделена на два округа.",
    "Concentration of objects in the largest okrug — the defect that made first-delivery district results unusable.":
        "Концентрация объектов в крупнейшем округе — дефект, из-за которого результаты первой поставки в разрезе округов были непригодны.",
    "The 2026 export recoded into the 2022 health taxonomy.":
        "Выгрузка 2026 года, перекодированная в таксономию здоровья 2022 года.",
    "The 2022 taxonomy across the three sources. The 2022 benchmark was built to the taxonomy; the 2026 export is a general-purpose census in which 63% of objects fall outside it.":
        "Таксономия 2022 в трёх источниках. Эталон 2022 года собирался под эту таксономию; выгрузка 2026 года — универсальная перепись, в которой 63 % объектов лежат за её пределами.",
    "2022-taxonomy classes by okrug (counts). Okrugs in rows, classes in columns.":
        "Классы таксономии 2022 по округам (в объектах). Округа в строках, классы в столбцах.",
    "Within-okrug composition: each row sums to 100%. A single sequential hue encodes magnitude.":
        "Состав внутри округа: каждая строка в сумме даёт 100 %. Величина закодирована одним последовательным оттенком.",
    "Health-supporting objects vs. risk factors by okrug, with the health-to-risk ratio. Counts are absolute; no population denominator is available in this delivery.":
        "Объекты, поддерживающие здоровье, против факторов риска по округам, с их соотношением. Значения абсолютные: знаменателя по численности населения в этой поставке нет.",
    "Health-supporting infrastructure (blue) against risk factors (orange) per okrug.":
        "Инфраструктура, поддерживающая здоровье (синим), против факторов риска (оранжевым) по округам.",
    "Spatial distribution of the 2026 export by okrug, on an OpenStreetMap/CARTO basemap.":
        "Пространственное распределение выгрузки 2026 года по округам на подложке OpenStreetMap/CARTO.",
    "Health-supporting objects (blue) and risk factors (orange) over the neutral remainder (grey). Risk factors concentrate along the central corridor.":
        "Объекты, поддерживающие здоровье (синим), и факторы риска (оранжевым) поверх нейтрального остатка (серым). Факторы риска сосредоточены вдоль центрального коридора.",
    "The commercial dump at a glance. Its okrug field is unusable and its coordinates are too coarse for record-level matching.":
        "Коммерческий справочник в цифрах. Поле округа непригодно, а координаты слишком грубые для сопоставления на уровне записей.",
    "Top 12 rubrics in the commercial dump. Its composition is business-directory-shaped, not infrastructure-shaped.":
        "12 самых частых рубрик коммерческого справочника. По составу это бизнес-справочник, а не реестр инфраструктуры.",
    "The indicator panel, second delivery against third.":
        "Панель показателей: вторая поставка против третьей.",
    "Third-delivery indicators by section, with the years each actually covers. Only the climate series span the full period.":
        "Показатели третьей поставки по разделам с фактически покрытыми годами. Полный период охватывают только климатические ряды.",
    "Year coverage per indicator. Outside climate, the panel is a two- or three-year snapshot, not a time series.":
        "Покрытие по годам для каждого показателя. За пределами климата панель — это срез за два-три года, а не временной ряд.",
    "The environment section in full. All four series are single-year 2025 expenditure figures.":
        "Раздел «Экология» целиком. Все четыре ряда — это затраты за один 2025 год.",
    "The climate series — the only indicators covering the full 2021-2026 period. Values come from a reanalysis archive.":
        "Климатические ряды — единственные показатели, покрывающие весь период 2021–2026. Значения взяты из архива реанализа.",
}

# ------------------------------------------------------------- prose blocks
BLOCKS = [
(
"""# Introduction

The third delivery (`data/raw_v3/`, generated 2026-08-31) is **not an increment on
the second**. It replaces the city-wide export outright and drops both artefacts
the second delivery was built around — the 2022↔2026 record comparison workbook
and its per-okrug summary. What arrives instead is a fresh city-wide export, a
commercial directory dump that has no precedent in earlier deliveries, and a
rebuilt indicator panel.""",
"""# Введение

Третья поставка (`data/raw_v3/`, сформирована 2026-08-31) — **не дополнение ко
второй**. Она полностью заменяет общегородскую выгрузку и не содержит обоих
артефактов, на которых была построена вторая поставка: книги сравнения записей
2022↔2026 и её сводки по округам. Вместо них пришли новая общегородская
выгрузка, коммерческий справочник, не имевший аналогов в прежних поставках, и
пересобранная панель показателей."""),
(
"""## The headline of this delivery

- The **okrug-assignment defect is fixed city-wide**. The first export put 71 % of
  all objects in Oktyabrsky; here the largest okrug holds 35 %, and Isakogorsky
  and Tsiglomensky — merged into one label in the first export — are separate.
- **2GIS is back.** The second delivery was OSM-only; here 759 objects carry 2GIS
  coverage and 172 are independently corroborated by both providers.
- The export is a **fresh census, not a revision**: 81 % of its content in the
  three 2022 okrugs has no counterpart in the 2022 benchmark.
- The **ARKTMED panel is no longer synthetic** — but it lost every health outcome
  indicator it used to carry.""",
"""## Главное в этой поставке

- **Дефект отнесения к округам исправлен по всему городу.** В первой выгрузке
  71 % всех объектов приходился на Октябрьский округ; здесь крупнейший округ
  держит 35 %, а Исакогорский и Цигломенский — слитые в первой выгрузке в одну
  метку — разделены.
- **2ГИС вернулся.** Вторая поставка была только на OSM; здесь 759 объектов
  имеют покрытие 2ГИС, а 172 независимо подтверждены обоими поставщиками.
- Выгрузка — это **новая перепись, а не правка прежней**: 81 % её содержимого в
  трёх округах 2022 года не имеет соответствия в эталоне 2022 года.
- **Панель ARKTMED перестала быть синтетической** — но лишилась всех показателей
  исходов здоровья, которые несла раньше."""),
(
"""# Part I — source provenance and verification {#sec-provenance}""",
"""# Часть I — происхождение и подтверждение источников {#sec-provenance}"""),
(
"""Only **172 objects (2.4 %)** are confirmed by both providers. The export is
overwhelmingly a single-source OSM product with a 2GIS minority; a
"`confirmed_by_2gis_and_osm`" label therefore marks a small privileged subset,
not the normal case.""",
"""Обоими поставщиками подтверждены лишь **172 объекта (2,4 %)**. Выгрузка — это
преимущественно односточниковый продукт на базе OSM с меньшинством из 2ГИС,
поэтому метка «`confirmed_by_2gis_and_osm`» обозначает небольшое привилегированное
подмножество, а не обычный случай."""),
(
"""## The export's internal cross-source check

The export ships its own 2GIS↔OSM reconciliation in `match_distance_meters` and
`match_name_similarity`, populated for 6,785 objects.""",
"""## Внутренняя сверка источников в самой выгрузке

Выгрузка несёт собственную сверку 2ГИС↔OSM в полях `match_distance_meters` и
`match_name_similarity`, заполненных для 6 785 объектов."""),
(
"""The distribution is degenerate: 99.5 % of scored records sit at exactly 0 m and
99.8 % at a name similarity of exactly 1.00. This is a **deduplication key, not
an independent verification** — it records that the same string at the same point
was seen twice, which is a much weaker claim than two sources independently
attesting an object.""",
"""Распределение вырожденное: 99,5 % оценённых записей стоят ровно на 0 м, а
99,8 % — на сходстве названий ровно 1,00. Это **ключ дедупликации, а не
независимая верификация**: он фиксирует, что одна и та же строка в одной и той же
точке встретилась дважды, а это гораздо более слабое утверждение, чем
независимое подтверждение объекта двумя источниками."""),
(
"""## Field completeness""",
"""## Полнота полей"""),
(
"""`website_check_status` is **empty for all `{python} f"{n_obj:,}"` records** — the
column exists but was never populated, so no website was validated. `opening_date_orig`
is present for 0.6 % of objects, which rules out any analysis of when objects appeared.""",
"""Поле `website_check_status` **пусто во всех `{python} f"{n_obj:,}"` записях** —
столбец существует, но не был заполнен, то есть ни один сайт не проверялся. Поле
`opening_date_orig` заполнено для 0,6 % объектов, что исключает любой анализ
времени появления объектов."""),
(
"""# Part II — raw object groups {#sec-raw}

The export carries `{python} f"{n_cat}"` source categories and
`{python} f"{n_type}"` object types across `{python} f"{n_okrug}"` okrugs.""",
"""# Часть II — сырые группы объектов {#sec-raw}

Выгрузка содержит `{python} f"{n_cat}"` исходных категорий и
`{python} f"{n_type}"` типов объектов в `{python} f"{n_okrug}"` округах."""),
(
"""Half the export (50.1 %) is a single category, `Магазины` / Shops. The category
field is therefore coarse; the `type_orig` field below carries the resolution.""",
"""Половина выгрузки (50,1 %) приходится на одну категорию — `Магазины`. Поле
категории, таким образом, слишком грубое; разрешающую способность несёт поле
`type_orig` ниже."""),
(
"""# Part III — recoding into the 2022 taxonomy {#sec-recode}

The 2022 study used a seven-class health taxonomy. `recode_2022()` maps the 2026
export onto it from `category_orig`, `type_orig` and the object name, in that
priority order. The full rule set and the resulting crosswalk are in
`docs/crosswalk_2022.md`.""",
"""# Часть III — перекодировка в таксономию 2022 года {#sec-recode}

В исследовании 2022 года использовалась таксономия здоровья из семи классов.
Функция `recode_2022()` отображает на неё выгрузку 2026 года по полям
`category_orig`, `type_orig` и названию объекта — именно в этом порядке
приоритета. Полный свод правил и итоговая таблица соответствия приведены в
`docs/crosswalk_2022.md`."""),
(
"""::: {.callout-note}
## A defect inherited from the earlier reports

The copy of this rule in `analysis/v1/eda.qmd` and `analysis/v2/eda-v2.qmd` lowercases
the type field and then tests it against a **capitalised** list of grocery types.
The test can never succeed, so the `Grocery shops` class is empty in every
previously delivered report and its objects were absorbed into
`Other (outside 2022 scheme)`. The rule is corrected here: it moves
**811 objects (11.2 %)** of this export, 854 of the first export, and 392 of the
1,753 records in the 2022 benchmark — 22 % of the benchmark. Counts of
`Other` in the first- and second-delivery reports are inflated accordingly.
:::""",
"""::: {.callout-note}
## Дефект, унаследованный от предыдущих отчётов

Копия этого правила в `analysis/v1/eda.qmd` и `analysis/v2/eda-v2.qmd` приводит поле
типа к нижнему регистру, а затем сравнивает его со списком продуктовых типов,
записанным **с заглавных букв**. Проверка не может сработать никогда, поэтому
класс `Grocery shops` пуст во всех ранее сданных отчётах, а его объекты
поглощены классом `Other (outside 2022 scheme)`. Здесь правило исправлено: оно
перемещает **811 объектов (11,2 %)** этой выгрузки, 854 объекта первой выгрузки и
392 из 1 753 записей эталона 2022 года — 22 % эталона. Значения `Other` в
отчётах первой и второй поставок завышены соответственно.
:::"""),
(
"""The 2022 benchmark was assembled *to* this taxonomy, so only 7 of its records fall
outside it. The 2026 export is a general-purpose census: 63 % of it is outside the
2022 scheme. Comparisons between the two must therefore be made class by class,
never on totals.""",
"""Эталон 2022 года собирался *под* эту таксономию, поэтому за её пределы выходят
лишь 7 его записей. Выгрузка 2026 года — универсальная перепись: 63 % её
содержимого лежит вне схемы 2022 года. Поэтому сравнивать их следует
класс за классом и никогда — по итоговым суммам."""),
(
"""## Health-supporting infrastructure vs. risk factors

Following the 2022 framing, `Medical` and `Sport` are health-supporting, and
`Alcohol shops`, `Tobacco outlets` and `Industrial` are risk factors.""",
"""## Инфраструктура, поддерживающая здоровье, против факторов риска

Следуя рамке 2022 года, классы `Medical` и `Sport` относятся к поддерживающим
здоровье, а `Alcohol shops`, `Tobacco outlets` и `Industrial` — к факторам
риска."""),
(
"""The city-wide ratio is 5.3 health-supporting objects per risk object. The spread
across okrugs (3.7 to 8.5) rests on small risk-side counts — the smallest okrugs
carry 2 to 6 risk objects each — so okrug-level ratios should be read as
indicative only. Risk objects are also the classes the export covers least well
(see @sec-provenance), which biases the ratio upward.""",
"""По городу в целом соотношение составляет 5,3 объекта, поддерживающего здоровье,
на один объект риска. Разброс по округам (от 3,7 до 8,5) держится на малых
значениях в части риска — в самых маленьких округах приходится от 2 до 6 таких
объектов, — поэтому окружные соотношения следует читать лишь как ориентировочные.
Кроме того, объекты риска относятся к классам, которые выгрузка покрывает хуже
всего (см. @sec-provenance), что смещает соотношение вверх."""),
(
"""# Part IV — spatial distribution {#sec-map}""",
"""# Часть IV — пространственное распределение {#sec-map}"""),
(
"""Okrug colouring now follows visible spatial boundaries. The export spans
64.41–64.71 °N, covering the outlying northern and southern okrugs rather than
the centre alone.""",
"""Раскраска по округам теперь следует видимым пространственным границам. Выгрузка
охватывает полосу 64,41–64,71° с. ш., включая удалённые северные и южные округа,
а не только центр."""),
(
"""The three okrugs covered by the 2022 study hold
`{python} f"{len(three):,}"` of the export's `{python} f"{n_obj:,}"` objects
(`{python} f"{len(three) / n_obj * 100:.0f}"` %). The record-level comparison
against the 2022 benchmark, including the confirmation map for those three
okrugs, is the subject of the companion report
(`reports/v3/eda-v3-validation.pdf`); its headline is that only **19 %** of the
2026 content in those okrugs has a 2022 counterpart, and that the contractor's
reported 94.3 % match rate does not survive independent re-checking.""",
"""На три округа, охваченных исследованием 2022 года, приходится
`{python} f"{len(three):,}"` из `{python} f"{n_obj:,}"` объектов выгрузки
(`{python} f"{len(three) / n_obj * 100:.0f}"` %). Сравнение на уровне записей с
эталоном 2022 года, включая карту подтверждения по этим трём округам, — предмет
парного отчёта (`reports/v3/eda-v3-validation-ru.pdf`); его главный вывод в том,
что лишь **19 %** содержимого 2026 года в этих округах имеет соответствие в 2022
году, а заявленная подрядчиком доля совпадений 94,3 % не выдерживает независимой
перепроверки."""),
(
"""# Part V — the commercial directory dump {#sec-base}""",
"""# Часть V — коммерческий справочник {#sec-base}"""),
(
"""`export_base_688669_zal6mp.xlsx` has no precedent in earlier deliveries:
`{python} f"{n_base:,}"` records across 25 fields, in a **third taxonomy**
(`Рубрика` / `Подрубрика` / `Тип подрубрики`) unrelated to either the export's
own categories or the 2022 scheme. It carries fields no other source has —
revenue analysis, online rating, review counts, messenger contacts.""",
"""Файл `export_base_688669_zal6mp.xlsx` не имеет аналогов в прежних поставках:
`{python} f"{n_base:,}"` записей по 25 полям в **третьей таксономии**
(`Рубрика` / `Подрубрика` / `Тип подрубрики`), не связанной ни с собственными
категориями выгрузки, ни со схемой 2022 года. Он несёт поля, которых нет ни в
одном другом источнике: анализ выручки, рейтинг в интернете, число отзывов,
контакты в мессенджерах."""),
(
"""Two properties disqualify this file as a primary source. Its okrug field is
**empty for every record**, so okrug can only be recovered spatially; and its
coordinates are rounded to three decimals — roughly ±55 m at this latitude —
which is coarser than the 50 m radius used for record matching. It is usable as a
supplementary attribute source and as a weak third-party corroboration signal
(the companion report measures that corroboration at 3.6 % on name and address),
but it cannot replace or validate the main export.""",
"""Два свойства лишают этот файл права быть первичным источником. Поле округа в нём
**пусто во всех записях**, поэтому округ восстановим только пространственно; а
координаты округлены до трёх знаков — примерно ±55 м на этой широте, — что грубее
радиуса 50 м, применяемого при сопоставлении записей. Файл пригоден как
дополнительный источник атрибутов и как слабый сигнал стороннего подтверждения
(парный отчёт оценивает это подтверждение в 3,6 % по названию и адресу), но он не
может ни заменить основную выгрузку, ни подтвердить её."""),
(
"""# Part VI — the ARKTMED indicator panel {#sec-arktmed}""",
"""# Часть VI — панель показателей ARKTMED {#sec-arktmed}"""),
(
"""::: {.callout-important}
## The synthetic-panel caveat no longer applies — but the panel lost its health indicators

The second delivery's panel was synthetic: **27 of its 27** testable series were
exactly linear in time (R² ≥ 0.999). In this delivery **0 of
`{python} f"{len(lin3)}"`** are, with a median R² of
`{python} f"{np.median(lin3):.2f}"`, and the sources are named Rosstat files
rather than portal home pages. The numbers are now citable. However, every
health-outcome indicator the previous panel carried — morbidity, mortality, life
expectancy, air pollution, emissions — has been **removed**, and the risk-index
sheet is empty.
:::""",
"""::: {.callout-important}
## Оговорка о синтетической панели снята — но панель лишилась показателей здоровья

Панель второй поставки была синтетической: **27 из 27** проверяемых рядов были
строго линейны по времени (R² ≥ 0,999). В этой поставке таких **0 из
`{python} f"{len(lin3)}"`** при медианном R², равном
`{python} f"{np.median(lin3):.2f}"`, а в источниках указаны конкретные файлы
Росстата, а не главные страницы порталов. Числа теперь можно цитировать. Однако
все показатели исходов здоровья, которые несла прежняя панель — заболеваемость,
смертность, ожидаемая продолжительность жизни, загрязнение воздуха, выбросы, —
**удалены**, а лист индекса риска пуст.
:::"""),
(
"""## Environmental indicators""",
"""## Экологические показатели"""),
(
"""The environment section consists of four **2025-only expenditure lines**. They
describe municipal spending on environmental protection, not environmental
state — there is no air quality, emissions or water quality measure anywhere in
this delivery. The second delivery did carry `air_pollution_index`,
`emissions_total` and `water_quality_index`, but those series were synthetic and
are not recoverable.""",
"""Раздел «Экология» состоит из четырёх строк затрат **только за 2025 год**. Они
описывают муниципальные расходы на охрану окружающей среды, а не её состояние: ни
качества воздуха, ни выбросов, ни качества воды в этой поставке нет нигде. Вторая
поставка содержала `air_pollution_index`, `emissions_total` и
`water_quality_index`, но эти ряды были синтетическими и восстановлению не
подлежат."""),
(
"""Note that 2026 is incomplete at the time of this delivery: the panel's 2026
climate values cover a partial year and its economy series run to 2026 as well.
Treat the final year as provisional.""",
"""Обратите внимание, что на момент поставки 2026 год не завершён: климатические
значения панели за 2026 год покрывают неполный год, и экономические ряды тоже
доведены до 2026 года. Последний год следует считать предварительным."""),
(
"""# Caveats {#sec-caveats}

- **Independent corroboration is rare.** 2.4 % of objects are confirmed by both
  providers; 89.6 % rest on OSM alone. The export's own
  `match_distance_meters` / `match_name_similarity` fields are a deduplication
  key, not independent verification.
- **`website_check_status` is empty for every record** and `opening_date_orig`
  is present for 0.6 %.
- **The `Grocery shops` class was empty in all previously delivered reports**
  (see @sec-recode). Any published count of `Other (outside 2022 scheme)` from
  the first- or second-delivery reports is inflated by roughly 800 objects.
- **`Industrial` is unreliable at this size.** It holds 25 objects, several of
  them name-substring false positives (a hostel, a jewellery shop). Do not read
  okrug-level industrial counts.
- **No population denominator** ships with this delivery, so all okrug
  comparisons are absolute counts. Okrug-level health-to-risk ratios rest on
  single-digit risk counts in the smaller okrugs.
- **The commercial dump cannot be used for okrug-level or record-level work** —
  empty okrug field, coordinates rounded to ±55 m.
- **The ARKTMED panel carries no health-outcome indicator** and its risk-index
  sheet is empty. Outside the climate series it is a two- to three-year snapshot,
  and its 2026 values are provisional.
- **Five okrugs remain unvalidated against any benchmark.** The 2022 study covers
  Lomonosovsky, Oktyabrsky and Maiskaya Gorka only; nothing in this delivery
  independently checks the other six.""",
"""# Оговорки {#sec-caveats}

- **Независимое подтверждение встречается редко.** Обоими поставщиками
  подтверждены 2,4 % объектов; 89,6 % держатся только на OSM. Собственные поля
  выгрузки `match_distance_meters` / `match_name_similarity` — это ключ
  дедупликации, а не независимая верификация.
- **Поле `website_check_status` пусто во всех записях**, а `opening_date_orig`
  заполнено для 0,6 %.
- **Класс `Grocery shops` был пуст во всех ранее сданных отчётах**
  (см. @sec-recode). Любое опубликованное значение `Other (outside 2022 scheme)`
  из отчётов первой или второй поставки завышено примерно на 800 объектов.
- **Класс `Industrial` при таком размере ненадёжен.** В нём 25 объектов, часть из
  которых — ложные срабатывания по подстроке в названии (хостел, ювелирный
  магазин). Не используйте окружные значения по промышленным объектам.
- **Знаменателя по численности населения** в этой поставке нет, поэтому все
  сравнения по округам — это абсолютные значения. Окружные соотношения
  «здоровье / риск» опираются на однозначные величины риска в малых округах.
- **Коммерческий справочник непригоден для работы на уровне округов и записей**:
  пустое поле округа, координаты округлены до ±55 м.
- **Панель ARKTMED не содержит ни одного показателя исходов здоровья**, а её лист
  индекса риска пуст. За пределами климатических рядов это срез за два-три года,
  а значения за 2026 год предварительны.
- **Пять округов по-прежнему не проверены ни против какого эталона.**
  Исследование 2022 года покрывает только Ломоносовский, Октябрьский и Майскую
  Горку; ничто в этой поставке не проверяет остальные шесть независимо."""),
]


def main() -> int:
    out = src
    assert FRONT_OLD in out, "front matter block not found"
    out = out.replace(FRONT_OLD, FRONT_NEW, 1)

    missing = []
    for en, ru in CAPTIONS.items():
        needle = f'"{en}"'
        if needle not in out:
            missing.append(("CAP", en[:60]))
            continue
        out = out.replace(needle, f'"{ru}"', 1)

    for en, ru in BLOCKS:
        if en not in out:
            missing.append(("BLOCK", en.split("\n")[0][:60]))
            continue
        out = out.replace(en, ru, 1)

    if missing:
        for kind, txt in missing:
            print(f"NOT FOUND [{kind}] {txt}")
        return 1

    # Nothing English should survive outside the code cells.
    leftovers = []
    incode = False
    for n, line in enumerate(out.split("\n"), 1):
        if line.startswith("```"):
            incode = not incode
            continue
        if incode or not line.strip():
            continue
        if re.search(r"[A-Za-z]{4,}", re.sub(r"`[^`]*`", "", line)):
            leftovers.append(f"  L{n}: {line[:88]}")
    if leftovers:
        print("Possible untranslated prose (inline code stripped):")
        print("\n".join(leftovers))

    io.open(DST, "w", encoding="utf-8").write(out)
    print(f"written {DST} ({len(out):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
