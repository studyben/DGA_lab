import {importFieldLabels,sourceValue} from './siteImportPresentation';
import {useState} from 'react';
import {useAuth} from '../../Auth';
import {useRead} from './assetUi';

type Source={id:string;batch_id:string;filename:string;source_note:string|null;sheet:string;row_number:number;revision:number;reason:string;display_name:string;occurred_at:string;original_values:Record<string,unknown>;reviewed_values:Record<string,unknown>};
export function ImportSourcesPanel({kind,id}:{kind:'sites'|'customers';id:string}) {
  const {can}=useAuth();const [page,setPage]=useState(1),[filter,setFilter]=useState('');
  const data=useRead<{sources:Source[];total:number}>(`/api/assets/${kind}/${id}/sources?page=${page}`);
  const name=kind==='sites'?'现场导入来源':'客户导入来源';
  return <section className="dashboard-table-panel" aria-label={name}><h2>{name}</h2><p className="dashboard-note">每次来源单独保留；引用已有资料不会覆盖原属性或原来源备注。原始文件需要资产导入权限。</p>
    <label>筛选本页来源<input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="备注、文件名或核对人"/></label>
    {data.error?<p role="alert">{data.error}<button onClick={data.retry}>重试</button></p>:!data.data?<p>正在读取来源…</p>:data.data.total===0?<p>尚无导入来源记录。</p>:<>
    <div className="dashboard-table-scroll"><table aria-label={name}><thead><tr><th>来源备注</th><th>文件 / 原行</th><th>核对依据</th><th>原值与采用值</th></tr></thead><tbody>{data.data.sources.filter(s=>JSON.stringify(s).toLocaleLowerCase().includes(filter.toLocaleLowerCase())).map(s=><tr key={s.id}><td className="site-import-note">{s.source_note??'未提供'}</td><td>{s.filename}<br/>{s.sheet} / {s.row_number}<br/>{can('assets.import')&&<a href={`/assets/import?mode=SITES&batch=${s.batch_id}`}>查看导入批次</a>}</td><td>{s.reason}<br/>{s.display_name} · {new Date(s.occurred_at).toLocaleString()}<br/>核对修订 {s.revision}</td><td><details><summary>查看来源原值与核对值</summary><dl>{Object.keys({...s.original_values,...s.reviewed_values}).map(field=><div key={field}><dt>{importFieldLabels[field]??(field==='reason'?'核对原因':field)}</dt><dd>原始：{sourceValue(s.original_values[field])}<br/>核对：{sourceValue(s.reviewed_values[field])}</dd></div>)}</dl></details></td></tr>)}</tbody></table></div>
    <div className="table-paging"><span>共 {data.data.total} 条 · 第 {page} 页</span><button disabled={page<=1} onClick={()=>setPage(n=>n-1)}>上一页来源</button><button disabled={page*20>=data.data.total} onClick={()=>setPage(n=>n+1)}>下一页来源</button></div></>}
  </section>;
}
