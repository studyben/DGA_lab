import { useState } from 'react';
import { useAuth } from '../../Auth';
import { DataTable, useQuery, useRead } from './assetUi';
import { machineNames, lifecycleNames as statuses } from './assetPresentation';
import { EquipmentDetails, equipmentLayouts, fieldValue, unknownLayout } from './equipmentLayouts';
import { LifecyclePanel } from './LifecyclePanel';

type Detail = { equipment: EquipmentDetails; path: EquipmentDetails[]; children: EquipmentDetails[];
  health_status: 'UNASSESSED'; location: { kind: string; label: string }; site: { id: string; site_name: string; customer_name: string; location_text: string | null } | null };
type History = { total: number; samples: { id: string; barcode_value: string; sampled_at: string;
  equipment_serial: string; test_types: string[]; test_count: number; testing_status: string }[] };
const testNames: Record<string, string> = { DGA: 'DGA', MOISTURE: '微水', BREAKDOWN_VOLTAGE: '击穿电压' };

function TestHistory({ assetId }: { assetId: string }) {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ barcode: '', test_type: '', page: 1 });
  const search = new URLSearchParams({ barcode: filters.barcode, page: String(filters.page), ...(filters.test_type ? { test_type: filters.test_type } : {}) });
  const { data, error, retry } = useRead<History>(`/api/laboratory/assets/${encodeURIComponent(assetId)}/test-history?${search}`);
  return <section className="dashboard-table-panel" aria-label="油样检测记录"><h2>油样检测记录</h2>
    <p>按采样时设备路径展示，包括当时的子设备。未定稿数据不代表正式报告。</p>
    <form className="dashboard-filters" onSubmit={e => { e.preventDefault(); const values = new FormData(e.currentTarget); setFilters({ barcode: String(values.get('barcode') ?? ''), test_type: String(values.get('test_type') ?? ''), page: 1 }); }}>
      <label>条码筛选<input name="barcode" maxLength={160} /></label><label>检测类型筛选<select name="test_type"><option value="">全部</option>{Object.entries(testNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><button>筛选检测记录</button>
    </form>
    {error ? <p role="alert">{error}<button onClick={retry}>重试检测记录</button></p> : !data ? <p role="status">正在加载检测记录…</p> : <>
      <div className="dashboard-table-scroll"><table aria-label="油样检测历史"><thead><tr><th>条码</th><th>采样时间</th><th>采样设备序列号</th><th>检测类型</th><th>检测数量</th><th>检测状态</th></tr></thead><tbody>{data.samples.map(sample => <tr key={sample.id}>
        <td>{can('laboratory.read') ? <a href={`/lab/workbench?barcode=${encodeURIComponent(sample.barcode_value)}`}>{sample.barcode_value}</a> : sample.barcode_value}</td>
        <td>{new Date(sample.sampled_at).toLocaleString('zh-CN')}</td><td>{sample.equipment_serial}</td><td>{sample.test_types.map(type => testNames[type] ?? type).join('、') || '尚无检测'}</td><td>{sample.test_count}</td><td>{sample.testing_status === 'FINALIZED' ? '已定稿' : '检测中'}</td>
      </tr>)}</tbody></table></div>
      {data.total === 0 && <p role="status">暂无符合条件的油样记录。</p>}
      <div className="table-paging"><span>共 {data.total} 条 · 第 {filters.page} 页</span><button disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })}>上一页检测记录</button><button disabled={filters.page * 20 >= data.total} onClick={() => setFilters({ ...filters, page: filters.page + 1 })}>下一页检测记录</button></div>
    </>}
  </section>;
}

export function EquipmentDetailPage({ assetId }: { assetId: string }) {
  const { query, update } = useQuery();
  const { data, error, retry } = useRead<Detail>(`/api/assets/equipment/${encodeURIComponent(assetId)}`);
  if (error) return <p role="alert">{error} <button onClick={retry}>重试</button></p>;
  if (!data) return <p role="status">正在加载设备资料…</p>;
  const layout = equipmentLayouts[data.equipment.machine_type ?? ''] ?? unknownLayout;
  const line = data.path[0].product_line === 'ESS' ? 'ESS' : 'PV';
  const siteHref = data.site ? `/assets/sites/${data.site.id}?product_line=${line}` : '/assets/repair-center';
  const returnTo = /^\/assets\/sites\/[a-f0-9-]+\?/.test(query.return_to ?? '') ? query.return_to : siteHref;
  const childHref = (row: EquipmentDetails) => `/assets/equipment/${row.id}?return_to=${encodeURIComponent(returnTo)}`;
  const sorted = data.children.filter(child => (!query.child_search || [child.display_name, child.serial_number, child.model].some(value => value?.toLowerCase().includes(query.child_search.toLowerCase()))) && (!query.child_type || child.machine_type === query.child_type));
  const sortKey = ['display_name', 'serial_number', 'model', 'machine_type'].includes(query.sort) ? query.sort as keyof EquipmentDetails : 'display_name';
  sorted.sort((a, b) => String(a[sortKey] ?? '').localeCompare(String(b[sortKey] ?? ''), 'zh-CN') * (query.direction === 'desc' ? -1 : 1) || a.id.localeCompare(b.id));
  const page = Math.max(1, Number(query.page) || 1), size = [1,10,20,50,100].includes(Number(query.page_size)) ? Number(query.page_size) : 20;
  return <div className="asset-dashboard"><a href={returnTo}>返回现场详情</a>
    <nav aria-label="设备路径" className="equipment-path"><a href={siteHref}>{data.site?.site_name ?? data.location.label}</a>{data.path.map(node => <span key={node.id}> / <a href={childHref(node)} aria-current={node.id === assetId ? 'page' : undefined}>{node.display_name}</a></span>)}</nav>
    <section className="site-facts" aria-label="设备属性"><h2>{data.equipment.display_name} <small>{layout.title}</small></h2>
      <dl><div><dt>健康状态</dt><dd>未评估</dd></div><div><dt>设备状态</dt><dd>{statuses[data.equipment.lifecycle_status] ?? data.equipment.lifecycle_status}</dd></div>{layout.fields.map(field => <div key={field.key}><dt>{field.label}</dt><dd>{fieldValue(data.equipment, field)}</dd></div>)}<div><dt>客户</dt><dd>{data.site?.customer_name ?? '不适用'}</dd></div><div><dt>当前位置</dt><dd>{data.location.label}</dd></div><div><dt>现场位置</dt><dd>{data.site?.location_text ?? '不适用'}</dd></div></dl>
    </section>
    <form className="dashboard-filters" onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget); update({ child_search: String(form.get('search') ?? ''), child_type: String(form.get('type') ?? ''), page: '1' }); }}>
      <label>子设备名称或序列号筛选<input name="search" defaultValue={query.child_search ?? ''} maxLength={160} /></label><label>子设备类型筛选<select name="type" defaultValue={query.child_type ?? ''}><option value="">全部</option>{Object.entries(machineNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><button>筛选子设备</button>
    </form>
    <DataTable name="子设备清单" rows={sorted.slice((page-1)*size, page*size)} total={sorted.length} columns={[{ key: 'display_name', label: '设备名称 / Tag number' }, { key: 'serial_number', label: '序列号' }, { key: 'model', label: '设备型号' }, { key: 'machine_type', label: '设备类型', render: row => machineNames[row.machine_type ?? ''] ?? '未分类设备' }]} query={{ ...query, page_size: String(size) }} update={update} href={childHref} />
    <TestHistory assetId={assetId} />
    <LifecyclePanel assetId={assetId} />
  </div>;
}
