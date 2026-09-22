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
r=v3.recode_2022(alld)
for cls in ["Sport","Medical","Alcohol shops","Tobacco outlets","Industrial"]:
    s=alld[r==cls]
    P("\n=== %s : %d objects ==="%(cls,len(s)))
    P("  by category_orig: "+str(s.category_orig.value_counts().to_dict()))
    P("  by type_orig (top 20):")
    for k,v in s.type_orig.fillna("(nan)").value_counts().head(20).items(): P("     %4d  %s"%(v,k))
P("\n=== why is a sauna Sport? category of Досуг: sauna rows ===")
sa=alld[alld.type_orig.fillna("")=="Досуг: sauna"]
P(sa.category_orig.value_counts().to_dict())
P("\n=== what else does category 'Досуг и спорт' contain, and where does it land? ===")
ds=alld[alld.category_orig.fillna("")=="Досуг и спорт"]
P("n=%d"%len(ds)); P(pd.crosstab(ds.type_orig.fillna("(nan)"),r[ds.index]).to_string())
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q5.txt").write_text(out.getvalue(),encoding="utf-8")
