from plots_and_residuals import *

def main():
    d=pd.read_csv(W/'plot_refs.csv',dtype={'observing_device_id':str});d=d[d.markerName.str.startswith('YXJ')]
    fig,axes=plt.subplots(6,1,figsize=(15,15),sharex=True)
    for ax,(ch,g) in zip(axes,sorted(d.groupby('channel'))):
        for field,color,label in [('x','#888888','raw X'),('calX','#1769aa','recorded calX')]:
            v=g[field].copy();v[~g.valid]=np.nan;real_line(ax,g.timestamp,v,label=label,color=color,lw=.8)
        for night in ['2026-11-05','2026-11-06']:
            st=epoch(night+' 23:20');ax.axvspan(time([st])[0],time([st+460*60000])[0],color='#d9e5f2',alpha=.35)
        ax.set_title(ch,loc='left');format_ax(ax);ax.legend(loc='upper right',fontsize=8,ncol=2)
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(interval=6,tz=time([0]).tz))
    fig.suptitle('All YXJ observations: full native resolution, Nov 5-7 Beijing\nShaded = nominal core correction window; actual field gate not recorded',y=1.005)
    fig.tight_layout();save(fig,'08_YXJ_raw_cal_full_period.png')
if __name__=='__main__':main()
