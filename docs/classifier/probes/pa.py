import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3, v4_common as v4
out=io.StringIO()
def P(*a): print(*a,file=out)
alld=pd.read_csv(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv",sep=";",encoding="utf-8-sig",low_memory=False)
r3=v3.recode_2022(alld); r4=v4.recode_2022_v4(alld)
P("recode_2022  on _all.csv:",r3.value_counts().to_dict())
P("recode_2022_v4 on _all.csv:",r4.value_counts().to_dict())
P("differ:",int((r3!=r4).sum()))
P("\n_TOBACCO_STEM:",repr(v4._TOBACCO_STEM))
t=alld.type_orig.astype(str)
for pat in ["Табач","табач","табак","Вейп","вейп","Кальян","кальян","Сигарет"]:
    P(f"  type_orig contains {pat!r}: {int(t.str.contains(pat,regex=False).sum())}")
P("\nexport types containing 'абач':", t[t.str.contains('абач',regex=False)].value_counts().to_dict())
P("\n=== does recode_2022 (v3) catch 'Табачный магазин'? ===")
sub=alld[t=="Табачный магазин"]
P("n:",len(sub)," recode_2022 says:",r3[sub.index].value_counts().to_dict()," recode_v4 says:",r4[sub.index].value_counts().to_dict())
P("\n=== opening_hours encodings in _all.csv ===")
oh=alld.opening_hours_orig
P("populated:",int(oh.notna().sum()),f"={100*oh.notna().mean():.1f}%")
P("json-looking:",int(oh.astype(str).str.strip().str.startswith(('{','[')).sum()))
P("\n=== field coverage ===")
for c in ["website_check_status","opening_date_orig","website_orig","phone_orig","match_distance_meters","match_name_similarity"]:
    P(f"  {c}: {100*alld[c].notna().mean():.1f}%")
P("verification_status:",alld.verification_status.value_counts().to_dict())
md=pd.to_numeric(alld.match_distance_meters,errors="coerce"); ms=pd.to_numeric(alld.match_name_similarity,errors="coerce")
P("match_distance_meters ==0 share (of populated):",f"{100*(md==0).sum()/md.notna().sum():.1f}%")
P("match_name_similarity ==1 share (of populated):",f"{100*(ms==1).sum()/ms.notna().sum():.1f}%")
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\pa.txt").write_text(out.getvalue(),encoding="utf-8")
