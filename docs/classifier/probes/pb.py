import sys, io, itertools
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths
out=io.StringIO()
def P(*a): print(*a,file=out)
rd=lambda p: pd.read_csv(p,sep=";",encoding="utf-8-sig",low_memory=False)
R=paths.RAW4
F={"tobacco":paths.V4_TOBACCO,"alcohol":paths.V4_ALCOHOL,
   "catering":R/"infrastructure_архангельск_2026-09-05_quality_excelобщепит.csv",
   "grocery":R/"infrastructure_архангельск_2026-09-05_quality_excelпродуктовые магазины.csv"}
alld=rd(R/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
ak=set(zip(alld.latitude.round(6),alld.longitude.round(6)))
K={k:set(zip(rd(v).latitude.round(6),rd(v).longitude.round(6))) for k,v in F.items()}
uni=set().union(*K.values())
cnt=pd.Series({c:sum(c in s for s in K.values()) for c in uni})
P("=== stats 8: sites by number of layers ===")
P(cnt.value_counts().sort_index().to_string())
P("total sites:",len(uni)," multi-layer:",int((cnt>1).sum()),f"={100*(cnt>1).mean():.1f}%")
P("\npairwise:")
for a,b in itertools.combinations(K,2):
    P(f"  {a} x {b}: {len(K[a]&K[b])}")
P("\n=== how many multi-layer sites land on an _all.csv object? ===")
multi={c for c in uni if cnt[c]>1}
P("multi-layer sites in _all:",len(multi&ak),f"={100*len(multi&ak)/len(multi):.1f}%")
tg=K["tobacco"]&K["grocery"]
P("tobacco x grocery:",len(tg)," of which in _all:",len(tg&ak))
# junk contamination of the grocery layer overall and in overlaps
g=rd(F["grocery"])
junk=g.name_orig.astype(str).str.contains("усор|онтейнер|Урна",regex=True,na=False)
jk=set(zip(g.loc[junk,"latitude"].round(6),g.loc[junk,"longitude"].round(6)))
P("\ngrocery junk rows:",int(junk.sum())," junk coords:",len(jk),
  " junk coords that are multi-layer:",len(jk&multi)," junk coords in _all:",len(jk&ak))
mk=set(zip(g.loc[g.type_orig=="Стационарные рынки и ярмарки","latitude"].round(6),
           g.loc[g.type_orig=="Стационарные рынки и ярмарки","longitude"].round(6)))
P("'Стационарные рынки и ярмарки' coords:",len(mk)," in _all:",len(mk&ak)," multi-layer:",len(mk&multi))
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\pb.txt").write_text(out.getvalue(),encoding="utf-8")
