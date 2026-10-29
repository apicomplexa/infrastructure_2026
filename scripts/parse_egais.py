"""Reduce the FSRAR consolidated licence registry to the Arkhangelsk rows.

The published XML is ~10.9 GB, so it is never held in memory: the file is read
in binary chunks and cut on the ``</row>`` boundary, and only the segments whose
raw bytes already mention "Архангельск" are handed to the XML parser.  That is a
memchr-speed substring test over the whole file and a real parse over a few
thousand records.

Note the published data does *not* follow its own XSD: the schema describes
``Details/Detail`` with attributes, the file delivers ``data/row`` with child
elements, and several element names differ from the schema (the registry's own
"выезного" typo among them).  The map below follows the file.

The registry is published as a ZIP holding that one XML.  Either is accepted:
a member of a ZIP is read through `zipfile`'s decompressing stream, so the
archive never has to be unpacked to disk, at the cost of ~1 minute of inflate.

`--settlements` swaps the city filter for a list of settlements (the final
delivery covers Архангельск, Северодвинск and Новодвинск) and writes a separate
file, EGAIS_FINAL_TSV; the default run, and the TSV the v4 join reads, are
unchanged.

Usage:  pixi run parse-egais [--scope city|oblast] [--limit N] [--src PATH]
        pixi run parse-egais-final   # --settlements архангельск северодвинск новодвинск
"""
from __future__ import annotations

import argparse
import re
import zipfile
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import paths  # noqa: E402

CHUNK = 16 << 20  # 16 MiB

# Case variants of "рхангельск" without the leading letter, so one pass catches
# "Архангельск", "архангельск" and "АРХАНГЕЛЬСК" alike.
NEEDLES = ("рхангельск".encode(), "РХАНГЕЛЬСК".encode())

# Element name in the file -> column name in the TSV.  Anything not listed is
# dropped; История_изменений_сведений_о_действии_лицензии is the big one, and
# dropping it is most of what makes the output compact.
FIELDS = {
    "Полное_и_сокращенное_наименование_организации_сельскохозяйственного_товаропроизводителя_с_указанием_ее_ОПФ": "org_name",
    "ИНН_организации_сельскохозяйственного_товаропроизводителя_": "org_inn",
    "КПП_организации_сельскохозяйственного_товаропроизводителя_": "org_kpp",
    "Адрес__место_нахождения___организации_сельскохозяйственного_товаропроизводителя_": "org_address",
    "Адрес_электронной_почты_организации_сельскохозяйственного_товаропроизводителя_": "org_email",
    "Место_нахождения__адрес__обособленного_подразделения_организации__осуществляющего_лицензируемый_вид_деятельности": "outlet_address",
    "КПП_обособленного_подразделения_организации__осуществляющего_лицензируемый_вид_деятельности": "outlet_kpp",
    "Код_субъекта_Российской_Федерации_по_месту_нахождения_организации": "org_region_code",
    "Код_субъекта_РФ_по_месту_нахождения_обособленного_подразделения_организации__осуществляющего_лицензируемый_вид_деятельности": "outlet_region_code",
    "Вид_лицензируемой_деятельности_организации": "activity",
    "Виды_продукции": "products",
    "Номер_лицензии__соответствующий_номеру_записи_в_реестре": "licence_no",
    "Номер_ранее_выданной_лицензии": "licence_prev_no",
    "Дата_выдачи_лицензии": "date_issued",
    "Дата_окончания_действия_лицензии": "date_expires",
    "Сведения_о_действии_лицензии": "status",
    "Дата_изменения_сведений_о_действии_лицензии": "status_changed",
    "Основание_изменения_сведений_о_действии_лицензии": "status_reason",
    "Орган_выдавший_лицензию": "issuing_body",
    "Координаты": "coords_raw",
}

# Present in the file, deliberately not carried over.
IGNORED = {
    "История_изменений_сведений_о_действии_лицензии",
    "Номер_бланка",
    "Дата__время_и_место_выезного_обслуживания",
    "Дата__время_и_место_выездного_обслуживания",
    "Уточненные_сведения_о_выездном_обслуживании",
    "Дата_внесения_изменений_в_сведения_о_лицензии_по_судебным_актам_и_актам_других_органов",
}

COLUMNS = [
    "licence_no", "licence_prev_no", "status", "date_issued", "date_expires",
    "status_changed", "status_reason", "activity", "products",
    "org_name", "org_inn", "org_kpp", "org_email", "org_address",
    "org_region_code", "outlet_region_code", "outlet_address",
    "outlet_settlement", "outlet_subsettlement", "outlet_street",
    "outlet_house", "outlet_kpp", "lat", "lon", "coord_plausible",
    "coords_raw", "issuing_body",
]

# Generous box around the city, used only to flag the registry's own coordinate
# typos (dropped degrees, transposed digits) — the values are kept either way.
BBOX = (64.40, 64.75, 40.30, 40.90)  # lat_min, lat_max, lon_min, lon_max
# The same, per settlement, for a `--settlements` run: each row is checked
# against the box of its own settlement.  A settlement missing here gets no
# `coord_plausible` verdict, and `egais.load_egais()` then drops its coordinate.
BOXES = {
    "архангельск": BBOX,
    "северодвинск": (64.45, 64.70, 39.40, 40.20),
    "новодвинск": (64.35, 64.47, 40.65, 41.00),
}

# A settlement token as the registry writes it: "Архангельск Город", "Талаги
# Деревня", occasionally "г Архангельск".  Matching whole tokens is what keeps
# "Архангельская Область" out of a city filter.
_TYPES = r"город|г|пгт|рп|пос|поселок|посёлок|п|село|с|деревня|д|станция|ст|снт|мкр"
_SETTLEMENT = re.compile(
    rf"^(?:(?P<t1>{_TYPES})\.?\s+(?P<n1>.+)|(?P<n2>.+?)\s+(?P<t2>{_TYPES})\.?)$", re.I
)
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
# Region-level words, so a region never gets read as the settlement.
_REGIONISH = re.compile(r"\b(обл|область|край|респ|республика|ао|округ\s+автономный|автономный)\b", re.I)
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def settlement_name(token: str) -> str:
    """"Архангельск Город" -> "архангельск"; anything unparsed comes back as-is."""
    m = _SETTLEMENT.match(token.strip())
    if not m:
        return token.strip().lower()
    return (m.group("n1") or m.group("n2") or "").strip().lower()


def split_address(addr: str) -> tuple[str, str, str, str]:
    """(settlement, subsettlement, street, house) from the comma-packed address.

    The layout is positional and stable across the registry:

        0 country, 2 region, 4 settlement, 5 subsettlement, 6 street, 7 house

    with the tail (8+) holding free-form premises text.  Position is what a bare
    "Архангельск" needs — it carries no type word, so a type-word search walks
    past it and latches onto the house number "д. 120" instead.  The type-word
    search stays as the fallback for the rare row with a shifted layout.
    """
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) > 4 and parts[4] and not _REGIONISH.search(parts[4]):
        sub = parts[5] if len(parts) > 5 else ""
        street = parts[6] if len(parts) > 6 else ""
        house = parts[7] if len(parts) > 7 else ""
        return parts[4], sub, street, house

    # Shifted layout (a region word sitting in the settlement slot, or an empty
    # one): fall back to hunting the type word.  The name must contain a letter,
    # or the single-letter types д/с/п match a house number such as "д. 120".
    for i, p in enumerate(parts):
        if not p or p.lower() == "россия" or _REGIONISH.search(p):
            continue
        m = _SETTLEMENT.match(p)
        name = (m.group("n1") or m.group("n2") or "") if m else ""
        if name and _HAS_LETTER.search(name):
            rest = [q for q in parts[i + 1:] if q]
            return p, "", (rest[0] if rest else ""), (rest[1] if len(rest) > 1 else "")
    return "", "", "", ""


def in_arkhangelsk_city(addr: str) -> bool:
    """True when the settlement slot names the city itself.

    Checked on the settlement slot rather than the whole string, so neither
    "Архангельская Область" nor a street called "Архангельская" can pull a
    record in.  ``outlet_region_code`` is *not* used: the registry leaves it
    wrong on ~4 % of Arkhangelsk rows.
    """
    return settlement_name(split_address(addr)[0]) == "архангельск"


def needles_for(names: list[str]) -> tuple[bytes, ...]:
    """Byte needles for a settlement list, as NEEDLES is for the one city.

    The first letter is dropped so one needle catches the capitalised and the
    lower-case spelling, and an upper-case one catches the shouted form.
    """
    out: list[bytes] = []
    for n in names:
        stem = n.strip().lower()[1:]
        out += [stem.encode(), stem.upper().encode()]
    return tuple(out)


def open_source(src: Path):
    """(binary stream, uncompressed size) for the XML or a ZIP holding it."""
    if src.suffix.lower() != ".zip":
        return src.open("rb"), src.stat().st_size
    zf = zipfile.ZipFile(src)
    xml = [i for i in zf.infolist() if i.filename.lower().endswith(".xml")]
    if len(xml) != 1:
        raise ValueError(f"{src}: expected one .xml member, found {len(xml)}")
    return zf.open(xml[0]), xml[0].file_size


def parse_coords(raw: str) -> tuple[str, str]:
    """"Широта - 64° 32' 22''; Долгота - 40° 32' 5''" -> ("64.539444", "40.534722")."""
    if not raw or "Широта" not in raw:
        return "", ""
    lat_part, _, lon_part = raw.partition(";")
    out = []
    for part in (lat_part, lon_part):
        nums = [float(n.replace(",", ".")) for n in _NUM.findall(part)]
        if not nums:
            out.append("")
            continue
        deg = nums[0]
        if len(nums) >= 3:
            deg += nums[1] / 60 + nums[2] / 3600
        elif len(nums) == 2:
            deg += nums[1] / 60
        out.append(f"{deg:.6f}")
    return out[0], (out[1] if len(out) > 1 else "")


def clean(v: str | None) -> str:
    """TSV-safe: no tabs, no newlines, no doubled spaces."""
    return " ".join((v or "").split())


def row_to_record(xml: bytes, unknown: set[str]) -> dict[str, str]:
    rec: dict[str, str] = {}
    for child in ET.fromstring(xml):
        col = FIELDS.get(child.tag)
        if col is None:
            if child.tag not in IGNORED:
                unknown.add(child.tag)
            continue
        val = clean(child.text)
        # A few tags repeat inside one row (licence_prev_no does); first
        # non-empty value wins.
        if val and not rec.get(col):
            rec[col] = val
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scope", choices=("city", "oblast"), default="city",
                    help="city: outlet address in Arkhangelsk city (default); "
                         "oblast: every row mentioning Arkhangelsk anywhere.")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N kept rows (smoke test)")
    ap.add_argument("--settlements", nargs="+", default=None, metavar="NAME",
                    help="keep rows whose outlet settlement is one of these "
                         "(lower case, e.g. архангельск северодвинск); "
                         "overrides --scope and writes EGAIS_FINAL_TSV")
    ap.add_argument("--src", type=Path, default=None,
                    help="the registry XML, or the ZIP holding it "
                         "(default: the XML if unpacked, else the ZIP)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    src = args.src or (paths.EGAIS_XML if paths.EGAIS_XML.exists() else paths.EGAIS_ZIP)
    if not src.exists():
        raise FileNotFoundError(src)
    keep_names = {s.strip().lower() for s in args.settlements} if args.settlements else None
    needles = needles_for(sorted(keep_names)) if keep_names else NEEDLES
    if keep_names:
        out = args.out or paths.EGAIS_FINAL_TSV
    else:
        out = args.out or (paths.EGAIS_TSV if args.scope == "city"
                           else paths.PROC_EGAIS / "egais_licences_arkhangelsk_oblast.tsv")
    out.parent.mkdir(parents=True, exist_ok=True)

    def keep(rec: dict[str, str]) -> bool:
        addr = rec.get("outlet_address", "")
        if keep_names:
            return settlement_name(split_address(addr)[0]) in keep_names
        return args.scope == "oblast" or in_arkhangelsk_city(addr)

    fh, total = open_source(src)
    unknown: set[str] = set()
    records: list[dict[str, str]] = []
    n_rows = n_hits = read = next_report = 0
    buf = b""

    with fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            read += len(chunk)
            segments = (buf + chunk).split(b"</row>")
            buf = segments.pop()
            for seg in segments:
                n_rows += 1
                if not any(n in seg for n in needles):
                    continue
                start = seg.find(b"<row>")
                if start < 0:
                    continue
                n_hits += 1
                rec = row_to_record(seg[start:] + b"</row>", unknown)
                if keep(rec):
                    records.append(rec)
            if read >= next_report:
                print(f"  {read / 1e9:6.2f} / {total / 1e9:.2f} GB "
                      f"({100 * read / total:5.1f}%)  rows {n_rows:,}  "
                      f"hits {n_hits:,}  kept {len(records):,}",
                      file=sys.stderr, flush=True)
                next_report = read + (1 << 30)
            if args.limit and len(records) >= args.limit:
                break

    for rec in records:
        addr = rec.get("outlet_address", "")
        (rec["outlet_settlement"], rec["outlet_subsettlement"],
         rec["outlet_street"], rec["outlet_house"]) = split_address(addr)
        lat, lon = parse_coords(rec.get("coords_raw", ""))
        rec["lat"], rec["lon"] = lat, lon
        box = BOXES.get(settlement_name(rec["outlet_settlement"])) if keep_names else BBOX
        if lat and lon and box:
            lo_a, hi_a, lo_o, hi_o = box
            rec["coord_plausible"] = str(lo_a <= float(lat) <= hi_a and lo_o <= float(lon) <= hi_o).lower()

    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(COLUMNS) + "\n")
        for rec in records:
            fh.write("\t".join(rec.get(c, "") for c in COLUMNS) + "\n")

    print(f"\nrows scanned        {n_rows:,}", file=sys.stderr)
    print(f"needle hits         {n_hits:,}", file=sys.stderr)
    scope = "settlements " + ",".join(sorted(keep_names)) if keep_names else args.scope
    print(f"written ({scope})  {len(records):,} -> {out}", file=sys.stderr)
    if unknown:
        print("unmapped elements (dropped): " + ", ".join(sorted(unknown)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
