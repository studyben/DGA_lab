export type Metric = { value: string | number | null; reason: string | null };
export type TrendPoint = {
  sample_id: string; test_id: string; barcode: string; sampled_at: string; measured_at: string;
  method_version_id: string; method_name: string; version_label: string; unit: string | null;
  group_id: string; qualifier: 'EQ' | 'ND' | 'LT' | 'GT'; value: string | number | null;
  exclusion_reasons: string[]; site_name: string; equipment_serial: string; instrument_name: string | null;
  warnings: string[]; delta: Metric; annualized_change: Metric; moving_mean: Metric;
};
export type TrendGroup = { id: string; method_name: string; version_label: string; unit: string };
export type TrendData = {
  asset: { id: string; system_asset_number: string; serial_number: string; model: string | null };
  groups: TrendGroup[]; selected_group: TrendGroup | null; points: TrendPoint[];
  latest: TrendPoint | null; latest_numeric: TrendPoint | null; latest_time_tied: boolean; numeric_count: number;
  statistics: Record<'minimum' | 'maximum' | 'mean' | 'delta' | 'annualized_change' | 'moving_mean' | 'regression_slope', Metric>;
};
export const reasonText: Record<string, string> = {
  placeholder_method: '方法尚未配置', missing_unit: '单位尚未配置', different_method: '方法版本不同',
  different_unit: '单位不同', qualified_result: '限定结果不参与统计', no_comparable_group: '没有可比较分组',
  no_numeric_points: '没有有效数值', need_two_numeric_points: '至少需要两个有效数值',
  need_three_numeric_points: '至少需要三个有效数值', same_sampling_time: '采样时间相同，无法计算年化变化',
  need_distinct_sampling_times: '至少需要两个不同的采样时间', excluded_result: '未参与统计',
};
export const numberText = (value: string | number | null) => value === null ? '—' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 });
export const timeText = (value: string) => new Date(value).toLocaleString('zh-CN', { timeZone: 'America/Chicago', hour12: false });
export const readingText = (point: TrendPoint | null) => !point ? '暂无观测' : point.qualifier === 'ND' ? 'ND（未检出）' : `${point.qualifier === 'LT' ? '< ' : point.qualifier === 'GT' ? '> ' : ''}${numberText(point.value)} ${point.unit ?? '单位待配置'}`;
