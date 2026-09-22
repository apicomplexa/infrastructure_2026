import sys, io
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
out=io.StringIO()
def P(*a): print(*a,file=out)
rd=lambda p: pd.read_csv(p,sep=";",encoding="utf-8-sig",low_memory=False)
alld=rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
m=rd(paths.PROC/"match_2022_local.csv")
lk=m[m.tier.isin(["exact","probable"])].copy(); lk["ti"]=lk.target_index.astype(int)
tr=alld.iloc[np.sort(lk.ti.unique())].copy()
tr["nn"]=tr.name_orig.map(v3.norm_name); tr["na"]=tr.adress_orig.map(v3.norm_address)
K=np.cos(np.radians(64.5))*111320.0
X=np.c_[tr.longitude.values*K, tr.latitude.values*111320.0]

def comps(edges_lists, n):
    par=list(range(n))
    def f(a):
        while par[a]!=a: par[a]=par[par[a]]; a=par[a]
        return a
    for lst in edges_lists:
        for grp in lst:
            g=list(grp)
            for x in g[1:]:
                ra,rb=f(g[0]),f(x)
                if ra!=rb: par[ra]=rb
    c=pd.Series([f(i) for i in range(n)])
    return c.value_counts()

n=len(tr); idx=np.arange(n)
addr_groups=[g.tolist() for v,g in pd.Series(idx).groupby(tr.na.to_numpy()) if v!=""]
name_vc=tr.nn.value_counts()
name_groups=[g.tolist() for v,g in pd.Series(idx).groupby(tr.nn.to_numpy()) if v!=""]
name_ge3=[g.tolist() for v,g in pd.Series(idx).groupby(tr.nn.to_numpy()) if v!="" and name_vc[v]>=3]
name_lt3=[g.tolist() for v,g in pd.Series(idx).groupby(tr.nn.to_numpy()) if v!="" and name_vc[v]<3]
# 25 m coordinate edges
from itertools import combinations
D=np.sqrt(((X[:,None,:]-X[None,:,:])**2).sum(-1))
coord_groups=[]
for i in range(n):
    j=np.where(D[i]<=25)[0]
    if len(j)>1: coord_groups.append(j.tolist())

variants={
 "ML: name OR address":[name_groups,addr_groups],
 "ML fallback: name(cnt>=3) OR address":[name_ge3,addr_groups],
 "name(cnt<3) OR address":[name_lt3,addr_groups],
 "address only":[addr_groups],
 "STATS: address OR coords<=25m (building)":[addr_groups,coord_groups],
 "chain (name) only":[name_groups],
 "name OR address OR coords<=25m":[name_groups,addr_groups,coord_groups],
}
P("=== grouping variants on the 1,072 training export rows ===")
for k,v in variants.items():
    sz=comps(v,n)
    P(f"{k:42s} groups {len(sz):4d}  largest {sz.iat[0]:4d} = {100*sz.iat[0]/n:5.1f}%  top5 {sz.head(5).tolist()}")

# §8.1: is Магазины grocery?
P("\n=== ML 8.1: what is 'Магазины' in the 2022 benchmark? ===")
mm=m[m.category_orig=="Магазины"]
P("all 400 rows, type_orig:"); P(mm.type_orig.value_counts().to_string())
P("\nGROCERY_TYPES set:", sorted(v3.GROCERY_TYPES))
P("share of Магазины whose type is in GROCERY_TYPES:",
  f"{100*mm.type_orig.isin(v3.GROCERY_TYPES).mean():.1f}%")
P("recode_2022 of the 400 Магазины benchmark rows:")
P(mm.category_2022.value_counts().to_string())

# training-row category_orig of the export (what the model sees)
P("\n=== export category_orig of the 1,072 training rows vs of the 7,263 ===")
P(pd.concat([tr.category_orig.value_counts().rename("train"),
             alld.category_orig.value_counts().rename("all")],axis=1).fillna(0).astype(int).to_string())
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p7.txt").write_text(out.getvalue(),encoding="utf-8")
