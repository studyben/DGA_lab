import {importBatchHref,importPayloadDigest,newImportIntentKey} from './siteImportIntent';
import {importFieldLabels as labels} from './siteImportPresentation';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import { useRead } from './assetUi';
import {ImportSourcesPanel} from './ImportSourcesPanel';
import { SiteExportButton } from './SiteExportButton';
import './siteImport.css';

type Values = Record<string, string | number | boolean | null>;
type Sheet='Customers'|'Sites'|'Materials'|'Assets';
type Candidate = {id?:string;kind?:string;record_key?:string;sheet?:string;row?:number;site_name?:string;customer_name?:string;customer_id?:string;location_text?:string;material_number?:string;model?:string;asset_type?:string;system_asset_number?:string;serial_number?:string;status?:string;location?:unknown;lines?:{product_line:string;power_mw:string|null;energy_mwh:string|null}[]};
type Row={sheet:Sheet;row:number;values:Values;original_values:Values;candidates:Candidate[];target_id?:string;target_key?:string;system_asset_number?:string;references?:unknown;resolved_context?:unknown};
type Issue={id?:string;code:string;sheet:string;row:number;field:string;severity:'WARNING'|'ERROR';message:string};
type Operation={outcome:string;batch_id:string;targets?:{kind:string;target_id?:string;target_key?:string;system_asset_number?:string}[]};
type Meta={id:string;filename:string;format_version:number;mode:'SITES'|'ASSETS';state:'STAGED'|'VALIDATED'|'PUBLISHED'|'FAILED'};
type Batch=Meta & {validation_revision:number;page:number;total_rows:number;rows:Row[];issues:Issue[];summary:{total_rows:number;error_count:number;warning_count:number;by_kind?:Record<string,{new_rows:number;reference_rows:number}>};duplicate_batches:Meta[];duplicate_total:number;operation_result?:Operation};
type History={batches:Meta[];total:number;page:number};
type RevisionHistory={changes:{revision:number;reason:string;sheet:string;row:number;before:Values;after:Values;display_name:string;occurred_at:string}[];total:number};
type RevisionRequest={expected_revision:number;changes:{sheet:Sheet;row:number;values:Values}[];reason:string};
type Pending={key:string;kind:'upload'|'revise'|'publish';digest:string;batch?:string;mode?:'SITES'|'ASSETS';format_version?:number;revision_request?:RevisionRequest};
const root='/api/assets/imports';

const columns:Record<Sheet,string[]>={Customers:['record_key','decision','customer_id','customer_name','source_note'],Sites:['record_key','decision','site_id','site_name','customer_ref','location_text','product_lines','pv_power_mw','ess_power_mw','ess_energy_mwh','commissioning_date','grid_status','operation_status','source_note'],Materials:['record_key','decision','material_number','model','asset_type','source_note'],Assets:['record_key','decision','serial_number','material_ref','product_line','machine_type','status','location_kind','effective_at','parent_record_key','site_id','site_name','power_mw','energy_mwh','equipment_name','tag_number','commissioning_date','battery_manufacturer','source_note']};
// The one-row editor has a bounded scalar payload; never replay arbitrary stored requests.
function isRevisionRequest(value:unknown):value is RevisionRequest {
  if(!value||typeof value!=='object'||Array.isArray(value))return false;
  const request=value as Record<string,unknown>;
  if(Object.keys(request).sort().join(',')!=='changes,expected_revision,reason'||!Number.isInteger(request.expected_revision)||Number(request.expected_revision)<0||typeof request.reason!=='string'||!request.reason.trim()||Array.from(request.reason).length>1000||!Array.isArray(request.changes)||request.changes.length!==1)return false;
  const change=request.changes[0];
  if(!change||typeof change!=='object'||Array.isArray(change)||Object.keys(change).sort().join(',')!=='row,sheet,values'||typeof change.sheet!=='string'||!Object.prototype.hasOwnProperty.call(columns,change.sheet)||!Number.isInteger(change.row)||change.row<2||!change.values||typeof change.values!=='object'||Array.isArray(change.values))return false;
  return Object.entries(change.values).every(([field,v])=>(field==='reason'||columns[change.sheet as Sheet].includes(field))&&(v===null||typeof v==='string'&&Array.from(v).length<=2000||typeof v==='number'&&Number.isFinite(v)||typeof v==='boolean'));
}

const stateNames:Record<string,string>={STAGED:'待后台校验',VALIDATED:'待核对 / 可提交',FAILED:'文件或校验失败',PUBLISHED:'已整批发布'};
const messages:Record<string,string>={import_has_errors:'还有阻断问题，请先逐行核对。',import_warnings_unacknowledged:'请逐项确认全部警告，可切换预览页继续核对。',import_stale_validation:'预览已变化，请重新加载并核对。',import_operation_conflict:'操作键与原请求内容不同，请先查询原操作结果。',object_storage_unavailable:'原文件服务暂不可用，结果未确认；请查询原操作后重试。',import_submit_unavailable:'上传结果未确认，请先查询原操作。',import_revision_unavailable:'核对结果未确认，请先查询原操作。',import_publish_unavailable:'发布结果未确认，请先查询原操作。',permission_denied:'当前账号没有此操作权限。',session_expired:'登录已失效，请重新登录后查询原操作。',csrf_rejected:'会话已更新，请刷新页面后查询原操作。',invalid_import_revision:'核对内容不符合格式，请检查字段和原因。',import_already_published:'批次已发布，不能继续修改。'};
const text=(v:unknown)=>v==null?'未提供':String(v);
async function errorMessage(response:Response,parsed?:{code?:string}) {const body=parsed??await response.json().catch(()=>({}));return messages[body.code]??`操作未成功（${response.status}），请检查输入或重新读取批次。`;}

export function V2ImportPanel({mode}:{mode:'SITES'|'ASSETS'}) {
  const {session}=useAuth();
  const isSites=mode==='SITES',title=isSites?'现场':'设备物料';
  const [selected,setSelected]=useState(()=>new URLSearchParams(location.search).get('batch')??'');
  const [batch,setBatch]=useState<Batch|null>(null);
  const [page,setPage]=useState(1),[historyPage,setHistoryPage]=useState(1),[revisionPage,setRevisionPage]=useState(1);
  const [duplicatePage,setDuplicatePage]=useState(1),[uploadProgress,setUploadProgress]=useState<number|null>(null);
  const [refresh,setRefresh]=useState(0),[search,setSearch]=useState(''),[filter,setFilter]=useState('');
  const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState('');
  const [retainedRevision,setRetainedRevision]=useState<Pending|null>(null);
  const [revisionTerminal,setRevisionTerminal]=useState(false);
  const [ack,setAck]=useState<string[]>([]),[editing,setEditing]=useState<Row|null>(null),[draft,setDraft]=useState<Values>({}),[reason,setReason]=useState('');
  const fieldErrors:Record<string,string>=Object.fromEntries(Object.entries(draft).flatMap(([field,value])=>{
    const count=typeof value==='string'?Array.from(value).length:0;
    return count>2000?[[field,`${labels[field]}最多2000个字符，当前${count}个；输入已保留，请缩短后保存。`]]:[];
  }));
  const reasonCount=Array.from(reason).length;
  const reasonError=reasonCount>1000?`本次核对原因最多1000个字符，当前${reasonCount}个；输入已保留，请缩短后保存。`:'';
  const revisionInputError=Object.values(fieldErrors)[0]??reasonError;
  const seen=useRef(''), lock=useRef(false),alert=useRef<HTMLDivElement>(null);
  const history=useRead<History>(`${root}?query=${encodeURIComponent(search)}&page=${historyPage}&refresh=${refresh}`);
  const revisions=useRead<RevisionHistory>(selected?`${root}/${selected}/revisions?page=${revisionPage}&refresh=${refresh}`:null);
  const storageKey=`${isSites?'dga-site-import-pending':'dga-asset-import-pending'}:${session?.actor.id??'anonymous'}`;
  const readPending=():Pending|null=>{
    const raw=sessionStorage.getItem(storageKey);if(!raw)return null;
    const pending:Pending=JSON.parse(raw);
    if((pending.mode&&pending.mode!==mode)||(pending.format_version&&pending.format_version!==2))throw new Error('未确认操作格式不同，请保留并返回原导入模式查询。');
    if(pending.revision_request!==undefined){
      if(pending.kind!=='revise'||!pending.batch||!isRevisionRequest(pending.revision_request))throw new Error('保存的原修订格式不完整，请保留原操作记录；尚未发送重试。');
      const digest=importPayloadDigest(new TextEncoder().encode(JSON.stringify(pending.revision_request)));
      if(pending.digest!==`2:${mode}:${digest}`&&!(isSites&&!pending.mode&&pending.digest===digest))throw new Error('保存的原修订与摘要不符，请保留原操作记录；尚未发送重试。');
    }
    return pending;
  };
  function persistPending(pending:Pending){
    if(pending.kind==='revise'&&!isRevisionRequest(pending.revision_request))throw new Error('原修订超出单行编辑范围，尚未发送请求，请保留当前输入。');
    const saved=JSON.stringify(pending);
    try{sessionStorage.setItem(storageKey,saved);if(sessionStorage.getItem(storageKey)!==saved)throw new Error('readback');}
    catch{throw new Error('无法安全保存原操作及修订输入；尚未发送请求，请保留当前输入并检查浏览器存储后重试。');}
  }


  function choose(id:string) {setSelected(id);setBatch(null);setRevisionTerminal(false);setPage(1);setEditing(null);setError('');setAck([]);setRevisionPage(1);setDuplicatePage(1);setRefresh(n=>n+1);historyReplace(id);}
  function historyReplace(id:string) {window.history.replaceState(null,'',id?importBatchHref({id,format_version:2,mode}):`/assets/import?mode=${mode}`);}
  useEffect(()=>{if(error){alert.current?.focus();alert.current?.scrollIntoView({block:'nearest'});}},[error]);
  useEffect(()=>{
    if(!selected){setBatch(null);return;}
    let active=true;let timer:ReturnType<typeof setTimeout>|undefined;const controller=new AbortController();
    async function load(){try{
      const response=await fetch(`${root}/${selected}?page=${page}&duplicate_page=${duplicatePage}`,{cache:'no-store',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
      if(!response.ok)throw new Error(await errorMessage(response));
      const value:Batch=await response.json();if(!active)return;
      if(value.format_version!==2||value.mode!==mode){location.assign(importBatchHref(value));return;}
      const revision=`${value.id}:${value.validation_revision}`;if(seen.current!==revision){setAck([]);seen.current=revision;}
      setBatch(value);if(value.state==='STAGED')timer=setTimeout(()=>void load(),1500);
    }catch(e){if(active)setError(e instanceof Error?e.message:'无法读取批次。');}}
    void load();return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[selected,page,duplicatePage,refresh,mode]);

  async function recover():Promise<boolean> {
    const pending=readPending();if(!pending)return false;
    const response=await fetch(`${root}/operations/${pending.key}`,{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(response.status===404){
      if(pending.kind==='revise'&&pending.revision_request){
        setRetainedRevision(pending);if(selected!==pending.batch)choose(pending.batch!);
        setNotice('原修订尚未确认，已恢复当时输入；可查询结果或使用同一原操作重试。404不表示已回滚。');
      }else setNotice(pending.kind==='revise'?'旧版本只保存了修订摘要，未保存当时输入，无法自动恢复；原操作键仍保留。请核对原操作，不要将404当作失败或猜填原内容。':'此操作暂未查到完成记录；请保留原输入并使用原操作重试。');
      return false;
    }
    if(!response.ok)throw new Error(await errorMessage(response));
    const result=await response.json();sessionStorage.removeItem(storageKey);setRetainedRevision(null);choose(result.batch_id);
    setNotice(result.outcome==='PUBLISHED'?(isSites?'客户与现场已整批发布。':'设备与相关主数据已整批发布。'):result.outcome==='REFRESHED'?'原操作已刷新预览，请重新核对。':'已找到原操作结果，正在读取批次。');return true;
  }
  async function mutate(kind:Pending['kind'],retained?:Pending) {
    if((kind==='revise'&&(revisionTerminal||(!retained&&batch?.state==='PUBLISHED')))||lock.current||!session||(kind==='upload'?!file:retained?!retained.batch||!retained.revision_request:!batch)||(kind==='revise'&&!retained&&!editing))return;
    if(kind==='revise'&&!retained&&revisionInputError){setError(revisionInputError);return;}
    lock.current=true;setBusy(true);setError('');setNotice('');
    try{
      if(kind==='upload'&&file!.size>10*1024*1024)throw new Error('导入文件不得超过10 MiB，请分批。');
      const batchId=retained?.batch??batch?.id;
      const payload=retained?.revision_request??(kind==='upload'?undefined:kind==='revise'?{expected_revision:batch!.validation_revision,changes:[{sheet:editing!.sheet,row:editing!.row,values:{...draft,reason:reason.trim()}}],reason:reason.trim()}:{validation_revision:batch!.validation_revision,acknowledged_warning_ids:[...ack].sort()});
      const bytes=kind==='upload'?await file!.arrayBuffer():new TextEncoder().encode(JSON.stringify(payload));
      const originalSignature=importPayloadDigest(bytes)+(kind==='upload'?`:${file!.name}`:'');
      const signature=`2:${mode}:`+originalSignature;
      let pending=readPending();
      if(pending){if(await recover())return;if(pending.kind!==kind||(pending.digest!==signature&&!(isSites&&!pending.mode&&pending.digest===originalSignature))||pending.batch!==(kind==='upload'?undefined:batchId))throw new Error('仍有未确认操作。请先查询结果，或恢复原文件／原核对输入后重试。');}
      else {pending={key:newImportIntentKey(),kind,digest:signature,mode,format_version:2,batch:kind==='upload'?undefined:batchId,...(kind==='revise'?{revision_request:payload as RevisionRequest}:{})};persistPending(pending);}
      const response=kind==='upload'?await new Promise<Response>((resolve,reject)=>{
        const request=new XMLHttpRequest();
        request.open('POST',`${root}?format_version=2&mode=${mode}&filename=${encodeURIComponent(file!.name)}`);
        request.withCredentials=true;request.timeout=45000;
        request.setRequestHeader('X-CSRF-Token',session.csrf_token);
        request.setRequestHeader('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        request.setRequestHeader('Idempotency-Key',pending!.key);
        request.upload.onprogress=event=>{if(event.lengthComputable)setUploadProgress(Math.round(100*event.loaded/event.total));};
        request.onload=()=>resolve(new Response(request.responseText,{status:request.status}));
        request.onerror=()=>reject(new TypeError('连接中断，结果尚未确认'));
        request.ontimeout=()=>reject(new Error('响应超时，结果尚未确认，请查询原操作。'));
        setUploadProgress(0);request.send(file);
      }):await fetch(`${root}/${batchId}/${kind==='revise'?'revisions':'publish'}`,{
        method:'POST',credentials:'same-origin',signal:AbortSignal.timeout(45000),headers:{'X-CSRF-Token':session.csrf_token,'Content-Type':'application/json'},body:JSON.stringify({...payload,idempotency_key:pending.key})});
      if(!response.ok){
        const failure:{code?:string}=(await response.json().catch(()=>({})))??{};
        // The server checks an existing intent first. This exact domain rejection
        // precedes all revision writes; lookup404 or an arbitrary409 proves nothing.
        const terminal=kind==='revise'&&response.status===409&&failure.code==='import_already_published';
        const rejected=terminal||kind==='revise'&&response.status===409&&failure.code==='import_stale_validation';
        if(rejected){
          const original=payload as RevisionRequest,change=original.changes[0];
          sessionStorage.removeItem(storageKey);setRetainedRevision(null);setRevisionTerminal(terminal);
          setEditing(batch?.rows.find(row=>row.sheet===change.sheet&&row.row===change.row)??{sheet:change.sheet,row:change.row,values:change.values,original_values:{},candidates:[]});
          setDraft(Object.fromEntries(Object.entries(change.values).filter(([field])=>columns[change.sheet].includes(field))));
          setReason(original.reason);
        }else if(kind!=='revise'&&response.status<500&&![401,403].includes(response.status))sessionStorage.removeItem(storageKey);
        throw new Error((terminal?'本次修订已被服务器明确拒绝，批次已发布；原输入保留供复制，请重新读取批次并创建新批次。':rejected?'本次修订已被服务器明确拒绝，未保存；输入已保留，请重新读取批次并重新核对。':'')+await errorMessage(response,failure));
      }
      const result:Batch=await response.json();sessionStorage.removeItem(storageKey);setRetainedRevision(null);choose(result.id);
      // This authoritative result is already displayed. A same-version reread
      // must not clear warnings the user confirms before that response arrives.
      seen.current=`${result.id}:${result.validation_revision}`;setBatch(result);
      setNotice(kind==='upload'?`${title}文件已接收，等待后台校验。`:kind==='revise'?'核对已保存，预览已更新，请重新确认警告。':result.operation_result?.outcome==='PUBLISHED'?(isSites?'客户与现场已整批发布。':'设备与相关主数据已整批发布。'):'正式资料已变化，预览已刷新，尚未发布；请重新核对。');
    }catch(e){setError(e instanceof TypeError?'连接中断，结果尚未确认，请查询原操作；不要重新创建上传。':e instanceof Error&&e.name!=='TimeoutError'?e.message:'响应超时，结果尚未确认，请查询原操作；不要重新创建上传。');}
    finally{lock.current=false;setBusy(false);setUploadProgress(null);}
  }
  function edit(row:Row){setEditing(row);setDraft(Object.fromEntries(columns[row.sheet].map(field=>[field,row.values[field]??null])));setReason('');setError('');setTimeout(()=>document.getElementById('import-review')?.scrollIntoView({block:'start'}),0);}
  useEffect(()=>{if(batch&&batch.summary.error_count>0){const issues=document.getElementById('import-issues');issues?.focus();issues?.scrollIntoView({block:'nearest'});}},[batch?.id,batch?.validation_revision]);
  const matching=(row:unknown)=>JSON.stringify(row).toLocaleLowerCase().includes(filter.toLocaleLowerCase());
  const rows=batch?.rows.filter(matching)??[],issues=batch?.issues.filter(matching)??[];
  const retainedPayload=retainedRevision?.revision_request;
  const canPublish=!retainedRevision&&!editing&&batch?.state==='VALIDATED'&&batch.summary.error_count===0&&ack.length>=batch.summary.warning_count;
  return <div className="asset-dashboard site-import">
    <SiteExportButton/>
    <section className="dashboard-table-panel" aria-label={isSites?"仅现场导入":"设备物料导入"}>
      <div className="table-toolbar"><h2>{isSites?'仅导入现场信息':'导入设备与相关主数据'}</h2><a className="button" href={`${root}/template?format_version=2&mode=${mode}`}>{mode==='SITES'?'下载 v2 现场模板':'下载 v2 设备物料模板'}</a></div>
      <p>客户与现场分表填写，客户可引用已有编号或同批新增。现场可以没有设备；已有资料只引用，差异需明确核对。</p>
      <p className="import-note">每表最多500条 · XLSX不超过10 MiB · 来源备注最多2000字符 · 编号使用文本，未知容量留空</p>
      <label>{isSites?'选择现场 Excel 文件':'选择设备物料 Excel 文件'}<input type="file" accept=".xlsx" disabled={busy} onChange={e=>{setFile(e.target.files?.[0]??null);choose('');}}/></label>
      <div className="site-import-actions"><button disabled={!file||busy} onClick={()=>void mutate('upload')}>{isSites?'上传现场文件并校验':'上传设备物料文件并校验'}</button><button disabled={busy} onClick={()=>{setError('');void recover().then(found=>{if(!found&&!readPending())setNotice('未找到已完成的未确认操作；可使用原输入重试。');}).catch(e=>setError(String(e.message)));}}>查询未确认操作</button></div>
    </section>
    {retainedRevision&&retainedPayload&&<section className="dashboard-table-panel" aria-label="未确认原修订"><h3>原修订输入（未确认）</h3><p>批次 {retainedRevision.batch} · 原核对修订 {retainedPayload.expected_revision}。按保存的原输入和原操作键重试，不采用当前预览或其他编辑内容。</p>{retainedPayload.changes.map(change=><div key={`${change.sheet}:${change.row}`}><p>{change.sheet} 第{change.row}行</p>{Object.entries(change.values).map(([field,value])=><label key={field}>恢复的{labels[field]??field}<textarea aria-label={`恢复的${labels[field]??field}`} readOnly value={value===null?'':String(value)}/></label>)}</div>)}<label>恢复的核对原因<textarea aria-label="恢复的核对原因" readOnly value={retainedPayload.reason}/></label><button disabled={busy} onClick={()=>void mutate('revise',retainedRevision)}>使用原操作重试修订</button></section>}
    {error&&<div className="import-error" role="alert" tabIndex={-1} ref={alert}>{error}<button disabled={busy} onClick={()=>{setError('');setRefresh(n=>n+1);}}>重新读取批次</button></div>}
    {uploadProgress!==null&&<p role="status">实际上传进度 {uploadProgress}% <progress aria-label="文件上传进度" max={100} value={uploadProgress}/></p>}{busy&&<p role="status">正在处理，请稍候；原文件与操作记录会保留。</p>}{notice&&<p role="status">{notice}</p>}
    {selected&&!batch&&<p>正在读取现场批次…</p>}
    {batch&&<section className="dashboard-table-panel" aria-label={`${title}导入预览`}>
      <div className="table-toolbar"><h2>{batch.filename}</h2><span>{stateNames[batch.state]}</span><a className="button" href={`${root}/${batch.id}/source`}>下载原始上传文件</a></div>
      <p className="import-note">批次 {batch.id} · 核对修订 {batch.validation_revision} · 总行数 {batch.summary.total_rows} · 阻断 {batch.summary.error_count} · 警告 {batch.summary.warning_count}</p>
      {batch.state==='STAGED'&&<p>后台正在校验，页面将自动更新；无需重复上传。</p>}
      {batch.duplicate_batches.length>0&&<section aria-label="相同文件已有结果"><h3>相同文件的已有批次（已发布优先）</h3>{batch.duplicate_batches.map(b=><p key={b.id}><a href={importBatchHref(b)}>{b.filename}（v{b.format_version} {b.mode} · {stateNames[b.state]}）</a></p>)}<p>第 {duplicatePage} 页 / 共 {batch.duplicate_total} 条</p><button disabled={duplicatePage<=1} onClick={()=>setDuplicatePage(n=>n-1)}>上一页相同文件</button><button disabled={duplicatePage*20>=batch.duplicate_total} onClick={()=>setDuplicatePage(n=>n+1)}>下一页相同文件</button></section>}
      <label>筛选本页预览与问题<input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="名称、记录键、来源备注或问题文字"/></label>
      <h3>逐项问题</h3><div id="import-issues" tabIndex={-1} className="dashboard-table-scroll"><table aria-label={`${title}导入问题`}><thead><tr><th>表 / 行</th><th>字段</th><th>级别</th><th>说明</th></tr></thead><tbody>{issues.map((i,n)=><tr key={i.id??n}><td>{i.sheet} / {i.row||'文件'} {batch.rows.some(r=>r.sheet===i.sheet&&r.row===i.row)&&<button onClick={()=>edit(batch.rows.find(r=>r.sheet===i.sheet&&r.row===i.row)!)}>定位问题</button>}</td><td>{labels[i.field]??i.field}</td><td>{i.severity==='ERROR'?'阻断':'需确认'}</td><td>{i.message}</td></tr>)}</tbody></table></div>
      {(isSites?['Customers','Sites']:['Customers','Sites','Materials','Assets']).map(sheet=><section key={sheet} aria-label={`${sheet}预览`}><h3>{sheet} · 全批新增 {batch.summary.by_kind?.[sheet]?.new_rows??rows.filter(r=>r.sheet===sheet&&r.values.decision==='NEW').length} / 引用 {batch.summary.by_kind?.[sheet]?.reference_rows??rows.filter(r=>r.sheet===sheet&&r.values.decision==='REFERENCE').length}</h3><div className="dashboard-table-scroll"><table aria-label={isSites?'现场导入记录':`${sheet}导入记录`}><thead><tr><th>表 / 行 / 记录键</th><th>名称 / 引用 / 上下文</th><th>处理决定</th><th>来源备注 / 原值与采用值</th><th>操作</th></tr></thead><tbody>{rows.filter(r=>r.sheet===sheet).map(r=><tr key={`${r.sheet}:${r.row}`}><td>{r.sheet} / {r.row} / {r.values.record_key}<br/>{r.system_asset_number}</td><td>{text(r.values.site_name??r.values.customer_name??r.values.serial_number??r.values.material_number)}<br/>{text(r.values.customer_ref??r.values.material_ref)}{r.resolved_context!=null&&<pre>{JSON.stringify(r.resolved_context,null,2)}</pre>}</td><td>{r.values.decision==='NEW'?'确认新增':r.values.decision==='REFERENCE'?'引用已有':'待决定'}</td><td className="site-import-note">{text(r.values.source_note)}<details><summary>查看原值与采用值</summary>{Object.keys({...r.original_values,...r.values}).map(k=><p key={k}>{labels[k]??k}：原始 {text(r.original_values[k])} / 采用 {text(r.values[k])}</p>)}</details></td><td>{batch.state!=='PUBLISHED'?<button disabled={busy} onClick={()=>edit(r)}>核对 {r.sheet} 第{r.row}行</button>:r.sheet==='Sites'?<a href={`/assets/sites/${r.target_id}?product_line=${String(r.values.product_lines).includes('PV')?'PV':'ESS'}&return_to=${encodeURIComponent(importBatchHref(batch))}`}>查看现场</a>:r.sheet==='Assets'?<a href={`/assets/equipment/${r.target_id}?return_to=${encodeURIComponent(importBatchHref(batch))}`}>查看设备</a>:r.sheet==='Materials'?<a href={`#material-${r.row}`}>物料 {r.target_key}</a>:r.target_id}</td></tr>)}</tbody></table></div>{sheet==='Materials'&&batch.state==='PUBLISHED'&&rows.filter(r=>r.sheet==='Materials').map(r=><div id={`material-${r.row}`} key={r.row}><p>物料 {r.target_key} · {text(r.values.model)} · {text(r.values.asset_type)}</p><ImportSourcesPanel kind="materials" id={r.target_key!}/></div>)}</section>)}
      <div className="table-paging"><span>共 {batch.total_rows} 行 · 第 {page} 页</span><button disabled={busy||page<=1} onClick={()=>setPage(n=>n-1)}>上一页预览</button><button disabled={busy||page*20>=batch.total_rows} onClick={()=>setPage(n=>n+1)}>下一页预览</button></div>
      {batch.state==='VALIDATED'&&<div className="site-import-warnings">{batch.issues.filter(i=>i.severity==='WARNING').map(i=><label key={i.id}><input type="checkbox" disabled={busy} checked={ack.includes(i.id!)} aria-label={i.code==='site_name_difference'?`确认警告：采用现场编号 ${batch.rows.find(r=>r.sheet===i.sheet&&r.row===i.row)?.values.site_id}；${i.message}`:i.code==='duplicate_serial'?`确认警告：确认另一台物理设备；${i.message}`:`确认警告：${i.message}`} onChange={e=>setAck(a=>e.target.checked?[...new Set([...a,i.id!])]:a.filter(id=>id!==i.id))}/>{i.message}</label>)}<p className="import-note">已确认 {ack.length} / {batch.summary.warning_count} 项。其他页的警告也须逐项核对；修改资料会清除确认。</p></div>}
      {!canPublish&&<p className="import-note">{retainedRevision?'请先查询或重试未确认原修订。':editing?'请保存或取消当前核对。':batch.state==='STAGED'?'等待后台校验完成。':batch.summary.error_count?'请先修正阻断问题。':batch.state==='VALIDATED'?'请逐项确认当前警告后发布。':'当前批次不可发布。'}</p>}{editing&&<p className="import-note">请先保存或取消当前核对，再发布。</p>}{batch.state!=='PUBLISHED'&&<button disabled={!canPublish||busy} onClick={()=>void mutate('publish')}>{isSites?'发布客户与现场':'发布设备与相关主数据'}</button>}
    </section>}
    {editing&&<section className="dashboard-table-panel" aria-label="核对编辑" id="import-review">
      <h2>核对 {editing.sheet} 第{editing.row}行</h2>
      {(revisionTerminal||batch?.state==='PUBLISHED')&&<p role="status">该批次已发布，保留输入供复制；不能再修订，请创建新批次。</p>}
      <section aria-label="候选资料与差异"><h3>候选资料与差异</h3><p className="import-note">名称只用于提示。点击候选后仍须保存核对；引用会保留正式属性，不能通过导入改客户归属。</p>{editing.candidates.length===0?<p>没有候选；请明确填写已有引用或确认新增。</p>:editing.candidates.map((c,n)=><article key={c.id??n} className="site-import-candidate"><strong>{c.site_name??c.customer_name??c.serial_number??c.material_number??c.record_key}</strong><p>编号：{c.id??c.material_number??`${c.sheet} ${c.row}`}<br/>客户：{text(c.customer_name)} · 型号：{text(c.model)} · 状态：{text(c.status)}</p>{c.location!=null&&<pre>{JSON.stringify(c.location,null,2)}</pre>}{c.lines?.map(line=><p key={line.product_line}>{line.product_line}：{text(line.power_mw)} MW {line.product_line==='ESS'?`${text(line.energy_mwh)} MWh`:''}</p>)}{c.kind==='ASSET'?<a href={`/assets/equipment/${c.id}`} target="_blank" rel="noreferrer">查看已有设备 {c.system_asset_number}</a>:c.kind==='BATCH_ASSET'?<p>同批设备，确认另一台物理设备后才能发布。</p>:<button disabled={busy} onClick={()=>setDraft(d=>editing.sheet==='Assets'?{...d,site_id:c.id??null,site_name:c.site_name??null}:editing.sheet==='Materials'?{...d,decision:'REFERENCE',material_number:c.material_number??null,model:c.model??null,asset_type:c.asset_type??null}:{...d,decision:'REFERENCE',[editing.sheet==='Sites'?'site_id':'customer_id']:c.id??null,...(c.customer_id?{customer_ref:c.customer_id}:{})})}>引用这个候选</button>}</article>)}</section>
      <form onSubmit={e=>{e.preventDefault();void mutate('revise');}}><div className="site-import-grid">{columns[editing.sheet].map(field=><label key={field}>{labels[field]}{field==='decision'?<select aria-label={labels[field]} value={String(draft[field]??'')} onChange={e=>setDraft(d=>({...d,[field]:e.target.value}))}><option value="">请选择</option><option value="NEW">确认新增不同实体</option>{editing.sheet!=='Assets'&&<option value="REFERENCE">明确引用已有编号</option>}</select>:field==='source_note'?<textarea aria-label={labels[field]} aria-invalid={!!fieldErrors[field]} aria-describedby={fieldErrors[field]?`import-review-${field}-error`:undefined} value={String(draft[field]??'')} onChange={e=>setDraft(d=>({...d,[field]:e.target.value||null}))}/>:<input aria-label={labels[field]} aria-invalid={!!fieldErrors[field]} aria-describedby={fieldErrors[field]?`import-review-${field}-error`:undefined} value={String(draft[field]??'')} onChange={e=>setDraft(d=>({...d,[field]:e.target.value||null}))}/>}{fieldErrors[field]&&<span role="alert" id={`import-review-${field}-error`}>{fieldErrors[field]}</span>}</label>)}</div><label>本次核对原因<textarea aria-label="本次核对原因" required aria-invalid={!!reasonError} aria-describedby={reasonError?'import-review-reason-error':undefined} value={reason} onChange={e=>setReason(e.target.value)}/>{reasonError&&<span role="alert" id="import-review-reason-error">{reasonError}</span>}</label><div className="site-import-actions"><button disabled={busy||!reason.trim()||!!revisionInputError||revisionTerminal||batch?.state==='PUBLISHED'} type="submit">保存核对并重新校验</button><button type="button" disabled={busy} onClick={()=>setEditing(null)}>取消编辑</button></div></form>
    </section>}
    {selected&&<section className="dashboard-table-panel"><h3>核对修订历史</h3>{revisions.error&&<p role="alert">{revisions.error}</p>}<div className="dashboard-table-scroll"><table aria-label="核对修订历史"><thead><tr><th>修订 / 表行</th><th>原因 / 操作人</th><th>原值</th><th>核对值</th></tr></thead><tbody>{revisions.data?.changes.map((r,n)=><tr key={n}><td>{r.revision} / {r.sheet} {r.row}</td><td>{r.reason}<br/>{r.display_name} · {new Date(r.occurred_at).toLocaleString()}</td><td>{Object.keys(r.after).filter(k=>JSON.stringify(r.after[k])!==JSON.stringify(r.before[k])).map(k=><p key={k}>{labels[k]??(k==='reason'?'核对原因':k)}：{text(r.before[k])}</p>)}</td><td>{Object.keys(r.after).filter(k=>JSON.stringify(r.after[k])!==JSON.stringify(r.before[k])).map(k=><p key={k}>{labels[k]??(k==='reason'?'核对原因':k)}：{text(r.after[k])}</p>)}</td></tr>)}</tbody></table></div><button disabled={revisionPage<=1} onClick={()=>setRevisionPage(n=>n-1)}>上一页修订</button><button disabled={!revisions.data||revisionPage*20>=revisions.data.total} onClick={()=>setRevisionPage(n=>n+1)}>下一页修订</button></section>}
    <section className="dashboard-table-panel" aria-label={`${title}批次历史`}><h2>批次历史</h2><label>搜索批次文件名或编号<input value={search} onChange={e=>{setSearch(e.target.value);setHistoryPage(1);}}/></label>{history.error&&<p role="alert">{history.error}</p>}{!history.data&&!history.error&&<p>正在读取批次历史…</p>}{history.data?.total===0&&<p>没有符合条件的批次。</p>}<div className="dashboard-table-scroll"><table><thead><tr><th>文件名</th><th>格式</th><th>状态</th></tr></thead><tbody>{history.data?.batches.map(b=><tr key={b.id}><td><a href={importBatchHref(b)}>{b.filename}</a></td><td>v{b.format_version}</td><td>{stateNames[b.state]}</td></tr>)}</tbody></table></div><button disabled={historyPage<=1} onClick={()=>setHistoryPage(n=>n-1)}>上一页批次</button><button disabled={!history.data||historyPage*20>=history.data.total} onClick={()=>setHistoryPage(n=>n+1)}>下一页批次</button></section>
  </div>;
}
