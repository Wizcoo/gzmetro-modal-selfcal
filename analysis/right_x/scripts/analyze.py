"""Read-only field-data diagnosis. No production algorithm is executed or edited."""
from pathlib import Path
import csv,json,hashlib,math
import pandas as pd,numpy as np
W=Path(__file__).resolve().parent.parent;C=W/'.cache';OUT=W;OUT.mkdir(parents=True,exist_ok=True)
TZ='Asia/Shanghai'
def iso(ts):return pd.Timestamp(ts,unit='ms',tz='UTC').tz_convert(TZ).isoformat(timespec='milliseconds')
def tag(d,tc='timestamp'):
    d=d.copy();d['timestamp']=d[tc].astype('int64');dt=pd.to_datetime(d.timestamp,unit='ms',utc=True).dt.tz_convert(TZ)
    h=dt.dt.hour+dt.dt.minute/60+dt.dt.second/3600
    d['date_beijing']=dt.dt.strftime('%Y-%m-%d')
    d['nominal_phase']=np.select([h.between(22,23,inclusive='left'),h.between(23,23+1/3,inclusive='left'),h.between(7,7+1/3,inclusive='left'),(h<7)|(h>=23+1/3)],['baseline','ramp_in','ramp_out','full_correction'],default='daytime')
    d['night_date']= (dt-pd.to_timedelta(np.where(h<12,1,0),unit='D')).dt.strftime('%Y-%m-%d')
    d['phase_key']=d.date_beijing+'|'+d.nominal_phase+'|'+d.night_date
    return d
def write_csv(df,path):
    path=OUT/path;path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(path,index=False,encoding='utf-8',float_format='%.9g')
    if path.stat().st_size>=1950000:raise RuntimeError(f'CSV too large: {path}')
def split_csv(df,rel):
    rel=Path(rel);paths=[];size=0;part=1;buf=[]
    # Deterministic byte-limited partitioning. Retains every row and timestamp.
    header=','.join(map(str,df.columns))+'\n'
    import io
    def line(row):
        s=io.StringIO();csv.writer(s,lineterminator='\n').writerow(['' if pd.isna(v) else format(v,'.0f') if isinstance(v,(float,np.floating)) and abs(v)>=1e11 and v==int(v) else format(v,'.9g') if isinstance(v,(float,np.floating)) else v for v in row]);return s.getvalue()
    for row in df.itertuples(index=False,name=None):
        text=line(row);b=len(text.encode('utf-8'))
        if buf and size+b+len(header.encode())>1750000:
            p=OUT/rel.parent/f'{rel.stem}.part{part:02}.csv';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(header+''.join(buf),encoding='utf-8');paths.append(str(p.relative_to(OUT)).replace('\\','/'));part+=1;buf=[];size=0
        buf.append(text);size+=b
    if buf:
        p=OUT/rel.parent/f'{rel.stem}.part{part:02}.csv';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(header+''.join(buf),encoding='utf-8');paths.append(str(p.relative_to(OUT)).replace('\\','/'))
    return paths
def q(v,p):
    v=np.asarray(v,dtype=float);v=v[np.isfinite(v)];return float(np.quantile(v,p)) if len(v) else np.nan
def corr(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float);m=np.isfinite(a)&np.isfinite(b)
    return float(np.corrcoef(a[m],b[m])[0,1]) if m.sum()>=20 and np.std(a[m])>1e-10 and np.std(b[m])>1e-10 else np.nan
def metrics(ts,values):
    ts=np.asarray(ts,np.int64);v=np.asarray(values,float);m=np.isfinite(v);ts=ts[m];v=v[m]
    if not len(v):return {'n_valid':0}
    order=np.argsort(ts);ts=ts[order];v=v[order]
    dt=np.diff(ts)/1000;steps=np.diff(v);adj=(dt>=30)&(dt<=90)
    # No differences cross missing-frame gaps. Each run has its own trailing
    # medians; lagged drift requires the same run and a real sample within 90s.
    run=np.cumsum(np.r_[False,(dt>90)|(dt<30)])
    residual=[];drifts={10:[],30:[],60:[]};smooth=np.full(len(v),np.nan)
    for rid in np.unique(run):
        ix=np.flatnonzero(run==rid);t=ts[ix];s=pd.Series(v[ix],index=pd.to_datetime(t,unit='ms',utc=True))
        smooth[ix]=s.rolling('5min',min_periods=3).median().values
        residual.extend((s-s.rolling('31min',min_periods=15).median()).dropna().values)
        for lag in drifts:
            target=t-lag*60000;loc=np.searchsorted(t,target);loc=np.clip(loc,0,len(t)-1)
            prev=np.maximum(loc-1,0);loc=np.where(abs(t[prev]-target)<abs(t[loc]-target),prev,loc)
            good=(abs(t[loc]-target)<=90000)&(t-target>=0)&(loc<np.arange(len(t)))
            vals=smooth[ix]-smooth[ix[loc]];drifts[lag].extend(vals[good&np.isfinite(vals)])
    base_mask=ts<ts[0]+600000;base=float(np.median(v[base_mask]));off=v-base
    r={'n_valid':len(v),'baseline_first10min_mm':base,'baseline_samples':int(base_mask.sum()),'pv_mm':float(v.max()-v.min()),'robust_p99_p01_range_mm':q(v,.99)-q(v,.01),
       'local_offset_abs_p95_mm':q(abs(off),.95),'local_offset_abs_p99_mm':q(abs(off),.99),'adjacent_pairs':int(adj.sum()),'step_abs_p95_mm':q(abs(steps[adj]),.95),'step_abs_p99_mm':q(abs(steps[adj]),.99),'step_abs_max_mm':q(abs(steps[adj]),1),
       'trailing31min_residual_abs_p95_mm':q(abs(np.array(residual)),.95),'trailing31min_residual_abs_p99_mm':q(abs(np.array(residual)),.99),
       'sustained5min_offset_abs_max_mm':q(abs(smooth-base),1),'last10min_minus_first10min_mm':float(np.median(v[ts>ts[-1]-600000])-base),'gaps_gt90s':int((dt>90).sum())}
    for lag,z in drifts.items():r[f'drift{lag}min_abs_p95_mm']=q(abs(np.array(z)),.95);r[f'drift{lag}min_abs_p99_mm']=q(abs(np.array(z)),.99)
    return r
def paired_stats(g,axis,scope,device,marker,period):
    raw=axis.lower();cal='cal'+axis;valid=g.RoiCalState.eq(1)&~g.ambiguous_business_key&np.isfinite(g[raw])&np.isfinite(g[cal]);z=g.loc[valid]
    row={'scope':scope,'device_id':device,'marker_name':marker,'axis':axis,'period':period,'start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'unit':'mm','n_rows':len(g),'roi_valid_fraction':float(g.RoiCalState.eq(1).mean()),'actual_gate':'not_recorded','actual_modes_ready':'not_recorded'}
    for label,col in [('raw',raw),('cal',cal),('correction',None)]:
        vals=z[col].values if col else (z[raw]-z[cal]).values
        for k,v in metrics(z.timestamp,vals).items():row[label+'_'+k]=v
    row['nonzero_correction_fraction']=float((z[raw]-z[cal]).abs().gt(1e-6).mean()) if len(z) else np.nan
    row['pv_reduction_fraction']=1-row.get('cal_pv_mm',np.nan)/row.get('raw_pv_mm',np.nan) if row.get('raw_pv_mm',0)>1e-9 else np.nan
    row['step_p99_reduction_fraction']=1-row.get('cal_step_abs_p99_mm',np.nan)/row.get('raw_step_abs_p99_mm',np.nan) if row.get('raw_step_abs_p99_mm',0)>1e-9 else np.nan
    return row

def main():
    md=tag(pd.read_pickle(C/'MarkerData.pkl'));sd=tag(pd.read_pickle(C/'SubDeviceDisData.pkl'))
    upstream={};envs={};common=[];summary=[];quality=[];phase_rows=[];links=[]
    for p in sorted(C.glob('Marker_780*.pkl')):
        dev=p.stem.split('_')[1];d=tag(pd.read_pickle(p));d['device_id']=dev
        d['valid_observation']=d.RoiCalState.eq(1)&~d.ambiguous_business_key
        upstream[dev]=d
        e=tag(pd.read_pickle(C/f'EnvData_{dev}.pkl'),'ts');envs[dev]=e
        envcols=[k for k in ['temp','humidity','pressure','realDis','sx','sy','sz','innerTemp','innerLensTemp'] if k in e]
        ev=e.groupby('timestamp')[envcols].mean()
        quality.extend([{'device_id':dev,'field':k,'finite_rows':int(np.isfinite(e[k]).sum()),'distinct_values':e[k].nunique(),'min':e[k].min(),'max':e[k].max(),'all_zero':e[k].eq(0).all(),'usable_for_correlation':e[k].nunique()>=5,'unit':'degC' if 'temp' in k.lower() else 'percent' if k=='humidity' else 'unverified'} for k in envcols])
        detail=[]
        for axis in ['X','Y']:
            raw=axis.lower();cal='cal'+axis
            piv=d[d.valid_observation].pivot(index='timestamp',columns='markerName',values=[raw,cal])
            r=piv[raw];v=piv[cal];ref=r.loc[r.index<r.index.min()+600000].median();off=r-ref;cv=v-v.loc[v.index<v.index.min()+600000].median()
            structural=[n for n in r if n.startswith('YD')]
            for phase,g in d.groupby('phase_key',sort=True):
                # Device summary is the median trajectory of YD marker offsets,
                # not a sum or pooling of point coordinates.
                key=g.timestamp.unique();rr=r.reindex(key)[structural];vv=v.reindex(key)[structural]
                rb=rr.loc[rr.index<rr.index.min()+600000].median();vb=vv.loc[vv.index<vv.index.min()+600000].median()
                cm=(rr-rb).median(axis=1);cc=(vv-vb).median(axis=1)
                device_row={'scope':'device_common_median','device_id':dev,'marker_name':'YD_median','axis':axis,'period':phase,'unit':'mm','start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'actual_gate':'not_recorded','actual_modes_ready':'not_recorded'}
                for label,val in [('raw',cm),('cal',cc)]:
                    for k,z in metrics(key,val).items():device_row[label+'_'+k]=z
                device_row['pv_reduction_fraction']=1-device_row.get('cal_pv_mm',np.nan)/device_row.get('raw_pv_mm',np.nan) if device_row.get('raw_pv_mm',0)>1e-9 else np.nan
                phase_rows.append(device_row)
                # Complete-case PCA: no missing-value fill and no modeled truth.
                for lab,a in [('raw',rr),('cal',vv)]:
                    complete=a.dropna(axis=0);ratio=np.nan
                    if len(complete)>=20 and complete.shape[1]>=3:
                        z=complete.values-complete.values.mean(axis=0);eig=np.linalg.svd(z,compute_uv=False)**2
                        ratio=float(eig[0]/eig.sum()) if eig.sum()>0 else np.nan
                    device_row[lab+'_pc1_variance_fraction']=ratio;device_row[lab+'_pca_complete_frames']=len(complete)
                for name,gm in g.groupby('markerName'):
                    row=paired_stats(gm,axis,'marker',dev,name,phase)
                    valid=gm.valid_observation;ix=gm.loc[valid,'timestamp'];a=gm.loc[valid,raw];b=gm.loc[valid,cal]
                    other=[n for n in structural if n!=name]
                    if len(other)>=3:
                        oc=(r[other]-r[other].loc[key].iloc[:min(10,len(key))].median()).median(axis=1)
                        row['raw_vs_other_marker_common_r']=corr(a,oc.reindex(ix));row['cal_vs_other_marker_common_r']=corr(b,oc.reindex(ix))
                    for field in ['temp','humidity','sx','sy','sz']:
                        if field not in ev:continue
                        aligned=ev[field].reindex(ix)
                        row[f'raw_{field}_r']=corr(a,aligned);row[f'cal_{field}_r']=corr(b,aligned)
                    detail.append(row)
            commonframe=pd.DataFrame({'timestamp':r.index,'device_id':dev,'axis':axis,'raw_common_offset_mm':off[structural].median(axis=1).values,'cal_common_offset_mm':cv[structural].median(axis=1).values,'correction_median_mm':(r-v)[structural].median(axis=1).values,'nonzero_correction_marker_fraction':(r-v).abs().gt(1e-6).sum(axis=1).values/r.notna().sum(axis=1).values,'valid_marker_count':r.notna().sum(axis=1).values})
            common.append(commonframe)
            for period,mask in [('all_window',pd.Series(True,index=d.index)),('nominal_daytime',d.nominal_phase.eq('daytime')),('nominal_full_correction',d.nominal_phase.eq('full_correction'))]:
                for name,g in d[mask].groupby('markerName'):
                    summary.append(paired_stats(g,axis,'marker',dev,name,period))
        split_csv(pd.DataFrame(detail),f'summaries/{dev}_phase_metrics.csv')
        # Source-visible membership only: not solver topology or device ownership.
        for name,g in d.groupby('markerName'):
            links.append({'marker_name':name,'observing_device_id':dev,'n_observations':len(g),'valid_observations':int(g.valid_observation.sum()),'start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'mapping_status':'observed_in_Marker_table_not_solver_ownership','unit':'mm_for_coordinates'})
        print('metrics complete',dev,flush=True)
    sf=pd.DataFrame(summary);ph=pd.DataFrame(phase_rows)
    # Main summary contains device and marker rows with all/day/core periods.
    split_csv(sf,'summaries/all_marker_metrics.csv')
    compact=[k for k in sf if not any(x in k for x in ['correction_','drift30','drift60','trailing31','last10','baseline_samples','adjacent_pairs','gaps_'])]
    sm=sf.copy()
    devagg=sf.groupby(['device_id','axis','period'],as_index=False).agg(raw_pv_mm=('raw_pv_mm','median'),cal_pv_mm=('cal_pv_mm','median'),raw_step_abs_p99_mm=('raw_step_abs_p99_mm','median'),cal_step_abs_p99_mm=('cal_step_abs_p99_mm','median'),nonzero_correction_fraction=('nonzero_correction_fraction','median'),n_rows=('n_rows','sum'),roi_valid_fraction=('roi_valid_fraction','mean'))
    devagg['scope']='device_median_of_marker_metrics';devagg['marker_name']='all_markers_median';devagg['unit']='mm';devagg['start_beijing']=iso(md.timestamp.min());devagg['end_beijing']=iso(md.timestamp.max())
    devagg['pv_reduction_fraction']=1-devagg.cal_pv_mm/devagg.raw_pv_mm
    main=pd.concat([devagg,sm],ignore_index=True)
    # Explicitly compact the primary CSV; all remaining metrics are in shards.
    keep=['scope','device_id','marker_name','axis','period','unit','start_beijing','end_beijing','n_rows','roi_valid_fraction','raw_pv_mm','cal_pv_mm','pv_reduction_fraction','raw_local_offset_abs_p95_mm','cal_local_offset_abs_p95_mm','raw_local_offset_abs_p99_mm','cal_local_offset_abs_p99_mm','raw_step_abs_p95_mm','cal_step_abs_p95_mm','raw_step_abs_p99_mm','cal_step_abs_p99_mm','raw_step_abs_max_mm','cal_step_abs_max_mm','nonzero_correction_fraction']
    write_csv(main[[k for k in keep if k in main]],'right_x_summary.csv')
    write_csv(ph,'device_phase_metrics.csv');write_csv(pd.DataFrame(quality),'environment_quality.csv');write_csv(pd.DataFrame(links),'marker_device_membership.csv')
    cf=tag(pd.concat(common,ignore_index=True));cf['time_beijing']=cf.timestamp.map(iso);cf['actual_gate']='not_recorded';cf['actual_modes_ready']='not_recorded'
    for dev,g in cf.groupby('device_id'):write_csv(g,f'continuous_overview/{dev}_all_frames.csv')
    # Downstream field identities, not inferred publication formulas.
    identities=[]
    for axis in ['X','Y']:
        for day,g in md.groupby('date_beijing'):
            z=g[axis.lower()+'0']-(g['filtered'+axis+'0']-g['init'+axis])
            identities.append({'date_beijing':day,'axis':axis,'n_rows':len(g),'identity':'x0_or_y0 = filtered_axis0 - init_axis','max_abs_difference_mm':z.abs().max(),'p99_abs_difference_mm':z.abs().quantile(.99),'within_0_00011mm_fraction':z.abs().le(.00011).mean(),'postFiltered_all_zero':g['postFiltered'+axis+'0'].eq(0).all(),'cloud_publication_confirmed':False})
    write_csv(pd.DataFrame(identities),'field_identity_checks.csv')
    ds=[]
    for (name,phase),g in md.groupby(['markerName','phase_key']):
        for axis in ['X','Y']:
            row={'marker_name':name,'axis':axis,'period':phase,'unit':'mm','start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'all_zero_xyz0':g[['x','y','x0','y0']].eq(0).all().all()}
            row.update(metrics(g.timestamp,g[axis.lower()+'0']));ds.append(row)
    split_csv(pd.DataFrame(ds),'summaries/downstream_phase_metrics.csv')
    # Candidate associations retain *all* same-name parents, including multiple
    # observations of the same physical marker by different cameras.
    parent=pd.concat([d[['timestamp','markerName','device_id','RoiCalState','x','calX','y','calY']] for d in upstream.values()],ignore_index=True)
    joined=md[['timestamp','markerName','x0','y0','x','y','initX','initY','filteredX0','filteredY0']].merge(parent,on=['timestamp','markerName'],how='left',suffixes=('_down','_up'))
    counts=joined.groupby(['timestamp','markerName']).device_id.count()
    audit={'window_start':iso(md.timestamp.min()),'window_end':iso(md.timestamp.max()),'downstream_rows':len(md),'marker_name_timestamp_parent_counts':{str(k):int(v) for k,v in counts.value_counts().items()},'mapping_type':'same-name exact-timestamp candidate edges, not verified solver dependency','empty_deviceId_rows':int(md.deviceId.eq('').sum()),'field_unit_evidence':'DLL header declares input/output millimetres; DB write mapping unavailable'}
    # Ordinary and differenced associations. Never call these transfer gains.
    assoc=[]
    for (dev,name),g in joined.dropna(subset=['device_id']).groupby(['device_id','markerName']):
        g=g.sort_values('timestamp');g=g[g.RoiCalState.eq(1)]
        for period,sub in [('all_window',g),('nominal_full_correction',g.loc[tag(g).nominal_phase.eq('full_correction')])]:
            dt=sub.timestamp.diff().between(30000,90000);deltas=sub[['x_up','calX','x0']].diff().where(dt,axis=0)
            assoc.append({'device_id':dev,'marker_name':name,'period':period,'matched_valid_rows':len(sub),'rawX_vs_x0_r':corr(sub.x_up,sub.x0),'calX_vs_x0_r':corr(sub.calX,sub.x0),'rawX_step_vs_x0_step_r':corr(deltas.x_up,deltas.x0),'calX_step_vs_x0_step_r':corr(deltas.calX,deltas.x0),'association_only_not_sensitivity':True})
    write_csv(pd.DataFrame(assoc),'upstream_downstream_associations.csv')
    (OUT/'data_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    # Keep work caches out of the review branch.
    md.to_pickle(C/'md_tagged.pkl');cf.to_pickle(C/'common.pkl');pd.DataFrame(ds).to_pickle(C/'downstream_metrics.pkl');ph.to_pickle(C/'device_metrics.pkl');sf.to_pickle(C/'marker_metrics.pkl')
    print('DONE',json.dumps(audit),flush=True)
if __name__=='__main__':main()
