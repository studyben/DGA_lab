import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAuth } from '../../Auth';
import { healthRequest, statusNames, type Rule, type Method } from './healthApi';
import './health.css';

const empty={name:'',method:'',analyte:'',asset:'',priority:'0',from:'',to:'',operator:'GT',threshold:'',severity:'WARNING'};
const local=(value:string|null)=>{if(!value)return '';const d=new Date(value);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,19);};
function instant(value:string,original:string|null|undefined){
  if(original&&value===local(original))return original;
  const date=new Date(value);
  if(!Number.isFinite(date.getTime())||local(date.toISOString()).slice(0,value.length)!==value)throw new Error('该本地时间不存在或无效，请检查夏令时切换。');
  return date.toISOString();
}
export function RulesPage(){
  const {can,session}=useAuth();
  const [rules,setRules]=useState<Rule[]>([]),[methods,setMethods]=useState<Method[]>([]);
  const [form,setForm]=useState(empty),[editing,setEditing]=useState<Rule|null>(null);
  const [filter,setFilter]=useState(''),[status,setStatus]=useState('');
  const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[ready,setReady]=useState(false);
  const [approval,setApproval]=useState<{rule:Rule;action:'activate'|'retire'}|null>(null),[reason,setReason]=useState('');
  const [audit,setAudit]=useState<{action:string;reason:string;occurred_at:string;actor_id:string}[]|null>(null);
  const inFlight=useRef(false);
  const field=(key:keyof typeof empty,value:string)=>setForm(f=>({...f,[key]:value}));
  const selected=methods.find(m=>m.id===form.method);
  async function reload(){
    const [r,m]=await Promise.all([healthRequest<Rule[]>('/rules',{signal:AbortSignal.timeout(15000)}),healthRequest<Method[]>('/rule-methods',{signal:AbortSignal.timeout(15000)})]);
    setRules(r);setMethods(m);setReady(true);
  }
  useEffect(()=>{let active=true;const controller=new AbortController();
    Promise.all([healthRequest<Rule[]>('/rules',{signal:controller.signal}),healthRequest<Method[]>('/rule-methods',{signal:controller.signal})]).then(([r,m])=>{if(active){setRules(r);setMethods(m);setReady(true);}}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;controller.abort();};
  },[]);
  async function run(task:()=>Promise<void>){
    if(inFlight.current)return;inFlight.current=true;setBusy(true);setError('');setMessage('');
    try{await task();}catch(e){setError(e instanceof Error?e.message:'操作失败，请重试。');}finally{inFlight.current=false;setBusy(false);}
  }
  function mutation<T>(path:string,body?:unknown,method='POST'){
    return healthRequest<T>(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':session?.csrf_token??''},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
  }
  function edit(rule:Rule){setEditing(rule);setForm({name:rule.name,method:rule.method_version_id,analyte:rule.analyte,asset:rule.asset_id??'',priority:String(rule.priority),from:local(rule.effective_from),to:local(rule.effective_to),operator:rule.operator,threshold:rule.threshold,severity:rule.severity});setMessage('草稿已载入下方表单。');}
  function save(e:FormEvent){e.preventDefault();void run(async()=>{
    const unit=selected?.fields.find(f=>f.code===form.analyte)?.unit_code;
    if(!selected||!unit)throw new Error('请选择已配置单位的检测方法与结果项。');
    const from=instant(form.from,editing?.effective_from),to=form.to?instant(form.to,editing?.effective_to):null;
    if(to&&new Date(to)<=new Date(from))throw new Error('截止时间必须晚于生效时间。');
    const payload={name:form.name,test_type:selected.test_type,analyte:form.analyte,method_version_id:selected.id,unit,asset_id:form.asset.trim()||null,priority:Number(form.priority),effective_from:from,effective_to:to,operator:form.operator,threshold:form.threshold,severity:form.severity};
    await mutation(editing?'/rules/'+editing.id:'/rules',editing?{rule:payload,expected_revision:editing.revision}:payload,editing?'PUT':'POST');
    setForm(empty);setEditing(null);setMessage('草稿已保存，批准启用后才参与评估。');await reload();
  });}
  return <div>
    <section className="health-card"><h2>健康规则的作用</h2><p className="health-help">规则把指定方法版本下的检测数值，与经批准的阈值进行比较。规则只适用于相同检测类型、结果项、方法版本和单位，不自动判断 ASTM 方法兼容性，也不预设正式阈值。</p><p className="health-help">先保存草稿，再填写原因批准启用。已启用规则不能修改或删除；需要调整时复制为新草稿。每次按当前生效规则评估最新已定稿采样结果；优先级数字越大越优先，仅采用最高优先级规则，不叠加低优先级阈值。ND / LT / GT 等限定结果不作精确数值判断。</p>
      <button disabled={busy} onClick={()=>void run(reload)}>重新加载规则</button>
      {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    </section>
    <section className="health-card"><h2>规则列表</h2><div className="health-form"><label>规则关键词<input value={filter} onChange={e=>setFilter(e.target.value)}/></label><label>规则状态筛选<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">全部</option>{['DRAFT','ACTIVE','RETIRED'].map(s=><option key={s} value={s}>{statusNames[s]}</option>)}</select></label></div>
      {!ready?<p role="status">正在加载规则…</p>:<div className="health-table-scroll"><table aria-label="健康规则列表"><thead><tr><th>名称 / 结果项</th><th>范围与阈值</th><th>状态</th><th>操作</th></tr></thead><tbody>{rules.filter(r=>(!status||r.state===status)&&[r.name,r.analyte,r.unit].join(' ').toLowerCase().includes(filter.toLowerCase())).map(r=><tr key={r.id}><td>{r.name}<p className="health-help">{r.analyte} · {methods.find(m=>m.id===r.method_version_id)?.version_label??r.method_version_id}</p></td><td>{r.operator} {r.threshold} {r.unit}<p className="health-help">{r.asset_id??'所有变压器'} · 优先级 {r.priority}<br/>{new Date(r.effective_from).toLocaleString('zh-CN')} 至 {r.effective_to?new Date(r.effective_to).toLocaleString('zh-CN'):'不限'}</p></td><td>{statusNames[r.state]}<p className="health-help">{statusNames[r.severity]}</p></td><td>
        {can('analysis.write')&&<>{r.state==='DRAFT'&&<><button disabled={busy} onClick={()=>edit(r)}>编辑草稿</button><button disabled={busy} onClick={()=>{setApproval({rule:r,action:'activate'});setReason('');}}>批准启用</button></>}{r.state==='ACTIVE'&&<button disabled={busy} onClick={()=>{setApproval({rule:r,action:'retire'});setReason('');}}>停用</button>}<button disabled={busy} onClick={()=>void run(async()=>{const copy=await mutation<Rule>('/rules/'+r.id+'/copy');await reload();edit(copy);})}>复制为草稿</button></>}
        <button disabled={busy} onClick={()=>void run(async()=>setAudit(await healthRequest('/rules/'+r.id+'/history',{signal:AbortSignal.timeout(15000)})))}>变更记录</button>
      </td></tr>)}</tbody></table>{rules.length===0&&<p>暂无规则。没有已批准规则时设备显示未评估。</p>}</div>}
      {audit&&<div><h3>规则变更记录</h3>{audit.map((a,i)=><p className="health-help" key={i}>{new Date(a.occurred_at).toLocaleString('zh-CN')} · {a.action} · {a.reason} · 操作人 {a.actor_id}</p>)}<button onClick={()=>setAudit(null)}>收起记录</button></div>}
    </section>
    {approval&&<section className="health-card" aria-label="规则审批"><h2>{approval.action==='activate'?'批准启用':'停用'}：{approval.rule.name}</h2><p className="health-help">请确认规则内容与适用范围。审批身份、时间及原因会被保留。</p><label>审批或停用原因<textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000}/></label><button disabled={busy||!reason.trim()} onClick={()=>void run(async()=>{await mutation('/rules/'+approval.rule.id+'/'+approval.action,{expected_revision:approval.rule.revision,reason});setApproval(null);setMessage('规则状态已更新。');await reload();})}>{approval.action==='activate'?'确认批准启用':'确认停用'}</button><button onClick={()=>setApproval(null)} disabled={busy}>取消审批</button></section>}
    {can('analysis.write')&&<section className="health-card"><h2>{editing?'编辑规则草稿':'新增规则草稿'}</h2><p className="health-help">单位由所选方法配置决定。{can('laboratory.configure')?<a href="/lab/configuration">前往实验室配置添加方法</a>:'缺少方法时请联系实验室管理员。'} 所有时间使用本机时区（{Intl.DateTimeFormat().resolvedOptions().timeZone}），保存时转换为统一时间；夏令时重复小时采用本机默认的首次时刻，未修改的原时间保持不变。</p><form onSubmit={save}><fieldset className="health-form" disabled={busy}>
      <label>规则名称<input required maxLength={160} value={form.name} onChange={e=>field('name',e.target.value)}/></label>
      <label>适用方法版本<select aria-label="适用方法版本" required value={form.method} onChange={e=>{const m=methods.find(m=>m.id===e.target.value);setForm(f=>({...f,method:e.target.value,analyte:m?.fields.find(f=>f.unit_code)?.code??''}));}}><option value="">请选择已配置方法</option>{methods.filter(m=>m.configured&&m.fields.some(f=>f.unit_code)).map(m=><option key={m.id} value={m.id}>{m.name} · {m.version_label}{m.is_active?'':'（已停用，历史适用）'}</option>)}</select></label>
      <label>结果项<select required value={form.analyte} onChange={e=>field('analyte',e.target.value)}><option value="">请选择结果项</option>{selected?.fields.filter(f=>f.unit_code).map(f=><option key={f.code} value={f.code}>{f.code} · {f.unit_code}</option>)}</select></label>
      <label>限定变压器资产 ID（留空为全部）<input value={form.asset} onChange={e=>field('asset',e.target.value)} pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"/></label>
      <label>比较方式<select value={form.operator} onChange={e=>field('operator',e.target.value)}>{[['GT','大于'],['GE','大于等于'],['LT','小于'],['LE','小于等于']].map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      <label>比较阈值<input type="number" required min="0" step="0.000001" value={form.threshold} onChange={e=>field('threshold',e.target.value)}/></label>
      <label>严重程度<select value={form.severity} onChange={e=>field('severity',e.target.value)}>{['ATTENTION','WARNING','CRITICAL'].map(s=><option key={s} value={s}>{statusNames[s]}</option>)}</select></label>
      <label>优先级<input type="number" required min="0" max="1000" step="1" value={form.priority} onChange={e=>field('priority',e.target.value)}/></label>
      <label>生效时间<input type="datetime-local" step="1" required value={form.from} onChange={e=>field('from',e.target.value)}/></label><label>截止时间（不含，选填）<input type="datetime-local" step="1" value={form.to} onChange={e=>field('to',e.target.value)}/></label>
      <button disabled={busy||!ready}>保存草稿</button><button type="button" disabled={busy} onClick={()=>{setForm(empty);setEditing(null);}}>清空表单</button>
    </fieldset></form></section>}
  </div>;
}
