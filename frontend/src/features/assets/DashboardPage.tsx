import { useEffect, useState, type ReactNode } from 'react';
import './dashboard.css';

type Values = Record<string, string>;
type Site = {
  id: string; site_name: string; location_text: string | null; customer_id: string; customer_name: string;
  product_line: 'PV' | 'ESS'; power_mw: number | null; energy_mwh: number | null;
  grid_status: string | null; operation_status: string | null; commissioning_date: string | null;
};
type Equipment = {
  id: string; system_asset_number: string; serial_number: string; model: string | null; material_number: string | null;
  machine_type: string | null; lifecycle_status: string; power_mw: number | null; energy_mwh: number | null;
};
type Machine = { machine_type: string | null; count: number; power_mw: number | null; energy_mwh: number | null; missing_power_count: number; missing_energy_count: number };
type Dashboard = { site_count: number; customer_count: number; sites: Site[]; machine_totals: Machine[] };
type Detail = { site: Site; equipment_count: number; equipment: Equipment[] };
type Column<T> = { key: Extract<keyof T, string>; label: string; render?: (row: T) => ReactNode };
const machineNames: Values = { INVERTER_UNIT: '逆变器整机', INVERTER: '逆变器', ESS_SYSTEM: '储能系统', PCS_UNIT: 'PCS整机', PCS: 'PCS本体', BATTERY_CABINET: '电池柜', TRANSFORMER: '变压器' };
const gridNames: Values = { NOT_STARTED: '未开始', IN_PROGRESS: '调试中', COMPLETED: '已完成' };
const operationNames: Values = { NOT_OPERATIONAL: '未投运', PARTIAL: '部分投运', OPERATIONAL: '已投运', DECOMMISSIONED: '已退役' };
const lifecycleNames: Values = { COMMISSIONING: '调试中', IN_SERVICE: '在役', OUT_OF_SERVICE: '离役', RETIRED: '停用', MERGED: '已合并' };
const quantity = (value: string | number | null, unit: string) => value == null ? '未提供' : `${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })} ${unit}`;
const label = (names: Values, value: string | number | null) => value == null ? '未提供' : names[String(value)] ?? String(value);
const cellText = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? value : '未提供';

function useQuery() {
  const [query, setQuery] = useState<Values>(() => Object.fromEntries(new URLSearchParams(location.search)));
  function update(patch: Values, reset = false) {
    const next = { ...(reset ? { product_line: query.product_line ?? 'PV', columns: query.columns ?? '' } : query), ...patch };
    const search = new URLSearchParams(Object.entries(next).filter(([, value]) => value !== ''));
    history.replaceState(null, '', location.pathname + '?' + search.toString());
    setQuery(next);
  }
  return { query, update };
}

function useRead<T>(url: string) {
  const [attempt, retry] = useState(0);
  const [state, setState] = useState<{ url: string; data?: T; error?: string }>({ url: '' });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    setState({ url });
    void (async () => {
      try {
        const response = await fetch(url, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error(response.status === 404 ? '未找到该产品线的现场。' : response.status === 401 ? '登录已失效，请重新登录。' : response.status === 403 ? '没有查看资产的权限。' : response.status === 422 ? '筛选条件无效，请清除筛选后重试。' : '资产服务暂不可用，请重试。');
        const data: T = await response.json();
        if (active) setState({ url, data });
      } catch (error) {
        if (active) setState({ url, error: error instanceof Error && error.name !== 'AbortError' ? error.message : '请求超时，请重试。' });
      } finally { clearTimeout(timeout); }
    })();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [url, attempt]);
  return { data: state.url === url ? state.data : undefined, error: state.url === url ? state.error : undefined, retry: () => retry(v => v + 1) };
}

function apiQuery(query: Values, keys: string[]) {
  return new URLSearchParams(Object.entries(query).filter(([key, value]) => keys.includes(key) && value !== '')).toString();
}
const pagingKeys = ['product_line', 'sort', 'direction', 'page', 'page_size'];

function Filters({ fields, query, update }: { fields: { key: string; label: string; options?: Values; number?: boolean }[]; query: Values; update: (patch: Values, reset?: boolean) => void }) {
  return <form className="dashboard-filters" key={JSON.stringify(query)} onSubmit={e => {
    e.preventDefault();
    update({ ...Object.fromEntries(new FormData(e.currentTarget)) as Values, page: '1' });
  }}>
    {fields.map(field => <label key={field.key}>{field.label}{field.options ?
      <select name={field.key} defaultValue={query[field.key] ?? ''}><option value="">全部</option>{Object.entries(field.options).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select> :
      <input name={field.key} type={field.number ? 'number' : 'text'} min={field.number ? 1900 : undefined} max={field.number ? 2200 : undefined} maxLength={160} defaultValue={query[field.key] ?? ''} />}</label>)}
    <button type="submit">应用筛选</button><button type="button" onClick={() => update({ page: '1' }, true)}>清除筛选</button>
  </form>;
}

function DataTable<T extends { id: string }>({ name, rows, total, columns, query, update, href }: {
  name: string; rows: T[]; total: number; columns: Column<T>[]; query: Values;
  update: (patch: Values) => void; href?: (row: T) => string;
}) {
  const hidden = new Set((query.columns ?? '').split(',').filter(Boolean));
  const visible = columns.filter((c, index) => index === 0 || !hidden.has(c.key));
  const page = Math.max(1, Number(query.page) || 1), pageSize = Number(query.page_size) || 20;
  const sort = query.sort ?? columns[0].key;
  return <section className="dashboard-table-panel">
    <div className="table-toolbar"><h2>{name} <small>共 {total} 条</small></h2>
      <details><summary>显示列</summary><div className="column-options">{columns.slice(1).map(c => <label key={c.key}><input type="checkbox" checked={!hidden.has(c.key)} onChange={() => {
        if (hidden.has(c.key)) hidden.delete(c.key); else hidden.add(c.key);
        update({ columns: [...hidden].join(',') });
      }} />{c.label}</label>)}</div></details>
    </div>
    <div className="dashboard-table-scroll"><table aria-label={name}><thead><tr>{visible.map(c => <th key={c.key} aria-sort={sort === c.key ? query.direction === 'desc' ? 'descending' : 'ascending' : 'none'}>
      <button onClick={() => update({ sort: c.key, direction: sort === c.key && query.direction !== 'desc' ? 'desc' : 'asc', page: '1' })}>{c.label}{sort === c.key ? query.direction === 'desc' ? ' ↓' : ' ↑' : ''}</button>
    </th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id} className={href ? 'clickable-row' : undefined} onClick={href ? e => { if (!(e.target as HTMLElement).closest('a')) location.assign(href(row)); } : undefined}>
      {visible.map((c, index) => <td key={c.key}>{index === 0 && href ? <a href={href(row)}>{cellText(row[c.key])}</a> : c.render ? c.render(row) : cellText(row[c.key])}</td>)}
    </tr>)}</tbody></table></div>
    {rows.length === 0 && <p className="dashboard-empty" role="status">没有符合条件的记录。</p>}
    <div className="table-paging"><label>每页条数 <select value={String(pageSize)} onChange={e => update({ page_size: e.target.value, page: '1' })}>{[1, 10, 20, 50, 100].map(n => <option key={n}>{n}</option>)}</select></label>
      <span>第 {page} 页 / 共 {Math.max(1, Math.ceil(total / pageSize))} 页</span>
      <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>上一页</button>
      <button disabled={page * pageSize >= total} onClick={() => update({ page: String(page + 1) })}>下一页</button>
    </div>
  </section>;
}

const siteFields = [
  { key: 'site', label: '现场筛选' }, { key: 'customer', label: '客户筛选' }, { key: 'location', label: '位置筛选' },
  { key: 'grid_status', label: '并网调试状态筛选', options: gridNames },
  { key: 'operation_status', label: '投运状态筛选', options: operationNames },
];
function siteColumns(ess: boolean): Column<Site>[] {
  return [{ key: 'site_name', label: '现场名称' }, { key: 'location_text', label: '位置' }, { key: 'customer_name', label: '客户' },
    { key: 'power_mw', label: ess ? '装机功率 MW' : '装机容量 MW', render: r => quantity(r.power_mw, 'MW') },
    ...(ess ? [{ key: 'energy_mwh' as const, label: '电池容量 MWh', render: (r: Site) => quantity(r.energy_mwh, 'MWh') }] : []),
    { key: 'grid_status', label: '并网调试状态', render: r => label(gridNames, r.grid_status) },
    { key: 'operation_status', label: '投运状态', render: r => label(operationNames, r.operation_status) }, { key: 'commissioning_date', label: 'Commissioning date' }];
}

export function DashboardPage() {
  const { query, update } = useQuery();
  const ess = query.product_line === 'ESS';
  const { data, error, retry } = useRead<Dashboard>('/api/assets/dashboard?' + apiQuery(query, [...pagingKeys, ...siteFields.map(f => f.key)]));
  return <div className="asset-dashboard">
    <div className="line-toggle" aria-label="产品线"><button aria-pressed={!ess} onClick={() => update({ product_line: 'PV', page: '1', sort: 'site_name' })}>光伏 PV</button><button aria-pressed={ess} onClick={() => update({ product_line: 'ESS', page: '1', sort: 'site_name' })}>储能 ESS</button></div>
    <Filters fields={siteFields} query={query} update={update} />
    {error ? <p role="alert">{error} <button onClick={retry}>重试</button></p> : !data ? <p role="status">正在加载现场资料…</p> : <>
      <section aria-label="筛选结果指标" className="dashboard-metrics">
        <article><span>现场数量</span><strong>{data.site_count}</strong></article><article><span>客户数量</span><strong>{data.customer_count}</strong></article>
        {data.machine_totals.map(m => <article key={m.machine_type ?? 'unknown'}><span>{m.machine_type ? machineNames[m.machine_type] ?? m.machine_type : '未分类设备'}</span><strong>{m.count} <small>台</small></strong><p>{quantity(m.power_mw, 'MW')}{m.missing_power_count > 0 && m.power_mw != null ? '（已知部分）' : ''}{ess && <><br />{quantity(m.energy_mwh, 'MWh')}{m.missing_energy_count > 0 && m.energy_mwh != null ? '（已知部分）' : ''}</>}</p></article>)}
      </section><p className="dashboard-note">指标按全部筛选结果统计。各机器类型容量分别汇总，现场容量以正式项目资料为准。</p>
      <DataTable name="现场列表" rows={data.sites} total={data.site_count} columns={siteColumns(ess)} query={query} update={update} href={row => `/assets/sites/${row.id}?product_line=${ess ? 'ESS' : 'PV'}&return_to=${encodeURIComponent(location.pathname + location.search)}`} />
    </>}
  </div>;
}

const equipmentFields = [{ key: 'serial', label: '序列号筛选' }, { key: 'model', label: '型号筛选' }, { key: 'machine_type', label: '机器类型筛选', options: machineNames }, { key: 'lifecycle_status', label: '设备状态筛选', options: lifecycleNames }];
export function SiteDetailPage({ siteId }: { siteId: string }) {
  const { query, update } = useQuery();
  const ess = query.product_line === 'ESS';
  const { data, error, retry } = useRead<Detail>(`/api/assets/sites/${encodeURIComponent(siteId)}?` + apiQuery(query, [...pagingKeys, ...equipmentFields.map(f => f.key)]));
  const requestedReturn = query.return_to ?? '';
  const returnTo = /^\/assets(?:\/sites)?(?:\?|$)/.test(requestedReturn) ? requestedReturn : `/assets?product_line=${ess ? 'ESS' : 'PV'}`;
  const columns: Column<Equipment>[] = [{ key: 'system_asset_number', label: '系统资产号' }, { key: 'serial_number', label: '序列号' }, { key: 'model', label: '设备型号' }, { key: 'material_number', label: '设备物料号' }, { key: 'machine_type', label: '机器类型', render: r => label(machineNames, r.machine_type) }, { key: 'lifecycle_status', label: '设备状态', render: r => label(lifecycleNames, r.lifecycle_status) }, { key: 'power_mw', label: '功率 MW', render: r => quantity(r.power_mw, 'MW') }, ...(ess ? [{ key: 'energy_mwh' as const, label: '电池容量 MWh', render: (r: Equipment) => quantity(r.energy_mwh, 'MWh') }] : [])];
  return <div className="asset-dashboard"><a className="dashboard-back" href={returnTo}>返回现场列表</a>
    {error ? <p role="alert">{error} <button onClick={retry}>重试</button></p> : !data ? <p role="status">正在加载现场资料…</p> : <section className="site-facts" aria-label="现场资料"><h2>{data.site.site_name}</h2><dl>{siteColumns(ess).slice(1).map(c => <div key={c.key}><dt>{c.label}</dt><dd>{c.render ? c.render(data.site) : data.site[c.key] ?? '未提供'}</dd></div>)}</dl></section>}
    <Filters fields={equipmentFields} query={query} update={(patch, reset) => update(reset ? { ...patch, return_to: query.return_to ?? '' } : patch, reset)} />
    {data && <DataTable name="一级设备清单" rows={data.equipment} total={data.equipment_count} columns={columns} query={query} update={update} />}
  </div>;
}
