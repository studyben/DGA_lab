import { useEffect, useState } from 'react';
import { useAuth } from '../../Auth';
import { healthRequest, statusNames, reasons, type Rule } from './healthApi';
import './health.css';

type State={status:string;incomplete:boolean};
type Source={asset_id:string;status:string;reason:string|null;latest_time_tied?:boolean;rule:Rule|null;
  measurement:null|{barcode:string;sampled_at:string;measured_at:string;test_type:string;analyte:string;
    method_version_id:string;method_name:string;version_label:string;unit:string|null;qualifier:string;value:string|null;test_id:string;sample_id:string}};
type Assessment=State&{subject_id:string;own:State;descendants:State;checked_at:string;evaluated_at:string;evaluation_id:string;
  sources:Source[];assets:{id:string;serial_number:string;system_asset_number:string}[]};
const time=(value:string)=>new Date(value).toLocaleString('zh-CN');

export function HealthPanel({assetId}:{assetId:string}){
  const {can}=useAuth();
  const [attempt,setAttempt]=useState(0);
  const [state,setState]=useState<{assetId:string;data?:Assessment;error?:string}>({assetId:''});
  useEffect(()=>{
    let active=true; let timer:number|undefined;
    const controller=new AbortController();
    setState({assetId});
    async function load(){
      try{
        const data=await healthRequest<Assessment>('/health/'+encodeURIComponent(assetId),{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
        if(active)setState({assetId,data});
      }catch(error){if(active)setState({assetId,error:error instanceof Error?error.message:'读取失败'});}
      finally{if(active)timer=window.setTimeout(()=>void load(),30000);}
    }
    void load();
    return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[assetId,attempt]);
  const data=state.assetId===assetId?state.data:undefined;
  return <section className="health-panel" aria-label="设备健康评估">
    <div className="health-toolbar"><h3>健康状态</h3><button onClick={()=>setAttempt(n=>n+1)}>刷新健康状态</button></div>
    {state.error?<p role="alert">{state.error}</p>:!data?<p role="status">正在评估…</p>:<>
      <p className={'health-status '+(['ATTENTION','WARNING','CRITICAL'].includes(data.status)?'health-abnormal':'')}>{['ATTENTION','WARNING','CRITICAL'].includes(data.status)?'⚠ ':''}{statusNames[data.status]}</p>
      <p className="health-help">自身：{statusNames[data.own.status]} · 子设备汇总：{statusNames[data.descendants.status]}。{data.incomplete?'存在未评估项，覆盖不完整。':'仅反映已评估的油样项目，不代表整机健康认证。'}</p>
      <p className="health-help">最近检查：{time(data.checked_at)} · 证据形成：{time(data.evaluated_at)}</p>
      <details><summary>查看评估来源</summary>
        {data.sources.length===0&&<p>没有可评估的变压器检测结果。</p>}
        {data.sources.map((s,i)=>{const m=s.measurement;const asset=data.assets.find(a=>a.id===s.asset_id);return <article className="health-source" key={i}>
          <strong>{asset?.serial_number??s.asset_id} · {statusNames[s.status]}</strong>
          {s.reason&&<p>{reasons[s.reason]??s.reason}</p>}
          {s.latest_time_tied&&<p className="health-help">最新采样时间并列，保留所有结果并取已知最高严重程度。</p>}
          {m&&<><p>{m.barcode} · {m.analyte}：{m.qualifier==='EQ'?'':m.qualifier+' '}{m.value??'—'} {m.unit??'单位待配置'}</p>
            <p className="health-help">采样：{time(m.sampled_at)} · 检测：{time(m.measured_at)}<br/>方法：{m.method_name} · {m.version_label}</p>
            {can('laboratory.read')&&<div className="health-toolbar"><a href={'/lab/workbench?barcode='+encodeURIComponent(m.barcode)}>检测记录</a><a href={'/lab/reports?barcode='+encodeURIComponent(m.barcode)}>条码报告</a></div>}
          </>}
          {s.rule&&<p className="health-help">规则：{s.rule.name} · {s.rule.operator} {s.rule.threshold} {s.rule.unit} · 优先级 {s.rule.priority}<br/>规则版本：{s.rule.id}</p>}
        </article>;})}
        <p className="health-help">评估证据：{data.evaluation_id}</p>
      </details>
    </>}
  </section>;
}

export function HealthOverview(){
  return <section className="health-card"><h2>从设备查看健康状态</h2><p>请从现场进入设备详情，查看设备自身及当前子设备的健康评估与检测来源。</p><a href="/assets">选择现场与设备</a><p className="health-help">更换或移出的变压器保留自身检测历史，不再影响原父设备。没有适用规则时显示未评估。</p><a href="/assets/analysis/rules">管理健康规则</a></section>;
}
