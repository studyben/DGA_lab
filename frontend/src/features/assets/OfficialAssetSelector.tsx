import { FormEvent, useState } from 'react';


type FormalAsset = {
  id: string;
  system_asset_number: string;
  asset_type: 'WHOLE_UNIT' | 'TRANSFORMER';
  serial_number: string;
  model: string | null;
  material_number: string | null;
  lifecycle_status: string;
};

type AssetContext = {
  asset: FormalAsset;
  customer_id: string;
  customer_name: string;
  site_id: string;
  site_name: string;
  site_location: string | null;
  equipment_path: FormalAsset[];
};

type SearchMatch = AssetContext & {
  match_reason: 'EXACT_SERIAL' | 'SERIAL_PREFIX' | 'SERIAL_CONTAINS';
  linkable_transformers: FormalAsset[];
};

export type OfficialAssetSelection = AssetContext;

const statusLabels: Record<string, string> = {
  COMMISSIONING: '调试中',
  IN_SERVICE: '投运',
  OUT_OF_SERVICE: '停运',
  RETIRED: '退役',
  MERGED: '已合并',
};

const reasonLabels = {
  EXACT_SERIAL: '序列号完全匹配',
  SERIAL_PREFIX: '序列号前缀匹配',
  SERIAL_CONTAINS: '序列号部分匹配',
};

function sampledAtIso(sampledAt: string) {
  const instant = new Date(sampledAt);
  if (Number.isNaN(instant.valueOf())) throw new Error('请先填写有效的采样时间。');
  return instant.toISOString();
}

export function OfficialAssetSelector({
  sampledAt,
  onSelect,
}: {
  sampledAt: string;
  onSelect: (selection: OfficialAssetSelection) => void;
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<SearchMatch[]>([]);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);

  async function search(event: FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const at = sampledAtIso(sampledAt);
      const response = await fetch(
        `/api/assets/search?q=${encodeURIComponent(query.trim())}&effective_at=${encodeURIComponent(at)}`,
        { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000) },
      );
      if (!response.ok) throw new Error('无法搜索正式资产，请稍后重试。');
      const body: unknown = await response.json();
      if (!Array.isArray(body)) throw new Error('资产搜索响应无效。');
      setMatches(body as SearchMatch[]);
      setSearched(true);
    } catch (failure) {
      setMatches([]);
      setSearched(false);
      setError(failure instanceof Error ? failure.message : '无法搜索正式资产。');
    } finally {
      setBusy(false);
    }
  }

  async function select(asset: FormalAsset) {
    setError('');
    setBusy(true);
    try {
      const at = sampledAtIso(sampledAt);
      const response = await fetch(
        `/api/assets/${asset.id}/sampling-context?sampled_at=${encodeURIComponent(at)}`,
        { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000) },
      );
      if (!response.ok) throw new Error('无法确认采样时的资产关系，请重新搜索。');
      onSelect(await response.json() as AssetContext);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '无法关联正式资产。');
    } finally {
      setBusy(false);
    }
  }

  return <section className="asset-selector" aria-labelledby="asset-search-title">
    <div className="section-heading">
      <div><span className="step">02 / 正式资产</span><h2 id="asset-search-title">搜索并关联正式资产</h2></div>
      <span className="required-note">必须明确选择</span>
    </div>
    <form className="asset-search-form" onSubmit={search}>
      <label>整机或变压器序列号
        <input value={query} onChange={event => setQuery(event.target.value)} maxLength={160}
          placeholder="支持完整或部分序列号" required disabled={busy} />
      </label>
      <button type="submit" disabled={busy}>{busy ? '查询中…' : '搜索正式资产'}</button>
    </form>
    {error && <p className="form-error" role="alert">{error}</p>}
    {searched && matches.length === 0 && <p className="no-results">没有找到该采样时间下可关联的正式资产。</p>}
    <div className="asset-results">
      {matches.map(match => <fieldset className="asset-result" key={match.asset.id}>
        <legend>{match.asset.serial_number}</legend>
        <div className="match-banner">{reasonLabels[match.match_reason]}</div>
        <dl className="asset-facts">
          <div><dt>客户</dt><dd>{match.customer_name}</dd></div>
          <div><dt>现场</dt><dd>{match.site_name}</dd></div>
          <div><dt>位置</dt><dd>{match.site_location ?? '—'}</dd></div>
          <div><dt>系统资产号</dt><dd>{match.asset.system_asset_number}</dd></div>
          <div><dt>设备型号</dt><dd>{match.asset.model ?? '—'}</dd></div>
          <div><dt>状态</dt><dd>{statusLabels[match.asset.lifecycle_status] ?? match.asset.lifecycle_status}</dd></div>
        </dl>
        {match.asset.asset_type === 'TRANSFORMER' &&
          <button className="select-asset" type="button" disabled={busy}
            onClick={() => void select(match.asset)} aria-label={`选择变压器 ${match.asset.serial_number}`}>
            选择此变压器
          </button>}
        {match.linkable_transformers.length > 0 && <div className="linked-assets">
          <h3>采样时可关联变压器</h3>
          {match.linkable_transformers.map(transformer => <div className="linked-asset" key={transformer.id}>
            <div><strong>{transformer.serial_number}</strong><span>{transformer.model ?? '型号未提供'} · {transformer.system_asset_number}</span></div>
            <button className="select-asset" type="button" disabled={busy}
              onClick={() => void select(transformer)} aria-label={`选择变压器 ${transformer.serial_number}`}>
              选择
            </button>
          </div>)}
        </div>}
      </fieldset>)}
    </div>
  </section>;
}
