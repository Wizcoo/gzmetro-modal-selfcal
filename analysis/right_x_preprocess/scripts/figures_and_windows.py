from dataio import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'figure.dpi':135,'savefig.dpi':160})
COLORS=['#303846','#e69828','#bd3b36','#7854a8','#087e8b']
LABELS=['原 V51','N1→V51','αβ→V51','局部线性→V51','N3→V51']

def save(fig,name):
 (O/'figures').mkdir(exist_ok=True);fig.savefig(O/'figures'/name,bbox_inches='tight');plt.close(fig)

def main():
 c=pd.read_csv(O/'heldout_key_AB.csv',dtype={'device_id':str});events=[]
 for line,method,kind,metric in [('right','B2_N2_ab','node','ratio_LF_Q95_Q05_mm'),('right','B3_N3','node','ratio_LF_Q95_Q05_mm'),('right','B3_N3','reference','ratio_LF_Q95_Q05_mm'),('right','B2_N2_ab','reference','ratio_LF_Q95_Q05_mm'),('left','B2ll_N2_linear','node','ratio_LF_Q95_Q05_mm')]:
  z=c[c.line.eq(line)&c.method.eq(method)&c.kind.eq(kind)].nlargest(1,metric).iloc[0];events.append(z.to_dict())
 fig,ax=plt.subplots(5,1,figsize=(13,13),layout='constrained')
 for ei,e in enumerate(events):
  line,dev,name,date=e['line'],str(e['device_id']),e['marker_name'],e['date'];names,methods,fields,d=load(W/'validation'/f'clean_{line}_{dev}.bin');di={n:i for i,n in enumerate(fields)};st=epoch(date+' 23:20');en=st+460*60000;mask=(d['ts']>=st)&(d['ts']<en);t=d['ts'][mask];idx=names.index(name);v=d['methods']['cal'][mask,:,idx];time=pd.to_datetime(t,unit='ms',utc=True).tz_convert('Asia/Shanghai');base=np.nanmedian(v[:30,0]);eid=f'E{ei+1:02d}';selected=[n for n in names if n.startswith(('YJ','YXJ','ZJ','ZXJ'))];source=pd.read_pickle(W/f'validation_{line}_{dev}.pkl').set_index(['timestamp','markerName']);rows=[]
  for marker in selected:
   i=names.index(marker)
   for j in np.flatnonzero(mask):
    q={'event_id':eid,'line':line,'device_id':dev,'marker_name':marker,'timestamp_ms':int(d['ts'][j]),'time_beijing':iso(d['ts'][j]),'rawX_mm':d['raw'][j,i],'field_calX_mm_observation_only':d['field'][j,i],'rawY_mm':d['yinput'][j,i],'original_V51_calY_mm':d['youtput'][j,i]}
    sk=(int(d['ts'][j]),marker)
    if sk in source.index:
     s=source.loc[sk];q.update(source_db=s.source_db,source_rowid=int(s._source_rowid),RoiCalState=s.RoiCalState,centerX_unverified_domain=s.centerX,centerY_unverified_domain=s.centerY,scale_unverified=s.scale)
    for mi,m in enumerate(methods):
     pre=d['methods']['pre'][j,mi,i];cal=d['methods']['cal'][j,mi,i];q.update({m+'_preX_mm':pre,m+'_calX_mm':cal,m+'_raw_minus_pre_mm':d['raw'][j,i]-pre,m+'_pre_minus_cal_mm':pre-cal})
    for f in ['gate','modes_ready','n_history','n_frame_valid','state_code','v1','v2','v3'] :q['B0_'+f]=d['methods']['diag'][j,0,di[f]]
    q['N3_common_qualified']=d['methods']['diag'][j,-1,di['common_qualified']];rows.append(q)
  write_parts(pd.DataFrame(rows),f'windows/{eid}_{line}_{dev}_{date}.csv')
  for mi in [0,1,2,3,4]:ax[ei].plot(time,v[:,mi]-base,lw=1 if mi!=0 else 1.5,color=COLORS[mi],label=LABELS[mi],alpha=.85)
  ax[ei].set_title(f'{eid}  {line} {dev[-6:]} / {name}  夜起 {date}；选择依据：{e["method"]} 低频退化')
  ax[ei].set_ylabel('X / mm\n相对同一局部起点');ax[ei].grid(alpha=.2);ax[ei].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=time.tz))
  e.update(event_id=eid,start_beijing=iso(st),end_exclusive_beijing=iso(en),selection='predeclared worst ratio per method/key kind; plots are output stability, not true displacement accuracy')
 ax[0].legend(ncol=5,fontsize=9);fig.suptitle('冻结后新增夜验证：完整连续曲线与失败通道（不插值、不填补）',fontsize=15);save(fig,'key_continuous.png');write(pd.DataFrame(events),'event_index.csv')

 fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
 for row,line in enumerate(['right','left']):
  z=c[c.line.eq(line)]
  for col,f in enumerate(['ratio_LF_Q95_Q05_mm','ratio_step_abs_P99_mm']):
   methods=[m for m in z.method.unique() if m!='B1_N1'];vals=[z[z.method.eq(m)][f].dropna().to_numpy() for m in methods];axes[row,col].boxplot(vals,tick_labels=[LABELS[['B0_raw','B1_N1','B2_N2_ab','B2ll_N2_linear','B3_N3'].index(m)] for m in methods],showfliers=True);axes[row,col].axhline(1,color='#333',ls='--');axes[row,col].axhline(1.1,color='#bd3b36',ls=':');axes[row,col].set_title(line+('：5 分钟低频范围比' if col==0 else '：相邻步 P99 比'));axes[row,col].set_ylabel('相对原 V51（小于 1 为波动减少）');axes[row,col].grid(axis='y',alpha=.2)
 fig.suptitle('全部关键通道 × 夜：中位数不能掩盖最差通道',fontsize=15);save(fig,'all_key_channel_ratios.png')

 old=pd.read_csv(O/'old_noise_components.csv');sp=pd.read_csv(O/'old_spatial_common.csv');freq=pd.read_csv(O/'old_frequency_components.csv');fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
 groups=['YJ','YXJ','ordinary'];axes[0].boxplot([old[old.kind.eq(k)].C0_residual_step_lag1_r.dropna() for k in groups],tick_labels=groups);axes[0].axhline(-.5,ls=':',color='#bd3b36');axes[0].set_title('残余增量负相关：支持随机样抖动');axes[0].set_ylabel('增量 lag-1 相关系数')
 axes[1].boxplot([old[old.kind.eq(k)].raw_step_vs_C0_common_step_r.dropna() for k in groups],tick_labels=groups);axes[1].set_title('原始增量与共模修正增量相关');axes[1].set_ylabel('相关系数；不是噪声占比')
 med=freq[['period2to6min_energy_fraction','period6to30min_energy_fraction','period_over30min_energy_fraction']].median();axes[2].bar(['2–6 min','6–30 min','>30 min'],med,color=['#bd3b36','#e69828','#087e8b']);axes[2].set_title('原始时序分频能量中位数');axes[2].set_ylabel('去线性趋势后能量比例')
 for a in axes:a.grid(axis='y',alpha=.2)
 fig.suptitle('旧右线数据：随机样成分与共同运动同时存在；约一分钟采样不代表提点帧率',fontsize=14);save(fig,'noise_identifiability.png')

 dev='780639173835';line='right';onset=1794423600000;names,methods,fields,d=load(W/'validation'/f'clean_{line}_{dev}.bin');idx=pd.Index(d['ts']);node=next(n for n in names if n.startswith('YXJ'));ni=names.index(node);cases=[node+'_step1','nodes_ramp3_3h','repeated_pulse3','multiple_step3','missing_nodes'];fig,axes=plt.subplots(4,2,figsize=(13,12),layout='constrained')
 for ci,scenario in enumerate(cases):
  kn,mm,ff,z=load(W/'validation'/f'{scenario}_{onset}_{line}_{dev}.bin');ki=kn.index(node);j=idx.get_indexer(z['ts']);truth=z['raw'][:,ki]-d['raw'][j,ni];minutes=(z['ts']-onset)/60000.;rows=[]
  for col,layer in enumerate(['pre','cal']):
   if ci>=4:continue
   axes[ci,col].plot(minutes,truth,color='#777',ls='--',lw=2,label='已知观测域增量')
   for mi in range(5):
    response=z['methods'][layer][:,mi,ki]-d['methods'][layer][j,mi,ni];axes[ci,col].plot(minutes,response,color=COLORS[mi],lw=1,label=LABELS[mi])
   axes[ci,col].set_title(scenario+('：前处理响应' if layer=='pre' else '：V51 后响应'));axes[ci,col].set_ylabel('配对增量 / mm');axes[ci,col].set_xlabel('注入后 / min');axes[ci,col].grid(alpha=.2);axes[ci,col].ticklabel_format(axis='y',style='plain',useOffset=False)
   if scenario.endswith('step1'):axes[ci,col].set_ylim(-.05,1.15)
   if scenario=='missing_nodes':axes[ci,col].axvspan(0,10,color='#e69828',alpha=.2)
  for k,ts in enumerate(z['ts']):
   r={'line':line,'device_id':dev,'marker_name':node,'scenario':scenario,'timestamp_ms':int(ts),'time_beijing':iso(ts),'known_observation_increment_mm':truth[k],'clean_rawX_mm':d['raw'][j[k],ni],'injected_rawX_mm':z['raw'][k,ki]}
   for mi,m in enumerate(methods):
    for layer in ['pre','cal']:
     r[m+'_'+layer+'_paired_response_mm']=z['methods'][layer][k,mi,ki]-d['methods'][layer][j[k],mi,ni];r[m+'_clean_'+layer+'X_mm']=d['methods'][layer][j[k],mi,ni];r[m+'_injected_'+layer+'X_mm']=z['methods'][layer][k,mi,ki]
    for f in ['gate','n_frame_valid','n_learn','n_corrected','common_qualified','pre_changed']:
     r[m+'_clean_'+f]=d['methods']['diag'][j[k],mi,fields.index(f)];r[m+'_injected_'+f]=z['methods']['diag'][k,mi,ff.index(f)]
   rows.append(r)
  write(pd.DataFrame(rows),f'windows/injection_{scenario}.csv')
 axes[0,0].legend(fontsize=8,ncol=3);fig.suptitle('11-12 03:00 右线 173835 / '+node+'：已知输入保真，不是世界坐标精度',fontsize=14);save(fig,'injection_shapes.png')

 # One complete three-stage view, rather than additional per-channel plots.
 dev='780639346578';names,methods,fields,d=load(W/'validation'/f'clean_right_{dev}.bin');k=names.index('YJ5');st=epoch('2026-11-09 23:20');mask=(d['ts']>=st)&(d['ts']<st+460*60000);time=pd.to_datetime(d['ts'][mask],unit='ms',utc=True).tz_convert('Asia/Shanghai');raw=d['raw'][mask,k];pre=d['methods']['pre'][mask,:,k];cal=d['methods']['cal'][mask,:,k];fig,axes=plt.subplots(3,1,figsize=(13,8),sharex=True,layout='constrained');origin=np.nanmedian(raw[:30]);co=np.nanmedian(cal[:30,0])
 for mi in range(5):
  axes[0].plot(time,pre[:,mi]-origin,color=COLORS[mi],lw=1,label=LABELS[mi]);axes[1].plot(time,raw-pre[:,mi],color=COLORS[mi],lw=1);axes[2].plot(time,cal[:,mi]-co,color=COLORS[mi],lw=1)
 for a,title in zip(axes,['Raw / preX：各组前处理输入的变化趋势','rawX−preX：仅前处理改变量（绝对零点）','V51 后 calX：各组独立完整历史与修正']):a.set_title(title);a.set_ylabel('X / mm');a.grid(alpha=.2)
 axes[0].legend(ncol=5,fontsize=9);axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=time.tz));fig.suptitle('右线 346578 / YJ5，11-09 夜：输入层与输出层各按原解首30帧中位数对齐',fontsize=14);save(fig,'raw_pre_cal_chain.png')

if __name__=='__main__':main()
