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
P("=== E. city-wide impact of the missing grocery type ===")
t=alld.type_orig.fillna("").str.lower()
P("Овощи и фрукты in export:",int((t=="овощи и фрукты").sum()),
  " -> currently recoded:",r[t=="овощи и фрукты"].value_counts().to_dict())
P("фрукты-овощи in export :",int((t=="фрукты-овощи").sum()))
P("current Grocery shops city-wide:",int((r=="Grocery shops").sum()))

P("\n=== F. every export type landing in 'Other', sorted, top 60 ===")
oth=alld[r=="Other (outside 2022 scheme)"]
vc=oth.type_orig.fillna("(nan)").value_counts()
P("Other total:",len(oth)," distinct types:",vc.size)
for k,v in vc.head(60).items(): P("  %5d  %s"%(v,k))

P("\n=== G. food/health stems still sitting in Other ===")
STEM=["продукт","магазин продук","овощ","фрукт","хлеб","пекарн","мясн","рыбн","молоч",
      "гастроном","минимаркет","универсам","бакале","аптек","медиц","спорт","стадион",
      "площадк","табач","алкогол","пив","вино","бар","кафе","столов","буфет","кондитер","чай","кофе"]
for s in STEM:
    hit=vc[[str(i).lower().find(s)>=0 for i in vc.index]]
    if len(hit): P("  stem %-14s -> %s"%(s,hit.to_dict()))
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q3.txt").write_text(out.getvalue(),encoding="utf-8")
