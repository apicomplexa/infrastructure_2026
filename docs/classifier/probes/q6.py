import sys, io
from pathlib import Path
ROOT=Path(r"D:\Projects\03_Science_and_Education\infrastructure_2026")
sys.path.insert(0,str(ROOT/"src"))
import pandas as pd, numpy as np
from arkhinfra import paths, v3_common as v3
from arkhinfra.v3_common import _has, GROCERY_TYPES
out=io.StringIO()
def P(*a): print(*a,file=out)
rd=lambda p: pd.read_csv(p,sep=";",encoding="utf-8-sig",low_memory=False)
df=rd(paths.RAW4/"infrastructure_архангельск_2026-08-31_quality_excel_all.csv")
cat=df.category_orig.fillna("").astype(str); t=cat.str.lower()*0+df.type_orig.fillna("").astype(str).str.lower()
blob=(cat.str.lower()+" | "+t+" | "+df.name_orig.fillna("").astype(str).str.lower())
B={
"Tobacco":(cat=="Точки продажи табака")|_has(blob,"табак","вейп","сигарет","кальян","vape"),
"Alcohol":_has(t,"алкогол")|_has(blob,"алкомаркет","винотек")|(_has(t,"винный")&_has(t,"магазин")),
"Medical":(cat=="Медицинские организации")|_has(blob,"аптек","поликлин","больниц","стоматолог","клиник","врач","диагност","лаборатор","диспансер","госпит","медиц","оптика","реабилит","санатор","профилакт","роддом","родильн","фельдшер"),
"Sport":(cat=="Спортивные объекты")|_has(blob,"спорт","фитнес","бассейн","стадион","тренаж","воркаут","каток","манеж","йога")|_has(t,"парк","сквер","набережн"),
"Catering":cat.isin(["Общепит","фастфуд"])|_has(t,"кафе","фастфуд","бар","ресторан","паб","кофейн","столов","закусочн","пиццери","суши","бистро"),
"Grocery":t.isin(GROCERY_TYPES),
"Industrial":_has(blob,"завод","энергокомплекс","тэц","гэс","фабрика","промышл","комбинат"),
}
M=pd.DataFrame(B)
k=M.sum(axis=1)
P("=== I. multi-label already latent in the rule's own predicates ===")
P("objects matching k predicates:",k.value_counts().sort_index().to_dict())
P("objects matching >=2:",int((k>=2).sum()),"(%.1f%% of 7263)"%(100*(k>=2).mean()))
P("\nsingle-label marginal (np.select priority) vs boolean marginal:")
r=v3.recode_2022(df)
NAME={"Tobacco":"Tobacco outlets","Alcohol":"Alcohol shops","Medical":"Medical","Sport":"Sport",
      "Catering":"Catering","Grocery":"Grocery shops","Industrial":"Industrial"}
for c in B:
    P("  %-11s boolean %5d   after priority %5d   suppressed %4d"%(
        c,int(M[c].sum()),int((r==NAME[c]).sum()),int(M[c].sum()-(r==NAME[c]).sum())))
P("\n=== J. commonest co-membership pairs ===")
cols=list(B)
pairs=[]
for i in range(len(cols)):
    for j in range(i+1,len(cols)):
        n=int((M[cols[i]]&M[cols[j]]).sum())
        if n: pairs.append((cols[i],cols[j],n))
for a,b,n in sorted(pairs,key=lambda x:-x[2]): P("  %-10s x %-10s %4d"%(a,b,n))
P("\n=== K. who loses what: examples of suppressed Grocery ===")
sup=df[M.Grocery&(r!="Grocery shops")]
P("suppressed grocery n=%d, taken by: %s"%(len(sup),r[sup.index].value_counts().to_dict()))
P("  types: "+str(sup.type_orig.value_counts().head(6).to_dict()))
Path(r"C:\Users\alex\.claude\jobs\4684f119\tmp\q6.txt").write_text(out.getvalue(),encoding="utf-8")
