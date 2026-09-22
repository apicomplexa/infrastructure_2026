import sys, io
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
out = io.StringIO()
def P(*a): print(*a, file=out)
rd = lambda p: pd.read_csv(p, sep=";", encoding="utf-8-sig", low_memory=False)
alld = rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
m = rd(paths.PROC/"match_2022_local.csv")
lk = m[m.tier.isin(["exact","probable"])].copy(); lk["ti"]=lk.target_index.astype(int)

# --- target defined as raw category_orig (ML doc) vs recoded (stats doc) ---
CATMAP={"Общепит":"Catering","Медицинские организации":"Medical","Магазины":"Shops",
 "Спортивные объекты":"Sport","Спецмагазины алкоголя":"Alcohol","Точки продажи табака":"Tobacco",
 "Пром. Объекты":"Industrial"}
lk["cat_en"]=lk.category_orig.map(CATMAP)
P("=== disagreement between the two target definitions on the 1,133 linked rows ===")
P(pd.crosstab(lk.cat_en, lk.category_2022).to_string())

# --- connected components: name OR address edges, on the 1072 export rows ---
tr = alld.iloc[np.sort(lk.ti.unique())].copy()
tr["nn"]=tr.name_orig.map(v3.norm_name); tr["na"]=tr.adress_orig.map(v3.norm_address)
P("\nempty norm_name:",(tr.nn=="").sum()," empty norm_address:",(tr.na=="").sum())
parent=list(range(len(tr)))
def find(a):
    while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
    return a
def uni(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: parent[ra]=rb
idx=np.arange(len(tr))
for col in ["nn","na"]:
    for v,g in pd.Series(idx).groupby(tr[col].to_numpy()):
        if v=="" or pd.isna(v): continue
        gg=g.to_numpy()
        for x in gg[1:]: uni(int(gg[0]),int(x))
comp=pd.Series([find(i) for i in idx])
sz=comp.value_counts()
P("\n=== ML doc's name-OR-address connected components (1,072 export rows) ===")
P("n components:",len(sz)," largest:",sz.iat[0],f"= {100*sz.iat[0]/len(tr):.1f}% (ML bound: <=8%)")
P("top 10 sizes:",sz.head(10).tolist())
P("rows in components >=5:",int(sz[sz>=5].sum()))
big=comp[comp==sz.index[0]].index
P("largest component sample names:", tr.iloc[big]["name_orig"].value_counts().head(12).to_dict())

# address-only and name-only, both units
P("\n=== address-only groups (export rows) ===")
a=tr.na.replace("",np.nan)
P("groups:",a.nunique(),"largest:",a.value_counts().iat[0])
P("=== name-only groups (export rows) ===")
n=tr.nn.replace("",np.nan)
P("groups:",n.nunique(),"largest:",n.value_counts().iat[0],
  " rows in chains>=5:",int(n.value_counts()[n.value_counts()>=5].sum()),
  f" share sharing a name: {100*n.isin(n.value_counts()[n.value_counts()>1].index).mean():.1f}%")
P("top chains:",n.value_counts().head(10).to_dict())

# --- benchmark-side, as the statistician computed it (1,133 rows) ---
bn=lk.name_orig.map(v3.norm_name); ba=lk.adress_orig.map(v3.norm_address)
P("\n=== benchmark-side (1,133 rows), as statistician computed ===")
P("norm_address groups:",ba.replace('',np.nan).nunique(),"largest:",ba.replace('',np.nan).value_counts().iat[0])
P("norm_name groups:",bn.replace('',np.nan).nunique(),"largest:",bn.replace('',np.nan).value_counts().iat[0])
vc=bn.replace('',np.nan).value_counts()
P("rows in chains>=5:",int(vc[vc>=5].sum()), " share sharing a name:",f"{100*bn.isin(vc[vc>1].index).mean():.1f}%")
P("top chains:",vc.head(10).to_dict())
# chain purity
P("\nchain -> category mix:")
for c in vc.head(6).index:
    P(f"  {c}: {lk.loc[bn==c,'category_orig'].value_counts().to_dict()}")

# --- matched_source_ids ---
P("\n=== matched_source_ids in _all.csv ===")
s=alld["matched_source_ids"].astype(str)
P("non-null:",alld.matched_source_ids.notna().sum(),"/",len(alld))
P("sample:",s.head(5).tolist())
P("distinct prefixes:", pd.Series([x.split(':')[0] if ':' in x else x[:6] for x in s]).value_counts().head(8).to_dict())
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p6.txt").write_text(out.getvalue(),encoding="utf-8")
