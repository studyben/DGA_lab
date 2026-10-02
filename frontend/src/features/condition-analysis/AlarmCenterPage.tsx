import { useState } from 'react';
import { useAuth } from '../../Auth';
import { alarmRequest, alarmStates, alarmStatus, time, useAlarms, type AlarmDetail, type AlarmList, type Evidence } from './alarmApi';
import { statusNames, reasons } from './healthApi';
import './health.css';
import './alarms.css';

const path='/assets/analysis/alarms';
const typeNames:Record<string,string>={DGA:'DGA',MOISTURE:'微水',BREAKDOWN_VOLTAGE:'击穿电压'};
const why:Record<string,string>={...reasons,not_later_sample:'没有严格晚于最近异常的正常采样结果；同一采样或规则调整不能解除。',different_method_or_unit:'最新结果与异常基线的方法版本或单位不一致，不能自动解除。',still_abnormal:'最新结果仍异常。',later_normal:'后续同方法、同单位的完整正常结果满足解除条件。'};
const eventNames:Record<string,string>={OPENED:'产生报警',ACKNOWLEDGED:'确认报警',ABNORMAL_UPDATED:'更新异常依据',RESOLVED:'正常结果解除',RECOVERY_INVALIDATED:'解除证据变化，撤销原解除',CONSOLIDATED:'并入原报警',BASELINE_INHERITED:'继承后续异常依据',OBSERVATION_CHANGED:'更新评估或来源有效性'};
const filterKeys=['scope','product_line','site','customer','equipment','asset_id','test_type','analyte','severity','state','from_date','to_date','page','page_size'];
function link(query:URLSearchParams,patch:Record<string,string>){const next=new URLSearchParams(query);Object.entries(patch).forEach(([key,value])=>value?next.set(key,value):next.delete(key));return path+'?'+next;}

function Source({source}:{source:Evidence}){
  const {can}=useAuth();const m=source.measurement;
  return <article className="health-source">
    <strong>{m.barcode} · {m.analyte}：{m.qualifier==='EQ'?'':m.qualifier+' '}{m.value??'—'} {m.unit??'单位待配置'}</strong>
    <p className="health-help">采样：{time(m.sampled_at)} · 检测：{time(m.measured_at)}<br/>方法：{m.method_name} · {m.version_label} · {m.method_version_id}<br/>采样时现场：{m.sampling_context?.site_name??'不适用'} · 客户：{m.sampling_context?.customer_name??'不适用'}</p>
    {source.rule&&<p className="health-help">规则：{source.rule.name} · {source.rule.operator} {source.rule.threshold} {source.rule.unit}<br/>规则版本：{source.rule.id}</p>}
    <div className="alarm-actions">{can('laboratory.write')&&<a href={'/lab/workbench?barcode='+encodeURIComponent(m.barcode)}>检测记录</a>}{can('laboratory.read')&&<a href={'/lab/reports?barcode='+encodeURIComponent(m.barcode)}>条码报告</a>}</div>
    <details><summary>来源标识</summary><p className="health-help">检测记录：{m.test_id}<br/>样品：{m.sample_id}<br/>定稿标识：{m.finalization_token}</p></details>
  </article>;
}

function Detail({id,query}:{id:string;query:URLSearchParams}){
  const {can,session}=useAuth();const {data,error,retry}=useAlarms<AlarmDetail>('/'+encodeURIComponent(id));
  const [note,setNote]=useState(''),[busy,setBusy]=useState(false),[failure,setFailure]=useState(''),[message,setMessage]=useState('');
  async function acknowledge(){
    if(!data||busy)return;setBusy(true);setFailure('');setMessage('');
    try{await alarmRequest('/'+encodeURIComponent(id)+'/acknowledgement',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session?.csrf_token??''},body:JSON.stringify({expected_revision:data.revision,note}),signal:AbortSignal.timeout(15000)});setMessage('确认操作已保存。');setNote('');retry();}
    catch(e){setFailure(e instanceof Error?e.message:'确认失败，说明已保留。');}finally{setBusy(false);}
  }
  return <section className="health-card" aria-label="报警详情"><div className="health-toolbar"><a href={link(query,{alarm:''})}>返回报警列表</a><button disabled={busy} onClick={retry}>刷新报警详情</button></div>
    {failure&&<p role="alert">{failure}</p>}{message&&<p role="status">{message}</p>}
    {error?<p role="alert">{error}</p>:!data?<p role="status">正在读取报警详情…</p>:<>
      <h2>{data.current_asset?.serial_number??data.asset_id} · {data.analyte}</h2>
      <p className={!data.superseded_by&&data.state!=='RESOLVED'?'health-abnormal alarm-status':'alarm-status'}>{alarmStatus(data)} · 保留的异常级别：{statusNames[data.severity]}</p>
      <p className="health-help">当前位置：{data.current_asset?.site_name??'维修中心 / 无当前现场'} · 当前客户：{data.current_asset?.customer_name??'不适用'}<br/>报警产生：{time(data.opened_at)} · 最近检查：{time(data.checked_at)}</p>
      {can('assets.read')&&<a href={'/assets/equipment/'+encodeURIComponent(data.asset_id)}>查看物理设备</a>}
      {data.superseded_by&&<p>本事件历史保留，后续处理见<a href={link(query,{alarm:data.superseded_by})}>原报警</a>；并入不代表恢复正常。</p>}
      <p className="health-help">最新评估说明：{why[data.observation.reason]??data.observation.reason} 报警状态保留历史处理结果，不等同于当前健康评估。</p>
      {!data.trigger_currently_finalized&&<p role="status">原触发证据已撤回或重新定稿，历史记录保留，不因此自动解除。</p>}
      {data.acknowledgement?<p>确认人：{data.acknowledgement.actor_name} · {time(data.acknowledgement.at)}<br/>确认说明：{data.acknowledgement.note}</p>:can('analysis.acknowledge')&&data.state!=='RESOLVED'&&!data.superseded_by?<form className="health-form" onSubmit={e=>{e.preventDefault();void acknowledge();}}><label className="health-wide">确认说明<textarea required maxLength={1000} disabled={busy} value={note} onChange={e=>setNote(e.target.value)}/></label><button disabled={busy||!note.trim()}>确认报警</button></form>:null}
      <h3>触发来源</h3><Source source={data.trigger}/>
      <details><summary>最近异常依据</summary>{data.latest_abnormal.map((source,i)=><Source key={i} source={source}/>)}</details>
      {data.recovery&&<><h3>解除依据</h3>{data.recovery.sources.map((source,i)=><Source key={i} source={source}/>)}</>}
      <h3>报警时间线</h3><ol className="alarm-timeline">{data.events.map((event,i)=><li key={i}><strong>{eventNames[event.action]??event.action}</strong> · {time(event.occurred_at)}<p className="health-help">{alarmStatus(event.data)} · {statusNames[event.data.severity]}{event.action==='ACKNOWLEDGED'&&event.data.acknowledgement?` · ${event.data.acknowledgement.actor_name}：${event.data.acknowledgement.note}`:''}</p><details><summary>查看当时依据</summary><Source source={event.data.trigger}/>{(event.data.recovery?.sources??event.data.latest_abnormal).map((source,index)=><Source key={index} source={source}/>)}</details></li>)}</ol>
    </>}
  </section>;
}

export function AlarmCenterPage(){
  const [search,setSearch]=useState(location.search);const query=new URLSearchParams(search);
  function update(patch:Record<string,string>){const url=link(query,patch);history.replaceState(null,'',url);setSearch(new URL(url,location.origin).search);}
  const params=new URLSearchParams([...query].filter(([key,value])=>filterKeys.includes(key)&&value));
  const id=query.get('alarm');
  return id?<Detail key={id} id={id} query={query}/>:<Listing query={query} params={params} update={update}/>;
}
function Listing({query,params,update}:{query:URLSearchParams;params:URLSearchParams;update:(patch:Record<string,string>)=>void}){
  const {data,error,retry}=useAlarms<AlarmList>('?'+params);
  const from=query.get('return_to')??'';
  const choices:Record<string,Record<string,string>>={scope:{current:'未解除',history:'历史（已解除 / 已并入）',all:'全部'},product_line:{PV:'光伏 PV',ESS:'储能 ESS'},test_type:typeNames,severity:{ATTENTION:'关注',WARNING:'警示',CRITICAL:'严重'},state:alarmStates};
  const names:Record<string,string>={scope:'报警范围',product_line:'产品线',site:'当前现场',customer:'当前客户',equipment:'设备序列号 / 资产编号',test_type:'检测类型',analyte:'结果项',severity:'严重程度',state:'处理状态',from_date:'产生日期起（Chicago）',to_date:'产生日期止（Chicago）'};
  return <section className="health-card" aria-label="报警中心内容">
    {/^\/assets(?:[/?]|$)/.test(from)&&<a href={from}>返回来源页面</a>}
    <div className="health-toolbar"><h2>设备报警</h2><button onClick={retry}>刷新报警列表</button></div>
    <p className="health-help">确认表示已知悉，不改变严重程度。解除需严格更晚采样、同方法版本和单位、已定稿且选入报告的完整正常结果。规则停用、设备更换或撤回异常报告不会直接解除。按当前安装位置筛选，采样时现场保留在来源中。</p>
    {query.get('asset_id')&&<p className="health-help">限定物理设备及其当前子设备：{query.get('asset_id')}</p>}
    <form className="health-form alarm-filters" key={params.toString()} onSubmit={e=>{e.preventDefault();update({...Object.fromEntries(new FormData(e.currentTarget)) as Record<string,string>,page:'1'});}}>
      {Object.entries(names).map(([key,name])=><label key={key}>{name}{choices[key]?<select name={key} defaultValue={query.get(key)??(key==='scope'?'current':'')}>{key!=='scope'&&<option value="">全部</option>}{Object.entries(choices[key]).map(([value,text])=><option key={value} value={value}>{text}</option>)}</select>:key==='analyte'?<select name={key} defaultValue={query.get(key)??''}><option value="">全部</option>{['H2','CH4','C2H2','C2H4','C2H6','CO','CO2','MOISTURE','BREAKDOWN_VOLTAGE'].map(value=><option key={value} value={value}>{typeNames[value]??value}</option>)}</select>:<input name={key} type={key.endsWith('_date')?'date':'text'} maxLength={160} defaultValue={query.get(key)??''}/>}</label>)}
      <div className="alarm-actions"><button>筛选报警</button><a href={path}>清除筛选</a></div>
    </form>
    {error?<p role="alert">{error}</p>:!data?<p role="status">正在读取报警…</p>:<>
      <p>共 {data.total} 条 · 未解除 {data.unresolved_count} 条</p>
      <div className="health-table-scroll"><table aria-label="报警列表"><thead><tr><th>设备 / 当前现场</th><th>检测 / 严重程度</th><th>状态</th><th>产生时间</th><th>操作</th></tr></thead><tbody>{data.items.map(alarm=><tr key={alarm.id}><td>{alarm.current_asset?.serial_number??alarm.asset_id}<p className="health-help">{alarm.current_asset?.system_asset_number}<br/>{alarm.current_asset?.site_name??'维修中心 / 无当前现场'}<br/>{alarm.current_asset?.customer_name??'不适用'}</p></td><td>{typeNames[alarm.test_type]} · {alarm.analyte}<p className={!alarm.superseded_by&&alarm.state!=='RESOLVED'?'health-abnormal':''}>{statusNames[alarm.severity]}</p></td><td>{alarmStatus(alarm)}</td><td>{time(alarm.opened_at)}</td><td><a href={link(query,{alarm:alarm.id})}>查看报警</a></td></tr>)}</tbody></table></div>
      {data.total===0&&<p role="status">暂无符合条件的报警。</p>}
      <div className="alarm-actions"><span>第 {data.page} 页</span><button disabled={data.page<=1} onClick={()=>update({page:String(data.page-1)})}>上一页报警</button><button disabled={data.page*data.page_size>=data.total} onClick={()=>update({page:String(data.page+1)})}>下一页报警</button></div>
      <p className="health-help">最近检查：{time(data.checked_at)}。页面打开时及每 30 秒刷新；不提供后台通知保证。</p>
    </>}
  </section>;
}
