"""Private asset rules for new-only import previews; also used at publication."""
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID
from collections import Counter
from sqlalchemy import text

REQUIRED = ('record_key', 'serial_number', 'material_number', 'product_line',
            'machine_type', 'status', 'location_kind', 'effective_at')
OPTIONAL = ('customer_id', 'site_id', 'parent_record_key', 'power_mw', 'energy_mwh',
            'equipment_name', 'tag_number', 'commissioning_date', 'battery_manufacturer')
TEXT_LIMITS = dict(record_key=120, serial_number=160, material_number=120, product_line=3,
                   machine_type=40, status=30, location_kind=30, parent_record_key=120,
                   equipment_name=200, tag_number=160, battery_manufacturer=200)
KINDS = {'PV': {'INVERTER_UNIT', 'INVERTER', 'TRANSFORMER'},
         'ESS': {'ESS_SYSTEM', 'PCS_UNIT', 'PCS', 'BATTERY_CABINET', 'TRANSFORMER'}}


def issue(row, field, message, severity='ERROR'):
    return dict(row=row, field=field, message=message, severity=severity)


def summary(rows, issues):
    errors = {i['row'] for i in issues if i['severity'] == 'ERROR'}
    warnings = {i['row'] for i in issues if i['severity'] == 'WARNING'} - errors
    return dict(total_rows=len(rows), valid_rows=sum(r['row'] not in errors | warnings for r in rows),
                error_rows=len(errors), warning_rows=len(warnings),
                error_count=sum(i['severity'] == 'ERROR' for i in issues),
                warning_count=sum(i['severity'] == 'WARNING' for i in issues))


def validate(c, source, now):
    materials = {r['material_number']: dict(r) for r in c.execute(text('SELECT * FROM asset_materials')).mappings()}
    sites = {str(r['id']): dict(r) for r in c.execute(text('SELECT id,customer_id FROM sites')).mappings()}
    lines = {(str(r['site_id']), r['product_line']) for r in c.execute(text('SELECT site_id,product_line FROM site_product_lines')).mappings()}
    rows, issues = [], []
    for entry in source:
        n, raw = entry['row'], entry['values']
        values = {key: raw.get(key) for key in REQUIRED + OPTIONAL}

        def error(field, message):
            issues.append(issue(n, field, message))

        for key in raw.keys() - set(REQUIRED + OPTIONAL):
            error(key, '不支持此列；本模板只新增资产，不接收资产ID、更新操作或历史结束时间。')
        for key, limit in TEXT_LIMITS.items():
            value = values[key]
            if value is None or value == '':
                values[key] = None
                if key in REQUIRED:
                    error(key, '必填；请填写文本值。')
            elif not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                error(key, f'请填写不超过 {limit} 字符的文本；标识列请使用 Excel 文本格式。')
                values[key] = None
            else:
                values[key] = value.strip()
        for key in ('customer_id', 'site_id'):
            if values[key] not in (None, ''):
                try:
                    values[key] = str(UUID(values[key]))
                except (ValueError, TypeError, AttributeError):
                    error(key, '请从参考表复制已有记录的完整ID。')
                    values[key] = None
            else:
                values[key] = None
        try:
            dt = datetime.fromisoformat(values['effective_at'])
            if dt.tzinfo is None or dt > now:
                raise ValueError()
            values['effective_at'] = dt.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            error('effective_at', '填写带时区且不晚于当前时间的日期时间，例如 2025-01-01T08:00:00Z。')
            values['effective_at'] = None
        for key in ('power_mw', 'energy_mwh'):
            value = values[key]
            if value in (None, ''):
                values[key] = None
                continue
            try:
                number = Decimal(str(value))
                if not number.is_finite() or not 0 <= number < Decimal('10000000000') or number.as_tuple().exponent < -6:
                    raise ValueError()
                values[key] = str(number)
            except (InvalidOperation, ValueError):
                error(key, '请填写非负有限数值，最多6位小数，且小于10000000000。')
                values[key] = None
        if values['commissioning_date'] not in (None, ''):
            try:
                values['commissioning_date'] = date.fromisoformat(values['commissioning_date']).isoformat()
            except (TypeError, ValueError):
                error('commissioning_date', '请以文本填写日期 YYYY-MM-DD。')
                values['commissioning_date'] = None
        else:
            values['commissioning_date'] = None
        material = materials.get(values['material_number'])
        if material is None:
            error('material_number', '物料未在可用目录中；请核对参考表，联系管理员处理缺失或冲突的物料。')
        else:
            values.update(model=material['model'], asset_type=material['asset_type'])
            if (values['machine_type'] == 'TRANSFORMER') != (material['asset_type'] == 'TRANSFORMER'):
                error('machine_type', '机器类型与物料对应的资产类型不一致。')
        if values['product_line'] not in KINDS:
            error('product_line', '请选择 PV 或 ESS。')
        elif values['machine_type'] not in KINDS[values['product_line']]:
            error('machine_type', '机器类型不属于该产品线；请核对模板说明。')
        if values['product_line'] == 'PV' and values['energy_mwh'] is not None:
            error('energy_mwh', '光伏设备只填写 MW，MWh 必须留空。')
        location = values['location_kind']
        if location == 'SITE':
            site = sites.get(values['site_id'])
            if not site:
                error('site_id', '请选择已存在的现场ID。')
            elif str(site['customer_id']) != values['customer_id']:
                error('customer_id', '客户ID与该现场的已有客户不一致。')
            if site and (values['site_id'], values['product_line']) not in lines:
                error('site_id', '该现场尚未配置此产品线，请联系管理员。')
            if values['machine_type'] not in ('INVERTER_UNIT', 'ESS_SYSTEM'):
                error('machine_type', '只有光伏整机或储能系统可以直接归属现场。')
            if values['parent_record_key']:
                error('parent_record_key', '直接归属现场时请留空父记录键。')
        elif location in ('PARENT', 'REPAIR_CENTER'):
            for key in ('site_id', 'customer_id'):
                if values[key]:
                    error(key, '子设备继承位置，维修中心无客户现场；请留空此列。')
            if location == 'REPAIR_CENTER' and values['parent_record_key']:
                error('parent_record_key', '维修中心独立设备请留空父记录键。')
            if location == 'PARENT' and not values['parent_record_key']:
                error('parent_record_key', '请填写同一批次中父设备的 record_key。')
        else:
            error('location_kind', '请选择 SITE、PARENT 或 REPAIR_CENTER。')
        allowed = ('SPARE', 'UNDER_REPAIR', 'RETIRED') if location == 'REPAIR_CENTER' else ('IN_SERVICE',)
        if values['status'] not in allowed:
            error('status', '状态与位置不一致：现场/已安装子设备为 IN_SERVICE；维修中心为 SPARE、UNDER_REPAIR 或 RETIRED。')
        rows.append(dict(row=n, values=values))
    keys = Counter(r['values']['record_key'] for r in rows)
    by_key = {r['values']['record_key']: r['values'] for r in rows if keys[r['values']['record_key']] == 1}
    serials = Counter(r['values']['serial_number'].lower() for r in rows if r['values']['serial_number'])
    existing = {}
    for asset in c.execute(text('''SELECT serial_number,system_asset_number,model FROM formal_assets
            WHERE lower(serial_number)=ANY(:serials) ORDER BY system_asset_number'''), {'serials': list(serials)}).mappings():
        existing.setdefault(asset['serial_number'].lower(), []).append(f"{asset['system_asset_number']} / {asset['model'] or '型号未知'}")
    for row in rows:
        n, v = row['row'], row['values']
        key, serial = v['record_key'], v['serial_number']
        if key and keys[key] > 1:
            issues.append(issue(n, 'record_key', '记录键在本批次重复；请为每台新资产分配不同记录键。'))
        if serial and (serials[serial.lower()] > 1 or serial.lower() in existing):
            matches = '；'.join(existing.get(serial.lower(), [])[:5]) or '本批次其他行'
            issues.append(issue(n, 'serial_number', f'序列号重复（{matches}）；请确认是不同物理设备。本导入只新增，不覆盖或合并。', 'WARNING'))
        current, visited = v, set()
        while current['location_kind'] == 'PARENT':
            current_key = current['record_key']
            if current_key in visited or len(visited) >= 99:
                issues.append(issue(n, 'parent_record_key', '父子关系存在循环或超过99层，请检查父记录键。'))
                break
            visited.add(current_key)
            parent = by_key.get(current['parent_record_key'])
            if not parent:
                issues.append(issue(n, 'parent_record_key', '父记录键不存在或重复，必须引用本批次中一条明确记录。'))
                break
            if current['effective_at'] and parent['effective_at'] and current['effective_at'] < parent['effective_at']:
                issues.append(issue(n, 'effective_at', '子设备安装时间不能早于父设备初始位置生效时间。'))
            if current['product_line'] != parent['product_line']:
                issues.append(issue(n, 'parent_record_key', '父子设备产品线不一致。'))
            if parent['status'] == 'RETIRED':
                issues.append(issue(n, 'parent_record_key', '不能安装在已停用的父设备下面。'))
            current = parent
    return rows, issues, summary(rows, issues)
