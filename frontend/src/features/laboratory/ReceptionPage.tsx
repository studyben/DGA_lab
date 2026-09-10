import { useState } from 'react';

import {
  OfficialAssetSelection,
  OfficialAssetSelector,
} from '../assets/OfficialAssetSelector';


export function ReceptionPage() {
  const [sampledAt, setSampledAt] = useState('');
  const [selection, setSelection] = useState<OfficialAssetSelection | null>(null);

  return <div className="reception-layout">
    <section className="reception-panel" aria-labelledby="sample-context-title">
      <div className="section-heading">
        <div><span className="step">01 / 采样信息</span><h2 id="sample-context-title">确认采样时间</h2></div>
      </div>
      <label className="sample-time">采样时间
        <input type="datetime-local" value={sampledAt} required
          onChange={event => { setSampledAt(event.target.value); setSelection(null); }} />
      </label>
      <p className="field-help">资产关系将按这个时间解析，后续设备更换不会改写采样时身份。</p>
    </section>
    <OfficialAssetSelector sampledAt={sampledAt} onSelect={setSelection} />
    <section className={`selection-summary ${selection ? 'selected' : ''}`} aria-label="资产关联结果">
      {selection ? <div role="status">
        <span className="selection-mark" aria-hidden="true">✓</span>
        <div><strong>已关联 {selection.asset.serial_number}</strong>
          <p>{selection.customer_name} · {selection.site_name} · {selection.equipment_path.map(asset => asset.serial_number).join(' → ')}</p>
        </div>
      </div> : <p>尚未选择正式资产</p>}
    </section>
  </div>;
}
