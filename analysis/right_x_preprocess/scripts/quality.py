from dataio import *

def main():
 rows=[]
 for q in pd.read_csv(O/'input_identity_validation.csv',dtype={'device_id':str}).to_dict('records'):
  line,dev=q['line'],q['device_id'];names,_,_,d=load(W/'validation'/f'clean_{line}_{dev}.bin');source=pd.read_pickle(W/f'validation_{line}_{dev}.pkl')
  for i,n in enumerate(names):
   z=source[source.markerName.eq(n)].sort_values('timestamp');valid=np.isfinite(d['raw'][:,i]);vt=d['ts'][valid];rows.append({'line':line,'device_id':dev,'marker_name':n,'start_beijing':iso(d['ts'][0]),'end_beijing':iso(d['ts'][-1]),'device_frames':len(d),'record_rows':len(z),'missing_observation_frames':len(d)-len(z),'ROI_state_not1_rows':int(z.RoiCalState.ne(1).sum()),'valid_X_frames':int(valid.sum()),'valid_Y_frames':int(np.isfinite(d['yinput'][:,i]).sum()),'valid_X_max_gap_minutes':np.diff(vt).max()/60000 if len(vt)>1 else np.nan,'unit':'X/Y V51 mm contract; gaps minutes; counts rows/frames; damaged unknown tails not inferred'})
 write(pd.DataFrame(rows),'observation_quality.csv')

if __name__=='__main__':main()
