from relations import *

def main():
    d=pd.read_pickle(W/'refs.pkl');rows=[]
    for seg,st,en in SEGMENTS:
        z=d[d.timestamp.ge(st)&d.timestamp.lt(en)&d.valid&d.markerName.str.startswith('YJ')]
        for dev,g in z.groupby('observing_device_id'):
            for field in ['x','calX']:
                mat=g.pivot(index='timestamp',columns='markerName',values=field);mat-=mat.iloc[:10].median();complete=mat.dropna();median=mat.median(axis=1);sm=smooth(median);e=np.linalg.eigvalsh(np.cov(complete.values,rowvar=False))
                rows.append({'segment':seg,'device_id':dev,'field':field,'start_beijing':iso(st),'end_exclusive_beijing':iso(en),'complete_case_frames':len(complete),'reference_channels':mat.shape[1],'pc1_sd_mm':np.sqrt(max(e[-1],0)),'pc1_variance_fraction':e[-1]/e.sum() if e.sum()>0 else np.nan,'median_trajectory_lowfreq_range_mm':sm.quantile(.95)-sm.quantile(.05),'rows_raw_cal_difference_gt_0p0002_fraction':g.x.sub(g.calX).abs().gt(.0002).mean(),'unit':'mm_API_contract; fraction_dimensionless','actual_gate':'not_recorded','interpretation':'observed_common_variation_not_physical_truth; daytime_not_assumed_static'})
    write(pd.DataFrame(rows),'day_night_common_comparison.csv');print(pd.DataFrame(rows).query("segment in ['day_1106','night_1106','day_1107']")[[ 'segment','device_id','field','median_trajectory_lowfreq_range_mm','rows_raw_cal_difference_gt_0p0002_fraction']].to_string(index=False))
if __name__=='__main__':main()
