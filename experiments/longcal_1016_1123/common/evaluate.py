"""Causal V53 post-calibration benchmark. Paths are arguments; no database writes."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TZ = timezone(timedelta(hours=8))
HERE = Path(__file__).resolve().parent
LEFT = {"780630499846","780637798298","780638271319","780638310097","780638327479","780638349768"}
RIGHT = {"780639173835","780639298317","780639333715","780639346578","780639376393","780639414923"}
VAL = "2026-11-07"
TEST = "2026-11-15"


def native(exe, folder, ts, values, collect=False, events=None):
    n, _, p = values.shape
    data = np.empty(n, dtype=[("ts","<i8"),("xy","<f8",(2,p))])
    data["ts"], data["xy"] = ts, values
    src, dst, sample = (folder / name for name in ("input.bin","out.bin","samples.bin"))
    with src.open("wb") as stream:
        np.array([p,n],dtype="<u4").tofile(stream)
        data.tofile(stream)
    cmd=[str(exe),str(src),str(dst),str(sample) if collect else "-"]
    if events is not None:cmd.append(str(events))
    run = subprocess.run(cmd,
                         capture_output=True,text=True,check=True)
    output = np.fromfile(dst,"<f8").reshape(n,2,2,p)
    samples = np.fromfile(sample,"<f8").reshape(-1,6) if collect else None
    for path in (src,dst,sample):
        path.unlink(missing_ok=True)
    return output[:,0],output[:,1],json.loads(run.stdout),samples


def load(path):
    with np.load(path,allow_pickle=False) as z:
        ts = z["ts"].astype(np.int64)
        values = np.stack([z["x"],z["y"]],axis=1).astype(np.float64)
        names = z["names"].astype(str)
    if not len(ts) or np.any(np.diff(ts)<=0) or values.shape!=(len(ts),2,len(names)):
        raise ValueError(f"invalid input {path}")
    return ts,values,names


def minute_clock(ts):
    local = (ts//60000+480)
    day = local//1440
    tod = local%1440
    return local,tod,day-(tod<480)


def datestr(day):
    return str(np.datetime64("1970-01-01")+np.timedelta64(int(day),"D"))


def score(ts,values,out,refs,names,device):
    local,tod,night = minute_clock(ts)
    if not np.array_equal(np.isfinite(values),np.isfinite(out)):
        raise ValueError("candidate changed missing-data mask")
    day = (tod>=600)&(tod<960)
    # Identity on all daytime observations implies identity on every stable block.
    daytime = []
    for split,lo,hi in (("train","2026-10-16",VAL),("validation",VAL,TEST),("test",TEST,"2026-11-24")):
        start,end=(int(datetime.fromisoformat(s).replace(hour=8,tzinfo=TZ).timestamp()*1000) for s in (lo,hi))
        mask=day&(ts>=start)&(ts<end)
        dif=np.abs(values[mask]-out[mask])
        for ax,axis in enumerate("XY"):
            d=dif[:,ax]; ok=np.isfinite(d)
            daytime.append((split,device,axis,int(ok.sum()),np.sum(d[ok]),np.max(d[ok],initial=0.)))
    rows=[]
    for k in np.unique(night):
        date=datestr(k)
        if date<"2026-10-16" or local[-1]+2 < (k+1)*1440+480: continue
        indices=np.flatnonzero((night==k)&((tod>=1320)|(tod<480)))
        if not len(indices): continue
        # A single evaluation observation per wall-clock minute, even across rollover.
        ii=indices[np.r_[True,np.diff(local[indices])!=0]]
        minutes=local[ii]
        for ax,axis in enumerate("XY"):
            old,new,ref=values[ii,ax],out[ii,ax],refs[ii,ax]
            for col in np.flatnonzero(np.isfinite(old).sum(axis=0)>=480):
                b,c,r=old[:,col],new[:,col],ref[:,col]
                valid=np.isfinite(b)
                adj=valid[1:]&valid[:-1]&(np.diff(minutes)==1)
                br,cr=(v[np.isfinite(r)&valid]-r[np.isfinite(r)&valid] for v in (b,c))
                rows.append((date,"train" if date<VAL else "validation" if date<TEST else "test",
                    "left" if device in LEFT else "right",device,names[col],axis,valid.sum(),
                    np.var(b[valid]),np.var(c[valid]),adj.sum(),
                    (np.abs(np.diff(b)[adj])>.5).sum(),(np.abs(np.diff(c)[adj])>.5).sum(),
                    len(br),np.abs(br).sum(),np.abs(cr).sum(),np.square(br).sum(),np.square(cr).sum(),
                    np.count_nonzero(np.abs(c[valid]-b[valid])>1e-10)))
    return rows,daytime


COLS="night split line device marker axis count var0 var1 adjacent spikes0 spikes1 anchors abs0 abs1 sq0 sq1 changed".split()
DAYCOLS="split device axis count sum_abs max_abs".split()


def summary(g):
    def ratio(num,den): return float(num/den) if den else None
    v0,v1=g.var0.mean(),g.var1.mean()
    result=dict(cells=len(g),devices=g.device.nunique(),nights=g.night.nunique(),samples=int(g["count"].sum()),
                baseline_variance=v0,variance=v1,reduction_pct=ratio(100*(v0-v1),v0),
                changed_pct=ratio(100*g.changed.sum(),g["count"].sum()),
                degraded_cell_pct=100*(g.var1>g.var0+1e-12).mean(),
                p95_variance_increase=float((g.var1-g.var0).quantile(.95)),
                worst_variance_increase=float((g.var1-g.var0).max()),
                anchor_samples=int(g.anchors.sum()))
    for j,tag in ((0,"baseline_"),(1,"")):
        result[tag+"spike_rate"]=ratio(g["spikes"+str(j)].sum(),g.adjacent.sum())
        result[tag+"anchor_mae"]=ratio(g["abs"+str(j)].sum(),g.anchors.sum())
        mse=ratio(g["sq"+str(j)].sum(),g.anchors.sum())
        result[tag+"anchor_rmse"]=None if mse is None else np.sqrt(mse)
    return result


def injections(exe,folder,ts,values,ordinary,names,device):
    local,tod,night=minute_clock(ts)
    edited=values.copy(); jobs=[]
    test_days=sorted(k for k in np.unique(night) if datestr(k)>=TEST)
    # Six disjoint night windows per device. Onset 01:10, duration 60 minutes.
    # Each case is run on both axes; baseline and perturbation have identical past.
    for typ,k in zip(("local_step","common_step","local_ramp","common_ramp","local_small_step","common_small_step"),test_days):
        minute=local-((k+1)*1440+70)
        pos=np.flatnonzero((minute>=0)&(minute<60))
        if len(np.unique(minute[pos]))<54: continue
        for ax in (0,1):
            valid=np.flatnonzero(np.isfinite(values[pos,ax]).sum(axis=0)>=.9*len(pos))
            if not len(valid): continue
            cols=valid if typ.startswith("common") else valid[:1]
            amp=.35 if "small" in typ else 1.
            profile=amp*(np.minimum((minute[pos]+1)/45.,1.) if "ramp" in typ else np.ones(len(pos)))
            if ax: profile=-profile
            edited[pos[:,None],ax,cols]+=profile[:,None]
            jobs.append((typ,k,ax,pos,cols,profile))
    if not jobs:return []
    # Native driver forks the exact pre-onset state for each case, then discards it.
    event_path=folder/"events.bin"
    with event_path.open("wb") as stream:
        for event_id,typ in enumerate(dict.fromkeys(x[0] for x in jobs),start=1):
            pos=next(x[3] for x in jobs if x[0]==typ)
            rec=np.empty(len(pos),dtype=[("ts","<i8"),("case","<u4"),("v","<f8",values.shape[1:])])
            rec["ts"],rec["case"],rec["v"]=ts[pos],event_id,edited[pos]
            rec.tofile(stream)
    perturbed,_,_,_=native(exe,folder,ts,values,events=event_path)
    event_path.unlink()
    rows=[]
    for typ,k,ax,pos,cols,profile in jobs:
        late=profile==profile[-1] if "ramp" in typ else np.ones(len(pos),dtype=bool)
        diff=perturbed[pos[:,None],ax,cols]-ordinary[pos[:,None],ax,cols]
        for jj,col in enumerate(cols):
            ratio=diff[late,jj]/profile[late]
            finite=ratio[np.isfinite(ratio)]
            if len(finite): rows.append((device,datestr(k),names[col],"XY"[ax],typ,len(finite),np.median(finite),np.min(finite)))
    return rows


def figures(test,cache,folder,dest):
    if test.empty: return
    chosen=[]
    for axis in "XY":
        subset=test[test.axis==axis]
        if subset.empty:continue
        chosen.append(("V53 highest variance",subset.loc[subset.var0.idxmax()]))
        worst=(subset.var1-subset.var0).idxmax()
        if test.changed.sum():chosen.append(("Largest variance increase",subset.loc[worst]))
    fig,axes=plt.subplots(len(chosen),1,figsize=(10,2.7*len(chosen)),squeeze=False,layout="constrained")
    for ax,(label,r) in zip(axes.ravel(),chosen):
        ts,b,names=load(cache/(r.device+".npz"))
        local,tod,night=minute_clock(ts)
        k=(np.datetime64(r.night)-np.datetime64("1970-01-01")).astype(int)
        mask=(night==k)&((tod>=1320)|(tod<480))
        col=list(names).index(r.marker); axis="XY".index(r.axis)
        with np.load(folder/(r.device+".npz")) as data:
            c=data["out"][mask,axis,col]; ref=data["ref"][mask,axis,col]
        t=(local[mask]-(k*1440+1320))/60.
        ax.plot(t,b[mask,axis,col],label="V53",lw=1.5,color="#117699")
        ax.plot(t,c,label="Experiment",lw=1,ls="--",color="#d65a2e")
        ax.plot(t,ref,label="Past daylight anchor",ls=":",lw=1,color="#484848")
        ax.set(title=f"{label} | {r.night} | {r.device} / {r.marker} / {r.axis}",ylabel="mm",xlabel="Hours after 22:00 (UTC+8)")
        ax.grid(alpha=.2); ax.legend(ncol=3,fontsize=8)
    fig.savefig(dest/"bad_cases.png",dpi=145);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("cache","candidate","work","results"):p.add_argument("--"+arg,required=True,type=Path)
    p.add_argument("--collect",type=Path,help="write causal train features/targets")
    p.add_argument("--identity",action="store_true",help="exact identity event control")
    p.add_argument("--device",action="append",help="optional subset for smoke tests")
    p.add_argument("--await-cache",action="store_true",help="consume each expected device as its atomic output becomes available")
    a=p.parse_args(); folder=a.work.resolve(); dest=a.results.resolve()
    folder.mkdir(parents=True,exist_ok=True);dest.mkdir(parents=True,exist_ok=True)
    exe=folder/"stream.exe"
    subprocess.run(["g++","-std=c++17","-O2","-I"+str(a.candidate.resolve()),str(HERE/"stream.cpp"),
                    "-o",str(exe),"-lpsapi"],check=True)
    allrows=[];allday=[];bench=[];sample=[];events=[]
    files=[a.cache/(d+".npz") for d in sorted(a.device or LEFT|RIGHT)]
    for path in files:
        if a.await_cache:
            deadline=time.monotonic()+3600
            while not path.exists() and time.monotonic()<deadline:time.sleep(2)
        device=path.stem
        ts,v,names=load(path)
        out,ref,b,s=native(exe,folder,ts,v,collect=bool(a.collect))
        bench.append(dict(device=device,**b))
        rows,day=score(ts,v,out,ref,names,device);allrows+=rows;allday+=day
        np.savez(folder/(device+".npz"),out=out,ref=ref)
        if s is not None:sample.append(s)
        if not a.identity:
            events+=injections(exe,folder,ts,v,out,names,device)
        print(device,len(ts),len(rows),flush=True)
    if sample:
        merged=np.concatenate(sample);np.savez(a.collect,features=merged[:,:5],target=merged[:,5])
    cells=pd.DataFrame(allrows,columns=COLS);day=pd.DataFrame(allday,columns=DAYCOLS)
    cells.to_csv(dest/"per_cell.csv.gz",index=False,compression={"method":"gzip","mtime":0})
    day.to_csv(dest/"daytime.csv",index=False)
    pd.DataFrame(bench).to_csv(dest/"native_benchmark.csv",index=False)
    ev=pd.DataFrame(events,columns="device night marker axis case count median_ratio min_ratio".split())
    ev.to_csv(dest/"injections.csv",index=False)
    totals={}
    for split,g in cells.groupby("split"):
        groups={"all":g,**dict(list(g.groupby("axis"))),**dict(list(g.groupby("line")))}
        totals[split]={k:summary(w) for k,w in groups.items()}
    (dest/"metrics.json").write_text(json.dumps(totals,indent=2,allow_nan=False)+"\n")
    figures(cells[cells.split=="test"],a.cache,folder,dest)


if __name__=="__main__": main()
