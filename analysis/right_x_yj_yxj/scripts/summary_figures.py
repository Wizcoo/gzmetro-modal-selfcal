from plots_and_residuals import *
def main():
    m=pd.read_csv(O/'candidate_metrics.csv');p=m[(m.fold=='primary_05_to_06')&(m.kind=='YXJ')&(m.evaluation_scope=='all_valid_with_recorded_fallback')];channels=sorted(p.channel.unique());fig,axes=plt.subplots(1,2,figsize=(14,4.7));x=np.arange(len(channels));methods=['V51_field_record','A_YJ_guided','B_graph_residual']
    for ax,metric,title in zip(axes,['lowfreq_p95_p05_range_mm','step_abs_p99_mm'],['Low-frequency range (trailing 5min median Q95-Q05)','Adjacent real-frame absolute step P99']):
        for j,method in enumerate(methods):
            z=p[p.method.eq(method)].set_index('channel').reindex(channels);bars=ax.bar(x+(j-1)*.25,z[metric],.23,color=COL[method],label=method)
            if method=='B_graph_residual':
                for bar,coverage in zip(bars,z.candidate_B_coverage):
                    if coverage==0:bar.set_hatch('///');bar.set_alpha(.45)
        ax.set_xticks(x,[c[:12][-4:]+':'+c.split(':')[1] for c in channels],rotation=30,ha='right');ax.set_ylabel('mm');ax.set_title(title);ax.grid(axis='y',alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('Primary holdout: fit Nov 5, test Nov 6 night — no validated improvement over recorded V51\nHatched B bars = no qualified residual reference group; recorded-baseline fallback',y=1.06);fig.tight_layout();save(fig,'06_primary_AB_summary.png')
    r=pd.read_csv(O/'displacement_injection_results.csv');z=r[(r.scenario=='coherent_reference_and_target_step')&r.method.isin(['V51_cold_source','A','B'])];fig,ax=plt.subplots(figsize=(12,4));chs=sorted(z.channel.unique());x=np.arange(len(chs))
    for j,(method,col) in enumerate([('V51_cold_source','#1769aa'),('A','#e07a19'),('B','#b42c68')]):
        a=z[z.method.eq(method)].set_index('channel').reindex(chs);ax.bar(x+(j-1)*.25,a.retained_fraction_if_target_injected,.23,label=method,color=col)
    ax.axhline(1,color='black',ls='--',lw=.8,label='retain injected increment');ax.axhline(0,color='black',lw=.6);ax.set_xticks(x,[c[-17:] for c in chs],rotation=25,ha='right');ax.set_ylabel('retained signed fraction');ax.set_title('Adversarial coherent reference + target movement injection\nControlled empty-state source replay; observation-domain test, no world-coordinate geometry');ax.legend(ncol=4,fontsize=8);ax.grid(axis='y',alpha=.2);fig.tight_layout();save(fig,'07_injection_identifiability_risk.png')
    print('Summary and injection figures ready')
if __name__=='__main__':main()
