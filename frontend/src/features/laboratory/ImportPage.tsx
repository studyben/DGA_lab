import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {useAuth} from '../../Auth';
import {ImportError,importRoot,readImport,sendImport,uploadOriginal} from './importApi';
import {fileMetadata,forgetIntent,loadIntent,prepareIntent,retainIntent,sameOriginal,type ImportIntent} from './importIntent';
import type {Batch,CreateInput,FileRole,InputFormat,Operation,OriginalFile,Page,Purpose,Revision,SourceDecision,SourcePage,TemporalEvidence,StagedRow,StagedIssue,SamplesPage,SampleDetail,UnassignedPage,IssuesPage} from './importTypes';
import './imports.css';

const labels:Record<FileRole,string>={WORKBOOK:'工作簿',SAMPLES:'油样信息 CSV',TESTS:'检测结果 CSV'};
const receiptState={PENDING:'尚未确认保存',RETRYABLE:'存储未确认，可由原上传者恢复',RECEIVED:'原件已确认保存'};
const purposeLabel={HISTORICAL:'历史资料',DAILY:'日常检测资料'};
function text(error:unknown){return error instanceof Error?error.message:'请求未完成，请重试。';}
function time(value:string){return new Date(value).toLocaleString();}
function queryString(value:Record<string,string|number>){const q=new URLSearchParams();Object.entries(value).forEach(([k,v])=>{if(v!=='')q.set(k,String(v));});return q.toString();}


function validateMetadata(zone:string,confirmed:boolean){
  if([...zone].length>100)throw new Error('来源时区最多 100 字符，请保留原值后核对。');
  if(confirmed&&!zone)throw new Error('确认来源时区前，请明确填写 IANA 来源时区。');
  if(zone){try{new Intl.DateTimeFormat('en',{timeZone:zone}).format(0);}
    catch{throw new Error('来源时区无效，请填写明确的 IANA 名称（例如 America/Chicago），或保持空白。');}}
}
function validateSources(values:SourceDecision[]){
  if(values.length>500)throw new Error('一次最多确认 500 项来源身份，请拆分批次。');
  for(const value of values){
    if(!value.reason.trim()||[...value.reason].length>1000||value.reason.includes('\u0000'))
      throw new Error('来源身份确认原因须为 1–1000 字符，且不能包含 NUL。');
    if(value.decision==='NEW'&&(!value.proposed_name.trim()||[...value.proposed_name].length>200||/[\u0000-\u001f]/.test(value.proposed_name)))
      throw new Error('来源实验室名称须为 1–200 字符，且不能包含控制字符。');
  }
}

function SourceChoices({onAdd,disabled}:{onAdd:(value:SourceDecision)=>void;disabled:boolean}){
  const [alias,setAlias]=useState(''),[decision,setDecision]=useState<'NEW'|'REFERENCE'>('REFERENCE');
  const [name,setName]=useState(''),[kind,setKind]=useState<'IN_HOUSE'|'THIRD_PARTY'>('THIRD_PARTY');
  const [reason,setReason]=useState(''),[ack,setAck]=useState(false),[reference,setReference]=useState('');
  const [candidates,setCandidates]=useState<SourcePage|null>(null),[candidateName,setCandidateName]=useState('');
  const [page,setPage]=useState(1),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const request=useRef(0);
  async function search(next=1){
    const id=++request.current;setBusy(true);setError('');setAck(false);setReference('');
    try{const result=await readImport<SourcePage>('/sources?'+queryString({query:decision==='REFERENCE'?name:'',...(decision==='NEW'?{exact_name:name}:{}),page:next}));
      if(id===request.current){setCandidates(result);setCandidateName(name);setPage(next);}
    }catch(e){if(id===request.current)setError(text(e));}finally{if(id===request.current)setBusy(false);}
  }
  function add(){
    setError('');
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(alias)||!reason.trim()||[...reason].length>1000||reason.includes('\u0000')){
      setError('来源键须以英文字母开头、最多 80 字符；请填写不超过 1000 字符的确认原因。');return;
    }
    if(decision==='NEW'){
      if(!name.trim()||[...name].length>200||/[\u0000-\u001f]/.test(name)||candidateName!==name||!candidates?.candidate_digest||!ack){
        setError('请查询当前同名候选，并明确确认这是独立来源身份。');return;
      }
      onAdd({key:alias,decision,proposed_name:name,source_kind:kind,reason,confirm_distinct:true,candidate_digest:candidates.candidate_digest});
    }else{
      if(!reference){setError('请明确选择一个来源实验室稳定 ID。');return;}
      onAdd({key:alias,decision,source_lab_id:reference,reason});
    }
    setAlias('');setReason('');setAck(false);setReference('');setCandidates(null);
  }
  return <fieldset disabled={disabled||busy} className="lab-import-source"><legend>确认来源实验室（可稍后补充）</legend>
    <p>文件内的来源键与稳定身份单独确认。同名只用于查找，不会自动合并。</p>
    <div className="lab-import-grid">
      <label>文件内来源键<input value={alias} onChange={e=>setAlias(e.target.value)} placeholder="例如 LAB_A"/></label>
      <label>身份决定<select aria-label="身份决定" value={decision} onChange={e=>{request.current++;setDecision(e.target.value as 'NEW'|'REFERENCE');setCandidates(null);setReference('');setAck(false);}}><option value="REFERENCE">引用已有稳定身份</option><option value="NEW">确认新的独立身份</option></select></label>
      <label>来源实验室名称<input value={name} onChange={e=>{request.current++;setName(e.target.value);setCandidates(null);setAck(false);setReference('');}}/></label>
      {decision==='NEW'&&<label>来源性质<select aria-label="来源性质" value={kind} onChange={e=>setKind(e.target.value as typeof kind)}><option value="THIRD_PARTY">第三方</option><option value="IN_HOUSE">内部实验室</option></select></label>}
    </div>
    <button type="button" onClick={()=>void search()} disabled={decision==='NEW'&&!name.trim()}>查询来源候选</button>
    {candidates&&<div className="lab-import-candidates" aria-label="来源实验室候选">
      <p>{decision==='NEW'?'当前同名候选':'查找结果'}：{candidates.exact_name_total??candidates.total} 项。稳定 ID 与显示名称分别列示。</p>
      {candidates.items.map(s=><label className="lab-import-choice" key={s.id}>{decision==='REFERENCE'&&<input type="radio" name="reference-source" checked={reference===s.id} onChange={()=>setReference(s.id)}/>}<span>{s.display_name} · {s.source_kind==='IN_HOUSE'?'内部':'第三方'}<code>{s.id}</code></span></label>)}
      <div className="lab-import-pager"><button type="button" disabled={page===1} onClick={()=>void search(page-1)}>上一页候选</button><span>第 {page} 页</span><button type="button" disabled={page*20>=candidates.total} onClick={()=>void search(page+1)}>下一页候选</button></div>
      {decision==='NEW'&&<label className="lab-import-choice"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>已核对全部同名候选数量，确认这是新的独立来源身份</label>}
    </div>}
    <label>来源身份确认原因<textarea aria-label="来源身份确认原因" value={reason} onChange={e=>setReason(e.target.value)} rows={2}/><small>{[...reason].length}/1000 字符</small></label>
    {error&&<p role="alert">{error}</p>}
    <button type="button" onClick={add}>加入本次来源确认</button>
  </fieldset>;
}
function DecisionList({values,onRemove,disabled}:{values:SourceDecision[];onRemove:(index:number)=>void;disabled:boolean}){
  return values.length>0?<ul className="lab-import-decisions">{values.map((s,i)=><li key={s.key}>{s.key} → {s.decision==='NEW'?'新身份：'+s.proposed_name:'引用：'+s.source_lab_id}<span>原因：{s.reason}</span><button type="button" disabled={disabled} onClick={()=>onRemove(i)}>移除本次选择 {s.key}</button></li>)}</ul>:null;
}
function Pager({page,total,label,onPage,pageSize=20}:{page:number;total:number;label:string;onPage:(n:number)=>void;pageSize?:number}){
  return <div className="lab-import-pager" aria-label={label+'分页'}><button type="button" disabled={page===1} onClick={()=>onPage(page-1)}>上一页{label}</button><span>第 {page} 页 · 共 {total} 项</span><button type="button" disabled={page*pageSize>=total} onClick={()=>onPage(page+1)}>下一页{label}</button></div>;
}


function RowRevision({before,after}:{before:unknown;after:unknown}){
  const old=before&&typeof before==='object'?before as Record<string,unknown>:{};
  const current=after&&typeof after==='object'?after as Record<string,unknown>:{};
  return <table aria-label="行字段修订前后"><thead><tr><th>字段</th><th>核对前</th><th>核对后</th></tr></thead><tbody>{Array.from(new Set([...Object.keys(old),...Object.keys(current)])).map(key=><tr key={key}><th>{key}</th><td><pre>{evidenceText(old[key])}</pre></td><td><pre>{evidenceText(current[key])}</pre></td></tr>)}</tbody></table>;
}

function RevisionSnapshot({value}:{value:unknown}){
  if(!value||typeof value!=='object')return <p>未提供。</p>;
  const v=value as {purpose?:Purpose;source_timezone?:string|null;source_timezone_confirmed?:boolean;
    active_files?:{id:string;role:FileRole;filename:string;sha256:string}[];
    source_labs?:{source_lab_key:string;source_lab_id:string}[]};
  return <div className="lab-import-revision-snapshot">
    <p>用途：{v.purpose?purposeLabel[v.purpose]:'未提供'}；来源时区：{v.source_timezone??'未提供'}（{v.source_timezone_confirmed?'已核实':'未核实'}）</p>
    <p>采用的原件：{v.active_files?.length??0} 份</p>
    {v.active_files?.map(f=><p key={f.id}>{labels[f.role]}：{f.filename}<code>{f.id}</code><small>SHA256 {f.sha256}</small></p>)}
    <p>来源绑定：{v.source_labs?.length??0} 项</p>
    {v.source_labs?.map(s=><p key={s.source_lab_key}>{s.source_lab_key}<code>{s.source_lab_id}</code></p>)}
  </div>;
}


const previewKeys=['sample_page','test_page','unassigned_page','issue_page','sample','row','field','view','sample_severity','issue_severity','issue_code','issue_sheet','issue_row'] as const;
type PreviewContext={sample_page:number;test_page:number;unassigned_page:number;issue_page:number;sample:string;row:string;field:string;view:string;sample_severity:string;issue_severity:string;issue_code:string;issue_sheet:string;issue_row:string};
function previewContext():PreviewContext{
  const q=new URLSearchParams(location.search);
  const page=(key:string)=>{const n=Number(q.get(key)??1);return Number.isInteger(n)&&n>=1&&n<=100000?n:1;};
  return {sample_page:page('sample_page'),test_page:page('test_page'),unassigned_page:page('unassigned_page'),issue_page:page('issue_page'),
    sample:q.get('sample')??'',row:q.get('row')??'',field:q.get('field')??'',view:q.get('view')==='unassigned'?'unassigned':'samples',
    sample_severity:q.get('sample_severity')??'',issue_severity:q.get('issue_severity')??'',issue_code:q.get('issue_code')??'',issue_sheet:q.get('issue_sheet')??'',issue_row:q.get('issue_row')??''};
}
function evidenceText(value:unknown):string{
  if(value==='')return '空白';
  if(value===null||value===undefined)return '未提供';
  return typeof value==='object'?JSON.stringify(value,null,2):String(value);
}
function validationLabel(batch:Batch){
  if(batch.validation_state==='QUEUED')return '校验已排队';
  if(batch.validation_state==='RUNNING')return '正在校验';
  if(batch.validation_state==='FAILED')return '校验未完成，可重新校验';
  if(batch.validation_state==='COMPLETE'&&batch.validation_current===true)return (batch.summary?.error_count??1)>0?'待核对':'已校验（仅暂存）';
  return batch.stale?'上次结果已过期，待重新校验':'尚未校验';
}
function revisionSignature(batch:Batch){
  return JSON.stringify([batch.id,batch.revision,batch.current_job?.id,batch.validation_state,batch.validation_current,batch.summary?.last_job_id]);
}
function TemporalValues({values}:{values:Record<string,TemporalEvidence>}){
  return <div className="lab-import-temporal">{Object.entries(values).map(([field,v])=><section key={field}><h5>{field}</h5><dl>
    <dt>原始时间</dt><dd>{evidenceText(v.raw)}</dd><dt>精度</dt><dd>{v.precision==='DATE'?'日期（未补造时刻）':v.precision==='INSTANT'?'已确定时点':v.precision==='MISSING'?'未提供':'尚未确定时点'}</dd>
    <dt>业务日期</dt><dd>{evidenceText(v.business_date)}</dd><dt>来源本地时间</dt><dd>{evidenceText(v.local_time)}</dd><dt>来源时区</dt><dd>{evidenceText(v.source_timezone)}</dd>
    <dt>明确偏移</dt><dd>{evidenceText(v.explicit_offset)}</dd><dt>UTC 时点</dt><dd>{evidenceText(v.utc_instant)}</dd></dl>{v.issue_codes.length>0&&<p>时间问题：{v.issue_codes.join('、')}</p>}</section>)}</div>;
}
function RowEvidence({row,title,onReview,disabled}:{row:StagedRow;title:string;onReview?:(row:StagedRow)=>void;disabled?:boolean}){
  const p=row.parsed_values;
  const ordinary=Object.entries(p).filter(([key])=>!['temporal','measurements','reports','asset','source_evidence'].includes(key));
  return <section aria-label={title} className="lab-import-row-evidence"><h4 id={'evidence-'+row.id} tabIndex={-1}>{row.sheet} 第{row.row_number}行 · {row.external_test_id??row.external_sample_id??'身份未提供'}</h4>
    {onReview&&<button type="button" disabled={disabled} onClick={()=>onReview(row)}>{row.sheet==='油样信息'?'核对油样 ':'核对检测 '}{row.external_test_id??row.external_sample_id??'第'+row.row_number+'行'}</button>}
    {row.stale&&<p className="lab-import-stale">旧版证据，不能作为当前校验结论。</p>}
    <p>来源原件 ID：<code>{row.file_id}</code>来源实验室稳定 ID：<code>{row.source_lab_id??'未确认'}</code></p>
    <table aria-label={row.sheet+'原始与核对值'}><thead><tr><th>字段</th><th>原始值（保留）</th><th>核对值（只读）</th><th>原始类型</th></tr></thead><tbody>{Object.keys(row.raw_values).map(key=><tr key={key}>
      <th>{key}</th><td id={'evidence-'+row.id+'-'+key} tabIndex={-1} aria-label={key+' 原始值'}><pre>{evidenceText(row.raw_values[key])}</pre></td><td aria-label={key+' 核对值'}><pre>{evidenceText(row.reviewed_values[key])}</pre></td><td>{row.raw_cell_types[key]}</td></tr>)}</tbody></table>
    <h4>解析证据（只读）</h4>{p.temporal&&<TemporalValues values={p.temporal}/>}
    {p.measurements&&<table aria-label="解析测量与限定符"><thead><tr><th>项目</th><th>原始数值</th><th>限定符</th><th>解析十进制文本</th><th>来源单位</th><th>来源小数位数</th></tr></thead><tbody>{Object.entries(p.measurements).map(([key,m])=><tr key={key}>
      <th>{key}</th><td>{evidenceText(m.raw_value)}</td><td>{evidenceText(m.qualifier)}</td><td>{m.qualifier==='ND'&&m.value===null?'无数值（ND）':evidenceText(m.value)}</td><td>{evidenceText(m.unit)}</td><td>{evidenceText(m.source_precision)}</td></tr>)}</tbody></table>}
    {p.source_evidence&&<div><h5>原检测来源证据</h5><dl>{Object.entries(p.source_evidence).map(([key,v])=><div key={key}><dt>{key}</dt><dd><pre>{evidenceText(v)}</pre></dd></div>)}</dl><p>这些人员和 QA 文本属于来源证据；保存与核对者见批次修订历史。</p></div>}
    {p.reports&&<div><h5>第三方报告声明</h5>{p.reports.length?p.reports.map(r=><p key={r.filename}>{r.filename} · 已声明，未提供文件</p>):<p>未声明</p>}</div>}
    {'asset' in p&&<div><h5>正式资产与历史上下文核对</h5><pre>{evidenceText(p.asset)}</pre></div>}
    <dl className="lab-import-parsed">{ordinary.map(([key,v])=><div key={key}><dt>{key==='notes'?'业务备注 notes':key==='source_note'?'来源备注 source_note':key}</dt><dd><pre>{evidenceText(v)}</pre></dd></div>)}</dl>
    {row.issues.length>0&&<div><h5>本行问题</h5><ul>{row.issues.map(i=><li key={i.id}>{i.severity} · {i.code} · {i.field??'整行'}：{i.message}</li>)}</ul></div>}
  </section>;
}
function TestRows({rows,selected,onSelect,label}:{rows:StagedRow[];selected:string;onSelect:(row:StagedRow)=>void;label:string}){
  return <table aria-label={label}><thead><tr><th>完整检测 ID</th><th>来源行</th><th>检测类型</th><th>采用状态</th><th>问题</th><th>证据</th></tr></thead><tbody>{rows.map(r=><tr key={r.id} className={r.id===selected?'lab-import-selected':''}>
    <td>{r.external_test_id??'未提供'}<small>样品 {r.external_sample_id??'未提供'}</small></td><td>{r.sheet} 第{r.row_number}行</td><td>{evidenceText(r.parsed_values.test_type)}</td><td>{evidenceText(r.parsed_values.report_selection)}</td>
    <td>错误 {r.issue_counts.ERROR} / 警告 {r.issue_counts.WARNING}</td><td><button type="button" onClick={()=>onSelect(r)}>查看检测 {r.external_test_id??'第'+r.row_number+'行'}</button></td></tr>)}</tbody></table>;
}

type ReviewScalar=string|boolean|number|null;
type RowDraft={batch_id:string;row_id:string;sheet?:string;row_number?:number;expected_revision:number;reason:string;baseline:Record<string,unknown>;values:Record<string,ReviewScalar>;touched:string[]};
const reviewLimits:Record<string,number>={source_lab_key:80,external_sample_id:160,external_test_id:160,source_lab_name:200,source_site_name:200,source_whole_unit_serial:160,source_transformer_serial:160,system_asset_number:80,sampled_at:80,measured_at:80,received_at:80,sampled_timezone:100,measured_timezone:100,received_timezone:100,source_method:160,source_method_version:80,source_instrument:160,source_analyst:150,source_qa:2000,notes:2000,source_note:2000,report_filenames:32767};
function reviewLimit(field:string){return reviewLimits[field]??(field.endsWith('_value')?128:field.endsWith('_unit')?40:32767);}
function changedValues(draft:RowDraft){
  return Object.fromEntries(draft.touched.filter(key=>!Object.is(draft.values[key],draft.baseline[key])).map(key=>[key,draft.values[key]]));
}
function rowReviewErrors(draft:RowDraft){
  const errors:string[]=[];
  if(!draft.reason.trim()||[...draft.reason].length>1000||draft.reason.includes('\u0000'))errors.push('本行核对原因须为 1–1000 字符且不含 NUL。');
  for(const [field,value] of Object.entries(changedValues(draft))){
    if(typeof value==='string'&&[...value].length>reviewLimit(field))errors.push(field+' 超过 '+reviewLimit(field)+' 字符；原输入仍保留。');
    if(typeof value==='string'&&/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value))errors.push(field+' 包含不允许的控制字符。');
    if(typeof value==='number'&&!Number.isInteger(value))errors.push(field+' 的数值须使用文本表达。');
    if(field.endsWith('_value')&&typeof value!=='string')errors.push(field+' 须使用十进制文本；不从浮点数猜测精度。');
  }
  return errors;
}
function draftFromRow(row:StagedRow,revision:number):RowDraft{
  const values:Record<string,ReviewScalar>={};
  for(const [key,value] of Object.entries(row.reviewed_values))values[key]=value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isInteger(value)?value:evidenceText(value);
  return {batch_id:row.batch_id,row_id:row.id,sheet:row.sheet,row_number:row.row_number,expected_revision:revision,reason:'',baseline:{...row.reviewed_values},values,touched:[]};
}
function draftFromIntent(value:ImportIntent,revision?:number):RowDraft|null{
  if(value.action!=='REVISE'||!value.payload.changes?.length)return null;
  const change=value.payload.changes[0];
  return {batch_id:value.batch_id,row_id:change.row_id,expected_revision:revision??value.payload.expected_revision,reason:value.payload.reason,baseline:{},values:{...change.values},touched:Object.keys(change.values)};
}
function RowEditor({draft,disabled,onChange,onSave,onClose}:{draft:RowDraft;disabled:boolean;onChange:(value:RowDraft)=>void;onSave:()=>void;onClose:()=>void}){
  const errors=rowReviewErrors(draft),changed=changedValues(draft);
  function update(field:string,value:string){onChange({...draft,values:{...draft.values,[field]:value},touched:draft.touched.includes(field)?draft.touched:[...draft.touched,field]});}
  function options(field:string):string[]|null{
    if(field.endsWith('_qualifier'))return ['','EQ','ND','LT','GT'];
    if(['physical_received','report_selected'].includes(field))return ['','TRUE','FALSE'];
    if(field==='test_type')return ['','DGA','MOISTURE','BREAKDOWN_VOLTAGE'];
    if(field==='sampling_context')return ['','SITE','REPAIR_CENTER','OTHER'];
    return null;
  }
  return <section className="lab-import-editor" aria-label="本行核对"><h3 id="lab-import-row-editor-heading" tabIndex={-1}>{draft.sheet?'核对 '+draft.sheet+' 第'+draft.row_number+'行':'恢复的原请求行'}</h3>
    <p>行 ID：<code>{draft.row_id}</code>本请求基于版本 {draft.expected_revision}。仅明确改动的字段会保存；原始值和原件保持保留，保存后须显式重新校验。</p>
    {!draft.sheet&&<p>这里保留原请求中提交的字段与原因；未知结果不会用最新资料重建。需要其他字段时，可在明确拒绝并准备新请求后重新打开完整行。</p>}
    <fieldset disabled={disabled}><legend>本行核对值</legend><div className="lab-import-editor-fields">{Object.entries(draft.values).map(([field,value])=>{
      const valueText=value===null?'':String(value),choices=options(field),max=reviewLimit(field),count=[...valueText].length;
      const multiline=['notes','source_note','source_qa','report_filenames'].includes(field);
      return <label key={field}>{field==='notes'?'业务备注 notes':field==='source_note'?'来源备注 source_note':field}
        {choices?<select id={'review-'+draft.row_id+'-'+field} aria-label={'核对 '+field} value={valueText} onChange={e=>update(field,e.target.value)}>
          {!choices.includes(valueText)&&<option value={valueText}>{valueText}（保留原值）</option>}{choices.map(choice=><option key={choice} value={choice}>{choice||'空白（未提供）'}</option>)}</select>
        :multiline?<textarea id={'review-'+draft.row_id+'-'+field} aria-label={'核对 '+field} value={valueText} onChange={e=>update(field,e.target.value)} rows={3}/>
        :<input id={'review-'+draft.row_id+'-'+field} aria-label={'核对 '+field} value={valueText} onChange={e=>update(field,e.target.value)}/>}
        <small className={count>max?'lab-import-overlimit':''}>{count}/{max} 字符</small>
      </label>;
    })}</div><label>本行核对原因<textarea aria-label="本行核对原因" value={draft.reason} onChange={e=>onChange({...draft,reason:e.target.value})} rows={2}/><small>{[...draft.reason].length}/1000 字符</small></label></fieldset>
    {errors.length>0&&<ul className="lab-import-review-errors">{errors.map(error=><li key={error}>{error}</li>)}</ul>}
    <button type="button" disabled={disabled||errors.length>0||Object.keys(changed).length===0} onClick={onSave}>保存本行核对</button>
    <button type="button" disabled={disabled} onClick={onClose}>关闭本行核对</button>
  </section>;
}

function ImportPreview({batch,onBatch,locked,onValidate,onReview}:{batch:Batch;onBatch:(value:Batch,expectedSignature?:string)=>void;locked:boolean;onValidate:()=>void;onReview:(row:StagedRow)=>void}){
  const [ctx,setCtx]=useState<PreviewContext>(previewContext),[sampleRows,setSampleRows]=useState<SamplesPage|null>(null);
  const [detail,setDetail]=useState<SampleDetail|null>(null),[orphans,setOrphans]=useState<UnassignedPage|null>(null),[issues,setIssues]=useState<IssuesPage|null>(null);
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[pollError,setPollError]=useState(''),[retry,setRetry]=useState(0),[pollRetry,setPollRetry]=useState(0);
  const request=useRef(0),previewRoot=useRef<HTMLDivElement>(null),contextBatch=useRef(batch.id),focusedLocator=useRef(''),signature=revisionSignature(batch);
  const update=useCallback((patch:Partial<PreviewContext>)=>{
    if('row' in patch||'field' in patch)focusedLocator.current='';
    setCtx(old=>{const next={...old,...patch},u=new URL(location.href);
      for(const key of previewKeys){const value=next[key];if(value===''||(typeof value==='number'&&value===1)||(key==='view'&&value==='samples'))u.searchParams.delete(key);else u.searchParams.set(key,String(value));}
      window.history.replaceState(null,'',u);return next;});
  },[]);
  useEffect(()=>{const pop=()=>setCtx(previewContext());window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop);},[]);
  useEffect(()=>{if(contextBatch.current!==batch.id){contextBatch.current=batch.id;setCtx(previewContext());setSampleRows(null);setDetail(null);setOrphans(null);setIssues(null);}},[batch.id]);
  useEffect(()=>{
    if(!['QUEUED','RUNNING'].includes(batch.validation_state))return;
    const controller=new AbortController();let active=true,timer:ReturnType<typeof setTimeout>|undefined;setPollError('');
    async function poll(){try{
      const value=await readImport<Batch>('/'+batch.id,controller.signal);if(!active)return;
      onBatch(value,signature);setPollError('');if(['QUEUED','RUNNING'].includes(value.validation_state))timer=setTimeout(()=>void poll(),1500);
    }catch(e){if(active)setPollError('校验进度暂不可读取，已确认的请求仍保留。'+text(e));}}
    timer=setTimeout(()=>void poll(),1500);
    return()=>{active=false;controller.abort();if(timer)clearTimeout(timer);};
  },[batch.id,batch.revision,batch.current_job?.id,batch.validation_state,pollRetry,onBatch]);
  useEffect(()=>{
    const id=++request.current,controller=new AbortController();let active=true;setLoading(true);setError('');
    async function load(){try{
      const [s,u,i,d]=await Promise.all([
        readImport<SamplesPage>('/'+batch.id+'/samples?'+queryString({page:ctx.sample_page,severity:ctx.sample_severity}),controller.signal),
        readImport<UnassignedPage>('/'+batch.id+'/unassigned-tests?page='+ctx.unassigned_page,controller.signal),
        readImport<IssuesPage>('/'+batch.id+'/issues?'+queryString({page:ctx.issue_page,severity:ctx.issue_severity,code:ctx.issue_code,sheet:ctx.issue_sheet,row_id:ctx.issue_row}),controller.signal),
        ctx.sample?readImport<SampleDetail>('/'+batch.id+'/samples/'+ctx.sample+'?test_page='+ctx.test_page,controller.signal):Promise.resolve(null)]);
      const current=await readImport<Batch>('/'+batch.id,controller.signal);
      if(!active||request.current!==id)return;
      if(revisionSignature(current)!==signature){onBatch(current,signature);return;}
      setSampleRows(s);setOrphans(u);setIssues(i);setDetail(d);
    }catch(e){if(active&&request.current===id)setError(text(e));}
    finally{if(active&&request.current===id)setLoading(false);}}
    void load();return()=>{active=false;controller.abort();};
  },[batch.id,signature,ctx,retry,onBatch]);
  useEffect(()=>{
    if(loading||!ctx.row)return;
    const locator='evidence-'+ctx.row+(ctx.field?'-'+ctx.field:'');
    if(focusedLocator.current===locator)return;
    const target=document.getElementById(locator);
    if(target){focusedLocator.current=locator;target.focus();target.scrollIntoView({block:'center'});}
  },[loading,ctx.row,ctx.field,detail,orphans]);
  function locate(i:StagedIssue){
    if(!i.row_id){const h=previewRoot.current?.querySelector<HTMLElement>('#lab-import-issues-heading');h?.focus();h?.scrollIntoView({block:'start'});return;}
    if(i.sample_row_id)update({view:'samples',sample:i.sample_row_id,sample_page:i.sample_page??1,test_page:i.test_page??1,row:i.row_id,field:i.field??'',sample_severity:''});
    else if(i.unassigned_page)update({view:'unassigned',unassigned_page:i.unassigned_page,row:i.row_id,field:i.field??''});
    else setError('此问题尚无可用的行定位，请刷新问题清单；原件仍保留。');
  }
  const job=batch.current_job,phase:Record<string,string>={QUEUED:'等待执行',READING:'读取原件',PARSING:'解码完整表格',VALIDATING:'核对完整记录',PERSISTING:'保存暂存校验结果',COMPLETE:'校验结束'};
  const stale=batch.stale===true||sampleRows?.stale===true||detail?.stale===true||orphans?.stale===true||issues?.stale===true;
  const current=batch.validation_current===true&&sampleRows?.validation_current===true&&sampleRows.result_job_id===job?.id&&!stale;
  const selectedTest=(ctx.view==='unassigned'?orphans?.items:detail?.tests.items)?.find(r=>r.id===ctx.row);
  return <div ref={previewRoot} className="lab-import-preview">
    <section className="lab-import-validation" aria-label="暂存校验状态"><h3>{validationLabel(batch)}</h3>
      <p>校验只核对当前采用的原件，结果仍属于暂存。正式油样、检测、报告与分析记录保持原状。</p>
      <button type="button" disabled={locked||batch.manifest_state!=='COMPLETE'||['QUEUED','RUNNING'].includes(batch.validation_state)} onClick={onValidate}>{batch.validation_state==='NOT_REQUESTED'?'校验暂存资料':'重新校验暂存资料'}</button>
      {batch.manifest_state!=='COMPLETE'&&<p>请先确认保存当前需要的工作簿或两份 CSV。</p>}
      {job&&<div className="lab-import-job"><p>当前任务：{phase[job.phase]??job.phase} · 输入版本 {job.input_revision} · 尝试 {job.attempt}</p>
        {job.state==='RUNNING'&&<><progress max={job.progress_total||1} value={job.progress_done}/><p>{job.phase==='READING'?job.progress_done+' / '+job.progress_total+' 字节已读取':job.progress_total?job.progress_done+' / '+job.progress_total+' 条记录':'正在解码；尚未确定完整记录数。'}</p></>}
        {job.state==='FAILED'&&<p role="alert">校验未完成：{job.error_code??'validation_unavailable'}。原件已保留，请核对状态后显式重试。</p>}
        {job.validation_as_of&&<p>核对依据时间：{job.validation_as_of}</p>}</div>}
      {pollError&&<p role="alert">{pollError}<button type="button" onClick={()=>setPollRetry(n=>n+1)}>重试读取校验进度</button></p>}
      {stale&&<p className="lab-import-stale" role="status">以下是上次保留的校验证据，已过期，不能视为当前结论；当前版本或当前任务尚未成功完成。</p>}
      {current&&<p>当前校验结果：油样 {batch.summary?.sample_count??0} 条，完整检测 {batch.summary?.test_count??0} 条，未关联检测 {batch.summary?.unassigned_test_count??0} 条；错误 {batch.summary?.error_count??0}，警告 {batch.summary?.warning_count??0}。</p>}
    </section>
    {error&&<p role="alert">{error}<button type="button" onClick={()=>setRetry(n=>n+1)}>重试读取预览</button></p>}{loading&&<p role="status">正在读取分页校验证据…</p>}
    <section aria-label="校验问题"><h3 id="lab-import-issues-heading" tabIndex={-1}>校验问题</h3><div className="lab-import-grid">
      <label>问题严重程度<select aria-label="问题严重程度" value={ctx.issue_severity} onChange={e=>update({issue_severity:e.target.value,issue_page:1})}><option value="">全部</option><option value="ERROR">错误</option><option value="WARNING">警告</option><option value="INFO">提示</option></select></label>
      <label>问题代码<input value={ctx.issue_code} onChange={e=>update({issue_code:e.target.value,issue_page:1})}/></label>
      <label>问题业务表<select aria-label="问题业务表" value={ctx.issue_sheet} onChange={e=>update({issue_sheet:e.target.value,issue_page:1})}><option value="">全部</option><option>油样信息</option><option>检测结果</option></select></label>
      <label>问题行 ID<input value={ctx.issue_row} onChange={e=>update({issue_row:e.target.value,issue_page:1})}/></label></div>
      {issues&&<><p>当前筛选：错误 {issues.severity_counts.ERROR} / 警告 {issues.severity_counts.WARNING} / 提示 {issues.severity_counts.INFO}。</p><table aria-label="暂存校验问题"><thead><tr><th>问题与级别</th><th>原件位置</th><th>原值与建议</th><th>定位</th></tr></thead><tbody>{issues.items.map(i=><tr key={i.id}>
        <td>{i.severity} · <strong>{i.code}</strong><small>{i.message}</small></td><td>{i.sheet??'文件'} {i.row_number?'第'+i.row_number+'行':''} · {i.field??''}<code>{i.file_id}</code></td>
        <td><pre>{evidenceText(i.raw_value)}</pre><small>{i.suggestion}</small></td><td><button type="button" onClick={()=>locate(i)}>{i.row_id?'定位 '+i.sheet+' 第'+i.row_number+'行 '+(i.field||'整行'):'查看文件问题'}</button></td></tr>)}</tbody></table>
        {issues.total===0&&<p>{job?.state==='COMPLETE'?'当前筛选没有问题。':'校验完成后显示问题。'}</p>}<Pager page={ctx.issue_page} total={issues.total} pageSize={50} label="问题" onPage={page=>update({issue_page:page})}/></>}
    </section>
    <div className="lab-import-preview-nav"><button type="button" onClick={()=>update({view:'samples',row:ctx.sample,field:''})}>查看油样与关联检测</button>
      <button type="button" onClick={()=>update({view:'unassigned',row:'',field:''})}>查看未关联检测</button><span>未关联检测共 {sampleRows?.unassigned_test_total??0} 条，独立保留并可分页查看。</span></div>
    {ctx.view==='samples'&&<section aria-label="暂存油样清单"><h3>暂存油样清单</h3>
      <label>油样问题级别<select aria-label="油样问题级别" value={ctx.sample_severity} onChange={e=>update({sample_severity:e.target.value,sample_page:1,sample:'',row:'',field:'',test_page:1})}><option value="">全部油样</option><option value="ERROR">有错误</option><option value="WARNING">有警告</option><option value="INFO">有提示</option></select></label>
      {sampleRows&&<><table aria-label="暂存油样"><thead><tr><th>来源样品 ID</th><th>来源行</th><th>完整检测数</th><th>问题</th><th>证据</th></tr></thead><tbody>{sampleRows.items.map(s=><tr key={s.id}>
        <td>{s.external_sample_id??'未提供'}<small>{evidenceText(s.parsed_values.source_lab_key)}</small></td><td>油样信息 第{s.row_number}行</td><td>{s.related_test_count}</td><td>错误 {s.issue_counts.ERROR} / 警告 {s.issue_counts.WARNING}</td><td><button type="button" onClick={()=>update({sample:s.id,row:s.id,field:'',test_page:1})}>查看油样 {s.external_sample_id??'第'+s.row_number+'行'}</button></td></tr>)}</tbody></table>
        {sampleRows.total===0&&<p>当前筛选暂无可显示油样；未关联检测和文件问题仍可独立查看。</p>}<Pager page={ctx.sample_page} total={sampleRows.total} label="油样" onPage={page=>update({sample_page:page,sample:'',row:'',field:'',test_page:1})}/></>}
    </section>}
    {ctx.view==='samples'&&detail&&<section aria-label="油样与关联检测预览"><h3>油样 {detail.sample.external_sample_id??'未提供'} · 完整关联检测 {detail.tests.total} 条</h3><RowEvidence row={detail.sample} title="油样原始与解析证据" onReview={onReview} disabled={locked}/>
      <h4>关联检测</h4><TestRows rows={detail.tests.items} selected={ctx.row} label="关联检测" onSelect={r=>update({row:r.id,field:''})}/>
      <Pager page={ctx.test_page} total={detail.tests.total} label="关联检测" onPage={page=>update({test_page:page,row:detail.sample.id,field:''})}/>
      {selectedTest&&<RowEvidence row={selectedTest} title="检测原始与解析证据" onReview={onReview} disabled={locked}/>}</section>}
    {ctx.view==='unassigned'&&<section aria-label="未关联检测"><h3>未关联检测</h3><p>无法唯一关联到样品的完整检测仍保留原始行和问题；不自动忽略或合并。</p>
      {orphans&&<><TestRows rows={orphans.items} selected={ctx.row} label="未关联完整检测" onSelect={r=>update({row:r.id,field:''})}/>{orphans.total===0&&<p>暂无未关联检测。</p>}
        <Pager page={ctx.unassigned_page} total={orphans.total} label="未关联检测" onPage={page=>update({unassigned_page:page,row:'',field:''})}/></>}
      {selectedTest&&<RowEvidence row={selectedTest} title="检测原始与解析证据" onReview={onReview} disabled={locked}/>}</section>}
  </div>;
}

export function ImportPage(){
  const {session}=useAuth();
  const actor=session?.actor.id??'',csrf=session?.csrf_token??'';
  const initial=new URLSearchParams(location.search);
  const [batch,setBatch]=useState<Batch|null>(null),[batchId,setBatchId]=useState(initial.get('batch')??'');
  const [files,setFiles]=useState<Page<OriginalFile>|null>(null),[history,setHistory]=useState<Page<Revision>|null>(null);
  const [filePage,setFilePage]=useState(1),[revisionPage,setRevisionPage]=useState(1);
  const [purpose,setPurpose]=useState<Purpose>('HISTORICAL'),[format,setFormat]=useState<InputFormat>('XLSX');
  const [zone,setZone]=useState(''),[zoneConfirmed,setZoneConfirmed]=useState(false),[decisions,setDecisions]=useState<SourceDecision[]>([]);
  const [reviewPurpose,setReviewPurpose]=useState<Purpose>('HISTORICAL'),[reviewZone,setReviewZone]=useState(''),[reviewConfirmed,setReviewConfirmed]=useState(false);
  const [reviewReason,setReviewReason]=useState(''),[reviewDecisions,setReviewDecisions]=useState<SourceDecision[]>([]);
  const [editing,setEditingState]=useState<RowDraft|null>(null);
  const editingRef=useRef<RowDraft|null>(null);
  const setEditing=useCallback((value:RowDraft|null)=>{editingRef.current=value;setEditingState(value);},[]);
  useEffect(()=>{if(editing?.row_id){const q=new URLSearchParams(location.search),field=q.get('row')===editing.row_id?q.get('field'):null;const target=(field?document.getElementById('review-'+editing.row_id+'-'+field):null)??document.getElementById('lab-import-row-editor-heading');target?.focus();target?.scrollIntoView({block:'center'});}},[editing?.row_id]);
  const [selected,setSelected]=useState<Partial<Record<FileRole,File>>>({});
  const [intent,setIntent]=useState<ImportIntent|null>(null),[operation,setOperation]=useState<Operation|null>(null);
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[progress,setProgress]=useState<number|null>(null);
  const [storageBlocked,setStorageBlocked]=useState(false);
  const [message,setMessage]=useState(''),[error,setError]=useState('');
  const [batches,setBatches]=useState<Page<Batch>|null>(null),[listPage,setListPage]=useState(1);
  const [filter,setFilter]=useState({q:'',purpose:'',state:'',created_from:'',created_to:'',actor_id:'',source_lab_id:''});
  const flight=useRef<symbol|null>(null),retained=useRef<ImportIntent|null>(null);
  const remember=useCallback((value:ImportIntent|null)=>{retained.current=value;setIntent(value);},[]);
  // Claim synchronously before task() can perform its first asynchronous file read or request.
  const owned=useCallback(async(task:(owner:symbol)=>Promise<void>)=>{
    if(flight.current)return;
    const owner=Symbol('laboratory import request');flight.current=owner;setBusy(true);
    try{await task(owner);}
    finally{if(flight.current===owner){flight.current=null;setBusy(false);setProgress(null);}}
  },[]);

  const detailRequest=useRef(0),listRequest=useRef(0),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;flight.current=null;detailRequest.current++;listRequest.current++;};},[]);
  const refreshList=useCallback(async()=>{
    const id=++listRequest.current;
    try{const result=await readImport<Page<Batch>>('?'+queryString({...filter,page:listPage}));if(mounted.current&&id===listRequest.current)setBatches(result);}
    catch(e){if(mounted.current&&id===listRequest.current)setError(text(e));}
  },[filter,listPage]);
  const open=useCallback(async(id:string,fp=1,rp=1)=>{
    if(editingRef.current&&editingRef.current.batch_id!==id&&Object.keys(changedValues(editingRef.current)).length&&!retained.current){setError('请先保存或明确关闭当前行核对，再打开其他批次。');return;}
    const version=++detailRequest.current;setLoading(true);
    try{
      const [value,f,r]=await Promise.all([readImport<Batch>('/'+id),readImport<Page<OriginalFile>>('/'+id+'/files?page='+fp),readImport<Page<Revision>>('/'+id+'/revisions?page='+rp)]);
      if(!mounted.current||version!==detailRequest.current)return;
      setBatch(value);setBatchId(id);setFiles(f);setHistory(r);setFilePage(fp);setRevisionPage(rp);
      setReviewPurpose(value.purpose);setReviewZone(value.source_timezone??'');setReviewConfirmed(value.source_timezone_confirmed);
      const url=new URL(location.href);if(url.searchParams.get('batch')!==id)for(const key of previewKeys)url.searchParams.delete(key);url.searchParams.set('batch',id);window.history.replaceState(null,'',url);
      return value;
    }catch(e){if(mounted.current&&version===detailRequest.current)setError(text(e));}
    finally{if(mounted.current&&version===detailRequest.current)setLoading(false);}
  },[]);
  const finish=useCallback(async(op:Operation,owner:symbol)=>{
    if(!mounted.current||flight.current!==owner)return;
    setOperation(op);
    if(op.state==='COMPLETED'){
      if(retained.current?.action==='REVISE'&&retained.current.payload.changes?.length)setEditing(null);
      forgetIntent(actor);remember(null);
      setMessage(op.action==='VALIDATE'?'校验请求已确认排队。当次操作结果保持 QUEUED；当前任务进度见下方。':op.action==='RECEIVE'?'原件已确认保存。收件结果与当前批次版本分别显示。':'请求已确认保存。');
      if(op.result?.batch_id)await open(op.result.batch_id);
      if(flight.current===owner)await refreshList();
    }else if(op.state==='REJECTED')setError('原请求已明确拒绝：'+(op.result?.code??'请核对资料')+'。保留原输入；可加载最新批次后准备新的核对。');
    else setMessage('原操作尚未确认完成。请保留请求；上传恢复须重新选择完全相同的原件。');
  },[actor,open,refreshList,remember]);
  const recover=useCallback(async(value:ImportIntent,restoreInputs=false)=>owned(async owner=>{
    setError('');
    try{
      if(restoreInputs){
        if(value.batch_id)await open(value.batch_id);
        if(flight.current!==owner)return;
        if(value.action==='CREATE'){
          setPurpose(value.payload.purpose);setFormat(value.payload.input_format);
          setZone(value.payload.source_timezone??'');setZoneConfirmed(value.payload.source_timezone_confirmed);
          setDecisions(value.payload.source_labs);
        }else if(value.action==='REVISE'){
          const restored=draftFromIntent(value);if(restored)setEditing(restored);
          setReviewReason(value.payload.reason);setReviewDecisions(value.payload.source_labs??[]);
          const metadata=value.payload.metadata;
          if(metadata?.purpose)setReviewPurpose(metadata.purpose);
          if(metadata&&'source_timezone' in metadata)setReviewZone(metadata.source_timezone??'');
          if(metadata&&'source_timezone_confirmed' in metadata)setReviewConfirmed(metadata.source_timezone_confirmed??false);
        }
      }
      await finish(await readImport<Operation>('/operations/'+value.key),owner);
    }catch(e){if(flight.current===owner)setError(e instanceof ImportError&&e.status===404?'尚未查到持久结果，不代表原请求失败。保留原 key，可再次查询或原样重试。':text(e));}
  }),[finish,open,owned]);
  // Restore only the current actor's exact retained request, then query its durable result.
  useEffect(()=>{
    if(!actor)return;
    let current:ImportIntent|null=null;
    try{current=loadIntent(actor);remember(current);setStorageBlocked(false);}catch(e){setError(text(e));setStorageBlocked(true);}
    if(current)void recover(current,true);
    else if(initial.get('batch'))void open(initial.get('batch')!);
    // Actor changes establish the recovery scope; form edits never trigger recovery.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[actor]);
  useEffect(()=>{if(actor)void refreshList();},[actor,refreshList]);
  function addDecision(value:SourceDecision,review=false){
    const update=review?setReviewDecisions:setDecisions;
    update(old=>{if(old.length>=500){setError('一次最多确认 500 项来源身份，请拆分批次。');return old;}if(old.some(x=>x.key===value.key)){setError('本次选择中来源键重复，请移除旧选择后重新加入。');return old;}return [...old,value];});
  }
  async function run(value:ImportIntent,owner:symbol,file?:File){
    if(flight.current!==owner)return;
    setError('');setMessage('');setProgress(null);
    try{
      if(retained.current&&retained.current.key!==value.key)throw new Error('已有未确认请求，请先恢复原操作。');
      retainIntent(actor,value);remember(value);setOperation(null);
      if(value.action==='RECEIVE'){
        if(!file)throw new Error('请选择原操作的同一份原件。');
        const metadata=await fileMetadata(file,value.batch_id,value.payload.role);
        if(flight.current!==owner)return;
        if(!sameOriginal(metadata,value.payload))throw new Error('所选原件与原请求的名称、MIME、长度或 SHA256 不一致，尚未发送。');
        const result=await uploadOriginal(value.payload,value.key,file,csrf,p=>{if(flight.current===owner)setProgress(p);});
        await finish(result.operation,owner);
      }else{
        const result=await sendImport(value.action,value.key,value.payload,value.batch_id,csrf);
        await finish(result.operation,owner);
      }
    }catch(e){
      if(flight.current!==owner)return;
      if(e instanceof ImportError&&e.disposition==='DURABLE_REJECTED'&&e.operation?.action===value.action)
        await finish(e.operation,owner);
      else setError(text(e)+(e instanceof ImportError&&e.status<500?'':' 保存结果尚未确认；请查询原操作。'));
    }
  }
  async function create(e:FormEvent){
    e.preventDefault();if(retained.current||storageBlocked)return;
    await owned(async owner=>{
      try{
        validateMetadata(zone,zoneConfirmed);validateSources(decisions);
        const payload:CreateInput={format_version:1,input_format:format,purpose,
          source_timezone:zone||null,source_timezone_confirmed:zoneConfirmed,source_labs:decisions};
        await run(prepareIntent({action:'CREATE',batch_id:null,payload}),owner);
      }catch(e){if(flight.current===owner)setError(text(e));}
    });
  }
  async function upload(role:FileRole){
    const file=selected[role];
    if(!batch||!file||retained.current||storageBlocked)return;
    await owned(async owner=>{
      setError('');
      try{
        const payload=await fileMetadata(file,batch.id,role);
        if(flight.current===owner)await run(prepareIntent({action:'RECEIVE',batch_id:batch.id,payload}),owner,file);
      }catch(e){if(flight.current===owner)setError(text(e));}
    });
  }
  async function revise(activeFiles?:Partial<Record<FileRole,string>>){
    if(!batch||retained.current||storageBlocked)return;
    await owned(async owner=>{
      try{
        if(!reviewReason.trim()||[...reviewReason].length>1000||reviewReason.includes('\u0000'))
          throw new Error('请填写 1–1000 字符的本次核对原因。');
        if(!activeFiles){validateMetadata(reviewZone,reviewConfirmed);validateSources(reviewDecisions);}
        const payload={expected_revision:batch.revision,reason:reviewReason,
          ...(activeFiles?{active_files:activeFiles}:{metadata:{purpose:reviewPurpose,source_timezone:reviewZone||null,source_timezone_confirmed:reviewConfirmed},source_labs:reviewDecisions})};
        await run(prepareIntent({action:'REVISE',batch_id:batch.id,payload}),owner);
      }catch(e){if(flight.current===owner)setError(text(e));}
    });
  }
  async function retry(value:ImportIntent){
    await owned(owner=>run(value,owner,value.action==='RECEIVE'?selected[value.payload.role]:undefined));
  }
  async function prepareChanged(){
    const original=retained.current;
    if(!original||operation?.state!=='REJECTED')return;
    await owned(async owner=>{
      try{
        const current=original.batch_id?await open(original.batch_id):undefined;
        if(flight.current!==owner||original.batch_id&&!current)return;
        const recovered=draftFromIntent(original,current?.revision);
        forgetIntent(actor);remember(null);setOperation(null);setError('');
        if(recovered)setEditing(recovered);
        setMessage('原拒绝结果已保留在操作历史；请核对最新资料后再保存。');
      }catch(e){if(flight.current===owner)setError(text(e));}
    });
  }
  function startReview(row:StagedRow){
    if(!batch||retained.current||flight.current||storageBlocked)return;
    if(editingRef.current&&Object.keys(changedValues(editingRef.current)).length){
      setError('已有未保存的本行核对，请先保存或明确关闭；原输入仍保留。');return;
    }
    setError('');setEditing(draftFromRow(row,batch.revision));
  }
  async function saveRow(){
    const draft=editingRef.current;
    if(!batch||!draft||draft.batch_id!==batch.id||retained.current||storageBlocked)return;
    await owned(async owner=>{
      const errors=rowReviewErrors(draft),values=changedValues(draft);
      if(errors.length){setError(errors[0]);return;}
      if(!Object.keys(values).length){setError('请先明确修改本行字段。');return;}
      try{await run(prepareIntent({action:'REVISE',batch_id:batch.id,payload:{expected_revision:draft.expected_revision,
        reason:draft.reason,changes:[{row_id:draft.row_id,values}]}}),owner);}
      catch(e){if(flight.current===owner)setError(text(e));}
    });
  }

  const acceptBatch=useCallback((value:Batch,expectedSignature?:string)=>{
    setBatch(old=>old&&old.id===value.id&&old.revision<=value.revision&&(!expectedSignature||revisionSignature(old)===expectedSignature)?value:old);
  },[]);
  async function validate(){
    if(!batch||retained.current||storageBlocked||batch.manifest_state!=='COMPLETE'||['QUEUED','RUNNING'].includes(batch.validation_state))return;
    await owned(async owner=>{
      try{await run(prepareIntent({action:'VALIDATE',batch_id:batch.id,payload:{expected_revision:batch.revision}}),owner);}
      catch(e){if(flight.current===owner)setError(text(e));}
    });
  }

  const roles:FileRole[]=batch?.input_format==='CSV_PAIR'?['SAMPLES','TESTS']:['WORKBOOK'];
  const locked=busy||!!intent||storageBlocked;
  return <div className="lab-import">
    <section className="panel lab-import-intro" aria-label="模板与原件说明">
      <h2>保存实验室资料原件</h2><p>原件和来源身份先保存在暂存批次中。此处不会增加正式油样、检测、报告或分析记录。</p>
      <p>XLSX 含“油样信息”和“检测结果”两张业务表；CSV 使用两份 UTF-8 文件。每份原件最多 10 MiB，CSV 两份合计最多 20 MiB。</p>
      <div className="lab-import-links">{(['XLSX','CSV_PAIR'] as InputFormat[]).map(f=><span key={f}><a href={importRoot+'/template?format='+f+'&version=1'}>下载 v1 {f==='XLSX'?'XLSX':'CSV 双表'} 模板</a><a href={importRoot+'/template?format='+f+'&example=true&version=1'}>下载虚构{f==='XLSX'?' XLSX':' CSV 双表'}示例</a></span>)}</div>
    </section>
    {error&&<p className="lab-import-alert" role="alert">{error}</p>}
    {message&&<p className="lab-import-status" role="status">{message}</p>}
    {intent&&<section className="panel lab-import-recovery" aria-label="未确认操作">
      <h2>恢复原请求</h2><p>类型：{intent.action==='CREATE'?'创建批次':intent.action==='RECEIVE'?'保存原件':intent.action==='VALIDATE'?'校验资料':'保存核对'}。保留原 key 和原请求，不会自动重复创建。</p>
      {intent.action==='RECEIVE'&&<p>请重新选择：{intent.payload.filename} · {intent.payload.byte_size} 字节 · SHA256 <code>{intent.payload.sha256}</code></p>}
      <button disabled={busy} onClick={()=>void recover(intent)}>查询未确认操作</button>
      <button disabled={busy||operation?.state==='REJECTED'} onClick={()=>void retry(intent)}>原样重试请求</button>
      {operation?.state==='REJECTED'&&<button disabled={busy} onClick={()=>void prepareChanged()}>加载最新批次并准备新的核对</button>}
      {intent.action==='RECEIVE'&&!batch&&<label>重新选择同一原件<input type="file" accept={intent.payload.role==='WORKBOOK'?'.xlsx':'.csv'} onChange={e=>setSelected(old=>({...old,[intent.payload.role]:e.target.files?.[0]}))}/></label>}
    </section>}
    {operation?.state==='COMPLETED'&&<p className="lab-import-operation">已确认操作：{operation.result?.outcome} · 当次生效版本 {operation.result?.applied_revision}；当前批次版本见下方。</p>}
    {!batch&&<section className="panel" aria-label="创建暂存批次"><h2>创建暂存批次</h2>
      <form onSubmit={e=>void create(e)}>
        <fieldset disabled={locked}><legend>批次元数据</legend><div className="lab-import-grid">
          <label>导入用途<select aria-label="导入用途" value={purpose} onChange={e=>setPurpose(e.target.value as Purpose)}><option value="HISTORICAL">历史资料</option><option value="DAILY">日常检测资料</option></select></label>
          <label>原件格式<select aria-label="原件格式" value={format} onChange={e=>setFormat(e.target.value as InputFormat)}><option value="XLSX">XLSX 工作簿</option><option value="CSV_PAIR">两份 UTF-8 CSV</option></select></label>
          <label>来源时区（可留空，IANA）<input value={zone} onChange={e=>{setZone(e.target.value);setZoneConfirmed(false);}} placeholder="例如 America/Chicago"/></label>
          <label className="lab-import-choice"><input type="checkbox" checked={zoneConfirmed} onChange={e=>setZoneConfirmed(e.target.checked)} disabled={!zone}/>已核实此来源时区，不使用浏览器默认时区</label>
        </div></fieldset>
        <SourceChoices onAdd={v=>addDecision(v)} disabled={locked}/>
        <DecisionList values={decisions} disabled={locked} onRemove={i=>setDecisions(old=>old.filter((_,n)=>n!==i))}/>
        <button type="submit" disabled={locked}>{busy?'正在确认请求…':'创建暂存批次'}</button>
      </form>
    </section>}
    {loading&&<p role="status">正在读取暂存批次…</p>}
    {batch&&<section className="panel" aria-label="当前暂存批次"><h2>当前暂存批次</h2>
      <dl className="lab-import-facts"><div><dt>批次 ID</dt><dd><code>{batch.id}</code></dd></div><div><dt>当前版本</dt><dd>{batch.revision}</dd></div><div><dt>用途与格式</dt><dd>{purposeLabel[batch.purpose]} · {batch.input_format}</dd></div><div><dt>原件清单</dt><dd>{batch.manifest_state==='COMPLETE'?'当前采用的原件已齐备':batch.manifest_state==='PARTIAL'?'当前采用的原件尚缺一份':'尚无已确认采用的原件'} · 仅暂存</dd></div><div><dt>来源时区</dt><dd>{batch.source_timezone??'未提供'} · {batch.source_timezone_confirmed?'已核实':'未核实'}</dd></div></dl>
      <button disabled={busy||loading} onClick={()=>void open(batch.id,filePage,revisionPage)}>刷新当前批次</button>
      <button disabled={locked} onClick={()=>{if(editingRef.current&&Object.keys(changedValues(editingRef.current)).length){setError('请先保存或明确关闭本行核对。');return;}setEditing(null);detailRequest.current++;setBatch(null);setBatchId('');setSelected({});setDecisions([]);setReviewDecisions([]);setReviewReason('');const u=new URL(location.href);u.searchParams.delete('batch');window.history.replaceState(null,'',u);}}>准备另一批次</button>
      <section aria-label="当前采用的原件"><h3>当前采用的原件</h3>{batch.active_files?.length?<ul>{batch.active_files.map(f=><li key={f.id}>{labels[f.role]}：{f.filename} · {f.byte_size} 字节 · 已确认保存</li>)}</ul>:<p>尚未选择已确认的原件。</p>}</section>
      <div className="lab-import-upload">{roles.map(role=><fieldset key={role} disabled={busy||(!!intent&&!(intent.action==='RECEIVE'&&intent.payload.role===role))}>
        <legend>{labels[role]}原件</legend><label>选择{labels[role]}原件<input type="file" accept={role==='WORKBOOK'?'.xlsx':'.csv'} onChange={e=>setSelected(old=>({...old,[role]:e.target.files?.[0]}))}/></label>
        <button disabled={locked||!selected[role]} onClick={()=>void upload(role)}>保存{labels[role]}原件</button>
      </fieldset>)}</div>
      {progress!==null&&<div role="status"><progress max={100} value={progress}/><p>原件字节已发送 {progress}%{progress===100?'，正在等待服务器确认收件。':'。此进度不代表已保存。'}</p></div>}
      <>{editing&&editing.batch_id===batch.id&&<RowEditor draft={editing} disabled={locked} onChange={setEditing} onSave={()=>void saveRow()} onClose={()=>setEditing(null)}/>}<ImportPreview key={batch.id} batch={batch} onBatch={acceptBatch} locked={locked} onValidate={()=>void validate()} onReview={startReview}/></>
      <h3>已确认的来源身份</h3>{batch.source_labs?.length?<ul>{batch.source_labs.map(s=><li key={s.source_lab_key}><strong>{s.source_lab_key}</strong> → {s.display_name} · {s.source_kind==='IN_HOUSE'?'内部':'第三方'}<code>{s.source_lab_id}</code></li>)}</ul>:<p>尚未确认来源身份。</p>}
      <details className="lab-import-review"><summary>核对用途、来源时区与身份</summary><fieldset disabled={locked}><legend>本次元数据核对</legend>
        <div className="lab-import-grid"><label>核对导入用途<select aria-label="核对导入用途" value={reviewPurpose} onChange={e=>setReviewPurpose(e.target.value as Purpose)}><option value="HISTORICAL">历史资料</option><option value="DAILY">日常检测资料</option></select></label><label>核对来源时区（可留空，IANA）<input value={reviewZone} onChange={e=>{setReviewZone(e.target.value);setReviewConfirmed(false);}}/></label><label className="lab-import-choice"><input type="checkbox" checked={reviewConfirmed} disabled={!reviewZone} onChange={e=>setReviewConfirmed(e.target.checked)}/>已核实本次来源时区</label></div>
      </fieldset><SourceChoices onAdd={v=>addDecision(v,true)} disabled={locked}/><DecisionList values={reviewDecisions} disabled={locked} onRemove={i=>setReviewDecisions(old=>old.filter((_,n)=>n!==i))}/>
        <button disabled={locked} onClick={()=>void revise()}>保存元数据与来源核对</button>
      </details>
      <label>本次核对原因（修改元数据或选用其他原件时必填）<textarea aria-label="本次核对原因" value={reviewReason} onChange={e=>setReviewReason(e.target.value)} rows={2} disabled={locked}/><small>{[...reviewReason].length}/1000 字符</small></label>
      <section aria-label="保留的原件历史"><h3>保留的原件历史</h3><p>未确认或未采用的历史原件单独保留，不替换当前原件；其他上传者的私有恢复请求不可访问。</p>
        {files&&<><table><thead><tr><th>原件与角色</th><th>状态</th><th>长度与 SHA256</th><th>保留时间</th><th>操作</th></tr></thead><tbody>{files.items.map(f=><tr key={f.id} className={f.active?'lab-import-active':''}><td>{f.filename}<small>{labels[f.role]}</small></td><td>{receiptState[f.state]}<strong>{f.active?' · 当前采用':' · 历史记录'}</strong></td><td>{f.byte_size} 字节<code>{f.sha256}</code></td><td>{time(f.reserved_at)}</td><td>{f.state==='RECEIVED'?<><a href={importRoot+'/'+batch.id+'/files/'+f.id+'/original'}>下载原件：{f.filename}</a>{!f.active&&<button disabled={locked} onClick={()=>void revise({[f.role]:f.id})}>改用此{labels[f.role]}原件</button>}</>:<span>尚无已确认的可下载原件</span>}</td></tr>)}</tbody></table><Pager page={filePage} total={files.total} label="原件" onPage={p=>void open(batch.id,p,revisionPage)}/></>}
      </section>
      <section aria-label="暂存修订历史"><h3>暂存修订历史</h3>{history&&<><table><thead><tr><th>版本</th><th>核对者与时间</th><th>原因</th></tr></thead><tbody>{history.items.map(r=><tr key={r.id}><td>{r.revision}</td><td>{r.display_name}<small>{time(r.occurred_at)}</small></td><td>{r.reason}<details><summary>查看此修订的前后资料</summary><p>{r.change_kind==='ROW'?r.sheet+' 第'+r.row_number+'行':'批次资料'} · 事件 <code>{r.event_id??r.id}</code></p>{r.change_kind==='ROW'?<RowRevision before={r.before_value} after={r.after_value}/>:<><p>本次行核对：{r.row_change_count??0} 行，逐行内容分页显示。</p><h4>修订前</h4><RevisionSnapshot value={r.before_value}/><h4>修订后</h4><RevisionSnapshot value={r.after_value}/></>}</details></td></tr>)}</tbody></table>{history.total===0&&<p>暂无修订。</p>}<Pager page={revisionPage} total={history.total} label="修订" onPage={p=>void open(batch.id,filePage,p)}/></>}</section>
    </section>}
    <section className="panel" aria-label="暂存批次历史"><h2>暂存批次历史</h2><form onSubmit={e=>{e.preventDefault();setListPage(1);void refreshList();}}><div className="lab-import-grid">
      <label>批次 ID 或原文件名<input value={filter.q} onChange={e=>{setFilter(v=>({...v,q:e.target.value}));setListPage(1);}}/></label>
      <label>历史用途<select value={filter.purpose} onChange={e=>{setFilter(v=>({...v,purpose:e.target.value}));setListPage(1);}}><option value="">全部</option><option value="HISTORICAL">历史资料</option><option value="DAILY">日常检测资料</option></select></label>
      <label>历史校验状态<select aria-label="历史校验状态" value={filter.state} onChange={e=>{setFilter(v=>({...v,state:e.target.value}));setListPage(1);}}><option value="">全部</option><option value="NOT_REQUESTED">尚未校验</option><option value="QUEUED">已排队</option><option value="RUNNING">正在校验</option><option value="COMPLETE">校验结束（仅暂存）</option><option value="FAILED">校验未完成</option></select></label>
      <label>创建日期从（UTC）<input type="date" value={filter.created_from} onChange={e=>{setFilter(v=>({...v,created_from:e.target.value}));setListPage(1);}}/></label>
      <label>创建日期至（UTC）<input type="date" value={filter.created_to} onChange={e=>{setFilter(v=>({...v,created_to:e.target.value}));setListPage(1);}}/></label>
      <label>操作人员 ID<input value={filter.actor_id} onChange={e=>{setFilter(v=>({...v,actor_id:e.target.value}));setListPage(1);}}/></label>
      <label>来源实验室稳定 ID<input value={filter.source_lab_id} onChange={e=>{setFilter(v=>({...v,source_lab_id:e.target.value}));setListPage(1);}}/></label>
    </div><button type="submit">刷新批次历史</button></form>
      {batches?<><table><thead><tr><th>批次</th><th>用途与格式</th><th>版本与状态</th><th>创建时间</th></tr></thead><tbody>{batches.items.map(b=><tr key={b.id}><td><a href={'/lab/imports?batch='+b.id} onClick={e=>{e.preventDefault();void open(b.id);}}><code>{b.id}</code></a></td><td>{purposeLabel[b.purpose]} · {b.input_format}</td><td>{b.revision} · {{NOT_REQUESTED:'尚未校验',QUEUED:'已排队',RUNNING:'正在校验',COMPLETE:'校验结束',FAILED:'校验未完成'}[b.validation_state]??b.validation_state} · 仅暂存{b.summary?.last_job_id&&<small>上次校验：油样 {b.summary.sample_count??'未知'} / 完整检测 {b.summary.test_count??'未知'} / 错误 {b.summary.error_count??'未知'}</small>}</td><td>{time(b.created_at)}</td></tr>)}</tbody></table>{batches.total===0&&<p>没有符合条件的暂存批次。</p>}<Pager page={listPage} total={batches.total} label="批次" onPage={setListPage}/></>:<p role="status">正在读取批次历史…</p>}
    </section>
  </div>;
}
