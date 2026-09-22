import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
out=io.StringIO()
def P(*a): print(*a,file=out)
rd=lambda p: pd.read_csv(p,sep=";",encoding="utf-8-sig",low_memory=False)
alld=rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
m=rd(paths.PROC/"match_2022_local.csv")
lk=m[m.tier.isin(["exact","probable"])].copy(); lk["ti"]=lk.target_index.astype(int)
okr=alld.district_orig.map(v3.norm_okrug)
BENCH={"Lomonosovsky","Oktyabrsky","Maiskaya Gorka"}
elig=okr.isin(BENCH)
rule=v3.recode_2022(alld)
pos=set(lk.ti)
P("=== THE CLOSED-WORLD ASSUMPTION, quantified ===")
P("eligible-negative pool (3 benchmark okrugs):",int(elig.sum()))
P(f"{'class':16s} {'rule says in 3 okrugs':>22s} {'labelled positive':>18s} {'rule-positive but trained as NEGATIVE':>38s}")
for c,lab in [("Grocery shops","Grocery"),("Medical","Medical"),("Catering","Catering"),
              ("Sport","Sport"),("Alcohol shops","Alcohol"),("Tobacco outlets","Tobacco"),("Industrial","Industrial")]:
    r = (rule==c)&elig
    labpos = lk[lk.category_2022==c].ti.unique()
    inter = r.to_numpy().nonzero()[0]
    npos = len(set(labpos))
    neg = len(set(inter)-set(labpos))
    P(f"{lab:16s} {int(r.sum()):22d} {npos:18d} {neg:38d}")
P("\ntotal export rows in 3 okrugs that the free rule assigns to SOME 2022 class:",
  int(((rule!="Other (outside 2022 scheme)")&elig).sum()),
  " of which labelled:",len(pos))

# gps_only mask size, per class, at export-row level
gp=m[m.tier=="gps_only"].copy(); gp=gp[gp.target_index.notna()]; gp["ti"]=gp.target_index.astype(int)
P("\ngps_only rows with a target_index:",len(gp),"distinct export rows:",gp.ti.nunique())
P("gps_only target rows that are ALSO a labelled positive row:",len(set(gp.ti)&pos))
P("by class:",gp.category_2022.value_counts().to_dict())

# v4_licences coverage
vl=pd.read_csv(paths.PROC/"v4_licences.csv",sep=";",encoding="utf-8-sig",low_memory=False)
P("\n=== v4_licences.csv ===",vl.shape)
P("licence_status:",vl.licence_status.value_counts().to_dict() if "licence_status" in vl else "n/a")
kk=set(zip(vl.latitude.round(6),vl.longitude.round(6)))
ak=set(zip(alld.latitude.round(6),alld.longitude.round(6)))
P("distinct coords:",len(kk)," in _all:",len(kk&ak),f"={100*len(kk&ak)/len(kk):.1f}%")
P("cols:",[c for c in vl.columns if c.startswith("licence")])

# EGAIS active off-trade by okrug
try:
    from arkhinfra import egais
    P("\negais module:",[n for n in dir(egais) if not n.startswith("_")])
except Exception as e:
    P("egais import fail",e)
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p8.txt").write_text(out.getvalue(),encoding="utf-8")
