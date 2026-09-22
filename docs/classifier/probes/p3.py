import sys, io
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd, numpy as np
from arkhinfra import paths
out = io.StringIO()
def P(*a): print(*a, file=out)
RAW4 = paths.RAW4
rd = lambda p: pd.read_csv(p, sep=";", encoding="utf-8-sig", low_memory=False)
g = rd(RAW4/"infrastructure_архангельск_2026-09-05_quality_excelпродуктовые магазины.csv")
c = rd(RAW4/"infrastructure_архангельск_2026-09-05_quality_excelобщепит.csv")

P("=== grocery layer: name_orig top 40 ===")
P(g["name_orig"].value_counts().head(40).to_string())
P("\n=== grocery 'Стационарные рынки и ярмарки' (406): name top 25 ===")
m = g[g.type_orig=="Стационарные рынки и ярмарки"]
P(m["name_orig"].value_counts().head(25).to_string())
P("\ngarbage-ish rows in whole grocery layer:")
bad = g["name_orig"].astype(str).str.contains("мусор|Контейнер|контейнер|Урна|урна", regex=True, na=False)
P(f"  {bad.sum()} of {len(g)} ({100*bad.mean():.1f}%)  by type: {g.loc[bad,'type_orig'].value_counts().to_dict()}")
P("\n=== grocery 'Торговые центры' names top 20 ===")
P(g[g.type_orig=="Торговые центры"]["name_orig"].value_counts().head(20).to_string())
P("\n=== grocery 'Продуктовые магазины и супермаркеты' names top 20 ===")
P(g[g.type_orig=="Продуктовые магазины и супермаркеты"]["name_orig"].value_counts().head(20).to_string())
P("\n=== grocery verification_comment sample ===")
P(g["verification_comment"].astype(str).value_counts().head(6).to_string())
P("\n=== catering names top 20 ===")
P(c["name_orig"].value_counts().head(20).to_string())
P("\n=== catering verification_comment ===")
P(c["verification_comment"].astype(str).value_counts().head(5).to_string())
P("\n=== duplicate coords within grocery ===")
P(str(g.duplicated(subset=["latitude","longitude"]).sum()))
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p3.txt").write_text(out.getvalue(), encoding="utf-8")
