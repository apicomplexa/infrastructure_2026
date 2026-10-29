"""The deliverable spreadsheets: what was matched, and what was not.

`v4_licences.csv` is the working file -- 58 columns in source order, English
headers, one row per v4 record whether or not a licence was found.  It answers
questions; it is not something to hand to a reader who has to *check* the join
by eye.  This module builds what is:

* **one file per risk layer, rows holding a licence of their own only**
  (`v4_egais.STATUS_OWN`), whose columns put the two sides of every comparison
  next to each other -- the object's name beside the licence holder's, its
  address beside the outlet address, its coordinate beside the registry's --
  each pair followed by the term it scored, and the three terms followed by the
  total.  A reader checking a row never has to scroll to see what was compared
  with what;
* **one file for the alcohol rows with no licence of their own**
  (`v4_egais.STATUS_NO_OWN`), which says *why* -- the outlet went to another
  object, only another chain's or another trade's licences stand there, or
  there is no licence at all -- and carries the manual Yandex Maps check
  (`v4_yandex`) and the *best candidate the join refused*.  A list of such rows
  is only reviewable if it says how near each one came;
* **the learned fascia -> holder pairs** (`v4_brand_aliases.csv`) as a table a
  person can confirm or reject, the pairs in use first.

Nothing here re-decides anything.  The join is re-run through `v4_egais.join()`
with its published defaults and checked row for row against
`data/processed/v4_licences/v4_licences.csv` before a file is written, so these
spreadsheets carry the same numbers as the summary and the report or they are
not written at all.  The re-run exists only to reach fields the working file
does not keep: the registry's own coordinate, and the losing candidate.

The near-miss selection deliberately does **not** prefer licences in force, as
the accepted one does, and applies none of the join's three choice rules (one
outlet per object, trade compatibility, brand conflict).  Its question is "how
close did this row come to matching", and the honest answer is the plain
best-scoring candidate, not the best one this object was allowed to hold.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import v4_egais as mg
from . import v4_yandex as yx
from .paths import PROC_DELIVER, PROC_LICENCES, ensure_licmatch_path

ensure_licmatch_path()

import licmatch as lm  # noqa: E402

MATCHED_CSV = PROC_LICENCES / "v4_licences.csv"
YANDEX_CSV = yx.OUT_CSV

OUT_ALCOHOL = PROC_DELIVER / "v4_licences_alcohol_matched.xlsx"
OUT_TOBACCO = PROC_DELIVER / "v4_licences_tobacco_matched.xlsx"
OUT_NO_LICENCE = PROC_DELIVER / "v4_alcohol_no_licence.xlsx"
BRANDS_CSV = PROC_LICENCES / "v4_brand_aliases.csv"
OUT_BRANDS = PROC_DELIVER / "v4_brand_aliases.xlsx"

# --------------------------------------------------------------------------
# Russian labels for the coded columns
# --------------------------------------------------------------------------
RISK_RU = {"Alcohol": "Алкоголь", "Tobacco": "Табак"}
EVIDENCE_RU = {"Direct": "прямой", "Inferred": "предполагаемый"}
TRADE_RU = {"off-trade": "навынос", "on-trade": "общепит"}
METHOD_RU = {"geo": "по координатам", "address": "только по адресу", "": ""}
LEVEL_RU = {"house": "до дома", "street": "до улицы", "": ""}
TIER_RU = {"direct": "прямое", "probable": "вероятное", "weak": "слабое", "": ""}
STATUS_RU = {"Active": "действующая", "Expired": "истёкшая",
             "Terminated": "прекращённая", "Reissued": "переоформленная",
             "Annulled": "аннулированная", "": ""}
ACTIVITY_RU = {"Retail (off-trade)": "розница без общепита",
               "Retail + on-trade": "розница с общепитом",
               "Wholesale & storage": "опт и хранение",
               "Production": "производство",
               "Ethanol transport": "перевозка спирта", "": ""}
# Why an object holds no licence of its own -- `licence_status` in STATUS_NO_OWN.
OWN_STATUS_RU = {
    mg.STATUS_TAKEN: "точка закреплена за другим объектом",
    mg.STATUS_OTHER_CHAIN: "по адресу только лицензии другой сети",
    mg.STATUS_OTHER_TRADE: "по адресу только лицензии другого вида деятельности",
    mg.STATUS_NONE: "лицензии по адресу нет",
}
# Where the name term of the chosen pair came from -- `licence_name_basis`.
NAME_BASIS_RU = {
    mg.NAME_MANUAL: "справочник сетей",
    mg.NAME_LEARNED: "выученная пара",
    mg.NAME_FUZZY: "сравнение строк",
    mg.NAME_GENERIC: "родовая вывеска, не оценивалось",
    "": "",
}

# Why the best-scoring candidate was refused.  Both floors are named, because a
# row that fails only the address floor is a different review task from one
# whose nearest candidate is 90 m away with an unrelated name.
REASON_NO_CANDIDATE = "кандидатов нет"
REASON_BOTH = f"не пройдены оба порога (балл < {mg.ACCEPT}, адрес < {mg.ADDR_MIN})"
REASON_SCORE = f"итоговый балл < {mg.ACCEPT}"
REASON_ADDR = f"адресный балл < {mg.ADDR_MIN}"
REASON_NONE = "пороги пройдены"
# For the three statuses in which a licence *did* clear both floors, the floors
# are not why the object has none; the choice rules are.  Said first, so the
# column cannot be read as "failed a floor".
REASON_STATUS = {
    mg.STATUS_TAKEN: "пороги не причина: лицензия по адресу прошла их, но точка "
                     "закреплена за другим объектом (см. «Кому отдана точка»)",
    mg.STATUS_OTHER_CHAIN: "пороги не причина: лицензии по адресу прошли их, но все "
                           "принадлежат известному держателю другой сети",
    mg.STATUS_OTHER_TRADE: "пороги не причина: лицензии по адресу прошли их, но "
                           "их вид деятельности не разрешает торговлю этого объекта",
}

# --------------------------------------------------------------------------
# the column plan
# --------------------------------------------------------------------------
# Each block is (heading, [(Russian column label, source column)]).  The
# heading is what the legend sheet and the header banding are built from, so
# the plan is stated once and the spreadsheet follows it.
BLOCK_MATCH = "Сопоставление: объект ↔ лицензия"
BLOCK_LICENCE = "Лицензия"
BLOCK_OBJECT = "Объект: остальные поля выгрузки"
BLOCK_YANDEX = "Ручная проверка по Яндекс Картам"
BLOCK_NEAR = "Лучшая отклонённая лицензия"
BLOCK_WHY = "Почему нет своей лицензии"


def matched_plan() -> list[tuple[str, list[tuple[str, str]]]]:
    """Columns of a matched-rows file, in reading order."""
    return [
        (BLOCK_MATCH, [
            ("Округ", "district_orig"),
            ("Объект: название", "name_orig"),
            ("Лицензия: держатель", "licence_org_name"),
            ("Балл названия", "licence_name_score"),
            ("Основа балла названия", "_name_basis_ru"),
            ("Объект: адрес", "adress_orig"),
            ("Лицензия: адрес точки", "licence_outlet_address"),
            ("Балл адреса", "licence_addr_score"),
            ("Точность адреса", "_level_ru"),
            ("Объект: широта", "latitude"),
            ("Объект: долгота", "longitude"),
            ("Лицензия: широта", "_lic_lat"),
            ("Лицензия: долгота", "_lic_lon"),
            ("Расстояние, м", "licence_distance_m"),
            ("Балл расстояния", "_dist_score"),
            ("ИТОГОВЫЙ БАЛЛ", "licence_score"),
            ("Маршрут сопоставления", "_method_ru"),
            ("Степень доказательности", "_tier_ru"),
        ]),
        (BLOCK_LICENCE, [
            ("Номер лицензии", "licence_no"),
            ("Предыдущий номер", "licence_prev_no"),
            ("Статус лицензии", "_lic_status_ru"),
            ("Статус в реестре", "licence_status_registry"),
            ("Причина статуса", "licence_status_reason"),
            ("Выдана", "licence_date_issued"),
            ("Действует до", "licence_date_expires"),
            ("Статус изменён", "licence_status_changed"),
            ("Вид деятельности", "licence_activity"),
            ("Класс деятельности", "_activity_ru"),
            # `licence_products` is not here on purpose: the registry publishes
            # the element and leaves it empty in all 2,100 Arkhangelsk rows, and
            # an all-blank column reads as data lost in transit.  Said instead
            # in the legend, where it is a fact about the source.
            ("ИНН держателя", "licence_org_inn"),
            ("Орган, выдавший лицензию", "licence_issuing_body"),
            ("Лицензий по адресу", "licence_n_matched"),
            ("Действующих по адресу", "licence_n_active"),
            ("Действующих розничных", "licence_n_active_retail"),
            ("Все номера по адресу", "licence_all_nos"),
            ("Действующие номера по адресу", "licence_active_nos"),
        ]),
        (BLOCK_OBJECT, [
            ("Класс объекта", "type_orig"),
            ("Категория выгрузки", "category_orig"),
            ("Признак", "_evidence_ru"),
            ("Тип торговли", "_trade_ru"),
            ("Класс 2022", "category_2022"),
            ("Источники", "providers"),
            ("Статус проверки подрядчика", "verification_status"),
            ("Телефон", "phone_orig"),
            ("Сайт", "website_orig"),
            ("Часы работы", "opening_hours_orig"),
            ("Комментарий подрядчика", "verification_comment"),
            ("Идентификаторы источников", "matched_source_ids"),
            ("Ключ объекта", "site_key"),
        ]),
    ]


def no_licence_plan() -> list[tuple[str, list[tuple[str, str]]]]:
    """Columns of the no-licence file, in reading order."""
    return [
        ("Объект", [
            ("Округ", "district_orig"),
            ("Название", "name_orig"),
            ("Адрес", "adress_orig"),
            ("Класс объекта", "type_orig"),
            ("Признак", "_evidence_ru"),
            ("Тип торговли", "_trade_ru"),
            ("Широта", "latitude"),
            ("Долгота", "longitude"),
            ("Источники", "providers"),
        ]),
        (BLOCK_WHY, [
            ("Причина", "_own_status_ru"),
            ("Кому отдана точка", "licence_claimed_by"),
            ("Лицензий по адресу", "licence_n_matched"),
            ("Действующих розничных", "licence_n_active_retail"),
            ("Все номера по адресу", "licence_all_nos"),
        ]),
        (BLOCK_YANDEX, [
            ("Я.Карты: метка", "yandex_status_ru"),
            ("Я.Карты: найденная организация", "yandex_name"),
            ("Я.Карты: её адрес", "yandex_address"),
            ("Я.Карты: расстояние, м", "yandex_distance_m"),
            ("Я.Карты: сходство названий", "yandex_name_sim"),
            ("Я.Карты: ближайшая организация", "yandex_nearby"),
            ("Я.Карты: дата проверки", "checked"),
            ("ССЫЛКА НА ЗАПРОС Я.КАРТ", "search_url"),
            ("Я.Карты: карточка организации", "yandex_url"),
        ]),
        (BLOCK_NEAR, [
            ("Почему не принята", "_reject_reason"),
            ("Номер лицензии", "near_licence_no"),
            ("Держатель", "near_org_name"),
            ("Адрес точки", "near_outlet_address"),
            ("Статус", "_near_status_ru"),
            ("Класс деятельности", "_near_activity_ru"),
            ("Балл названия", "near_name_score"),
            ("Основа балла названия", "_near_name_basis_ru"),
            ("Балл адреса", "near_addr_score"),
            ("Расстояние, м", "near_distance_m"),
            ("Балл расстояния", "_near_dist_score"),
            ("ИТОГОВЫЙ БАЛЛ", "near_score"),
            ("Маршрут сопоставления", "_near_method_ru"),
        ]),
    ]


BLOCK_PAIR = "Пара «вывеска → держатель»"
BLOCK_EVIDENCE = "Доказательства из данных"
BLOCK_DECISION = "Решение"


def brands_plan() -> list[tuple[str, list[tuple[str, str]]]]:
    """Columns of the learned-pairs file, in reading order."""
    return [
        (BLOCK_PAIR, [
            ("Группа", "_group_ru"),
            ("Вывеска (ключ)", "fascia"),
            ("Держатель", "holder_name"),
            ("ИНН держателя", "holder"),
        ]),
        (BLOCK_EVIDENCE, [
            ("Адресов вывески", "fascia_sites"),
            ("Адресов, где держатель рядом", "sites_present"),
            ("Адресов, где точка отдана вывеске", "sites_assigned"),
            ("Доля (share)", "share"),
            ("Покрытие (cover)", "cover"),
            ("Базовая частота (base_rate)", "base_rate"),
            ("Подъём (lift)", "lift"),
            ("Франшиза (franchise)", "_franchise_ru"),
        ]),
        (BLOCK_DECISION, [
            ("Принята порогами (accepted)", "_accepted_ru"),
            ("Какие пороги не пройдены", "_fails_ru"),
            ("Принятых держателей у вывески", "holders_for_fascia"),
            ("Решение эксперта (review)", "review"),
            ("Основание решения", "review_reason"),
            ("Используется в сопоставлении", "_used_ru"),
        ]),
    ]


# --------------------------------------------------------------------------
# the join, re-run for the fields the working file does not keep
# --------------------------------------------------------------------------
def distance_score(d) -> pd.Series:
    """The distance term as the formula states it: 1 - d / max_m, floored at 0.

    Empty on the address route, where there is no usable coordinate on the
    registry side and the term is dropped, the other two weights renormalised.
    """
    d = pd.to_numeric(pd.Series(d).reset_index(drop=True), errors="coerce")
    return (1.0 - d / mg.MAX_M).clip(lower=0.0).round(3)


def rejoin(v4: pd.DataFrame, eg: pd.DataFrame) -> dict:
    """Re-run the join at its published settings, and again with no floors.

    Returns the published `Join` itself (`"join"`, for `mg.enrich(result=...)`),
    the accepted selection's extra columns and the near-miss one's.  The
    accepted selection is the join's own `sel` -- exclusivity, trade
    compatibility and brand conflict included -- so the registry coordinate is
    that of the licence the object was actually given.  The near-miss one is
    the whole of the no-licence file's licence half.
    """
    j = mg.join(v4, eg)
    # No floors, no preference, no choice rules: the question is which
    # candidate came closest, not which one this object was allowed to hold.
    # Scored on the join's own matrix, so learned pairs count in the name term.
    loose = lm.select(j.scores, mg.params(accept=0.0, addr_min=0.0),
                      keys=eg["licence_no"], groups={mg.GROUP_MATCHED: None})

    lat = eg["latitude"].to_numpy(dtype=object)
    lon = eg["longitude"].to_numpy(dtype=object)
    accepted = pd.DataFrame({
        "_lic_lat": j.sel.take(lat, empty=""),
        "_lic_lon": j.sel.take(lon, empty=""),
    })

    basis = mg.name_basis(loose, mg.prepare_v4(v4)["name_key"], eg)
    near = pd.DataFrame({
        "near_hit": loose.hit,
        "near_licence_no": loose.take(eg["licence_no"].to_numpy(dtype=object)),
        "near_org_name": loose.take(eg["org_name"].to_numpy(dtype=object)),
        "near_outlet_address": loose.take(eg["outlet_address"].to_numpy(dtype=object)),
        "near_status_en": loose.take(eg["status_en"].to_numpy(dtype=object)),
        "near_activity_class": loose.take(eg["activity_class"].to_numpy(dtype=object)),
        "near_score": np.round(loose.score, 3),
        "near_addr_score": np.round(loose.addr, 3),
        # A generic fascia's name was never scored: blank, not 0.
        "near_name_score": np.where(basis == mg.NAME_GENERIC, np.nan,
                                    np.round(loose.name, 3)),
        "near_name_basis": basis,
        "near_distance_m": np.round(loose.distance, 1),
        "near_method": loose.method,
    })
    return {"join": j, "accepted": accepted, "near": near}


def floor_reason(near: pd.DataFrame) -> pd.Series:
    """Which floor the best candidate failed."""
    score = pd.to_numeric(near["near_score"], errors="coerce")
    addr = pd.to_numeric(near["near_addr_score"], errors="coerce")
    low_score = score < mg.ACCEPT
    low_addr = addr < mg.ADDR_MIN
    return pd.Series(
        np.where(~near["near_hit"].to_numpy(bool), REASON_NO_CANDIDATE,
                 np.where(low_score & low_addr, REASON_BOTH,
                          np.where(low_score, REASON_SCORE,
                                   np.where(low_addr, REASON_ADDR, REASON_NONE)))),
        index=near.index)


def reject_reason(near: pd.DataFrame) -> pd.Series:
    """Why this row holds no licence -- the review's first question.

    For `Not in registry` it is the floor the best candidate failed.  For the
    three statuses in which a licence cleared both floors it is the choice rule
    that kept it from this object; the shown candidate is the plain best-scoring
    one, which need not be the licence that cleared the floors, so where it
    fails a floor itself that is added after the rule.
    """
    floors = floor_reason(near)
    status = (near["licence_status"].fillna("").astype(str) if "licence_status" in near
              else pd.Series(mg.STATUS_NONE, index=near.index))
    rule = status.map(REASON_STATUS)
    extra = np.where(floors.isin([REASON_NONE, REASON_NO_CANDIDATE]), "",
                     "; показанный кандидат сам не проходит порог: " + floors)
    return pd.Series(np.where(rule.notna(), rule.fillna("") + extra, floors),
                     index=near.index)


def derived(d: pd.DataFrame) -> pd.DataFrame:
    """The `_`-prefixed columns the plans refer to: labels and the distance term."""
    out = pd.DataFrame(index=d.index)
    out["_method_ru"] = d["licence_match_method"].fillna("").map(METHOD_RU).fillna("")
    out["_level_ru"] = d["licence_match_level"].fillna("").map(LEVEL_RU).fillna("")
    out["_tier_ru"] = d["licence_evidence"].fillna("").map(TIER_RU).fillna("")
    out["_lic_status_ru"] = d["licence_status_raw"].fillna("").map(STATUS_RU).fillna("")
    out["_activity_ru"] = d["licence_activity_class"].fillna("").map(ACTIVITY_RU).fillna("")
    out["_evidence_ru"] = d["evidence"].fillna("").map(EVIDENCE_RU).fillna("")
    out["_trade_ru"] = d["trade"].fillna("").map(TRADE_RU).fillna("")
    out["_dist_score"] = distance_score(d["licence_distance_m"]).to_numpy()
    out["_name_basis_ru"] = d["licence_name_basis"].fillna("").map(NAME_BASIS_RU).fillna("")
    out["_own_status_ru"] = d["licence_status"].fillna("").map(OWN_STATUS_RU).fillna("")
    return out


def derived_near(d: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=d.index)
    out["_near_name_basis_ru"] = d["near_name_basis"].fillna("").map(NAME_BASIS_RU).fillna("")
    out["_near_status_ru"] = d["near_status_en"].fillna("").map(STATUS_RU).fillna("")
    out["_near_activity_ru"] = d["near_activity_class"].fillna("").map(ACTIVITY_RU).fillna("")
    out["_near_method_ru"] = pd.Series(d["near_method"]).fillna("").map(METHOD_RU).fillna("")
    out["_near_dist_score"] = distance_score(d["near_distance_m"]).to_numpy()
    out["_reject_reason"] = reject_reason(d).to_numpy()
    return out


YES_NO = {True: "да", False: "нет"}
GROUP_USED = "используется"
GROUP_NEAR = "близко к порогу"
GROUP_OTHER = "не принята"
GROUP_ORDER = [GROUP_USED, GROUP_NEAR, GROUP_OTHER]


def _flag(s: pd.Series) -> pd.Series:
    """A True/False column as read back from CSV (bool or "True"/"False")."""
    return s.astype(str).str.strip().str.lower().isin(["true", "1"])


def brand_frame(t: pd.DataFrame, bp: lm.BrandParams = lm.BRAND_DEFAULTS) -> pd.DataFrame:
    """The learned-pairs table with its derived labels, in reading order.

    Pairs in use first, then the near misses -- pairs that failed exactly one
    of the three thresholds -- then the rest; within a group, the most
    addresses first.
    """
    t = t.copy()
    for c in ("review", "review_reason"):
        t[c] = t[c].fillna("").astype(str) if c in t else ""
    used, accepted, franchise = _flag(t["used"]), _flag(t["accepted"]), _flag(t["franchise"])
    few = t["sites_assigned"] < bp.min_sites
    low_share = ~((t["share"] >= bp.min_share)
                  | (franchise & (t["share"] >= bp.franchise_min_share)))
    low_lift = t["lift"] < bp.min_lift
    share_bar = np.where(franchise, bp.franchise_min_share, bp.min_share)
    fails = []
    for f, s, li, bar, fr, rv in zip(few, low_share, low_lift, share_bar, franchise,
                                     t["review"]):
        parts = []
        if f:
            parts.append(f"адресов < {bp.min_sites}")
        if s:
            parts.append(f"доля < {bar:g}" + (" (франшиза)" if fr else ""))
        if li:
            parts.append(f"подъём < {bp.min_lift:g}")
        if rv == mg.REVIEW_REJECT:
            parts.append("отклонена вручную")
        fails.append("; ".join(parts))
    n_fail = few.astype(int) + low_share.astype(int) + low_lift.astype(int)
    # A near miss failed one threshold -- and, if that one is the vote count,
    # missed it by a single address.  A pair seen once is not near anything:
    # every fascia with one licensed address yields one at share 1.0.
    near = (n_fail == 1) & (~few | (t["sites_assigned"] >= bp.min_sites - 1))
    t["_group_ru"] = np.where(used, GROUP_USED, np.where(near, GROUP_NEAR, GROUP_OTHER))
    t["_fails_ru"] = fails
    t["_franchise_ru"] = franchise.map(YES_NO)
    t["_accepted_ru"] = accepted.map(YES_NO)
    t["_used_ru"] = used.map(YES_NO)
    t["holder"] = t["holder"].astype(str).str.replace(r"\.0$", "", regex=True)
    t["_g"] = t["_group_ru"].map({g: i for i, g in enumerate(GROUP_ORDER)})
    t = t.sort_values(["_g", "sites_assigned", "share", "fascia"],
                      ascending=[True, False, False, True])
    return t.drop(columns="_g").reset_index(drop=True)


def assemble(d: pd.DataFrame, plan) -> pd.DataFrame:
    """One frame in the plan's column order, with the plan's Russian headers.

    The score terms are rounded here rather than trusted from upstream: the
    scorer works in float32, so a term already rounded to three places arrives
    as 0.2349999994039536, which a cell format hides and a CSV export does not.
    """
    cols, seen = {}, set()
    for _, fields in plan:
        for label, src in fields:
            if label in seen:
                raise ValueError(f"duplicate column label: {label}")
            seen.add(label)
            cols[label] = d[src] if src in d.columns else ""
    out = pd.DataFrame(cols, index=d.index)
    for group, places in ((SCORE_COLS, 3), (DIST_COLS, 1), (SIM_COLS, 1)):
        for label in group:
            if label in out.columns:
                out[label] = pd.to_numeric(out[label], errors="coerce").round(places)
    return out


def block_spans(plan) -> list[tuple[str, int, int]]:
    """(heading, first column, last column), 1-based, for the header banding."""
    out, start = [], 1
    for heading, fields in plan:
        out.append((heading, start, start + len(fields) - 1))
        start += len(fields)
    return out


# --------------------------------------------------------------------------
# the spreadsheet
# --------------------------------------------------------------------------
# One fill per block, so a reader sees where the export stops and the registry
# begins without reading a single header.
BLOCK_FILL = {
    BLOCK_MATCH: "FFF2CC",
    BLOCK_LICENCE: "DDEBF7",
    BLOCK_OBJECT: "E2EFDA",
    BLOCK_YANDEX: "FBE5D6",
    BLOCK_NEAR: "E4DFEC",
    BLOCK_WHY: "FCE4E4",
    "Объект": "E2EFDA",
    BLOCK_PAIR: "FFF2CC",
    BLOCK_EVIDENCE: "DDEBF7",
    BLOCK_DECISION: "E2EFDA",
}
SCORE_COLS = ("Балл названия", "Балл адреса", "Балл расстояния", "ИТОГОВЫЙ БАЛЛ")
DIST_COLS = ("Расстояние, м", "Я.Карты: расстояние, м")
SIM_COLS = ("Я.Карты: сходство названий",)
# Cells that hold a URL carry the URL as their text *and* as a hyperlink: the
# text so it can be copied out of the file, the hyperlink so a reviewer working
# through the list opens the query with one click.
LINK_COLS = ("ССЫЛКА НА ЗАПРОС Я.КАРТ", "Я.Карты: карточка организации", "Сайт")
WIDTH_MIN, WIDTH_MAX = 10, 46


def _legend_rows(plan, title: str, notes: list[str],
                 column_notes: dict | None = None) -> list[list[str]]:
    """The "Как читать" sheet: every column named, then what may not be claimed."""
    column_notes = COLUMN_NOTE if column_notes is None else column_notes
    rows = [[title], [], ["Блок", "Столбец", "Что в нём"]]
    for heading, fields in plan:
        for label, src in fields:
            rows.append([heading, label, column_notes.get(label, "")])
    rows += [[], ["Как читать этот файл"]]
    rows += [[n] for n in notes]
    return rows


def write_sheet(path, frame: pd.DataFrame, plan, title: str,
                notes: list[str], column_notes: dict | None = None,
                formats: dict | None = None) -> None:
    """One workbook: the table under a banded two-row header, plus the legend.

    The block heading is a merged row above the column labels rather than a
    prefix on every label, because a prefix repeated forty-eight times is read
    once and then ignored, and it doubles the width of every column.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Данные"

    thin = Side(style="thin", color="BFBFBF")
    for heading, first, last in block_spans(plan):
        fill = PatternFill("solid", fgColor=BLOCK_FILL.get(heading, "F2F2F2"))
        cell = ws.cell(row=1, column=first, value=heading)
        cell.font = Font(bold=True, size=11)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in range(first, last + 1):
            ws.cell(row=1, column=col).fill = fill
            ws.cell(row=2, column=col).fill = fill
        if last > first:
            ws.merge_cells(start_row=1, start_column=first,
                           end_row=1, end_column=last)

    for j, label in enumerate(frame.columns, start=1):
        cell = ws.cell(row=2, column=j, value=label)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="bottom")
        cell.border = Border(bottom=thin)

    link_font = Font(color="0563C1", underline="single")
    links = [j for j, label in enumerate(frame.columns, start=1)
             if label in LINK_COLS]
    for i, (_, row) in enumerate(frame.iterrows(), start=3):
        for j, label in enumerate(frame.columns, start=1):
            cell = ws.cell(row=i, column=j, value=_cell(row[label]))
            if j in links and isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.font = link_font

    n = len(frame) + 2
    for j, label in enumerate(frame.columns, start=1):
        letter = get_column_letter(j)
        width = max(len(str(label)) * 0.9,
                    *(len(str(v)) for v in frame[label].head(400).astype(str)))
        ws.column_dimensions[letter].width = min(max(width + 2, WIDTH_MIN), WIDTH_MAX)
        fmt = ((formats or {}).get(label)
               or ("0.000" if label in SCORE_COLS
                   else "0.0" if label in DIST_COLS + SIM_COLS else None))
        if fmt:
            for i in range(3, n + 1):
                ws.cell(row=i, column=j).number_format = fmt
    ws.freeze_panes = "C3"
    ws.auto_filter.ref = f"A2:{get_column_letter(len(frame.columns))}{n}"

    leg = wb.create_sheet("Как читать")
    for row in _legend_rows(plan, title, notes, column_notes):
        leg.append(row)
    leg["A1"].font = Font(bold=True, size=13)
    for col, width in (("A", 38), ("B", 34), ("C", 96)):
        leg.column_dimensions[col].width = width
    for row in leg.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _cell(v):
    """Excel takes numbers as numbers and everything else as text."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    return v


# --------------------------------------------------------------------------
# the legend
# --------------------------------------------------------------------------
# Only the columns whose meaning is not their name.  A note here is what keeps
# a reader from adding two numbers that count different things.
_BP = lm.BRAND_DEFAULTS

COLUMN_NOTE = {
    "Объект: название": "Вывеска из выгрузки подрядчика, как её записали 2GIS/OSM.",
    "Лицензия: держатель": (
        "Реестр называет ЛИЦЕНЗИАТА, а выгрузка — МАГАЗИН. «Тандер» и «Магнит» — "
        "одно и то же лицо. Такие пары сведены двумя способами: ручным "
        "справочником сетей и парами «вывеска → ИНН держателя», выученными из "
        "самих данных (таблица — v4_brand_aliases.xlsx). Остальные названия "
        "сравниваются как строки и обычно получают низкий балл."),
    "Балл названия": (
        "0…1, вес в итоговом балле — 0,20. ПУСТО для родовой вывески («Продукты», "
        "«Кафе», «Пиво»): такое название ничего не говорит о держателе, поэтому "
        "член названия НЕ ОЦЕНИВАЛСЯ, а не оценён нулём; его вес передан адресу и "
        "расстоянию: (0,50·адрес + 0,30·расстояние) / 0,80."),
    "Основа балла названия": (
        "Откуда взят балл названия. «справочник сетей» — ручной список "
        "«держатель → сеть» (Тандер → Магнит и т. п.), балл 1; «выученная пара» — "
        "пара «вывеска → ИНН держателя», выученная из данных (v4_brand_aliases.xlsx), "
        "балл 1 — это ГИПОТЕЗА со счётом за ней, а не факт; «сравнение строк» — "
        "названия сравнены как текст; «родовая вывеска, не оценивалось» — см. "
        "«Балл названия»."),
    "Лицензия: адрес точки": "Адрес торговой точки из реестра, не юридический адрес.",
    "Балл адреса": (
        "0…1, вес 0,50. Сравниваются РАЗОБРАННЫЕ топонимы, а не строки: тип улицы, "
        "стеммированное название, дом и корпус — поле за полем."),
    "Точность адреса": (
        "«до дома» — обе стороны называют одно здание; «до улицы» — номер дома "
        "написан только с одной стороны."),
    "Лицензия: широта": "Координата реестра округлена до секунд (~31 м по широте).",
    "Лицензия: долгота": "Координата реестра округлена до секунд (~31 м по широте).",
    "Расстояние, м": "Пусто на маршруте «только по адресу»: у 47 % строк реестра нет координаты.",
    "Балл расстояния": "max(0; 1 − расстояние/100 м), вес 0,30. Пусто на адресном маршруте.",
    "ИТОГОВЫЙ БАЛЛ": (
        "0,50·адрес + 0,20·название + 0,30·расстояние. На маршруте «только по "
        "адресу» член расстояния выбрасывается, а два оставшихся веса "
        "перенормируются: (0,50·адрес + 0,20·название) / 0,70. Для родовой "
        "вывески выбрасывается член названия (см. «Балл названия»)."),
    "Маршрут сопоставления": (
        "«по координатам» — пара нашлась в радиусе 100 м; «только по адресу» — "
        "у лицензии нет координаты, и порог по адресу для неё строже."),
    "Степень доказательности": (
        "«прямое» — реестр лицензирует именно тот товар, которым размечен объект "
        "(только алкоголь). «вероятное» — строка размечена табаком, а за объектом "
        "закреплена ДЕЙСТВУЮЩАЯ РОЗНИЧНАЯ алкогольная лицензия: табачного реестра не "
        "существует, и это косвенный довод, а не подтверждение. «слабое» — за "
        "объектом закреплена только архивная или нерозничная лицензия. "
        "СКЛАДЫВАТЬ ЭТИ СТОЛБЦЫ НЕЛЬЗЯ."),
    "Статус лицензии": (
        "Статус лицензии, закреплённой ИМЕННО ЗА ЭТИМ объектом, — не адреса. "
        "Сколько лицензий стоит по адресу, говорят столбцы «… по адресу»."),
    "Лицензий по адресу": (
        "Считаются РАЗЛИЧНЫЕ номера лицензий, прошедших оба порога, а не строки "
        "реестра: продлённая лицензия лежит в реестре по строке на каждое изменение "
        "статуса. Счётчик описывает АДРЕС: сюда входят и лицензии, которые "
        "достались другим объектам."),
    "Действующих розничных": "Счётчик по АДРЕСУ, не по объекту: сюда входят и лицензии соседей.",
    "Все номера по адресу": "Все лицензии, прошедшие оба порога по этому адресу, — чьи бы они ни были.",
    "Признак": (
        "«прямой» — объект помечен как специализированная точка продажи; "
        "«предполагаемый» — тип объекта лишь СОВМЕСТИМ с продажей, что сам "
        "подрядчик отмечает как требующее отдельной проверки. 82 % поставки — "
        "предполагаемый признак; объединять два тира в один показатель нельзя."),
    "Часы работы": "Два несовместимых формата в одном столбце: JSON 2GIS и строка OSM.",
    "Причина": (
        "Почему у объекта нет СОБСТВЕННОЙ лицензии. «точка закреплена за другим "
        "объектом» — лицензия его вида деятельности по адресу ЕСТЬ, но эта точка "
        "досталась объекту с более сильной заявкой (одна точка — один объект); "
        "«по адресу только лицензии другой сети» — все подходящие лицензии "
        "принадлежат известному держателю другой вывески; «по адресу только "
        "лицензии другого вида деятельности» — например, лицензия магазина там, "
        "где объект — бар, или наоборот, или оптовая; «лицензии по адресу нет» — "
        "ни одна лицензия не прошла оба порога."),
    "Кому отдана точка": (
        "Только для «точка закреплена за другим объектом»: объект выгрузки "
        "(название и адрес), которому досталась точка этого объекта."),
    "Я.Карты: метка": (
        "«есть» — организация с тем же названием стоит по этому адресу; «закрыт» — "
        "карточка помечена «Больше не работает»; «не опознан» — по адресу кто-то "
        "есть, но название объекта родовое целиком («Столовая»), и сопоставлять "
        "нечего; «нет» — ничего похожего; «не пров.» — Яндекс не ответил."),
    "Я.Карты: сходство названий": "0…100 по ключу названия, порог принятия — 72.",
    "Я.Карты: расстояние, м": "Порог принятия — 150 м, для родового названия — 60 м.",
    "Я.Карты: ближайшая организация": "Заполняется для метки «нет»: что стоит по этому адресу вместо объекта.",
    "ССЫЛКА НА ЗАПРОС Я.КАРТ": "Тот самый запрос, по которому поставлена метка. Открывается в браузере.",
    "Почему не принята": (
        "Для «лицензии по адресу нет» — какой порог не прошёл лучший по баллу "
        "кандидат. Порог по адресу существует потому, что в радиусе 100 м "
        "соседний дом отличается только номером, а округлённые координаты реестра "
        "его не различают. Для трёх остальных статусов пороги НЕ причина: лицензия "
        "их прошла, а объекту её не дало одно из правил выбора (одна точка — один "
        "объект, совместимость вида деятельности, конфликт брендов). Показанный "
        "кандидат — просто лучший по баллу и может не совпадать с той лицензией; "
        "если он сам не проходит порог, это дописано после правила."),
    # the learned-pairs file
    "Группа": (
        "«используется» — пара участвует в сопоставлении; «близко к порогу» — не "
        "прошла ровно один из трёх порогов, а если это порог голосов — не добрала "
        "одного адреса; «не принята» — всё остальное, в том числе пары, "
        "увиденные на одном адресе (у каждой вывески с одним адресом такая пара "
        "имеет долю 1,0 и ничего не доказывает)."),
    "Вывеска (ключ)": (
        "Вывеска, приведённая к ключу: без описателя («магазин», «кафе»), в нижнем "
        "регистре, «Красное&Белое» и «Красное & Белое» — один ключ."),
    "ИНН держателя": "Пара называет держателя по ИНН, а не по названию: два ООО «Ритейл» — разные лица.",
    "Адресов вывески": "Различных адресов этой вывески в алкогольном слое, у которых есть хоть один кандидат.",
    "Адресов, где держатель рядом": "Из них — адресов, где лицензия этого держателя прошла пороги (присутствие).",
    "Адресов, где точка отдана вывеске": (
        "Из них — адресов, где точка держателя ДОСТАЛАСЬ этой вывеске при "
        "распределении «одна точка — один объект» (голос). Именно голоса, а не "
        "присутствие, отличают хозяина от соседа."),
    "Доля (share)": (
        f"Голоса / адреса вывески. Порог — {_BP.min_share:g}; для франшизы — "
        f"{_BP.franchise_min_share:g}."),
    "Покрытие (cover)": "Присутствие / адреса вывески: у какой доли адресов вывески этот держатель вообще стоит рядом.",
    "Базовая частота (base_rate)": (
        "Доля ВСЕХ адресов алкогольного слоя, где стоит этот держатель. У крупной "
        "сети она высока: «Агроторг» стоит рядом с чем угодно."),
    "Подъём (lift)": (
        f"cover / base_rate: во сколько раз чаще держатель стоит у этой вывески, "
        f"чем у адреса вообще. Порог — {_BP.min_lift:g}."),
    "Франшиза (franchise)": (
        f"«да» — ни один держатель не взял и {_BP.franchise_top_max:g} адресов "
        "вывески: её держат несколько операторов (так «Петровский»), и каждому "
        "достаточно пониженной доли."),
    "Принята порогами (accepted)": (
        f"Все три порога пройдены: голосов ≥ {_BP.min_sites}, доля ≥ порога, "
        f"подъём ≥ {_BP.min_lift:g}."),
    "Принятых держателей у вывески": "Сколько держателей принято для этой вывески (у франшизы — несколько).",
    "Решение эксперта (review)": (
        "ЗДЕСЬ ЧЕЛОВЕК ПОДТВЕРЖДАЕТ ИЛИ ОТКЛОНЯЕТ ПАРУ. «accept» — принять пару, "
        "которую пороги отклонили; «reject» — отклонить принятую. Решение вносится "
        "не в этот файл, а в словарь BRAND_REVIEW в src/arkhinfra/v4_egais.py "
        "(ключ — (вывеска, ИНН), значение — (решение, основание)), после чего "
        "перезапускаются pixi run match-egais-v4 и pixi run export-licences. "
        "Пусто — пара не просматривалась."),
    "Основание решения": "Почему человек принял или отклонил пару. Обязательно для каждого решения.",
    "Используется в сопоставлении": (
        "Итог: «да», если пара принята порогами и не отклонена вручную, либо "
        "принята вручную."),
    "Какие пороги не пройдены": "Пусто — пройдены все. «отклонена вручную» — решение из BRAND_REVIEW.",
}

NOTES_RULES = [
    "• Три правила выбора, после двух порогов. (1) ОДНА ТОЧКА — ОДИН ОБЪЕКТ: "
    "точка — это ИНН держателя по одному разобранному адресу; в пределах слоя "
    "(алкоголь, табак) она достаётся не более чем одному объекту, сильнейшая "
    "заявка первой, действующая лицензия выше архивной. Проигравший получает "
    "статус «точка закреплена за другим объектом». Слои — отдельные разбиения: "
    "один магазин в обоих файлах может в каждом держать свою лицензию. "
    "(2) СОВМЕСТИМОСТЬ ВИДА ДЕЯТЕЛЬНОСТИ: объекту навынос подходит только "
    "розничная лицензия, общепиту — только лицензия «при оказании услуг "
    "общественного питания»; оптовая, производственная и транспортная не "
    "подходят никому. (3) КОНФЛИКТ БРЕНДОВ: если вывеска объекта известна "
    "(справочник сетей или выученная пара), а держатель лицензии — известный "
    "держатель ДРУГОЙ вывески, пара не рассматривается: «Бристоль» не торгует по "
    "лицензии «Тандера». Неизвестная вывеска или неизвестный держатель конфликта "
    "не создают.",
    "• Выученные пары «вывеска → ИНН держателя» получены из самих данных "
    "голосованием по адресам алкогольного слоя; полная таблица, с парами у "
    "порога, — v4_brand_aliases.xlsx. Выученная пара — ГИПОТЕЗА со счётом за ней, "
    "а не факт: строки, опирающиеся на неё, помечены в «Основа балла названия».",
]

NOTES_MATCHED = [
    "• Строки только те, за которыми закреплена СОБСТВЕННАЯ лицензия "
    "(действующая или архивная). Объекты, у которых лицензия по адресу есть, но "
    "досталась другому объекту, другой сети или другого вида деятельности, сюда "
    "не попадают: для алкоголя они в v4_alcohol_no_licence.xlsx, для табака — "
    "только в v4_licences.csv.",
    "• Закреплённая лицензия — это совпадение АДРЕСА и держателя, а не "
    "доказательство, что именно эта вывеска торгует по ней. Правило «одна точка "
    "— один объект» лишь не даёт пяти магазинам в одном здании делить одну "
    "лицензию.",
    *NOTES_RULES,
    "• Реестр ФСРАР ведёт АЛКОГОЛЬ и не имеет табачного класса вовсе.",
    "• Столбца «продукция» здесь нет: реестр публикует это поле пустым во всех "
    "2 100 архангельских строках. Это свойство источника, а не потеря при выгрузке.",
    "• Снимок реестра — 01.07.2026; выгрузка подрядчика — 03–04.09.2026.",
]

NOTES_TOBACCO_EXTRA = [
    "• ЭТО НЕ ПРОВЕРКА ТАБАКА. Табачные строки сопоставлены с АЛКОГОЛЬНЫМИ "
    "лицензиями, потому что табачного реестра не существует. Найденная лицензия "
    "говорит лишь о том, что по этому адресу легально торгуют алкоголем.",
    "• Долю «вероятных» нельзя публиковать как долю подтверждённых табачных точек.",
]

NOTES_NO_LICENCE = [
    "• Строки — все алкогольные объекты БЕЗ СОБСТВЕННОЙ лицензии, по четырём "
    "причинам (столбец «Причина»). Это список кандидатов на ручную проверку, "
    "а не список доказанных ошибок разметки и не список нелегальной торговли.",
    "• «Точка закреплена за другим объектом» — это НЕ «лицензии по адресу нет». "
    "Лицензия там есть и оба порога прошла; её получил сосед с более сильной "
    "заявкой (столбец «Кому отдана точка»). Это может быть второй объект в том "
    "же здании (кафе в торговом центре, отдел в супермаркете), дубль одной точки "
    "под другим названием или объект, чья собственная лицензия записана по "
    "другому адресу; какой случай перед вами, решает только ручная проверка.",
    "• «Лицензии по адресу нет» означает одно из трёх: объект действительно не "
    "торгует алкоголем; лицензия записана по другому адресу; объект — общепит без "
    "собственной лицензии. Реестр эти случаи не различает.",
    *NOTES_RULES,
    "• Блок «Лучшая отклонённая лицензия» — самый близкий по баллу кандидат из "
    "реестра, без порогов, без предпочтения действующих и без трёх правил "
    "выбора. Он НЕ является лицензией этого объекта: он показывает, насколько "
    "близко строка подошла к совпадению.",
    "• Блок Я.Карт — третий справочник, а не второй реестр. Яндекс лицензий не "
    "ведёт: метка «есть» означает, что объект существует, а не что он торгует "
    "алкоголем легально. Метка «нет» тоже не доказательство отсутствия: "
    "справочник неполон, снимок сделан за один день.",
]

NOTES_BRANDS = [
    "• Реестр называет держателя лицензии, выгрузка — вывеску. Для крупных сетей "
    "пара «держатель → сеть» задана вручную (справочник сетей); остальные пары "
    "выучены из данных: каждый объект алкогольного слоя сопоставлен с лицензиями "
    "по адресу и расстоянию БЕЗ названия, точки розданы по правилу «одна точка — "
    "один объект», и держатель, который раз за разом достаётся одной вывеске на "
    "разных адресах, считается её держателем. Табачный слой не голосует: табачный "
    "киоск в супермаркете каждый раз стоит у лицензии супермаркета.",
    f"• Пара принимается, если набрала не меньше {_BP.min_sites} голосов, долю не "
    f"ниже {_BP.min_share:g} (для франшизы — {_BP.franchise_min_share:g}) и "
    f"подъём не ниже {_BP.min_lift:g}.",
    "• Принятая пара даёт балл названия 1 и участвует в правиле конфликта брендов. "
    "Это ГИПОТЕЗА со счётом за ней, а не факт: подтвердить или отклонить её может "
    "только человек, через столбец «Решение эксперта (review)» — то есть через "
    "словарь BRAND_REVIEW в src/arkhinfra/v4_egais.py.",
    "• Строки идут так: сначала используемые пары, затем «близко к порогу» (см. "
    "столбец «Группа»), затем остальные; внутри группы — по числу голосов.",
    "• Этот файл — снимок того запуска pixi run match-egais-v4, который записал "
    "v4_brand_aliases.csv.",
]
