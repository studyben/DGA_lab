import { useEffect, useState } from 'react';
import { useAuth } from '../../Auth';
import './operations.css';

export const sampleStates: Record<string, string> = { IDENTITY_PENDING: '身份待确认', RECEIVED: '已收样', DETECTING: '检测中', COMPLETED: '检测完成', REPORTED: '已报告' };
export const chicagoTime = (value: string) => new Date(value).toLocaleString('zh-CN', { timeZone: 'America/Chicago', hour12: false });
type SampleRow = { id: string; barcode_value: string; sample_number: string; site_name: string; equipment_serial: string; state: string; created_at: string; received_at: string; sampled_at: string; test_types: string[] };
type Ledger = { samples: SampleRow[]; total: number; page: number; page_size: number };
type Dashboard = { metrics: Record<string, number>; business_date: string; as_of: string; recent_samples: SampleRow[] };

export function useLaboratoryRead<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setData(null); setError('');
    void fetch(url, { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) }).then(async response => {
      if (!response.ok) throw new Error(response.status === 401 ? '登录已失效，请重新登录。' : response.status === 422 ? '筛选条件无效，请重置后重试。' : '无法读取实验室数据，请检查权限或稍后重试。');
      const value: T = await response.json();
      if (active) setData(value);
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : '无法读取数据。'); });
    return () => { active = false; controller.abort(); };
  }, [url, revision]);
  return { data, error, retry: () => setRevision(n => n + 1) };
}

const metrics = [
  ['detecting_samples', '检测中油样', '已新增有效检测且尚未整体定稿，含身份待确认油样'],
  ['tests_created_today', '今日检测数量', '今日实际新增的检测记录，含随后移除的记录，不按检测时间回填'],
  ['samples_created_today', '今日创建数量', '今日登记创建的油样，不按收样时间回填'],
  ['samples_created_total', '总创建数量', '所有已创建并保留的油样'],
];

export function LaboratoryHomePage() {
  const { can } = useAuth();
  const read = useLaboratoryRead<Dashboard>('/api/laboratory/dashboard');
  const [barcode, setBarcode] = useState('');
  return <div className="lab-operations">
    {read.error && <p role="alert">{read.error}<button onClick={read.retry}>重试</button></p>}
    {!read.data && !read.error && <p role="status">正在读取实验室概览…</p>}
    {read.data && <><p>业务日期 {read.data.business_date} · America/Chicago · 截至 {chicagoTime(read.data.as_of)}</p>
      <section className="lab-metrics" aria-label="实验室指标">{metrics.map(([key, title, explanation]) => <article key={key}><h2>{title}</h2><strong>{read.data!.metrics[key]}</strong><p>{explanation}</p></article>)}</section>
      <section className="lab-panel"><div className="lab-toolbar"><h2>开始工作</h2><a href="/lab/samples">查看油样台账</a>{can('laboratory.write') && <a href="/lab/reception">新建油样</a>}</div>
        {can('laboratory.write') && <form className="lab-toolbar" onSubmit={e => { e.preventDefault(); if (barcode.trim()) location.assign('/lab/workbench?barcode='+encodeURIComponent(barcode.trim())); }}><label>扫描或输入条码<input value={barcode} maxLength={40} onChange={e => setBarcode(e.target.value)} /></label><button disabled={!barcode.trim()}>继续检测</button></form>}
      </section>
      <section className="lab-panel"><h2>最近油样</h2><ul>{read.data.recent_samples.map(s => <li key={s.id}><a href={can('laboratory.write') ? '/lab/workbench?barcode='+encodeURIComponent(s.barcode_value) : '/lab/samples?barcode='+encodeURIComponent(s.barcode_value)}>{s.barcode_value}</a> · {s.site_name} · {sampleStates[s.state]}</li>)}</ul>{!read.data.recent_samples.length && <p>尚未创建油样。</p>}</section></>}
  </div>;
}

const textFilters = [['barcode', '条码筛选'], ['sample_number', '样品号'], ['site', '现场'], ['serial', '设备序列号']] as const;
const columns = [['sample_number','油样编号'], ['site_name','现场'], ['equipment_serial','设备序列号'], ['state','状态'], ['created_at','创建时间'], ['received_at','收样时间'], ['sampled_at','采样时间'], ['test_types','检测类型']] as const;
const testLabels: Record<string,string> = { DGA: 'DGA', MOISTURE: '微水', BREAKDOWN_VOLTAGE: '击穿电压' };

export function SampleLedgerPage({ pending = false, onChoose, onInspect }: { pending?: boolean; onChoose?: (barcode: string) => void; onInspect?: (barcode: string) => void }) {
  const { can } = useAuth();
  const initial = () => Object.fromEntries(new URLSearchParams(location.search));
  const [query, setQuery] = useState<Record<string,string>>(initial);
  const [draft, setDraft] = useState<Record<string,string>>(initial);
  const [hidden, setHidden] = useState<string[]>([]);
  const effective = Object.fromEntries(Object.entries({ ...query, ...(pending ? { state: 'IDENTITY_PENDING' } : {}) }).filter(([,value]) => value !== ''));
  const read = useLaboratoryRead<Ledger>('/api/laboratory/ledger?'+new URLSearchParams(effective));
  function apply(values: Record<string,string>) {
    setQuery(values); setDraft(values);
    history.replaceState(null, '', location.pathname+'?'+new URLSearchParams(values));
  }
  const link = (s: SampleRow) => '/lab/workbench?barcode='+encodeURIComponent(s.barcode_value)+'&return_to='+encodeURIComponent(location.pathname+location.search);
  return <div className="lab-operations"><section className="lab-panel">
    <h2>{pending ? '身份待确认油样' : '油样台账'}</h2>
    <form className="lab-filters" onSubmit={e => { e.preventDefault(); apply({ ...draft, page:'1' }); }}>
      {textFilters.map(([key,label]) => <label key={key}>{label}<input maxLength={key==='site'?200:160} value={draft[key]??''} onChange={e=>setDraft({...draft,[key]:e.target.value})} /></label>)}
      {!pending && <label>状态筛选<select value={draft.state??''} onChange={e=>setDraft({...draft,state:e.target.value})}><option value="">全部</option>{Object.entries(sampleStates).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>}
      <label>检测类型筛选<select value={draft.test_type??''} onChange={e=>setDraft({...draft,test_type:e.target.value})}><option value="">全部</option>{Object.entries(testLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>日期口径<select value={draft.date_field??'created_at'} onChange={e=>setDraft({...draft,date_field:e.target.value})}>{columns.filter(([k])=>k.endsWith('_at')).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>开始日期<input type="date" value={draft.start_date??''} onChange={e=>setDraft({...draft,start_date:e.target.value})}/></label><label>结束日期<input type="date" value={draft.end_date??''} onChange={e=>setDraft({...draft,end_date:e.target.value})}/></label>
      <label>排序字段<select value={draft.sort??'created_at'} onChange={e=>setDraft({...draft,sort:e.target.value})}>{columns.filter(([k])=>['created_at','received_at','sampled_at','sample_number','site_name'].includes(k)).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>排序方向<select value={draft.direction??'desc'} onChange={e=>setDraft({...draft,direction:e.target.value})}><option value="desc">降序</option><option value="asc">升序</option></select></label>
      <div className="lab-toolbar"><button>应用筛选</button><button type="button" onClick={()=>apply({})}>重置筛选</button></div>
    </form><p>日期按 America/Chicago 统计和显示，结束日期包含当日。</p>
    <details><summary>显示列</summary>{columns.map(([key,label])=><label className="lab-column-choice" key={key}><input type="checkbox" checked={!hidden.includes(key)} onChange={()=>setHidden(hidden.includes(key)?hidden.filter(k=>k!==key):[...hidden,key])}/>{label}</label>)}</details>
    {read.error && <p role="alert">{read.error}<button onClick={read.retry}>重试</button></p>}
    {!read.data && !read.error && <p role="status">正在读取油样…</p>}
    {read.data && <><p>共 {read.data.total} 条</p><div className="lab-table-scroll"><table aria-label="油样台账"><thead><tr><th>条码</th>{columns.filter(([key])=>!hidden.includes(key)).map(([key,label])=><th key={key}>{label}</th>)}{onInspect && <th>运营信息</th>}</tr></thead><tbody>{read.data.samples.map(s=><tr key={s.id}><td>{can('laboratory.write')?(onChoose ? <button onClick={()=>onChoose(s.barcode_value)} aria-label={'核实 '+s.barcode_value}>{s.barcode_value}</button> : <a href={link(s)}>{s.barcode_value}</a>):s.barcode_value}</td>{columns.filter(([key])=>!hidden.includes(key)).map(([key])=><td key={key}>{key==='state'?sampleStates[s.state]:key==='test_types'?s.test_types.map(t=>testLabels[t]).join('、'):key.endsWith('_at')?chicagoTime(String(s[key])):s[key]}</td>)}{onInspect && <td><button onClick={()=>onInspect(s.barcode_value)} aria-label={'查看运营信息 '+s.barcode_value}>查看运营信息</button></td>}</tr>)}</tbody></table></div>
      {!read.data.total && <p role="status">没有符合条件的油样，可重置筛选。</p>}
      <div className="lab-toolbar"><label>每页条数<select value={query.page_size??'20'} onChange={e=>apply({...query,page_size:e.target.value,page:'1'})}>{[10,20,50,100].map(n=><option key={n}>{n}</option>)}</select></label><span>第 {read.data.page} 页</span><button disabled={read.data.page<=1} onClick={()=>apply({...query,page:String(read.data!.page-1)})}>上一页</button><button disabled={read.data.page*read.data.page_size>=read.data.total} onClick={()=>apply({...query,page:String(read.data!.page+1)})}>下一页</button></div></>}
  </section></div>;
}
