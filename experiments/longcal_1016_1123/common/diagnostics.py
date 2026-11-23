"""Held-out night variability, event exposure and paired example plots."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from evaluate import load,minute_clock,datestr

p=argparse.ArgumentParser(description=__doc__)
for key in ("cache","work","results"):p.add_argument("--"+key,required=True,type=Path)
a=p.parse_args()
df=pd.read_csv(a.results/"per_cell.csv.gz",dtype={"device":str,"marker":str})
g=df[df.split=="test"].copy()
g["improvement"]=g.var0-g.var1
night=g.groupby("night").agg(cells=("count","size"),baseline=("var0","mean"),candidate=("var1","mean"))
night["reduction_pct"]=100*(1-night.candidate/night.baseline)
night.to_csv(a.results/"test_nights.csv")
ev=pd.read_csv(a.results/"injections.csv",dtype={"device":str,"marker":str})
examples=[]
for axis,rows in g.groupby("axis"):
    for label,key in (("Largest variance reduction",rows.improvement.idxmax()),("Largest variance increase",rows.improvement.idxmin())):
        examples.append((label,rows.loc[key]))
fig,axes=plt.subplots(len(examples),1,figsize=(10,2.7*len(examples)),layout="constrained",squeeze=False)
for ax,(label,r) in zip(axes[:,0],examples):
    ts,b,names=load(a.cache/(r.device+".npz"))
    m,tod,night=minute_clock(ts)
    k=int((np.datetime64(r.night)-np.datetime64("1970-01-01")).astype(int))
    mask=(night==k)&((tod>=1320)|(tod<480))
    j=list(names).index(r.marker); u="XY".index(r.axis)
    with np.load(a.work/(r.device+".npz")) as z: c=z["out"][mask,u,j];ref=z["ref"][mask,u,j]
    t=(m[mask]-(k*1440+1320))/60.
    ax.plot(t,b[mask,u,j],color="#117699",lw=1.5,label="V53")
    ax.plot(t,c,color="#c64a22",ls="--",lw=1,label="Candidate")
    ax.plot(t,ref,color="#555",ls=":",lw=1,label="Daylight anchor")
    ax.set(title=f"{label} | {r.night} | {r.device} / {r.marker} / {r.axis}",ylabel="mm",xlabel="Hours after 22:00 (UTC+8)")
    ax.grid(alpha=.2);ax.legend(ncol=3,fontsize=8)
fig.savefig(a.results/"paired_examples.png",dpi=140);plt.close(fig)
if len(ev):
    ev["active_before"]=False
    for device,rows in ev.groupby("device"):
        ts,b,names=load(a.cache/(device+".npz"));m,tod,night=minute_clock(ts)
        with np.load(a.work/(device+".npz")) as z:c=z["out"]
        for date,subset in rows.groupby("night"):
            k=int((np.datetime64(date)-np.datetime64("1970-01-01")).astype(int))
            onset=(k+1)*1440+70
            mask=(m>=onset-30)&(m<onset)
            diff=np.abs(b[mask]-c[mask]);valid=np.isfinite(diff)
            avg=np.nansum(diff,axis=0)/np.maximum(1,valid.sum(axis=0))
            for i,r in subset.iterrows():
                ev.loc[i,"active_before"]=avg["XY".index(r.axis),list(names).index(r.marker)]>.001
    ev.to_csv(a.results/"injections.csv",index=False)
    ev.groupby(["case","active_before"]).agg(cells=("count","size"),min_frame_ratio=("min_ratio","min"),
        worst_cell_median=("median_ratio","min"),median_ratio=("median_ratio","median")).to_csv(a.results/"event_summary.csv")
