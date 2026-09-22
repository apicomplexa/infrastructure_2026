import sys, io
from pathlib import Path
ROOT = Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
out = io.StringIO()
def P(*a): print(*a, file=out)
rd = lambda p: pd.read_csv(p, sep=";", encoding="utf-8-sig", low_memory=False)
alld = rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
m = rd(paths.PROC/"match_2022_local.csv")
lk = m[m.tier.isin(["exact","probable"])].copy()
lk["ti"] = lk["target_index"].astype(int)

okr = alld["district_orig"].map(v3.norm_okrug)
P("=== okrug distribution of _all.csv ===")
P(okr.value_counts(dropna=False).to_string())
BENCH = {"Lomonosovsky","Oktyabrsky","Maiskaya Gorka"}
P("in benchmark okrugs:", int(okr.isin(BENCH).sum()), "other:", int((~okr.isin(BENCH)).sum()))

ti = np.sort(lk.ti.unique())
tr = alld.iloc[ti]
P("\n=== training block ===", tr.shape)
P(okr.iloc[ti].value_counts().to_string())

seen = set(tr["type_orig"].dropna().unique())
P("\ndistinct type_orig in export:", alld["type_orig"].nunique(), " in training block:", len(seen))
un = ~alld["type_orig"].isin(seen)
P("export rows with unseen type_orig:", int(un.sum()), f"= {100*un.mean():.1f}%")

etype = alld["type_orig"].to_numpy()[lk.ti.to_numpy()]
tab = pd.crosstab(pd.Series(etype, name="etype"), lk["category_2022"].to_numpy())
P(f"\nlookup (export type_orig -> modal 2022 class), in-sample over {int(tab.values.sum())} linked rows: "
  f"{100*tab.max(axis=1).sum()/tab.values.sum():.1f}%   n types {len(tab)}")
P("export coverage of those types:", int(alld['type_orig'].isin(tab.index).sum()),
  f"= {100*alld['type_orig'].isin(tab.index).mean():.1f}%")

byrow = lk.groupby("ti")["category_2022"].agg(lambda s: s.mode().iat[0])
tt = alld["type_orig"].to_numpy()[byrow.index.to_numpy()]
tab2 = pd.crosstab(pd.Series(tt), byrow.to_numpy())
P(f"per distinct export row: rows {int(tab2.values.sum())}, acc {100*tab2.max(axis=1).sum()/tab2.values.sum():.1f}%, n types {len(tab2)}")

rec_all = v3.recode_2022(alld)
cmpdf = pd.DataFrame({"rule": rec_all.to_numpy()[byrow.index.to_numpy()], "truth": byrow.to_numpy()})
P("\n=== v3_common.recode_2022 vs 2022 truth on the 1,072 training export rows ===")
P(pd.crosstab(cmpdf.rule, cmpdf.truth).to_string())
P("agreement:", f"{100*(cmpdf.rule==cmpdf.truth).mean():.1f}%")
for c in sorted(set(cmpdf.truth)):
    tp = ((cmpdf.rule==c)&(cmpdf.truth==c)).sum(); pr=(cmpdf.rule==c).sum(); rc=(cmpdf.truth==c).sum()
    P(f"  {c:32s} P={tp/pr if pr else float('nan'):.3f} ({tp}/{pr})  R={tp/rc if rc else float('nan'):.3f} ({tp}/{rc})")
P("\nrecode_2022 over the WHOLE export (7,263):")
P(rec_all.value_counts().to_string())
Path(r"C:\Users\alex\AppData\Local\Temp\claude\D--Projects-03-Science-and-Education-infrastructure-2026\680f2257-e82f-4863-8ce3-fb50e37ec762\scratchpad\probe\p5.txt").write_text(out.getvalue(), encoding="utf-8")
