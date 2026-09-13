import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../Auth';

type ReportState = 'UNAVAILABLE' | 'QUEUED' | 'GENERATING' | 'READY' | 'FAILED';
type ReportStatus = {
  barcode: string;
  state: ReportState;
  unavailable_reason: string | null;
  error_code: string | null;
  requested_at: string | null;
  generated_at: string | null;
};

const unavailableMessages: Record<string, string> = {
  sample_not_finalized: '检测尚未整体定稿，无法生成报告。',
  refinalization_required: '这份历史数据需撤回并重新定稿后才能生成报告。',
  report_not_requested: '报告尚未进入生成队列，请撤回并重新定稿。',
  report_not_current: '当前报告已失效，请撤回并重新定稿。',
};

function stateMessage(report: ReportStatus) {
  if (report.state === 'UNAVAILABLE') {
    return unavailableMessages[report.unavailable_reason ?? ''] ?? '当前没有可用报告。';
  }
  if (report.state === 'QUEUED') return '报告排队中，请稍候…';
  if (report.state === 'GENERATING') return '报告正在生成，请稍候…';
  if (report.state === 'FAILED') return '报告生成失败，可以重试。';
  return '报告已生成，可在线预览或下载。';
}

export function ReportPage() {
  const { session, can } = useAuth();
  const [barcode, setBarcode] = useState(() => (new URLSearchParams(location.search).get('barcode') ?? '').trim().toUpperCase());
  const [report, setReport] = useState<ReportStatus | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);
  const request = useRef<AbortController | null>(null);
  const pollCount = useRef(0);
  const mounted = useRef(true);

  function stopPending() {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    request.current?.abort();
    request.current = null;
  }

  useEffect(() => {
    mounted.current = true;
    const sourceBarcode = (new URLSearchParams(location.search).get('barcode') ?? '').trim().toUpperCase();
    if (sourceBarcode && sourceBarcode.length <= 40) void load(sourceBarcode);
    return () => { mounted.current = false; stopPending(); };
  }, []);

  function schedule(value: string) {
    if (pollCount.current >= 20) {
      setError('报告生成时间较长，请稍后重新查询。');
      return;
    }
    pollCount.current += 1;
    timer.current = window.setTimeout(() => void load(value, true), 1000);
  }

  async function load(value: string, polling = false) {
    const normalized = value.trim().toUpperCase();
    if (!normalized) return;
    if (!polling) { stopPending(); pollCount.current = 0; setBusy(true); }
    else request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setError('');
    try {
      const response = await fetch(`/api/laboratory/reports/by-barcode/${encodeURIComponent(normalized)}`, {
        cache: 'no-store', signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.code === 'sample_not_found' ? '没有找到这个油样条码。' : '报告服务暂不可用，请重试。');
      }
      const current: ReportStatus = await response.json();
      if (!mounted.current || controller.signal.aborted) return;
      setBarcode(current.barcode);
      setReport(current);
      if (current.state === 'QUEUED' || current.state === 'GENERATING') schedule(current.barcode);
    } catch (failure) {
      if (!controller.signal.aborted && mounted.current) {
        setReport(null);
        setError(failure instanceof Error ? failure.message : '报告服务暂不可用，请重试。');
      }
    } finally {
      if (!polling && mounted.current && !controller.signal.aborted) setBusy(false);
    }
  }

  async function retry() {
    if (!report || !session) return;
    stopPending(); setBusy(true); setError('');
    try {
      const response = await fetch(
        `/api/laboratory/reports/by-barcode/${encodeURIComponent(report.barcode)}/retry`,
        {
          method: 'POST', cache: 'no-store',
          headers: { 'X-CSRF-Token': session.csrf_token },
          body: JSON.stringify({}),
        },
      );
      if (!response.ok) throw new Error('无法重新生成报告，请刷新状态后再试。');
      const current: ReportStatus = await response.json();
      setReport(current); pollCount.current = 0; schedule(current.barcode);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '无法重新生成报告。');
    } finally { setBusy(false); }
  }

  const encoded = report ? encodeURIComponent(report.barcode) : '';
  const inlineUrl = encoded ? `/api/laboratory/reports/by-barcode/${encoded}/file?disposition=inline` : '';
  const downloadUrl = encoded ? `/api/laboratory/reports/by-barcode/${encoded}/file?disposition=attachment` : '';

  return <div className="report-workspace">
    <section className="report-search-panel" aria-labelledby="report-search-title">
      <div><span className="step">01 / 条码查询</span><h2 id="report-search-title">查询检测报告</h2><p>输入或扫描油样条码，查看整体定稿后的当前报告。</p></div>
      <form onSubmit={event => { event.preventDefault(); void load(barcode); }}>
        <label>油样条码<input value={barcode} onChange={event => setBarcode(event.target.value)} autoFocus required /></label>
        <button className="primary-action" type="submit" disabled={busy}>{busy ? '查询中…' : '查询报告'}</button>
      </form>
    </section>
    {(report || error) && <section className="report-result-panel" aria-live="polite">
      {error && <p role="alert" className="report-error">{error}</p>}
      {report && <>
        <div className="report-result-heading"><div><span className="step">02 / 报告状态</span><h2>{report.barcode}</h2></div><span className={`report-state ${report.state.toLowerCase()}`}>{report.state === 'READY' ? '已生成' : report.state === 'FAILED' ? '生成失败' : report.state === 'UNAVAILABLE' ? '不可生成' : '生成中'}</span></div>
        <p role="status">{stateMessage(report)}</p>
        {report.generated_at && <p className="report-meta">生成时间：{new Date(report.generated_at).toLocaleString('zh-CN')}</p>}
        {report.state === 'FAILED' && can('laboratory.finalize') && <button type="button" className="primary-action" disabled={busy} onClick={() => void retry()}>重新生成报告</button>}
        {report.state === 'READY' && <>
          <div className="report-actions"><a className="button" href={downloadUrl}>下载 PDF</a><a href={inlineUrl} target="_blank" rel="noreferrer">在新窗口打开</a></div>
          <iframe className="report-preview" src={inlineUrl} title="中文检测报告预览" />
        </>}
      </>}
    </section>}
  </div>;
}
