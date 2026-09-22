import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
out=io.StringIO()
def P(*a): print(*a,file=out)
alld=pd.read_csv(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv",sep=";",encoding="utf-8-sig",low_memory=False)
m=pd.read_csv(paths.PROC/"match_2022_local.csv",sep=";",encoding="utf-8-sig",low_memory=False)
lk=m[m.tier.isin(["exact","probable"])]; ti=np.sort(lk.target_index.astype(int).unique())
seen=set(alld.iloc[ti].type_orig.dropna())
un=~alld.type_orig.isin(seen)
rule=v3.recode_2022(alld)
P("=== the 3,271 unseen-type rows: what the free rule says they are ===")
P(rule[un].value_counts().to_string())
P("\n=== the 3,992 seen-type rows ===")
P(rule[~un].value_counts().to_string())
P("\n=== unseen types the rule assigns to a 2022 class (top 25) ===")
sub=alld[un & (rule!="Other (outside 2022 scheme)")]
P(sub.type_orig.value_counts().head(25).to_string())
P("\nn unseen rows the rule places in a 2022 class:",len(sub),
  f" = {100*len(sub)/int(un.sum()):.1f}% of the unseen slice")
P("\n=== top unseen types the rule calls 'Other' (top 20) ===")
P(alld[un&(rule=='Other (outside 2022 scheme)')].type_orig.value_counts().head(20).to_string())
P("\n=== category_orig of the unseen slice ===")
P(alld[un].category_orig.value_counts().to_string())
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\pd.txt").write_text(out.getvalue(),encoding="utf-8")
