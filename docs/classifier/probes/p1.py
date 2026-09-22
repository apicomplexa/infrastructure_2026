import sys, io, hashlib
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd, numpy as np
from arkhinfra import paths

out = io.StringIO()
def P(*a):
    print(*a, file=out)

RAW4 = paths.RAW4
ALL = RAW4 / "infrastructure_архангельск_2026-08-31_quality_excel_all.csv"
TOB = paths.V4_TOBACCO
ALC = paths.V4_ALCOHOL
CAT = RAW4 / "infrastructure_архангельск_2026-09-05_quality_excelобщепит.csv"
GRO = RAW4 / "infrastructure_архангельск_2026-09-05_quality_excelпродуктовые магазины.csv"

def rd(p):
    return pd.read_csv(p, sep=";", encoding="utf-8-sig", low_memory=False)

alld = rd(ALL)
P("=== _all.csv ===", alld.shape)
P("cols:", list(alld.columns))
P("md5 all :", hashlib.md5(ALL.read_bytes()).hexdigest())
P("md5 v3  :", hashlib.md5(paths.V3_CSV.read_bytes()).hexdigest())

layers = {"tobacco": TOB, "alcohol": ALC, "catering": CAT, "grocery": GRO}
L = {k: rd(v) for k, v in layers.items()}
for k, d in L.items():
    P(f"--- {k}: {d.shape}")
    P("   category_orig:", d["category_orig"].value_counts().to_dict())
    P("   type_orig:", d["type_orig"].value_counts().to_dict())

# coordinate overlap with _all.csv
def key(df):
    return set(zip(df["latitude"].round(6), df["longitude"].round(6)))
allk = key(alld)
P("\n=== coordinate overlap with _all.csv (exact, rounded 6dp) ===")
for k, d in L.items():
    kk = key(d)
    inter = kk & allk
    P(f"{k}: rows {len(d)}, distinct coords {len(kk)}, in _all {len(inter)} "
      f"= {100*len(inter)/len(kk):.1f}% of distinct; row-level "
      f"{d.apply(lambda r: (round(r['latitude'],6), round(r['longitude'],6)) in allk, axis=1).sum()}/{len(d)}")

# union of layers
uni = set()
for d in L.values():
    uni |= key(d)
P("union distinct coords over 4 layers:", len(uni), "landing in _all:", len(uni & allk))
P("share of _all tagged by any layer:", len(uni & allk), "/", len(allk), "=", f"{100*len(uni&allk)/len(allk):.1f}%")
P("n distinct coords in _all:", len(allk), " rows:", len(alld))

# grocery breakdown of the non-matching coords
g = L["grocery"]
g["inall"] = [ (round(a,6), round(b,6)) in allk for a,b in zip(g["latitude"], g["longitude"]) ]
P("\ngrocery not-in-all by type_orig:")
P(g.loc[~g["inall"], "type_orig"].value_counts().to_dict())
P("grocery distinct coords not in all:", len(key(g[~g['inall']]) - allk))

Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p1.txt").write_text(out.getvalue(), encoding="utf-8")
