from common import *
if __name__=='__main__':
 changed=[]
 for q in roster():
  folder=W/q['line']/q['device_id'];p=folder/'extended_candidates.npz'
  if not p.exists():continue
  with np.load(p) as d:
   if 'night_blend_version' in d:continue
   v={k:d[k].copy() for k in d.files}
  normal=np.load(folder/'normal.npz');st=pd.read_csv(folder/'normal_frames.csv');h,_=clocks(normal['t']);g=st.base_gate.to_numpy()*st.base_ready.to_numpy()*st.base_ncorrected.gt(0).to_numpy()*((h>=23)|(h<7+1/3));v['out'][:,:,4]=normal['base']+g[:,None]*(v['out'][:,:,4]-normal['base']);v['eligible'][:,:,4]&=g[:,None]>0;v['night_blend_version']=1;np.savez_compressed(p,**v);changed.append(q['device_id'])
 save_json({'applied_to':changed,'contract':'All new trend channels equal original B0 in daytime. W3-only historical comparator remains a separate full-history control. D_W3 = B0+g_B0*(inner_L1_W3-B0), preserving original night taper.','ABC_and_D_B0_math_unchanged':True},'night_boundary_contract.json')
