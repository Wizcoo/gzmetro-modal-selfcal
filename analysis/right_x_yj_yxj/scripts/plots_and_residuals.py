from relations import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':125})
COL={'raw_X':'#8b8b8b','V51_field_record':'#1769aa','A_YJ_guided':'#e07a19','B_graph_residual':'#b42c68'}
def time(ts):return pd.DatetimeIndex(pd.to_datetime(np.asarray(ts),unit='ms',utc=True)).tz_convert(TZ)
def save(fig,name):
    p=O/'figures'/name;p.parent.mkdir(exist_ok=True);fig.savefig(p,bbox_inches='tight');plt.close(fig)
def format_ax(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=time([0]).tz));ax.grid(alpha=.18);ax.set_ylabel('X (mm)')
def real_line(ax,ts,values,**kwargs):
    t=np.asarray(ts,dtype=np.int64);v=np.asarray(values,dtype=float);xx=[];yy=[]
    for i in range(len(t)):
        if i and t[i]-t[i-1]>90000:xx.append((t[i]+t[i-1])//2);yy.append(np.nan)
        xx.append(t[i]);yy.append(v[i])
    return ax.plot(time(xx),yy,**kwargs)
def main():
    d=pd.read_csv(W/'plot_refs.csv',dtype={'observing_device_id':str});tr=pd.read_csv(W/'plot_candidates.csv',dtype={'observing_device_id':str})
    for dev,g in d.groupby('observing_device_id'):
        cols=['timestamp','markerName','observing_device_id','RoiCalState','valid','x','calX','y','calY','source_db','_source_rowid']
        for name,z in g.groupby('markerName'):
            z=z[cols].copy();z['time_beijing']=z.timestamp.map(iso);write(z,f'observed_traces/{dev}_{name}.csv')
    yjdev=[dev for dev,g in d[d.markerName.str.startswith('YJ')].groupby('observing_device_id')]
    fig,axes=plt.subplots(len(yjdev),1,figsize=(13,10),sharex=True)
    for ax,dev in zip(axes,yjdev):
        g=d[d.observing_device_id.eq(dev)&d.markerName.str.startswith('YJ')]
        for name,z in g.groupby('markerName'):
            zz=z.copy();zz.loc[~zz.valid,'x']=np.nan;real_line(ax,zz.timestamp,zz.x,lw=.7,label=name)
        for night in ['2026-11-05','2026-11-06']:ax.axvspan(pd.Timestamp(night+' 23:00',tz=TZ),pd.Timestamp(night+' 23:00',tz=TZ)+pd.Timedelta(hours=8),color='#1769aa',alpha=.07)
        ax.set_title(f'{dev}: original YJ X, all real observations');format_ax(ax);ax.legend(ncol=4,loc='upper right',fontsize=8)
    fig.suptitle('YJ raw reference trends, Nov 5-7 (Beijing)\nShading = nominal night, no claim of zero physical displacement',y=1.01);fig.tight_layout();save(fig,'01_YJ_raw_full_period.png')
    fig,axes=plt.subplots(len(yjdev),2,figsize=(14,10),sharex='col')
    residual=[]
    for row,dev in enumerate(yjdev):
        for col,night in enumerate(['2026-11-05','2026-11-06']):
            st=epoch(night+' 23:20');en=st+460*60000;g=d[d.observing_device_id.eq(dev)&d.markerName.str.startswith('YJ')&d.timestamp.ge(st)&d.timestamp.lt(en)&d.valid];ax=axes[row,col]
            for field,color in [('x','#777777'),('calX','#1769aa')]:
                z=g.pivot(index='timestamp',columns='markerName',values=field);z=z-z.iloc[:10].median();med=z.median(axis=1);real_line(ax,z.index,smooth(med),color=color,label='raw YJ median' if field=='x' else 'recorded YJ residual')
                complete=z.dropna();pcstd=frac=np.nan
                if len(complete)>=20:
                    ev=np.linalg.eigvalsh(np.cov(complete.values,rowvar=False));pcstd=float(np.sqrt(max(ev[-1],0)));frac=float(ev[-1]/ev.sum()) if ev.sum()>0 else np.nan
                residual.append({'device_id':dev,'night_date':night,'field':field,'complete_case_frames':len(complete),'reference_channels':z.shape[1],'pc1_sd_mm':pcstd,'pc1_variance_fraction':frac,'median_trajectory_lowfreq_range_mm':smooth(med).quantile(.95)-smooth(med).quantile(.05),'interpretation':'common_variation_not_physical_error'})
            ax.set_title(f'{dev}, night {night}');format_ax(ax);ax.xaxis.set_major_locator(mdates.HourLocator(interval=2,tz=time([0]).tz));ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M',tz=time([0]).tz));ax.legend(fontsize=8)
    fig.tight_layout();save(fig,'02_YJ_common_residual_two_nights.png');write(pd.DataFrame(residual),'yj_residual_common_metrics.csv')
    # Explicit observations and binding fields, not a reconstructed geometry.
    ed=pd.read_csv(O/'yxj_observation_edges.csv',dtype=str);fig,ax=plt.subplots(figsize=(12,6));left={v:(0,i) for i,v in enumerate(DEVS)};right={v:(2,i) for i,v in enumerate(DEVS)};mid={n:(1,i+.4) for i,n in enumerate(sorted(ed.yxj_name.unique()))}
    for v,(x,y) in left.items():ax.text(x,y,v,ha='center',va='center',bbox={'boxstyle':'round','fc':'#e8eef5','ec':'#adb9c6'})
    for v,(x,y) in right.items():ax.text(x,y,v,ha='center',va='center',bbox={'boxstyle':'round','fc':'#f5ece8','ec':'#c9b5aa'})
    for n,(x,y) in mid.items():ax.text(x,y,n,ha='center',va='center',bbox={'boxstyle':'round','fc':'#edf3e8','ec':'#b5c6a9'})
    for _,r in ed.iterrows():
        a=left[r.observing_device_id];b=mid[r.yxj_name];c=right[r.explicit_MarkerData_bound_device];ax.plot([a[0],b[0]],[a[1],b[1]],color='#1769aa',alpha=.6,lw=1);ax.plot([b[0],c[0]],[b[1],c[1]],color='#b45032',alpha=.6,lw=1,ls='--')
    ax.text(0,-.7,'Observed in Marker_<device>',ha='center',weight='bold');ax.text(1,-.7,'YXJ name',ha='center',weight='bold');ax.text(2,-.7,'Explicit MarkerData.deviceId',ha='center',weight='bold');ax.set_xlim(-.45,2.45);ax.set_ylim(5.6,-1.1);ax.axis('off');ax.set_title('Recorded YXJ observation/binding graph\nEdges are database relationships, not camera geometry or confirmed mounting');save(fig,'03_YXJ_observation_binding_graph.png')
    for ch in sorted(tr.channel.unique()) if 'channel' in tr else sorted((tr.observing_device_id+':'+tr.markerName).unique()):
        if ':YXJ' not in ch:continue
        dev,name=ch.split(':');g=tr[tr.observing_device_id.eq(dev)&tr.markerName.eq(name)&tr.fold.eq('primary_05_to_06')];fig,ax=plt.subplots(figsize=(12,3.7))
        for field,label,color in [('x','raw X',COL['raw_X']),('calX','recorded V51',COL['V51_field_record']),('A_X_mm','A: YJ-guided',COL['A_YJ_guided']),('B_X_mm','B: constrained residual',COL['B_graph_residual'])]:
            z=g.copy();z.loc[~z.valid,field]=np.nan;real_line(ax,z.timestamp,z[field],lw=.85,label=label,color=color,alpha=.9)
        core=g.timestamp.ge(epoch('2026-11-06 23:20'))&g.timestamp.lt(epoch('2026-11-07 07:00'))&g.valid
        ax.set_title(f'{ch}: fit Nov 5, hold out Nov 6 night\nCore coverage: A={g.loc[core,"A_applied"].mean():.1%}, B={g.loc[core,"B_applied"].mean():.1%}; fallback = recorded V51');format_ax(ax);ax.legend(ncol=4,fontsize=8);fig.tight_layout();save(fig,f'04_{dev}_{name}_heldout_AB.png')
    # Same physical YJ6 observed by two devices: raw directions need not match.
    fig,axes=plt.subplots(2,1,figsize=(12,6),sharey=False)
    for ax,night in zip(axes,['2026-11-05','2026-11-06']):
        st=epoch(night+' 23:20');en=st+460*60000
        for dev in ['780639346578','780639376393']:
            g=d[d.observing_device_id.eq(dev)&d.markerName.eq('YJ6')&d.timestamp.ge(st)&d.timestamp.lt(en)&d.valid];s=pd.Series(g.x.values,index=g.timestamp);real_line(ax,s.index,smooth(s-s.iloc[:10].median()),label=dev)
        ax.set_title(f'Same name YJ6, independent observing devices, night {night}');format_ax(ax);ax.legend()
    fig.tight_layout();save(fig,'05_same_YJ6_cross_observer_direction.png')
    print('Plots and full-resolution reference CSVs ready')
if __name__=='__main__':main()
