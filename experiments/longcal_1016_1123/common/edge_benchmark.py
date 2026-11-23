"""Paired fresh x86 processes. Use last original-V53 roster epoch for each device."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import time

p=argparse.ArgumentParser(description=__doc__)
for key in ("candidate","v53","segments","work","out"):p.add_argument("--"+key,required=True,type=Path)
p.add_argument("--baseline-only",action="store_true")
p.add_argument("--await-segments",action="store_true",help="consume one finalized epoch directory at a time")
a=p.parse_args()
a.work.mkdir(parents=True,exist_ok=True)
exe=(a.work/"edge_benchmark.exe").resolve()
subprocess.run(["g++","-std=c++17","-O2","-I"+str(a.candidate.resolve()),"-I"+str(a.v53.resolve()),
                str(Path(__file__).with_suffix(".cpp").resolve()),str(a.v53.resolve()/"ModalSelfCal.cpp"),
                "-o",str(exe),"-lpsapi"],check=True)
rows=[]
ids="780630499846 780637798298 780638271319 780638310097 780638327479 780638349768 780639173835 780639298317 780639333715 780639346578 780639376393 780639414923".split()
devices=[a.segments/i for i in ids] if a.await_segments else sorted(path for path in a.segments.iterdir() if path.is_dir() and path.name.isdigit())
if len(devices)!=12:raise ValueError("Expected final real input epoch for each of the 12 devices")
for d in devices:
    if a.await_segments:
        deadline=time.monotonic()+3600
        while not (d/"input.bin").exists() and time.monotonic()<deadline:time.sleep(2)
    for mode in (("baseline",) if a.baseline_only else ("baseline","candidate")):
        run=subprocess.run([str(exe),d.name,str(d/"names.txt"),str(d/"input.bin"),mode],
                           check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        rows.append(dict(device=d.name,mode=mode,**json.loads(run.stdout)))
if not rows:raise ValueError("No real input epochs")
with a.out.open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
