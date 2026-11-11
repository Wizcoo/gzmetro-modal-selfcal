from pathlib import Path
import json,itertools
import pandas as pd,numpy as np
import os
O=Path(os.environ.get('YJ_ANALYSIS_OUTPUT',Path(__file__).resolve().parents[1]))
W=Path(os.environ.get('YJ_ANALYSIS_WORK',O/'.work'));W.mkdir(parents=True,exist_ok=True)
C=Path(os.environ.get('YJ_ANALYSIS_INPUT_CACHE',O.parent/'right_x'/'.cache'))
O.mkdir(parents=True,exist_ok=True)
TZ='Asia/Shanghai';DEVS=[p.stem.split('_')[1] for p in sorted(C.glob('Marker_780*.pkl'))]
def iso(t):return pd.Timestamp(t,unit='ms',tz='UTC').tz_convert(TZ).isoformat(timespec='milliseconds')
def epoch(s):return int(pd.Timestamp(s,tz=TZ).timestamp()*1000)
def write(d,name):
    p=O/name;p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False,encoding='utf-8',lineterminator='\n',float_format='%.12g')
    if p.stat().st_size>=1950000:raise ValueError('Split required '+str(p))
def load_refs():
    frames=[]
    for dev in DEVS:
        d=pd.read_pickle(C/f'Marker_{dev}.pkl');d=d[d.markerName.str.startswith(('YJ','YXJ'))].copy();d['observing_device_id']=dev
        d['channel']=dev+':'+d.markerName;d['valid']=d.RoiCalState.eq(1)&~d.ambiguous_business_key;frames.append(d)
    return pd.concat(frames,ignore_index=True)
def align(s,index,tol=2000):
    s=s[~s.index.duplicated()].sort_index();ix=s.index.get_indexer(index,method='nearest',tolerance=tol);out=np.full(len(index),np.nan);good=ix>=0;out[good]=s.to_numpy()[ix[good]];return out
def smooth(s,minutes=5,minp=3):
    s=s.sort_index();out=pd.Series(np.nan,index=s.index);t=s.index.to_numpy();runs=np.cumsum(np.r_[False,np.diff(t)>90000])
    for run in np.unique(runs):
        ix=np.flatnonzero(runs==run);z=pd.Series(s.iloc[ix].values,index=pd.to_datetime(t[ix],unit='ms',utc=True));out.iloc[ix]=z.rolling(f'{minutes}min',min_periods=minp).median().values
    return out
def pair_stats(a,b):
    ix=a.index;bv=align(b,ix);av=a.values;m=np.isfinite(av)&np.isfinite(bv)
    if m.sum()<20:return {'n':int(m.sum())}
    x=av[m];y=bv[m];xc=x-x.mean();yc=y-y.mean();slope=float(xc@yc/(xc@xc)) if xc@xc>1e-12 else np.nan
    r=float(np.corrcoef(x,y)[0,1]) if np.std(x)>1e-8 and np.std(y)>1e-8 else np.nan
    ts=ix.to_numpy()[m];dt=np.diff(ts);dx=np.diff(x);dy=np.diff(y);adj=(dt>=30000)&(dt<=90000)
    dr=float(np.corrcoef(dx[adj],dy[adj])[0,1]) if adj.sum()>20 and np.std(dx[adj])>1e-8 and np.std(dy[adj])>1e-8 else np.nan
    return {'n':int(m.sum()),'r':r,'slope_b_per_a':slope,'step_r':dr,'response_direction':'same' if slope>0 else 'opposite','residual_std_mm':float(np.std(y-(y.mean()+slope*xc))),'x_sd_mm':float(np.std(x)),'y_sd_mm':float(np.std(y))}
SEGMENTS=[('day_1105_pre',epoch('2026-11-05 07:20'),epoch('2026-11-05 11:30:19.758')),('day_1105_transition',epoch('2026-11-05 11:30:19.758'),epoch('2026-11-05 13:00')),('day_1105_post',epoch('2026-11-05 13:00'),epoch('2026-11-05 22:00')),('night_1105',epoch('2026-11-05 23:20'),epoch('2026-11-06 07:00')),('day_1106',epoch('2026-11-06 07:20'),epoch('2026-11-06 22:00')),('night_1106',epoch('2026-11-06 23:20'),epoch('2026-11-07 07:00')),('day_1107',epoch('2026-11-07 07:20'),epoch('2026-11-07 15:00'))]
def main():
    d=load_refs();d.to_pickle(W/'refs.pkl');rows=[];inv=[];edges=[];md=pd.read_pickle(C/'MarkerData.pkl')
    bound=md[md.deviceId.ne('')][['markerName','deviceId']].drop_duplicates().set_index('markerName').deviceId.to_dict()
    for (dev,name),g in d.groupby(['observing_device_id','markerName']):
        inv.append({'observing_device_id':dev,'marker_name':name,'kind':'YJ_physical_reference_user_context' if name.startswith('YJ') else 'YXJ_role_mount_unconfirmed','rows':len(g),'valid_rows':int(g.valid.sum()),'bound_device_id':bound.get(name,''),'bound_relation':'explicit_MarkerData_deviceId' if name in bound else 'not_available','same_device_as_bound':dev==bound.get(name),'start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'unit':'mm_API_contract_DB_writer_unavailable'})
        if name.startswith('YXJ'):edges.append({'observing_device_id':dev,'yxj_name':name,'explicit_MarkerData_bound_device':bound.get(name,''),'geometric_relation':'not_available','camera_mounting':'hypothesis_not_confirmed','same_name_multi_observer':int(d[d.markerName.eq(name)].observing_device_id.nunique())})
    write(pd.DataFrame(inv),'reference_inventory.csv');write(pd.DataFrame(edges),'yxj_observation_edges.csv')
    for seg,st,en in SEGMENTS:
        z=d[d.timestamp.ge(st)&d.timestamp.lt(en)&d.valid];series={}
        for ch,g in z.groupby('channel'):
            for field in ['x','calX']:
                s=pd.Series(g[field].values,index=g.timestamp.values).sort_index();series[(ch,field)]=s
        channels=sorted(z.channel.unique())
        for a,b in itertools.combinations(channels,2):
            da,na=a.split(':');db,nb=b.split(':')
            if na.startswith('YJ') and nb.startswith('YJ'):relation='YJ_within_device' if da==db else 'YJ_same_physical_name_cross_observer' if na==nb else 'YJ_cross_device_different_reference'
            elif na.startswith('YXJ') and nb.startswith('YXJ'):relation='YXJ_same_name_cross_observer' if na==nb else 'YXJ_different_nodes'
            else:relation='YJ_to_YXJ_local' if da==db else 'YJ_to_YXJ_remote'
            for field in ['x','calX']:
                for scale in ['native','trailing5min_median']:
                    av=series[(a,field)];bv=series[(b,field)]
                    if scale!='native':av=smooth(av);bv=smooth(bv)
                    r=pair_stats(av,bv);r.update({'segment':seg,'start_beijing':iso(st),'end_exclusive_beijing':iso(en),'channel_a':a,'channel_b':b,'relation':relation,'field':field,'time_scale':scale,'alignment':'nearest_real_timestamp_le2s_no_interpolation','coefficient_unit':'mm_per_mm','correlation_unit':'dimensionless'})
                    rows.append(r)
    r=pd.DataFrame(rows)
    for rel,g in r.groupby('relation'):write(g,f'relations/{rel}.csv')
    # Response coefficient changes are descriptions, not selection on validation.
    sub=r[(r.time_scale=='trailing5min_median')&r.segment.isin(['night_1105','night_1106'])]
    a=sub[sub.segment=='night_1105'];b=sub[sub.segment=='night_1106'];v=a.merge(b,on=['channel_a','channel_b','relation','field'],suffixes=('_train1105','_holdout1106'))
    v['sign_consistent']=np.sign(v.slope_b_per_a_train1105)==np.sign(v.slope_b_per_a_holdout1106)
    v['holdout_minus_train_slope']=v.slope_b_per_a_holdout1106-v.slope_b_per_a_train1105
    cols=['channel_a','channel_b','relation','field','r_train1105','r_holdout1106','slope_b_per_a_train1105','slope_b_per_a_holdout1106','sign_consistent','holdout_minus_train_slope','n_train1105','n_holdout1106']
    write(v[cols],'cross_night_response_stability.csv');r.to_pickle(W/'relations.pkl')
    print('within YJ smoothed raw by period')
    print(r[(r.relation=='YJ_within_device')&(r.field=='x')&(r.time_scale=='trailing5min_median')].groupby(['segment',r.channel_a.str.split(':').str[0]]).r.agg(['count','min','median','max']).to_string())
    print('same reference cross observers\n',r[(r.relation=='YJ_same_physical_name_cross_observer')&(r.field=='x')&(r.time_scale=='trailing5min_median')&r.segment.str.startswith('night')][['segment','channel_a','channel_b','r','slope_b_per_a']].to_string(index=False))
    print('YXJ shared\n',r[(r.relation=='YXJ_same_name_cross_observer')&(r.time_scale=='trailing5min_median')&r.segment.str.startswith('night')][['segment','channel_a','channel_b','field','r','slope_b_per_a']].to_string(index=False))
if __name__=='__main__':main()
