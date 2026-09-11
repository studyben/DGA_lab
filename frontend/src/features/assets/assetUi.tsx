import { useEffect, useState, type ReactNode } from 'react';
type Values = Record<string, string>;
type Column<T> = { key: Extract<keyof T, string>; label: string; render?: (row: T) => ReactNode };
const cellText = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? value : '未提供';

export function useQuery() {
  const [query, setQuery] = useState<Values>(() => Object.fromEntries(new URLSearchParams(location.search)));
  function update(patch: Values, reset = false) {
    const next = { ...(reset ? { product_line: query.product_line ?? 'PV', columns: query.columns ?? '' } : query), ...patch };
    const search = new URLSearchParams(Object.entries(next).filter(([, value]) => value !== ''));
    history.replaceState(null, '', location.pathname + '?' + search.toString());
    setQuery(next);
  }
  return { query, update };
}

export function useRead<T>(url: string) {
  const [attempt, retry] = useState(0);
  const [state, setState] = useState<{ url: string; data?: T; error?: string }>({ url: '' });
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    setState({ url });
    void (async () => {
      try {
        const response = await fetch(url, { signal: controller.signal, cache: 'no-store' });
        if (!response.ok) throw new Error(response.status === 404 ? '未找到请求的资料。' : response.status === 401 ? '登录已失效，请重新登录。' : response.status === 403 ? '没有查看资料的权限。' : response.status === 409 ? '设备安装关系不完整或存在冲突，请联系管理员。' : response.status === 422 ? '筛选条件无效，请清除筛选后重试。' : '资产服务暂不可用，请重试。');
        const data: T = await response.json();
        if (active) setState({ url, data });
      } catch (error) {
        if (active) setState({ url, error: error instanceof Error && error.name !== 'AbortError' ? error.message : '请求超时，请重试。' });
      } finally { clearTimeout(timeout); }
    })();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [url, attempt]);
  return { data: state.url === url ? state.data : undefined, error: state.url === url ? state.error : undefined, retry: () => retry(v => v + 1) };
}

export function DataTable<T extends { id: string }>({ name, rows, total, columns, query, update, href }: {
  name: string; rows: T[]; total: number; columns: Column<T>[]; query: Values;
  update: (patch: Values) => void; href?: (row: T) => string;
}) {
  const hidden = new Set((query.columns ?? '').split(',').filter(Boolean));
  const visible = columns.filter((c, index) => index === 0 || !hidden.has(c.key));
  const page = Math.max(1, Number(query.page) || 1), pageSize = Number(query.page_size) || 20;
  const sort = query.sort ?? columns[0].key;
  return <section className="dashboard-table-panel">
    <div className="table-toolbar"><h2>{name} <small>共 {total} 条</small></h2>
      <details><summary>显示列</summary><div className="column-options">{columns.slice(1).map(c => <label key={c.key}><input type="checkbox" checked={!hidden.has(c.key)} onChange={() => {
        if (hidden.has(c.key)) hidden.delete(c.key); else hidden.add(c.key);
        update({ columns: [...hidden].join(',') });
      }} />{c.label}</label>)}</div></details>
    </div>
    <div className="dashboard-table-scroll"><table aria-label={name}><thead><tr>{visible.map(c => <th key={c.key} aria-sort={sort === c.key ? query.direction === 'desc' ? 'descending' : 'ascending' : 'none'}>
      <button onClick={() => update({ sort: c.key, direction: sort === c.key && query.direction !== 'desc' ? 'desc' : 'asc', page: '1' })}>{c.label}{sort === c.key ? query.direction === 'desc' ? ' ↓' : ' ↑' : ''}</button>
    </th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id} className={href ? 'clickable-row' : undefined} onClick={href ? e => { if (!(e.target as HTMLElement).closest('a')) location.assign(href(row)); } : undefined}>
      {visible.map((c, index) => <td key={c.key}>{index === 0 && href ? <a href={href(row)}>{cellText(row[c.key])}</a> : c.render ? c.render(row) : cellText(row[c.key])}</td>)}
    </tr>)}</tbody></table></div>
    {rows.length === 0 && <p className="dashboard-empty" role="status">没有符合条件的记录。</p>}
    <div className="table-paging"><label>每页条数 <select value={String(pageSize)} onChange={e => update({ page_size: e.target.value, page: '1' })}>{[1, 10, 20, 50, 100].map(n => <option key={n}>{n}</option>)}</select></label>
      <span>第 {page} 页 / 共 {Math.max(1, Math.ceil(total / pageSize))} 页</span>
      <button disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>上一页</button>
      <button disabled={page * pageSize >= total} onClick={() => update({ page: String(page + 1) })}>下一页</button>
    </div>
  </section>;
}
