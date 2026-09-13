export type TestType = 'DGA' | 'MOISTURE' | 'BREAKDOWN_VOLTAGE';
export type Qualifier = 'EQ' | 'ND' | 'LT' | 'GT';
export type FieldConfig = {
  code: string; display_name: string; unit_code: string | null;
  display_decimal_places: number | null; detection_limit: string | number | null;
  quantitation_limit?: string | number | null; minimum?: string | number | null; maximum?: string | number | null;
  allowed_qualifiers: Qualifier[];
};
export type QaCheck = { code: string; label: string; instructions: string };
export type QaResult = QaCheck & { status: 'PASS' | 'FAIL' | 'NOT_RUN'; note: string };
export type MethodDraft = {
  test_type: TestType; display_name: string; version_label: string; standard_reference: string | null;
  fields: FieldConfig[]; qa_checks: QaCheck[];
};
export type CatalogMethod = { id: string; is_active: boolean; configuration: MethodDraft | null } & Omit<MethodDraft, 'fields' | 'qa_checks'>;
export type Instrument = { id: string; code: string; name: string; model: string | null; serial_number: string | null; status: 'ACTIVE' | 'OUT_OF_SERVICE' | 'RETIRED' };
export type Calibration = { id: string; instrument_id: string; calibrated_on: string; expires_on: string | null; outcome: string; provider: string | null; certificate: string | null };
export type PackageItem = { test_type: TestType; method_version_id: string; required: boolean };
export type TestPackage = { id: string; code: string; name: string; items: PackageItem[] };
export type Catalog = { types: { code: TestType; display_name: string; is_active: boolean }[]; methods: CatalogMethod[]; instruments: Instrument[]; calibrations: Calibration[]; packages: TestPackage[] };
export const TYPE_LABEL: Record<TestType, string> = { DGA: 'DGA', MOISTURE: '微水', BREAKDOWN_VOLTAGE: '击穿电压' };
export const FIELD_CODES: Record<TestType, string[]> = { DGA: ['H2','CH4','C2H2','C2H4','C2H6','CO','CO2'], MOISTURE: ['MOISTURE'], BREAKDOWN_VOLTAGE: ['BREAKDOWN_VOLTAGE'] };
export const STATUS_LABEL: Record<string, string> = { ACTIVE:'在用', OUT_OF_SERVICE:'停用', RETIRED:'退役', VALID:'有效', EXPIRED:'已过期', FAILED:'失败', UNKNOWN:'未知', NOT_LINKED:'未关联仪器，未评估', PASS:'通过', FAIL:'失败', NOT_RUN:'未执行' };
