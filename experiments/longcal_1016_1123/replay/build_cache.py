"""Build one verified chronological native replay per device, Windows x86-64."""
import argparse
import ctypes as C
from datetime import datetime, timedelta, timezone
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import numpy as np
import pandas as pd

TZ = timezone(timedelta(hours=8))
CONFIG = json.loads(Path(__file__).with_name("replay_config.json").read_text(encoding="utf8"))
START = int(datetime.fromisoformat(CONFIG["start_inclusive"]).timestamp()*1000)
END = int(datetime.fromisoformat(CONFIG["end_exclusive"]).timestamp()*1000)
DEVICES = CONFIG["devices"]
SQLROW = np.dtype([("ts","<i8"), ("x","<f8"), ("y","<f8"), ("index","<i4"), ("name","S36")])
COMPACT = np.dtype([("ts","<i8"), ("x","<f8"), ("y","<f8"), ("index","<i4"), ("name","<i4")])
HASHES = CONFIG["v53_sha256"]

def iso(ts):
    return datetime.fromtimestamp(ts/1000,TZ).isoformat(timespec="seconds")

def coalesce_errors(stats):
    intervals=stats["unreadable"]
    stats["failed_terminal_queries"]=len(intervals)
    merged=[]
    for lo,hi,reason in intervals:
        if merged and merged[-1][1]==lo and merged[-1][2]==reason: merged[-1][1]=hi
        else: merged.append([lo,hi,reason])
    stats["unreadable"]=merged

def sql_reader(work):
    # Locate MinGW SQLite and C++ runtime dependencies in the compiler directory.
    dll_directory=os.add_dll_directory(str(Path(shutil.which("g++")).parent))
    library=C.CDLL(str(work/"read_rows.dll"))
    library.read_rows.argtypes=[C.c_char_p,C.c_char_p,C.c_int64,C.c_int64,C.POINTER(C.c_void_p)]
    library.read_rows.restype=C.c_int
    library.read_error.restype=C.c_char_p
    return dll_directory,library

def read_shard(lib,path,device,report):
    table=f"Marker_{device}"
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)) as con:
        con.execute("PRAGMA writable_schema=ON")
        tables=con.execute("select name from sqlite_master where type='table' and name=?",(table,)).fetchone()
        if not tables: return []
        try:
            lo=con.execute(f"select timestamp from {table} order by timestamp limit 1").fetchone()
            hi=con.execute(f"select timestamp from {table} order by timestamp desc limit 1").fetchone()
            if not lo or not hi: return []
            lo,hi=max(START,lo[0]),min(END,hi[0]+1)
        except sqlite3.DatabaseError:
            # An incomplete index can make even the file endpoints unreadable.
            # Scan the entire requested interval; terminal errors are audited.
            lo,hi=START,END
    if lo>=hi: return []
    before=path.stat()
    stats={"shard":path.name,"line_source_lo":iso(lo),"line_source_hi":iso(hi-1),"rows":0,"unreadable":[]}
    def window(a,b):
        ptr=C.c_void_p()
        count=lib.read_rows(str(path).encode(),device.encode(),a,b,C.byref(ptr))
        if count>=0:
            stats["rows"]+=count
            if not count: return []
            return [np.frombuffer((C.c_char*(count*SQLROW.itemsize)).from_address(ptr.value),dtype=SQLROW).copy()]
        reason=lib.read_error().decode(errors="replace")
        if "unsupported marker name" in reason or b-a<=60000:
            if "unsupported marker name" in reason: raise ValueError(reason)
            stats["unreadable"].append([a,b,reason])
            return []
        mid=a+(b-a)//2
        return window(a,mid)+window(mid,b)
    pieces=window(lo,hi)
    after=path.stat()
    if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
        raise ValueError(f"Input changed: {path}")
    coalesce_errors(stats)
    report.append(stats)
    return pieces

def observations(root,work,line,device,report):
    folder=root/"左线"/"NewDevice" if line=="left" else root/"右线"
    cookie,lib=sql_reader(work)
    names={}
    chunks=[]
    for path in sorted(folder.glob("*DataBaseFile*.db")):
        for a in read_shard(lib,path,device,report):
            codes,labels=pd.factorize(a["name"])
            ids=np.array([names.setdefault(v.decode(),len(names)) for v in labels])
            out=np.empty(len(a),dtype=COMPACT)
            for field in ("ts","x","y","index"): out[field]=a[field]
            out["name"]=ids[codes]
            chunks.append(out)
    cookie.close()
    data=np.concatenate(chunks)
    ts,frames=np.unique(data["ts"],return_inverse=True)
    cols=data["name"]
    shape=(len(ts),len(names))
    key=frames*len(names)+cols
    repeat=pd.Series(key).duplicated(keep=False).to_numpy()
    dense=[np.full(shape,np.nan) for _ in range(2)]
    index=np.full(shape,-1,dtype=np.int32)
    index[frames,cols]=data["index"]
    conflicts={}
    for field,array in zip(("x","y"),dense):
        array[frames,cols]=data[field]
        dup=pd.DataFrame({"key":key[repeat],"v":data[field][repeat]})
        variants=dup.groupby("key").v.nunique(dropna=False)
        different=variants.index[variants>1].to_numpy(dtype=np.int64)
        array.flat[different]=np.nan
        array[~np.isfinite(array)]=np.nan
        conflicts[field]=len(different)
    counts={"read_rows":len(data),"unique_cells":int((index>=0).sum()),"conflicting_axes_excluded":conflicts}
    return ts,np.array(list(names)),index,*dense,counts

def segments(index):
    # Process runs of identical observed membership. The 60th consecutive
    # absence triggers removal, independently of how long the run eventually is.
    seen=index>=0
    edges=np.r_[0,np.nonzero(np.any(seen[1:]!=seen[:-1],axis=1))[0]+1,len(seen)]
    active=set()
    gaps=np.zeros(index.shape[1],int)
    last_index=np.zeros(index.shape[1],int)
    pieces=[]
    for a,b in zip(edges[:-1],edges[1:]):
        row=seen[a]
        observed=set(np.where(row)[0])
        last_index[row]=index[a,row]
        gaps[row]=0
        active|=observed
        drops={}
        for j in active-observed:
            offset=CONFIG["absent_rows_before_roster_removal"]-1-gaps[j]
            if offset<b-a:
                drops.setdefault(a+max(0,offset),set()).add(j)
        for t in sorted({a,*drops}):
            active-=drops.get(t,set())
            roster=tuple(sorted(active,key=lambda j:(last_index[j],j)))
            if not pieces or set(roster)!=set(pieces[-1][1]): pieces.append((t,roster))
        gaps[~row]+=b-a
    return pieces

def run_one(args,line,device):
    source=[]
    ts,names,index,x,y,counts=observations(args.root,args.work,line,device,source)
    piece=segments(index)
    folder=args.work/device
    folder.mkdir(exist_ok=True)
    vx=np.full_like(x,np.nan); vy=np.full_like(y,np.nan)
    runs=[]
    for i,(a,roster) in enumerate(piece):
        b=piece[i+1][0] if i+1<len(piece) else len(ts)
        cols=list(roster)
        p=len(cols)
        raw=np.empty(b-a,dtype=[("ts","<i8"),("x","<f8",(p,)),("y","<f8",(p,))])
        raw["ts"]=ts[a:b]; raw["x"]=x[a:b,cols]; raw["y"]=y[a:b,cols]
        raw.tofile(folder/"input.bin")
        (folder/"names.txt").write_text("\n".join(names[cols])+"\n",encoding="utf8")
        proc=subprocess.run([str(args.work/"replay.exe"),device,"names.txt","input.bin","output.bin"],
                            cwd=folder,check=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        native=np.fromfile(folder/"output.bin",dtype="<f8").reshape(b-a,2,p)
        vx[a:b,cols]=native[:,0,:]; vy[a:b,cols]=native[:,1,:]
        lines=proc.stdout.splitlines()
        n,rss_before,rss_peak,micros,worst,checkpoint=map(float,lines[0].split())
        states={"x":{},"y":{}}
        for s in lines[1:]:
            axis,status,count=s.split()
            states[axis][status]=int(count)
        if int(n)!=b-a: raise ValueError("frame count mismatch")
        runs.append(dict(start=iso(ts[a]),end=iso(ts[b-1]),points=p,frames=b-a,
                         admitted=sorted(set(names[cols])-set(names[list(piece[i-1][1])])) if i else list(names[cols]),
                         removed=sorted(set(names[list(piece[i-1][1])])-set(names[cols])) if i else [],
                         rss_pre_init=int(rss_before),rss_peak=int(rss_peak),process_us=micros,max_us=worst,
                         final_state_bytes=int(checkpoint),states=states))
    if not np.array_equal(np.isfinite(vx),np.isfinite(x)) or not np.array_equal(np.isfinite(vy),np.isfinite(y)):
        raise ValueError("V53 output availability differs from input")
    if (np.diff(ts)<=0).any(): raise ValueError("non-monotonic timestamp")
    tmp=args.cache/(device+".partial.npz")
    np.savez(tmp,ts=ts,names=names,x=vx,y=vy)
    tmp.replace(args.cache/(device+".npz"))
    minute=np.unique(ts//60000)
    gaps=np.where(np.diff(minute)>30)[0]
    report=dict(device=device,line=line,first=iso(ts[0]),last=iso(ts[-1]),frames=len(ts),minutes=len(minute),
                channel_union=len(names),gaps_over_30min=[[iso(minute[k]*60000),iso(minute[k+1]*60000)] for k in gaps],
                valid_x=int(np.isfinite(vx).sum()),valid_y=int(np.isfinite(vy).sum()),**counts,epochs=runs,shards=source)
    (args.results/(device+".json")).write_text(json.dumps(report,indent=2,ensure_ascii=False,default=int),encoding="utf8")
    print("READY",device,line,len(ts),len(names),len(runs),flush=True)
    return device

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("root","v53","cache","work","results"): parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--jobs",type=int,default=2)
    parser.add_argument("--devices",nargs="+")
    args=parser.parse_args()
    for key in ("root","v53","cache","work","results"): setattr(args,key,getattr(args,key).resolve())
    for path in (args.cache,args.work,args.results): path.mkdir(parents=True,exist_ok=True)
    for name,expected in HASHES.items():
        if hashlib.sha256((args.v53/name).read_bytes()).hexdigest()!=expected: raise ValueError("V53 source hash: "+name)
    src=Path(__file__).resolve().parent
    subprocess.run(["g++","-O2","-std=c++17","-shared",str(src/"read_rows.cpp"),"-lsqlite3","-o",str(args.work/"read_rows.dll")],check=True)
    subprocess.run(["g++","-O2","-std=c++17","-I"+str(args.v53),str(src/"replay.cpp"),str(args.v53/"ModalSelfCal.cpp"),
                    "-lpsapi","-o",str(args.work/"replay.exe")],check=True)
    jobs=[(line,dev) for line,devices in DEVICES.items() for dev in devices if not args.devices or dev in args.devices]
    if args.devices and len(set(args.devices))!=len(jobs): raise ValueError("unknown device")
    with ProcessPoolExecutor(args.jobs) as pool:
        futures=[pool.submit(run_one,args,line,dev) for line,dev in jobs]
        for f in futures: f.result()

if __name__=="__main__": main()
