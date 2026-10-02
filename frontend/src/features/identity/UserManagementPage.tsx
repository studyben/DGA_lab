import { useEffect, useState } from 'react';
import { useAuth } from '../../Auth';
import './identity.css';

type User = { id: string; username: string; display_name: string; user_status: string; roles: string[]; revision: number; credential_kind: string; blocked_until: string | null };
type Detail = User & { actions: string[] };
type Role = { role_code: string; role_name: string; assignable: boolean };
type Result = { items: User[]; total: number; page: number };
type Filters = { query: string; status: string; role: string };
const emptyFilters: Filters = { query: '', status: '', role: '' };
const statusNames: Record<string, string> = { ACTIVE: '启用', LOCKED: '锁定', DISABLED: '停用' };
const errors: Record<string, string> = {
  permission_denied: '当前账号无权执行此操作，请重新加载权限。',
  stale_user: '账号已被其他操作更新。你的输入尚未提交，请重新加载详情后确认。',
  last_local_admin: '必须保留至少一个启用的本地恢复管理员。',
  invalid_roles: '请选择至少一个有效角色；不能同时添加和移除同一角色。',
  legacy_role_not_assignable: '旧兼容角色不能新增分配。', username_taken: '用户名已存在，请更换。',
  invalid_input: '请检查必填项和输入格式。', invalid_user: '用户名或显示名称不符合要求。',
  session_expired: '登录已失效，请重新登录。', csrf_rejected: '会话已更新，请刷新页面后重试。',
};

export function UserManagementPage() {
  const auth = useAuth();
  const allowed = ['identity.manage', 'identity.ordinary.manage', 'identity.am.manage'].some(auth.can);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [applied, setApplied] = useState<Filters>(emptyFilters);
  const [result, setResult] = useState<Result>({ items: [], total: 0, page: 1 });
  const [roles, setRoles] = useState<Role[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [recovery, setRecovery] = useState({ username: '', display_name: '', password: '' });

  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch('/api/auth/' + path, {
      method, cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(10000),
      headers: { 'Content-Type': 'application/json', ...(auth.session ? { 'X-CSRF-Token': auth.session.csrf_token } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const value = await response.json();
    if (!response.ok) {
      if (response.status === 401) void auth.refresh();
      throw new Error(errors[value.code] ?? '操作未完成，请检查连接后重试。');
    }
    return value as T;
  }
  async function guarded(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '连接失败，请重试。'); }
    finally { setBusy(false); }
  }
  function query(page: number, current: Filters) {
    return 'users?' + new URLSearchParams({ query: current.query, page: String(page),
      ...(current.status ? { status: current.status } : {}), ...(current.role ? { role: current.role } : {}) });
  }
  async function load(page = 1, current = applied) {
    const value = await request<Result>(query(page, current));
    setResult(value); setApplied(current);
  }
  async function open(id: string) {
    const value = await request<Detail>('users/' + id);
    setDetail(value); setName(value.display_name); setSelected(value.roles);
  }
  useEffect(() => {
    if (!allowed) return;
    let live = true;
    setBusy(true);
    Promise.all([request<Result>(query(1, emptyFilters)), request<Role[]>('roles')]).then(([users, catalog]) => {
      if (live) { setResult(users); setRoles(catalog); }
    }).catch(failure => { if (live) setError(failure instanceof Error ? failure.message : '加载失败'); })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
    // Explicit reads keep periodic session refresh from erasing unsaved edits.
  }, [allowed]);
  if (!allowed) return <section className="identity-panel"><p role="alert">当前账号无用户管理权限。</p></section>;
  const roleName = (code: string) => roles.find(r => r.role_code === code)?.role_name ?? code;
  async function changed(action: string, body: unknown, message: string) {
    if (!detail) return;
    await request('users/' + detail.id + '/' + action, 'PUT', body);
    setNotice(message);
    if (detail.id === auth.session?.actor.id) { await auth.refresh(); location.assign('/assets'); return; }
    try { await open(detail.id); await load(result.page); }
    catch { setError('变更已保存，但最新资料刷新失败。请重新加载详情，不要重复提交。'); }
  }

  return <div className="identity-management">
    <p className="identity-help">角色可以组合。管理层仅能调整普通账号的 AM 角色；实验室经理可管理普通账号，但不能恢复已停用账号。旧兼容角色保留历史授权，不再新增分配。</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <section className="identity-panel" aria-label="用户列表">
      <form className="identity-filters" onSubmit={e => { e.preventDefault(); void guarded(async () => { setDetail(null); await load(1, filters); }); }}>
        <label>用户关键词<input value={filters.query} maxLength={150} disabled={busy} onChange={e => setFilters({ ...filters, query: e.target.value })} placeholder="用户名或显示名称" /></label>
        <label>账号状态<select value={filters.status} disabled={busy} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">全部</option>{Object.entries(statusNames).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
        <label>角色筛选<select value={filters.role} disabled={busy} onChange={e => setFilters({ ...filters, role: e.target.value })}><option value="">全部</option>{roles.map(role => <option key={role.role_code} value={role.role_code}>{role.role_name}</option>)}</select></label>
        <button disabled={busy}>筛选用户</button>
      </form>
      <div className="identity-table"><table><thead><tr><th>用户名</th><th>显示名称</th><th>角色</th><th>状态</th><th>操作</th></tr></thead><tbody>{result.items.map(user => <tr key={user.id}><td>{user.username}</td><td>{user.display_name}</td><td>{user.roles.map(roleName).join('、')}</td><td>{statusNames[user.user_status]}{user.blocked_until && Date.parse(user.blocked_until) > Date.now() ? ' · 登录冷却中' : ''}</td><td><button disabled={busy} aria-label={'查看 ' + user.username} onClick={() => void guarded(() => open(user.id))}>查看</button></td></tr>)}</tbody></table></div>
      {!busy && !result.items.length && <p>没有符合条件的用户。</p>}
      <div className="identity-actions"><span>共 {result.total} 条 · 第 {result.page} 页</span><button disabled={busy || result.page <= 1} onClick={() => void guarded(() => load(result.page - 1))}>上一页</button><button disabled={busy || result.page * 20 >= result.total} onClick={() => void guarded(() => load(result.page + 1))}>下一页</button></div>
    </section>
    {detail && <section className="identity-panel" aria-label="用户详情">
      <h2>{detail.username}</h2><p>账号状态：{statusNames[detail.user_status]} · {detail.credential_kind === 'RECOVERY' ? '本地恢复账号' : detail.credential_kind === 'NONE' ? '企业登录账号' : '既有本地账号'}</p>
      <button disabled={busy} onClick={() => void guarded(() => open(detail.id))}>重新加载详情</button>
      <form onSubmit={e => { e.preventDefault(); void guarded(() => changed('profile', { display_name: name, expected_revision: detail.revision }, '显示名称已更新。')); }}>
        <label>显示名称<input value={name} onChange={e => setName(e.target.value)} maxLength={150} required disabled={busy || !detail.actions.includes('profile')} /></label>
        {detail.actions.includes('profile') && <button disabled={busy}>保存显示名称</button>}
      </form>
      <form onSubmit={e => { e.preventDefault(); void guarded(() => changed('roles', { add: selected.filter(r => !detail.roles.includes(r)), remove: detail.roles.filter(r => !selected.includes(r)), expected_revision: detail.revision }, '角色已更新。')); }}>
        <fieldset disabled={busy}><legend>业务角色</legend><div className="identity-role-options">{roles.map(role => <label key={role.role_code}><input type="checkbox" checked={selected.includes(role.role_code)} disabled={!detail.actions.includes('roles:' + role.role_code)} onChange={e => setSelected(e.target.checked ? [...selected, role.role_code] : selected.filter(r => r !== role.role_code))} />{role.role_name}{!role.assignable && '（兼容保留）'}</label>)}</div></fieldset>
        {!selected.length && <p className="identity-help">账号必须保留至少一个角色。</p>}
        {detail.actions.some(a => a.startsWith('roles:')) && <button disabled={busy || !selected.length || selected.join('|') === detail.roles.join('|')}>保存角色变更</button>}
      </form>
      <div className="identity-actions">{detail.actions.filter(a => a.startsWith('status:')).map(action => {
        const status = action.slice(7); const label = status === 'ACTIVE' ? (detail.user_status === 'DISABLED' ? '恢复账号' : '解除锁定 / 冷却') : status === 'DISABLED' ? '停用账号' : '锁定账号';
        return <button disabled={busy} key={action} onClick={() => { if (confirm('确认' + label + '？账号状态变化将立即生效。')) void guarded(() => changed('status', { status, expected_revision: detail.revision }, '账号状态已更新。')); }}>{label}</button>;
      })}</div>
      {!detail.actions.length && <p className="identity-help">此账号不在你的管理范围内。受保护账号请联系系统管理员。</p>}
    </section>}
    {auth.can('identity.manage') && <section className="identity-panel"><h2>新增本地恢复管理员</h2><p className="identity-help">仅用于管理员恢复入口，不创建普通员工密码账号。首次登录必须修改初始密码。</p>
      <form onSubmit={e => { e.preventDefault(); const body = recovery; void guarded(async () => { try { await request('users/recovery', 'POST', body); setRecovery({ username: '', display_name: '', password: '' }); setNotice('恢复管理员已创建。'); try { await load(); } catch { setError('账号已创建，但列表刷新失败。请重新筛选用户，不要重复创建。'); } } finally { setRecovery(value => ({ ...value, password: '' })); } }); }}>
        <div className="identity-filters"><label>新管理员用户名<input required maxLength={80} disabled={busy} autoComplete="off" value={recovery.username} onChange={e => setRecovery({ ...recovery, username: e.target.value })} /></label><label>新管理员显示名称<input required maxLength={150} disabled={busy} value={recovery.display_name} onChange={e => setRecovery({ ...recovery, display_name: e.target.value })} /></label><label>初始密码<input type="password" required minLength={15} maxLength={128} disabled={busy} autoComplete="new-password" value={recovery.password} onChange={e => setRecovery({ ...recovery, password: e.target.value })} /></label><button disabled={busy}>创建恢复管理员</button></div>
      </form></section>}
  </div>;
}
