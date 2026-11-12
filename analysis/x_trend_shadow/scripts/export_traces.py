from common import *
import concurrent.futures

def one(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;src=load_data(line,dev);d=np.load(folder/'normal.npz');c=np.load(folder/'final_candidates.npz');t=src['t'];names=src['names'].tolist();lookup={n:i for i,n in enumerate(names)};timeindex=pd.Index(t);base=d['base'];w3=d['w3'];ys=d['y'];new=c['out'];events=c['event'];status=pd.read_csv(folder/'normal_frames.csv');h,night=clocks(t);source=pd.read_pickle(OLD/f'validation_{line}_{dev}.pkl');ix=timeindex.get_indexer(source.timestamp.to_numpy());assert (ix>=0).all();in_window=((h[ix]>=23)|(h[ix]<7+1/3));source=source.loc[in_window].copy();source['night']=night[ix[in_window]];counts=[]
 for date,group in source.groupby('night',sort=True):
  if date<'2026-11-05':continue
  j=timeindex.get_indexer(group.timestamp.to_numpy());k=np.array([lookup[n] for n in group.markerName]);order=np.lexsort((k,j));group=group.iloc[order];j=j[order];k=k[order];v=pd.DataFrame({'timestamp_ms':t[j],'marker_name':group.markerName.to_numpy(),'RoiCalState':group.RoiCalState.to_numpy(),'rawX_mm':src['x'][j,k],'stored_calX_mm':np.where(np.isfinite(src['x'][j,k]),src['field'][j,k],np.nan),'B0_original_mm':base[j,k],'W3_original_mm':w3[j,k],'A_thermal_mm':new[j,k,0],'B_event_mm':new[j,k,1],'C_reference_mm':new[j,k,2],'D_L1trend_mm':new[j,k,3],'D_W3_L1trend_mm':new[j,k,4],'E_residual_factor_mm':new[j,k,5],'originalY_mm':ys[j,k],'base_gate':status.base_gate.to_numpy()[j],'base_ready':status.base_ready.to_numpy()[j],'original_core_state':status.base_state.to_numpy()[j],'event_recorded':events[j,k].astype(int),'source_db':group.source_db.to_numpy(),'source_rowid':group._source_rowid.to_numpy()});save_parts(v,f'traces/{line}_{dev}_{date}.csv');counts.append(dict(line=line,device_id=dev,night=date,rows=len(v),source_observation_rows_only=True,start_beijing=iso(t[j[0]]),end_beijing=iso(t[j[-1]]),scope='23:00-next07:20; absolute mm; no filled observations',files_prefix=f'traces/{line}_{dev}_{date}'));print('TRACES',line,dev,date,len(v),flush=True)
 return counts

if __name__=='__main__':
 allrows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for rows in pool.map(one,roster()):allrows.extend(rows)
 save(allrows,'trace_catalog.csv')
