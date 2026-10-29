import { useState } from 'react';
import { useAuth } from '../../Auth';
import { gridNames, operationNames } from './assetPresentation';

export type SiteBasics = {
  id: string; revision: number; site_name: string; location_text: string | null;
  grid_status: string | null; operation_status: string | null; commissioning_date: string | null;
  product_line: 'PV' | 'ESS'; power_mw: number | null; energy_mwh: number | null;
};

export function SiteBasicsEditor({ site, saved }: { site?: SiteBasics; saved: () => void }) {
  const auth = useAuth();
  const [base, setBase] = useState<SiteBasics | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!auth.can('assets.site.edit')) return null;
  if (!base) return site ? <button type="button" onClick={() => { setBase(site); setError(''); }}>编辑现场资料</button> : null;
  return <form className="site-basics-editor" onSubmit={async event => {
    event.preventDefault();
    if (busy) return;
    const input = new FormData(event.currentTarget);
    const optional = (key: string) => String(input.get(key) ?? '').trim() || null;
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/assets/sites/${encodeURIComponent(base.id)}/basics`, {
        method: 'PUT', cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': auth.session?.csrf_token ?? '' },
        body: JSON.stringify({ expected_revision: base.revision, product_line: base.product_line,
          site_name: optional('site_name'), location_text: optional('location_text'),
          grid_status: optional('grid_status'), operation_status: optional('operation_status'),
          commissioning_date: optional('commissioning_date'), power_mw: optional('power_mw'),
          energy_mwh: base.product_line === 'ESS' ? optional('energy_mwh') : null }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? '现场资料已被他人修改；输入已保留。请先复制输入，取消编辑并刷新资料后核对重试。' :
        response.status === 401 ? '登录已失效，请重新登录。' : response.status === 403 ? '没有修改权限或会话已更新，请重新登录后核对。' :
        response.status === 422 ? '请检查字段，容量须为非负数、最多六位小数，整数部分最多十位。' : '保存失败，请稍后重试。');
      setBase(null); saved();
    } catch (cause) { setError(cause instanceof Error && cause.name !== 'TimeoutError' ? cause.message : '请求超时，保存结果尚未确认。请先核对最新资料，勿重复提交。'); }
    finally { setBusy(false); }
  }}>
    <p className="dashboard-note">仅编辑现场基础资料及当前产品线容量，不改变客户归属或设备安装关系。留空表示未提供。</p>
    <label>现场名称<input name="site_name" defaultValue={base.site_name} required maxLength={200} /></label>
    <label>现场位置<input name="location_text" defaultValue={base.location_text ?? ''} maxLength={300} /></label>
    <label>并网调试状态<select name="grid_status" defaultValue={base.grid_status ?? ''}><option value="">未提供</option>{Object.entries(gridNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
    <label>投运状态<select name="operation_status" defaultValue={base.operation_status ?? ''}><option value="">未提供</option>{Object.entries(operationNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
    <label>Commissioning date<input name="commissioning_date" type="date" defaultValue={base.commissioning_date ?? ''} /></label>
    <label>现场功率 MW<input name="power_mw" type="number" min="0" max="9999999999.999999" step="0.000001" defaultValue={base.power_mw ?? ''} /></label>
    {base.product_line === 'ESS' && <label>现场电池容量 MWh<input name="energy_mwh" type="number" min="0" max="9999999999.999999" step="0.000001" defaultValue={base.energy_mwh ?? ''} /></label>}
    {error && <p role="alert">{error}</p>}
    <div><button type="submit" disabled={busy}>{busy ? '保存中…' : '保存现场资料'}</button> <button type="button" disabled={busy} onClick={() => setBase(null)}>取消编辑</button></div>
  </form>;
}
