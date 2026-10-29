"""Shared loaders and recoding rules for the third delivery (data/raw_v3).

Both analysis/v3/eda-v3.qmd and analysis/v3/eda-v3-validation.qmd import this module so
the two reports cannot drift apart.  (The v1/v2 reports each carry their own copy
of recode_2022(); the copy here is rule-for-rule identical to the one in
analysis/v1/eda.qmd -- keep all three in sync.)
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Re-exported so existing report code keeps using c.RAW3 / c.V3_CSV unchanged;
# arkhinfra.paths is the single definition.
from .paths import (  # noqa: F401
    ROOT, RAW, RAW2, RAW3, PROC, PROC_MATCH_2022,
    V3_CSV, V3_BASE, V3_ARK, V2_ARK, V2_CMP, V1_CSV, REF_2022,
)

# The three okrugs the 2022 study covered.  2022 spells them without the
# "округ" suffix and with inconsistent case (Майская Горка / Майская горка).
OKRUGS_2022 = ["Lomonosovsky", "Oktyabrsky", "Maiskaya Gorka"]

# House palette, shared with eda.qmd / eda-v2.qmd so deliveries stay comparable.
# Validated for CVD separation against the report surface (worst adjacent pair
# ΔE 8.3 protan / 21.9 normal), so every categorical chart also carries direct
# labels or a legend rather than relying on hue alone.
ACCENT = "#2b6cb0"   # health-supporting / neutral primary
RISK = "#c05621"     # risk factors
GREEN = "#2f855a"    # confirmed / third series
PURPLE = "#6b21a8"   # fourth series
MIXED = "#6b7280"
OLD = "#a0aec0"      # previous deliveries, for before/after comparisons


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------
def load_v3() -> pd.DataFrame:
    """The third-delivery quality export (7,263 x 22)."""
    df = pd.read_csv(V3_CSV, sep=";", encoding="utf-8-sig", low_memory=False)
    df["category_2022"] = recode_2022(df)
    df["okrug_key"] = df["district_orig"].map(norm_okrug)
    return df


def load_v1() -> pd.DataFrame:
    """The first delivery, used as the 'before' baseline."""
    df = pd.read_csv(V1_CSV, sep=";", encoding="utf-8-sig", low_memory=False)
    df["category_2022"] = recode_2022(df)
    df["okrug_key"] = df["district_orig"].map(norm_okrug)
    return df


def load_ref_2022_local() -> pd.DataFrame:
    """Etalon A -- the 2022 object list held in this repo (1,753 rows)."""
    df = pd.read_excel(REF_2022)
    df["okrug_key"] = df["district_orig"].map(norm_okrug)
    df["category_2022"] = recode_2022(df)
    return df


def load_ref_2022_vendor() -> pd.DataFrame:
    """Etalon B -- the 2022 document as the contractor shipped it inside the v2
    comparison workbook (2,293 rows).  Its columns are prefixed with a
    "Документ 1: " tag which is stripped here."""
    d = pd.read_excel(V2_CMP, sheet_name="Документ 1 с результатом")
    d = d.rename(columns={c: re.sub(r"^Документ 1:\s*", "", str(c)) for c in d.columns})
    if "district_orig" in d.columns:
        d["okrug_key"] = d["district_orig"].map(norm_okrug)
    if {"category_orig", "type_orig", "name_orig"} <= set(d.columns):
        d["category_2022"] = recode_2022(d)
    return d


_MINIMAL_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
    "</styleSheet>"
).encode("utf-8")


def load_export_base() -> pd.DataFrame:
    """The commercial directory dump shipped with the third delivery.

    openpyxl refuses this workbook -- its styles.xml carries a fill entry that
    fails openpyxl's own type check.  Nothing in the analysis needs cell
    styling, so the file is re-zipped in memory with a minimal stylesheet before
    parsing.  Row 1 of the data repeats the header labels and is dropped, so the
    frame holds 10,557 records rather than the sheet's 10,558 rows.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(V3_BASE) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = _MINIMAL_STYLES if item.filename == "xl/styles.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    buf.seek(0)
    d = pd.read_excel(buf)
    # One header cell ("Район города") is stored in decomposed form -- и + a
    # combining breve rather than a precomposed й -- so a plain d["Район города"]
    # raises KeyError.  Normalising the header to NFC makes every column
    # reachable by its printed name.  The data cells are already NFC.
    d.columns = [unicodedata.normalize("NFC", str(col)) for col in d.columns]
    d = d[d["Город"] != "Город"].reset_index(drop=True)
    # Despite the column's name the pair is space-separated, and both members
    # are rounded to three decimals -- roughly +-55 m here at 64.5 N.  That is
    # coarser than the 50 m matching radius, so these coordinates support
    # neighbourhood-level work only, never record-level GPS matching.
    coords = (d["Координаты (широта, долгота)"].astype(str)
              .str.strip().str.split(r"[\s,]+", n=1, expand=True, regex=True))
    d["latitude"] = pd.to_numeric(coords[0], errors="coerce")
    d["longitude"] = pd.to_numeric(coords[1], errors="coerce") if coords.shape[1] > 1 else np.nan
    return d


def load_arktmed(path: Path | None = None) -> dict:
    x = pd.ExcelFile(path or V3_ARK)
    return {s: x.parse(s) for s in x.sheet_names}


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------
_OKRUG_TABLE = {
    "ломоносовский": "Lomonosovsky",
    "октябрьский": "Oktyabrsky",
    "майская горка": "Maiskaya Gorka",
    "соломбальский": "Solombalsky",
    "варавино-фактория": "Varavino-Faktoriya",
    "исакогорский": "Isakogorsky",
    "цигломенский": "Tsiglomensky",
    "северный": "Severny",
    "маймаксанский": "Maimaksansky",
}


def norm_okrug(v) -> str:
    """Fold okrug spellings from 2022, v1 and v3 onto one key.

    v1 additionally merges Isakogorsky and Tsiglomensky into a single okrug;
    that pair keeps its own key so the merge stays visible in comparisons.
    """
    if pd.isna(v):
        return "Unknown"
    s = str(v).strip().lower().replace(chr(0x451), "е")
    s = re.sub(r"\bокруга?\b", "", s).strip()
    if "исакогорск" in s and "цигломен" in s:
        return "Isakogorsky+Tsiglomensky (merged)"
    return _OKRUG_TABLE.get(s, str(v).strip())


# Legal forms and generic nouns carry no identifying signal and only inflate
# similarity between unrelated records, so they are dropped before comparison.
_TOKEN_DROP = {
    "ооо", "оао", "зао", "ао", "ип", "пао", "нко", "мбу", "мбоу", "гбуз", "фгбоу",
    "магазин", "компания", "фирма", "сеть", "супермаркет", "тц", "тк",
}

_QUOTES = "[" + chr(0xAB) + chr(0xBB) + chr(0x22) + chr(0x27) + chr(0x60) + "]"


def norm_name(v) -> str:
    """Casefold, strip quotes / legal forms / punctuation, collapse whitespace."""
    if pd.isna(v):
        return ""
    s = str(v).lower().replace(chr(0x451), "е")
    s = re.sub(_QUOTES, " ", s)
    s = re.sub(r"[^0-9a-zа-я]+", " ", s)
    return " ".join(t for t in s.split() if t not in _TOKEN_DROP).strip()


_STREET_WORDS = (r"(?:улица|ул|проспект|пр|пр-кт|переулок|пер|набережная|наб|"
                 r"шоссе|ш|площадь|пл|проезд|бульвар|б-р|тракт)")


def norm_address(v) -> str:
    """Reduce an address to a comparable 'street housenumber' token string."""
    if pd.isna(v):
        return ""
    s = str(v).lower().replace(chr(0x451), "е")
    s = re.sub(r"^\s*\d{6}\s*", " ", s)            # postal index
    s = re.sub(r"\bархангельск\b,?", " ", s)       # city name
    s = re.sub(_QUOTES, " ", s)
    s = re.sub(r"\b" + _STREET_WORDS + r"\b\.?", " ", s)
    s = re.sub(r"\b(?:дом|д|корпус|корп|к|строение|стр|ст|литера|лит)\b\.?", " ", s)
    s = re.sub(r"[^0-9a-zа-я]+", " ", s)
    return " ".join(s.split()).strip()


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres, vectorised over numpy arrays."""
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------
# 2022 taxonomy
# --------------------------------------------------------------------------
# Stored lowercased on purpose.  recode_2022() lowercases type_orig before the
# membership test, so the copy of this set in analysis/v1/eda.qmd -- which is
# capitalised -- can never match and silently empties the Grocery shops class.
# That defect is live in the v1 and v2 reports; see the "Recoding" section of
# analysis/v3/eda-v3.qmd for what it costs (846 objects here, 392 in the 2022
# benchmark).  Fixed here rather than replicated.
GROCERY_TYPES = {
    "продуктовый магазин", "супермаркет", "фрукты-овощи", "булочная",
    "кулинария", "мясной магазин", "рыбный магазин", "молочный магазин",
    "гипермаркет", "продукты",
}


def _has(series: pd.Series, *subs: str) -> pd.Series:
    out = pd.Series(False, index=series.index)
    for sub in subs:
        out |= series.str.contains(sub, na=False, regex=False)
    return out


def recode_2022(df: pd.DataFrame) -> pd.Series:
    """Map objects onto the 2022 taxonomy using category + type + name."""
    cat = df["category_orig"].fillna("").astype(str)
    t = df["type_orig"].fillna("").astype(str).str.lower()
    blob = (cat.str.lower() + " | " + t + " | "
            + df["name_orig"].fillna("").astype(str).str.lower())

    tobacco = (cat == "Точки продажи табака") | _has(blob, "табак", "вейп", "сигарет", "кальян", "vape")
    alcohol = _has(t, "алкогол") | _has(blob, "алкомаркет", "винотек") | (_has(t, "винный") & _has(t, "магазин"))
    medical = (cat == "Медицинские организации") | _has(
        blob, "аптек", "поликлин", "больниц", "стоматолог", "клиник", "врач",
        "диагност", "лаборатор", "диспансер", "госпит", "медиц", "оптика",
        "реабилит", "санатор", "профилакт", "роддом", "родильн", "фельдшер")
    sport = (cat == "Спортивные объекты") | _has(
        blob, "спорт", "фитнес", "бассейн", "стадион", "тренаж", "воркаут",
        "каток", "манеж", "йога") | _has(t, "парк", "сквер", "набережн")
    catering = cat.isin(["Общепит", "фастфуд"]) | _has(
        t, "кафе", "фастфуд", "бар", "ресторан", "паб", "кофейн", "столов",
        "закусочн", "пиццери", "суши", "бистро")
    grocery = t.isin(GROCERY_TYPES)
    industrial = _has(blob, "завод", "энергокомплекс", "тэц", "гэс", "фабрика", "промышл", "комбинат")

    return pd.Series(np.select(
        [tobacco, alcohol, medical, sport, catering, grocery, industrial],
        ["Tobacco outlets", "Alcohol shops", "Medical", "Sport", "Catering",
         "Grocery shops", "Industrial"],
        default="Other (outside 2022 scheme)"), index=df.index)


CLASS_ORDER = ["Medical", "Sport", "Grocery shops", "Catering",
               "Alcohol shops", "Tobacco outlets", "Industrial",
               "Other (outside 2022 scheme)"]
HEALTH_CLASSES = ["Medical", "Sport"]
RISK_CLASSES = ["Alcohol shops", "Tobacco outlets", "Industrial"]

CATEGORY_EN = {
    "Магазины": "Shops", "Организации": "Organisations",
    "Медицинские организации": "Medical organisations", "Услуги": "Services",
    "Общепит": "Catering", "Образование": "Education",
    "Спортивные объекты": "Sport facilities",
    "Государственные организации": "Government organisations",
    "фастфуд": "Fast food", "Почта и связь": "Post & telecom",
    "Финансовые организации": "Financial organisations", "Авто": "Automotive",
    "Досуг и спорт": "Leisure & sport", "Культура": "Culture",
    "Точки продажи табака": "Tobacco outlets",
    "Гостиницы и туризм": "Hotels & tourism",
    "Реабилитация и профилактика": "Rehabilitation & prevention",
    "Досуг": "Leisure", "Спецмагазины алкоголя": "Alcohol shops",
    "Пром. Объекты": "Industrial objects",
}

STATUS_EN = {
    "confirmed_by_2gis_and_osm": "Confirmed by 2GIS + OSM",
    "only_osm": "OSM only",
    "only_2gis": "2GIS only",
}

SECTION_EN = {
    "Климат": "Climate", "Демография": "Demography", "Экономика": "Economy",
    "Инфраструктура": "Infrastructure", "Медицина": "Healthcare",
    "Экология": "Environment", "Здоровье": "Health",
}
