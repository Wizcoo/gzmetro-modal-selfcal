from results import *

def main():
    m=pd.read_csv(O/'ablation_results.csv');m=m[m.scope.eq('same_original_active_frames')&m.kind.eq('YXJ')];p=m.pivot_table(index=['night','channel'],columns='method',values='LF_Q95_Q05_mm');out=[]
    for method in ['E_Huber','E_full','A','B0','B1','B2','D_EMA','D_Kalman']:
        r=p[method]/p.V51-1
        for night,g in r.groupby(level='night'):out.append({'method':method,'night':night,'key_channels_improved_LF':int((g<-.00001).sum()),'key_channels_worsened_LF_over10pct':int((g>.1).sum()),'worst_channel':g.idxmax()[1],'worst_LF_increase_fraction':g.max(),'best_channel':g.idxmin()[1],'best_LF_change_fraction':g.min(),'not_acceptance':'historical development screen; variation not accuracy'})
    write(pd.DataFrame(out),'candidate_screen.csv')
    effects=[]
    for dev in DEVS:
        names,modes,fields,d=load(W/'final'/f'normal_{dev}.bin');di={v:i for i,v in enumerate(fields)};ti=pd.Index(d['ts'])
        for path in (W/'final').glob(f'*_{dev}.bin'):
            if path.name.startswith('normal_'):continue
            kn,mm,ff,z=load(path);scenario,onset,_=path.stem.rsplit('_',2);onset=int(onset);j=ti.get_indexer(z['ts']);ix=[names.index(n) for n in kn]
            truth=z['rawx']-d['rawx'][j][:,ix];delta=z['methods']['x']-d['methods']['x'][j][:,:,ix]
            for mi,method in enumerate(modes):
                if method=='identity':continue
                mask=np.isfinite(truth)&(abs(truth)<1e-9);v=np.where(mask,delta[:,mi]-delta[:,0],np.nan)
                effects.append({'device_id':dev,'night':iso(onset)[:10],'scenario':scenario,'method':method,'max_extra_nontarget_key_response_vs_V51_mm':np.nanmax(abs(v)) if np.isfinite(v).any() else np.nan,'interpretation':'paired per-frame difference of injection responses; not difference of maxima'})
    write(pd.DataFrame(effects),'additional_key_fault_propagation.csv')
    inj=pd.read_pickle(W/'injections_final.pkl');target=inj[inj.channel.str.contains(':YXJ',na=False)&inj.raw_target_increment_mm.abs().gt(.5)&~inj.scenario.str.startswith(('modal','multiple_ref','single_ref'))];summary=target.groupby(['method','scenario']).retained_fraction.agg(['min','median','max']).reset_index();write(summary,'injection_retention_overview.csv')
    print(pd.DataFrame(out).to_string(index=False));print('Reference-fault extra response\n',pd.DataFrame(effects).query('scenario in ["single_ref1","single_ref3","multiple_ref3","reference_spike3","missing_refs"]',engine='python').groupby(['method','scenario']).max_extra_nontarget_key_response_vs_V51_mm.max().unstack().round(4).to_string())
if __name__=='__main__':main()
