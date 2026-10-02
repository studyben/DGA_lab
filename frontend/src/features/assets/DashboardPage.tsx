import { useState, type ReactNode } from 'react';
import { SiteBasicsEditor } from './SiteBasicsEditor';
import { DataTable, useQuery, useRead } from './assetUi';
import { machineNames, gridNames, operationNames, lifecycleNames, quantity, label } from './assetPresentation';
import './dashboard.css';
import { AlarmLink } from '../condition-analysis/AlarmLink';

type Values = Record<string, string>;
type Site = {
  revision: number;
  id: string; site_name: string; location_text: string | null; customer_id: string; customer_name: string;
  product_line: 'PV' | 'ESS'; power_mw: number | null; energy_mwh: number | null;
  grid_status: string | null; operation_status: string | null; commissioning_date: string | null;
};
type Equipment = {
  display_name: string;
  id: string; system_asset_number: string; serial_number: string; model: string | null; material_number: string | null;
  machine_type: string | null; lifecycle_status: string; power_mw: number | null; energy_mwh: number | null;
};
type Machine = { machine_type: string | null; count: number; power_mw: number | null; energy_mwh: number | null; missing_power_count: number; missing_energy_count: number };
type Dashboard = { site_count: number; customer_count: number; sites: Site[]; machine_totals: Machine[] };
type Detail = { site: Site; equipment_count: number; equipment: Equipment[] };
type Column<T> = { key: Extract<keyof T, string>; label: string; render?: (row: T) => ReactNode };
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
    <AlarmLink filters={{product_line:ess?'ESS':'PV',site:query.site??'',customer:query.customer??''}} description="按产品线、当前现场和客户筛选；不应用位置关键词、调试状态或投运状态筛选"/>
    {error ? <p role="alert">{error} <button onClick={retry}>重试</button></p> : !data ? <p role="status">正在加载现场资料…</p> : <>
      <section aria-label="筛选结果指标" className="dashboard-metrics">
        <article><span>现场数量</span><strong>{data.site_count}</strong></article><article><span>客户数量</span><strong>{data.customer_count}</strong></article>
        {data.machine_totals.map(m => <article key={m.machine_type ?? 'unknown'}><span>{m.machine_type ? machineNames[m.machine_type] ?? m.machine_type : '未分类设备'}</span><strong>{m.count} <small>台</small></strong><p>{quantity(m.power_mw, 'MW')}{m.missing_power_count > 0 && m.power_mw != null ? '（已知部分）' : ''}{ess && <><br />{quantity(m.energy_mwh, 'MWh')}{m.missing_energy_count > 0 && m.energy_mwh != null ? '（已知部分）' : ''}</>}</p></article>)}
      </section><p className="dashboard-note">指标按全部筛选结果统计。各机器类型容量分别汇总，现场容量以正式项目资料为准。</p>
      <DataTable name="现场列表" rows={data.sites} total={data.site_count} columns={siteColumns(ess)} query={query} update={update} href={row => `/assets/sites/${row.id}?product_line=${ess ? 'ESS' : 'PV'}&return_to=${encodeURIComponent(location.pathname + location.search)}`} />
    </>}
  </div>;
}

const equipmentFields = [{ key: 'name', label: '设备名称 / Tag 筛选' }, { key: 'serial', label: '序列号筛选' }, { key: 'model', label: '型号筛选' }, { key: 'machine_type', label: '机器类型筛选', options: machineNames }, { key: 'lifecycle_status', label: '设备状态筛选', options: lifecycleNames }];
export function SiteDetailPage({ siteId }: { siteId: string }) {
  const [savedNotice, setSavedNotice] = useState('');
  const { query, update } = useQuery();
  const ess = query.product_line === 'ESS';
  const { data, error, retry } = useRead<Detail>(`/api/assets/sites/${encodeURIComponent(siteId)}?` + apiQuery(query, [...pagingKeys, ...equipmentFields.map(f => f.key)]));
  const requestedReturn = query.return_to ?? '';
  const returnTo = /^\/assets(?:\/sites)?(?:\?|$)/.test(requestedReturn) ? requestedReturn : `/assets?product_line=${ess ? 'ESS' : 'PV'}`;
  const columns: Column<Equipment>[] = [{ key: 'display_name', label: '设备名称 / Tag number' }, { key: 'system_asset_number', label: '系统资产号' }, { key: 'serial_number', label: '序列号' }, { key: 'model', label: '设备型号' }, { key: 'material_number', label: '设备物料号' }, { key: 'machine_type', label: '机器类型', render: r => label(machineNames, r.machine_type) }, { key: 'lifecycle_status', label: '设备状态', render: r => label(lifecycleNames, r.lifecycle_status) }, { key: 'power_mw', label: '功率 MW', render: r => quantity(r.power_mw, 'MW') }, ...(ess ? [{ key: 'energy_mwh' as const, label: '电池容量 MWh', render: (r: Equipment) => quantity(r.energy_mwh, 'MWh') }] : [])];
  return <div className="asset-dashboard"><a className="dashboard-back" href={returnTo}>返回现场列表</a>
    {savedNotice && <p role="status">{savedNotice}</p>}
    {error ? <p role="alert">{error} <button onClick={retry}>重试</button></p> : !data ? <p role="status">正在加载现场资料…</p> : <section className="site-facts" aria-label="现场资料"><h2>{data.site.site_name}</h2><dl>{siteColumns(ess).slice(1).map(c => <div key={c.key}><dt>{c.label}</dt><dd>{c.render ? c.render(data.site) : data.site[c.key] ?? '未提供'}</dd></div>)}</dl></section>}
    <SiteBasicsEditor key={`${siteId}:${ess ? 'ESS' : 'PV'}`} site={data?.site} saved={() => { setSavedNotice('现场资料已保存。若刷新失败，请重试读取，不要重复提交。'); retry(); }} />
    <Filters fields={equipmentFields} query={query} update={(patch, reset) => update(reset ? { ...patch, return_to: query.return_to ?? '' } : patch, reset)} />
    {data && <DataTable name="一级设备清单" rows={data.equipment} total={data.equipment_count} columns={columns} query={query} update={update} href={row => `/assets/equipment/${row.id}?return_to=${encodeURIComponent(location.pathname + location.search)}`} />}
  </div>;
}
