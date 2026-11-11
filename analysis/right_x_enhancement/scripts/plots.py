from results import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as dates
from matplotlib.colors import TwoSlopeNorm
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'figure.dpi':125,'axes.spines.top':False,'axes.spines.right':False})
COL={'V51':'#1769aa','E_full':'#bd493d','A':'#d58b16','B1':'#087f8c','D_EMA':'#7c8470','D_Kalman':'#7842a1'}
def save(fig,n):
    (O/'figures').mkdir(exist_ok=True);fig.savefig(O/'figures'/n,bbox_inches='tight');plt.close(fig)
def local(t):return pd.to_datetime(t,unit='ms',utc=True).tz_convert('Asia/Shanghai')
def line(ax,t,v,**kw):
    t=np.asarray(t);v=np.asarray(v);a=[];b=[]
    for i in range(len(t)):
        if i and t[i]-t[i-1]>90000:a.append((t[i]+t[i-1])//2);b.append(np.nan)
        a.append(t[i]);b.append(v[i])
    ax.plot(local(a),b,**kw)
def main():
    m=pd.read_csv(O/'ablation_results.csv');z=m[m.scope.eq('same_original_active_frames')&m.kind.eq('YXJ')];p=z.pivot_table(index=['night','channel'],columns='method',values='LF_Q95_Q05_mm');methods=['E_Huber','E_full','A','B1','D_EMA','D_Kalman'];r=(p[methods].div(p.V51,axis=0)-1)*100;fig,ax=plt.subplots(figsize=(11,6));im=ax.imshow(r,norm=TwoSlopeNorm(vcenter=0,vmin=-30,vmax=80),cmap='RdBu_r',aspect='auto');ax.set_xticks(range(len(methods)),methods);ax.set_yticks(range(len(r)),[n[0][5:]+' '+n[1].split(':')[0][-6:]+':'+n[1].split(':')[1] for n in r.index]);
    for i in range(len(r)):
        for j in range(len(methods)):ax.text(j,i,f'{r.iloc[i,j]:+.1f}%',ha='center',va='center',fontsize=8)
    fig.colorbar(im,ax=ax,label='Change vs identical cold V51 (%)');ax.set_title('All six YXJ channels, both historical nights\nLF = trailing 5-min median Q95-Q05; blue = less variation, not accuracy; B fallback can be 0%');fig.tight_layout();save(fig,'01_all_YXJ_LF_changes.png')
    fig,axes=plt.subplots(2,2,figsize=(15,7))
    for row,(dev,marker) in enumerate([('780639173835','YXJ2'),('780639346578','YXJ6')]):
        for col,night in enumerate(['2026-11-05','2026-11-06']):
            g=pd.read_csv(O/f'continuous/{dev}_{marker}_{night}.csv');ax=axes[row,col];line(ax,g.timestamp,g.raw_X_mm,color='#aaaaaa',lw=.7,label='raw X')
            for method in ['V51','E_full','A','B1','D_Kalman']:line(ax,g.timestamp,g[method+'_X_mm'],label=method,color=COL[method],lw=.9)
            ax.set_title(dev+':'+marker+' night '+night+' (03:00-05:00 next day)');ax.set_ylabel('X (mm)');ax.grid(alpha=.15);ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M',tz=local([0]).tz));ax.legend(ncol=3,fontsize=7)
    fig.tight_layout();save(fig,'02_continuous_key_residuals.png')
    q=pd.read_csv(O/'injection_retention_overview.csv');fig,axes=plt.subplots(1,2,figsize=(13,4.7));meth=['V51','E_Huber','E_full','A','B1','D_EMA','D_Kalman'];scens=['YXJ5_step1','YXJ6_step3','YXJ_ramp3_3h','coherent1'];x=np.arange(len(meth))
    for k,s in enumerate(scens):
        v=q[q.scenario.eq(s)].set_index('method')['min'].reindex(meth);axes[0].plot(x,v,marker='o',label=s)
    axes[0].axhline(.9,color='#888',ls='--',lw=.7);axes[0].set_xticks(x,meth,rotation=30);axes[0].set_ylabel('Worst YXJ retained fraction across channels / nights');axes[0].set_title('Known observation-coordinate changes');axes[0].legend(fontsize=8)
    f=pd.read_csv(O/'additional_key_fault_propagation.csv');f=f[f.scenario.isin(['single_ref1','single_ref3','multiple_ref3','reference_spike3'])];v=f.groupby('method').max_extra_nontarget_key_response_vs_V51_mm.max().reindex(meth);axes[1].bar(x,v,color=[COL.get(a,'#777') for a in meth]);axes[1].set_xticks(x,meth,rotation=30);axes[1].set_ylabel('Maximum extra non-target key response (mm)');axes[1].set_title('Reference faults: extra response relative to V51');fig.suptitle('These injections are not world-geometry projected physical truth');fig.tight_layout();save(fig,'03_displacement_and_reference_faults.png')
    dev='780639346578';names,modes,fields,d=load(W/'final'/f'normal_{dev}.bin');kn,mm,ff,q=load(W/'final'/f'modal_step3_1793991600000_{dev}.bin');j=pd.Index(d['ts']).get_indexer(q['ts']);ii=fields.index('v_used_1');delta=q['methods']['diag'][:,:,ii]-d['methods']['diag'][j][:,:,ii];base=np.median(delta[-30:,0]);fig,ax=plt.subplots(figsize=(10,4))
    for method in ['V51','A','D_EMA','D_Kalman']:ax.plot(np.arange(12),delta[:12,modes.index(method)]/base,marker='o',label=method,color=COL[method])
    ax.axhline(.95,ls='--',color='#777',lw=.7);ax.set_xlabel('Real frames after 3 mm mode-shaped input step');ax.set_ylabel('Coefficient increment / late original V51 increment');ax.set_title('346578 second night: causal coefficient response\nNormalization is original-model response, not world-coordinate ground truth');ax.legend();ax.grid(alpha=.2);fig.tight_layout();save(fig,'04_coefficient_step_response.png')
    print('Four mechanism figures ready')
if __name__=='__main__':main()
