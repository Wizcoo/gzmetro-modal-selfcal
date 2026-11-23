"""Raw vs original V53 for the highest-variance eligible test case of one replay epoch."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def plot(epoch,dest):
    names=(epoch/"names.txt").read_text(encoding="utf8").splitlines()
    p=len(names)
    raw=np.fromfile(epoch/"input.bin",dtype=[("ts","<i8"),("x","<f8",(p,)),("y","<f8",(p,))])
    native=np.fromfile(epoch/"output.bin","<f8").reshape(-1,2,p)
    times=pd.to_datetime(raw["ts"],unit="ms",utc=True).tz_convert("Asia/Shanghai")
    best=None
    for day in pd.date_range("2026-11-15","2026-11-22",tz="Asia/Shanghai"):
        rows=(times>=day+pd.Timedelta(hours=22)) & (times<day+pd.Timedelta(hours=32))
        for axis in range(2):
            for marker in range(p):
                values=native[rows,axis,marker]
                ts=raw["ts"][rows][np.isfinite(values)]
                if len(np.unique(ts//60000))<480: continue
                var=np.nanvar(values)
                if best is None or var>best[0]: best=(var,day,axis,marker,rows)
    if best is None: raise ValueError("no eligible test nights")
    variance,day,axis,marker,rows=best
    field="xy"[axis]
    t=times[rows]
    fig,axes=plt.subplots(2,1,figsize=(9.5,5.5),height_ratios=(3,1),sharex=True,layout="constrained")
    axes[0].plot(t,raw[field][rows,marker],label="Raw input",linewidth=1.15,color="#777d83")
    axes[0].plot(t,native[rows,axis,marker],label="Native V53",linewidth=1.3,color="#175a91")
    axes[1].plot(t,raw[field][rows,marker]-native[rows,axis,marker],color="#b55318",linewidth=1.15)
    axes[1].axhline(0,color="#aaa",linewidth=.7)
    axes[0].legend(loc="best")
    axes[0].set_title(f"{epoch.name} / {names[marker]} / {field.upper()}     Night of {day.date()}",loc="left")
    axes[0].set_ylabel(f"{field.upper()} (mm)"); axes[1].set_ylabel("Raw − V53 (mm)")
    axes[1].set_xlabel("Local time (UTC+8)")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M",tz=t.tz))
    for ax in axes: ax.grid(axis="y",alpha=.22)
    dest.parent.mkdir(exist_ok=True,parents=True); fig.savefig(dest,dpi=145); plt.close(fig)
    print(day.date(),names[marker],field,variance,np.nanvar(raw[field][rows,marker]))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epoch",type=Path); parser.add_argument("dest",type=Path)
    a=parser.parse_args(); plot(a.epoch,a.dest)
