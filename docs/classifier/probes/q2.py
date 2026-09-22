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
LAB={"Медицинские организации":"Medical","Спортивные объекты":"Sport","Магазины":"Grocery shops",
     "Общепит":"Catering","Спецмагазины алкоголя":"Alcohol shops",
     "Точки продажи табака":"Tobacco outlets","Пром. Объекты":"Industrial"}
lk["y"]=lk.category_orig.map(LAB)
ex=alld.iloc[lk.ti.values].reset_index(drop=True); lk=lk.reset_index(drop=True)
D=pd.DataFrame({"y":lk.y,"yhat":v3.recode_2022(ex).values,"tier":lk.tier,
  "ex_cat":ex.category_orig.values,"ex_type":ex.type_orig.values,"ex_name":ex.name_orig.values,
  "bm_type":lk.type_orig.values,"bm_name":lk.name_orig.values})
E=D[D.y!=D.yhat]
P("=== C. the 96 errors, by (label -> prediction), with the export type that caused it ===")
for (y,yh),g in E.groupby(["y","yhat"]):
    if len(g)<2: continue
    P("\n%-16s -> %-28s n=%d"%(y,yh,len(g)))
    P("   ex_type: "+str(g.ex_type.value_counts().head(8).to_dict()))
    P("   bm_type: "+str(g.bm_type.value_counts().head(8).to_dict()))
    P("   names  : "+", ".join(map(str,g.ex_name.head(6))))
P("\n=== D. singletons ===")
for (y,yh),g in E.groupby(["y","yhat"]):
    if len(g)>=2: continue
    P("  %-16s -> %-28s | %s | %s"%(y,yh,g.ex_type.iloc[0],g.ex_name.iloc[0]))
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q2.txt").write_text(out.getvalue(),encoding="utf-8")
