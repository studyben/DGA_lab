import { TrendData, numberText, readingText, timeText } from './trendTypes';

export function TrendChart({ data }: { data: TrendData }) {
  const points = data.points.filter(p => p.group_id === data.selected_group?.id);
  if (!points.length) return null;
  const times = points.map(p => new Date(p.sampled_at).getTime());
  const values = points.flatMap(p => p.value === null ? [] : [Number(p.value)]);
  const low = Math.min(0, ...values), high = Math.max(1, ...values);
  const first = Math.min(...times), last = Math.max(...times);
  const x = (i: number) => first === last ? 470 : 80 + (times[i]-first)/(last-first)*780;
  const y = (value: string | number) => 260 - (Number(value)-low)/(high-low)*210;
  return <section className="trend-card" aria-label="趋势曲线"><h2>{data.selected_group?.unit} · 采样时间趋势</h2>
    <svg viewBox="0 0 940 370" role="img" aria-label="检测趋势图">
      <title>仅绘制所选方法分组，限定结果以独立符号展示，不按零计入统计。</title>
      {[0,1,2,3].map(i => <g key={i}><line x1="80" x2="860" y1={50+i*70} y2={50+i*70} stroke="#e7ebf0" /><text x="70" y={55+i*70} textAnchor="end">{numberText(high-(high-low)*i/3)}</text></g>)}
      {points.map((point, i) => {
        const numeric = !point.exclusion_reasons.length, prior = points[i-1];
        return <g key={point.test_id}>
          {numeric && prior && !prior.exclusion_reasons.length && <line x1={x(i-1)} y1={y(prior.value!)} x2={x(i)} y2={y(point.value!)} stroke="#bd5a0c" strokeWidth="2" />}
          <g><title>{`${point.barcode} · ${timeText(point.sampled_at)} · ${readingText(point)}`}</title>
            {numeric ? <circle cx={x(i)} cy={y(point.value!)} r="5" fill="#bd5a0c" /> : <text x={x(i)} y={point.value === null ? 300 : y(point.value)} textAnchor="middle" fontWeight="bold">{point.qualifier === 'ND' ? 'ND' : point.qualifier === 'LT' ? '▽' : '△'}</text>}
          </g>
        </g>;
      })}
      <text x="80" y="337">{timeText(points[0].sampled_at)}</text><text x="860" y="357" textAnchor="end">{timeText(points[points.length-1].sampled_at)}</text>
    </svg><p className="trend-help">● 数值　▽ 低于限值　△ 高于限值　ND 未检出（独立标记区，不代表零）。横轴为实际采样时间；限定结果处断开连线。详细数值见下方列表。</p>
  </section>;
}
