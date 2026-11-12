from common import *
import html

def table(frame):
 cols=list(frame.columns);return '| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None))

def main():
 v=pd.read_csv(O/'key_and_all_overview.csv');s=pd.read_csv(O/'signal_safety_overview.csv');normal=pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in (O/'metrics').glob('*.csv')]);late=normal[normal.scope.eq('night23_07')&normal.night.ge('2026-11-09')&normal.kind.ne('ordinary')&normal.method.eq('D_L1trend')];rows=[]
 for (line,dev),g in late.groupby(['line','device_id']):rows.append(dict(line=line,device_id=dev,key_marker_nights=len(g),D_over_B0_P95_P05=g.ratio_B0_P95_P05_mm.median(),D_over_W3_P95_P05=g.ratio_W3_P95_P05_mm.median(),D_over_B0_60min=g.ratio_B0_slow60min_change_P99_mm.median(),worst_D_over_B0_P95_P05=g.ratio_B0_P95_P05_mm.max()))
 devices=pd.DataFrame(rows);save(devices,'key_device_comparison.csv');ds=devices.copy();ds.iloc[:,3:]=ds.iloc[:,3:].round(4);score=v[v.channel_group.eq('key')][['line','method','marker_nights','median_ratio_B0_P95_P05_mm','median_ratio_W3_P95_P05_mm','median_ratio_B0_PV_mm','worst_ratio_B0_P95_P05_mm','median_ratio_B0_slow60min_change_P99_mm']].copy();score.iloc[:,3:]=score.iloc[:,3:].round(4);worst=late.nlargest(6,'B0_P95_P05_mm')[['line','device_id','marker_name','night','B0_P95_P05_mm','P95_P05_mm','W3_P95_P05_mm']].copy();worst.iloc[:,4:]=worst.iloc[:,4:].round(4);key=v[v.channel_group.eq('key')&v.method.eq('D_L1trend')].set_index('line');allv=v[v.channel_group.eq('all')&v.method.eq('D_L1trend')].set_index('line');inj=s[s.method.eq('D_L1trend')&s.scenario.isin(['node_step1','node_step3','ramp1_1h','ramp3_3h','cohort20_step3','pulse1frame3','pulse2frame3','thermal_structural_pair'])][['line','scenario','median_retention','max_abs_additional_amplitude_loss_mm','median_extra_delay95_vs_B0_seconds','maximum_extra_delay95_vs_B0_seconds','maximum_additional_slope_error_abs_mm_per_hour','median_peak_retention','max_extra_nontarget_peak_mm']].copy();inj.iloc[:,2:]=inj.iloc[:,2:].round(5)
 facts=json.loads((O/'result_facts.json').read_text());em=pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in (O/'safety_E').glob('*_manifest.csv')],ignore_index=True);save(em,'E_injection_manifest.csv');validation=json.loads((O/'validation.json').read_text());
 text=f'''# 实测判断：可提供独立影子趋势，尚未解决小时级异常漂移

完成五种机制、原版B0及独立W3、12设备524点全历史回放。A–D完成{facts['all_scenes']}个原核心有效修正窗注入续跑；E另完成{len(em)}个重点设备同输入续跑。所有失败和非目标通道保留。当前最值得工程实现的是 **D-L1-2只读旁路稳定趋势**，不能替换监测值或报警，不能宣称解决了温漂、真实沉降误差或最终X0。

## 三个问题的直接回答

1. **有比纯W3更收窄整夜波动的候选，但收益不均。** D在11/09–11/11三个后期历史夜，关键YJ/YXJ/ZJ/ZXJ的P95−P5相比B0中位改善右线{(1-key.loc['right','median_ratio_B0_P95_P05_mm'])*100:.1f}%、左线{(1-key.loc['left','median_ratio_B0_P95_P05_mm'])*100:.1f}%；相比W3再改善右线{(1-key.loc['right','median_ratio_W3_P95_P05_mm'])*100:.1f}%、左线{(1-key.loc['left','median_ratio_W3_P95_P05_mm'])*100:.1f}%。全点对应B0改善{(1-allv.loc['right','median_ratio_B0_P95_P05_mm'])*100:.1f}%/{(1-allv.loc['left','median_ratio_B0_P95_P05_mm'])*100:.1f}%，不能用它代替关键点结果。左327479关键点总体比W3约差2%，应列为重点回退/观察设备。
2. **改善主要来自可量化的时序曲率约束，尚无证据证明真正识别了设备扰动。** D关键点60分钟漂移中位比右线{key.loc['right','median_ratio_B0_slow60min_change_P99_mm']:.4f}、左线{key.loc['left','median_ratio_B0_slow60min_change_P99_mm']:.4f}，基本没改善。1mm节点持续阶跃的额外95%延迟中位右9min、左13min；脉冲削弱、转折过冲、协同运动的非目标额外差异可明显。数学降波动不是物理准确度。
3. **可以提供不改变原监测/报警路径的影子版本。** 已提供独立C++模块、CSV适配器和JSON重启状态；只追加stableTrendX/差值/资格/版本，原calX/calY及告警载荷原样保留。白天exact B0。当前适合并列显示和冻结后的新夜影子验证，未部署，不作为报警输入；没有真实串联几何，未做最终X0 A/B。

## 全部关键通道对照（比值<1才是波动减少）

{table(score)}

每个比值先在相同点、相同夜、相同有效帧计算，再取点夜中位数；不是所有点混合后分位数。key右60点夜、左54点夜；无关键前缀的右333715仍在全点统计/图册中。完整全部夜和两个scope见metrics，不只展示改善结果。

## 设备差异和最严重窗口

{table(ds)}

后期历史中原B0关键通道波动最大的窗口（夜=当天23点至次日7点）：

{table(worst)}

左327479:ZXJ6在11/09夜B0 P95−P5=9.7614mm，D=9.5568mm，W3=9.3413mm；D不解决该主导低频起伏。右346578:YJ6在11/10夜B0=1.4722mm，D=1.3796mm，仍比W3的1.3610mm差。不能把全设备平均收益承诺给这些严重通道。

## 五种机制的实测取舍

- A动态温度：热惯性/升降温分量和历史独立验证均实现。大多数点不满足预测资格；中位比接近1，最差普通点夜左约1.714、右约1.448，不建议工程补偿。关联性和物理扰动预测力不同。
- B事件切换：保留较多事件形态，但约半夜进入运动透传，关键整夜范围改善有限，整体弱于W3。可作为事件标注研究，而非用固定EMA替代；不未经验证与D叠加成新通过方案。
- C参考传递：严格目标验证和参考故障保护，很多设备资格不足。关键中位收益接近0；个别YXJ/参考仍退化。保留原输出是必要回退，不能为覆盖率放松资格。
- D L1曲率趋势：整体范围和步差最稳定地改善，是本轮显示候选；小时级慢漂未改善，必须接受并展示延迟/过冲成本。W3+D没有稳定叠加收益，个别点相对B0恶化近3倍，因此首选直接B0→D。
- E低秩+稀疏：实际全设备运行，避免参考单点主导，也尝试隔离20%局部持续变化；关键P95−P5中位约1，右最差2.442、左最差1.223。空间共同性不能自动变成可扣除的扰动，停留研究，不靠后续按夜调参救结果。

## 波形与安全代价（D，全点完整见safety）

{table(inj)}

持续阶跃的末段幅度多数接近B0，不代表瞬态安全：节点1mm典型新增延迟9–13分钟，20%协同3mm中有更长额外延迟；单帧3mm峰值显著减小。20%协同3mm非目标点的最大新增瞬态差可达约2mm，缺失恢复亦有明显时序差异。原版自身也会在共模学习/求解中吸收或传播注入量；表中additional是**相对B0新增**，不能用原版错误来免责。

注入均在原核心ready、gate=1的真实窗口开始：11/10及11/12 03:00，包含1/3mm节点/普通点阶跃、1/3h斜坡、20%协同、参考+节点、单/双帧冲击、参考异常、温变+真增量、缺失、重启、跨夜。温变为已知合成观测域共同增量，不是用真实温度得到了物理真值；参考共同运动与设备扰动仍可能不可辨识。

`injection_failure_index.csv`保留最差点；`plots/safety/`展示一例节点延迟和一例非目标变化。稳定趋势不能承担突变检测；原曲线和原报警必须可见。D不检测物理事件，其新增事件列不代表原报警已经解除。

## 夜/昼、复现与证据强度

- 新候选所有白天输入输出逐值等于B0，晨间按实际gate释放差值。对D逐帧分解原版变化、滤波变化及gate切换项，公式残差<1e−10mm；晨间纯gate变化项最大0.2923mm，夜间启用段最大0.6066mm。因此渐入/渐出不等于无切换代价，严重设备必须并列观察。完整分解见transition_decomposition。`night_day_transitions`报告新增步差，不能只看最终差值归零而称“切换无跳变”。缺帧/时间倒退重置短窗；JSON重启与连续处理一致。
- Y逐位一致，原接口不透明告警载荷不改；真实现场报警引擎和云平台串联接口不可得，所以仅验证了旁路契约，不冒充现场功能验收。
- 独立回核{validation['continuous_trace_rows_checked']:,}条连续CSV、{validation['numerical_comparisons']:,}个数值比较；8个只读源DB、12原包和生产V51/V53哈希未变；524全点图+18重点图。D独立13,034个原对偶数值证书全部通过，正常及注入无未认证点帧。
- 所有历史结果仅为开发/按时间向前检验；本轮后增加的结果也不能冒充客户未见夜验收。下一步冻结D及差值/事件显示契约，收集独立事件记录和未见完整夜，专门验收严重设备与切换，而不是继续在当前历史上挑最佳PV。

结论：**可交付可独立影子验证的稳定趋势工具；不能交付已证实的小时级硬件漂移消除或监测精度升级。**
'''
 (O/'findings.md').write_text(text,encoding='utf-8',newline='\n')
 catalog=pd.read_csv(O/'plot_catalog.csv').to_dict('records');focus=pd.read_csv(O/'focus_plot_catalog.csv').to_dict('records');data=json.dumps(catalog,ensure_ascii=False);fc=json.dumps(focus,ensure_ascii=False)
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>左右线 X 稳定趋势图册</title><style>body{font:16px system-ui,sans-serif;margin:24px;color:#243243;background:#f4f6f8}header{max-width:1200px}select,button{font:inherit;padding:8px;margin:4px}img{width:100%;background:white;border:1px solid #ccd3dc;margin-top:12px}small{display:block;line-height:1.7}a{color:#145dae}nav{position:sticky;top:0;background:#f4f6f8;padding:6px}#meta{margin:8px}</style><header><h1>左右线 X：524点完整图册</h1><p>灰虚Raw、红实存calX、蓝D影子趋势；独立B0消融另列。无绘图平滑、插值或重新归零。稳定趋势不能用于报警或当作物理真值。</p><p><a href="findings.md">实测结论</a> · <a href="README.md">口径与复现</a> · <a href="key_device_comparison.csv">关键设备比较</a></p></header><nav><select id="device"></select><select id="marker"></select><select id="range"><option value="all">全历史+最新整夜+消融</option><option value="8hours">重点8小时</option><option value="60minutes">重点60分钟</option><option value="10minutes">重点10分钟</option></select><button id="previous">上一点</button><button id="next">下一点</button></nav><div id="meta"></div><a id="open" target="_blank"><img id="plot" alt="连续曲线"></a><small>本页面只读取本目录相对路径图片，无联网服务。重点局部窗以D−B0最大差异选取，非物理误差真值。所有设备/点的统计都保留。</small><script>const rows=CATALOG, focus=FOCUS;const d=document.querySelector('#device'),m=document.querySelector('#marker'),r=document.querySelector('#range');for(const id of [...new Set(rows.map(x=>x.device_id))]){const x=rows.find(x=>x.device_id===id);d.add(new Option(x.line+' '+id,id));}function markers(){m.replaceChildren();for(const x of rows.filter(x=>x.device_id===d.value))m.add(new Option(x.marker_name+' ('+x.kind+')',x.marker_name));show();}function show(){let x=rows.find(x=>x.device_id===d.value&&x.marker_name===m.value);if(r.value!=='all'){let f=focus.find(f=>f.device_id===d.value&&f.marker_name===m.value&&f.range===r.value);if(f)x={...x,...f};else{r.value='all';}}document.querySelector('#plot').src=x.path;document.querySelector('#open').href=x.path;document.querySelector('#meta').textContent=x.line+' '+x.device_id+' / '+x.marker_name+' | 全历史有效样本 '+x.raw_valid_samples+'；最新夜 '+x.last_night_valid_samples;}d.onchange=markers;m.onchange=show;r.onchange=show;for(const [id,step] of [['previous',-1],['next',1]])document.querySelector('#'+id).onclick=()=>{m.selectedIndex=(m.selectedIndex+step+m.length)%m.length;show();};markers();</script></html>'''.replace('CATALOG',data).replace('FOCUS',fc)
 (O/'index.html').write_text(page,encoding='utf-8',newline='\n');save_json({'main_candidate':'D_L1trend','second_expanded':'B_event','all_five_expanded_to_12_devices':True,'E_injection_focus_only':True,'decision':'whole-night range, worst channels and known waveform costs evaluated together; D only for shadow display, not hour-scale drift or physical accuracy','no_new_PV_parameter_search':True,'original_monitor_and_alarm_unchanged':True},'expansion_decision.json');print('REPORT',len(catalog),len(em))

if __name__=='__main__':main()
