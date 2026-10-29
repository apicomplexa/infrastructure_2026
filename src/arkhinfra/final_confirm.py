"""Is an object of the final delivery confirmed by two sources or more?

The final delivery (`data/raw_final/`, one XLSX per city and object class) ends
each row with source flags -- `OSM`, `GIS`, `Яндекс: найдено`, `Arkh_admin` --
and the deliverable asks for one more column, «Подтверждено»: 1 where at least
two *independent* sources say the object exists, 0 otherwise.  Summing the
flags is not enough, for three reasons found in the data:

* **A row is not an object.**  The export repeats one place under every type it
  could be -- «#хочуЛето, гастрокафе» is a bakery, a restaurant and a canteen,
  three rows at one coordinate.  Arkhangelsk's 2,500 catering rows are 1,141
  objects.  Sources are counted per object (`entity`) and the verdict is
  written back to every row of it; the contractor's flags disagree inside an
  object in a handful of cases, and any row's flag counts for the object.
* **The contractor's Yandex «Найдено» confirms an address, not an object.**  Its
  rule is city + full address + category; the name matched in 190 of 407 cases
  in Arkhangelsk, and «Tupperware, дистрибьюторный центр» counts as found
  because «Йоко суши» shares its building.  The names Yandex returned are kept
  in `Яндекс: название`, so the hit is re-judged here with the same name rule as
  our own check (`v4_yandex.name_similarity`), at no cost in requests.
* **The contractor's merge missed pairs.**  «1234» (OSM only) and «1234,
  кофейня» (OSM + 2GIS) stand 14 m apart as two objects.  Where an object lacks
  a provider and a near, alike-named object of the *other* provider stands
  within `RELINK_M`, that provider is counted for it (`relink`), and the row
  says which record lent it.

Yandex is counted once however it is reached -- the contractor's re-judged hit
or our own query (`v4_yandex`, name + address, map centred on the object).  A
card Yandex marks «Больше не работает» asserts the opposite of existence and is
never counted; it is reported beside the verdict instead, because two sources
of an object that has closed are a reason to look again.

Independence: OSM, 2GIS and Yandex are three companies' directories.  Flamp
(2GIS) and Яндекс Еда (Yandex) would not be new sources, and must not be added
as such.
"""
from __future__ import annotations

import re
from copy import copy
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from . import v4_yandex as y
from .paths import PROC_CONFIRM, ensure_licmatch_path

ensure_licmatch_path()

from licmatch import fold  # noqa: E402

CACHE = PROC_CONFIRM / "final_yandex_cache.jsonl"
OBJECTS_CSV = PROC_CONFIRM / "final_confirm_objects.csv"
SUMMARY_TXT = PROC_CONFIRM / "final_confirm_summary.txt"

DATA_SHEET = "data"
CONFIRMED = "Подтверждено"
REASONS = "Основания"
# Columns put in front of the contractor's, in this order.
FOOD = "Общепит?"
FRONT = [(CONFIRMED, "confirmed", 14), (REASONS, "reasons", 70), (FOOD, "food", 14)]
MIN_SOURCES = 2

# A near pair from the two providers is the contractor's own missed merge only
# at a building's depth; a nameless fascia ("Столовая") has to be closer still,
# since every canteen matches every other by name.
RELINK_M = 50.0
RELINK_GENERIC_M = 20.0
NAME_MIN = y.NAME_MIN

# Words that name a kind of catering rather than a business.  An object whose
# fascia is made of nothing else ("Кофейный автомат", "Шаурма", "Пекарня") can
# be matched by distance only, never by name.  `fascia_name` already drops
# кафе / бар / ресторан / столовая / кулинария / пекарня / кофейня.
GENERIC_TOKENS = frozenset({
    "кофе", "кофейный", "кофейная", "автомат", "автоматы", "вендинг",
    "самообслуживания", "собой", "навынос", "буфет", "бистро", "закусочная",
    "фастфуд", "фаст", "фуд", "food", "шаурма", "шаверма", "пицца", "пиццерия",
    "суши", "роллы", "пончики", "пончиковая", "блины", "блинная", "пироги",
    "пирожковая", "выпечка", "хлеб", "хлебный", "кондитерская", "чебуречная",
    "пельменная", "шашлык", "шашлычная", "гриль", "бургерная", "кафе-бар",
    "ресто-бар", "кофе-бар", "столовая", "еда", "обеды", "горячие", "напитки",
    "чайная", "кухня", "домашняя", "уличная", "точка", "киоск", "павильон",
    "магазин", "овощей", "фруктов", "и", "с", "на", "24", "часа",
    "кофе-пойнт", "кофепойнт", "коктейльная", "пивной", "бар-ресторан",
    "шаурменная", "шаверменная", "булочная", "кулинарная", "хлебная", "лавка",
    "кофейня", "пекарня", "кулинария", "мини", "экспресс",
})

STATUS_FOUND = "Найдено"

# The export and the directories write one sign in either alphabet -- «Stare
# Mesto» / «Старе Место», «Polina» / «Полина».  Latin is read into Cyrillic the
# way a Russian reader would say it; digraphs first.
_LAT_DIGRAPHS = [("shch", "щ"), ("sh", "ш"), ("ch", "ч"), ("zh", "ж"), ("kh", "х"),
                 ("ts", "ц"), ("ya", "я"), ("yu", "ю"), ("yo", "ё"), ("ee", "и"),
                 ("oo", "у"), ("ph", "ф"), ("ck", "к"), ("th", "т")]
_LAT_SINGLE = str.maketrans(dict(zip(
    "abcdefghijklmnopqrstuvwxyz",
    ["а", "б", "к", "д", "е", "ф", "г", "х", "и", "дж", "к", "л", "м", "н", "о",
     "п", "к", "р", "с", "т", "у", "в", "в", "кс", "й", "з"])))


def translit(name: str) -> str:
    """Latin letters read into Cyrillic; Cyrillic and digits left alone."""
    s = fold(name)
    for a, b in _LAT_DIGRAPHS:
        s = s.replace(a, b)
    return s.translate(_LAT_SINGLE)


def similar(a: str, b: str) -> float:
    """`v4_yandex.name_similarity`, also tried with both sides in Cyrillic."""
    sim = y.name_similarity(a, b)
    if sim >= NAME_MIN or not re.search(r"[a-z]", fold(a + b)):
        return sim
    return max(sim, y.name_similarity(translit(a), translit(b)))


def source_links(ids: str) -> tuple[list[str], list[str]]:
    """`matched_source_ids` ("osm:node:1; 2gis:7000…") as (OSM, 2GIS) URLs."""
    osm, gis = [], []
    for tok in str(ids).split(";"):
        parts = tok.strip().split(":")
        if parts[0] == "osm" and len(parts) == 3:
            osm.append(f"https://www.openstreetmap.org/{parts[1]}/{parts[2]}")
        elif parts[0] == "2gis" and len(parts) == 2:
            gis.append(f"https://2gis.ru/firm/{parts[1]}")
    return osm, gis


def is_generic(name: str) -> bool:
    """True where the fascia names a trade, not a business."""
    if y.is_generic(name):
        return True
    toks = re.sub(r"[^0-9a-zа-я\- ]+", " ", fold(name)).split()
    return all(t in GENERIC_TOKENS for t in toks)


def load(path: Path) -> pd.DataFrame:
    """The `data` sheet as read, plus the object each row belongs to.

    The `quality` sheet carries the source ids (`matched_source_ids`) but in a
    *different row order* -- joined by position its `providers` disagree with
    `data`'s OSM/GIS on most rows.  `original_data` is row-aligned with `data`
    and shares five columns with `quality` that are unique per row in every
    file, so the ids travel through it by key; the join is checked to be
    one-to-one and to agree with OSM/GIS on every row, or the load fails.
    """
    df = pd.read_excel(path, sheet_name=DATA_SHEET)
    orig = pd.read_excel(path, sheet_name="original_data")
    qual = pd.read_excel(path, sheet_name="quality")
    key = ["type_orig", "name_orig", "adress_orig", "latitude", "longitude"]
    if len(orig) != len(df) or orig.duplicated(key).any() or qual.duplicated(key).any():
        raise RuntimeError(f"{path.name}: original_data/quality cannot be keyed to data")
    ids = orig[key].merge(qual[key + ["providers", "matched_source_ids"]], on=key,
                          how="left", validate="1:1")
    prov = ids["providers"].fillna("")
    if not ((prov.str.contains("osm") == df["OSM"].eq(1))
            & (prov.str.contains("2gis") == df["GIS"].eq(1))).all():
        raise RuntimeError(f"{path.name}: quality providers disagree with data OSM/GIS")
    df["_ids"] = ids["matched_source_ids"].fillna("").to_numpy()
    df["_name"] = df["name"].fillna("").astype(str).str.strip()
    df["_addr"] = df["address"].fillna("").astype(str).str.strip()
    key = (df["city"].astype(str) + "|" + df["_name"] + "|"
           + df["latitude"].round(6).astype(str) + "|"
           + df["longitude"].round(6).astype(str))
    df["entity"] = pd.factorize(key)[0]
    df["site_key"] = key
    return df


def contractor_yandex(df: pd.DataFrame) -> pd.DataFrame:
    """The contractor's «Найдено», kept only where Yandex's name is ours too.

    `Яндекс: название` holds every name the card list showed at the address,
    "; "-separated; the best of them is compared.  A miss here is not "absent"
    -- it only means the contractor's hit does not name this object.  Returns
    `ok` and, where ok, the Yandex name that matched.
    """
    found = df["Яндекс: статус"].eq(STATUS_FOUND)
    out = pd.DataFrame({"ok": False, "ya_c_name": ""}, index=df.index)
    for i in df.index[found]:
        names = [n.strip() for n in str(df.at[i, "Яндекс: название"]).split(";")
                 if n.strip() and n.strip() != "nan"]
        scored = [(similar(df.at[i, "_name"], n), n) for n in names]
        sim, best = max(scored, default=(0.0, ""))
        if sim >= NAME_MIN:
            out.at[i, "ok"], out.at[i, "ya_c_name"] = True, best
    return out


def _first_nonempty(s: pd.Series) -> str:
    return next((v for v in s if isinstance(v, str) and v and v != "nan"), "")


def _links(s: pd.Series, which: int) -> str:
    return " ".join(dict.fromkeys(u for ids in s for u in source_links(ids)[which]))


def objects(df: pd.DataFrame) -> pd.DataFrame:
    """One row per object: its flags OR-ed over the rows that repeat it."""
    cy = contractor_yandex(df)
    df = df.assign(_ya_contr=cy["ok"],
                   _ya_c_name=cy["ya_c_name"].where(cy["ok"], ""),
                   _ya_c_addr=df["Яндекс: адрес"].where(cy["ok"], ""),
                   _ya_c_url=df["Яндекс: ссылка"].where(cy["ok"], ""),
                   _arkh=pd.to_numeric(df.get("Arkh_admin"), errors="coerce").fillna(0).eq(1))
    g = df.groupby("entity", sort=True)
    ob = pd.DataFrame({
        "city": g["city"].first(), "name": g["_name"].first(),
        "address": g["_addr"].first(), "lat": g["latitude"].first(),
        "lon": g["longitude"].first(), "site_key": g["site_key"].first(),
        "n_rows": g.size(), "types": g["type"].agg(lambda s: "; ".join(sorted(set(map(str, s))))),
        "osm": g["OSM"].max().fillna(0).astype(bool),
        "gis": g["GIS"].max().fillna(0).astype(bool),
        "arkh_admin": g["_arkh"].any(),
        "ya_contractor": g["_ya_contr"].any(),
        "ya_contractor_raw": g["Яндекс: статус"].agg(lambda s: s.eq(STATUS_FOUND).any()),
        "ya_c_name": g["_ya_c_name"].agg(_first_nonempty),
        "ya_c_addr": g["_ya_c_addr"].agg(_first_nonempty),
        "ya_c_url": g["_ya_c_url"].agg(_first_nonempty),
        "osm_urls": g["_ids"].agg(lambda s: _links(s, 0)),
        "gis_urls": g["_ids"].agg(lambda s: _links(s, 1)),
    })
    ob["generic"] = [is_generic(n) for n in ob["name"]]
    return ob


def _dist_matrix(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    la, lo = np.radians(lat), np.radians(lon)
    dla = la[:, None] - la[None, :]
    dlo = lo[:, None] - lo[None, :]
    h = np.sin(dla / 2) ** 2 + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlo / 2) ** 2
    return 2 * 6371008.8 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def relink(ob: pd.DataFrame) -> pd.DataFrame:
    """Lend a provider to an object from the other provider's twin next door.

    Symmetric name test (the weaker direction of `name_similarity`), because
    both sides are records of the same export and neither is the "directory".
    Within one city only; nearest qualifying twin wins.
    """
    ob = ob.assign(osm_link=False, gis_link=False, link_note="",
                   osm_link_from="", gis_link_from="")
    for _, part in ob.groupby("city"):
        idx = part.index.to_numpy()
        d = _dist_matrix(part["lat"].to_numpy(float), part["lon"].to_numpy(float))
        np.fill_diagonal(d, np.inf)
        for a_pos, a in enumerate(idx):
            for prov in ("osm", "gis"):
                if ob.at[a, prov]:
                    continue
                cand = np.where((d[a_pos] <= RELINK_M) & part[prov].to_numpy(bool))[0]
                for b_pos in cand[np.argsort(d[a_pos, cand])]:
                    b = idx[b_pos]
                    limit = RELINK_GENERIC_M if (ob.at[a, "generic"] or ob.at[b, "generic"]) else RELINK_M
                    if d[a_pos, b_pos] > limit:
                        continue
                    na, nb = ob.at[a, "name"], ob.at[b, "name"]
                    sim = min(similar(na, nb), similar(nb, na))
                    if sim < NAME_MIN:
                        continue
                    ob.at[a, f"{prov}_link"] = True
                    note = (f"{'OSM' if prov == 'osm' else '2GIS'} из записи «{nb}»"
                            f" ({d[a_pos, b_pos]:.0f} м)")
                    urls = ob.at[b, f"{prov}_urls"]
                    ob.at[a, f"{prov}_link_from"] = f"«{nb}», {d[a_pos, b_pos]:.0f} м" + (
                        f", {urls}" if urls else "")
                    ob.at[a, "link_note"] = "; ".join(filter(None, [ob.at[a, "link_note"], note]))
                    break
    return ob


def own_yandex(ob: pd.DataFrame, cache: dict[str, dict]) -> pd.DataFrame:
    """Judge every cached Yandex answer; objects never read stay "".

    Judging is free, so thresholds can move without a request.  The verdict
    uses this module's `is_generic`, not retail's.
    """
    cols = {k: [] for k in ("ya_status", "ya_name", "ya_address", "ya_url",
                            "ya_distance_m", "ya_nearby", "ya_search_url", "ya_checked")}
    for _, r in ob.iterrows():
        rec = cache.get(r["site_key"])
        if rec is None:
            for k in cols:
                cols[k].append("")
            continue
        v = y.verdict(rec, r["name"], float(r["lat"]), float(r["lon"]), generic=bool(r["generic"]))
        cols["ya_status"].append(v["status"])
        cols["ya_name"].append(v["yandex_name"])
        cols["ya_address"].append(v["yandex_address"])
        cols["ya_url"].append(v["yandex_url"])
        cols["ya_distance_m"].append(v["yandex_distance_m"])
        cols["ya_nearby"].append(v["yandex_nearby"])
        cols["ya_search_url"].append(rec.get("search_url", ""))
        cols["ya_checked"].append(rec.get("checked", ""))
    return ob.assign(**cols)


def _osm_gis_reason(r: pd.Series, prov: str, label: str) -> str:
    if r[prov]:
        urls = r[f"{prov}_urls"]
        return f"{label}: запись выгрузки" + (f" ({urls})" if urls else "")
    if r[f"{prov}_link"]:
        return f"{label}: соседняя запись {r[f'{prov}_link_from']}"
    return ""


def _yandex_reason(r: pd.Series) -> str:
    parts = []
    if r["ya_status"] == y.STATUS_PRESENT:
        parts.append(f"карточка «{r['ya_name']}», {r['ya_address']}, {r['ya_distance_m']} м"
                     f" (наша проверка {r['ya_checked']}; {r['ya_url'] or r['ya_search_url']})")
    if r["ya_contractor"]:
        parts.append(f"карточка «{r['ya_c_name']}», {r['ya_c_addr']} (проверка подрядчика"
                     + (f"; {r['ya_c_url']}" if r["ya_c_url"] else "") + ")")
    return ("Яндекс: " + "; ".join(parts)) if parts else ""


def _against(r: pd.Series) -> str:
    """What was looked for and not found -- where to dig next."""
    out = []
    if r["ya_contractor_raw"] and not r["ya_contractor"]:
        out.append("Яндекс (подрядчик): по адресу есть общепит, но с другим названием")
    if r["ya_status"] == y.STATUS_CLOSED:
        out.append(f"Яндекс: «{r['ya_name']}» — «Больше не работает»")
    elif r["ya_status"] == y.STATUS_ABSENT:
        out.append("Яндекс: по названию и адресу не найден"
                   + (f" (рядом: {r['ya_nearby']})" if r["ya_nearby"] else ""))
    elif r["ya_status"] == y.STATUS_AMBIGUOUS:
        out.append(f"Яндекс: по адресу кто-то есть, вывеска безымянная (рядом: {r['ya_nearby']})")
    if r.get("egais_note") and not r.get("src_egais"):
        out.append(f"ЕГАИС: {r['egais_note']}")
    if r.get("ov_note"):
        out.append(f"Overture: «{r['ov_name']}» — {r['ov_note']}")
    if r.get("fsq_note"):
        out.append(f"Foursquare: «{r['fsq_name']}» {r['fsq_distance_m']} м, {r['fsq_note']}")
    return "; ".join(out)


# Overture Places (`scripts/fetch_overture.py`): Meta, Foursquare,
# AllThePlaces, never OSM.  Same acceptance as our Yandex check; Overture's own
# `confidence` below this is its own "probably not there".
OV_CONF_MIN = 0.5
# Stricter than the Yandex name floor: AllThePlaces is chains, so a same-brand
# branch is often the nearest place, and at 72 «Coffee Lab» took «Coffee Like»
# 120 m away and «Stare Mesto» the hostel «Старое Место».  85 drops those and
# two true pairs («Америго» / «Боулинг-центр «Америго»», «Эдисон» / «Бар Edison»).
OV_NAME_MIN = 85.0


def load_overture(path: Path | None = None) -> pd.DataFrame | None:
    """The newest Overture snapshot in `RAW_OVERTURE`, or None when absent."""
    from .paths import RAW_OVERTURE
    files = [path] if path else sorted(RAW_OVERTURE.glob("overture_places_*.parquet"))
    if not files or not files[-1].exists():
        return None
    import duckdb  # the env has no pyarrow; duckdb reads parquet on its own
    pl = duckdb.sql(f"SELECT * FROM '{files[-1]}'").df()
    pl["name"] = pl["name"].fillna("").astype(str)
    return pl[pl["name"].ne("")].reset_index(drop=True)


def overture(ob: pd.DataFrame, places: pd.DataFrame | None) -> pd.DataFrame:
    """Nearest alike-named Overture place for every object, if any."""
    cols = {"ov_match": False, "ov_name": "", "ov_category": "", "ov_dataset": "",
            "ov_confidence": np.nan, "ov_distance_m": np.nan, "ov_id": "", "ov_note": ""}
    ob = ob.assign(**cols)
    if places is None or places.empty:
        return ob
    plat, plon = np.radians(places["lat"].to_numpy(float)), np.radians(places["lon"].to_numpy(float))
    conf = places["confidence"].fillna(0).to_numpy(float)
    for i, r in ob.iterrows():
        la, lo = np.radians(r["lat"]), np.radians(r["lon"])
        h = (np.sin((plat - la) / 2) ** 2
             + np.cos(la) * np.cos(plat) * np.sin((plon - lo) / 2) ** 2)
        d = 2 * 6371008.8 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
        limit = y.GENERIC_M if r["generic"] else y.NEAR_M
        for j in np.where((d <= limit) & (conf >= OV_CONF_MIN))[0][np.argsort(d[(d <= limit) & (conf >= OV_CONF_MIN)])]:
            if similar(r["name"], places.at[j, "name"]) >= OV_NAME_MIN:
                ob.loc[i, list(cols)] = [True, places.at[j, "name"], places.at[j, "category"] or "",
                                         places.at[j, "datasets"] or places.at[j, "dataset"],
                                         round(float(conf[j]), 2), round(float(d[j]), 1),
                                         places.at[j, "id"], ""]
                break
    return ob


# FSQ OS Places direct (`scripts/fetch_foursquare.py`): ~16k places in the box
# against Overture's 200 Foursquare rows.  Most were last refreshed in
# 2013-2016, and a 2014 record says the place existed in 2014; only a record
# refreshed since FSQ_FRESH counts, older matches are shown, not counted.  A
# record with `date_closed` never counts.  Name floor as for Overture.
FSQ_FRESH = "2022-01-01"
FSQ_NAME_MIN = OV_NAME_MIN


def load_foursquare(path: Path | None = None) -> pd.DataFrame | None:
    """The newest FSQ OS Places snapshot in `RAW_FOURSQUARE`, or None when absent."""
    from .paths import RAW_FOURSQUARE
    files = [path] if path else sorted(RAW_FOURSQUARE.glob("fsq_places_*.parquet"))
    if not files or not files[-1].exists():
        return None
    import duckdb
    pl = duckdb.sql(f"SELECT * FROM '{files[-1]}'").df()
    pl["name"] = pl["name"].fillna("").astype(str)
    for c in ("date_refreshed", "date_closed", "categories"):
        pl[c] = pl[c].fillna("").astype(str)
    return pl[pl["name"].ne("")].reset_index(drop=True)


def foursquare(ob: pd.DataFrame, places: pd.DataFrame | None) -> pd.DataFrame:
    """Nearest alike-named open FSQ place, preferring a fresh one.

    `fsq_match` is True only for a fresh, open record; `fsq_name` etc. describe
    the record found either way, `fsq_note` says why a found one did not count.
    """
    cols = {"fsq_match": False, "fsq_name": "", "fsq_category": "", "fsq_refreshed": "",
            "fsq_distance_m": np.nan, "fsq_id": "", "fsq_note": ""}
    ob = ob.assign(**cols)
    if places is None or places.empty:
        return ob
    plat, plon = np.radians(places["lat"].to_numpy(float)), np.radians(places["lon"].to_numpy(float))
    fresh = places["date_refreshed"].ge(FSQ_FRESH).to_numpy()
    closed = places["date_closed"].ne("").to_numpy()
    for i, r in ob.iterrows():
        la, lo = np.radians(r["lat"]), np.radians(r["lon"])
        h = (np.sin((plat - la) / 2) ** 2
             + np.cos(la) * np.cos(plat) * np.sin((plon - lo) / 2) ** 2)
        d = 2 * 6371008.8 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
        near = np.where(d <= (y.GENERIC_M if r["generic"] else y.NEAR_M))[0]
        hits = [j for j in near[np.argsort(d[near])]
                if similar(r["name"], places.at[j, "name"]) >= FSQ_NAME_MIN]
        if not hits:
            continue
        # A fresh open record wins over a nearer stale or closed one.
        best = next((j for j in hits if fresh[j] and not closed[j]), hits[0])
        ok = bool(fresh[best] and not closed[best])
        note = ("" if ok else f"закрыт с {places.at[best, 'date_closed']}" if closed[best]
                else f"запись не обновлялась с {places.at[best, 'date_refreshed'][:4]}")
        ob.loc[i, list(cols)] = [ok, places.at[best, "name"], places.at[best, "categories"],
                                 places.at[best, "date_refreshed"], round(float(d[best]), 1),
                                 places.at[best, "fsq_place_id"], note]
    return ob


def exclusive(ob: pd.DataFrame) -> pd.DataFrame:
    """One place record confirms one site, not every alike-named object near it.

    A record matched by several objects goes to the nearest of them and to the
    objects within `RELINK_M` of that one -- the contractor's own unmerged
    duplicates («Библио-Кофе» / «Библио-кофе, кофейня», one door).  The rest
    lose it: Hindi on Троицкий 61 and 67 are two restaurants, one FSQ point.
    """
    ob = ob.copy()
    for pre, ident in (("ov", "ov_id"), ("fsq", "fsq_id")):
        if ident not in ob:
            continue
        hit = ob[ob[ident].fillna("").astype(str).ne("")]
        for _, g in hit[hit[ident].duplicated(keep=False)].groupby(ident):
            w = g[f"{pre}_distance_m"].idxmin()
            d = _dist_matrix(g["lat"].to_numpy(float), g["lon"].to_numpy(float))[g.index.get_loc(w)]
            for i, di in zip(g.index, d):
                if di <= RELINK_M:
                    continue
                note = (f"запись ближе к объекту «{ob.at[w, 'name']}» ({ob.at[w, 'address']}), "
                        f"{di:.0f} м отсюда")
                ob.at[i, f"{pre}_match"] = False
                if pre == "fsq":
                    ob.at[i, "fsq_note"] = note
                else:
                    ob.at[i, "ov_note"] = note
    return ob


# Is the object catering at all?  The export's class is not trusted: it files
# «Лемана Про», Fix Price and a dozen design bureaus under «Кафе и кофейни».
# Four independent descriptions of the object's kind are read, none of them
# the contractor's: the descriptor 2GIS writes after the comma in the name
# («…, проектная компания»), Yandex's rubric for the very card it matched,
# Foursquare's category and Overture's.  A stale FSQ record still tells the
# kind (a hardware store does not become a café), so every found record is
# read here, not only the counted ones.  Order of tests matters: a vending
# machine is neither, a «магазин-кафе» is catering, «магазин» alone is not.
# «Служба доставки» says nothing either way: in this class it is sushi and pizza.
PROFILE_VENDING = re.compile(r"автомат|кофемат|вендинг|кофемашин")
# Wins over a catering word in the same text: wholesale and kit for kitchens
# name food without being a place to eat; «кафедра» / «кафедральный» start with «кафе».
PROFILE_NOT_PLACE = re.compile(r"оптом|оптов|оборудовани|кафедр|собор|храм|церк")
PROFILE_FOOD = re.compile(
    r"кафе(?!др)|кофе|ресторан|столов|\bбар|бар\b|паб\b|пекарн|кулинари|кондитерская|бистро|пиццер|"
    r"бургер|шаурм|шаверм|суши|роллы|закусоч|буфет|фуд-?трак|чайхан|банкетн|доставки еды|"
    r"быстрого питания|общественного питания|кейтеринг|гриль|рюмочн|пельмен|блин|чебуреч|трактир|харчевн|донер|хинкал|пирожк|"
    r"кухня|гастро|лаундж|кальянн|таверн|шашлык|хот-?дог|банкет|"
    r"coffee|cafe|pizza|grill|sushi|burger|bakery|kitchen|\bbar\b|\bpub\b")
PROFILE_OTHER = re.compile(
    r"магазин|маркет|гипермаркет|компани|организаци|мастерская|студи|торговый дом|салон|"
    r"\bцентр\b|клуб|склад|\bбаза\b|представительств|ателье|аптек|офис|"
    r"агентств|бюро|фирма|завод|производств|оптов|бутик|отдел|ларёк|киоск печати|"
    r"гостиниц|хостел|отель|школа|сервис|товары|продукты|продукция|курсы|мастер-класс")
PROFILE_ADDR = re.compile(r"\d|\bул\.|улица|проспект|просп\.|\bпр\.|пр-т|\bш\.|\bпер\.|\bпл\.|наб\.|набережная|площадь|шоссе|переулок|"
                          r"бульвар|архангельск|северодвинск|новодвинск|округ|район")
OV_FOOD = re.compile(r"restaurant|cafe|coffee|\bbar\b|_bar|pub|bakery|cafeteria|food|pizza|lounge|"
                     r"buffet|tea_room|bistro|diner|deli|brewery|canteen|dessert|ice_cream|caterer")
OV_OTHER = re.compile(r"store|shop|mall|market|company|service|office|agency|contractor|"
                      r"supplier|wholesale|repair|salon|school|bank|clinic|pharmacy")


FSQ_NOT_FOOD = ("Retail", "Business and Professional Services", "Health and Medicine",
                "Community and Government")


def _kind(text: str) -> str:
    """'да' / 'нет' / 'автомат' / '' for a Russian descriptor or rubric."""
    t = text.lower()
    if not t:
        return ""
    if PROFILE_VENDING.search(t):
        return "автомат"
    if PROFILE_NOT_PLACE.search(t):
        return "нет"
    if PROFILE_FOOD.search(t):
        return "да"
    if PROFILE_OTHER.search(t):
        return "нет"
    return ""


def _yandex_rubric(rec: dict | None, url: str) -> str:
    """Yandex's rubrics for the card our check matched, from the page title."""
    if not rec or not url:
        return ""
    oid = re.search(r"/(\d{6,})/?", url)
    if not oid or oid.group(1) not in (rec.get("canonical") or ""):
        return ""
    title = re.sub(r"^Больше не работает:\s*", "", rec.get("og_title") or "")
    title = title.split(" — Яндекс")[0]
    parts = [p.strip() for p in title.split(",")][1:]   # drop the name
    out = []
    for p in parts:
        if PROFILE_ADDR.search(p.lower()):
            break
        out.append(p)
    return ", ".join(out)


def profile(ob: pd.DataFrame, cache: dict[str, dict]) -> pd.DataFrame:
    """«Профиль: общепит» -- да / нет / противоречие / автомат / нет данных, with reasons."""
    verdicts, reasons = [], []
    for _, r in ob.iterrows():
        votes = []
        name = str(r["name"])
        if "," in name:
            desc = name.rsplit(",", 1)[1].strip()
            votes.append(("2GIS, описание в названии", desc, _kind(desc)))
        else:
            votes.append(("название", name, _kind(name)))
        rub = _yandex_rubric(cache.get(r["site_key"]), str(r.get("ya_url") or ""))
        if rub:
            votes.append(("Яндекс, рубрика", rub, _kind(rub)))
        fcat = str(r.get("fsq_category") or "")
        if fcat and str(r.get("fsq_name") or ""):
            labels = fcat.split("|")
            k = ("да" if any(l.startswith("Dining and Drinking") or re.search(r"Cafeteria|Restaurant|Caf[eé]|Bar\b", l)
                            for l in labels) else
                 "нет" if all(l.split(" > ")[0] in FSQ_NOT_FOOD for l in labels)
                 else "")
            votes.append(("Foursquare", fcat, k))
        ocat = str(r.get("ov_category") or "")
        if ocat and str(r.get("ov_name") or ""):
            k = "да" if OV_FOOD.search(ocat) else "нет" if OV_OTHER.search(ocat) else ""
            votes.append(("Overture", ocat, k))
        said = {k for _, _, k in votes if k}
        if not said:
            v = "нет данных"
        elif said == {"да"}:
            v = "да"
        elif said == {"нет"}:
            v = "нет"
        elif said == {"автомат"}:
            v = "автомат"
        elif "да" in said and "нет" in said:
            v = "противоречие"
        else:   # vending beside one other kind: the other kind decides
            v = (said - {"автомат"}).pop()
        verdicts.append(v)
        reasons.append(" | ".join(f"{src}: «{txt}» → {k or '?'}" for src, txt, k in votes))
    return ob.assign(food=verdicts, food_reasons=reasons)


def decide(ob: pd.DataFrame) -> pd.DataFrame:
    """Count the independent sources and pass the verdict.

    `egais_*` columns are optional: present when `final_egais.match_catering`
    has been run, and then a catering licence of the object's own counts as
    one more source.
    """
    ob = ob.copy()
    if "egais_match" not in ob:
        ob["egais_match"] = False
    if "ov_match" not in ob:
        ob["ov_match"] = False
    if "fsq_match" not in ob:
        ob["fsq_match"] = False
    ob["src_osm"] = ob["osm"] | ob["osm_link"]
    ob["src_gis"] = ob["gis"] | ob["gis_link"]
    ob["src_yandex"] = ob["ya_contractor"] | ob["ya_status"].eq(y.STATUS_PRESENT)
    ob["src_arkh"] = ob["arkh_admin"]
    ob["src_egais"] = ob["egais_match"].fillna(False).astype(bool)
    # An Overture place built from Foursquare alone is Foursquare, not a
    # second source beside it: it counts under Foursquare, by the same
    # freshness rule (Overture keeps no refresh date, so it falls to FSQ direct).
    ov_fsq_only = ob["ov_dataset"].fillna("").astype(str).str.lower().eq("foursquare")
    ob["src_overture"] = ob["ov_match"].fillna(False).astype(bool) & ~ov_fsq_only
    ob["src_fsq"] = ob["fsq_match"].fillna(False).astype(bool)
    src = {"OSM": "src_osm", "2GIS": "src_gis", "Яндекс": "src_yandex",
           "Overture": "src_overture", "Foursquare": "src_fsq",
           "Администрация": "src_arkh", "ЕГАИС": "src_egais"}
    ob["n_sources"] = sum(ob[c].astype(int) for c in src.values())
    ob["sources"] = ["; ".join(k for k, c in src.items() if r[c]) for _, r in ob.iterrows()]
    ob["confirmed"] = (ob["n_sources"] >= MIN_SOURCES).astype(int)
    ob["ya_closed"] = ob["ya_status"].eq(y.STATUS_CLOSED)
    ob["yandex_how"] = [
        "; ".join(filter(None, [
            "подрядчик: имя совпало" if r["ya_contractor"] else
            ("подрядчик: только адрес+категория" if r["ya_contractor_raw"] else ""),
            {y.STATUS_PRESENT: "наша проверка: есть", y.STATUS_CLOSED: "наша проверка: закрыт",
             y.STATUS_AMBIGUOUS: "наша проверка: не опознан", y.STATUS_ABSENT: "наша проверка: нет",
             y.STATUS_ERROR: "наша проверка: ошибка"}.get(r["ya_status"], ""),
        ])) for _, r in ob.iterrows()]
    reasons = []
    for _, r in ob.iterrows():
        pro = [_osm_gis_reason(r, "osm", "OSM"), _osm_gis_reason(r, "gis", "2GIS"),
               _yandex_reason(r),
               (f"Overture: «{r['ov_name']}» ({r['ov_category']}), {r['ov_distance_m']} м, "
                f"источник {r['ov_dataset']}, уверенность {r['ov_confidence']}, id {r['ov_id']}")
               if r["src_overture"] else "",
               (f"Foursquare: «{r['fsq_name']}» ({r['fsq_category']}), {r['fsq_distance_m']} м, "
                f"обновлено {r['fsq_refreshed']}, id {r['fsq_id']}") if r["src_fsq"] else "",
               "Администрация: в реестре (Arkh_admin = 1)" if r["src_arkh"] else ""]
        if r["src_egais"]:
            pro.append(f"ЕГАИС: лицензия {r['egais_licence_no']} ({r['egais_status']}), "
                       f"{r['egais_holder']}, {r['egais_outlet_address']}")
        text = " | ".join(p for p in pro if p) or "источников нет"
        con = _against(r)
        reasons.append(text + (f" || против/не найдено: {con}" if con else ""))
    ob["reasons"] = reasons
    return ob


def needs_yandex(ob: pd.DataFrame) -> pd.Series:
    """Objects whose verdict our own Yandex query could still change."""
    have = ob["osm"] | ob["osm_link"]
    have = have.astype(int) + (ob["gis"] | ob["gis_link"]).astype(int) + ob["arkh_admin"].astype(int)
    for extra in ("egais_match", "ov_match", "fsq_match"):
        if extra in ob:
            have = have + ob[extra].fillna(False).astype(bool).astype(int)
    return (have < MIN_SOURCES) & ~ob["ya_contractor"]


# Columns appended to the `data` sheet, after the contractor's own.
APPENDED = [
    ("Источников", "n_sources"),
    ("Источники", "sources"),
    ("Общепит: основания", "food_reasons"),
    ("Яндекс: как засчитан", "yandex_how"),
    ("Яндекс (наша): статус", "ya_status"),
    ("Яндекс (наша): название", "ya_name"),
    ("Яндекс (наша): адрес", "ya_address"),
    ("Яндекс (наша): карточка", "ya_url"),
    ("Яндекс (наша): расстояние, м", "ya_distance_m"),
    ("Яндекс (наша): рядом", "ya_nearby"),
    ("Яндекс (наша): запрос", "ya_search_url"),
    ("Яндекс (наша): дата", "ya_checked"),
    ("Связанная запись", "link_note"),
    ("ЕГАИС: лицензия", "egais_licence_no"),
    ("ЕГАИС: владелец", "egais_holder"),
    ("ЕГАИС: пояснение", "egais_note"),
    ("Overture: название", "ov_name"),
    ("Overture: источник", "ov_dataset"),
    ("Overture: расстояние, м", "ov_distance_m"),
    ("Overture: пояснение", "ov_note"),
    ("Foursquare: название", "fsq_name"),
    ("Foursquare: обновлено", "fsq_refreshed"),
    ("Foursquare: расстояние, м", "fsq_distance_m"),
    ("Foursquare: пояснение", "fsq_note"),
    ("Объект №", "entity"),
    ("Строк у объекта", "n_rows"),
]

LEGEND = [
    ("Подтверждено", "1 — о существовании объекта говорят не менее двух независимых источников; 0 — меньше двух."),
    ("Основания", "По каждому засчитанному источнику — где найден объект: ссылка на запись OSM / карточку 2GIS, "
     "карточка Яндекса с адресом и способом проверки, соседняя запись, давшая провайдера, лицензия ЕГАИС. "
     "Источники разделены « | ». После « || против/не найдено:» — что искали и не нашли (куда копать дальше)."),
    ("Что такое объект", "Одна вывеска в одной точке (название + координата). Выгрузка повторяет объект под каждым типом "
     "(кафе, ресторан, столовая…), поэтому источники считаются по объекту, а вердикт пишется во все его строки."),
    ("Источники", "OSM, 2GIS, Яндекс Карты, реестр администрации (колонка Arkh_admin, когда заполнена), "
     "Overture Maps Places (Meta / AllThePlaces, без OSM), Foursquare OS Places, "
     "лицензия ЕГАИС на общепит у самого объекта (когда сверка с реестром выполнена). "
     "Яндекс засчитывается один раз, как бы он ни был получен."),
    ("OSM / 2GIS", "Флаги OSM и GIS листа data, объединённые по строкам объекта. Если у объекта нет провайдера, но в пределах "
     f"{RELINK_M:.0f} м ({RELINK_GENERIC_M:.0f} м для безымянной вывески) стоит запись другого провайдера с тем же именем, "
     "провайдер засчитывается — это пропущенная подрядчиком склейка; колонка «Связанная запись» называет эту запись."),
    ("Яндекс: подрядчик", "«Найдено» подрядчика означает совпадение адреса и категории, а не объекта. Оно засчитывается, только "
     f"если одно из имён в «Яндекс: название» совпадает с именем объекта (сходство ≥ {NAME_MIN:.0f})."),
    ("Яндекс: наша проверка", "Запрос «название, город, адрес» с картой по координате объекта. Есть — организация с похожим именем "
     f"в пределах {y.NEAR_M:.0f} м ({y.GENERIC_M:.0f} м для безымянной вывески). Закрыт — Яндекс пишет «Больше не работает»; "
     "не засчитывается. Не опознан — по адресу кто-то есть, но безымянная вывеска не позволяет сказать кто. "
     "Пусто — объект не запрашивался (его вердикт не зависел от Яндекса)."),
    ("ЕГАИС", "Реестр лицензий ФСРАР (снимок 2026-07-01). Засчитывается только действующая лицензия общепита у самого объекта: "
     "адрес проходит оба порога licmatch и имя совпадает с владельцем или с названием заведения в адресе лицензии. "
     "Один адрес без имени не засчитывается (ТЦ, гостиницы, фудкорты). Колонки «ЕГАИС: лицензия / владелец» у неподтверждённых "
     "объектов описывают лицензию, о которой говорит пояснение, — читайте «Подтверждено», а не наличие номера."),
    ("Overture", "Открытый слой мест Overture Maps (снимок релиза в data/raw_alter_overture). Засчитывается место с похожим "
     f"(сходство ≥ {OV_NAME_MIN:.0f}) именем в пределах {y.NEAR_M:.0f} м ({y.GENERIC_M:.0f} м для безымянной вывески) и уверенностью Overture ≥ {OV_CONF_MIN}. "
     "Записи Meta — страницы Facebook, в России не обновляются с 2022 г.: это слабее, чем сайт сети (AllThePlaces). "
     "Место Overture, собранное только из Foursquare, засчитывается как Foursquare, а не как второй источник. "
     "Одна запись Overture или Foursquare подтверждает одну точку: если на неё претендуют несколько объектов, она достаётся "
     f"ближайшему и объектам в пределах {RELINK_M:.0f} м от него (дубли выгрузки), остальным — нет (колонки «… пояснение»)."),
    ("Foursquare", "Foursquare OS Places напрямую (снимок релиза в data/raw_alter_foursquare). Сопоставление как у Overture "
     f"(сходство имени ≥ {FSQ_NAME_MIN:.0f}). Засчитывается только запись, обновлённая с {FSQ_FRESH[:4]} г. и без даты закрытия: "
     "большинство записей по этим городам не обновлялось с 2013–2016 гг. и говорит лишь о том, что объект был тогда. "
     "Старые и закрытые совпадения показаны в «Основаниях» после « || » и в колонке «Foursquare: пояснение»."),
    ("Общепит?", "Похож ли объект на общепит, по описаниям, которые не зависят от класса выгрузки: описание 2GIS после запятой "
     "в названии (или само название), рубрика Яндекса у той же карточки, категория Foursquare, категория Overture. "
     "да — все высказавшиеся источники за общепит; нет — все против (магазин, компания, проектная организация, опт, гостиница…); "
     "противоречие — источники расходятся (фирменный магазин пекарни, кафе при гостинице); автомат — кофейный или иной автомат; "
     "нет данных — по имени и источникам вид не определить. Это пометка для отбраковки, а не удаление: "
     "«нет» и «противоречие» стоит просмотреть, колонка «Общепит: основания» показывает, кто что сказал."),
    ("Чего нельзя утверждать", "Подтверждено = 1 не означает, что объект работает сегодня и что он относится к этому типу. "
     "Подтверждено = 0 не означает, что объекта нет: это очередь для ручной проверки. Яндекс-проверка — снимок на дату в колонке."),
]


def write_xlsx(src: Path, dst: Path, rows: pd.DataFrame, summary: list[tuple[str, object]]) -> None:
    """Copy `src` to `dst` with «Подтверждено» and «Основания» in front, details appended.

    Edited with openpyxl so the contractor's formatting, freeze panes and other
    sheets survive.  The header of `data` is checked against what pandas read,
    which is what keeps the row order honest.
    """
    wb = openpyxl.load_workbook(src)
    ws = wb[DATA_SHEET]
    header = [c.value for c in ws[1]]
    expected = [c for c in rows.columns if not c.startswith("_") and c not in
                {"entity", "site_key"} | {k for _, k in APPENDED} | {k for _, k, _ in FRONT}]
    if header != expected:
        raise RuntimeError(f"{src.name}: header changed between reads")
    if ws.max_row - 1 != len(rows):
        raise RuntimeError(f"{src.name}: {ws.max_row - 1} rows on sheet, {len(rows)} read")

    style_src = ws.cell(1, 1)
    widths = {k: v.width for k, v in ws.column_dimensions.items()}
    ncol = ws.max_column
    nfront = len(FRONT)
    ws.insert_cols(1, nfront)
    for k, w in sorted(widths.items(), key=lambda kv: -openpyxl.utils.column_index_from_string(kv[0])):
        col = openpyxl.utils.column_index_from_string(k)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col + nfront)].width = w

    def put_header(col: int, text: str, width: float) -> None:
        c = ws.cell(1, col, text)
        c.font, c.fill, c.alignment, c.border = (copy(style_src.font), copy(style_src.fill),
                                                 copy(style_src.alignment), copy(style_src.border))
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    for j, (title, _, width) in enumerate(FRONT, start=1):
        put_header(j, title, width)
    first_new = ncol + nfront + 1
    for j, (title, _) in enumerate(APPENDED):
        put_header(first_new + j, title, 22 if "ссылк" not in title else 30)
    for i, (_, r) in enumerate(rows.iterrows(), start=2):
        ws.cell(i, 1, int(r["confirmed"]))
        ws.cell(i, 2, r["reasons"]).alignment = openpyxl.styles.Alignment(wrap_text=False)
        for j, (_, key) in enumerate(APPENDED):
            v = r[key]
            if isinstance(v, (np.integer, np.bool_)):
                v = int(v)
            elif isinstance(v, np.floating):
                v = float(v)
            ws.cell(i, first_new + j, None if v == "" else v)
    last = openpyxl.utils.get_column_letter(first_new + len(APPENDED) - 1)
    ws.auto_filter.ref = f"A1:{last}{ws.max_row}"

    if "Подтверждение" in wb.sheetnames:
        del wb["Подтверждение"]
    lg = wb.create_sheet("Подтверждение", 1)
    lg.column_dimensions["A"].width, lg.column_dimensions["B"].width = 26, 120
    lg.append(["Как читать", ""])
    for k, v in LEGEND:
        lg.append([k, v])
    lg.append([])
    lg.append(["Итоги", ""])
    for k, v in summary:
        lg.append([k, v])
    for row in lg.iter_rows():
        row[0].font = openpyxl.styles.Font(bold=True)
        if len(row) > 1:
            row[1].alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")
    dst.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dst)


def summarise(ob: pd.DataFrame, rows: pd.DataFrame) -> list[tuple[str, object]]:
    """The few numbers a reader of one file needs, in the file itself."""
    n = len(ob)
    out = [
        ("Строк", len(rows)),
        ("Объектов (уникальных вывесок в точке)", n),
        ("Подтверждено объектов", f"{ob['confirmed'].sum()} из {n} ({ob['confirmed'].mean():.1%})"),
        ("Подтверждено строк", f"{rows['confirmed'].sum()} из {len(rows)}"),
        ("— из них только OSM + 2GIS подрядчика", int(((ob['osm'] & ob['gis'])).sum())),
        ("— добавлено склейкой соседних записей", int((ob['confirmed'].astype(bool) & ~(ob['osm'] & ob['gis'])
                                                      & (ob['osm_link'] | ob['gis_link'])).sum())),
        ("— добавлено Яндексом", int((ob['confirmed'].astype(bool) & ob['src_yandex']
                                      & ((ob['src_osm'].astype(int) + ob['src_gis'].astype(int)
                                          + ob['src_arkh'].astype(int)) < MIN_SOURCES)).sum())),
        ("«Найдено» подрядчика, отклонено по имени (объектов)",
         int((ob['ya_contractor_raw'] & ~ob['ya_contractor']).sum())),
        ("Наша Яндекс-проверка: запрошено объектов", int(ob['ya_status'].ne("").sum())),
    ]
    for st in y.STATUS_ORDER:
        out.append((f"   {st}", int(ob['ya_status'].eq(st).sum())))
    out.append(("Найдено в Overture (объектов)", int(ob["ov_match"].sum())))
    out.append(("Foursquare: засчитано / найдено, но старое или закрыто (объектов)",
                f"{int(ob['src_fsq'].sum())} / {int((ob['fsq_name'].ne('') & ~ob['src_fsq']).sum())}"))
    for k in ("да", "нет", "противоречие", "автомат", "нет данных"):
        out.append((f"Общепит? — {k} (объектов)", int(ob["food"].eq(k).sum())))
    out.append(("Своя лицензия общепита в ЕГАИС (объектов)", int(ob["src_egais"].sum())))
    out.append(("Подтверждено, но Яндекс пишет «закрыт»", int((ob['confirmed'].astype(bool) & ob['ya_closed']).sum())))
    out.append(("Не запрошено, хотя вердикт зависит от Яндекса",
                int((needs_yandex(ob) & ob['ya_status'].eq("")).sum())))
    return out


def to_rows(df: pd.DataFrame, ob: pd.DataFrame) -> pd.DataFrame:
    """Broadcast the object verdict back onto every row of the export."""
    cols = [k for _, k, _ in FRONT] + [k for _, k in APPENDED if k not in ("entity",)]
    return df.join(ob[cols], on="entity")
