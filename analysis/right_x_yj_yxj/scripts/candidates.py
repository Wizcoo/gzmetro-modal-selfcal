from relations import *
import pickle

FOLDS=[('primary_05_to_06','2026-11-05','2026-11-06'),('reverse_06_to_05','2026-11-06','2026-11-05')]
BOUND={'YXJ2':'780639298317','YXJ3':'780639333715','YXJ4':'780639346578','YXJ5':'780639376393','YXJ6':'780639414923'}
def night_limits(n):return epoch(n+' 23:20'),epoch(n+' 23:20')+460*60000
def night_id(ts):
    dt=pd.to_datetime(ts,unit='ms',utc=True).tz_convert(TZ);h=dt.hour+dt.minute/60
    return np.asarray((dt-pd.to_timedelta((h<12).astype(int),unit='D')).strftime('%Y-%m-%d'))
def gate(ts):
    dt=pd.to_datetime(ts,unit='ms',utc=True).tz_convert(TZ);h=np.asarray(dt.hour+dt.minute/60+dt.second/3600);h=np.where(h<12,h+24,h)
    return np.where((h>=23)&(h<31),np.clip((h-23)/(1/3),0,1),np.where((h>=31)&(h<31+1/3),np.clip((31+1/3-h)/(1/3),0,1),0))
def offset(g,field):
    idx=g.timestamp.to_numpy();v=g[field].to_numpy(float).copy();v[~g.valid.to_numpy()]=np.nan
    ns=night_id(idx);out=np.full(len(v),np.nan)
    for n in np.unique(ns):
        st=epoch(n+' 22:00');m=(idx>=st)&(idx<st+3600000)&np.isfinite(v)
        if m.sum()>=10:out[ns==n]=v[ns==n]-np.mean(v[m])
    return pd.Series(out,index=idx)
def ridge(X,y,alpha=.1):
    sc=np.std(X,axis=0);sc=np.where(sc>1e-8,sc,1.0);z=X/sc
    b=np.linalg.solve(z.T@z+alpha*len(y)*np.eye(z.shape[1]),z.T@y)/sc
    return b
class Experiment:
    def __init__(self,d,fitnight,label='field_record'):
        self.d=d;self.fitnight=fitnight;self.label=label;self.channels={ch:g.sort_values('timestamp').reset_index(drop=True) for ch,g in d.groupby('channel')};self.cache={};self.group_audit=[]
    def groups(self,field,exclude=None):
        cachekey=(field,exclude)
        if cachekey in self.cache:return self.cache[cachekey]
        groups={};st,en=night_limits(self.fitnight)
        for dev in DEVS:
            names=[ch for ch in self.channels if ch.startswith(dev+':YJ') and not ch.split(':')[1].startswith('YXJ') and ch.split(':')[1]!=exclude]
            record={'baseline_label':self.label,'fit_night':self.fitnight,'field':field,'excluded_physical_reference':exclude or '', 'device_id':dev,'input_references':'|'.join(names)}
            if len(names)<2:record.update(qualified=False,reason='fewer_than_2_YJ');self.group_audit.append(record);continue
            signals={ch:offset(self.channels[ch],field) for ch in names};anchor=names[0];t=signals[anchor].index;mat=np.column_stack([align(signals[ch],t) for ch in names]);fit=(t>=st)&(t<en)
            smat=np.column_stack([smooth(pd.Series(mat[:,j],index=t)).values for j in range(len(names))]);ft=smat[fit];pairs=[]
            for a,b in itertools.combinations(range(len(names)),2):
                ok=np.isfinite(ft[:,a])&np.isfinite(ft[:,b]);
                if ok.sum()>=120 and np.std(ft[ok,a])>1e-8 and np.std(ft[ok,b])>1e-8:pairs.append(abs(np.corrcoef(ft[ok,a],ft[ok,b])[0,1]))
            coherence=float(np.median(pairs)) if pairs else np.nan;gains=[]
            for j in range(len(names)):
                ok=np.isfinite(ft[:,0])&np.isfinite(ft[:,j]);a=ft[ok,0];b=ft[ok,j];ac=a-a.mean();gain=float(ac@(b-b.mean())/(ac@ac)) if len(a)>=120 and ac@ac>1e-10 else np.nan;gains.append(gain)
            qualified=np.isfinite(coherence) and coherence>=.7 and all(np.isfinite(gains)) and all(.05<=abs(x)<=20 for x in gains)
            record.update(qualified=bool(qualified),median_abs_pair_r=coherence,gains_json=json.dumps(dict(zip(names,gains))),reason='qualified' if qualified else 'fit_night_coherence_or_gain_failure');self.group_audit.append(record)
            if not qualified:continue
            normalized=mat/np.asarray(gains);counts=np.isfinite(normalized).sum(axis=1)
            factor=np.full(len(normalized),np.nan);eligible=counts>=2
            factor[eligible]=np.nanmedian(normalized[eligible],axis=1)
            factor[counts<2]=np.nan;factor=smooth(pd.Series(factor,index=t));factor[counts<2]=np.nan
            groups[dev]={'signal':factor,'gains':dict(zip(names,gains)),'coherence':coherence}
        self.cache[cachekey]=groups;return groups
    def fit_target(self,ch,method):
        g=self.channels[ch];dev,name=ch.split(':');kind='YXJ' if name.startswith('YXJ') else 'YJ';field='x' if method=='A_YJ_guided' else 'calX';exclude=name if kind=='YJ' else None
        if method=='B_graph_residual' and kind=='YJ':return {'qualified':False,'reason':'YJ_is_unchanged_control','method':method,'channel':ch}
        groups=self.groups(field,exclude)
        selected=sorted(groups) if method=='A_YJ_guided' else [dv for dv in sorted({dev,BOUND.get(name,'')}) if dv in groups]
        if not selected:return {'qualified':False,'reason':'no_qualified_reference_group','method':method,'channel':ch}
        t=g.timestamp.to_numpy();X=np.column_stack([align(groups[dv]['signal'],t) for dv in selected]);target=smooth(offset(g,field)).values;st,en=night_limits(self.fitnight);m=(t>=st)&(t<en)&np.isfinite(target)&np.isfinite(X).all(axis=1)
        if m.sum()<120:return {'qualified':False,'reason':'fewer_than_120_joint_fit_samples','method':method,'channel':ch}
        b=ridge(X[m],target[m]);pred=X[m]@b;cap=float(min(np.quantile(abs(pred),.99),np.quantile(abs(target[m]),.99)));ts=t[m];dt=np.diff(ts)/60000;delta=abs(np.diff(pred));adj=(dt>=.5)&(dt<=1.5)
        slew=float(2*np.quantile(delta[adj]/dt[adj],.99)) if adj.sum() else 0
        return {'qualified':True,'reason':'qualified','method':method,'channel':ch,'groups':selected,'coefficients':b.tolist(),'fit_samples':int(m.sum()),'cap_mm':cap,'slew_mm_per_min':max(1e-6,slew),'field':field,'excluded_physical_reference':exclude,'alpha':.1}
    def predict(self,model,d_override=None):
        ch=model['channel'];g=(d_override or self.channels)[ch];t=g.timestamp.to_numpy();base=g.calX.to_numpy(float);out=base.copy();applied=np.zeros(len(t),bool);extra=np.zeros(len(t));reason=np.full(len(t),model['reason'],dtype=object)
        if not model['qualified']:return out,applied,extra,reason
        if d_override is None:groups=self.groups(model['field'],model['excluded_physical_reference'])
        else:
            # Use frozen gains and membership, recomputing only actual causal
            # reference features. Never refit an injected or held-out sample.
            groups={}
            train=self.groups(model['field'],model['excluded_physical_reference'])
            for dev in model['groups']:
                gains=train[dev]['gains'];anchor=next(iter(gains));idx=d_override[anchor].timestamp.to_numpy();mat=np.column_stack([align(offset(d_override[c],model['field']),idx)/v for c,v in gains.items()]);count=np.isfinite(mat).sum(axis=1)
                f=np.full(len(mat),np.nan);eligible=count>=2;f[eligible]=np.nanmedian(mat[eligible],axis=1)
                f[count<2]=np.nan;f=smooth(pd.Series(f,index=idx));f[count<2]=np.nan;groups[dev]={'signal':f}
        X=np.column_stack([align(groups[dev]['signal'],t) for dev in model['groups']]);ok=np.isfinite(X).all(axis=1)&g.valid.to_numpy();pred=np.zeros(len(t));pred[ok]=X[ok]@np.asarray(model['coefficients']);gt=gate(t)
        last=0.0;lastts=None
        for i in range(len(t)):
            if gt[i]<=0 or not ok[i]:last=0;lastts=None;reason[i]='outside_gate' if gt[i]<=0 else 'reference_or_target_unavailable';continue
            value=pred[i]
            if model['method']=='B_graph_residual':
                value=np.clip(value,-model['cap_mm'],model['cap_mm']);desired=gt[i]*value
                if lastts is not None and t[i]-lastts<=90000:
                    limit=model['slew_mm_per_min']*(t[i]-lastts)/60000;desired=np.clip(desired,last-limit,last+limit)
            else:desired=gt[i]*value
            last=desired;lastts=t[i];extra[i]=desired;out[i]=(g.x.iloc[i] if model['method']=='A_YJ_guided' else base[i])-desired;applied[i]=True;reason[i]='applied'
        return out,applied,extra,reason

def met(t,v,baseline):
    s=pd.Series(v,index=t);s=s[np.isfinite(s)];sm=smooth(s);dt=np.diff(s.index)/1000;dv=np.diff(s.values);adj=(dt>=30)&(dt<=90)
    r={'n':len(s),'pv_mm':float(s.max()-s.min()),'lowfreq_p95_p05_range_mm':float(sm.quantile(.95)-sm.quantile(.05)),'step_abs_p99_mm':float(np.quantile(abs(dv[adj]),.99)) if adj.sum() else np.nan}
    for mins in [10,30,60]:
        target=sm.index.to_numpy()-mins*60000;idx=sm.index.get_indexer(target,method='nearest',tolerance=90000);ok=idx>=0;lag=np.full(len(sm),np.nan);lag[ok]=sm.values[idx[ok]];diff=sm.values-lag
        run=np.cumsum(np.r_[False,np.diff(sm.index.to_numpy())>90000]);same=np.zeros(len(sm),bool);same[ok]=run[ok]==run[idx[ok]];diff[~same]=np.nan
        r[f'drift{mins}min_abs_p99_mm']=float(np.nanquantile(abs(diff),.99)) if np.isfinite(diff).any() else np.nan
    r['nonzero_synthetic_truth_claim']=False;return r
def main():
    d=pd.read_pickle(W/'refs.pkl');metric=[];models=[];audits=[];traces=[];cache={}
    for fold,fitnight,testnight in FOLDS:
        e=Experiment(d,fitnight);st,en=night_limits(testnight);foldmodels={}
        for ch,g in e.channels.items():
            t=g.timestamp.to_numpy();m=(t>=st)&(t<en)&g.valid.to_numpy();a=e.fit_target(ch,'A_YJ_guided');b=e.fit_target(ch,'B_graph_residual');oa,aa,ca,ra=e.predict(a);ob,ab,cb,rb=e.predict(b);foldmodels[ch]={'A':a,'B':b}
            for model in [a,b]:models.append({'fold':fold,'fit_night':fitnight,'holdout_night':testnight,**{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in model.items()}})
            arrays={'raw_X':g.x.to_numpy(),'V51_field_record':g.calX.to_numpy(),'A_YJ_guided':oa,'B_graph_residual':ob}
            # Fair paired comparison on rows where both recipes can be applied;
            # coverage and fallback-on-all-rows metrics are reported separately.
            pair=m&aa&ab if ch.split(':')[1].startswith('YXJ') else m&aa
            for scope,mask in [('all_valid_with_recorded_fallback',m),('paired_candidate_available',pair)]:
                for method,v in arrays.items():
                    if mask.sum()<20:continue
                    r=met(t[mask],v[mask],g.calX.to_numpy()[mask]);r.update({'fold':fold,'fit_night':fitnight,'holdout_night':testnight,'channel':ch,'kind':'YXJ' if ch.split(':')[1].startswith('YXJ') else 'YJ_LOPO_diagnostic','method':method,'evaluation_scope':scope,'candidate_A_coverage':float(aa[m].mean()),'candidate_B_coverage':float(ab[m].mean()),'metric_units':'mm','start_beijing':iso(st),'end_exclusive_beijing':iso(en),'actual_online_gate':'not_recorded'});metric.append(r)
            gg=g[(t>=epoch(testnight+' 22:00'))&(t<en+20*60000)].copy();loc=gg.index.to_numpy();gg['fold']=fold;gg['fit_night']=fitnight;gg['holdout_night']=testnight;gg['time_beijing']=gg.timestamp.map(iso);gg['A_X_mm']=oa[loc];gg['B_X_mm']=ob[loc];gg['A_applied']=aa[loc];gg['B_applied']=ab[loc];gg['A_extra_correction_mm']=ca[loc];gg['B_extra_correction_mm']=cb[loc];gg['A_status']=ra[loc];gg['B_status']=rb[loc];gg['candidate_Y_equals_recorded_calY']=True
            cols=['timestamp','time_beijing','observing_device_id','markerName','RoiCalState','valid','x','calX','A_X_mm','B_X_mm','y','calY','candidate_Y_equals_recorded_calY','A_applied','B_applied','A_extra_correction_mm','B_extra_correction_mm','A_status','B_status','fold','fit_night','holdout_night','source_db','_source_rowid']
            write(gg[cols],f'candidate_traces/{fold}_{ch.replace(":","_")}.csv');traces.append(gg[cols]);print(fold,ch,'coverage',round(aa[m].mean(),3),round(ab[m].mean(),3),flush=True)
        audits.extend([{'fold':fold,**v} for v in e.group_audit]);cache[fold]=(e,foldmodels)
    write(pd.DataFrame(metric),'candidate_metrics.csv');write(pd.DataFrame(models),'frozen_response_models.csv');write(pd.DataFrame(audits),'reference_group_qualification.csv');pd.concat(traces,ignore_index=True).to_pickle(W/'candidate_traces.pkl')
    with (W/'models.pkl').open('wb') as f:pickle.dump(cache,f)
    z=pd.DataFrame(metric);print(z[(z.fold==FOLDS[0][0])&(z.kind=='YXJ')&(z.evaluation_scope=='all_valid_with_recorded_fallback')][['channel','method','lowfreq_p95_p05_range_mm','drift60min_abs_p99_mm','step_abs_p99_mm','candidate_A_coverage','candidate_B_coverage']].to_string(index=False))
if __name__=='__main__':main()
