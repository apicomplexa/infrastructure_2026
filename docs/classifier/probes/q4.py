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
t=alld.type_orig.fillna("").astype(str)
lat=t.str.contains(r"[A-Za-z]",regex=True)
P("=== H. every type carrying a Latin (OSM tag) value ===")
P("rows with a latin type: %d of %d"%(int(lat.sum()),len(t)))
tab=pd.crosstab(t[lat],r[lat])
P(tab.to_string())
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q4.txt").write_text(out.getvalue(),encoding="utf-8")
