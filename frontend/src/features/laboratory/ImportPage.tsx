import {useCallback,useEffect,useRef,useState,type FormEvent} from 'react';
import {useAuth} from '../../Auth';
import {ImportError,importRoot,readImport,sendImport,uploadOriginal} from './importApi';
import {fileMetadata,forgetIntent,loadIntent,prepareIntent,retainIntent,sameOriginal,type ImportIntent} from './importIntent';
import type {Batch,CreateInput,FileRole,InputFormat,Operation,OriginalFile,Page,Purpose,Revision,SourceDecision,SourcePage} from './importTypes';
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
function Pager({page,total,label,onPage}:{page:number;total:number;label:string;onPage:(n:number)=>void}){
  return <div className="lab-import-pager" aria-label={label+'分页'}><button type="button" disabled={page===1} onClick={()=>onPage(page-1)}>上一页{label}</button><span>第 {page} 页 · 共 {total} 项</span><button type="button" disabled={page*20>=total} onClick={()=>onPage(page+1)}>下一页{label}</button></div>;
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
    const version=++detailRequest.current;setLoading(true);
    try{
      const [value,f,r]=await Promise.all([readImport<Batch>('/'+id),readImport<Page<OriginalFile>>('/'+id+'/files?page='+fp),readImport<Page<Revision>>('/'+id+'/revisions?page='+rp)]);
      if(!mounted.current||version!==detailRequest.current)return;
      setBatch(value);setBatchId(id);setFiles(f);setHistory(r);setFilePage(fp);setRevisionPage(rp);
      setReviewPurpose(value.purpose);setReviewZone(value.source_timezone??'');setReviewConfirmed(value.source_timezone_confirmed);
      const url=new URL(location.href);url.searchParams.set('batch',id);window.history.replaceState(null,'',url);
    }catch(e){if(mounted.current&&version===detailRequest.current)setError(text(e));}
    finally{if(mounted.current&&version===detailRequest.current)setLoading(false);}
  },[]);
  const finish=useCallback(async(op:Operation,owner:symbol)=>{
    if(!mounted.current||flight.current!==owner)return;
    setOperation(op);
    if(op.state==='COMPLETED'){
      forgetIntent(actor);remember(null);
      setMessage(op.action==='RECEIVE'?'原件已确认保存。收件结果与当前批次版本分别显示。':'请求已确认保存。');
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
    if(!retained.current||operation?.state!=='REJECTED')return;
    await owned(async owner=>{
      try{
        forgetIntent(actor);remember(null);setOperation(null);setError('');
        setMessage('原拒绝结果已保留在操作历史；请核对最新资料后再保存。');
        if(batchId&&flight.current===owner)await open(batchId);
      }catch(e){if(flight.current===owner)setError(text(e));}
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
      <h2>恢复原请求</h2><p>类型：{intent.action==='CREATE'?'创建批次':intent.action==='RECEIVE'?'保存原件':'保存核对'}。保留原 key 和原请求，不会自动重复创建。</p>
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
      <button disabled={locked} onClick={()=>{detailRequest.current++;setBatch(null);setBatchId('');setSelected({});setDecisions([]);setReviewDecisions([]);setReviewReason('');const u=new URL(location.href);u.searchParams.delete('batch');window.history.replaceState(null,'',u);}}>准备另一批次</button>
      <section aria-label="当前采用的原件"><h3>当前采用的原件</h3>{batch.active_files?.length?<ul>{batch.active_files.map(f=><li key={f.id}>{labels[f.role]}：{f.filename} · {f.byte_size} 字节 · 已确认保存</li>)}</ul>:<p>尚未选择已确认的原件。</p>}</section>
      <div className="lab-import-upload">{roles.map(role=><fieldset key={role} disabled={busy||(!!intent&&!(intent.action==='RECEIVE'&&intent.payload.role===role))}>
        <legend>{labels[role]}原件</legend><label>选择{labels[role]}原件<input type="file" accept={role==='WORKBOOK'?'.xlsx':'.csv'} onChange={e=>setSelected(old=>({...old,[role]:e.target.files?.[0]}))}/></label>
        <button disabled={locked||!selected[role]} onClick={()=>void upload(role)}>保存{labels[role]}原件</button>
      </fieldset>)}</div>
      {progress!==null&&<div role="status"><progress max={100} value={progress}/><p>原件字节已发送 {progress}%{progress===100?'，正在等待服务器确认收件。':'。此进度不代表已保存。'}</p></div>}
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
      <section aria-label="暂存修订历史"><h3>暂存修订历史</h3>{history&&<><table><thead><tr><th>版本</th><th>核对者与时间</th><th>原因</th></tr></thead><tbody>{history.items.map(r=><tr key={r.id}><td>{r.revision}</td><td>{r.display_name}<small>{time(r.occurred_at)}</small></td><td>{r.reason}<details><summary>查看此修订的前后资料</summary><h4>修订前</h4><RevisionSnapshot value={r.before_value}/><h4>修订后</h4><RevisionSnapshot value={r.after_value}/></details></td></tr>)}</tbody></table>{history.total===0&&<p>暂无修订。</p>}<Pager page={revisionPage} total={history.total} label="修订" onPage={p=>void open(batch.id,filePage,p)}/></>}</section>
    </section>}
    <section className="panel" aria-label="暂存批次历史"><h2>暂存批次历史</h2><form onSubmit={e=>{e.preventDefault();setListPage(1);void refreshList();}}><div className="lab-import-grid">
      <label>批次 ID 或原文件名<input value={filter.q} onChange={e=>{setFilter(v=>({...v,q:e.target.value}));setListPage(1);}}/></label>
      <label>历史用途<select value={filter.purpose} onChange={e=>{setFilter(v=>({...v,purpose:e.target.value}));setListPage(1);}}><option value="">全部</option><option value="HISTORICAL">历史资料</option><option value="DAILY">日常检测资料</option></select></label>
      <label>创建日期从（UTC）<input type="date" value={filter.created_from} onChange={e=>{setFilter(v=>({...v,created_from:e.target.value}));setListPage(1);}}/></label>
      <label>创建日期至（UTC）<input type="date" value={filter.created_to} onChange={e=>{setFilter(v=>({...v,created_to:e.target.value}));setListPage(1);}}/></label>
      <label>操作人员 ID<input value={filter.actor_id} onChange={e=>{setFilter(v=>({...v,actor_id:e.target.value}));setListPage(1);}}/></label>
      <label>来源实验室稳定 ID<input value={filter.source_lab_id} onChange={e=>{setFilter(v=>({...v,source_lab_id:e.target.value}));setListPage(1);}}/></label>
    </div><button type="submit">刷新批次历史</button></form>
      {batches?<><table><thead><tr><th>批次</th><th>用途与格式</th><th>版本与状态</th><th>创建时间</th></tr></thead><tbody>{batches.items.map(b=><tr key={b.id}><td><a href={'/lab/imports?batch='+b.id} onClick={e=>{e.preventDefault();void open(b.id);}}><code>{b.id}</code></a></td><td>{purposeLabel[b.purpose]} · {b.input_format}</td><td>{b.revision} · 仅暂存</td><td>{time(b.created_at)}</td></tr>)}</tbody></table>{batches.total===0&&<p>没有符合条件的暂存批次。</p>}<Pager page={listPage} total={batches.total} label="批次" onPage={setListPage}/></>:<p role="status">正在读取批次历史…</p>}
    </section>
  </div>;
}










