import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import egais
out=io.StringIO()
def P(*a): print(*a,file=out)
e=egais.load_egais()
P("rows",len(e),"active",int(e.is_active.sum()))
di=pd.to_datetime(e.date_issued,errors="coerce"); dx=pd.to_datetime(e.date_expires,errors="coerce")
P("date_issued range:",di.min(),"->",di.max())
P("date_expires range:",dx.min(),"->",dx.max())
cover2022 = (di<=pd.Timestamp("2022-12-31")) & (dx>=pd.Timestamp("2022-01-01"))
P("licences whose validity window overlaps calendar 2022:",int(cover2022.sum()),f"={100*cover2022.mean():.1f}%")
P("  of the ARCHIVED ones:",int((cover2022&~e.is_active).sum()),"of",int((~e.is_active).sum()))
P("activity_class:",e.activity_class.value_counts().to_dict())
P("active retail off-trade by okrug:")
ok=e.apply(egais.assign_okrug,axis=1) if False else None
P("assign_okrug signature test skipped")
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\pc.txt").write_text(out.getvalue(),encoding="utf-8")
