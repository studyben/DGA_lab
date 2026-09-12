import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import { useRead } from './assetUi';
import './dashboard.css';
import './assetImport.css';

type State = 'STAGED' | 'VALIDATED' | 'FAILED' | 'PUBLISHED';
type Counts = { total_rows: number; valid_rows: number; warning_rows: number; error_rows: number; warning_count: number; error_count: number };
type Row = { row: number; values: Record<string, string | null>; asset_id?: string; system_asset_number?: string };
type Issue = { row: number; field: string; severity: 'ERROR' | 'WARNING'; message: string };
type Batch = { id: string; filename: string; state: State; summary: Counts; rows: Row[]; issues: Issue[]; validation_revision: number; created_at: string; published_at: string | null; sha256: string; byte_size: number };
type BatchList = { batches: Pick<Batch, 'id' | 'filename' | 'state' | 'created_at'>[]; page: number; total: number };
const stateLabels: Record<State, string> = { STAGED: '等待后台校验', VALIDATED: '已校验', FAILED: '校验失败', PUBLISHED: '已发布' };
const errors: Record<string, string> = {
  import_file_size: '文件必须为 1 字节至 2 MiB，请拆分批次。',
  invalid_import_filename: '请选择文件名不超过200字符的 .xlsx 文件。',
  import_has_errors: '存在错误，不能发布。请修正文件后重新上传。',
  import_not_validated: '批次尚未完成校验或校验失败，不能发布。',
  import_stale_validation: '预览已更新，请重新查看批次并确认。',
  import_warnings_unacknowledged: '请先核对全部警告并勾选确认。',
  object_storage_unavailable: '源文件存储暂不可用，未完成上传，请稍后重试。',
  import_submit_unavailable: '上传结果尚未确认。请先按文件名查看批次历史，勿直接重复上传。',
  import_publish_unavailable: '发布服务暂不可用。请重新查看批次结果后再决定是否重试。',
  csrf_rejected: '会话已更新，请刷新页面后重试。',
  permission_denied: '当前账号没有资产导入权限。',
};

export function AssetImportPage() {
  const { session } = useAuth();
  const [selected, setSelected] = useState(() => new URLSearchParams(location.search).get('batch') ?? '');
  const [batch, setBatch] = useState<Batch | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [acknowledged, setAcknowledged] = useState(false);
  const [filter, setFilter] = useState('');
  const [severity, setSeverity] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const batches = useRead<BatchList>(`/api/assets/imports?query=${encodeURIComponent(search)}&page=${page}&refresh=${refresh}`);

  function select(id: string) {
    setSelected(id); setBatch(null); setAcknowledged(false); setError(''); setMessage(''); setFilter('');
    setRefresh(n => n + 1);
    history.replaceState(null, '', id ? `/assets/import?batch=${encodeURIComponent(id)}` : '/assets/import');
  }

  useEffect(() => {
    if (!selected) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`/api/assets/imports/${encodeURIComponent(selected)}`, { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
        if (!response.ok) throw new Error(response.status === 401 ? '登录已失效，请重新登录。' : '无法读取批次，请检查权限或稍后重试。');
        const data: Batch = await response.json();
        if (!active) return;
        setBatch(data); setError('');
        if (data.state === 'STAGED') timer = setTimeout(() => void load(), 2000);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : '无法读取批次。');
      }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [selected, refresh]);

  async function mutate(kind: 'upload' | 'publish') {
    if (lock.current || !session || (kind === 'upload' ? !file : !batch)) return;
    lock.current = true; setBusy(true); setError(''); setMessage('');
    try {
      if (kind === 'upload' && file!.size > 2 * 1024 * 1024) throw new Error(errors.import_file_size);
      const response = await fetch(kind === 'upload' ? `/api/assets/imports?filename=${encodeURIComponent(file!.name)}` : `/api/assets/imports/${batch!.id}/publish`, {
        method: 'POST', signal: AbortSignal.timeout(45000), credentials: 'same-origin',
        headers: { 'X-CSRF-Token': session.csrf_token, 'Content-Type': kind === 'upload' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'application/json' },
        body: kind === 'upload' ? file : JSON.stringify({ validation_revision: batch!.validation_revision, acknowledge_warnings: acknowledged }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(errors[result.code] ?? (response.status === 401 ? '登录已失效，请重新登录。' : '操作未确认成功。请重新查看批次列表和结果后再重试。'));
      }
      const result: Batch = await response.json();
      select(result.id); setBatch(result); setRefresh(n => n + 1);
      if (kind === 'publish' && result.state !== 'PUBLISHED') setMessage('正式资料已变化，预览已更新；尚未创建资产，请重新核对后发布。');
    } catch (e) {
      setError(e instanceof Error && e.name !== 'TimeoutError' ? e.message : '响应超时，结果尚未确认。请重新查看批次列表与结果，勿直接重复上传。');
      batches.retry();
    } finally { lock.current = false; setBusy(false); }
  }

  const visibleRows = batch?.rows.filter(r => Object.values(r.values).some(v => v?.toLowerCase().includes(filter.toLowerCase()))) ?? [];
  const visibleIssues = batch?.issues.filter(i => (!severity || i.severity === severity) && `${i.row} ${i.field} ${i.message}`.toLowerCase().includes(filter.toLowerCase())) ?? [];
  const canPublish = batch?.state === 'VALIDATED' && batch.summary.error_count === 0 && (!batch.summary.warning_count || acknowledged);
  return <div className="asset-dashboard asset-import">
    <section className="dashboard-table-panel" aria-label="上传资产文件">
      <div className="table-toolbar"><h2>新增资产批量导入</h2><a className="button" href="/api/assets/imports/template">下载 Excel 模板与参考资料</a></div>
      <p>只新增资产，引用已有客户、现场和物料。不覆盖已有资产；修正文件后会保留为新批次。</p>
      <div className="dashboard-filters"><label>选择 Excel 文件<input type="file" accept=".xlsx" disabled={busy} onChange={e => { setFile(e.target.files?.[0] ?? null); select(''); }} /></label>
        <button disabled={!file || busy} onClick={() => void mutate('upload')}>{busy ? '正在处理…' : '上传并校验'}</button></div>
      <p className="import-note">固定 XLSX 模板 · 每批最多500条资产 · 文件不超过2 MiB · 时间须注明时区</p>
    </section>
    {error && <div role="alert" className="import-error"><p>{error}</p><button disabled={busy} onClick={() => { setAcknowledged(false); setRefresh(n => n + 1); }}>重新查看批次</button></div>}
    {message && <p role="status">{message}</p>}
    {selected && !batch && !error && <p role="status">正在读取批次…</p>}
    {batch && <section className="dashboard-table-panel" aria-label="导入批次预览">
      <div className="table-toolbar"><h2>{batch.filename}</h2><span className={`import-state ${batch.state}`}>{stateLabels[batch.state]}</span></div>
      <p className="import-note">批次 {batch.id} · 创建于 {new Date(batch.created_at).toLocaleString()}</p>
      {batch.state === 'STAGED' && <p role="status">后台正在排队或校验，页面将自动更新。若长时间无变化，请联系管理员检查 import-worker；无需重复上传。</p>}
      {batch.state === 'PUBLISHED' && <p role="status">整批发布成功。下方可进入新资产详情；重复提交不会重复创建。</p>}
      <div className="import-counts">{([['total_rows', '总行数'], ['valid_rows', '有效行'], ['warning_rows', '警告行'], ['error_rows', '错误行']] as const).map(([key, label]) => <div key={key}><span>{label}</span><strong>{batch.summary[key]}</strong></div>)}</div>
      <div className="dashboard-filters"><label>筛选预览和问题<input value={filter} onChange={e => setFilter(e.target.value)} placeholder="记录键、序列号或问题文字" /></label>
        <label>问题级别<select value={severity} onChange={e => setSeverity(e.target.value)}><option value="">全部</option><option value="ERROR">错误</option><option value="WARNING">警告</option></select></label></div>
      <h3>逐行问题</h3><div className="dashboard-table-scroll"><table aria-label="逐行问题"><thead><tr><th>行号</th><th>字段</th><th>级别</th><th>处理说明</th></tr></thead><tbody>{visibleIssues.map((i, index) => <tr key={index}><td>{i.row || '文件'}</td><td>{i.field}</td><td className={i.severity === 'ERROR' ? 'import-error-text' : ''}>{i.severity === 'ERROR' ? '错误' : '警告'}</td><td>{i.message}</td></tr>)}</tbody></table></div>
      {!visibleIssues.length && batch.state !== 'STAGED' && <p>没有符合筛选条件的问题。</p>}
      <h3>资产预览</h3><div className="dashboard-table-scroll"><table aria-label="资产预览"><thead><tr><th>行号 / 记录键</th><th>序列号</th><th>物料 / 型号</th><th>类型</th><th>位置 / 父记录键</th><th>生效时间</th><th>新增资产</th></tr></thead><tbody>{visibleRows.map(r => <tr key={r.row}><td>{r.row} / {r.values.record_key}</td><td>{r.values.serial_number}</td><td>{r.values.material_number}<br />{r.values.model}</td><td>{r.values.machine_type}</td><td>{r.values.location_kind}<br />{r.values.parent_record_key || r.values.site_id}</td><td>{r.values.effective_at}</td><td>{r.asset_id ? <a href={`/assets/equipment/${r.asset_id}?return_to=${encodeURIComponent(`/assets/import?batch=${batch.id}`)}`}>{r.system_asset_number}</a> : '尚未创建'}</td></tr>)}</tbody></table></div>
      {batch.state !== 'PUBLISHED' && <div className="import-publication">
        {batch.summary.warning_count > 0 && <label><input type="checkbox" checked={acknowledged} disabled={busy || batch.state !== 'VALIDATED'} onChange={e => setAcknowledged(e.target.checked)} /> 我已核对全部警告，确认这些是需要新增的物理设备</label>}
        <button disabled={!canPublish || busy} onClick={() => void mutate('publish')}>发布新资产</button>
        <p>错误必须修正后重新上传。发布一次性创建整批资产及初始安装关系，不跳过错误行。</p>
      </div>}
    </section>}
    <section className="dashboard-table-panel" aria-label="批次历史">
      <h2>批次历史</h2><div className="dashboard-filters"><label>搜索批次<input value={search} placeholder="文件名或批次号" onChange={e => { setSearch(e.target.value); setPage(1); }} /></label><button onClick={() => batches.retry()}>刷新列表</button></div>
      {batches.error && <p role="alert">{batches.error}</p>}
      {!batches.data && !batches.error && <p>正在读取历史…</p>}
      {batches.data && <><div className="dashboard-table-scroll"><table aria-label="批次历史"><thead><tr><th>文件名</th><th>状态</th><th>创建时间</th></tr></thead><tbody>{batches.data.batches.map(b => <tr key={b.id}><td><button disabled={busy} onClick={() => select(b.id)}>{b.filename}</button></td><td>{stateLabels[b.state]}</td><td>{new Date(b.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>
        {!batches.data.total && <p>没有符合条件的批次。</p>}<div className="table-paging"><span>共 {batches.data.total} 条 · 第 {page} 页</span><button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button><button disabled={page * 20 >= batches.data.total} onClick={() => setPage(p => p + 1)}>下一页</button></div></>}
    </section>
  </div>;
}
