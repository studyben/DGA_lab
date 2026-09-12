import { useId, useLayoutEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import { useRead } from './assetUi';
import { lifecycleNames } from './assetPresentation';

type Candidate = { id: string; serial_number: string; system_asset_number: string; model: string | null; lifecycle_status: string; lifecycle_revision: number };
export type Catalog = { assets: Candidate[]; sites: { id: string; site_name: string }[]; total: number; page: number };
type Installation = { id: string; parent_asset_id: string | null; site_id: string | null; repair_center: boolean; valid_from: string; valid_to: string | null };
type Timeline = { revision: number; status: string; installations: Installation[];
  events: { id: string; action: string; effective_at: string; reason: string; actor_id: string; before_value: unknown; after_value: unknown }[] };
const actions: Record<string, string> = { ASSET_MOVE: '位置迁移', ASSET_STATUS: '状态变更', TRANSFORMER_REPLACE: '变压器替换', ASSET_HISTORY_CORRECT: '历史修正' };
const utcInput = (value: string) => new Date(value).toISOString().slice(0, 23);
const date = (value: string | null) => value ? `${new Date(value).toISOString().slice(0, 19).replace('T', ' ')} UTC` : '至今';
const errors: Record<string, string> = {
  stale_asset_revision: '资料已被其他操作更新。请刷新后核对再提交。', reason_required: '请填写操作原因。',
  use_history_correction: '生效时间冲突：必须晚于该设备已有的最新变更时间，不能相同或更早。请核对资产时间线；如确需更正过去的安装关系，再使用历史安装修正。', one_move_per_day: '同一设备每天最多迁移一次（按 UTC 日期计算）；填写不同时间也不能绕过此限制。',
  replacement_not_spare: '替换设备必须是维修中心的备用变压器。', conflicting_installation: '有效日期与已有安装关系重叠。',
  cyclic_installation: '该操作会形成设备树循环。', disabled_asset_cannot_install: '停用设备需先恢复状态，不能直接安装。',
  history_gap: '该修正会产生位置历史空档，不能提交。请保留相邻有效日期边界。',
  status_location_conflict: '修正后的状态与位置不一致，不能提交。',
  disabled_parent: '目标父设备或祖先设备在该有效日期内已停用，不能安装。',
  status_requires_repair_center: '请先将设备拆到维修中心，再设置维修中或备用。',
  in_service_requires_site: '在役设备必须有有效的现场关系。', parent_not_at_site: '父设备必须位于客户现场。',
  old_transformer_not_installed: '待更换变压器当前未安装。', invalid_effective_at: '生效日期和时间必须有效，且不能晚于当前时间（UTC）。',
  permission_denied: '当前账号没有操作权限。', csrf_rejected: '会话已更新，请刷新后重试。',
};

function LifecycleForm({ assetId, history }: { assetId: string; history: Timeline }) {
  const { can, session } = useAuth();
  const [action, setAction] = useState('move');
  const [destination, setDestination] = useState('REPAIR_CENTER');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [activeOption, setActiveOption] = useState(-1);
  const pickerId = useId();
  const optionList = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const list = optionList.current;
    const option = list?.querySelector<HTMLElement>('.active-option');
    if (!list || !option || !pickerOpen) return;
    const item = option.getBoundingClientRect(), box = list.getBoundingClientRect();
    if (item.top < box.top) list.scrollTop -= box.top - item.top;
    else if (item.bottom > box.bottom) list.scrollTop += item.bottom - box.bottom;
  }, [activeOption, pickerOpen]);
  const [installation, setInstallation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const catalog = useRead<Catalog>(`/api/assets/catalog?query=${encodeURIComponent(search)}&page=${page}`);
  const selected = catalog.data?.assets.find(a => a.id === target);
  const candidates = catalog.data?.assets.filter(a => a.id !== assetId) ?? [];
  const candidateLabel = (a: Candidate) => `${a.serial_number} · ${a.system_asset_number} · ${a.model ?? '型号未提供'} · ${lifecycleNames[a.lifecycle_status]}`;
  const choose = (a: Candidate) => { setTarget(a.id); setPickerOpen(false); setActiveOption(-1); };
  const original = history.installations.find(i => i.id === installation);
  return <form className="dashboard-filters lifecycle-form" aria-label="受控资产变更" onSubmit={async e => {
    e.preventDefault(); if (busy) return;
    const fields = new FormData(e.currentTarget);
    if ((action === 'replace' || ((action === 'move' || action === 'correct') && destination === 'PARENT')) && !selected) {
      setError('请从下拉搜索结果中选择目标设备，仅输入文字不能提交。'); return;
    }
    const common = { reason: String(fields.get('reason') ?? ''), expected_revision: history.revision };
    // datetime-local is explicitly entered in UTC, not the browser's local zone.
    const effective_at = `${fields.get('effective_at')}Z`;
    if (new Date(effective_at).getTime() > Date.now()) { setError(errors.invalid_effective_at); return; }
    let body: object;
    if (action === 'status') body = { ...common, effective_at, status: fields.get('status') };
    else if (action === 'replace') {
      if (!selected) { setError('请搜索并选择目标设备。'); return; }
      body = { ...common, effective_at, replacement_id: target, replacement_revision: selected.lifecycle_revision };
    } else {
      const relation = { parent_asset_id: destination === 'PARENT' ? target : null, site_id: destination === 'SITE' ? fields.get('site') : null };
      body = action === 'correct' ? { ...common, ...relation, installation_id: installation,
        valid_from: effective_at, valid_to: fields.get('valid_to') ? `${fields.get('valid_to')}Z` : null, repair_center: destination === 'REPAIR_CENTER' }
        : { ...common, ...relation, destination, effective_at };
    }
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/assets/equipment/${encodeURIComponent(assetId)}/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
        body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(errors[result.code] ?? `操作未完成（${result.code ?? response.status}），请检查输入或刷新后重试。`);
      window.location.reload();
    } catch (failure) { setError(failure instanceof Error ? failure.message : '无法确认提交结果，请刷新时间线后再操作。'); }
    finally { setBusy(false); }
  }}>
    <fieldset disabled={busy}>
      <legend>受控资产变更</legend>
      <label>资产操作<select value={action} onChange={e => { setAction(e.target.value); setTarget(''); }}><option value="move">位置迁移 / 安装拆除</option><option value="status">状态变更 / 恢复</option><option value="replace">变压器替换</option>{can('assets.history.correct') && <option value="correct">历史安装修正</option>}</select></label>
      {action === 'correct' && <><p>修正保留前后值和审计，不改写油样或报告快照。</p><label>历史安装记录<select required value={installation} onChange={e => { setInstallation(e.target.value); const row = history.installations.find(i => i.id === e.target.value); setDestination(row?.repair_center ? 'REPAIR_CENTER' : row?.site_id ? 'SITE' : 'PARENT'); setTarget(row?.parent_asset_id ?? ''); }}><option value="">请选择</option>{history.installations.map(i => <option key={i.id} value={i.id}>{date(i.valid_from)} — {date(i.valid_to)} · {i.repair_center ? '维修中心' : i.site_id ? '现场' : '父设备'}</option>)}</select></label></>}
      {(action === 'move' || action === 'correct') && <label>目标位置<select value={destination} onChange={e => { setDestination(e.target.value); setTarget(''); }}><option value="REPAIR_CENTER">维修中心</option><option value="SITE">客户现场（根资产）</option><option value="PARENT">安装到父设备</option></select></label>}
      {(action === 'move' || action === 'correct') && destination === 'SITE' && <label>客户现场<select name="site" required key={installation} defaultValue={original?.site_id ?? ''}><option value="">请选择</option>{catalog.data?.sites.map(s => <option key={s.id} value={s.id}>{s.site_name}</option>)}</select></label>}
      {(action === 'replace' || ((action === 'move' || action === 'correct') && destination === 'PARENT')) && <>
        <div className="asset-combobox" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setPickerOpen(false); }}>
          <label htmlFor={pickerId}>目标设备</label>
          <div className="asset-combobox-input">
            <input id={pickerId} role="combobox" autoComplete="off" aria-autocomplete="list" aria-expanded={pickerOpen}
              aria-controls={`${pickerId}-list`} aria-activedescendant={pickerOpen && candidates[activeOption] ? `${pickerId}-${candidates[activeOption].id}` : undefined}
              placeholder="输入序列号、资产编号或型号搜索" value={selected ? candidateLabel(selected) : search}
              onFocus={() => setPickerOpen(true)} onClick={() => setPickerOpen(true)}
              onChange={e => { setSearch(e.target.value.slice(0, 200)); setPage(1); setTarget(''); setActiveOption(-1); setPickerOpen(true); }}
              onKeyDown={e => {
                if (e.key === 'Escape') { e.preventDefault(); setPickerOpen(false); }
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); setPickerOpen(true); setActiveOption(i => candidates.length ? Math.max(0, Math.min(candidates.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1))) : -1); }
                if (e.key === 'Enter') { e.preventDefault(); if (pickerOpen && candidates[activeOption]) choose(candidates[activeOption]); }
              }} />
            <button type="button" aria-label="清空目标设备" onClick={() => { setTarget(''); setSearch(''); setPage(1); setActiveOption(-1); setPickerOpen(true); }}>清空</button>
          </div>
          {pickerOpen && <div className="asset-combobox-popup">
            {!catalog.data && !catalog.error && <p role="status">正在搜索设备…</p>}
            {catalog.data && candidates.length === 0 && <p role="status">本页没有匹配设备，请修改搜索条件或翻页。</p>}
            <div ref={optionList} id={`${pickerId}-list`} role="listbox" aria-label="目标设备搜索结果">
              {candidates.map((a, index) => <button key={a.id} id={`${pickerId}-${a.id}`} type="button" role="option" aria-selected={a.id === target}
                className={index === activeOption ? 'active-option' : undefined} onMouseDown={e => e.preventDefault()} onClick={() => choose(a)}>{candidateLabel(a)}</button>)}
            </div>
            <div className="table-paging">
              <button type="button" disabled={page <= 1} onClick={() => { setPage(page-1); setTarget(''); setActiveOption(-1); }}>上一页候选</button>
              <span>第 {page} 页</span>
              <button type="button" disabled={!catalog.data || page*20 >= catalog.data.total} onClick={() => { setPage(page+1); setTarget(''); setActiveOption(-1); }}>下一页候选</button>
            </div>
          </div>}
        </div>
      </>}
      {catalog.error && <p role="alert">{catalog.error}<button type="button" onClick={catalog.retry}>重试候选</button></p>}
      {action === 'status' && <label>目标状态<select name="status"><option value="SPARE">备用</option><option value="UNDER_REPAIR">维修中</option><option value="IN_SERVICE">在役</option><option value="RETIRED">停用</option></select></label>}
      <label>生效日期和时间（UTC）<input key={`${action}-${installation}`} name="effective_at" type="datetime-local" step="any" required defaultValue={action === 'correct' && original ? utcInput(original.valid_from) : undefined} /></label>
      <p>请填写 UTC 时间，不会按电脑所在时区转换。同一天可按时间先后变更状态；新变更必须晚于已有记录，且不能在未来。</p>
      {action === 'correct' && <label>失效日期和时间（UTC，留空表示至今）<input key={installation} name="valid_to" type="datetime-local" step="any" defaultValue={original?.valid_to ? utcInput(original.valid_to) : ''} /></label>}
      <label>操作原因<textarea name="reason" required maxLength={1000} /></label>
      {action === 'replace' && <p>提交后，旧变压器进入维修中心，新变压器安装到原父设备；两台设备的检测历史分别保留。</p>}
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? '正在提交…' : '提交资产变更'}</button>
    </fieldset>
  </form>;
}

export function LifecyclePanel({ assetId }: { assetId: string }) {
  const { can } = useAuth();
  const { data, error, retry } = useRead<Timeline>(`/api/assets/equipment/${encodeURIComponent(assetId)}/lifecycle`);
  const [filter, setFilter] = useState('');
  if (error) return <p role="alert">{error}<button onClick={retry}>重试资产历史</button></p>;
  if (!data) return <p role="status">正在加载资产历史…</p>;
  return <section className="dashboard-table-panel" aria-label="资产时间线"><h2>资产时间线</h2>
    <label>时间线筛选<input value={filter} onChange={e => setFilter(e.target.value)} placeholder="原因或操作类型" /></label>
    <ul>{data.installations.map(i => <li key={i.id}>{date(i.valid_from)} — {date(i.valid_to)}：{i.repair_center ? '维修中心' : i.site_id ? <a href={`/assets/sites/${i.site_id}`}>客户现场</a> : <a href={`/assets/equipment/${i.parent_asset_id}`}>父设备</a>}</li>)}</ul>
    {data.events.some(e => e.action === 'ASSET_HISTORY_CORRECT') && <p role="status">安装历史已修正。油样和报告快照保持原值，请核对采样时的关联信息。</p>}
    <ol>{data.events.filter(e => `${e.reason} ${actions[e.action]}`.includes(filter)).map(e => <li key={e.id}><strong>{actions[e.action] ?? e.action}</strong> · {date(e.effective_at)} · {e.reason}<details><summary>查看审计前后值</summary><p>操作人 ID：{e.actor_id}</p><pre>{JSON.stringify({ before: e.before_value, after: e.after_value }, null, 2)}</pre></details></li>)}</ol>
    {data.events.length === 0 && <p>暂无变更事件。早期状态的生效时间未记录。</p>}
    {can('assets.write') && <LifecycleForm assetId={assetId} history={data} />}
  </section>;
}

export function RepairCenterPage() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const { data, error, retry } = useRead<Catalog>(`/api/assets/catalog?repair_only=true&query=${encodeURIComponent(query)}&page=${page}`);
  return <section className="asset-dashboard dashboard-table-panel repair-center"><h2>维修中心设备</h2><form className="dashboard-filters" onSubmit={e => { e.preventDefault(); setQuery(String(new FormData(e.currentTarget).get('query') ?? '')); setPage(1); }}><label>资产搜索<input name="query" maxLength={200} placeholder="序列号、资产编号或型号" /></label><button type="submit">筛选资产</button></form>
    {error ? <p role="alert">{error}<button onClick={retry}>重试</button></p> : !data ? <p role="status">正在加载…</p> : <>
      <div className="dashboard-table-scroll">
        <table aria-label="维修中心清单">
          <thead><tr><th scope="col">序列号</th><th scope="col">资产编号</th><th scope="col">型号</th><th scope="col">状态</th></tr></thead>
          <tbody>{data.assets.map(a => <tr key={a.id}><td><a href={`/assets/equipment/${a.id}`}>{a.serial_number}</a></td><td>{a.system_asset_number}</td><td>{a.model ?? '未提供'}</td><td>{lifecycleNames[a.lifecycle_status]}</td></tr>)}</tbody>
        </table>
      </div>
      {data.assets.length === 0 && <p className="dashboard-empty" role="status">没有符合筛选条件的维修中心设备。</p>}
      <nav className="table-paging" aria-label="维修中心分页">
        <span>共 {data.total} 条 · 第 {page} 页</span>
        <button type="button" disabled={page<=1} onClick={() => setPage(page-1)}>上一页</button>
        <button type="button" disabled={page*20>=data.total} onClick={() => setPage(page+1)}>下一页</button>
      </nav>
    </>}
  </section>;
}
