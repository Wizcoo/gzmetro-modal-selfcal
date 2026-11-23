"""Compare full-stream and prefix outputs, including a sparse point and a camera outage."""
from pathlib import Path
import argparse
import subprocess
import tempfile
import numpy as np
from evaluate import HERE, native

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--candidate",type=Path,required=True)
p.add_argument("--scratch",type=Path,required=True)
a=p.parse_args()
a.scratch.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=a.scratch) as temp:
    work=Path(temp).resolve()
    exe=work/"stream.exe"
    subprocess.run(["g++","-O2","-std=c++17","-I"+str(a.candidate.resolve()),
                    str(HERE/"stream.cpp"),"-o",str(exe),"-lpsapi"],check=True)
    rng=np.random.default_rng(17)
    ts=np.arange(1793145600000,1794528000000,60000,dtype=np.int64)
    t=(ts//60000+480)%1440
    v=rng.normal(0,.015,(len(ts),2,4))
    v+=(((t>=1320)|(t<480))*.35)[:,None,None]
    v[1000:1689,:,1]=np.nan
    ts,v=np.delete(ts,np.s_[2100:2211]),np.delete(v,np.s_[2100:2211],axis=0)
    full=native(exe,work,ts,v,True)
    cutoff=int(np.searchsorted(ts,1794009600000))
    for stop in (cutoff,cutoff+3000):
        prefix=native(exe,work,ts[:stop],v[:stop],True)
        for j in (0,1):
            np.testing.assert_array_equal(prefix[j],full[j][:stop])
        np.testing.assert_array_equal(prefix[3],full[3])
    assert full[3].shape[0]>0
    assert np.array_equal(np.isfinite(v),np.isfinite(full[0]))
    day=((ts//60000+480)%1440>=600)&((ts//60000+480)%1440<960)
    np.testing.assert_array_equal(full[0][day],v[day])
print("PASS: identical prefixes, frozen training samples, missing masks and daylight outputs")
