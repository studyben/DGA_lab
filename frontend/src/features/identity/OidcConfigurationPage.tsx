import { useEffect, useState } from 'react';
import { useAuth, oidcError } from '../../Auth';
import './identity.css';

type Candidate = { id: string; issuer: string; client_id: string; callback_url: string | null };
type Proof = { id: string; config_id: string; issuer: string; subject: string; expires_at: string };
type Configuration = { active_id: string | null; revision: number; deployment_ready: boolean; candidates: Candidate[]; proofs: Proof[]; default_callback_url: string };
type User = { id: string; username: string; display_name: string; revision: number };
const messages: Record<string, string> = {
  permission_denied: '当前账号无配置权限。', session_expired: '登录已失效，请重新登录。',
  csrf_rejected: '会话已更新，请刷新后重试。', invalid_input: '请检查必填项和格式。',
  invalid_oidc_configuration: '配置格式不正确，请核对 IT 提供的参数。',
  oidc_endpoint_not_allowed: '此 Okta 地址不在部署允许列表中，请联系部署管理员。',
  oidc_key_unavailable: '无法解密配置，请联系部署管理员恢复原密钥。',
  oidc_test_required: '请由当前管理员先完成此配置的测试登录；证明有效期为 15 分钟。',
  stale_user: '账号已更新，请重新搜索并选择账号。',
  stale_oidc_configuration: '生效配置已被更新，请重新加载后核对；原配置未被本次操作覆盖。',
  oidc_identity_already_bound: '此外部身份或此账号已经有关联，不能覆盖或重新绑定。',
  oidc_callback_not_allowed: '回调地址须使用部署允许的应用地址，路径固定为 /api/auth/oidc/callback；须与 IT 注册一致。',
  oidc_candidate_callback_required: '旧候选未保存回调地址，请重新保存候选并测试，不能直接启用。',
};

export function OidcConfigurationPage() {
  const auth = useAuth();
  const [config, setConfig] = useState<Configuration | null>(null);
  const [candidate, setCandidate] = useState({ issuer: '', client_id: '', client_secret: '', callback_url: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(new URLSearchParams(location.search).get('oidc') === 'tested' ? '测试登录已通过。尚未启用，请核对后明确启用。' : '');
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [target, setTarget] = useState('');
  const [proofId, setProofId] = useState('');
  async function request<T>(path: string, body?: unknown): Promise<T> {
    const r = await fetch('/api/auth/' + path, { method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      signal: AbortSignal.timeout(40000), headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': auth.session?.csrf_token ?? '' },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const v = await r.json();
    if (!r.ok) { if (r.status === 401) void auth.refresh(); throw new Error(messages[v.code] ?? oidcError(v.code)); }
    return v as T;
  }
  async function load() { setConfig(await request<Configuration>('oidc/configuration')); }
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : '请求失败，请重试。'); }
    finally { setBusy(false); }
  }
  async function saved(message: string) {
    setNotice(message);
    try { await load(); } catch { setError('操作已保存，但列表刷新失败。请重新加载，不要重复提交。'); }
  }
  const allowed = auth.can('identity.manage');
  useEffect(() => {
    if (!allowed) return;
    let live = true;
    setBusy(true);
    request<Configuration>('oidc/configuration').then(v => { if (live) { setConfig(v); setCandidate(c => ({ ...c, callback_url: c.callback_url || v.default_callback_url })); } })
      .catch(e => { if (live) setError(e instanceof Error ? e.message : '加载失败'); }).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [allowed]);
  if (!allowed) return <p role="alert">当前账号无配置权限。</p>;
  return <div className="identity-management">
    <section className="identity-panel"><h2>先测试，再启用</h2>
      <p className="identity-help">保存候选配置不会影响当前登录。使用候选配置完成测试登录后，由同一管理员在 15 分钟内明确启用。测试登录不会替换本地管理员会话，也不会自动创建或关联员工账号。</p>
      <p className="identity-help">真实 Okta 验收需由 IT 配合完成，模拟测试不代表已验收。</p>
      <p><a href="/login/local">独立本地恢复登录入口</a></p>
      {config && !config.deployment_ready && <p role="alert">尚缺部署配置：加密密钥、允许的 Okta 主机及固定回调地址。请由部署管理员配置后重启服务；本地登录不受影响。</p>}
      <button disabled={busy} onClick={() => void run(load)}>重新加载配置</button>
    </section>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <section className="identity-panel"><h2>保存候选配置</h2>
      <form className="oidc-form" onSubmit={e => { e.preventDefault(); void run(async () => {
        try { await request('oidc/candidates', candidate); } finally { setCandidate(v => ({ ...v, client_secret: '' })); }
        await saved('候选配置已保存，尚未启用。');
      }); }}>
        <label>Issuer 地址<input type="url" required maxLength={500} disabled={busy} value={candidate.issuer} onChange={e => setCandidate({ ...candidate, issuer: e.target.value })} /></label>
        <label>Client ID<input required maxLength={200} disabled={busy} value={candidate.client_id} onChange={e => setCandidate({ ...candidate, client_id: e.target.value })} /></label>
        <label>回调地址<input type="url" required maxLength={500} disabled={busy} value={candidate.callback_url} onChange={e => setCandidate({ ...candidate, callback_url: e.target.value })} /></label>
        <p className="identity-help">需与 IT 注册完全一致，并与发起登录的应用地址同源。仅允许部署白名单内地址，路径固定为 /api/auth/oidc/callback。更改后必须重新测试并启用，不会修改 Okta 注册。</p>
        <label>Client Secret<input type="password" autoComplete="new-password" required maxLength={4096} disabled={busy} value={candidate.client_secret} onChange={e => setCandidate({ ...candidate, client_secret: e.target.value })} /></label>
        <p className="identity-help">参数由 IT 提供。不预设租户地址或授权服务器；密钥提交后不回显。</p>
        <button disabled={busy || !config?.deployment_ready}>保存候选配置</button>
      </form>
    </section>
    <section className="identity-panel"><h2>候选配置与生效状态</h2>
      <div className="identity-table"><table><thead><tr><th>Issuer / Client ID</th><th>状态</th><th>操作</th></tr></thead><tbody>
        {config?.candidates.map(c => { const proof = config.proofs.find(p => p.config_id === c.id); return <tr key={c.id}>
          <td>{c.issuer}<br />{c.client_id}<br />{c.callback_url ?? '未保存回调地址，需重建候选'}<br /><small>{c.id}</small></td><td>{config.active_id === c.id ? '当前生效' : '候选'}</td>
          <td><div className="identity-actions"><button disabled={busy || !config.deployment_ready} onClick={() => void run(async () => {
            const v = await request<{ authorization_url: string }>('oidc/candidates/' + c.id + '/test', {}); location.assign(v.authorization_url);
          })}>测试登录</button><button disabled={busy || !proof || !config.deployment_ready || config.active_id === c.id} onClick={() => {
            if (!proof || !window.confirm('启用此候选配置用于员工登录？当前本地恢复入口不变。')) return;
            void run(async () => { await request('oidc/activate', { config_id: c.id, proof_id: proof.id, expected_revision: config.revision }); await saved('配置已明确启用。'); });
          }}>明确启用</button></div>{proof && <small>测试证明有效至 {new Date(proof.expires_at).toLocaleString()}</small>}</td>
        </tr>; })}
      </tbody></table></div>{config?.candidates.length === 0 && <p>尚无候选配置。</p>}
    </section>
    <section className="identity-panel"><h2>核验并关联已有账号</h2>
      <p className="identity-help">仅用于已由管理员核验的同一人。先通过候选配置测试其外部身份，再选择现有账号并确认关联。不按邮箱自动合并，不改变原角色和状态，不覆盖已有绑定。</p>
      <form className="oidc-form" onSubmit={e => { e.preventDefault(); void run(async () => {
        setTarget(''); setUsers((await request<{ items: User[] }>('users?' + new URLSearchParams({ query }))).items);
      }); }}><label>现有账号关键词<input value={query} disabled={busy} maxLength={150} onChange={e => setQuery(e.target.value)} /></label><button disabled={busy}>搜索现有账号</button></form>
      <div className="oidc-form"><label>已核验的外部身份<select value={proofId} disabled={busy} onChange={e => setProofId(e.target.value)}><option value="">选择当前管理员的有效测试证明</option>{config?.proofs.map(p => <option key={p.id} value={p.id}>{p.issuer} · {p.subject}</option>)}</select></label>
        <label>目标内部账号<select value={target} disabled={busy} onChange={e => setTarget(e.target.value)}><option value="">选择搜索结果</option>{users.map(u => <option key={u.id} value={u.id}>{u.display_name} · {u.username}</option>)}</select></label>
        <button disabled={busy || !target || !proofId} onClick={() => {
          const user = users.find(u => u.id === target), proof = config?.proofs.find(p => p.id === proofId);
          if (!user || !proof || !window.confirm(`确认 ${proof.issuer} / ${proof.subject} 与内部账号 ${user.username} 是同一人？`)) return;
          void run(async () => { await request('oidc/bind', { user_id: user.id, proof_id: proof.id, expected_revision: user.revision }); setTarget(''); setUsers([]); await saved('外部身份已关联，原角色和账号状态保持不变。'); });
        }}>确认身份关联</button>
      </div>
    </section>
  </div>;
}
