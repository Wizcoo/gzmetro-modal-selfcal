from visualize import *

def load(prefix):return pd.concat([pd.read_csv(p) for p in sorted((O/'injection_windows').glob(prefix+'*.csv'))],ignore_index=True)

def main():
 specs=[('right_780639346578_node_step1','node_step1','单节点1mm阶跃：显示延迟与幅度'),('left_780638327479_cohort20_step3','cohort20_step3','20%测点协同3mm：非目标点的额外瞬态')];catalog=[]
 for prefix,scenario,title in specs:
  a=load(prefix);a['extra']=abs(a.D_L1trend_response_mm-a.B0_original_response_mm)
  group=a[a.target] if scenario=='node_step1' else a[~a.target]
  if scenario=='node_step1':name=group.marker_name.iloc[0]
  else:name=group.loc[group.extra.idxmax(),'marker_name']
  z=a[a.marker_name.eq(name)].sort_values('timestamp_ms');fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True,layout='constrained');draw(axes[0],z.timestamp_ms.to_numpy(),[z.known_physical_input_mm.to_numpy(),z.B0_original_response_mm.to_numpy(),z.D_L1trend_response_mm.to_numpy()],['已知观测域增量','B0配对响应','D配对响应'],['#222222','#cb8423','#1565b6']);draw(axes[1],z.timestamp_ms.to_numpy(),[z.B0_original_injected_output_mm.to_numpy(),z.D_L1trend_injected_output_mm.to_numpy()],['B0注入后输出','D注入后输出'],['#cb8423','#1565b6']);axes[0].set_ylabel('配对响应 / mm');axes[0].legend();axes[1].legend();fig.suptitle(title+' / '+name);fig.supxlabel('北京时间；真实现场基线上注入观测域增量，无串联几何投影；无显示滤波/归零。');p=O/'plots/safety'/(prefix+'.png');p.parent.mkdir(exist_ok=True);fig.savefig(p);plt.close(fig);catalog.append(dict(scenario=scenario,marker_name=name,path=p.relative_to(O).as_posix(),selection='target node' if scenario=='node_step1' else 'maximum D minus B0 paired response among exported non-target nodes'))
 save(catalog,'safety_plot_catalog.csv')

if __name__=='__main__':main()
