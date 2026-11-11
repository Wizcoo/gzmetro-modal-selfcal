from relations import *
BOUND={'YXJ2':'780639298317','YXJ3':'780639333715','YXJ4':'780639346578','YXJ5':'780639376393','YXJ6':'780639414923'}
def main():
    d=pd.read_pickle(W/'refs.pkl');r=pd.read_pickle(W/'relations.pkl');items=[]
    for ch,g in d[d.markerName.str.startswith('YXJ')].groupby('channel'):
        dev,name=ch.split(':')
        for endpoint,device in [('observing',dev),('bound',BOUND[name])]:
            refs=sorted(d[d.observing_device_id.eq(device)&d.markerName.str.startswith('YJ')].channel.unique())
            if not refs:items.append({'yxj_channel':ch,'endpoint':endpoint,'reference_group_device':device,'status':'no_local_YJ_at_endpoint'});continue
            # First name is predefined; do not pick the best holdout correlation.
            anchor=refs[0]
            a=d[d.channel.eq(anchor)&d.valid];b=g[g.valid]
            for seg,st,en in SEGMENTS:
                aa=a[a.timestamp.ge(st)&a.timestamp.lt(en)];bb=b[b.timestamp.ge(st)&b.timestamp.lt(en)];z=pair_stats(smooth(pd.Series(aa.x.values,index=aa.timestamp)),smooth(pd.Series(bb.x.values,index=bb.timestamp)))
                z.update({'yxj_channel':ch,'endpoint':endpoint,'reference_group_device':device,'anchor_reference_channel':anchor,'segment':seg,'start_beijing':iso(st),'end_exclusive_beijing':iso(en),'status':'descriptive_response_not_kinematic_gain','slope_unit':'mm_per_mm'});items.append(z)
    write(pd.DataFrame(items),'endpoint_response_coefficients.csv');z=pd.DataFrame(items);print(z[z.segment.isin(['night_1105','night_1106'])][['yxj_channel','endpoint','anchor_reference_channel','segment','r','slope_b_per_a']].to_string(index=False))
if __name__=='__main__':main()
