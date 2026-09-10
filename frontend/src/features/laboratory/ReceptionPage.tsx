import { FormEvent, useState } from 'react';

import { useAuth } from '../../Auth';
import {
  OfficialAssetSelection,
  OfficialAssetSelector,
} from '../assets/OfficialAssetSelector';
import { Code39Barcode } from './Code39Barcode';


type IdentityStatus = 'ASSOCIATED' | 'IDENTITY_PENDING';

type Sample = {
  id: string;
  sample_number: string;
  barcode_value: string;
  identity_status: IdentityStatus;
  sampled_at: string;
  received_at: string;
  site_name: string;
  equipment_serial: string;
  notes: string | null;
  formal_asset_id: string | null;
  asset_snapshot: null | {
    customer_name: string;
    site_name: string;
    site_location: string | null;
    equipment_path: { serial_number: string }[];
  };
  containers: { id: string; container_number: string; ordinal: number }[];
};


function toIso(value: string, label: string) {
  const instant = new Date(value);
  if (Number.isNaN(instant.valueOf())) throw new Error(`请填写有效的${label}。`);
  return instant.toISOString();
}


function LabelPreview({ sample, onPrint }: { sample: Sample; onPrint: () => Promise<void> }) {
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState('');
  return <section className="label-panel" role="region" aria-label="条码标签预览">
    <div className="section-heading no-print">
      <div><span className="step">04 / 标签</span><h2>条码标签预览</h2></div>
      <button className="primary-action" type="button" disabled={printing} onClick={async () => {
        setPrinting(true); setError('');
        try { await onPrint(); } catch (failure) {
          setError(failure instanceof Error ? failure.message : '无法记录打印操作。');
        } finally { setPrinting(false); }
      }}>{printing ? '准备打印…' : '打印条码标签'}</button>
    </div>
    {error && <p role="alert" className="form-error no-print">{error}</p>}
    <article className="barcode-label">
      <div className="label-brand"><strong>SUNGROW</strong><span>绝缘油样品</span></div>
      <Code39Barcode value={sample.barcode_value} />
      <strong className="barcode-value" data-testid="barcode-value">{sample.barcode_value}</strong>
      <dl>
        <div><dt>现场</dt><dd>{sample.asset_snapshot?.site_name ?? sample.site_name}</dd></div>
        <div><dt>设备</dt><dd>{sample.equipment_serial}</dd></div>
        <div><dt>采样</dt><dd>{new Date(sample.sampled_at).toLocaleString('zh-CN')}</dd></div>
      </dl>
      <p>容器 {sample.containers.length} 只</p>
    </article>
  </section>;
}


export function ReceptionPage() {
  const { session } = useAuth();
  const [sampledAt, setSampledAt] = useState('');
  const [receivedAt, setReceivedAt] = useState('');
  const [identityStatus, setIdentityStatus] = useState<IdentityStatus>('ASSOCIATED');
  const [selection, setSelection] = useState<OfficialAssetSelection | null>(null);
  const [siteName, setSiteName] = useState('');
  const [equipmentSerial, setEquipmentSerial] = useState('');
  const [notes, setNotes] = useState('');
  const [containerCount, setContainerCount] = useState('1');
  const [created, setCreated] = useState<Sample | null>(null);
  const [lookupBarcode, setLookupBarcode] = useState('');
  const [found, setFound] = useState<Sample | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lookupError, setLookupError] = useState('');

  function chooseAsset(value: OfficialAssetSelection) {
    setSelection(value);
    setSiteName(value.site_name);
    setEquipmentSerial(value.asset.serial_number);
  }

  async function receive(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (identityStatus === 'ASSOCIATED' && !selection) {
      setError('请先搜索并明确选择正式变压器。');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/laboratory/samples', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
        body: JSON.stringify({
          sampled_at: toIso(sampledAt, '采样时间'),
          received_at: toIso(receivedAt, '收样时间'),
          site_name: siteName.trim(),
          equipment_serial: equipmentSerial.trim(),
          notes: notes.trim() || null,
          container_count: Number(containerCount),
          identity_status: identityStatus,
          formal_asset_id: identityStatus === 'ASSOCIATED' ? selection?.asset.id : null,
        }),
      });
      if (!response.ok) throw new Error('无法登记油样，请检查信息后重试。');
      const sample = await response.json() as Sample;
      setCreated(sample);
      setFound(null);
      setLookupBarcode(sample.barcode_value);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '无法登记油样。');
    } finally { setBusy(false); }
  }

  async function lookup(event: FormEvent) {
    event.preventDefault();
    setLookupError(''); setFound(null);
    try {
      const response = await fetch(`/api/laboratory/samples/by-barcode/${encodeURIComponent(lookupBarcode.trim())}`, {
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      if (response.status === 404) throw new Error('没有找到该油样条码。');
      if (!response.ok) throw new Error('无法查询条码，请稍后重试。');
      setFound(await response.json() as Sample);
    } catch (failure) {
      setLookupError(failure instanceof Error ? failure.message : '无法查询条码。');
    }
  }

  async function printLabel(sample: Sample) {
    const response = await fetch(`/api/laboratory/samples/${encodeURIComponent(sample.barcode_value)}/label-prints`, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
      headers: { 'X-CSRF-Token': session?.csrf_token ?? '' },
    });
    if (!response.ok) throw new Error('无法记录打印操作，请重试。');
    window.print();
  }

  return <div className="reception-layout">
    <section className="reception-panel" aria-labelledby="sample-context-title">
      <div className="section-heading">
        <div><span className="step">01 / 采样信息</span><h2 id="sample-context-title">确认采样时间与身份方式</h2></div>
      </div>
      <label className="sample-time">采样时间
        <input type="datetime-local" value={sampledAt} required onChange={event => {
          setSampledAt(event.target.value); setSelection(null); setCreated(null);
        }} />
      </label>
      <fieldset className="identity-choice">
        <legend>油样身份</legend>
        <label><input type="radio" name="identity" checked={identityStatus === 'ASSOCIATED'} onChange={() => {
          setIdentityStatus('ASSOCIATED'); setSelection(null); setCreated(null);
        }} /> 关联正式资产</label>
        <label><input type="radio" name="identity" checked={identityStatus === 'IDENTITY_PENDING'} onChange={() => {
          setIdentityStatus('IDENTITY_PENDING'); setSelection(null); setCreated(null);
        }} /> 身份待确认</label>
      </fieldset>
      <p className="field-help">正式关联会冻结采样时的客户、现场和设备路径；待确认不会创建临时资产。</p>
    </section>

    {identityStatus === 'ASSOCIATED' && <OfficialAssetSelector sampledAt={sampledAt} onSelect={chooseAsset} />}
    <section className={`selection-summary ${selection ? 'selected' : ''}`} aria-label="资产关联结果">
      {selection ? <div role="status">
        <span className="selection-mark" aria-hidden="true">✓</span>
        <div><strong>已关联 {selection.asset.serial_number}</strong>
          <p>{selection.customer_name} · {selection.site_name} · {selection.equipment_path.map(asset => asset.serial_number).join(' → ')}</p>
        </div>
      </div> : <p>{identityStatus === 'ASSOCIATED' ? '尚未选择正式资产' : '将保存为身份待确认，不创建资产记录'}</p>}
    </section>

    <section className="reception-panel" aria-labelledby="reception-details-title">
      <div className="section-heading">
        <div><span className="step">03 / 收样登记</span><h2 id="reception-details-title">填写油样基本信息</h2></div>
      </div>
      <form className="reception-form" onSubmit={receive}>
        <label>收样时间<input type="datetime-local" value={receivedAt} onChange={event => setReceivedAt(event.target.value)} required /></label>
        <label>现场名称<input value={siteName} onChange={event => setSiteName(event.target.value)} maxLength={200} required disabled={identityStatus === 'ASSOCIATED'} /></label>
        <label>设备序列号<input value={equipmentSerial} onChange={event => setEquipmentSerial(event.target.value)} maxLength={160} required disabled={identityStatus === 'ASSOCIATED'} /></label>
        <label>样品容器数量<input type="number" min="1" max="20" value={containerCount} onChange={event => setContainerCount(event.target.value)} required /></label>
        <label className="wide-field">备注<textarea value={notes} onChange={event => setNotes(event.target.value)} maxLength={2000} rows={3} /></label>
        {error && <p role="alert" className="form-error wide-field">{error}</p>}
        <button className="primary-action wide-field" type="submit" disabled={busy}>{busy ? '登记中…' : '登记油样并生成条码'}</button>
      </form>
    </section>

    {created && <LabelPreview sample={created} onPrint={() => printLabel(created)} />}

    <section className="lookup-panel" aria-labelledby="barcode-lookup-title">
      <div className="section-heading">
        <div><span className="step">扫码取回</span><h2 id="barcode-lookup-title">查询已有油样</h2></div>
      </div>
      <form className="asset-search-form" onSubmit={lookup}>
        <label>扫描或输入油样条码<input value={lookupBarcode} onChange={event => setLookupBarcode(event.target.value.toUpperCase())} maxLength={40} required /></label>
        <button type="submit">查询条码</button>
      </form>
      {lookupError && <p role="alert" className="form-error">{lookupError}</p>}
      {found && <article className="lookup-result" role="region" aria-label="条码查询结果">
        <strong>{found.sample_number}</strong>
        <p>{found.asset_snapshot?.customer_name ?? '身份待确认'} · {found.asset_snapshot?.site_name ?? found.site_name} · {found.equipment_serial}</p>
        <span>{found.containers.length} 只样品容器</span>
      </article>}
    </section>
  </div>;
}
