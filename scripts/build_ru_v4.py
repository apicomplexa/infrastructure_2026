"""Build the Russian twin of analysis/v4/eda-v4.qmd.

Run from the repo root:  pixi run python scripts/build_ru_v4.py
Then normalise the numbers:  pixi run python scripts/ru_numfmt.py

Only prose, captions and the front matter are translated.  Every {python} cell is
copied byte-for-byte -- the twin needs no code edits at all, because the setup
cell finds the repository root itself -- so the rendered tables and figures stay
in English exactly as in the source document.
"""
import io
import re
import sys

SRC = "analysis/v4/eda-v4.qmd"
DST = "analysis/v4/eda-v4-ru.qmd"

FRONT_OLD = '''title: "Arkhangelsk Urban Infrastructure — EDA of the fourth delivery"
subtitle: "The alcohol and tobacco risk layers, checked against the 2022 study and the FSRAR licence registry"
author: "Northern State Medical University — Infrastructure project"
date: today
lang: en
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''
FRONT_NEW = '''title: "Городская инфраструктура Архангельска — разведочный анализ четвёртой поставки"
subtitle: "Слои риска по алкоголю и табаку в сверке с исследованием 2022 года и реестром лицензий ФСРАР"
author: "СГМУ — проект по городской инфраструктуре"
date: today
lang: ru
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''

CAPTIONS = {
    "Column schema against the third delivery. Names, order and inferred dtypes all agree.":
        "Схема колонок в сравнении с третьей поставкой. Названия, порядок и выведенные типы совпадают полностью.",
    "The fourth vocabulary. The 'возможная' (possible) types are an inference by the contractor, not an observation.":
        "Четвёртый словарь. Типы «возможная …» — это вывод подрядчика, а не наблюдение.",
    "Evidence tier by risk factor. Four rows in five are an inference from the object's type, which the contractor's own comment says still requires checking.":
        "Уровень доказательности по факторам риска. Четыре записи из пяти — вывод из типа объекта, который, по собственному комментарию подрядчика, ещё требует проверки.",
    "The shared 2022 recoder against the fourth vocabulary. The tobacco rule tests for the stem 'табак'; every label in this delivery spells it 'табач-'.":
        "Общий перекодировщик 2022 года на четвёртом словаре. Табачное правило ищет корень «табак», а все метки этой поставки пишут «табач-».",
    "The two files, and the combined layer. The files overlap: some sites carry both an alcohol and a tobacco row.":
        "Два файла и объединённый слой. Файлы пересекаются: часть точек несёт и алкогольную, и табачную запись.",
    "Verification status. The tobacco layer is the best-corroborated file the project has received; the alcohol layer is worse than the third delivery it is drawn from.":
        "Статус верификации. Табачный слой — наиболее подтверждённый файл из полученных проектом; алкогольный слой хуже третьей поставки, из которой он выведен.",
    "Field completeness. Two columns carried over from the third delivery remain unusable, and the match columns are now more missing than before.":
        "Заполненность полей. Две колонки, унаследованные от третьей поставки, по-прежнему непригодны, а колонки сопоставления стали пропущены чаще прежнего.",
    "Encoding of opening_hours_orig. One column, two formats, split by which provider supplied the row.":
        "Кодировка opening_hours_orig. Одна колонка, два формата, разделённые тем, какой поставщик дал запись.",
    "Distance from each fourth-delivery record to the nearest object already in the third delivery.":
        "Расстояние от каждой записи четвёртой поставки до ближайшего объекта, уже имевшегося в третьей.",
    "The 2022 class of the nearest third-delivery object, within 50 m. The delivery's substance is the promotion of grocery shops and catering into the risk classes.":
        "Класс 2022 года у ближайшего объекта третьей поставки в радиусе 50 м. Существо поставки — перевод продуктовых магазинов и общепита в классы риска.",
    "Recall of the 2022 risk objects, in the three okrugs the 2022 study covers. The fourth delivery does not improve on the third.":
        "Полнота обнаружения объектов риска 2022 года в трёх округах, охваченных исследованием 2022 года. Четвёртая поставка не улучшает результат третьей.",
    "2022 risk objects with some fourth-delivery object at the same site, split by whether the name also agrees. Most of the shortfall is a rebrand, not an absence.":
        "Объекты риска 2022 года, у которых на том же месте есть объект четвёртой поставки, с разбивкой по совпадению названия. Основная часть недостачи — смена вывески, а не отсутствие объекта.",
    "The other direction: how much of the fourth delivery in the three 2022 okrugs is new relative to the 2022 list.":
        "Обратное направление: какая часть четвёртой поставки в трёх округах 2022 года является новой относительно списка 2022 года.",
    "Alcohol availability city-wide, counted four ways. The third delivery's Alcohol shops class sat far below the licence count; the fourth delivery's off-trade layer sits slightly above it.":
        "Доступность алкоголя по городу, посчитанная четырьмя способами. Класс Alcohol shops третьей поставки лежал далеко ниже числа лицензий; слой off-trade четвёртой поставки — немного выше него.",
    "Active off-trade licences per export object, by okrug. A ratio far above 1 means the export missed outlets; the third delivery's spread ran from 2.9 to 12.0.":
        "Число действующих лицензий off-trade на один объект выгрузки, по округам. Отношение много больше 1 означает, что выгрузка пропустила торговые точки; у третьей поставки разброс шёл от 2,9 до 12,0.",
    "The same ratios, plotted. A perfectly calibrated export would sit on the dashed line at 1.0. The third delivery's error grows with distance from the centre; the fourth delivery's does not.":
        "Те же отношения на графике. Идеально откалиброванная выгрузка легла бы на пунктир в точке 1,0. Ошибка третьей поставки растёт с удалением от центра, ошибка четвёртой — нет.",
    "Two-way spatial agreement between the alcohol layer and licensed outlets in force. The reverse direction — licensed outlets the export can see — is the one the fivefold-undercount finding was about.":
        "Двустороннее пространственное согласие между алкогольным слоем и действующими лицензированными точками. Обратное направление — лицензированные точки, видимые выгрузке, — это именно то, о чём был вывод о пятикратном недоучёте.",
    "Licensed off-trade outlets in force (green) against the fourth delivery's off-trade objects (orange), on an OpenStreetMap/CARTO basemap. The two surfaces now cover the same city.":
        "Действующие лицензированные точки off-trade (зелёные) и объекты off-trade четвёртой поставки (оранжевые) на подложке OpenStreetMap/CARTO. Две поверхности теперь покрывают один и тот же город.",
    "Risk sites per 100 objects in the third delivery's pool, by okrug. The outlying okrugs carry a markedly higher share of risk objects than the centre.":
        "Число точек риска на 100 объектов пула третьей поставки, по округам. В окраинных округах доля объектов риска заметно выше, чем в центре.",
    "The combined risk layer. Sites carrying both an alcohol and a tobacco row are drawn last, in purple.":
        "Объединённый слой риска. Точки, несущие и алкогольную, и табачную запись, отрисованы последними, фиолетовым.",
}

BLOCKS = [
(
"""# Introduction

The fourth delivery arrived as two CSVs — `…2026-09-03…табачное изделие.csv`
(`{python} f"{n_tob:,}"` rows) and `…2026-09-04…алкоголь.csv`
(`{python} f"{n_alc:,}"` rows) — with the contractor's assurance that they carry
the same schema as the third delivery.

This report asks three questions in order. **Is it the same schema?** **What is
actually in it?** And **does it hold up against the two benchmarks this project
can check it with** — the 2022 study, and the FSRAR consolidated licence
registry profiled in `reports/egais/eda-egais.pdf`.

The short answer to the first is *as a container, yes; as a vocabulary, no, and
the difference is not cosmetic*. The short answer to the third is that the
delivery does one important thing very well and one thing not at all.

## Why this delivery exists

`reports/egais/eda-egais.pdf` closed on a specific finding: the commissioned
exports **undercount alcohol retail roughly fivefold**. The third delivery
recognised `{python} f"{(v3['category_2022'] == 'Alcohol shops').sum()}"`
`Alcohol shops` city-wide against
`{python} f"{len(eg_off)}"` alcohol retail licences in force, and the gap was
worst in the outlying okrugs — which biased every okrug risk comparison toward
the centre. The structural reason was that chains sell alcohol under a grocery
licence and so never appear as an alcohol shop.

This delivery is the answer to that. Its whole content is a judgement about
which existing objects plausibly sell alcohol or tobacco.

# Part I — Is it the same schema? {#sec-schema}

## The container: identical""",
"""# Введение

Четвёртая поставка пришла двумя CSV-файлами — `…2026-09-03…табачное изделие.csv`
(`{python} f"{n_tob:,}"` строк) и `…2026-09-04…алкоголь.csv`
(`{python} f"{n_alc:,}"` строк) — с заверением подрядчика, что они выполнены в
той же схеме, что и третья поставка.

Отчёт последовательно задаёт три вопроса. **Та ли это схема?** **Что в файлах на
самом деле?** И **выдерживают ли они сверку с двумя эталонами, доступными
проекту** — исследованием 2022 года и сводным реестром лицензий ФСРАР, описанным
в `reports/egais/eda-egais.pdf`.

Краткий ответ на первый вопрос: *как контейнер — да; как словарь — нет, и разница
не косметическая*. Краткий ответ на третий: одну важную вещь поставка делает
очень хорошо, а другую не делает вовсе.

## Зачем понадобилась эта поставка

Отчёт `reports/egais/eda-egais.pdf` завершился конкретным выводом: заказанные
выгрузки **недоучитывают розничную торговлю алкоголем примерно в пять раз**.
Третья поставка распознала по городу
`{python} f"{(v3['category_2022'] == 'Alcohol shops').sum()}"` объектов класса
`Alcohol shops` против
`{python} f"{len(eg_off)}"` действующих лицензий на розничную продажу алкоголя,
причём разрыв был максимален в окраинных округах — из-за чего любое окружное
сравнение риска смещалось в пользу центра. Структурная причина в том, что сети
продают алкоголь по продуктовой лицензии и потому никогда не попадают в
алкогольные магазины.

Эта поставка — ответ на такой вывод. Всё её содержание — суждение о том, какие из
уже известных объектов вероятно торгуют алкоголем или табаком.

# Часть I — Та ли это схема? {#sec-schema}

## Контейнер: идентичен"""),
(
"""Anything in this repository that reads the third delivery reads these files
unchanged. That part of the promise holds, and it is worth saying plainly
because the previous three deliveries each broke it somewhere.

## The vocabulary: a fourth taxonomy

`category_orig` and `type_orig` share **no value** with any earlier delivery.
Each file carries exactly one category, and four types between them.""",
"""Любой код этого репозитория, читающий третью поставку, прочитает эти файлы без
изменений. Эта часть обещания выполнена, и сказать об этом стоит прямо: каждая из
трёх предыдущих поставок где-нибудь его нарушала.

## Словарь: четвёртая таксономия

`category_orig` и `type_orig` **не имеют ни одного общего значения** ни с одной
прежней поставкой. В каждом файле ровно одна категория и четыре типа на двоих."""),
(
"""## The `возможная` tier is most of the delivery""",
"""## Уровень «возможная» составляет бо́льшую часть поставки"""),
(
"""`{python} f"{inf_share * 100:.0f}"` % of the delivery is the inferred tier. The
contractor's `verification_comment` states the limit itself:

> тип объекта подходит, но наличие … продукции **требует отдельной проверки**

These rows say "this is a grocery shop, and grocery shops sell beer and
cigarettes". That is a reasonable inference — @sec-egais shows it is broadly the
*right* one — but it is not an observation, and a headline count that merges the
two tiers is not defensible. Every count below is reported split.

## `recode_2022()` silently drops 93 % of the tobacco file""",
"""`{python} f"{inf_share * 100:.0f}"` % поставки приходится на выведенный уровень.
Комментарий подрядчика `verification_comment` сам называет это ограничение:

> тип объекта подходит, но наличие … продукции **требует отдельной проверки**

Такие записи говорят: «это продуктовый магазин, а продуктовые магазины торгуют
пивом и сигаретами». Вывод разумный — @sec-egais показывает, что в целом он
*верен*, — но это не наблюдение, и сводная цифра, смешивающая два уровня,
несостоятельна. Все подсчёты ниже приводятся с разделением.

## `recode_2022()` молча теряет 93 % табачного файла"""),
(
"""`v3_common.recode_2022()` tests the category/type/name blob for the substring
**`табак`**. Every label the fourth delivery uses spells the stem **`табач-`**
(`Табачная и никотинсодержащая продукция`, `Возможная продажа табачной
продукции`), which does not contain `табак`. The tobacco rule therefore never
fires, and **`{python} f"{lost}"` of `{python} f"{n_tob}"` rows fall into
`Other`** — only the rows saying `вейп` or `кальян` survive by another route.

This is the same class of defect as the `GROCERY_TYPES` case mismatch already
on record, and it fails the same way: silently, with a plausible-looking
distribution. The alcohol file is unaffected, because `алкогол` does match its
labels.

The fix is one stem, and it lives in `v4_common.recode_2022_v4()` — kept out of
`v3_common` on purpose, so the three already-rendered v3 reports keep producing
the numbers they were signed off on.

# Part II — What the layer contains {#sec-content}""",
"""Функция `v3_common.recode_2022()` ищет в склейке категории, типа и названия
подстроку **`табак`**. Все метки четвёртой поставки пишут корень **`табач-`**
(`Табачная и никотинсодержащая продукция`, `Возможная продажа табачной
продукции`), который подстроки `табак` не содержит. Поэтому табачное правило не
срабатывает никогда, и **`{python} f"{lost}"` из `{python} f"{n_tob}"` строк
попадают в `Other`** — уцелевают лишь строки со словами `вейп` или `кальян`,
проходящие по другому признаку.

Это тот же класс дефекта, что и уже зафиксированное несовпадение регистра в
`GROCERY_TYPES`, и отказ происходит так же: молча, с правдоподобно выглядящим
распределением. Алкогольный файл не затронут, поскольку `алкогол` его меткам
соответствует.

Исправление — один корень, и оно живёт в `v4_common.recode_2022_v4()`: намеренно
вне `v3_common`, чтобы три уже свёрстанных отчёта v3 продолжали выдавать те
цифры, под которыми они были сданы.

# Часть II — Что содержит слой {#sec-content}"""),
(
"""`{python} f"{dual_sites}"` sites carry **both** an alcohol and a tobacco row, so
the combined layer is `{python} f"{n_sites:,}"` distinct sites rather than the
`{python} f"{n_tob + n_alc:,}"` rows the two files sum to —
`{python} f"{n_sites / len(v3) * 100:.1f}"` % of the third delivery's object
pool. Anything counting sites must dedupe on the coordinate first.

## Provider mix diverges sharply between the two files""",
"""`{python} f"{dual_sites}"` точек несут **и** алкогольную, **и** табачную запись,
поэтому объединённый слой — это `{python} f"{n_sites:,}"` различных точек, а не
`{python} f"{n_tob + n_alc:,}"` строк, в которые складываются два файла, то есть
`{python} f"{n_sites / len(v3) * 100:.1f}"` % пула объектов третьей поставки.
Любой подсчёт точек обязан сначала снять дубликаты по координате.

## Состав поставщиков резко расходится между двумя файлами"""),
(
"""The two layers were evidently built by different routes. The tobacco file draws
**`{python} f"{tob['verification_status'].eq('only_2gis').mean() * 100:.0f}"` %**
of its records from 2GIS and confirms
`{python} f"{tob['verification_status'].eq('confirmed_by_2gis_and_osm').mean() * 100:.0f}"` %
with both providers — three times the third delivery's corroboration rate.

The alcohol file is the opposite:
**`{python} f"{osm_only_alc * 100:.1f}"` % rests on OSM alone**, and only
`{python} f"{both_alc}"` records are confirmed by both. That is *worse* than the
third delivery. Whatever the alcohol layer's merits — and @sec-egais finds them
substantial — its own `verification_status` column does not support calling it
verified.

## Field completeness""",
"""Два слоя явно собирались разными путями. Табачный файл берёт из 2GIS
**`{python} f"{tob['verification_status'].eq('only_2gis').mean() * 100:.0f}"` %**
своих записей и подтверждает
`{python} f"{tob['verification_status'].eq('confirmed_by_2gis_and_osm').mean() * 100:.0f}"` %
обоими поставщиками — втрое выше уровня подтверждения третьей поставки.

С алкогольным файлом всё наоборот:
**`{python} f"{osm_only_alc * 100:.1f}"` % держится на одном лишь OSM**, и только
`{python} f"{both_alc}"` записей подтверждены обоими источниками. Это *хуже*
третьей поставки. Каковы бы ни были достоинства алкогольного слоя — а @sec-egais
находит их существенными, — его собственная колонка `verification_status` не
даёт оснований называть его верифицированным.

## Заполненность полей"""),
(
"""Three things to carry forward:

- **`website_check_status` is empty for all `{python} f"{n_tob + n_alc:,}"`
  rows**, exactly as in the third delivery. The column has never held a value in
  any delivery.
- **`opening_date_orig`** is populated for
  `{python} f"{(raw_t['opening_date_orig'].notna().sum() + raw_a['opening_date_orig'].notna().sum())}"`
  rows. Opening-date analysis remains impossible.
- **`match_distance_meters` / `match_name_similarity` got worse.** They are null
  for `{python} f"{raw_t['match_distance_meters'].isna().mean() * 100:.1f}"` %
  of tobacco and
  `{python} f"{raw_a['match_distance_meters'].isna().mean() * 100:.1f}"` % of
  alcohol rows, against
  `{python} f"{raw_v3['match_distance_meters'].isna().mean() * 100:.1f}"` % in
  v3; and where present they still sit at exactly 0 m for
  `{python} f"{(raw_a['match_distance_meters'] == 0).mean() * 100:.0f}"` % of the
  alcohol file. They remain a deduplication key, not independent verification.

## `opening_hours_orig` holds two incompatible encodings""",
"""Три вещи, которые следует запомнить:

- **`website_check_status` пуста для всех `{python} f"{n_tob + n_alc:,}"`
  строк** — ровно как в третьей поставке. Эта колонка ни в одной поставке не
  содержала ни одного значения.
- **`opening_date_orig`** заполнена для
  `{python} f"{(raw_t['opening_date_orig'].notna().sum() + raw_a['opening_date_orig'].notna().sum())}"`
  строк. Анализ по дате открытия по-прежнему невозможен.
- **`match_distance_meters` / `match_name_similarity` стали хуже.** Они пусты у
  `{python} f"{raw_t['match_distance_meters'].isna().mean() * 100:.1f}"` %
  табачных и
  `{python} f"{raw_a['match_distance_meters'].isna().mean() * 100:.1f}"` %
  алкогольных строк против
  `{python} f"{raw_v3['match_distance_meters'].isna().mean() * 100:.1f}"` % в
  v3; а там, где значение есть, оно по-прежнему равно ровно 0 м у
  `{python} f"{(raw_a['match_distance_meters'] == 0).mean() * 100:.0f}"` %
  алкогольного файла. Это остаётся ключом дедупликации, а не независимой
  проверкой.

## `opening_hours_orig` содержит две несовместимые кодировки"""),
(
"""2GIS-sourced rows carry a JSON object keyed by weekday; OSM-sourced rows carry
an OSM `opening_hours` string such as `Mo-Su 08:00-22:00`. A reader that assumes
either format silently loses the other half. The trap exists in the third
delivery too — it is simply more visible here, because the tobacco layer's 2GIS
share is so much higher. `v4_common.parse_hours()` handles both and reports
which it found.

# Part III — Provenance: this re-tags the third delivery {#sec-provenance}

The files are named like exports and dated four days apart, which invites
reading them as new fieldwork. They are not.""",
"""Строки из 2GIS несут JSON-объект с ключами по дням недели; строки из OSM несут
строку OSM `opening_hours` вида `Mo-Su 08:00-22:00`. Читатель, рассчитывающий на
один из форматов, молча теряет вторую половину. Ловушка есть и в третьей
поставке — здесь она просто заметнее, потому что доля 2GIS в табачном слое
намного выше. Функция `v4_common.parse_hours()` разбирает оба формата и
сообщает, какой из них встретился.

# Часть III — Происхождение: это переразметка третьей поставки {#sec-provenance}

Файлы названы как выгрузки и датированы с разницей в четыре дня, что подталкивает
читать их как новый сбор данных. Это не так."""),
(
"""Every tobacco record and all but two alcohol records sit within 100 m of an
object the third delivery already held, and almost all of their OSM/2GIS source
ids are ids v3 already cites. **The fourth delivery adds no geographic
coverage.** What it adds is a classification.

That is not a criticism — it is precisely what was asked for — but it settles
how the delivery may be described. It cannot be cited as an independent
enumeration of alcohol or tobacco outlets, because it shares its object pool,
its providers and its errors with the export it is drawn from.

## What the third delivery had called these objects""",
"""Каждая табачная запись и все алкогольные, кроме двух, лежат в пределах 100 м от
объекта, который третья поставка уже содержала, и почти все их идентификаторы
источников OSM/2GIS — это идентификаторы, уже указанные в v3. **Четвёртая
поставка не добавляет географического охвата.** Она добавляет классификацию.

Это не упрёк — именно этого и просили, — но это определяет, как поставку можно
описывать. Её нельзя ссылать как независимый перечень алкогольных или табачных
точек, поскольку она делит пул объектов, поставщиков и ошибки с той выгрузкой,
из которой выведена.

## Как эти объекты называла третья поставка"""),
(
"""This is the delivery's whole content in one table. The third delivery's
`Grocery shops` and `Catering` classes are where the new risk objects come
from — which is exactly the mechanism `reports/egais/eda-egais.pdf` named for
the fivefold undercount: chains sell alcohol under a grocery licence, and cafés
serve it without being bars.

One caveat falls out of the same table. `{python} f"{med_fp}"` records match a
**medical** object — pharmacies caught by the type rule. They are false
positives for both risk factors and should be dropped before any risk index is
built.

# Part IV — Against the 2022 benchmark {#sec-2022}

The 2022 study enumerated `{python} f"{(ref['category_2022'] == 'Alcohol shops').sum()}"`
alcohol shops and `{python} f"{(ref['category_2022'] == 'Tobacco outlets').sum()}"`
tobacco outlets across three okrugs. The matcher is the one used in
`reports/v3/eda-v3-validation.pdf` — 50 m block, rapidfuzz `WRatio` ≥ 0.90 for
an exact tier, ≥ 0.75 for probable — run here without modification.""",
"""Вот всё содержание поставки в одной таблице. Новые объекты риска приходят из
классов `Grocery shops` и `Catering` третьей поставки — а это ровно тот механизм,
который `reports/egais/eda-egais.pdf` назвал причиной пятикратного недоучёта:
сети продают алкоголь по продуктовой лицензии, а кафе подают его, не будучи
барами.

Из той же таблицы следует одна оговорка. `{python} f"{med_fp}"` записей
совпадают с **медицинским** объектом — это аптеки, пойманные правилом по типу.
Для обоих факторов риска это ложные срабатывания, и их следует убрать до
построения любого индекса риска.

# Часть IV — Сверка с эталоном 2022 года {#sec-2022}

Исследование 2022 года перечислило
`{python} f"{(ref['category_2022'] == 'Alcohol shops').sum()}"` алкогольных
магазинов и
`{python} f"{(ref['category_2022'] == 'Tobacco outlets').sum()}"` табачных точек
в трёх округах. Алгоритм сопоставления — тот же, что в
`reports/v3/eda-v3-validation.pdf`: блокировка по 50 м, `WRatio` из rapidfuzz
≥ 0,90 для точного уровня и ≥ 0,75 для вероятного, — запущен здесь без
изменений."""),
(
"""Recall of the 2022 alcohol shops moves from `{python} r_v3_al` to
`{python} r_v4_al`, and tobacco from `{python} r_v3_tb` to `{python} r_v4_tb`.
**Against the 2022 list the fourth delivery is not an improvement.**

That is less damning than it looks, and the `Same site, other name` column says
why. Counting objects matched at *any* tier, including a same-site match under a
different name:""",
"""Полнота обнаружения алкогольных магазинов 2022 года меняется с
`{python} r_v3_al` на `{python} r_v4_al`, табачных точек — с `{python} r_v3_tb`
на `{python} r_v4_tb`. **По списку 2022 года четвёртая поставка улучшением не
является.**

Это менее тяжёлый приговор, чем кажется, и объясняет его колонка
`Same site, other name`. Если считать объекты, совпавшие на *любом* уровне,
включая совпадение по месту под другим названием:"""),
(
"""Four years is long enough for a small alcohol shop to change hands and its sign;
a same-site match under a different name is usually continuity, not error. But
this cannot be *shown* from the data, only argued, so the honest statement is
that the fourth delivery neither improves nor degrades agreement with 2022.""",
"""Четырёх лет достаточно, чтобы небольшой алкогольный магазин сменил владельца и
вывеску; совпадение по месту под другим названием обычно означает
преемственность, а не ошибку. Но *показать* это по данным нельзя, можно лишь
рассуждать, поэтому честная формулировка такова: четвёртая поставка не улучшает
и не ухудшает согласие с 2022 годом."""),
(
"""The overwhelming majority of the layer has no 2022 counterpart — because it is
mostly the inferred tier, and the 2022 study never tried to enumerate ordinary
shops that happen to sell beer. The 2022 list is therefore the **wrong
benchmark** for this delivery. The right one is the licence registry.

# Part V — Against the FSRAR licence registry {#sec-egais}

The licence registry is the only genuinely independent check available: a state
register, compiled for a different purpose, sharing neither providers nor
method with the contractor. Its limits are those established in
`reports/egais/eda-egais.pdf` — it holds **alcohol only**, so the tobacco layer
is untestable here, and it is a *register*, so only rows in force count.

Restricted to mainland city rows in force, it holds
**`{python} f"{len(eg_off)}"` off-trade** and
**`{python} f"{len(eg_on)}"` on-trade** retail licences.

## The fivefold gap closes""",
"""У подавляющего большинства слоя нет соответствия в 2022 году — потому что это
преимущественно выведенный уровень, а исследование 2022 года и не пыталось
перечислять обычные магазины, попутно торгующие пивом. Значит, список 2022 года —
**неподходящий эталон** для этой поставки. Подходящий — реестр лицензий.

# Часть V — Сверка с реестром лицензий ФСРАР {#sec-egais}

Реестр лицензий — единственная действительно независимая проверка из доступных:
государственный реестр, составленный с иной целью, не разделяющий с подрядчиком
ни поставщиков, ни метода. Его ограничения установлены в
`reports/egais/eda-egais.pdf`: он содержит **только алкоголь**, поэтому табачный
слой здесь непроверяем, и он является *реестром*, поэтому считать следует лишь
действующие записи.

Если ограничиться действующими записями по материковой части города, он содержит
**`{python} f"{len(eg_off)}"` розничных лицензий off-trade** и
**`{python} f"{len(eg_on)}"` — on-trade**.

## Пятикратный разрыв закрывается"""),
(
"""The third delivery recognised one alcohol shop for every
**`{python} f"{ratio_v3:.1f}"`** licences in force. The fourth delivery's
off-trade layer sits at **`{python} f"{ratio_v4:.2f}"`** — it now names slightly
*more* outlets than there are licences, which is the expected direction: the
inferred tier will include shops that sell no alcohol, and one licence can cover
a chain outlet that the register lists once.

On-trade agrees less well — `{python} f"{len(alc_on)}"` objects against
`{python} f"{len(eg_on)}"` licences in force — but the on-trade layer is
`{python} f"{alc_on['evidence'].eq('Inferred').mean() * 100:.0f}"` % inferred
from "this is a café", and many cafés genuinely serve no alcohol. Treat the
on-trade count as an upper bound.

## The okrug bias is substantially repaired

This matters more than the city total. The undercount was not uniform: it was
mildest in the centre and worst in the outlying okrugs, which meant any okrug
risk comparison built on the third delivery was biased *toward* the centre.""",
"""Третья поставка распознавала один алкогольный магазин на каждые
**`{python} f"{ratio_v3:.1f}"`** действующих лицензий. Слой off-trade четвёртой
поставки даёт **`{python} f"{ratio_v4:.2f}"`** — он называет чуть *больше* точек,
чем есть лицензий, и это ожидаемое направление: выведенный уровень включает
магазины, алкоголем не торгующие, а одна лицензия может покрывать сетевую точку,
которую реестр перечисляет однократно.

По on-trade согласие хуже — `{python} f"{len(alc_on)}"` объектов против
`{python} f"{len(eg_on)}"` действующих лицензий, — но слой on-trade на
`{python} f"{alc_on['evidence'].eq('Inferred').mean() * 100:.0f}"` % выведен из
признака «это кафе», а многие кафе действительно не подают алкоголь. Считайте
величину on-trade верхней границей.

## Смещение по округам в основном устранено

Это важнее городского итога. Недоучёт не был равномерным: он был наименьшим в
центре и наибольшим в окраинных округах, а значит, любое окружное сравнение
риска, построенное на третьей поставке, смещалось *в пользу* центра."""),
(
"""The third delivery's ratios spread over a factor of
**`{python} f"{sp3:.1f}"`** across okrugs — 12 licences per recognised shop in
Tsiglomensky against 2.9 in Lomonosovsky. The fourth delivery's spread is a
factor of **`{python} f"{sp4:.1f}"`**, and every okrug sits between
`{python} f"{okr['Ratio vs v4'].min():.2f}"` and
`{python} f"{okr['Ratio vs v4'].max():.2f}"`. **Okrug-level alcohol risk
comparisons become defensible for the first time in this project.**

## Spatial corroboration, both directions

Counts can agree while pointing at different places. This checks the locations.""",
"""Отношения третьей поставки разбросаны по округам с кратностью
**`{python} f"{sp3:.1f}"`** — 12 лицензий на один распознанный магазин в
Цигломенском против 2,9 в Ломоносовском. Разброс четвёртой поставки имеет
кратность **`{python} f"{sp4:.1f}"`**, и каждый округ укладывается между
`{python} f"{okr['Ratio vs v4'].min():.2f}"` и
`{python} f"{okr['Ratio vs v4'].max():.2f}"`. **Окружные сравнения
алкогольного риска впервые за весь проект становятся состоятельными.**

## Пространственное подтверждение в обе стороны

Итоги могут совпадать, указывая при этом на разные места. Здесь проверяются
координаты."""),
(
"""Read the fourth column. The share of licensed outlets in force with a matching
export object within 50 m rises from **`{python} f"{rev3_50}"` %** under the
third delivery to **`{python} f"{rev4_50}"` %** under the fourth, and reaches
`{python} f"{rev4_100}"` % at 100 m. The remaining gap is consistent with the
registry's own coordinate quality, which
`reports/egais/eda-egais.pdf` shows is missing for a substantial minority of
rows and biased toward recently issued licences.""",
"""Смотрите четвёртый столбец. Доля действующих лицензированных точек, у которых в
радиусе 50 м есть соответствующий объект выгрузки, растёт с
**`{python} f"{rev3_50}"` %** при третьей поставке до
**`{python} f"{rev4_50}"` %** при четвёртой и достигает
`{python} f"{rev4_100}"` % на 100 м. Оставшийся разрыв согласуется с качеством
координат самого реестра: `reports/egais/eda-egais.pdf` показывает, что они
отсутствуют у заметного меньшинства записей и смещены в сторону недавно выданных
лицензий."""),
(
"""# Part VI — The risk surface {#sec-surface}

With the calibration established, the layer can be read as a risk surface.""",
"""# Часть VI — Поверхность риска {#sec-surface}

После того как калибровка установлена, слой можно читать как поверхность риска."""),
(
"""The gradient runs from the two central okrugs at roughly
`{python} f"{dens.loc['Lomonosovsky', 'per_100']:.0f}"` risk sites per 100
objects to Tsiglomensky at
`{python} f"{dens.loc['Tsiglomensky', 'per_100']:.0f}"`. Read this as
*composition*, not absolute density: the outlying okrugs have fewer objects of
every kind, and a larger share of what they do have is a shop that sells beer
and cigarettes. A per-capita reading would need population by okrug, which no
delivery has supplied.""",
"""Градиент идёт от двух центральных округов с примерно
`{python} f"{dens.loc['Lomonosovsky', 'per_100']:.0f}"` точками риска на 100
объектов до Цигломенского с
`{python} f"{dens.loc['Tsiglomensky', 'per_100']:.0f}"`. Читать это следует как
*состав*, а не как абсолютную плотность: в окраинных округах меньше объектов
всякого рода, и бо́льшая доля имеющихся — это магазин, торгующий пивом и
сигаретами. Прочтение на душу населения потребовало бы численности населения по
округам, которой не дала ни одна поставка."""),
(
"""## The tobacco layer has no benchmark

Everything in @sec-egais applies to alcohol only. The licence registry holds
**no tobacco class at all** — the regulator's remit covers both, the published
data does not — and the 2022 tobacco list is
`{python} f"{(ref['category_2022'] == 'Tobacco outlets').sum()}"` objects in
three okrugs, which @sec-2022 shows the delivery reproduces about a third of by
name.

So the `{python} f"{n_tob}"`-object tobacco layer rests on the contractor's
inference and on 2GIS category labels, and **nothing in this repository can
check it**. Its high 2GIS corroboration rate is a point in its favour and is not
the same thing as verification. Report tobacco results with that stated.

# Conclusions

**On the schema question.** The contractor's promise holds where it is easy to
check and fails where it is not. The 22 columns, their order and their types are
identical to the third delivery, so existing code reads the files unchanged. But
`category_orig` and `type_orig` carry a fourth vocabulary sharing no value with
any earlier delivery, and the project's shared `recode_2022()` silently drops
`{python} f"{lost}"` of `{python} f"{n_tob}"` tobacco rows on it. Schema
compatibility at the column level is not schema compatibility.

**On what the delivery is.** It is a risk-attribution layer over the third
delivery, not a fourth survey: every tobacco record and all but two alcohol
records sit within 100 m of an object v3 already held. Four rows in five are an
inference from the object's type, which the contractor's own comment says
requires separate checking. It should be described as a classification of
existing objects, and its two tiers reported separately.

**On the 2022 benchmark.** No improvement — recall moves from
`{python} r_v3_al` to `{python} r_v4_al` for alcohol and from
`{python} r_v3_tb` to `{python} r_v4_tb` for tobacco. Most of the shortfall is
same-site rebranding rather than absence, but that is an argument, not a
measurement. The 2022 list is the wrong benchmark for a layer that is mostly
inferred availability.

**On the licence registry — the finding that matters.** The fivefold alcohol
undercount closes. Off-trade objects rise from
`{python} f"{(v3['category_2022'] == 'Alcohol shops').sum()}"` to
`{python} f"{len(alc_off)}"` against `{python} f"{len(eg_off)}"` licences in
force; the licences-per-object ratio moves from
`{python} f"{ratio_v3:.1f}"` to `{python} f"{ratio_v4:.2f}"`; the okrug spread
narrows from a factor of `{python} f"{sp3:.1f}"` to
`{python} f"{sp4:.1f}"`; and the share of licensed outlets visible to the export
within 50 m rises from `{python} f"{rev3_50}"` % to `{python} f"{rev4_50}"` %.
The centre-bias that made okrug comparisons unusable is substantially repaired.

**What still cannot be done.** The tobacco layer has no independent benchmark of
any kind. The alcohol layer is
`{python} f"{osm_only_alc * 100:.1f}"` % OSM-only, so it is well *calibrated*
without being *verified*. `{python} f"{med_fp}"` pharmacies are false positives
and must be removed before any index is built. And the five okrugs outside the
2022 study remain unvalidated against any object-level benchmark — the licence
registry now covers them for alcohol, which is a real gain, but for tobacco
they remain dark.""",
"""## У табачного слоя нет эталона

Всё, сказанное в @sec-egais, относится только к алкоголю. Реестр лицензий
**вообще не содержит табачного класса** — полномочия регулятора охватывают оба
продукта, опубликованные данные нет, — а табачный список 2022 года насчитывает
`{python} f"{(ref['category_2022'] == 'Tobacco outlets').sum()}"` объектов в трёх
округах, из которых, как показывает @sec-2022, поставка воспроизводит по названию
около трети.

Таким образом, табачный слой из `{python} f"{n_tob}"` объектов держится на выводе
подрядчика и на рубриках 2GIS, и **проверить его в этом репозитории нечем**.
Высокая доля подтверждения через 2GIS говорит в его пользу, но это не то же
самое, что верификация. Приводя табачные результаты, оговаривайте это.

# Выводы

**По вопросу о схеме.** Обещание подрядчика выполняется там, где его легко
проверить, и нарушается там, где трудно. 22 колонки, их порядок и типы идентичны
третьей поставке, поэтому существующий код читает файлы без изменений. Но
`category_orig` и `type_orig` несут четвёртый словарь, не имеющий ни одного
общего значения с прежними поставками, и общий для проекта `recode_2022()` молча
теряет на нём `{python} f"{lost}"` из `{python} f"{n_tob}"` табачных строк.
Совместимость схемы на уровне колонок не есть совместимость схемы.

**О том, чем является поставка.** Это слой атрибуции риска поверх третьей
поставки, а не четвёртое обследование: каждая табачная запись и все алкогольные,
кроме двух, лежат в пределах 100 м от объекта, уже имевшегося в v3. Четыре записи
из пяти — вывод из типа объекта, который, по собственному комментарию подрядчика,
требует отдельной проверки. Описывать это следует как классификацию уже известных
объектов, а два её уровня приводить раздельно.

**По эталону 2022 года.** Улучшения нет: полнота меняется с `{python} r_v3_al` на
`{python} r_v4_al` по алкоголю и с `{python} r_v3_tb` на `{python} r_v4_tb` по
табаку. Бо́льшая часть недостачи — смена вывески на прежнем месте, а не
отсутствие объекта, но это рассуждение, а не измерение. Список 2022 года —
неподходящий эталон для слоя, состоящего преимущественно из выведенной
доступности.

**По реестру лицензий — вывод, который имеет значение.** Пятикратный недоучёт
алкоголя закрывается. Число объектов off-trade растёт с
`{python} f"{(v3['category_2022'] == 'Alcohol shops').sum()}"` до
`{python} f"{len(alc_off)}"` против `{python} f"{len(eg_off)}"` действующих
лицензий; отношение лицензий к объектам меняется с
`{python} f"{ratio_v3:.1f}"` на `{python} f"{ratio_v4:.2f}"`; разброс по округам
сужается с кратности `{python} f"{sp3:.1f}"` до
`{python} f"{sp4:.1f}"`; а доля лицензированных точек, видимых выгрузке в радиусе
50 м, растёт с `{python} f"{rev3_50}"` % до `{python} f"{rev4_50}"` %. Смещение к
центру, делавшее окружные сравнения непригодными, в основном устранено.

**Чего по-прежнему сделать нельзя.** У табачного слоя нет независимого эталона
никакого рода. Алкогольный слой на
`{python} f"{osm_only_alc * 100:.1f}"` % держится на одном OSM, то есть он хорошо
*откалиброван*, но не *верифицирован*. `{python} f"{med_fp}"` аптек являются
ложными срабатываниями и должны быть удалены до построения любого индекса. А пять
округов вне исследования 2022 года остаются не проверенными ни по какому
пообъектному эталону — реестр лицензий теперь покрывает их по алкоголю, что
является реальным приобретением, но по табаку они остаются в темноте."""),
]


def main() -> int:
    out = io.open(SRC, encoding="utf-8").read()
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

    leftovers, incode, fm = [], False, 0
    for n, line in enumerate(out.split("\n"), 1):
        if fm < 2:
            if line.strip() == "---":
                fm += 1
            continue
        if line.startswith("```"):
            incode = not incode
            continue
        if incode or not line.strip():
            continue
        if re.search(r"[A-Za-z]{4,}", re.sub(r"`[^`]*`", "", line)):
            leftovers.append(f"  L{n}: {line[:88]}")
    if leftovers:
        print("Check for untranslated prose (inline code stripped):")
        print("\n".join(leftovers))

    io.open(DST, "w", encoding="utf-8").write(out)
    print(f"written {DST} ({len(out):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
