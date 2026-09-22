import sys, io
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd, numpy as np
from arkhinfra import paths
out = io.StringIO()
def P(*a): print(*a, file=out)

RAW4 = paths.RAW4
files = {
 "tobacco": paths.V4_TOBACCO, "alcohol": paths.V4_ALCOHOL,
 "catering": RAW4/"infrastructure_архангельск_2026-09-05_quality_excelобщепит.csv",
 "grocery": RAW4/"infrastructure_архангельск_2026-09-05_quality_excelпродуктовые магазины.csv"}
rd = lambda p: pd.read_csv(p, sep=";", encoding="utf-8-sig", low_memory=False)
alld = rd(RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")

K = np.cos(np.radians(64.5))*111320.0
ax = alld["longitude"].values*K; ay = alld["latitude"].values*111320.0
A = np.c_[ax, ay]

def nn(df):
    x = df["longitude"].values*K; y = df["latitude"].values*111320.0
    d = np.sqrt(((A[None,:,:] - np.c_[x,y][:,None,:])**2).sum(-1)) if False else None
    # chunked min distance
    res = np.empty(len(df)); idx = np.empty(len(df), dtype=int)
    for i0 in range(0, len(df), 200):
        Q = np.c_[x[i0:i0+200], y[i0:i0+200]]
        dd = np.sqrt(((A[None,:,:]-Q[:,None,:])**2).sum(-1))
        res[i0:i0+200] = dd.min(1); idx[i0:i0+200] = dd.argmin(1)
    return res, idx

P("=== distance from each layer row to the NEAREST _all.csv object (metres) ===")
for k,p in files.items():
    d = rd(p)
    dist, idx = nn(d)
    q = lambda t: (dist<=t).sum()
    P(f"{k:9s} n={len(d):5d}  ==0m {(dist==0).sum():5d} ({100*(dist==0).mean():5.1f}%)"
      f"  <=1m {q(1):5d} ({100*q(1)/len(d):5.1f}%)  <=10m {q(10):5d} ({100*q(10)/len(d):5.1f}%)"
      f"  <=25m {q(25):5d} ({100*q(25)/len(d):5.1f}%)  <=50m {q(50):5d} ({100*q(50)/len(d):5.1f}%)"
      f"  <=100m {q(100):5d} ({100*q(100)/len(d):5.1f}%)  median {np.median(dist):7.1f}")
    d["_d"] = dist
    if k=="grocery":
        P("  grocery: rows >100 m from any _all object, by type_orig:")
        P("   ", d.loc[d._d>100,"type_orig"].value_counts().to_dict())
        P("  grocery: rows >25 m, by type_orig:")
        P("   ", d.loc[d._d>25,"type_orig"].value_counts().to_dict())
        P("  grocery sample of far rows:")
        for _,r in d.nlargest(8,"_d").iterrows():
            P(f"    {r['_d']:8.0f} m  {r['name_orig']!r} | {r['type_orig']} | {r['adress_orig']!r}")
    # matched_source_ids overlap
    if "matched_source_ids" in d.columns:
        P(f"  {k}: matched_source_ids non-null {d['matched_source_ids'].notna().sum()}/{len(d)}")

# do layer rows duplicate _all rows by (name, address)?
akey = set(zip(alld["name_orig"].astype(str).str.strip().str.lower(), alld["adress_orig"].astype(str).str.strip().str.lower()))
for k,p in files.items():
    d = rd(p)
    kk = list(zip(d["name_orig"].astype(str).str.strip().str.lower(), d["adress_orig"].astype(str).str.strip().str.lower()))
    P(f"{k}: (name,address) present in _all: {sum(x in akey for x in kk)}/{len(d)}")

Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p2.txt").write_text(out.getvalue(), encoding="utf-8")
