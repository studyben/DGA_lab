export type EquipmentDetails = {
  id: string; display_name: string; equipment_name: string | null; tag_number: string | null;
  system_asset_number: string; serial_number: string; model: string | null; material_number: string | null;
  machine_type: string | null; lifecycle_status: string; product_line: string | null;
  commissioning_date: string | null; battery_manufacturer: string | null;
  power_mw: number | string | null; energy_mwh: number | string | null;
};
type Field = { key: keyof EquipmentDetails; label: string; unit?: string };
type Layout = { title: string; fields: Field[] };
const identity: Field[] = [
  { key: 'serial_number', label: '序列号' }, { key: 'model', label: '设备型号' },
  { key: 'material_number', label: '设备物料号' }, { key: 'commissioning_date', label: 'Commissioning date' },
  { key: 'system_asset_number', label: '系统资产号' },
];
const power: Field = { key: 'power_mw', label: '功率', unit: 'MW' };
const energy: Field = { key: 'energy_mwh', label: '电池容量', unit: 'MWh' };
// One stable registration per display type. Identity classification is not a layout key.
export const equipmentLayouts: Record<string, Layout> = {
  INVERTER_UNIT: { title: '逆变器整机', fields: [...identity, power] },
  INVERTER: { title: '逆变器', fields: [...identity, power] },
  ESS_SYSTEM: { title: '储能系统', fields: [...identity, power, energy] },
  PCS_UNIT: { title: 'PCS整机', fields: [...identity, power] },
  PCS: { title: 'PCS本体', fields: [...identity, power] },
  BATTERY_CABINET: { title: '电池柜', fields: [...identity, power, energy, { key: 'battery_manufacturer', label: '电池生产厂商' }] },
  TRANSFORMER: { title: '变压器 / MVT', fields: [...identity] },
};
export const unknownLayout: Layout = { title: '未分类设备', fields: identity };

export function fieldValue(equipment: EquipmentDetails, field: Field) {
  const value = equipment[field.key];
  if (value == null || value === '') return '未提供';
  return field.unit ? `${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })} ${field.unit}` : String(value);
}
