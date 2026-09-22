import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3, egais
out=io.StringIO()
def P(*a): print(*a,file=out)
rd=lambda p: pd.read_csv(p,sep=";",encoding="utf-8-sig",low_memory=False)
alld=rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
m=rd(paths.PROC/"match_2022_local.csv")
lk=m[m.tier.isin(["exact","probable"])].copy(); lk["ti"]=lk.target_index.astype(int)
okr=alld.district_orig.map(v3.norm_okrug); BENCH={"Lomonosovsky","Oktyabrsky","Maiskaya Gorka"}
elig=okr.isin(BENCH); rule=v3.recode_2022(alld); pos=set(lk.ti)
for cls in ["Sport","Grocery shops","Tobacco outlets","Alcohol shops"]:
    sel=alld[(rule==cls)&elig&~alld.index.isin(pos)]
    P(f"\n=== '{cls}': rule-positive, trained as negative (n={len(sel)}) — type_orig top 12 ===")
    P(sel.type_orig.value_counts().head(12).to_string())
    P("  sample names:",sel.name_orig.head(6).tolist())

# multi-tenant link rate (stats §6)
m2=m.copy(); m2["ck"]=list(zip(m2.latitude.round(6),m2.longitude.round(6)))
cnt=m2.ck.value_counts(); m2["multi"]=m2.ck.map(cnt)>1
m2["linked"]=m2.tier.isin(["exact","probable"])
P("\n=== stats 6: link rate single vs multi-tenant coordinate ===")
P(m2.groupby("multi").linked.agg(["mean","size"]).to_string())
P("n multi coordinates:", int((cnt>1).sum()))

# EGAIS okrug table
e=egais.load_egais()
P("\n=== EGAIS ===", e.shape, [c for c in e.columns][:30])
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p9.txt").write_text(out.getvalue(),encoding="utf-8")
