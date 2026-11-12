from dataio import *

def main():
 rows=[]
 for stage in ['old','validation']:
  for q in pd.read_csv(O/f'input_identity_{stage}.csv',dtype={'device_id':str}).to_dict('records'):
   line,dev=q['line'],q['device_id'];names,methods,fields,d=load(W/stage/f'clean_{line}_{dev}.bin');di={n:i for i,n in enumerate(fields)}
   for mi,m in enumerate(methods):
    z=d['methods']['diag'][:,mi];r={'stage':stage,'line':line,'device_id':dev,'method':m,'frames':len(d),'points':len(names),'start_beijing':iso(d['ts'][0]),'end_beijing':iso(d['ts'][-1]),'scope':'all native stream frames incl baseline/learning/model birth, raw source X; diagnostics export and raw feature extraction excluded'}
    for f in ['pre_us','core_us']:
     v=z[:,di[f]];r[f+'_median']=np.median(v);r[f+'_P99']=np.quantile(v,.99);r[f+'_max']=v.max();r[f+'_max_time_beijing']=iso(d['ts'][np.argmax(v)])
    r['degraded_frames']=int((z[:,di['state_code']]==5).sum());r['Y_mismatch_count']=z[:,di['Y_mismatch_count']].sum();rows.append(r)
 write(pd.DataFrame(rows),'runtime_full_stream.csv')

if __name__=='__main__':main()
