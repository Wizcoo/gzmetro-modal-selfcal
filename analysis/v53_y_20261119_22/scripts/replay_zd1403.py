"""Build V53, replay the included device case, and verify calY against the database."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
V53 = ROOT.parents[1] / "versions" / "V53"
TZ = timezone(timedelta(hours=8))
POINT = "ZD1403"
STATE_MAGIC = b"MSC_STATE_V50R\n"


def read_state(path):
    buf = path.read_bytes()
    assert buf.startswith(STATE_MAGIC)
    pos = len(STATE_MAGIC)

    def number():
        nonlocal pos
        value = struct.unpack_from("<Q", buf, pos)[0]
        pos += 8
        return value

    def string():
        nonlocal pos
        length = number()
        value = buf[pos:pos + length].decode("utf-8")
        pos += length
        return value

    version, timestamp = number(), number()
    device, config = string(), string()
    names = [string() for _ in range(number())]
    _, y_axis = string(), string()
    assert pos + 8 == len(buf)

    def point_history(axis):
        history = []
        for item in axis.split("hist_night_id=")[1:]:
            lines = item.splitlines()
            fields = dict(line.split("=",1) for line in lines[1:] if "=" in line)
            marker_names = fields["hist_names"].split(",")
            i = marker_names.index(POINT)
            diag = i * len(marker_names) - i * (i - 1) // 2
            night = (datetime(1970,1,1) + timedelta(days=int(lines[0]))).date().isoformat()
            count = int(float(fields["hist_N"].split(",")[diag]))
            history.append((night,count,int(fields["hist_n_frames"])))
        return history
    return version,timestamp,device,config,names,point_history(y_axis)


def stamp(day):
    return int(datetime(2026,11,day,22,tzinfo=TZ).timestamp() * 1000)


def write_input(path, device, names, raw):
    make = lambda key: raw.pivot(index="timestamp_ms",columns="marker_name",values=key).sort_index().reindex(columns=names)
    mask = make("roi").eq(1)
    x = make("x_mm").where(mask).to_numpy(dtype="<f8",copy=True)
    y = make("y_mm").where(mask).to_numpy(dtype="<f8",copy=True)
    x[~np.isfinite(x)] = np.nan
    y[~np.isfinite(y)] = np.nan
    with path.open("wb") as stream:
        def u64(n):
            stream.write(struct.pack("<Q",int(n)))
        def text(value):
            encoded = value.encode("utf-8")
            u64(len(encoded))
            stream.write(encoded)
        stream.write(b"MSC_OFFLINE_INPUT_V1\n")
        text(device)
        u64(len(names))
        for name in names:
            text(name)
        u64(len(mask))
        for i,ts in enumerate(mask.index):
            u64(ts)
            stream.write(x[i].tobytes())
            stream.write(y[i].tobytes())


def comparison(raw, result, history, cfg):
    joined = raw.merge(result,left_on=["timestamp_ms","marker_name"],right_on=["timestamp","markerName"],
                       validate="one_to_one")
    assert len(joined) == raw.timestamp_ms.ge(stamp(19)).sum()
    report = []
    for day in (19,20,21,22):
        offset = (joined.timestamp_ms - stamp(day)) / 60_000
        core = joined[offset.ge(80) & offset.lt(540) & joined.roi.eq(1)]
        pt = core[core.marker_name.eq(POINT)]
        count = sum(n for _,n,_ in history)
        total = sum(n for _,_,n in history)
        diff = abs(core.replayY - core.cal_y_mm)
        assert diff.max() < 1e-9 and len(pt)
        report.append({
            "night":f"2026-11-{day}",
            "history": [list(item) for item in history],
            "point_learning_valid":count,
            "pooled_learning_frames":total,
            "point_learning_ratio":count/total,
            "configured_minimum_ratio":float(cfg.split(",")[11]),
            "all_valid_observations":len(core),
            "max_abs_replay_error_mm":float(diff.max()),
            "point_valid_observations":len(pt),
            "point_corrected_observations":int(pt.correctionY.abs().gt(1e-7).sum()),
        })
        learned = joined[offset.ge(0) & offset.lt(240)]
        roi_good = learned.roi.eq(1) & np.isfinite(learned.y_mm)
        frames = learned.loc[roi_good,"timestamp_ms"].nunique()
        count_new = int((roi_good & learned.marker_name.eq(POINT)).sum())
        history = history[1:] + [(f"2026-11-{day}",count_new,frames)]
    assert [r["point_corrected_observations"] for r in report] == [207,257,0,0]
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compiler",default="g++")
    ap.add_argument("--output",type=Path,default=ROOT/"evidence"/"native_replay_zd1403.json")
    args = ap.parse_args()
    src = ROOT/"data"/"replay_zd1403"
    seed = src/"initial.state"
    raw = pd.read_csv(src/"device_frames.csv",float_precision="round_trip")
    _,ts,device,config,names,history = read_state(seed)
    assert ts == 1795083152141 and device == "780638271319" and len(names) == 34
    with tempfile.TemporaryDirectory(prefix="v53_y_replay_") as temp:
        work = Path(temp)
        write_input(work/"frames.bin",device,names,raw)
        shutil.copyfile(seed,work/"initial.state")
        exe = work/"replay.exe"
        subprocess.run([args.compiler,"-std=c++17","-O2",f"-I{V53}",
                        str(ROOT/"scripts"/"replay_with_state.cpp"),str(V53/"ModalSelfCal.cpp"),"-o",exe.name],
                       check=True,cwd=work)
        native = subprocess.run([str(exe),"frames.bin","initial.state","0","points.csv","timeline.csv",
                                 str(stamp(19)),"after.state"],check=True,cwd=work,text=True,capture_output=True)
        print(native.stdout.strip())
        result = pd.read_csv(work/"points.csv",float_precision="round_trip")
        comparisons = comparison(raw,result,history,config)
    output = {"device_id":device,"point":POINT,"seed_timestamp_ms":ts,
              "math_config":config,"core_local_window":"23:20 to next day 07:00",
              "nights":comparisons}
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for r in comparisons:
        print(r["night"],"history ratio",f'{r["point_learning_ratio"]:.2%}',
              "point corrected",r["point_corrected_observations"],"of",r["point_valid_observations"],
              "max error mm",r["max_abs_replay_error_mm"])


if __name__ == "__main__":
    main()
