"""Build the Russian twin of analysis/v3/eda-v3-basecheck.qmd.

Run from the repo root:  pixi run python scripts/build_ru_basecheck.py
Then normalise the numbers:  pixi run python scripts/ru_numfmt.py

Only prose, captions and the front matter are translated.  Every {python} cell is
copied byte-for-byte -- the twin needs no code edits at all, because the setup
cell finds the repository root itself -- so the rendered tables and figures stay
in English exactly as in the source document.
"""
import io
import re
import sys

SRC = "analysis/v3/eda-v3-basecheck.qmd"
DST = "analysis/v3/eda-v3-basecheck-ru.qmd"

FRONT_OLD = '''title: "Arkhangelsk Urban Infrastructure — the commercial directory as a third source"
subtitle: "export_base_688669 profiled, and re-matched against the 2026 export and the 2022 benchmark (2026-08-31)"
author: "Northern State Medical University — Infrastructure project"
date: today
lang: en
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''
FRONT_NEW = '''title: "Городская инфраструктура Архангельска — коммерческий справочник как третий источник"
subtitle: "Профиль export_base_688669 и повторное сопоставление с выгрузкой 2026 года и эталоном 2022 года (2026-08-31)"
author: "СГМУ — проект по городской инфраструктуре"
date: today
lang: ru
format:
  pdf:
    pdf-engine: xelatex
    include-in-header: ../_fonts.tex'''

CAPTIONS = {
    "The commercial directory at a glance.":
        "Коммерческий справочник в цифрах.",
    "Top 12 rubrics. The file is shaped like a business directory, not like an infrastructure register.":
        "12 самых частых рубрик. По составу это бизнес-справочник, а не реестр инфраструктуры.",
    "Almost half the directory's addresses carry a prefix the shipped normaliser cannot remove.":
        "Почти половина адресов справочника несёт префикс, который штатный нормализатор удалить не может.",
    "The same address under the shipped normaliser and the corrected one.":
        "Один и тот же адрес под штатным и исправленным нормализатором.",
    "Corroboration of the 2026 export's three-okrug records, by matching method. Method 1 is what the earlier report used.":
        "Подтверждение записей выгрузки 2026 года по трём округам в зависимости от метода сопоставления. Метод 1 — тот, что применялся в предыдущем отчёте.",
    "The same data under each method. The first bar is the published 3.6% figure.":
        "Одни и те же данные под каждым из методов. Первый столбец — опубликованные 3,6 %.",
    "Sample pairs scoring in the 0.85-0.90 band. These are not the same object.":
        "Примеры пар с оценкой в полосе 0,85–0,90. Это не один и тот же объект.",
    "Sample pairs scoring at or above 0.90.":
        "Примеры пар с оценкой 0,90 и выше.",
    "Corroboration by the commercial directory, at each threshold. 'Any within radius' shows why proximity alone proves nothing.":
        "Подтверждение коммерческим справочником при каждом пороге. Столбец «любая запись в радиусе» показывает, почему одна лишь близость ничего не доказывает.",
    "Corroboration by 2022-taxonomy class, whole city, at similarity >= 0.90.":
        "Подтверждение по классам таксономии 2022, весь город, при сходстве >= 0,90.",
    "Corroboration by okrug, whole city, at similarity >= 0.90.":
        "Подтверждение по округам, весь город, при сходстве >= 0,90.",
    "The reverse direction: how much of the directory the 2026 export accounts for.":
        "Обратное направление: какую часть справочника покрывает выгрузка 2026 года.",
    "Fields the directory carries that no other source in this project has.":
        "Поля справочника, которых нет ни в одном другом источнике проекта.",
}

BLOCKS = [
(
"""# Why this report exists

`reports/v3/eda-v3-validation.pdf` reports that the commercial directory
corroborates **3.6 %** of the 2026 export's three-okrug records. That figure is
an artefact of how the join was done, not a property of the data. Re-matched
properly, the directory corroborates
**`{python} f"{rate_three:.1f}"` %** of the same records — roughly nine times as
many.

This report profiles `export_base_688669_zal6mp.xlsx` on its own terms, shows
where the original join failed, and gives the corrected figures. It does not
modify the earlier reports; the 3.6 % figure still stands in
`reports/v3/eda-v3-validation.pdf` and should be read as superseded by this document.""",
"""# Зачем нужен этот отчёт

В отчёте `reports/v3/eda-v3-validation.pdf` указано, что коммерческий справочник
подтверждает **3,6 %** записей выгрузки 2026 года по трём округам. Эта цифра —
артефакт способа сопоставления, а не свойство данных. При корректном
сопоставлении справочник подтверждает
**`{python} f"{rate_three:.1f}"` %** тех же записей — примерно в девять раз
больше.

Настоящий отчёт описывает `export_base_688669_zal6mp.xlsx` сам по себе,
показывает, где именно исходное сопоставление дало сбой, и приводит
исправленные цифры. Существующие отчёты он не меняет: значение 3,6 % остаётся в
`reports/v3/eda-v3-validation.pdf`, и его следует считать замещённым настоящим
документом."""),
(
"""::: {.callout-warning}
## Do not cite the 3.6 % figure

Three compounding defects each suppressed matches independently — an address
prefix that never normalised away, exact string equality on names, and blocking
on the address alone. Sections @sec-defects and @sec-ladder quantify each.
:::""",
"""::: {.callout-warning}
## Не цитируйте значение 3,6 %

Три накладывающихся дефекта подавляли совпадения независимо друг от друга:
адресный префикс, который не удалялся при нормализации, точное посимвольное
равенство названий и блокировка только по адресу. Разделы @sec-defects и
@sec-ladder оценивают каждый из них.
:::"""),
(
"""# What the file is {#sec-what}""",
"""# Что представляет собой файл {#sec-what}"""),
(
"""The two files describe overlapping but different universes. The directory leads
with medical services, car service and construction; the 2026 export leads with
shops. A perfect match rate was never on the cards — but the gap is nothing like
as wide as 3.6 % implied.""",
"""Два файла описывают пересекающиеся, но разные совокупности. В справочнике
лидируют медицинские услуги, автосервис и строительство; в выгрузке 2026 года —
магазины. Полного совпадения ожидать и не приходилось, но разрыв далеко не
такой, каким его представляли 3,6 %."""),
(
"""# The three defects {#sec-defects}

## Defect 1 — the administrative address prefix""",
"""# Три дефекта {#sec-defects}

## Дефект 1 — административный префикс в адресе"""),
(
"""`v3_common.norm_address` strips the city with `\\bархангельск\\b`. The word
boundary means it never matches **Архангельская** in
"Архангельская область, Архангельск городской округ, …", so the whole
administrative prefix survives normalisation:""",
"""Функция `v3_common.norm_address` вырезает город регуляркой `\\bархангельск\\b`.
Из-за границы слова она никогда не совпадает с **Архангельская** в строке
«Архангельская область, Архангельск городской округ, …», поэтому весь
административный префикс переживает нормализацию:"""),
(
"""## Defect 2 — exact string equality on names

The directory habitually appends a trade descriptor to the business name. Exact
equality rejects every one of these pairs; they are plainly the same object.""",
"""## Дефект 2 — точное посимвольное равенство названий

Справочник систематически дописывает к названию род деятельности. Точное
равенство отвергает каждую из этих пар, хотя это очевидно один и тот же
объект."""),
(
"""## Defect 3 — blocking on the address alone

Even corrected, an address block only finds objects both sources spell the same
way. Blocking on distance instead — the directory does carry coordinates —
recovers the rest.""",
"""## Дефект 3 — блокировка только по адресу

Даже в исправленном виде блокировка по адресу находит лишь те объекты, которые
оба источника записали одинаково. Блокировка по расстоянию — координаты в
справочнике есть — возвращает остальные."""),
(
"""# The same question, asked six ways {#sec-ladder}""",
"""# Один вопрос, заданный шестью способами {#sec-ladder}"""),
(
"""# Where the threshold belongs {#sec-threshold}

Method 6 (similarity ≥ `{python} f"{WEAK:.2f}"`) is **not** defensible. In that
band the score is carried by a shared trade descriptor rather than by the
business name, and the pairs are different objects:""",
"""# Где должен стоять порог {#sec-threshold}

Метод 6 (сходство ≥ `{python} f"{WEAK:.2f}"`) **несостоятелен**. В этой полосе
оценку вытягивает общий род деятельности в названии, а не само название, и пары
оказываются разными объектами:"""),
(
"""At ≥ `{python} f"{STRONG:.2f}"` the pairs hold up:""",
"""При ≥ `{python} f"{STRONG:.2f}"` пары выдерживают проверку:"""),
(
"""**`{python} f"{STRONG:.2f}"` is the working threshold** for everything below.
The exact-name rate (method 4) is the conservative floor.""",
"""**`{python} f"{STRONG:.2f}"` — рабочий порог** для всего дальнейшего. Доля
точных совпадений по названию (метод 4) служит консервативной нижней
границей."""),
(
"""# Corrected corroboration {#sec-results}""",
"""# Исправленные показатели подтверждения {#sec-results}"""),
(
"""`{python} f"{100 * geo_city['near'].mean():.0f}"` % of export objects have *some*
directory record within `{python} f"{R:.0f}"` m. That number measures urban
density, not agreement — it is the same trap the contractor's 94.3 % fell into,
and it is why the name test does the work here.""",
"""У `{python} f"{100 * geo_city['near'].mean():.0f}"` % объектов выгрузки в
радиусе `{python} f"{R:.0f}"` м есть *какая-нибудь* запись справочника. Это
измеряет плотность городской застройки, а не согласие источников — ровно та
ловушка, в которую попали 94,3 % подрядчика. Именно поэтому здесь всю работу
делает проверка названия."""),
(
"""Alcohol shops stand out at the bottom: the directory carries almost none of them.
That matches the earlier finding that the risk classes are the least corroborated
part of the export, whichever source is asked.""",
"""В самом низу выделяются алкогольные магазины: справочник почти не содержит их.
Это согласуется с прежним выводом о том, что классы риска — наименее
подтверждённая часть выгрузки, каким источником ни проверяй."""),
(
"""Four fifths of the directory has no counterpart in the export. Most of it is
office-economy activity — legal, financial, construction, transport firms — that
the infrastructure export never set out to collect.""",
"""Четыре пятых справочника не имеют соответствия в выгрузке. В основном это
офисная экономика — юридические, финансовые, строительные и транспортные
компании, — которую инфраструктурная выгрузка и не собиралась собирать."""),
(
"""# What the file adds, and what it cannot do {#sec-value}""",
"""# Что файл добавляет и чего он не может {#sec-value}"""),
(
"""The three commercially interesting fields are **categorical, not numeric**.
`Рейтинг компании в Интернете` takes four values, the most common being
"Недостаточно данных"; `Примерное число отзывов` likewise, most commonly
"меньше 10". They cannot support quantitative analysis.""",
"""Три коммерчески интересных поля **категориальные, а не числовые**. Поле
`Рейтинг компании в Интернете` принимает четыре значения, самое частое —
«Недостаточно данных»; `Примерное число отзывов` устроено так же, чаще всего это
«меньше 10». Количественный анализ на них построить нельзя."""),
(
"""# Caveats {#sec-caveats}

- **The corrected rate is still a floor, not a ceiling.** Objects the directory
  lists under a franchise name while the export uses a local one stay unmatched,
  and no name test recovers them.
- **Chain names inflate the count at the margin.** "Антей, аптека" occurs 14
  times among the matches; with a `{python} f"{R:.0f}"` m radius in dense retail
  streets, some of those pairings are coincidental. Read the ≥ 0.90 figure as
  accurate to a few points, not to a decimal.
- **The radius is forced.** The directory's coordinates are rounded to three
  decimals — about ±55 m here — so a 50 m radius, as used against the 2022
  benchmark, is not available. `{python} f"{R:.0f}"` m is the smallest radius the
  rounding permits.
- **No okrug field**, so okrug for directory records was never used; okrug
  breakdowns in @sec-results come from the export side of each matched pair.
- **This is corroboration, not verification.** The directory is a commercial
  aggregator, not a survey. A match means two compilations agree an object
  exists at a place, which is weaker than independent field observation.
- **The earlier report's 3.6 % figure remains in print.** No existing report was
  modified. If `eda-v3-validation.qmd` is ever re-rendered, its
  `tbl-thirdsource` cell should be replaced with the method used here — it lives
  in `src/arkhinfra/basecheck.py`, deliberately separate from `src/arkhinfra/v3_common.py`
  so that the older reports keep producing exactly what they produced before.""",
"""# Оговорки {#sec-caveats}

- **Исправленная доля — по-прежнему нижняя, а не верхняя граница.** Объекты,
  которые справочник ведёт под франшизным названием, а выгрузка — под местным,
  остаются несопоставленными, и никакая проверка названий их не вернёт.
- **Сетевые названия немного завышают счёт.** «Антей, аптека» встречается среди
  совпадений 14 раз; при радиусе `{python} f"{R:.0f}"` м на плотных торговых
  улицах часть таких пар случайна. Значение при ≥ 0,90 следует читать с
  точностью до нескольких процентных пунктов, а не до десятой доли.
- **Радиус навязан данными.** Координаты справочника округлены до трёх знаков —
  здесь это около ±55 м, — поэтому радиус 50 м, применённый к эталону 2022 года,
  недоступен. `{python} f"{R:.0f}"` м — наименьший радиус, который допускает это
  округление.
- **Поля округа нет**, поэтому округ для записей справочника не использовался;
  разрезы по округам в @sec-results берутся со стороны выгрузки в каждой
  сопоставленной паре.
- **Это подтверждение, а не верификация.** Справочник — коммерческий агрегатор,
  а не полевое обследование. Совпадение означает, что две компиляции согласны в
  существовании объекта в данном месте, а это слабее независимого наблюдения на
  местности.
- **Значение 3,6 % из предыдущего отчёта остаётся напечатанным.** Ни один
  существующий отчёт не изменялся. Если `eda-v3-validation.qmd` когда-нибудь
  будут пересобирать, ячейку `tbl-thirdsource` следует заменить на метод из
  настоящего отчёта — он живёт в `src/arkhinfra/basecheck.py`, намеренно отделённом от
  `src/arkhinfra/v3_common.py`, чтобы прежние отчёты продолжали выдавать ровно то, что
  выдавали раньше."""),
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
