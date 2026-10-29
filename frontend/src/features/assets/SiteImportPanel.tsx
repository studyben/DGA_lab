import {importPayloadDigest,newImportIntentKey} from './siteImportIntent';
import {importFieldLabels as labels} from './siteImportPresentation';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import { useRead } from './assetUi';
import { SiteExportButton } from './SiteExportButton';
import './siteImport.css';

type Values = Record<string, string | number | null>;
type Candidate = { id: string; site_name?: string; customer_name?: string; customer_id?: string; location_text?: string; lines?: {product_line:string;power_mw:string|null;energy_mwh:string|null}[] };
type Row = {sheet:'Customers'|'Sites';row:number;values:Values;original_values:Values;candidates:Candidate[];target_id?:string};
type Issue = {id?:string;code:string;sheet:string;row:number;field:string;severity:'WARNING'|'ERROR';message:string};
type Batch = {id:string;format_version:number;state:'STAGED'|'VALIDATED'|'PUBLISHED'|'FAILED';filename:string;validation_revision:number;page:number;total_rows:number;rows:Row[];issues:Issue[];summary:{total_rows:number;error_count:number;warning_count:number};duplicate_batches:{id:string;filename:string;state:string}[]};
type History = {batches:{id:string;filename:string;format_version:number;state:string}[];total:number;page:number};
type RevisionHistory = {changes:{revision:number;reason:string;sheet:string;row:number;before:Values;after:Values;display_name:string;occurred_at:string}[];total:number};
type Pending = {key:string;kind:'upload'|'revise'|'publish';digest:string;batch?:string};
const root='/api/assets/imports';

const columns={Customers:['record_key','decision','customer_id','customer_name','source_note'],Sites:['record_key','decision','site_id','site_name','customer_ref','location_text','product_lines','pv_power_mw','ess_power_mw','ess_energy_mwh','commissioning_date','grid_status','operation_status','source_note']};
const stateNames:Record<string,string>={STAGED:'待后台校验',VALIDATED:'待核对 / 可提交',FAILED:'文件或校验失败',PUBLISHED:'已整批发布'};
const messages:Record<string,string>={import_has_errors:'还有阻断问题，请先逐行核对。',import_warnings_unacknowledged:'请逐项确认全部警告，可切换预览页继续核对。',import_stale_validation:'预览已变化，请重新加载并核对。',import_operation_conflict:'操作键与原请求内容不同，请先查询原操作结果。',object_storage_unavailable:'原文件服务暂不可用，结果未确认；请查询原操作后重试。',import_submit_unavailable:'上传结果未确认，请先查询原操作。',import_revision_unavailable:'核对结果未确认，请先查询原操作。',import_publish_unavailable:'发布结果未确认，请先查询原操作。',permission_denied:'当前账号没有此操作权限。',session_expired:'登录已失效，请重新登录后查询原操作。',csrf_rejected:'会话已更新，请刷新页面后查询原操作。',invalid_import_revision:'核对内容不符合格式，请检查字段和原因。',import_already_published:'批次已发布，不能继续修改。'};
const text=(v:unknown)=>v==null?'未提供':String(v);
async function errorMessage(response:Response) {const body=await response.json().catch(()=>({}));return messages[body.code]??`操作未成功（${response.status}），请检查输入或重新读取批次。`;}

export function SiteImportPanel() {
  const {session}=useAuth();
  const [selected,setSelected]=useState(()=>new URLSearchParams(location.search).get('batch')??'');
  const [batch,setBatch]=useState<Batch|null>(null);
  const [page,setPage]=useState(1),[historyPage,setHistoryPage]=useState(1),[revisionPage,setRevisionPage]=useState(1);
  const [refresh,setRefresh]=useState(0),[search,setSearch]=useState(''),[filter,setFilter]=useState('');
  const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState('');
  const [ack,setAck]=useState<string[]>([]),[editing,setEditing]=useState<Row|null>(null),[draft,setDraft]=useState<Values>({}),[reason,setReason]=useState('');
  const seen=useRef(''), lock=useRef(false),alert=useRef<HTMLDivElement>(null);
  const history=useRead<History>(`${root}?query=${encodeURIComponent(search)}&page=${historyPage}&refresh=${refresh}`);
  const revisions=useRead<RevisionHistory>(selected?`${root}/${selected}/revisions?page=${revisionPage}&refresh=${refresh}`:null);
  const storageKey=`dga-site-import-pending:${session?.actor.id??'anonymous'}`;
  const readPending=():Pending|null=>{const raw=sessionStorage.getItem(storageKey);return raw?JSON.parse(raw):null;};

  function choose(id:string) {setSelected(id);setPage(1);setEditing(null);setError('');setAck([]);setRevisionPage(1);setRefresh(n=>n+1);historyReplace(id);}
  function historyReplace(id:string) {window.history.replaceState(null,'','/assets/import?mode=SITES'+(id?`&batch=${encodeURIComponent(id)}`:''));}
  useEffect(()=>{if(error){alert.current?.focus();alert.current?.scrollIntoView({block:'nearest'});}},[error]);
  useEffect(()=>{
    if(!selected){setBatch(null);return;}
    let active=true;let timer:ReturnType<typeof setTimeout>|undefined;const controller=new AbortController();
    async function load(){try{
      const response=await fetch(`${root}/${selected}?page=${page}`,{cache:'no-store',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
      if(!response.ok)throw new Error(await errorMessage(response));
      const value:Batch=await response.json();if(!active)return;
      if(value.format_version!==2){location.assign(`/assets/import?batch=${value.id}`);return;}
      const revision=`${value.id}:${value.validation_revision}`;if(seen.current!==revision){setAck([]);seen.current=revision;}
      setBatch(value);if(value.state==='STAGED')timer=setTimeout(()=>void load(),1500);
    }catch(e){if(active)setError(e instanceof Error?e.message:'无法读取批次。');}}
    void load();return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[selected,page,refresh]);

  async function recover():Promise<boolean> {
    const pending=readPending();if(!pending)return false;
    const response=await fetch(`${root}/operations/${pending.key}`,{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(response.status===404){setNotice('此操作暂未查到完成记录；请保留原输入并使用原操作重试。');return false;}
    if(!response.ok)throw new Error(await errorMessage(response));
    const result=await response.json();sessionStorage.removeItem(storageKey);choose(result.batch_id);
    setNotice(result.outcome==='PUBLISHED'?'客户与现场已整批发布。':result.outcome==='REFRESHED'?'原操作已刷新预览，请重新核对。':'已找到原操作结果，正在读取批次。');return true;
  }
  async function mutate(kind:Pending['kind']) {
    if(lock.current||!session||(kind==='upload'?!file:!batch))return;
    lock.current=true;setBusy(true);setError('');setNotice('');
    try{
      if(kind==='upload'&&file!.size>10*1024*1024)throw new Error('现场文件不得超过10 MiB，请分批。');
      const payload=kind==='upload'?undefined:kind==='revise'?{expected_revision:batch!.validation_revision,changes:[{sheet:editing!.sheet,row:editing!.row,values:{...draft,reason:reason.trim()}}],reason:reason.trim()}:{validation_revision:batch!.validation_revision,acknowledged_warning_ids:[...ack].sort()};
      const bytes=kind==='upload'?await file!.arrayBuffer():new TextEncoder().encode(JSON.stringify(payload));
      const signature=importPayloadDigest(bytes)+(kind==='upload'?`:${file!.name}`:'');
      let pending=readPending();
      if(pending){if(await recover())return;if(pending.kind!==kind||pending.digest!==signature||pending.batch!==(kind==='upload'?undefined:batch!.id))throw new Error('仍有未确认操作。请先查询结果，或恢复原文件／原核对输入后重试。');}
      else {pending={key:newImportIntentKey(),kind,digest:signature,batch:kind==='upload'?undefined:batch!.id};sessionStorage.setItem(storageKey,JSON.stringify(pending));}
      const response=await fetch(kind==='upload'?`${root}?format_version=2&mode=SITES&filename=${encodeURIComponent(file!.name)}`:`${root}/${batch!.id}/${kind==='revise'?'revisions':'publish'}`,{
        method:'POST',credentials:'same-origin',signal:AbortSignal.timeout(45000),headers:{'X-CSRF-Token':session.csrf_token,'Content-Type':kind==='upload'?'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':'application/json','Idempotency-Key':pending.key},body:kind==='upload'?file:JSON.stringify({...payload,idempotency_key:pending.key})});
      if(!response.ok){if(response.status<500&&![401,403].includes(response.status))sessionStorage.removeItem(storageKey);throw new Error(await errorMessage(response));}
      const result:Batch=await response.json();sessionStorage.removeItem(storageKey);choose(result.id);setBatch(result);
      setNotice(kind==='upload'?'现场文件已接收，等待后台校验。':kind==='revise'?'核对已保存，预览已更新，请重新确认警告。':result.state==='PUBLISHED'?'客户与现场已整批发布。':'正式资料已变化，预览已刷新，尚未发布；请重新核对。');
    }catch(e){setError(e instanceof TypeError?'连接中断，结果尚未确认，请查询原操作；不要重新创建上传。':e instanceof Error&&e.name!=='TimeoutError'?e.message:'响应超时，结果尚未确认，请查询原操作；不要重新创建上传。');}
    finally{lock.current=false;setBusy(false);}
  }
  function edit(row:Row){setEditing(row);setDraft({...row.values});setReason('');setError('');}
  const matching=(row:unknown)=>JSON.stringify(row).toLocaleLowerCase().includes(filter.toLocaleLowerCase());
  const rows=batch?.rows.filter(matching)??[],issues=batch?.issues.filter(matching)??[];
  const canPublish=!editing&&batch?.state==='VALIDATED'&&batch.summary.error_count===0&&ack.length>=batch.summary.warning_count;
  return <div className="asset-dashboard site-import">
    <SiteExportButton/>
    <section className="dashboard-table-panel" aria-label="仅现场导入">
      <div className="table-toolbar"><h2>仅导入现场信息</h2><a className="button" href={`${root}/template?format_version=2&mode=SITES`}>下载 v2 现场模板</a></div>
      <p>客户与现场分表填写，客户可引用已有编号或同批新增。现场可以没有设备；已有资料只引用，差异需明确核对。</p>
      <p className="import-note">每表最多500条 · XLSX不超过10 MiB · 来源备注最多2000字符 · 编号使用文本，未知容量留空</p>
      <label>选择现场 Excel 文件<input type="file" accept=".xlsx" disabled={busy} onChange={e=>{setFile(e.target.files?.[0]??null);choose('');}}/></label>
      <div className="site-import-actions"><button disabled={!file||busy} onClick={()=>void mutate('upload')}>上传现场文件并校验</button><button disabled={busy} onClick={()=>{setError('');void recover().then(found=>{if(!found)setNotice('未找到已完成的未确认操作；可使用原输入重试。');}).catch(e=>setError(String(e.message)));}}>查询未确认操作</button></div>
    </section>
    {error&&<div className="import-error" role="alert" tabIndex={-1} ref={alert}>{error}<button disabled={busy} onClick={()=>{setError('');setRefresh(n=>n+1);}}>重新读取批次</button></div>}
    {busy&&<p role="status">正在处理，请稍候；原文件与操作记录会保留。</p>}{notice&&<p role="status">{notice}</p>}
    {selected&&!batch&&<p>正在读取现场批次…</p>}
    {batch&&<section className="dashboard-table-panel" aria-label="现场导入预览">
      <div className="table-toolbar"><h2>{batch.filename}</h2><span>{stateNames[batch.state]}</span><a className="button" href={`${root}/${batch.id}/source`}>下载原始上传文件</a></div>
      <p className="import-note">批次 {batch.id} · 核对修订 {batch.validation_revision} · 总行数 {batch.summary.total_rows} · 阻断 {batch.summary.error_count} · 警告 {batch.summary.warning_count}</p>
      {batch.state==='STAGED'&&<p>后台正在校验，页面将自动更新；无需重复上传。</p>}
      {batch.duplicate_batches.length>0&&<p>相同文件的已有批次：{batch.duplicate_batches.map(b=><a key={b.id} href={`/assets/import?mode=SITES&batch=${b.id}`}>{b.filename}（{stateNames[b.state]}） </a>)}</p>}
      <label>筛选本页预览与问题<input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="名称、记录键、来源备注或问题文字"/></label>
      <h3>逐项问题</h3><div className="dashboard-table-scroll"><table aria-label="现场导入问题"><thead><tr><th>表 / 行</th><th>字段</th><th>级别</th><th>说明</th></tr></thead><tbody>{issues.map((i,n)=><tr key={i.id??n}><td>{i.sheet} / {i.row||'文件'}</td><td>{labels[i.field]??i.field}</td><td>{i.severity==='ERROR'?'阻断':'需确认'}</td><td>{i.message}</td></tr>)}</tbody></table></div>
      <h3>客户与现场预览</h3><div className="dashboard-table-scroll"><table aria-label="现场导入记录"><thead><tr><th>表 / 行 / 记录键</th><th>名称 / 客户引用</th><th>处理决定</th><th>来源备注</th><th>操作</th></tr></thead><tbody>{rows.map(r=><tr key={`${r.sheet}:${r.row}`}><td>{r.sheet} / {r.row} / {r.values.record_key}</td><td>{text(r.values.site_name??r.values.customer_name)}<br/>{text(r.values.customer_ref)}</td><td>{r.values.decision==='NEW'?'确认新增':r.values.decision==='REFERENCE'?'引用已有':'待决定'}</td><td className="site-import-note">{text(r.values.source_note)}</td><td>{batch.state!=='PUBLISHED'?<button disabled={busy} onClick={()=>edit(r)}>核对 {r.sheet} 第{r.row}行</button>:r.sheet==='Sites'?<a href={`/assets/sites/${r.target_id}?product_line=${String(r.values.product_lines).includes('PV')?'PV':'ESS'}&return_to=${encodeURIComponent(`/assets/import?mode=SITES&batch=${batch.id}`)}`}>查看现场</a>:r.target_id}</td></tr>)}</tbody></table></div>
      <div className="table-paging"><span>共 {batch.total_rows} 行 · 第 {page} 页</span><button disabled={busy||page<=1} onClick={()=>setPage(n=>n-1)}>上一页预览</button><button disabled={busy||page*20>=batch.total_rows} onClick={()=>setPage(n=>n+1)}>下一页预览</button></div>
      {batch.state==='VALIDATED'&&<div className="site-import-warnings">{batch.issues.filter(i=>i.severity==='WARNING').map(i=><label key={i.id}><input type="checkbox" disabled={busy} checked={ack.includes(i.id!)} aria-label={`确认警告：${i.message}`} onChange={e=>setAck(a=>e.target.checked?[...new Set([...a,i.id!])]:a.filter(id=>id!==i.id))}/>{i.message}</label>)}<p className="import-note">已确认 {ack.length} / {batch.summary.warning_count} 项。其他页的警告也须逐项核对；修改资料会清除确认。</p></div>}
      {editing&&<p className="import-note">请先保存或取消当前核对，再发布。</p>}{batch.state!=='PUBLISHED'&&<button disabled={!canPublish||busy} onClick={()=>void mutate('publish')}>发布客户与现场</button>}
    </section>}
    {editing&&<section className="dashboard-table-panel" aria-label="核对编辑">
      <h2>核对 {editing.sheet} 第{editing.row}行</h2>
      <section aria-label="候选资料与差异"><h3>候选资料与差异</h3><p className="import-note">名称只用于提示。点击候选后仍须保存核对；引用会保留正式属性，不能通过导入改客户归属。</p>{editing.candidates.length===0?<p>没有同名候选；可填写已有正式编号，或明确确认新增。</p>:editing.candidates.map(c=><article key={c.id} className="site-import-candidate"><strong>{c.site_name??c.customer_name}</strong><p>编号：{c.id}<br/>客户：{text(c.customer_name)} · 位置：{text(c.location_text)}</p>{c.lines?.map(line=><p key={line.product_line}>{line.product_line}：{text(line.power_mw)} MW {line.product_line==='ESS'?`${text(line.energy_mwh)} MWh`:''}</p>)}<button disabled={busy} onClick={()=>setDraft(d=>({...d,decision:'REFERENCE',[editing.sheet==='Sites'?'site_id':'customer_id']:c.id,...(c.customer_id?{customer_ref:c.customer_id}:{})}))}>引用这个候选</button></article>)}</section>
      <form onSubmit={e=>{e.preventDefault();void mutate('revise');}}><div className="site-import-grid">{columns[editing.sheet].map(field=><label key={field}>{labels[field]}{field==='decision'?<select value={String(draft[field]??'')} onChange={e=>setDraft(d=>({...d,[field]:e.target.value}))}><option value="">请选择</option><option value="NEW">确认新增不同实体</option><option value="REFERENCE">明确引用已有编号</option></select>:field==='source_note'?<textarea aria-label={labels[field]} maxLength={2000} value={String(draft[field]??'')} onChange={e=>setDraft(d=>({...d,[field]:e.target.value||null}))}/>:<input aria-label={labels[field]} value={String(draft[field]??'')} maxLength={2000} onChange={e=>setDraft(d=>({...d,[field]:e.target.value||null}))}/>}</label>)}</div><label>本次核对原因<textarea aria-label="本次核对原因" required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><div className="site-import-actions"><button disabled={busy||!reason.trim()} type="submit">保存核对并重新校验</button><button type="button" disabled={busy} onClick={()=>setEditing(null)}>取消编辑</button></div></form>
    </section>}
    {selected&&<section className="dashboard-table-panel"><h3>核对修订历史</h3>{revisions.error&&<p role="alert">{revisions.error}</p>}<div className="dashboard-table-scroll"><table aria-label="核对修订历史"><thead><tr><th>修订 / 表行</th><th>原因 / 操作人</th><th>原值</th><th>核对值</th></tr></thead><tbody>{revisions.data?.changes.map((r,n)=><tr key={n}><td>{r.revision} / {r.sheet} {r.row}</td><td>{r.reason}<br/>{r.display_name} · {new Date(r.occurred_at).toLocaleString()}</td><td>{Object.keys(r.after).filter(k=>JSON.stringify(r.after[k])!==JSON.stringify(r.before[k])).map(k=><p key={k}>{labels[k]??(k==='reason'?'核对原因':k)}：{text(r.before[k])}</p>)}</td><td>{Object.keys(r.after).filter(k=>JSON.stringify(r.after[k])!==JSON.stringify(r.before[k])).map(k=><p key={k}>{labels[k]??(k==='reason'?'核对原因':k)}：{text(r.after[k])}</p>)}</td></tr>)}</tbody></table></div><button disabled={revisionPage<=1} onClick={()=>setRevisionPage(n=>n-1)}>上一页修订</button><button disabled={!revisions.data||revisionPage*20>=revisions.data.total} onClick={()=>setRevisionPage(n=>n+1)}>下一页修订</button></section>}
    <section className="dashboard-table-panel" aria-label="现场批次历史"><h2>批次历史</h2><label>搜索批次文件名或编号<input value={search} onChange={e=>{setSearch(e.target.value);setHistoryPage(1);}}/></label>{history.error&&<p role="alert">{history.error}</p>}{!history.data&&!history.error&&<p>正在读取批次历史…</p>}{history.data?.total===0&&<p>没有符合条件的批次。</p>}<div className="dashboard-table-scroll"><table><thead><tr><th>文件名</th><th>格式</th><th>状态</th></tr></thead><tbody>{history.data?.batches.map(b=><tr key={b.id}><td><a href={`/assets/import?${b.format_version===2?'mode=SITES&':''}batch=${b.id}`}>{b.filename}</a></td><td>v{b.format_version}</td><td>{stateNames[b.state]}</td></tr>)}</tbody></table></div><button disabled={historyPage<=1} onClick={()=>setHistoryPage(n=>n-1)}>上一页批次</button><button disabled={!history.data||historyPage*20>=history.data.total} onClick={()=>setHistoryPage(n=>n+1)}>下一页批次</button></section>
  </div>;
}
