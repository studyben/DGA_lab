type Values = Record<string, string>;
export const machineNames: Values = { INVERTER_UNIT: '逆变器整机', INVERTER: '逆变器', ESS_SYSTEM: '储能系统', PCS_UNIT: 'PCS整机', PCS: 'PCS本体', BATTERY_CABINET: '电池柜', TRANSFORMER: '变压器' };
export const gridNames: Values = { NOT_STARTED: '未开始', IN_PROGRESS: '调试中', COMPLETED: '已完成' };
export const operationNames: Values = { NOT_OPERATIONAL: '未投运', PARTIAL: '部分投运', OPERATIONAL: '已投运', DECOMMISSIONED: '已退役' };
export const lifecycleNames: Values = { COMMISSIONING: '调试中', IN_SERVICE: '在役', OUT_OF_SERVICE: '离役', RETIRED: '停用', MERGED: '已合并' };
export const quantity = (value: string | number | null, unit: string) => value == null ? '未提供' : `${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })} ${unit}`;
export const label = (names: Values, value: string | number | null) => value == null ? '未提供' : names[String(value)] ?? String(value);
