import { useEffect, useState } from 'react';
import { useAuth } from '../../Auth';
import { TrendChart } from './TrendChart';
import { TrendData, numberText, readingText, reasonText, timeText } from './trendTypes';
import './trends.css';

const typeNames: Record<string, string> = { DGA: 'DGA', MOISTURE: '微水', BREAKDOWN_VOLTAGE: '击穿电压' };
const fields: Record<string, string[]> = { DGA: ['H2','CH4','C2H2','C2H4','C2H6','CO','CO2'], MOISTURE: ['MOISTURE'], BREAKDOWN_VOLTAGE: ['BREAKDOWN_VOLTAGE'] };
const labels = { minimum: '最小值', maximum: '最大值', mean: '平均值', delta: '最近相邻变化量', annualized_change: '最近年化变化', moving_mean: '最近三点移动平均', regression_slope: '线性回归斜率' };

function safeReturn(value: string | null, assetId: string) {
  try {
    if (value) {
      const parsed = new URL(value, location.origin);
      if (parsed.origin === location.origin && /^\/assets\/equipment\/[a-f0-9-]+$/.test(parsed.pathname)) return parsed.pathname + parsed.search;
    }
  } catch { /* Invalid external return context is not navigation authority. */ }
  return `/assets/equipment/${encodeURIComponent(assetId)}`;
}

export function TrendsPage() {
  const { can } = useAuth();
  const [params, setParams] = useState(() => new URLSearchParams(location.search));
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState(1);
  const [state, setState] = useState<{ key: string; data?: TrendData; error?: string }>({ key: '' });
  const assetId = params.get('asset_id') ?? '';
  const type = params.get('test_type') ?? 'DGA', analyte = params.get('analyte') ?? fields[type]?.[0] ?? '';
  const filters = new URLSearchParams({ test_type: type, analyte });
  for (const key of ['start_date','end_date','group_id']) if (params.get(key)) filters.set(key, params.get(key)!);
  const requestKey = assetId + '?' + filters.toString();
  useEffect(() => {
    if (!assetId) return;
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    setState({ key: requestKey });
    void fetch(`/api/condition-analysis/transformers/${encodeURIComponent(assetId)}/trends?${filters}`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 401 ? '登录已失效，请重新登录。' : response.status === 403 ? '没有查看趋势的权限。' : response.status === 404 ? '没有找到该变压器。' : response.status === 422 ? '请选择变压器并检查检测类型、指标和日期范围。' : '趋势数据暂不可用，请重试；持续失败请联系管理员。');
        const data: TrendData = await response.json();
        if (active) setState({ key: requestKey, data });
      }).catch(error => { if (active) setState({ key: requestKey, error: error.name === 'AbortError' ? '请求超时，请重试。' : error.message }); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [requestKey, attempt]);
  function update(patch: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) value ? next.set(key, value) : next.delete(key);
    history.replaceState(null, '', location.pathname + '?' + next);
    setParams(next); setPage(1);
  }
  if (!assetId) return <section className="trend-card"><h2>先选择一台变压器</h2><p>请在资产管理中进入变压器详情，点击“查看变压器趋势”。每台物理设备独立分析，不按序列号拼接历史。</p>{can('assets.read') && <a href="/assets">前往资产管理</a>}</section>;
  const data = state.key === requestKey ? state.data : undefined, error = state.key === requestKey ? state.error : undefined;
  return <div className="transformer-trends">
    {can('assets.read') && <a href={safeReturn(params.get('return_to'), assetId)}>返回设备详情</a>}
    <form className="trend-card trend-filters" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); update({ start_date: String(form.get('start_date') ?? ''), end_date: String(form.get('end_date') ?? ''), group_id: '' }); }}>
      <label>趋势检测类型<select value={type} onChange={e => update({ test_type: e.target.value, analyte: fields[e.target.value][0], group_id: '' })}>{Object.entries(typeNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>趋势指标<select value={analyte} onChange={e => update({ analyte: e.target.value, group_id: '' })}>{(fields[type] ?? []).map(field => <option key={field} value={field}>{typeNames[field] ?? field}</option>)}</select></label>
      <label>趋势开始日期<input name="start_date" type="date" defaultValue={params.get('start_date') ?? ''} /></label><label>趋势结束日期<input name="end_date" type="date" defaultValue={params.get('end_date') ?? ''} /></label><button type="submit">筛选趋势</button>
      <label className="trend-group">可比较方法分组<select disabled={!data?.groups.length} value={params.get('group_id') ?? data?.selected_group?.id ?? ''} onChange={e => update({ group_id: e.target.value })}>
        {!data?.selected_group && <option value={params.get('group_id') ?? ''}>暂无可用分组</option>}{data?.groups.map(group => <option key={group.id} value={group.id}>{group.method_name} · {group.version_label} · {group.unit}</option>)}
      </select></label><p className="trend-help">日期按 America/Chicago；仅比较同一方法版本和单位。默认选择最新观测所属的可比较分组。停用方法不影响历史结果。</p>
    </form>
    {error ? <p role="alert">{error} <button onClick={() => setAttempt(v => v+1)}>重试趋势</button></p> : !data ? <p role="status">正在加载趋势…</p> : <>
      <section className="trend-card" aria-label="变压器身份"><h2>{data.asset.system_asset_number}</h2><p>序列号 {data.asset.serial_number} · {data.asset.model ?? '型号未提供'}</p><p className="trend-help">按物理资产记录分析。设备更换、序列号重复不会合并曲线。</p></section>
      {!data.points.length ? <p role="status">当前条件下没有已定稿的检测结果。</p> : !data.selected_group && <p role="status">当前条件下没有可比较分组；待配置结果仍显示在列表中。若指定分组已不可用，请重新筛选。</p>}
      <section className="trend-card trend-latest" aria-label="最新观测"><div><h2>最新观测</h2><strong>{readingText(data.latest)}</strong>{data.latest && <p>{timeText(data.latest.sampled_at)}</p>}</div><div><h2>最近有效数值</h2><strong>{readingText(data.latest_numeric)}</strong>{data.latest_numeric && <p>{timeText(data.latest_numeric.sampled_at)}</p>}</div><p className="trend-help">均限于所选分组。{data.latest_time_tied ? '最新采样时间有多条记录，按稳定记录顺序展示，未自动取平均。' : '未检出和限值结果原样显示，不替换为零。'}</p></section>
      <section className="trend-card" aria-label="趋势统计"><h2>趋势统计 <small>有效数值 {data.numeric_count}</small></h2><dl className="trend-metrics">{Object.entries(labels).map(([key, label]) => {
        const value = data.statistics[key as keyof typeof labels];
        return <div key={key}><dt>{label}</dt><dd>{value.value === null ? '—' : numberText(value.value)}{value.value !== null && <small> {data.selected_group?.unit}{['annualized_change','regression_slope'].includes(key) ? '/年' : ''}</small>}</dd>{value.reason && <small>{reasonText[value.reason] ?? value.reason}</small>}</div>;
      })}</dl><p className="trend-help">统计覆盖筛选范围，不受下方分页影响。仅计入数值结果；相邻变化及三点均值按连续有效数值计算。年化变化按实际间隔 × 365.25 天折算，回归按实际时间计算，均不是预测或健康判定。</p></section>
      <TrendChart data={data} />
      <section className="trend-card"><h2>检测结果与来源 <small>共 {data.points.length} 条</small></h2><div className="trend-table-scroll"><table aria-label="趋势结果"><thead><tr><th>采样时间</th><th>条码 / 检测</th><th>结果</th><th>方法 / 单位</th><th>统计说明</th><th>采样现场 / 仪器</th><th>详情</th></tr></thead><tbody>{data.points.slice((page-1)*20,page*20).map(point => <tr key={point.test_id}>
        <td>{timeText(point.sampled_at)}</td><td>{can('laboratory.read') ? <a href={`/lab/workbench?barcode=${encodeURIComponent(point.barcode)}`}>{point.barcode}</a> : point.barcode}<small>{point.test_id}</small></td><td>{readingText(point)}</td><td>{point.method_name}<small>{point.version_label} · {point.unit ?? '单位待配置'}</small></td><td>{point.exclusion_reasons.length ? point.exclusion_reasons.map(r => reasonText[r] ?? r).join('；') : '参与统计'}</td><td>{point.site_name}<small>{point.instrument_name ?? '仪器未记录'}</small></td>
        <td><details><summary>查看来源</summary><p>采样设备：{point.equipment_serial}</p><p>检测时间：{timeText(point.measured_at)}</p><p>方法标识：{point.method_version_id}</p><p>质量提示：{point.warnings.join('、') || '无'}</p>{can('laboratory.read') && <a href={`/lab/reports?barcode=${encodeURIComponent(point.barcode)}`}>查看条码报告</a>}</details></td>
      </tr>)}</tbody></table></div><div className="trend-paging"><button disabled={page <= 1} onClick={() => setPage(p => p-1)}>上一页结果</button><span>第 {page} 页</span><button disabled={page*20 >= data.points.length} onClick={() => setPage(p => p+1)}>下一页结果</button></div></section>
    </>}
  </div>;
}
