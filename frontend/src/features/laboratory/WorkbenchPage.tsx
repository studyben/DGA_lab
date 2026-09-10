import { FormEvent, useMemo, useState } from 'react';

import { useAuth } from '../../Auth';

type TestType = 'DGA' | 'MOISTURE' | 'BREAKDOWN_VOLTAGE';
type Qualifier = 'EQ' | 'ND' | 'LT' | 'GT';
type Measurement = { qualifier: Qualifier; value: number | null };
type MethodField = {
  code: string;
  display_name: string;
  unit_code: string | null;
  display_decimal_places: number | null;
  detection_limit: number | null;
};
type Method = {
  id: string;
  test_type: TestType;
  display_name: string;
  standard_reference: string | null;
  version_label: string;
  fields: MethodField[];
};
type TestRecord = {
  id: string;
  test_type: TestType;
  method: Method;
  measured_at: string;
  instrument_name: string | null;
  analyst_user_id: string;
  notes: string | null;
  result: Record<string, Measurement>;
  attachments: { id: string; filename: string; content_type: string; byte_size: number }[];
  created_at: string;
  updated_at: string;
};
type Workbench = {
  sample: {
    sample_number: string;
    barcode_value: string;
    identity_status: 'ASSOCIATED' | 'IDENTITY_PENDING';
    sampled_at: string;
    received_at: string;
    site_name: string;
    equipment_serial: string;
    notes: string | null;
    containers: { container_number: string; ordinal: number }[];
  };
  testing_status: 'OPEN' | 'FINALIZED';
  methods: Method[];
  tests: TestRecord[];
};

const TYPE_LABEL: Record<TestType, string> = {
  DGA: 'DGA',
  MOISTURE: '微水',
  BREAKDOWN_VOLTAGE: '击穿电压',
};

function localDateTime(value: string) {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function resultMeasurements(record: TestRecord) {
  return record.test_type === 'DGA'
    ? record.result
    : { [record.method.fields[0].code.toLowerCase()]: record.result.result };
}

async function attachmentPayload(file: File | null) {
  if (!file) return null;
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  bytes.forEach(value => { binary += String.fromCharCode(value); });
  return { filename: file.name, content_type: file.type || 'application/octet-stream', content_base64: btoa(binary) };
}

export function WorkbenchPage() {
  const { session } = useAuth();
  const [barcode, setBarcode] = useState('');
  const [data, setData] = useState<Workbench | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<TestRecord | null>(null);
  const [testType, setTestType] = useState<TestType>('DGA');
  const [measuredAt, setMeasuredAt] = useState('');
  const [instrument, setInstrument] = useState('');
  const [notes, setNotes] = useState('');
  const [measurements, setMeasurements] = useState<Record<string, { qualifier: Qualifier; value: string }>>({});
  const [attachment, setAttachment] = useState<File | null>(null);
  const method = useMemo(
    () => data?.methods.find(item => item.test_type === testType) ?? null,
    [data, testType],
  );

  async function load(value = barcode) {
    setError(''); setBusy(true);
    try {
      const response = await fetch(`/api/laboratory/workbench/${encodeURIComponent(value.trim())}`, {
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      if (response.status === 404) throw new Error('没有找到该油样条码。');
      if (!response.ok) throw new Error('无法加载检测工作台，请稍后重试。');
      const loaded = await response.json() as Workbench;
      setData(loaded); setBarcode(loaded.sample.barcode_value); setShowForm(false); setEditing(null);
    } catch (failure) {
      setData(null); setError(failure instanceof Error ? failure.message : '无法加载检测工作台。');
    } finally { setBusy(false); }
  }

  function beginCreate(type: TestType) {
    setEditing(null); setTestType(type); setMeasuredAt(localDateTime(new Date().toISOString()));
    setInstrument(''); setNotes(''); setMeasurements({}); setAttachment(null); setShowForm(true);
  }

  function beginEdit(record: TestRecord) {
    const current = resultMeasurements(record);
    setEditing(record); setTestType(record.test_type); setMeasuredAt(localDateTime(record.measured_at));
    setInstrument(record.instrument_name ?? ''); setNotes(record.notes ?? '');
    setMeasurements(Object.fromEntries(Object.entries(current).map(([code, item]) => [
      code.toLowerCase(), { qualifier: item.qualifier, value: item.value === null ? '' : String(item.value) },
    ])));
    setAttachment(null); setShowForm(true);
  }

  function measurement(code: string) {
    return measurements[code.toLowerCase()] ?? { qualifier: 'EQ' as Qualifier, value: '' };
  }

  function setMeasurement(code: string, change: Partial<{ qualifier: Qualifier; value: string }>) {
    const key = code.toLowerCase();
    setMeasurements(current => ({ ...current, [key]: { ...measurement(key), ...change } }));
  }

  async function saveTest(event: FormEvent) {
    event.preventDefault();
    if (!data || !method) return;
    setError(''); setBusy(true);
    try {
      const values = Object.fromEntries(method.fields.map(field => {
        const item = measurement(field.code);
        return [field.code.toLowerCase(), {
          qualifier: item.qualifier,
          value: item.qualifier === 'ND' ? null : item.value,
        }];
      }));
      const result = testType === 'DGA'
        ? { kind: 'DGA', ...values }
        : { kind: testType, result: values[method.fields[0].code.toLowerCase()] };
      const payload = {
        test_type: testType,
        method_version_id: method.id,
        measured_at: new Date(measuredAt).toISOString(),
        instrument_name: instrument.trim() || null,
        notes: notes.trim() || null,
        result,
        attachment: await attachmentPayload(attachment),
      };
      const endpoint = editing
        ? `/api/laboratory/samples/${encodeURIComponent(data.sample.barcode_value)}/tests/${editing.id}`
        : `/api/laboratory/samples/${encodeURIComponent(data.sample.barcode_value)}/tests`;
      const response = await fetch(endpoint, {
        method: editing ? 'PUT' : 'POST', credentials: 'same-origin', cache: 'no-store',
        signal: AbortSignal.timeout(15000),
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('无法保存检测数据，请检查数值与限定符。');
      await load(data.sample.barcode_value);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '无法保存检测数据。'); setBusy(false);
    }
  }

  async function remove(record: TestRecord) {
    if (!data) return;
    const reason = window.prompt('请输入删除原因');
    if (!reason?.trim()) return;
    setError(''); setBusy(true);
    try {
      const response = await fetch(
        `/api/laboratory/samples/${encodeURIComponent(data.sample.barcode_value)}/tests/${record.id}`,
        { method: 'DELETE', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
          body: JSON.stringify({ reason }) },
      );
      if (!response.ok) throw new Error('无法删除检测记录。');
      await load(data.sample.barcode_value);
    } catch (failure) { setError(failure instanceof Error ? failure.message : '无法删除检测记录。'); setBusy(false); }
  }

  async function saveBasics(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data) return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/laboratory/samples/${encodeURIComponent(data.sample.barcode_value)}`, {
        method: 'PATCH', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
        body: JSON.stringify({
          sampled_at: new Date(String(values.get('sampled_at'))).toISOString(),
          received_at: new Date(String(values.get('received_at'))).toISOString(),
          site_name: values.get('site_name'), equipment_serial: values.get('equipment_serial'),
          notes: values.get('notes') || null,
        }),
      });
      if (!response.ok) throw new Error('无法更新油样基础信息。');
      setData(await response.json() as Workbench);
    } catch (failure) { setError(failure instanceof Error ? failure.message : '无法更新油样基础信息。'); }
    finally { setBusy(false); }
  }

  return <div className="workbench-layout">
    <section className="lookup-panel" aria-labelledby="workbench-scan-title">
      <div className="section-heading"><div><span className="step">01 / 扫码</span><h2 id="workbench-scan-title">进入油样检测</h2></div></div>
      <form className="asset-search-form" onSubmit={event => { event.preventDefault(); void load(); }}>
        <label>扫描或输入油样条码<input aria-label="扫描或输入油样条码" autoFocus value={barcode} onChange={event => setBarcode(event.target.value.toUpperCase())} required /></label>
        <button type="submit" disabled={busy}>{busy ? '加载中…' : '加载油样'}</button>
      </form>
      {error && <p role="alert" className="form-error">{error}</p>}
    </section>

    {data && <>
      <section className="workbench-summary">
        <div><span className="step">02 / 油样</span><h2>{data.sample.sample_number}</h2></div>
        <span className={`status-pill ${data.testing_status === 'OPEN' ? 'open' : ''}`}>{data.testing_status === 'OPEN' ? '检测中' : '已定稿'}</span>
        <p>{data.sample.site_name} · {data.sample.equipment_serial} · {data.sample.containers.length} 只容器</p>
      </section>

      <section className="reception-panel">
        <div className="section-heading"><div><span className="step">03 / 基础信息</span><h2>核对或修正油样信息</h2></div></div>
        <form className="reception-form" onSubmit={saveBasics}>
          <label>采样时间<input name="sampled_at" type="datetime-local" defaultValue={localDateTime(data.sample.sampled_at)} required /></label>
          <label>收样时间<input name="received_at" type="datetime-local" defaultValue={localDateTime(data.sample.received_at)} required /></label>
          <label>现场名称<input name="site_name" defaultValue={data.sample.site_name} disabled={data.sample.identity_status === 'ASSOCIATED'} required /></label>
          <label>设备序列号<input name="equipment_serial" defaultValue={data.sample.equipment_serial} disabled={data.sample.identity_status === 'ASSOCIATED'} required /></label>
          <label className="wide-field">备注<textarea name="notes" defaultValue={data.sample.notes ?? ''} rows={2} /></label>
          <input type="hidden" name="site_name" value={data.sample.site_name} />
          <input type="hidden" name="equipment_serial" value={data.sample.equipment_serial} />
          <button className="primary-action wide-field" disabled={busy}>保存基础信息</button>
        </form>
      </section>

      <section className="test-records" aria-labelledby="test-records-title">
        <div className="section-heading"><div><span className="step">04 / 检测</span><h2 id="test-records-title">检测记录</h2></div>
          <div className="test-actions">{(Object.keys(TYPE_LABEL) as TestType[]).map(type => <button key={type} type="button" onClick={() => beginCreate(type)}>新增{TYPE_LABEL[type]}</button>)}</div>
        </div>
        {data.tests.length === 0 ? <p className="no-results">尚无检测记录。</p> : <div className="test-list">{data.tests.map((record, index) => <article className="test-card" key={record.id}>
          <div><span className="test-type">{TYPE_LABEL[record.test_type]}</span><strong>{TYPE_LABEL[record.test_type]} 检测 #{index + 1}</strong><p>{new Date(record.measured_at).toLocaleString('zh-CN')} · {record.instrument_name || '未填写仪器'}</p></div>
          <div className="measurement-preview">{Object.entries(resultMeasurements(record)).slice(0, 3).map(([code, item]) => <span key={code}>{code.toUpperCase()} {item.qualifier === 'EQ' ? '' : item.qualifier} {item.value ?? ''}</span>)}</div>
          <div className="record-actions"><button type="button" onClick={() => beginEdit(record)}>修改</button><button type="button" className="danger-action" onClick={() => void remove(record)}>删除</button></div>
        </article>)}</div>}
      </section>

      {showForm && method && <section className="test-editor" aria-labelledby="test-editor-title">
        <div className="section-heading"><div><span className="step">05 / 录入</span><h2 id="test-editor-title">{editing ? `修改${TYPE_LABEL[testType]}` : `新增${TYPE_LABEL[testType]}`}</h2></div><button type="button" className="quiet-action" onClick={() => setShowForm(false)}>取消</button></div>
        <p className="method-note">{method.display_name} · {method.standard_reference ?? 'ASTM 方法编号待配置'}</p>
        <form className="test-form" onSubmit={saveTest}>
          <label>检测时间<input type="datetime-local" value={measuredAt} onChange={event => setMeasuredAt(event.target.value)} required /></label>
          <label>仪器<input value={instrument} onChange={event => setInstrument(event.target.value)} maxLength={160} /></label>
          <div className="measurement-grid wide-field">{method.fields.map(field => {
            const item = measurement(field.code);
            return <fieldset key={field.code}><legend>{field.display_name}</legend>
              <select aria-label={`${field.display_name}限定符`} value={item.qualifier} onChange={event => setMeasurement(field.code, { qualifier: event.target.value as Qualifier })}>
                <option value="EQ">数值</option><option value="ND">ND 未检出</option><option value="LT">LT 小于</option><option value="GT">GT 大于</option>
              </select>
              <input aria-label={`${field.display_name}结果`} type="number" min="0" step={field.display_decimal_places === null ? 'any' : 10 ** -field.display_decimal_places} disabled={item.qualifier === 'ND'} value={item.value} onChange={event => setMeasurement(field.code, { value: event.target.value })} required={item.qualifier !== 'ND'} />
              <small>{field.unit_code ?? '单位待配置'} · {field.display_decimal_places === null ? '精度待配置' : `${field.display_decimal_places} 位小数`} · {field.detection_limit === null ? '检出限待配置' : `检出限 ${field.detection_limit}`}</small>
            </fieldset>;
          })}</div>
          <label>原始附件<input type="file" onChange={event => setAttachment(event.target.files?.[0] ?? null)} /></label>
          <label className="wide-field">备注<textarea value={notes} onChange={event => setNotes(event.target.value)} rows={2} /></label>
          <button className="primary-action wide-field" disabled={busy}>{busy ? '保存中…' : editing ? '保存修改' : `保存${TYPE_LABEL[testType]}检测`}</button>
        </form>
      </section>}
    </>}
  </div>;
}
