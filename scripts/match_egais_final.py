"""Check the final delivery's catering objects against the FSRAR licence registry.

Reads every `data/raw_final/infrastructure_*.xlsx` (sheet `data`) and the
three-city registry extract (`pixi run parse-egais-final`), and asks of each
object whether an in-force catering licence of its own stands at its address
(`arkhinfra.final_egais.match_catering`).  The files repeat an object under
each of its types, so an object is one (city, name, latitude, longitude).

    pixi run match-egais-final

Writes `data/processed/final_egais/final_egais.csv` -- one row per object --
and `final_egais_summary.txt`.  Cyrillic on a Windows console is mangled, so
the tables go to the summary file rather than to stdout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arkhinfra import paths  # noqa: E402
from arkhinfra.final_egais import load_registry, match_catering  # noqa: E402

KEY = ["city", "name", "latitude", "longitude"]


def load_objects() -> pd.DataFrame:
    """One row per object over all final files, with a stable id."""
    frames = []
    for f in paths.final_files():
        d = pd.read_excel(f, sheet_name="data")
        d["source_file"] = f.name
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["types"] = d.groupby(KEY, dropna=False)["type"].transform(
        lambda s: "; ".join(sorted(set(s.dropna().astype(str)))))
    ob = d.drop_duplicates(KEY).reset_index(drop=True)
    ob.index = pd.Index([f"F{i:05d}" for i in range(len(ob))], name="object_id")
    return ob


def main() -> int:
    ob = load_objects()
    eg = load_registry()
    res = match_catering(pd.DataFrame({
        "city": ob["city"], "name": ob["name"].fillna("").astype(str),
        "address": ob["address"].fillna("").astype(str),
        "lat": ob["latitude"], "lon": ob["longitude"]}, index=ob.index), eg)
    out = ob[["city", "name", "address", "latitude", "longitude", "types",
              "source_file"]].join(res)

    paths.PROC_FINAL_EGAIS.mkdir(parents=True, exist_ok=True)
    csv = paths.PROC_FINAL_EGAIS / "final_egais.csv"
    out.to_csv(csv, encoding="utf-8-sig")

    at_addr = out["egais_licence_no"] != ""
    cat_addr = (at_addr & out["egais_activity"].str.contains("общепит", case=False)
                & ~out["egais_note"].str.contains("по другому адресу", regex=False))
    t = pd.DataFrame({
        "objects": out.groupby("city").size(),
        "catering licence at address (any status)": cat_addr.groupby(out["city"]).sum(),
        "egais_match": out["egais_match"].groupby(out["city"]).sum(),
    })
    t.loc["Total"] = t.sum()
    t["match %"] = (100 * t["egais_match"] / t["objects"]).round(1)
    act = eg[eg["is_active"] & (eg["activity_class"] == "Retail + on-trade")]
    hit = out[out["egais_match"]]
    used = set(zip(hit["egais_licence_no"], hit["egais_outlet_address"]))
    act = act.assign(used=[k in used for k in zip(act["licence_no"], act["outlet_address"])])
    lic = pd.DataFrame({
        "active catering outlets": act.groupby("city_key").size(),
        "confirming an object": act.groupby("city_key")["used"].sum(),
    }).astype(int)
    notes = (out.loc[~out["egais_match"] & (out["egais_note"] != ""), "egais_note"]
             .str.replace(r"\s*\(.*\)$", "", regex=True)
             .str.replace(r"«.*»", "«…»", regex=True)
             .str.replace(r"в \d+ м", "в N м", regex=True))

    with (paths.PROC_FINAL_EGAIS / "final_egais_summary.txt").open("w", encoding="utf-8") as fh:
        fh.write(f"final_egais -- catering objects vs FSRAR registry ({paths.EGAIS_FINAL_TSV.name})\n\n")
        fh.write("Objects per city\n" + t.to_string() + "\n\n")
        fh.write("Registry side (in-force catering licence rows, one per outlet address)\n"
                 + lic.to_string() + "\n\n")
        fh.write("Near-miss reasons (not confirmed, something at or near the address)\n"
                 + notes.value_counts().to_string() + "\n")
    print(f"wrote {csv} ({len(out)} objects, {int(out['egais_match'].sum())} confirmed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
