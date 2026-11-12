from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');a=p.parse_args()
for q in roster():
 if a.focus and q['device_id'] not in FOCUS:continue
 folder=W/q['line']/q['device_id'];p=folder/'factor.npz'
 if not p.exists():continue
 c=np.load(folder/'extended_candidates.npz');e=np.load(p);d={k:c[k] for k in c.files};d['out']=np.concatenate([d['out'],e['out'][:,:,None]],axis=2);d['eligible']=np.concatenate([d['eligible'],e['eligible'][:,:,None]],axis=2);np.savez_compressed(folder/'final_candidates.npz',**d)
