from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import concurrent.futures,argparse,time

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':9,'path.simplify':False,'figure.dpi':115,'savefig.dpi':115})
COLORS=['#202b38','#ca8c20','#46916e','#9462a3','#3c9290','#1565b6','#b6744d','#5c6c25']
LABELS=['同条件 B0','独立 W3','A 温度状态','B 事件估计','C 参考传递','D L1 趋势','W3 后 L1','E 残余因子']

def draw(ax,t,arrays,labels,colors,primary=False):
 time=mdates.date2num(pd.to_datetime(t,unit='ms',utc=True).to_pydatetime());cuts=np.flatnonzero(np.diff(t)>90000)+1;xx=np.insert(time,cuts,time[cuts])
 for i,v in enumerate(arrays):
  yy=np.insert(np.asarray(v,dtype=float),cuts,np.nan);ax.plot(xx,yy,color=colors[i],ls='--' if primary and i==0 else '-',lw=.75 if primary and i==0 else 1.,label=labels[i],alpha=.75 if primary and i==0 else .9)
 ax.grid(alpha=.2);ax.set_ylabel('绝对 X / mm');ax.ticklabel_format(axis='y',style='plain',useOffset=False);ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M',tz=pd.Timestamp.now(tz='Asia/Shanghai').tz))

def figure(p,t,raw,field,series,title,st,en,global_st=None):
 ids=(t>=st)&(t<en);fig,axes=plt.subplots(2,1,figsize=(14,8),sharex=True,layout='constrained');draw(axes[0],t[ids],[raw[ids],field[ids],series[ids,5]],['Raw X','数据库实存 calX','D 影子稳定趋势'],['#909090','#c83636','#1565b6'],True);draw(axes[1],t[ids],[series[ids,i] for i in range(series.shape[1])],LABELS,COLORS);axes[0].set_title('主要三曲线：保留原采样，数据库实存与独立回放分列');axes[1].set_title('严格同输入消融：B0 与各候选独立对照');axes[0].legend(ncol=3,loc='upper left');axes[1].legend(ncol=4,loc='upper left',fontsize=8);axes[0].set_xlim(mdates.date2num(pd.Timestamp(st,unit='ms',tz='UTC').to_pydatetime()),mdates.date2num(pd.Timestamp(en,unit='ms',tz='UTC').to_pydatetime()));fig.suptitle(title,fontsize=13);fig.supxlabel('北京时间；未平滑、未插值、未重新归零。稳定趋势不作为报警输入。',fontsize=9)
 if not np.isfinite(raw[ids]).any():axes[0].text(.5,.5,'本窗无有效观测',transform=axes[0].transAxes,ha='center')
 p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p);plt.close(fig)

def one(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;src=load_data(line,dev);d=np.load(folder/'normal.npz');c=np.load(folder/'final_candidates.npz');t=src['t'];names=src['names'].tolist();raw=src['x'];field=np.where(np.isfinite(raw),src['field'],np.nan);base=d['base'];w3=d['w3'];curves=np.concatenate([base[:,:,None],w3[:,:,None],c['out']],axis=2);night_st=epoch('2026-11-11 23:00');night_en=epoch('2026-11-12 07:00');catalog=[];focus=[];tick=time.monotonic()
 for j,name in enumerate(names):
  # A single image contains the full-history three curves, latest8hours
  # three curves and strict seven-flow ablation for every point.
  fig,axes=plt.subplots(3,1,figsize=(14,10),layout='constrained');draw(axes[0],t,[raw[:,j],field[:,j],curves[:,j,5]],['Raw X','数据库实存 calX','D 影子稳定趋势'],['#909090','#c83636','#1565b6'],True);ids=(t>=night_st)&(t<night_en);draw(axes[1],t[ids],[raw[ids,j],field[ids,j],curves[ids,j,5]],['Raw X','数据库实存 calX','D 影子稳定趋势'],['#909090','#c83636','#1565b6'],True);draw(axes[2],t[ids],[curves[ids,j,i] for i in range(curves.shape[2])],LABELS,COLORS);axes[0].set_title('完整历史：原始与实存、候选绝对坐标');axes[1].set_title('11/11 23:00–11/12 07:00，完整8小时');axes[2].set_title('同条件回放消融：原版核心与各候选');axes[0].legend(ncol=3,fontsize=8,loc='upper left');axes[2].legend(ncol=4,fontsize=8,loc='upper left');fig.suptitle(f'{line} {dev} / {name}   D-L1-2 稳定趋势研究',fontsize=13);fig.supxlabel('北京时间；全部有效样本，无绘图平滑、插值或重新归零。原监测与报警不变。',fontsize=9)
  for a in axes[1:]:a.set_xlim(mdates.date2num(pd.Timestamp(night_st,unit='ms',tz='UTC').to_pydatetime()),mdates.date2num(pd.Timestamp(night_en,unit='ms',tz='UTC').to_pydatetime()))
  if not np.isfinite(raw[ids,j]).any():axes[1].text(.5,.5,'本夜无有效观测；全历史可用部分见上图',transform=axes[1].transAxes,ha='center')
  p=O/'plots/all_markers'/line/dev/(name+'.png');p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p);plt.close(fig);catalog.append(dict(line=line,device_id=dev,marker_name=name,kind=kind(name),path=p.relative_to(O).as_posix(),raw_valid_samples=int(np.isfinite(raw[:,j]).sum()),last_night_valid_samples=int(np.isfinite(raw[ids,j]).sum()),start_beijing=iso(t[0]),end_beijing=iso(t[-1]),curves='Raw grey dashed; stored calX red; D blue; strict B0/W3/A/B/C/D/DW3/E below',display_transformation='none; NaN inserts only break lines over >90s timestamp gaps'))
 if dev in FOCUS:
  preferred={'780639346578':'YXJ6','780639298317':'YXJ4','780639376393':'YXJ6','780638327479':'ZXJ6','780638349768':'ZJ7','780630499846':'ZXJ2'};name=preferred[dev];j=names.index(name);ids=np.flatnonzero((t>=night_st+1200000)&(t<night_en));delta=abs(curves[ids,j,5]-base[ids,j]);peak=ids[int(np.nanargmax(delta))] if np.isfinite(delta).any() else ids[len(ids)//2];center=int(t[peak])
  for label,duration in [('8hours',480),('60minutes',60),('10minutes',10)]:
   st=night_st if duration==480 else max(night_st,min(center-duration*30000,night_en-duration*60000));en=st+duration*60000;p=O/'plots/focus'/f'{line}_{dev}_{name}_{label}.png';figure(p,t,raw[:,j],field[:,j],curves[:,j],f'{line} {dev} / {name}   {label}   绝对坐标',st,en);focus.append(dict(line=line,device_id=dev,marker_name=name,range=label,start_beijing=iso(st),end_exclusive_beijing=iso(en),path=p.relative_to(O).as_posix(),selection='latest whole night; local center maximizes absolute D-B0 difference in actual full-correction range'))
 save(catalog,f'plot_catalog_{line}_{dev}.csv');save(focus,f'focus_catalog_{line}_{dev}.csv') if focus else None;print('PLOTS',line,dev,len(catalog),len(focus),'seconds',time.monotonic()-tick,flush=True);return catalog,focus

def main():
 p=argparse.ArgumentParser();p.add_argument('--device');a=p.parse_args();catalog=[];focus=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
  for plots,fc in pool.map(one,[q for q in roster() if a.device is None or q['device_id']==a.device]):catalog.extend(plots);focus.extend(fc)
 if not a.device:save(catalog,'plot_catalog.csv');save(focus,'focus_plot_catalog.csv')

if __name__=='__main__':main()
