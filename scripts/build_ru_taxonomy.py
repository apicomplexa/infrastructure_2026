"""Build the Russian twin of analysis/v4/taxonomy-v4.qmd.

Run from the repo root:  pixi run python scripts/build_ru_taxonomy.py
Then normalise the numbers:  pixi run python scripts/ru_numfmt.py

Only prose, captions and the front matter are translated.  Every {python} cell is
copied byte-for-byte -- the twin needs no code edits at all, because the setup
cell finds the repository root itself -- so the rendered tables and figures stay
in English exactly as in the source document.
"""
import io
import re
import sys

SRC = "analysis/v4/taxonomy-v4.qmd"
DST = "analysis/v4/taxonomy-v4-ru.qmd"

FRONT_OLD = '''title: "Arkhangelsk Urban Infrastructure — the 2022 taxonomy as seven lists"
subtitle: "A corrected multi-label rule over the city-wide export, and an honest account of what validates it"
author: "Northern State Medical University — Infrastructure project"
date: today
lang: en
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''
FRONT_NEW = '''title: "Городская инфраструктура Архангельска — таксономия 2022 года как семь списков"
subtitle: "Исправленное правило множественной принадлежности поверх общегородской выгрузки и честный отчёт о том, чем оно проверено"
author: "СГМУ — проект по городской инфраструктуре"
date: today
lang: ru
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''

CAPTIONS = {
    "Class counts before and after. Seven independent flags, so an object may appear in more than one bar; the old rule's bars are mutually exclusive by construction.":
        "Численность классов до и после. Семь независимых признаков, поэтому объект может попасть более чем в один столбец; столбцы старого правила взаимно исключают друг друга по построению.",
    "Evidence composition per class. A count resting on `category` is the export's own assertion; a count resting on `name` is a guess from the shop sign.":
        "Состав свидетельств по классам. Счёт, опирающийся на `category`, — это утверждение самой выгрузки; счёт, опирающийся на `name`, — догадка по вывеске.",
}

BLOCKS = [
(
"""# What this report is

The 2022 study recorded seven lists of objects — medical organisations, sport
facilities, shops, catering, specialised alcohol shops, tobacco outlets and
industrial objects. Every report in this repository so far has asked of a 2026
object *which one of the seven is it*, and answered with
`v3_common.recode_2022()`, which resolves seven predicates through a priority
order and keeps the first.

That is the wrong question. An object can sit on several of the lists at once, a
grocery that sells tobacco being the ordinary case, and a priority order does not
express that — it silently discards every class after the first. This report
replaces the single answer with **seven independent booleans**, one per list,
and attaches to each the *evidence* that put the object there.

It is deliberately not a model. The companion document
`docs/classifier_design.md` sets out why a learned classifier over this taxonomy
cannot be built in the shape it was commissioned: the labelled rows are almost
entirely rows a free rule already gets right, the negative set holds more true
positives than the positive set for the classes that matter, and — decisively —
the export's fields do not encode co-membership at all, so no amount of
labelling, model class or calibration reaches the seven-probability deliverable.
Section 10 of that document is the analysis this report implements.

::: {.callout-important}
## Scope of the validation, stated once and up front

The rule below is checked against the 2022 benchmark on **1,133 of 7,263
objects — 15.6 % of the city**, in three of nine okrugs, and accuracy on that
slice tracks how easily an object could be linked across four years. The
remaining 84 % is unvalidated by anything. Every number in §5 carries that
qualification; no number in this report is a city-wide accuracy guarantee.
:::

# Three defects, found where nobody was looking

All three sat on the 84 % that no evaluation reaches, which is why four years of
reports did not surface them.

## D1 — fifty-one greengrocers outside the taxonomy

`GROCERY_TYPES` holds the 2022 spelling `фрукты-овощи`. The 2026 export writes
the same two words in the other order, `Овощи и фрукты`, and the membership test
is exact string equality, so 51 objects fell through to *outside the 2022
scheme*.

This is the third member of a family the repository already documents: the
`GROCERY_TYPES` case mismatch that emptied the grocery class in the v1 and v2
reports, and the tobacco rule testing for `табак` while the fourth delivery
spells the stem `табач-`. Rather than add one more string, types are now matched
on their **bag of significant words**, so word order, separator, case and ё/е
stop mattering — and `assert_no_missed_types()` fails the build if any
unclassified type still carries an in-taxonomy stem, so there is no fourth
member.

## D2 — a third of the sport class was not a sport facility""",
"""# Что представляет собой этот отчёт

Исследование 2022 года зафиксировало семь списков объектов — медицинские
организации, спортивные сооружения, магазины, общепит, специализированные
алкогольные магазины, точки продажи табака и промышленные объекты. Все отчёты
этого репозитория до сих пор спрашивали об объекте 2026 года *который из семи
это*, и отвечали функцией `v3_common.recode_2022()`, которая разрешает семь
предикатов через порядок приоритета и оставляет первый.

Это неверный вопрос. Объект может находиться сразу в нескольких списках —
обычный случай здесь продуктовый магазин, торгующий табаком, — а порядок
приоритета этого не выражает: он молча отбрасывает все классы после первого.
Настоящий отчёт заменяет единственный ответ **семью независимыми булевыми
признаками**, по одному на список, и присоединяет к каждому *свидетельство*, по
которому объект туда попал.

Это намеренно не модель. Сопроводительный документ `docs/classifier_design.md`
излагает, почему обучаемый классификатор над этой таксономией нельзя построить в
том виде, в каком он был заказан: размеченные строки — это почти сплошь строки,
на которых и без всякой модели правило уже даёт верный ответ; по значимым
классам в отрицательном множестве истинно положительных больше, чем в
положительном; и — решающим образом — поля выгрузки вообще не кодируют
совместную принадлежность, так что никакой объём разметки, никакой класс моделей
и никакая калибровка не приводят к заказанному результату из семи вероятностей.
Раздел 10 того документа и есть анализ, который реализует настоящий отчёт.

::: {.callout-important}
## Границы валидации, сказанные один раз и сразу

Описанное ниже правило сверено с эталоном 2022 года на **1 133 объектах из
7 263 — 15,6 % города**, в трёх округах из девяти, и точность на этом срезе
следует за тем, насколько легко объект удавалось связать через четыре года.
Остальные 84 % не проверены ничем. Каждое число в §5 несёт эту оговорку; ни одно
число в этом отчёте не является гарантией точности по городу в целом.
:::

# Три дефекта, найденные там, куда никто не смотрел

Все три сидели на тех 84 %, до которых не доходит ни одна проверка, — потому
четыре года отчётов их и не выявили.

## D1 — пятьдесят один овощной магазин вне таксономии

В `GROCERY_TYPES` записано написание 2022 года `фрукты-овощи`. Выгрузка 2026
года пишет те же два слова в обратном порядке, `Овощи и фрукты`, а проверка
принадлежности — это точное равенство строк, поэтому 51 объект провалился в
категорию *вне схемы 2022 года*.

Это третий член семейства, уже описанного в репозитории: несовпадение регистра в
`GROCERY_TYPES`, опустошившее продуктовый класс в отчётах v1 и v2, и табачное
правило, ищущее `табак`, тогда как четвёртая поставка пишет корень `табач-`.
Вместо того чтобы добавить ещё одну строку, типы теперь сопоставляются по
**мешку значимых слов**, так что порядок слов, разделитель, регистр и ё/е
перестают иметь значение, — а `assert_no_missed_types()` роняет сборку, если
хоть один неклассифицированный тип всё ещё несёт корень из таксономии, так что
четвёртого члена не будет.

## D2 — треть спортивного класса не была спортивным объектом"""),
(
"""The old rule searches a blob that **includes `category_orig`** for the stem
`спорт`. The export's category `Досуг и спорт` therefore carried every sauna in
the city into the sport class — 63 objects, where the 2022 benchmark itself
labels a sauna `Общепит`. Plain substring search did the rest: `спорт` is inside
*па·спорт·ный стол* (nine passport offices) and *тран·спорт·ная компания* (seven
haulage firms), and `бар` is inside *лом·бар·д*.

Three changes: stems are matched on word boundaries; they are matched on
`type_orig` and `name_orig` only, never on `category_orig`; and sport retail
(`Спортивный магазин`, 20 objects) gets its own flag, because a shop that sells
football boots is not a place anyone exercises.

`Sport` is reported per okrug in the accessibility maps. It was overstated by
about a third.

## D3 — thirty-five rows of the export carry the wrong type""",
"""Старое правило ищет корень `спорт` в склейке, которая **включает
`category_orig`**. Поэтому категория выгрузки `Досуг и спорт` затащила в
спортивный класс все сауны города — 63 объекта, тогда как сам эталон 2022 года
относит сауну к `Общепит`. Остальное довершил простой поиск подстроки: `спорт`
сидит внутри *па·спорт·ный стол* (девять паспортных столов) и
*тран·спорт·ная компания* (семь транспортных компаний), а `бар` — внутри
*лом·бар·д*.

Три изменения: корни сопоставляются по границам слов; они ищутся только в
`type_orig` и `name_orig` и никогда в `category_orig`; а спортивная розница
(`Спортивный магазин`, 20 объектов) получает собственный признак, потому что
магазин, торгующий бутсами, — не место, где кто-либо занимается спортом.

`Sport` приводится по округам в картах доступности. Он был завышен примерно на
треть.

## D3 — тридцать пять строк выгрузки несут неверный тип"""),
(
"""Thirty-five objects pair `category_orig = Точки продажи табака` with
`type_orig = Продуктовый магазин`. The names settle what they are.

This defect was first read the other way round — as 35 grocery shops made
invisible by the priority order, since a grocery tagged as a tobacco outlet
loses its grocery membership. Building the seven flags is what disproved it.
Freed from the priority order, all 35 became grocery shops *as well as* tobacco
outlets, and the result was obviously wrong: a vape shop is not a grocery. The
old rule returned the right answer for these rows **by accident**, and that is
precisely what kept the defect hidden.

So the finding is not about the recoder at all. It is that `type_orig` is
unreliable on a known slice of the export. The rule resolves it through the
evidence hierarchy it already declares — where `category_orig` exactly names one
of the seven classes, that assertion outranks anything inferred from the type or
the fascia — and the 35 rows go into the review queue, where a wrong field
belongs.

# What moved""",
"""Тридцать пять объектов сочетают `category_orig = Точки продажи табака` с
`type_orig = Продуктовый магазин`. Названия не оставляют сомнений в том, что это
за объекты.

Сначала этот дефект прочли в обратную сторону — как 35 продуктовых магазинов,
сделанных невидимыми порядком приоритета: продуктовый магазин, помеченный как
точка продажи табака, теряет принадлежность к продуктовому классу. Опровергло
такое прочтение именно построение семи признаков. Освободившись от порядка
приоритета, все 35 стали продуктовыми магазинами *в дополнение к* точкам продажи
табака, и результат оказался очевидно неверным: вейп-шоп — не продуктовый
магазин. Старое правило давало на этих строках верный ответ **по случайности**,
и как раз это и удерживало дефект в тени.

Значит, находка вообще не о перекодировщике. Она о том, что `type_orig`
недостоверен на известном срезе выгрузки. Правило разрешает это через иерархию
свидетельств, которую оно и так объявляет: там, где `category_orig` точно
называет один из семи классов, это утверждение старше всего, что выведено из
типа или из вывески, — а 35 строк уходят в очередь на ручную проверку, где
неверному полю и место.

# Что сдвинулось"""),
(
"""`Grocery shops` gains 91: the 51 of D1, the 35 of D3, and five objects reached by
spelling variants the word-bag key now folds together. `Medical` loses six, of
which three are veterinary clinics — animal health is not the health
infrastructure this study measures. `Alcohol shops` and `Tobacco outlets` do not
move at all, which is the expected result: both rest on the export's own
category, and neither was ever the class with a spelling problem.

# What each count rests on

This is the column the repository did not have. Each flag records the strongest
field that carried the object into the class, and the three are not
interchangeable kinds of claim.""",
"""`Grocery shops` прибавляет 91 объект: 51 из D1, 35 из D3 и ещё пять, до которых
дотянулись варианты написания, теперь сводимые вместе ключом по мешку слов.
`Medical` теряет шесть, из них три — ветеринарные клиники: здоровье животных не
относится к той инфраструктуре здоровья, которую измеряет это исследование.
`Alcohol shops` и `Tobacco outlets` не сдвигаются вовсе, и это ожидаемый
результат: оба класса опираются на собственную категорию выгрузки, и ни один из
них никогда не был классом с проблемой написания.

# На чём держится каждый счёт

Это тот столбец, которого в репозитории не было. Каждый признак фиксирует самое
сильное поле, которое завело объект в класс, и три этих поля — не
взаимозаменяемые виды утверждения."""),
(
"""Read that table before quoting any count from it.

- **`Tobacco outlets` is 100 % `category`.** Every one of the 60 is the export
  asserting it. Nothing in this repository independently confirms any of them:
  the licence registry has no tobacco class, and the 2022 tobacco list is 46
  objects in three okrugs. That is not a weakness of the rule; it is the state of
  the evidence, and it is why the fourth delivery's tobacco layer is reported
  with its provenance and no verification rate.
- **`Grocery shops` is 100 % `type`.** The class is defined by what kind of shop
  it is, which is the most stable of the three signals.
- **`Industrial` is 100 % `name`, all 33 objects.** The class is a fascia
  keyword search and nothing more: it contains a pizza chain called
  *ПиццаФабрика*, a hostel and a jewellery shop. The 2022 benchmark has ten
  industrial objects and not one of them could be linked to the export, so there
  is no way to check it either. **Do not report `Industrial` per okrug.**
- **`Sport`'s six `name` rows** are the residue after D2: three sports schools, a
  university sports building, a therapeutic-exercise centre, and the city
  sports administration office — the last of which is an office, not a facility.
  Six objects is a rounding error on 256, but it is the kind of judgement the
  manual audit exists to settle.

# Co-membership: what the data can and cannot say""",
"""Прочитайте эту таблицу, прежде чем цитировать из неё любое число.

- **`Tobacco outlets` — на 100 % `category`.** Каждый из 60 объектов есть
  утверждение самой выгрузки. Ничто в этом репозитории не подтверждает ни один
  из них независимо: в реестре лицензий табачного класса нет, а табачный список
  2022 года — это 46 объектов в трёх округах. Это не слабость правила, это
  состояние доказательной базы, и именно поэтому табачный слой четвёртой
  поставки приводится с указанием происхождения и без доли верификации.
- **`Grocery shops` — на 100 % `type`.** Класс определяется тем, какого рода это
  магазин, а это самый устойчивый из трёх сигналов.
- **`Industrial` — на 100 % `name`, все 33 объекта.** Класс есть не более чем
  поиск ключевых слов по вывеске: в нём сидят сеть пиццерий *ПиццаФабрика*,
  хостел и ювелирный магазин. В эталоне 2022 года десять промышленных объектов,
  и ни один из них не удалось связать с выгрузкой, так что проверить класс тоже
  нечем. **Не приводите `Industrial` по округам.**
- **Шесть строк `Sport` со свидетельством `name`** — это остаток после D2: три
  спортивные школы, университетский спортивный корпус, центр лечебной
  физкультуры и городское управление по спорту, последнее из которых —
  учреждение, а не сооружение. Шесть объектов на 256 — ошибка округления, но это
  ровно тот род суждения, ради которого и существует ручной аудит.

# Совместная принадлежность: что данные могут сказать, а чего не могут"""),
(
"""**Seven objects in the whole city carry two of the seven classes. Two of those
seven are genuine**, and no object carries three.

The two are `Ларец, магазин-бистро` and `Бонус, магазин-кафе` — a grocery that is
also a snack bar, which is exactly the kind of double membership the 2022 study
recorded. The other five are a grocery flagged `Industrial` because its fascia
says *мясокомбинат* or *Хладокомбинат*, which is an artefact of the fascia search
rather than a second membership.

That is the finding of this section, and it is the strongest statement in the
report: **the export's fields encode essentially no co-membership at all.** They
state what an object *is*. They do not state what it *sells*. Nothing in
`category_orig`, `type_orig` or `name_orig` records that a `Продуктовый магазин`
also sells cigarettes — and the fourth delivery's risk layers imply that on the
order of 560 sites in this city do.

This is why the commissioned deliverable — seven calibrated probabilities
expressing multi-label membership — cannot be produced from this source, by any
model. The information is not in the inputs. More labelling would not create it
and neither would a larger model.

Two sources do carry it, and both are already in this repository: the
contractor's v4 risk layers (`data/raw_v4/`, with the caveat that 82 % of them
are the inferred tier the contractor's own comment says needs separate checking)
and the FSRAR licence registry for alcohol (`data/processed/v4_licences/v4_licences.csv`,
which matches 80.6 % of v4 records to a licence and finds a v4 object at the
address of 97.7 % of the 442 active off-trade retail licences). **Every
co-membership claim must be built from those, never from the table above.**


# Validation against the 2022 benchmark""",
"""**Во всём городе два класса из семи несут семь объектов. Из этих семи подлинны
два**, и ни один объект не несёт трёх классов.

Эти два — `Ларец, магазин-бистро` и `Бонус, магазин-кафе`: продуктовый магазин,
он же закусочная, а это ровно тот вид двойной принадлежности, который фиксировало
исследование 2022 года. Остальные пять — продуктовые магазины, помеченные как
`Industrial` из-за вывески со словом *мясокомбинат* или *Хладокомбинат*, и это
артефакт поиска по вывеске, а не вторая принадлежность.

В этом и состоит вывод настоящего раздела, и это самое сильное утверждение
отчёта: **поля выгрузки практически не кодируют совместную принадлежность.** Они
сообщают, чем объект *является*. Они не сообщают, чем он *торгует*. Ни
`category_orig`, ни `type_orig`, ни `name_orig` не фиксируют того, что
`Продуктовый магазин` торгует ещё и сигаретами, — а слои риска четвёртой
поставки дают основания полагать, что в этом городе так делают порядка 560
точек.

Именно поэтому заказанный результат — семь калиброванных вероятностей,
выражающих множественную принадлежность, — из этого источника получить нельзя
никакой моделью. Нужной информации нет во входных данных. Её не создадут ни
дополнительная разметка, ни более крупная модель.

Два источника её всё же несут, и оба уже есть в репозитории: слои риска v4 от
подрядчика (`data/raw_v4/`, с оговоркой, что 82 % из них — выведенный уровень,
который, по собственному комментарию подрядчика, требует отдельной проверки) и
реестр лицензий ФСРАР по алкоголю (`data/processed/v4_licences/v4_licences.csv`, который
сопоставляет с лицензией 80,6 % записей v4 и находит объект v4 по адресу у
97,7 % из 442 действующих розничных лицензий без общепита). **Любое утверждение
о совместной принадлежности должно строиться на них и никогда — на таблице
выше.**


# Сверка с эталоном 2022 года"""),
(
"""Two classes carry no usable number. `Tobacco outlets` has 16 labelled rows, so
its recall of 0.625 is 10 of 16 and a confidence interval on it spans most of the
unit interval. `Industrial` has none at all — not one of the 2022 study's ten
industrial objects could be linked to the export — so the row is blank rather
than showing the 0.000 precision that a single false positive would otherwise
produce.""",
"""Два класса не несут пригодного числа. У `Tobacco outlets` 16 размеченных строк,
так что показанная полнота — это 10 из 16, и доверительный интервал для неё
покрывает бо́льшую часть отрезка от нуля до единицы. У `Industrial` размеченных
строк нет вовсе — ни один из десяти промышленных объектов исследования 2022 года
не удалось связать с выгрузкой, — поэтому строка оставлена пустой и не
показывает ту нулевую точность, которую иначе дало бы одно-единственное ложное
срабатывание."""),
(
"""That last category is not a rounding error. `Medical` recall appears to dip by
one row against the old rule; the row is a dental clinic in the 2022 list that
the matcher linked to the **Central Veterinary Clinic** in the export. The new
rule's veterinary veto is right and the benchmark link is wrong, which is exactly
the failure mode the error decomposition in
`data/processed/taxonomy_2022/taxonomy_2022_validation.txt` separates out.

::: {.callout-warning}
## Why this table cannot be extrapolated

Linkage to the 2022 benchmark is **systematically class-dependent**: medical
organisations link at 86.5 %, alcohol shops at 49.1 %, sport at 42.0 %, tobacco
at 34.8 %, industrial at 0 %. It is worse inside classes — supermarkets link at
86.4 % against 48.5 % for ordinary grocery shops, sports complexes at 84.2 %
against 20.0 % for outdoor sports grounds. The table above is therefore measured
on indoor, commercial, chain-branded objects whose names survived four years,
and applied to a city where outdoor pitches and corner shops are most of the
population. The one axis that is *not* distorted is okrug.
:::

# By okrug""",
"""Последняя категория — не ошибка округления. Полнота `Medical` как будто
проседает на одну строку против старого правила; эта строка — стоматологическая
клиника из списка 2022 года, которую алгоритм сопоставления связал с
**Центральной ветеринарной клиникой** в выгрузке. Ветеринарное вето нового
правила право, а связь с эталоном ошибочна, — и это ровно тот режим отказа,
который выделяет разложение ошибок в
`data/processed/taxonomy_2022/taxonomy_2022_validation.txt`.

::: {.callout-warning}
## Почему эту таблицу нельзя экстраполировать

Связывание с эталоном 2022 года **систематически зависит от класса**: медицинские
организации связываются в 86,5 % случаев, алкогольные магазины — в 49,1 %,
спорт — в 42,0 %, табак — в 34,8 %, промышленность — в 0 %. Внутри классов ещё
хуже: супермаркеты связываются в 86,4 % случаев против 48,5 % у обычных
продуктовых магазинов, спорткомплексы — в 84,2 % против 20,0 % у открытых
спортивных площадок. Стало быть, таблица выше измерена на закрытых,
коммерческих, сетевых объектах, названия которых пережили четыре года, а
применяется к городу, где открытые площадки и магазины у дома составляют
бо́льшую часть совокупности. Единственная ось, которая при этом *не* искажена, —
округ.
:::

# По округам"""),
(
"""Three of these nine okrugs — Lomonosovsky, Oktyabrsky and Maiskaya Gorka — carry
the 2022 benchmark. The other six hold 1,649 objects, 22.7 % of the city, with no
object-level check of any kind for any class. For alcohol the licence registry
now covers all nine; for everything else the six stay dark, and a per-okrug
figure drawn from them should ship marked as extrapolated or not ship.

`Industrial` appears in this table for completeness and must not be read from
it: 33 objects city-wide, every one of them a fascia keyword match.

# What happens next

**The review queue** (`data/processed/taxonomy_2022/taxonomy_2022_review_queue.csv`) ranks every
object whose membership rests on weak evidence — the `name` rows, the
multi-label cells, sport retail, and types that are near-misses of a known class
type. It is work, not a number: a human going down it fixes real records.

**The audit** (`data/processed/taxonomy_2022/taxonomy_2022_audit_sample.csv`, protocol in
`docs/taxonomy_2022_audit_protocol.md`) is 600 objects in six strata drawn over
the rule's output across the whole city, including a simple random sample of all
7,263 so the stratified cells can be reweighted back. It costs about twenty
hours. It is the only instrument in this repository that reaches the 84 % the
benchmark does not, and the only one that can settle the definitional questions —
whether a sauna, a sports shop or a university canteen belongs on a 2022 list.

**Two questions belong to the authors of the 2022 study**, not to us. Is
`Магазины` "grocery shops" or "shops of any kind"? All 400 of its rows are food
retail and there is no non-food retail in the class at all, so the data reads as
a grocery class with a general name — but the answer changes the target and every
comparison downstream. And does `Спортивные объекты` include sports shops and
saunas? On the benchmark's own evidence it excludes at least saunas.

# What this does not do

- **No probabilities.** Seven booleans with a stated evidence level, not seven
  calibrated scores. The design document explains why the calibrated form is not
  reachable from these inputs.
- **No model.** Nothing here is learned, and nothing here needs a GPU.
- **No co-membership beyond the export's own fields.** §4's 49 objects are a
  floor roughly an order of magnitude below reality.
- **No tobacco verification rate.** The 60 tobacco objects rest entirely on the
  export's category and nothing in this repository can check them.
- **No `Industrial` anywhere it would be read as a measurement.**
- **No city-wide accuracy claim.** 15.6 % validated, at the easy end of the
  distribution, in three okrugs of nine.

The old rule remains in `v3_common.recode_2022()` and the rendered v3 reports
still carry the numbers it produces. That is deliberate — those reports are a
record of what was delivered and when. The figures corrected here are the ones to
cite going forward.""",
"""Три из этих девяти округов — Ломоносовский, Октябрьский и Майская Горка — несут
эталон 2022 года. Остальные шесть содержат 1 649 объектов, 22,7 % города, без
какой бы то ни было пообъектной проверки по какому бы то ни было классу. По
алкоголю реестр лицензий теперь покрывает все девять; по всему прочему шесть
округов остаются в темноте, и окружной показатель, взятый оттуда, следует либо
публиковать с пометкой «экстраполяция», либо не публиковать вовсе.

`Industrial` присутствует в этой таблице ради полноты, и читать его из неё
нельзя: 33 объекта по городу, и каждый из них — совпадение ключевого слова в
вывеске.

# Что дальше

**Очередь на ручную проверку**
(`data/processed/taxonomy_2022/taxonomy_2022_review_queue.csv`) ранжирует каждый объект, чья
принадлежность держится на слабом свидетельстве, — строки со свидетельством
`name`, ячейки с несколькими классами, спортивную розницу и типы, чуть не
дотянувшие до известного типа класса. Это работа, а не число: человек, идущий по
ней сверху вниз, исправляет реальные записи.

**Аудит** (`data/processed/taxonomy_2022/taxonomy_2022_audit_sample.csv`, протокол в
`docs/taxonomy_2022_audit_protocol.md`) — это 600 объектов в шести стратах,
отобранных по выходу правила на всём городе, включая простую случайную выборку
из всех 7 263, чтобы стратифицированные ячейки можно было перевзвесить обратно.
Он стоит около двадцати часов. Это единственный инструмент в этом репозитории,
который достаёт до тех 84 %, куда эталон не достаёт, и единственный, способный
решить вопросы определений: относится ли сауна, спортивный магазин или
университетская столовая к спискам 2022 года.

**Два вопроса адресованы авторам исследования 2022 года**, а не нам. Что такое
`Магазины` — «продуктовые магазины» или «магазины любого рода»? Все 400 строк
этого класса — продовольственная розница, а непродовольственной в классе нет
вовсе, так что данные читаются как продуктовый класс с общим названием, — но от
ответа зависят и целевая переменная, и всякое сравнение ниже по течению. И
включают ли `Спортивные объекты` спортивные магазины и сауны? По собственным
свидетельствам эталона они исключают по меньшей мере сауны.

# Чего этот отчёт не делает

- **Никаких вероятностей.** Семь булевых признаков с указанным уровнем
  свидетельства, а не семь калиброванных оценок. Проектный документ объясняет,
  почему калиброванная форма из этих входных данных недостижима.
- **Никакой модели.** Здесь ничего не обучается, и ничему здесь не нужен GPU.
- **Никакой совместной принадлежности сверх собственных полей выгрузки.** 49
  объектов из §4 — это нижняя граница, примерно на порядок ниже реальности.
- **Никакой доли верификации по табаку.** 60 табачных объектов целиком опираются
  на категорию выгрузки, и проверить их в этом репозитории нечем.
- **Никакого `Industrial` там, где он был бы прочитан как измерение.**
- **Никакого утверждения о точности по городу в целом.** Проверено 15,6 %, на
  лёгком конце распределения, в трёх округах из девяти.

Старое правило остаётся в `v3_common.recode_2022()`, и свёрстанные отчёты v3
по-прежнему несут те числа, которые оно производит. Это сделано намеренно: те
отчёты — свидетельство о том, что и когда было сдано. Цитировать впредь следует
исправленные здесь цифры."""),
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
        if line.startswith(":::"):
            continue        # Quarto div fence: markup, never prose
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
