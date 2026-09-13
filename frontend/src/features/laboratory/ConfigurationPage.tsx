import { FormEvent, useEffect, useState } from 'react';
import { useAuth } from '../../Auth';
import { Catalog, FieldConfig, MethodDraft, PackageItem, Qualifier, TestType, TYPE_LABEL, FIELD_CODES, STATUS_LABEL } from './configurationTypes';
import './configuration.css';

type Submit = (path: string, body: unknown, verb?: string) => Promise<boolean>;
function blankMethod(type: TestType): MethodDraft {
  return { test_type:type, display_name:'', version_label:'', standard_reference:null, qa_checks:[],
    fields:FIELD_CODES[type].map(code => ({code, display_name:code, unit_code:null, display_decimal_places:null,
      detection_limit:null, allowed_qualifiers:['EQ','ND','LT','GT']})) };
}

export function ConfigurationPage() {
  const { can, session } = useAuth();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogRevision, setCatalogRevision] = useState(0);
  const [tab, setTab] = useState('methods');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  async function load() {
    const response = await fetch('/api/laboratory/configuration', { cache:'no-store', signal:AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error('无法读取配置，请确认登录状态后重试。');
    setCatalog(await response.json() as Catalog);
    setCatalogRevision(revision => revision + 1);
    setUncertain(false);
  }
  useEffect(() => { void load().catch(e => setError(String(e))); }, []);
  const submit: Submit = async (path, body, verb='POST') => {
    if (busy || uncertain) return false;
    setBusy(true); setError(''); setMessage('');
    let saved = false;
    try {
      const response = await fetch(`/api/laboratory/${path}`, { method:verb, cache:'no-store',
        headers:{'Content-Type':'application/json','X-CSRF-Token':session?.csrf_token ?? ''},
        signal:AbortSignal.timeout(15000), body:JSON.stringify(body) });
      if (!response.ok) {
        if (response.status >= 500) setUncertain(true);
        const data = await response.json().catch(() => ({}));
        const errors: Record<string,string> = { configuration_duplicate:'编号或版本已存在，请核对列表。',
          invalid_input:'配置格式无效，请核对字段、范围、小数位数和必填项。',
          instrument_status_conflict:'仪器状态已被其他操作更新，请重新读取。',
          package_method_unavailable:'检测包中的方法或检测类型未启用。', forbidden:'没有维护配置的权限。' };
        throw new Error(errors[data.code] ?? '保存失败，请重新读取配置并检查输入或登录状态。');
      }
      saved = true;
      await load(); setMessage('配置已保存'); return true;
    } catch(e) {
      if (saved || !(e instanceof Error) || e.name === 'TypeError' || e.name === 'TimeoutError') setUncertain(true);
      setError(e instanceof Error ? e.message : '结果未知，请重新读取配置再操作。'); return false;
    } finally { setBusy(false); }
  };
  function matches(...values: (string | null)[]) { return values.join(' ').toLowerCase().includes(search.toLowerCase()); }
  return <div className="lab-config">
    <p>配置新版本不会改写历史检测。ASTM 编号、单位和限值请按实验室批准的方法填写；未确认时留空。</p>
    <div className="config-toolbar"><nav aria-label="配置分类">{[['methods','方法版本'],['types','检测类型'],['instruments','仪器与校准'],['packages','检测包']].map(([key,label]) =>
      <button type="button" key={key} aria-pressed={tab===key} onClick={() => { setTab(key); setSearch(''); }}>{label}</button>)}</nav>
      <button type="button" disabled={busy} onClick={() => { setError(''); void load().catch(e => setError(String(e))); }}>重新读取配置</button>
    </div>
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="form-error">{error}</p>}
    {uncertain && <p role="alert">保存结果尚未确认，请重新读取配置核对后再操作，不要重复提交。</p>}
    {!can('laboratory.configure') && <p>只读：请联系实验室管理员维护配置。</p>}
    {catalog && <>
      <label className="config-filter">筛选当前列表<input value={search} onChange={e => setSearch(e.target.value)} placeholder="名称、编号或版本" /></label>
      {tab==='methods' && <>
        <div className="config-table-wrap"><table aria-label="方法版本列表"><thead><tr><th>类型</th><th>方法</th><th>版本</th><th>ASTM 编号</th><th>状态</th><th>操作</th></tr></thead><tbody>
          {catalog.methods.filter(m => matches(m.display_name,m.version_label,m.standard_reference)).map(m => <tr key={m.id}>
            <td>{TYPE_LABEL[m.test_type]}</td><td>{m.display_name}</td><td>{m.version_label}</td><td>{m.standard_reference ?? '待配置'}</td><td>{m.is_active?'启用':'停用'}</td>
            <td><button disabled={busy || uncertain || !can('laboratory.configure')} onClick={() => void submit(`configuration/methods/${m.id}/activation`,{is_active:!m.is_active},'PUT')}>{m.is_active?'停用':'启用'}</button></td></tr>)}
        </tbody></table></div>
        <fieldset disabled={busy || uncertain || !can('laboratory.configure')}><MethodEditor catalog={catalog} submit={submit} /></fieldset>
      </>}
      {tab==='types' && <fieldset disabled={busy || uncertain || !can('laboratory.configure')}><h2>已支持的检测类型</h2><p>新检测类型需要对应的类型化结果结构；这里维护现有类型。</p>
        {catalog.types.filter(t => matches(t.display_name,t.code)).map(t => <form className="config-row" key={`${catalogRevision}:${t.code}`} onSubmit={e => {e.preventDefault(); const f = new FormData(e.currentTarget); void submit(`configuration/types/${t.code}`, {display_name:f.get('name'),is_active:f.get('active')==='on'},'PUT');}}>
          <strong>{t.code}</strong><label>显示名称<input name="name" defaultValue={t.display_name} required maxLength={100} /></label><label><input type="checkbox" name="active" defaultChecked={t.is_active} />启用类型</label><button>保存类型</button>
        </form>)}</fieldset>}
      {tab==='instruments' && <>
        <div className="config-table-wrap"><table aria-label="仪器台账"><thead><tr><th>编号</th><th>名称</th><th>型号 / 序列号</th><th>状态</th></tr></thead><tbody>{catalog.instruments.filter(i=>matches(i.code,i.name,i.serial_number)).map(i=><tr key={i.id}>
          <td>{i.code}</td><td>{i.name}</td><td>{i.model ?? '—'} / {i.serial_number ?? '—'}</td><td><select aria-label={`${i.code} 状态`} value={i.status} disabled={busy || uncertain || !can('laboratory.configure')} onChange={e=>void submit(`configuration/instruments/${i.id}/status`,{status:e.target.value,expected_status:i.status},'PUT')}>
            {['ACTIVE','OUT_OF_SERVICE','RETIRED'].map(s=><option value={s} key={s}>{STATUS_LABEL[s]}</option>)}</select></td></tr>)}</tbody></table></div>
        <fieldset disabled={busy || uncertain || !can('laboratory.configure')}><h2>新增仪器</h2><form className="config-form" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void submit('configuration/instruments',{code:f.get('code'),name:f.get('name'),model:f.get('model')||null,serial_number:f.get('serial')||null});}}>
          <label>仪器编号<input name="code" required maxLength={40} /></label><label>仪器名称<input name="name" required maxLength={150} /></label><label>型号<input name="model" maxLength={150} /></label><label>序列号<input name="serial" maxLength={150} /></label><button>新增仪器</button>
        </form><h2>添加校准记录</h2><p>日期按 America/Chicago；截止日当天有效。校准记录保存后不可覆盖。</p><form className="config-form" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void submit(`configuration/instruments/${f.get('instrument')}/calibrations`,{calibrated_on:f.get('date'),expires_on:f.get('expiry')||null,outcome:f.get('outcome'),provider:f.get('provider')||null,certificate:f.get('certificate')||null});}}>
          <label>校准仪器<select name="instrument" required><option value="">请选择仪器</option>{catalog.instruments.map(i=><option key={i.id} value={i.id}>{i.code} · {i.name}</option>)}</select></label>
          <label>校准日期<input name="date" type="date" required /></label><label>有效截止日<input name="expiry" type="date" /></label><label>校准结论<select name="outcome"><option value="VALID">通过</option><option value="FAILED">失败</option><option value="UNKNOWN">未知</option></select></label>
          <label>校准机构<input name="provider" maxLength={150} /></label><label>证书编号<input name="certificate" maxLength={100} /></label><button disabled={!catalog.instruments.length}>保存校准记录</button>
        </form></fieldset>
        <div className="config-table-wrap"><table aria-label="校准记录"><thead><tr><th>仪器</th><th>校准日期</th><th>有效截止日</th><th>记录结论</th><th>证书</th></tr></thead><tbody>{catalog.calibrations.filter(c=>matches(c.certificate,catalog.instruments.find(i=>i.id===c.instrument_id)?.code ?? '')).map(c=><tr key={c.id}><td>{catalog.instruments.find(i=>i.id===c.instrument_id)?.code}</td><td>{c.calibrated_on}</td><td>{c.expires_on ?? '未知'}</td><td>{STATUS_LABEL[c.outcome]}</td><td>{c.certificate ?? '—'}</td></tr>)}</tbody></table></div>
      </>}
      {tab==='packages' && <>
        <div className="config-table-wrap"><table aria-label="检测包列表"><thead><tr><th>编号</th><th>名称</th><th>项目</th></tr></thead><tbody>{catalog.packages.filter(p=>matches(p.code,p.name)).map(p=><tr key={p.id}><td>{p.code}</td><td>{p.name}</td><td>{p.items.map(i=>`${TYPE_LABEL[i.test_type]}${i.required?'（必做）':'（可选）'}`).join('、')}</td></tr>)}</tbody></table></div>
        <fieldset disabled={busy || uncertain || !can('laboratory.configure')}><PackageEditor catalog={catalog} submit={submit} /></fieldset>
      </>}
    </>}
  </div>;
}

function MethodEditor({catalog,submit}:{catalog:Catalog;submit:Submit}) {
  const [draft,setDraft]=useState<MethodDraft>(()=>blankMethod('DGA'));
  function field(index:number, change:Partial<FieldConfig>) { setDraft(d=>({...d,fields:d.fields.map((f,i)=>i===index?{...f,...change}:f)})); }
  async function save(e:FormEvent) {e.preventDefault(); await submit('configuration/methods',draft);}
  return <><h2>新增方法版本</h2><p>修改配置请复制为新版本。留空代表待配置，不表示零。</p>
    <label>复制已有方法<select defaultValue="" onChange={e=>{const m=catalog.methods.find(m=>m.id===e.target.value);if(m)setDraft(m.configuration?{...m.configuration,version_label:''}:{...blankMethod(m.test_type),display_name:m.display_name});}}><option value="">选择作为起点的方法</option>{catalog.methods.map(m=><option key={m.id} value={m.id}>{m.display_name} · {m.version_label}</option>)}</select></label>
    <form className="config-form" onSubmit={save}>
      <label>检测类型<select aria-label="检测类型" value={draft.test_type} onChange={e=>setDraft(blankMethod(e.target.value as TestType))}>{Object.entries(TYPE_LABEL).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>方法名称<input value={draft.display_name} onChange={e=>setDraft({...draft,display_name:e.target.value})} required maxLength={160} /></label>
      <label>方法版本标识<input value={draft.version_label} onChange={e=>setDraft({...draft,version_label:e.target.value})} required maxLength={80} /></label>
      <label>ASTM 方法编号<input value={draft.standard_reference ?? ''} placeholder="尚未确认可留空" onChange={e=>setDraft({...draft,standard_reference:e.target.value||null})} maxLength={160} /></label>
      <div className="config-fields">{draft.fields.map((f,index)=><fieldset key={f.code}><legend>{f.code}</legend><div className="config-form">
        <label>结果名称<input value={f.display_name} onChange={e=>field(index,{display_name:e.target.value})} required maxLength={80} /></label>
        <label>单位<input aria-label={`${f.code} 单位`} value={f.unit_code ?? ''} onChange={e=>field(index,{unit_code:e.target.value||null})} placeholder="待配置" maxLength={40} /></label>
        <label>小数位数<input aria-label={`${f.code} 小数位数`} type="number" min={0} max={6} value={f.display_decimal_places ?? ''} onChange={e=>field(index,{display_decimal_places:e.target.value===''?null:Number(e.target.value)})} /></label>
        {(['detection_limit','quantitation_limit','minimum','maximum'] as const).map((key,i)=><label key={key}>{['检出限','定量限','录入下限','录入上限'][i]}<input aria-label={`${f.code} ${['检出限','定量限','录入下限','录入上限'][i]}`} type="number" min="0" step="any" value={f[key] ?? ''} onChange={e=>field(index,{[key]:e.target.value||null})} /></label>)}
        <div><p>允许限定符</p>{(['EQ','ND','LT','GT'] as Qualifier[]).map(q=><label className="config-check" key={q}><input type="checkbox" checked={f.allowed_qualifiers.includes(q)} onChange={e=>field(index,{allowed_qualifiers:e.target.checked?[...f.allowed_qualifiers,q]:f.allowed_qualifiers.filter(v=>v!==q)})} />{q}</label>)}</div>
      </div></fieldset>)}</div>
      <div className="config-fields"><h3>QA/QC 检查项</h3><p>配置人工检查要求；不预置科学阈值。</p>{draft.qa_checks.map((q,index)=><div className="config-row" key={index}>
        <label>检查代码<input value={q.code} pattern="[A-Z][A-Z0-9_]{0,29}" required onChange={e=>setDraft({...draft,qa_checks:draft.qa_checks.map((v,i)=>i===index?{...v,code:e.target.value}:v)})} /></label>
        <label>检查名称<input value={q.label} required maxLength={100} onChange={e=>setDraft({...draft,qa_checks:draft.qa_checks.map((v,i)=>i===index?{...v,label:e.target.value}:v)})} /></label>
        <label>检查说明<input value={q.instructions} maxLength={500} onChange={e=>setDraft({...draft,qa_checks:draft.qa_checks.map((v,i)=>i===index?{...v,instructions:e.target.value}:v)})} /></label>
        <button type="button" onClick={()=>setDraft({...draft,qa_checks:draft.qa_checks.filter((_,i)=>i!==index)})}>移除检查项</button></div>)}
        <button type="button" disabled={draft.qa_checks.length>=20} onClick={()=>setDraft({...draft,qa_checks:[...draft.qa_checks,{code:'',label:'',instructions:''}]})}>添加 QA/QC 检查项</button>
      </div><button>发布新方法版本</button>
    </form></>;
}

function PackageEditor({catalog,submit}:{catalog:Catalog;submit:Submit}) {
  const [items,setItems]=useState<PackageItem[]>([]);
  return <><h2>新增检测包</h2><p>检测包保存后不覆盖；调整组合请使用新编号。应用到油样时保存项目快照。</p><form className="config-form" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void submit('configuration/packages',{code:f.get('code'),name:f.get('name'),items});}}>
    <label>检测包编号<input name="code" required maxLength={40} /></label><label>检测包名称<input name="name" required maxLength={120} /></label>
    {catalog.types.map(t=>{const item=items.find(i=>i.test_type===t.code);return <div className="config-fields config-row" key={t.code}>
      <label><input type="checkbox" checked={Boolean(item)} disabled={!t.is_active} onChange={e=>setItems(e.target.checked?[...items,{test_type:t.code,method_version_id:'',required:true}]:items.filter(i=>i.test_type!==t.code))} />{t.display_name}</label>
      {item && <><label>默认方法<select required value={item.method_version_id} onChange={e=>setItems(items.map(i=>i.test_type===t.code?{...i,method_version_id:e.target.value}:i))}><option value="">请选择方法</option>{catalog.methods.filter(m=>m.test_type===t.code&&m.is_active).map(m=><option key={m.id} value={m.id}>{m.display_name} · {m.version_label}</option>)}</select></label>
      <label><input type="checkbox" checked={item.required} onChange={e=>setItems(items.map(i=>i.test_type===t.code?{...i,required:e.target.checked}:i))} />必做</label></>}
    </div>;})}<button disabled={!items.length}>保存检测包</button>
  </form></>;
}
