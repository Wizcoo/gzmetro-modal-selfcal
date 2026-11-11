from relations import *
d=pd.read_pickle(W/'refs.pkl');rows=[]
for ch,g in d.groupby('channel'):
    for night in ['2026-11-05','2026-11-06']:
        st=epoch(night+' 22:00');en=st+9*3600000;z=g[g.timestamp.ge(st)&g.timestamp.lt(en)]
        rows.append({'channel':ch,'night_date':night,'scale_min':z.scale.min(),'scale_max':z.scale.max(),'scale_distinct':z.scale.nunique(),'centerX_min':z.centerX.min(),'centerX_max':z.centerX.max(),'centerY_min':z.centerY.min(),'centerY_max':z.centerY.max(),'units':'native_scale_and_center_units_unverified','calibration_identity':'not_available'})
write(pd.DataFrame(rows),'visible_scale_center_audit.csv')
