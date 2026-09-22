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

# label = 2022 category on the benchmark side, mapped to the rule's class names
LAB={"Медицинские организации":"Medical","Спортивные объекты":"Sport",
     "Магазины":"Grocery shops","Общепит":"Catering",
     "Спецмагазины алкоголя":"Alcohol shops","Точки продажи табака":"Tobacco outlets",
     "Пром. Объекты":"Industrial"}
lk["y"]=lk.category_orig.map(LAB)
P("linked rows:",len(lk),"  unmapped labels:",lk.y.isna().sum(),
  "  distinct export rows:",lk.ti.nunique())

ex=alld.iloc[lk.ti.values].reset_index(drop=True)
lk=lk.reset_index(drop=True)
ex["yhat"]=v3.recode_2022(ex).values
D=pd.DataFrame({"y":lk.y,"yhat":ex.yhat,"tier":lk.tier,"name_sim":lk.name_sim,
                "ex_cat":ex.category_orig.values,"ex_type":ex.type_orig.values,
                "ex_name":ex.name_orig.values,"bm_type":lk.type_orig.values,
                "bm_name":lk.name_orig.values})
D=D[D.y.notna()]
P("\n=== A1. rule on export features vs 2022 label, linked rows n=%d ==="%len(D))
def pr(D,tag):
    rows=[]
    for c in ["Medical","Catering","Grocery shops","Sport","Alcohol shops","Tobacco outlets","Industrial"]:
        tp=int(((D.y==c)&(D.yhat==c)).sum()); fp=int(((D.y!=c)&(D.yhat==c)).sum()); fn=int(((D.y==c)&(D.yhat!=c)).sum())
        rows.append((c,int((D.y==c).sum()),tp,fp,fn,
                     tp/(tp+fp) if tp+fp else float('nan'), tp/(tp+fn) if tp+fn else float('nan')))
    t=pd.DataFrame(rows,columns=["class","n_lab","tp","fp","fn","P","R"])
    P("\n--"+tag); P(t.to_string(index=False,float_format=lambda x:f"{x:.3f}"))
    P("  exact accuracy: %.4f  (%d/%d wrong)"%((D.y==D.yhat).mean(),(D.y!=D.yhat).sum(),len(D)))
    return t
pr(D,"all linked")

P("\n=== A2. errors: how many labelled rows does the rule get WRONG ===")
E=D[D.y!=D.yhat]
P("total wrong:",len(E),"of",len(D))
P(pd.crosstab(E.y,E.yhat).to_string())

P("\n=== A3. does link quality inflate the ceiling? ===")
for t in ["exact","probable"]:
    sub=D[D.tier==t]
    P("  tier=%-9s n=%4d  acc=%.4f"%(t,len(sub),(sub.y==sub.yhat).mean()))
for lo,hi in [(0.0,0.6),(0.6,0.9),(0.9,1.01)]:
    sub=D[(D.name_sim>=lo)&(D.name_sim<hi)]
    P("  name_sim [%.1f,%.2f) n=%4d  acc=%.4f"%(lo,hi,len(sub),(sub.y==sub.yhat).mean() if len(sub) else float('nan')))

P("\n=== B. how much of the rule is just copying export category_orig? ===")
P(pd.crosstab(D.ex_cat,D.y).to_string())
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q1.txt").write_text(out.getvalue(),encoding="utf-8")
