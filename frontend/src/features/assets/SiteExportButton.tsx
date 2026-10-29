import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';
import './siteExport.css';

export function SiteExportButton() {
  const { can } = useAuth();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  const urls = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  useEffect(() => () => {
    request.current?.abort();
    for (const [url, timer] of urls.current) { clearTimeout(timer); URL.revokeObjectURL(url); }
    urls.current.clear();
  }, []);

  async function download() {
    if (request.current || !can('assets.read')) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await fetch('/api/assets/sites/export', {
        credentials: 'same-origin', cache: 'no-store',
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(60000)]),
      });
      if (!response.ok) throw new Error(response.status === 401 ? '登录已失效，请重新登录后下载。' : response.status === 403 ? '当前账号没有读取现场的权限。' : '现场汇总生成失败，未提供下载文件，请稍后重试。');
      if (response.headers.get('content-type') !== 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') throw new Error('下载响应格式异常，请稍后重试。');
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (!blob.size) throw new Error('下载文件为空，请稍后重试。');
      const url = URL.createObjectURL(blob);
      const timer = setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url); }, 60000);
      urls.current.set(url, timer);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = /^attachment; filename="(site-reference-\d{8}T\d{6}Z\.xlsx)"$/.exec(response.headers.get('content-disposition') ?? '')?.[1] ?? 'site-reference.xlsx';
      document.body.appendChild(anchor);
      try { anchor.click(); } finally { anchor.remove(); }
      setMessage('已生成现场汇总并发起下载，请查看浏览器下载列表。');
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error && e.name === 'TimeoutError' ? '下载响应超时，未完成下载，请稍后重试。' : e instanceof TypeError ? '网络连接失败，未完成下载，请检查连接后重试。' : e instanceof Error ? e.message : '下载失败，请稍后重试。');
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      if (request.current === controller) request.current = null;
    }
  }

  return <section className="site-export" aria-label="现场汇总下载">
    <div><button type="button" disabled={busy || !can('assets.read')} onClick={() => void download()}>{busy ? '正在生成现场汇总…' : '下载当前现场汇总'}</button>
      <span className="site-export-note">XLSX · 全部可读现场，每个现场一行，包含无设备现场；不受当前筛选、分页或产品线影响。</span></div>
    {busy && <p role="status">正在生成下载文件，请稍候…</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
