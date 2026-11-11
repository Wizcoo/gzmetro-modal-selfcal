from analyze import *
def main():
    rows=[];gaps=[]
    for p in list(C.glob('Marker_780*.pkl'))+[C/'MarkerData.pkl',C/'SubDeviceDisData.pkl']:
        d=tag(pd.read_pickle(p));t=np.sort(d.timestamp.unique());dt=np.diff(t)/1000
        for i in np.flatnonzero(dt>90):gaps.append({'table':p.stem,'before_timestamp_ms':int(t[i]),'after_timestamp_ms':int(t[i+1]),'before_beijing':iso(t[i]),'after_beijing':iso(t[i+1]),'gap_seconds':dt[i],'missing_frames_at_60s_estimate':max(0,int(round(dt[i]/60)-1)),'unit':'seconds'})
        for key,g in d.groupby('phase_key'):
            rows.append({'table':p.stem,'period':key,'rows':len(g),'frames':g.timestamp.nunique(),'start_beijing':iso(g.timestamp.min()),'end_beijing':iso(g.timestamp.max()),'valid_RoiCalState_fraction':g.RoiCalState.eq(1).mean() if 'RoiCalState' in g else np.nan,'missing_finite_x_fraction':g.x.isna().mean() if 'x' in g else np.nan,'unit':'mm_for_coordinate_columns'})
    write_csv(pd.DataFrame(rows),'coverage_by_phase.csv');write_csv(pd.DataFrame(gaps),'time_gaps.csv')
    (OUT/'source_load_audit.json').write_text((W/'load_audit.json').read_text(encoding='utf-8'),encoding='utf-8')
    print(pd.DataFrame(gaps).sort_values('gap_seconds',ascending=False).head(12).to_string(index=False))
if __name__=='__main__':main()
