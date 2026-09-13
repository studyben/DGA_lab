import { useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import { OfficialAssetSelector, type OfficialAssetSelection } from '../assets/OfficialAssetSelector';
import { chicagoTime, SampleLedgerPage, useLaboratoryRead } from './OperationsPages';

type Container = { id: string; container_number: string; status: string; revision: number; allowed_targets: string[] };
type OperationEvent = { id: string; container_id: string | null; action_code: string; reason: string; actor_id: string; occurred_at: string; before_value: Record<string, unknown>; after_value: Record<string, unknown> };
type Operations = {
  sample: { barcode_value: string; identity_status: string; sampled_at: string; site_name: string; equipment_serial: string };
  testing_status: string;
  operations_revision: number;
  containers: Container[];
  history: OperationEvent[];
};
const containerLabels: Record<string, string> = { RECEIVED: '已接收', IN_USE: '使用中', RETAINED: '留样', EXHAUSTED: '已耗尽', BROKEN: '已破损', DISPOSED: '已处置' };
const messages: Record<string, string> = {
  stale_sample: '油样基础信息已被更新，请重新读取并核对采样时间后选择正式资产。',
  stale_container: '容器状态已被其他操作更新，请重新读取后核对当前状态。',
  identity_confirmation_not_allowed: '此油样已关联资产或已定稿，不能再次确认身份。',
  invalid_container_transition: '当前容器状态不允许此变更，请重新读取后选择。',
  permission_denied: '当前账号没有操作权限。',
  csrf_rejected: '会话已更新，请刷新页面后重试。',
  sample_requires_transformer: '请选择采样时对应的变压器。',
};

function ContainerForm({ container, disabled, submit }: { container: Container; disabled: boolean; submit: (target: string, reason: string) => Promise<boolean> }) {
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  return <fieldset className="lab-container" disabled={disabled}>
    <legend>{container.container_number}</legend>
    <p>当前状态：{containerLabels[container.status]}</p>
    {container.allowed_targets.length ? <form className="lab-toolbar" onSubmit={e => {
      e.preventDefault(); void submit(target, reason).then(saved => { if (saved) { setTarget(''); setReason(''); } });
    }}>
      <label>目标状态<select value={target} onChange={e => setTarget(e.target.value)} required><option value="">选择状态</option>{container.allowed_targets.map(t => <option key={t} value={t}>{containerLabels[t]}</option>)}</select></label>
      <label className="lab-reason">容器变更原因<textarea maxLength={500} rows={2} value={reason} onChange={e => setReason(e.target.value)} required /></label>
      <button disabled={!target || !reason.trim()}>保存容器状态</button>
    </form> : <p>此容器已处置，不可再变更。</p>}
  </fieldset>;
}

export function SampleOperationsPanel({ barcode, identity = false, onChanged }: { barcode: string; identity?: boolean; onChanged?: () => void }) {
  const { session, can } = useAuth();
  const path = '/api/laboratory/operations/'+encodeURIComponent(barcode);
  const read = useLaboratoryRead<Operations>(path);
  const [selection, setSelection] = useState<OfficialAssetSelection | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [needsReload, setNeedsReload] = useState(false);
  const submitting = useRef(false);
  const [selectorRevision, setSelectorRevision] = useState(0);

  function reload() {
    setSelection(null); setSelectorRevision(n => n+1); setNeedsReload(false); setError(''); read.retry();
  }
  async function submit(suffix: string, payload: unknown, success: string) {
    if (submitting.current || needsReload || !can('laboratory.write') || !session) return false;
    submitting.current = true; setBusy(true); setError(''); setNotice('');
    try {
      const response = await fetch(path+suffix, { method: 'POST', credentials: 'same-origin', cache: 'no-store',
        signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(payload) });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        if (response.status === 409 || response.status >= 500) setNeedsReload(true);
        setError(messages[result.code] ?? (response.status === 422 ? '输入无效，请核对目标、原因和时间。' : '操作未成功，请检查权限或稍后重试。'));
        return false;
      }
      setNotice(success); setSelection(null); read.retry(); onChanged?.(); return true;
    } catch {
      setError('未能确认提交结果。请重新读取状态后再操作，避免重复提交。'); setNeedsReload(true); return false;
    } finally { submitting.current = false; setBusy(false); }
  }
  const data = read.data;
  const pending = data?.sample.identity_status === 'IDENTITY_PENDING';
  return <section className="lab-operations lab-panel" aria-label="油样运营信息">
    <div className="lab-toolbar"><h2>{identity ? '核实油样身份' : '样品容器与操作历史'}</h2><button disabled={busy} onClick={reload}>重新读取状态</button></div>
    {notice && <p role="status">{notice}</p>}
    {(error || read.error) && <p role="alert">{error || read.error}</p>}
    {!data && !read.error && <p role="status">正在读取油样运营信息…</p>}
    {data && <>
      <p>{data.sample.barcode_value} · {data.sample.site_name} · {data.sample.equipment_serial}</p>
      <p>采样时间：{chicagoTime(data.sample.sampled_at)}（America/Chicago）· {pending ? '身份待确认' : '已关联正式资产'}</p>
      {identity && pending && data.testing_status === 'OPEN' && can('laboratory.write') && <>
        <fieldset disabled={busy || needsReload} className="lab-identity-selection">
          <legend>选择采样时的正式资产</legend>
          <OfficialAssetSelector key={selectorRevision} sampledAt={data.sample.sampled_at} onSelect={setSelection} />
          {selection && <p role="status">待关联：{selection.site_name} · {selection.asset.serial_number} · {selection.asset.system_asset_number}</p>}
          <form className="lab-toolbar" onSubmit={e => { e.preventDefault(); if (selection) void submit('/identity', { formal_asset_id: selection.asset.id, expected_revision: data.operations_revision, reason }, '身份关联已保存，条码与检测记录已保留。'); }}>
            <label className="lab-reason">身份确认原因<textarea value={reason} onChange={e => setReason(e.target.value)} maxLength={500} rows={2} required /></label>
            <button disabled={!selection || !reason.trim()}>确认关联正式资产</button>
          </form>
        </fieldset>
      </>}
      {can('laboratory.write') && <p><a href={'/lab/workbench?barcode='+encodeURIComponent(barcode)+'&return_to='+encodeURIComponent('/lab/identity?barcode='+barcode)}>按此条码继续检测</a>{!identity && pending && <> · <a href={'/lab/identity?barcode='+encodeURIComponent(barcode)}>前往核实身份</a></>}</p>}
      {!identity && <><p>容器状态记录实物使用情况，不改变已定稿检测或报告。</p>{data.containers.map(container => can('laboratory.write') ? <ContainerForm key={container.id} container={container} disabled={busy || needsReload} submit={(target, changeReason) => submit('/containers/'+container.id, { target, reason: changeReason, expected_revision: container.revision }, '容器状态已保存。')} /> : <p key={container.id}>{container.container_number} · {containerLabels[container.status]}</p>)}</>}
      <details><summary>操作历史（{data.history.length} 条）</summary>{data.history.length ? <ol>{data.history.map(event => <li key={event.id}><strong>{event.action_code === 'SAMPLE_ASSET_ASSOCIATED' ? '确认正式资产' : '容器状态变更'}</strong> · {chicagoTime(event.occurred_at)} · {event.reason}<p>操作人：{event.actor_id}</p>{event.container_id && <p>{data.containers.find(c => c.id === event.container_id)?.container_number}：{containerLabels[String(event.before_value.status)]} → {containerLabels[String(event.after_value.status)]}</p>}<details><summary>变更前后记录</summary><pre>{JSON.stringify({ before: event.before_value, after: event.after_value }, null, 2)}</pre></details></li>)}</ol> : <p>尚无身份确认或容器变更记录。</p>}</details>
    </>}
  </section>;
}

export function IdentityPage() {
  const [barcode, setBarcode] = useState('');
  const [revision, setRevision] = useState(0);
  return <><SampleLedgerPage key={revision} pending onChoose={setBarcode} />{barcode && <SampleOperationsPanel key={barcode} barcode={barcode} identity onChanged={() => setRevision(n => n+1)} />}</>;
}

export function LaboratoryLedgerPage() {
  const [barcode, setBarcode] = useState('');
  return <><SampleLedgerPage onInspect={setBarcode} />{barcode && <SampleOperationsPanel key={barcode} barcode={barcode} />}</>;
}
