from analyze import *
def main():
    rows=[];points=[];lags=[];md=tag(pd.read_pickle(C/'MarkerData.pkl'));down=md[md.markerName.str.startswith('YD')].pivot(index='timestamp',columns='markerName',values='x0')
    # Per-device, per-marker night metrics use each entire 23:20–07:00 span,
    # including midnight. No concatenation of unrelated nights.
    for p in C.glob('Marker_780*.pkl'):
        dev=p.stem.split('_')[1];d=tag(pd.read_pickle(p))
        for night in ['2026-11-05','2026-11-06']:
            st=int(pd.Timestamp(night+' 23:20',tz=TZ).timestamp()*1000);en=st+460*60000
            g=d[d.timestamp.ge(st)&d.timestamp.lt(en)].copy();v=g[g.RoiCalState.eq(1)&~g.ambiguous_business_key]
            for axis in ['X','Y']:
                raw=axis.lower();cal='cal'+axis
                r=v.pivot(index='timestamp',columns='markerName',values=raw);a=v.pivot(index='timestamp',columns='markerName',values=cal)
                struct=[n for n in r if n.startswith('YD')];rpv=r.max()-r.min();cpv=a.max()-a.min();red=1-cpv/rpv
                rcm=(r[struct]-r[struct].iloc[:10].median()).median(axis=1);ccm=(a[struct]-a[struct].iloc[:10].median()).median(axis=1)
                for name in r:
                    z=v[v.markerName.eq(name)].sort_values('timestamp');dt=z.timestamp.diff().between(30000,90000);dr=z[raw].diff().where(dt).abs();dc=z[cal].diff().where(dt).abs()
                    points.append({'night_date':night,'device_id':dev,'marker_name':name,'axis':axis,'unit':'mm','start_beijing':iso(st),'end_exclusive_beijing':iso(en),'valid_frames':len(z),'raw_pv_mm':rpv[name],'cal_pv_mm':cpv[name],'pv_reduction_fraction':red[name],'raw_step_p99_mm':dr.quantile(.99),'cal_step_p99_mm':dc.quantile(.99),'nonzero_correction_fraction':(z[raw]-z[cal]).abs().gt(1e-6).mean()})
                row={'night_date':night,'device_id':dev,'axis':axis,'unit':'mm','start_beijing':iso(st),'end_exclusive_beijing':iso(en),'observed_frames':g.timestamp.nunique(),'valid_marker_observations':len(v),'marker_count':len(r.columns),'raw_marker_pv_median_mm':rpv.median(),'cal_marker_pv_median_mm':cpv.median(),'marker_pv_reduction_median_fraction':red.median(),'markers_increased_pv_gt10pct':int((red<-.1).sum()),'markers_with_nonzero_correction':int(((r-a).abs()>1e-6).any().sum()),'raw_device_common_pv_mm':rcm.max()-rcm.min(),'cal_device_common_pv_mm':ccm.max()-ccm.min()}
                rows.append(row)
                # Lagged same-name associations for each point are exported for
                # selected critical markers separately; no causal transfer fit.
                if axis=='X':
                    for name in ['YD2603','YD3104','YD2304','YD1604']:
                        if name not in r or name not in down:continue
                        z=v[v.markerName.eq(name)].set_index('timestamp').sort_index();y=down[name].reindex(z.index)
                        for lag in [-10,-5,-2,-1,0,1,2,5,10]:
                            # Index by real timestamp with a strict 2s tolerance;
                            # lag>0 asks whether earlier upstream aligns with now.
                            target=z.index.to_numpy()-lag*60000;loc=z.index.get_indexer(target,method='nearest',tolerance=2000)
                            good=loc>=0;xx=np.full(len(z),np.nan);rawv=z.calX.values;xx[good]=rawv[loc[good]]
                            lags.append({'night_date':night,'device_id':dev,'marker_name':name,'lag_minutes_upstream_earlier_if_positive':lag,'matched_pairs':int((np.isfinite(xx)&np.isfinite(y)).sum()),'calX_vs_x0_r':corr(xx,y),'interpretation':'descriptive_lagged_association_not_filter_identification'})
    write_csv(pd.DataFrame(rows),'whole_night_device_comparison.csv');write_csv(pd.DataFrame(points),'whole_night_marker_comparison.csv');write_csv(pd.DataFrame(lags),'critical_marker_lag_correlations.csv')
    print(pd.DataFrame(rows).to_string(index=False))
    pts=pd.DataFrame(points);print('WORST X',pts[pts.axis.eq('X')].sort_values('pv_reduction_fraction').head(12).to_string(index=False))
if __name__=='__main__':main()
