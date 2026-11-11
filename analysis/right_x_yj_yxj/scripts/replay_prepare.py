from relations import *
import struct,subprocess
def main():
    assert epoch('2026-11-07 03:00')==1793991600000
    cache=W/'replay_cache';cache.mkdir(exist_ok=True)
    for dev in DEVS:
        d=pd.read_pickle(C/f'Marker_{dev}.pkl');names=sorted(d.markerName.unique());piv=d.pivot(index='timestamp',columns='markerName',values=['x','y','RoiCalState']);t=piv.index.to_numpy();x=piv.x.reindex(columns=names).to_numpy(dtype=float,copy=True);y=piv.y.reindex(columns=names).to_numpy(dtype=float,copy=True);ok=piv.RoiCalState.reindex(columns=names).to_numpy()==1;x[~ok]=np.nan;y[~ok]=np.nan
        with (cache/f'{dev}.bin').open('wb') as f:
            f.write(struct.pack('<I',len(names)))
            for n in names:b=n.encode();f.write(struct.pack('<I',len(b)));f.write(b)
            f.write(struct.pack('<I',len(t)))
            for i,ts in enumerate(t):f.write(struct.pack('<q',ts));f.write(x[i].astype('<f8').tobytes());f.write(y[i].astype('<f8').tobytes())
    print('Controlled replay inputs prepared. No production state read or written.')
if __name__=='__main__':main()
