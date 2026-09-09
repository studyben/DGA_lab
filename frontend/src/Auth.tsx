import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import sungrowLogo from './assets/sungrow-logo.svg';

type Session = {
  actor: { id: string; username: string; display_name: string };
  roles: string[]; permissions: string[]; must_change_password: boolean;
  csrf_token: string; expires_at: string;
};
type Auth = {
  session: Session | null | undefined; error: string;
  refresh: () => Promise<void>;
  mutate: (action: 'login' | 'password' | 'logout', body?: unknown) => Promise<void>;
  can: (permission: string) => boolean;
};
const AuthContext = createContext<Auth | null>(null);
const messages: Record<string, string> = {
  invalid_credentials: '用户名或密码不正确，或账号暂不可用。请核对后重试。',
  password_change_failed: '当前密码不正确，或新密码与当前密码相同。',
  invalid_input: '请检查输入；新密码需为 15–128 个字符。',
  csrf_rejected: '会话已更新，请刷新页面后重试。',
  origin_rejected: '当前访问地址未获授权，请联系管理员。',
  session_expired: '登录已失效，请重新登录。',
};

function validSession(value: unknown): value is Session {
  if (!value || typeof value !== 'object') return false;
  const s = value as Partial<Session>;
  return typeof s.actor?.id === 'string' && typeof s.actor?.username === 'string' &&
    typeof s.actor?.display_name === 'string' && typeof s.must_change_password === 'boolean' &&
    typeof s.csrf_token === 'string' && typeof s.expires_at === 'string' &&
    Array.isArray(s.roles) && s.roles.every(x => typeof x === 'string') &&
    Array.isArray(s.permissions) && s.permissions.every(x => typeof x === 'string');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>();
  const [error, setError] = useState('');
  const revision = useRef(0);
  const mutating = useRef(false);
  const refresh = useCallback(async () => {
    if (mutating.current) return;
    const version = ++revision.current;
    try {
      const response = await fetch('/api/auth/session', { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (version !== revision.current) return;
      if (response.status === 401) { setSession(null); setError(''); return; }
      if (!response.ok) throw new Error('会话服务暂不可用');
      const value: unknown = await response.json();
      if (!validSession(value)) throw new Error('会话响应无效');
      if (version === revision.current) { setSession(value); setError(''); }
    } catch {
      if (version === revision.current) setError('无法确认登录状态，请重试。');
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    const focus = () => void refresh();
    window.addEventListener('focus', focus);
    return () => { revision.current++; clearInterval(timer); window.removeEventListener('focus', focus); };
  }, [refresh]);

  async function mutate(action: 'login' | 'password' | 'logout', body?: unknown) {
    if (mutating.current) return;
    mutating.current = true;
    const version = ++revision.current;
    try {
      const response = await fetch('/api/auth/' + action, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json', ...(session ? { 'X-CSRF-Token': session.csrf_token } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (response.status === 401 && action !== 'login') setSession(null);
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(messages[result.code] ?? '操作失败，请稍后重试。');
      }
      if (action === 'logout') { setSession(null); setError(''); return; }
      const value: unknown = await response.json();
      if (!validSession(value)) throw new Error('会话响应无效，请刷新后重试。');
      if (revision.current === version) { setSession(value); setError(''); }
    } finally { mutating.current = false; }
  }
  return <AuthContext.Provider value={{ session, error, refresh, mutate,
    can: permission => !!session && !session.must_change_password && session.permissions.includes(permission),
  }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('AuthProvider is required');
  return auth;
}

export function AuthBoundary({ children, permission }: { children: ReactNode; permission: string }) {
  const auth = useAuth();
  if (auth.error) return <AuthCard><h1>连接暂不可用</h1><p role="alert">{auth.error}</p><button onClick={() => void auth.refresh()}>重试</button></AuthCard>;
  if (auth.session === undefined) return <AuthCard><p role="status">正在确认登录状态…</p></AuthCard>;
  if (!auth.session) return <CredentialsForm />;
  if (auth.session.must_change_password || location.pathname === '/account/password') return <CredentialsForm change />;
  if (!auth.can(permission)) return <AuthCard><h1>无权访问此页面</h1><p>当前账号没有所需权限，请联系管理员。</p><a className="button" href="/">返回首页</a><SessionControls /></AuthCard>;
  return children;
}

function AuthCard({ children }: { children: ReactNode }) {
  return <div className="auth-screen"><main className="auth-card"><img src={sungrowLogo} width={180} height={24} alt="SUNGROW" /><p className="auth-subtitle">资产与油样管理</p>{children}</main></div>;
}

function CredentialsForm({ change = false }: { change?: boolean }) {
  const { session, mutate } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <AuthCard>
    <h1>{change ? (session?.must_change_password ? '首次登录，请修改密码' : '修改密码') : '登录'}</h1>
    <p>{change ? '新密码需为 15–128 个字符，可以使用长口令。改密后其他会话将失效。' : '请使用管理员分配的内部账号。'}</p>
    <form onSubmit={async event => {
      event.preventDefault(); setError('');
      if (change && newPassword !== confirm) { setError('两次新密码不一致。'); return; }
      setBusy(true);
      try {
        await mutate(change ? 'password' : 'login', change ? { current_password: password, new_password: newPassword } : { username, password });
        setPassword(''); setNewPassword(''); setConfirm('');
        if (change && location.pathname === '/account/password') location.assign('/');
      } catch (failure) { setError(failure instanceof Error ? failure.message : '服务暂不可用，请重试。'); }
      finally { setBusy(false); }
    }}>
      {!change && <label>用户名<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} maxLength={80} required disabled={busy} /></label>}
      <label>{change ? '当前密码' : '密码'}<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} maxLength={128} required disabled={busy} /></label>
      {change && <><label>新密码<input type="password" autoComplete="new-password" value={newPassword} onChange={e => setNewPassword(e.target.value)} minLength={15} maxLength={128} required disabled={busy} /></label>
        <label>确认新密码<input type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} minLength={15} maxLength={128} required disabled={busy} /></label></>}
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? '处理中…' : change ? '保存密码并继续' : '登录'}</button>
    </form>
    {change && <SessionControls />}
  </AuthCard>;
}

export function SessionControls() {
  const { session, mutate } = useAuth();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return <div className="session-controls"><span>{session?.actor.display_name}</span>
    {!session?.must_change_password && <a href="/account/password">修改密码</a>}
    <button disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try { await mutate('logout'); } catch { setError('退出失败，请重试。'); } finally { setBusy(false); }
    }}>退出登录</button>{error && <span role="alert">{error}</span>}
  </div>;
}
