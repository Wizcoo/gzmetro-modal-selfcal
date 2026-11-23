"""Summarize the native V53 run. No raw frame products are published."""
import argparse
import csv
import json
import platform
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from build_cache import DEVICES, HASHES

def summarize(args):
    rows=[]
    daily=[]
    process_us=0
    largest_peak=0
    largest_delta=0
    largest_state=0
    total_states={"x":Counter(),"y":Counter()}
    for line,devices in DEVICES.items():
        for device in devices:
            report=json.loads((args.provenance/(device+".json")).read_text(encoding="utf8"))
            with np.load(args.cache/(device+".npz"),allow_pickle=False) as data:
                ts=data["ts"]
                x,y=data["x"],data["y"]
                if args.check:
                    with np.load(args.check/(device+".npz"),allow_pickle=False) as repeat:
                        for key in data.files:
                            a=data[key]; b=repeat[key]
                            if a.dtype.kind=="f":
                                np.testing.assert_array_equal(a.view(np.uint64),b.view(np.uint64))
                            else: np.testing.assert_array_equal(a,b)
                assert np.all(ts[1:]>ts[:-1]) and len(ts)==report["frames"]
                assert len(set(data["names"]))==x.shape[1] and x.shape==y.shape
                assert np.isfinite(x).sum()==report["valid_x"] and np.isfinite(y).sum()==report["valid_y"]
                times=pd.to_datetime(ts,unit="ms",utc=True).tz_convert("Asia/Shanghai")
                d=times.normalize(); hour=times.hour
                for day in pd.date_range("2026-10-16","2026-11-23",tz="Asia/Shanghai"):
                    day_mask=(d==day)
                    night=(times>=day+pd.Timedelta(hours=22))&(times<day+pd.Timedelta(hours=32))
                    stable=day_mask&(hour>=10)&(hour<16)
                    daily.append(dict(line=line,device=device,date=day.date(),
                                      minutes=len(np.unique(ts[day_mask]//60000)),
                                      anchor_window_minutes=len(np.unique(ts[stable]//60000)),
                                      night_minutes=len(np.unique(ts[night]//60000))))
            epochs=report["epochs"]
            elapsed=sum(k["process_us"] for k in epochs)
            process_us+=elapsed
            peak=max(k["rss_peak"] for k in epochs)
            delta=max(k["rss_peak"]-k["rss_pre_init"] for k in epochs)
            state=max(k["final_state_bytes"] for k in epochs)
            largest_peak=max(largest_peak,peak)
            largest_delta=max(largest_delta,delta)
            largest_state=max(largest_state,state)
            for k in epochs:
                for axis in ("x","y"): total_states[axis].update(k["states"][axis])
            rows.append(dict(line=line,device=device,frames=report["frames"],minutes=report["minutes"],
                            points=report["channel_union"],valid_x=report["valid_x"],valid_y=report["valid_y"],
                            sql_rows=report["read_rows"],duplicate_rows=report["read_rows"]-report["unique_cells"],
                            conflicts_x=report["conflicting_axes_excluded"]["x"],
                            conflicts_y=report["conflicting_axes_excluded"]["y"],epochs=len(epochs),
                            unreadable_ranges=sum(len(k["unreadable"]) for k in report["shards"]),
                            mean_frame_ms=elapsed/(1000*report["frames"]),peak_MiB=peak/2**20,
                            peak_delta_MiB=delta/2**20,largest_epoch_end_state_KiB=state/1024))
    args.out.mkdir(exist_ok=True,parents=True)
    for filename,data in (("device_replay.csv",rows),("calendar_coverage.csv",daily)):
        with (args.out/filename).open("w",encoding="utf8",newline="") as fp:
            writer=csv.DictWriter(fp,data[0].keys()); writer.writeheader(); writer.writerows(data)
    frames=sum(r["frames"] for r in rows)
    numbers=dict(devices=len(rows),frames=frames,valid_x=sum(r["valid_x"] for r in rows),
                 valid_y=sum(r["valid_y"] for r in rows),read_rows=sum(r["sql_rows"] for r in rows),
                 duplicate_rows=sum(r["duplicate_rows"] for r in rows),
                 conflicting_x=sum(r["conflicts_x"] for r in rows),conflicting_y=sum(r["conflicts_y"] for r in rows),
                 unreadable_query_ranges=sum(r["unreadable_ranges"] for r in rows),
                 roster_resets=sum(r["epochs"]-1 for r in rows),states=total_states,
                 v53_source_sha256=HASHES,model_weight_bytes=0,mean_native_ms=process_us/1000/frames,
                 process_peak_MiB=largest_peak/2**20,process_peak_minus_pre_init_peak_MiB=largest_delta/2**20,
                 max_serialized_epoch_end_state_KiB=largest_state/1024,
                 replay_exe_bytes=args.binary.stat().st_size,
                 cpu_arch=platform.machine(),system=platform.platform(),
                 independent_binary_replay_exact_match=bool(args.check))
    (args.out/"native_summary.json").write_text(json.dumps(numbers,indent=2)+"\n",encoding="utf8")
    print(json.dumps(numbers,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("provenance","cache","out","binary"): p.add_argument("--"+n,type=Path,required=True)
    p.add_argument("--check",type=Path)
    summarize(p.parse_args())
