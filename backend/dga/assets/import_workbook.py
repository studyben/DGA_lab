"""Private bounded XLSX adapter; business validation belongs to assets."""
from io import BytesIO
from datetime import date, datetime
from math import isfinite
from zipfile import ZipFile
from defusedxml.ElementTree import fromstring
from openpyxl import load_workbook, Workbook
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
from .import_validation import REQUIRED, OPTIONAL, issue

MAX_BYTES = 2 * 1024 * 1024


class WorkbookError(Exception):
    def __init__(self, issues):
        self.issues = issues


def reject(message, row=0, field='file'):
    raise WorkbookError([issue(row, field, message)])


def inspect_archive(content):
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 100 or len({e.filename for e in entries}) != len(entries) or sum(e.file_size for e in entries) > 10 * 1024 * 1024:
            reject('文件展开后超过10 MiB、成员重复或超过100个成员；请拆分或重新保存模板。')
        cells = 0
        for entry in entries:
            if entry.flag_bits & 1 or 'externallinks/' in entry.filename.lower() or entry.filename.lower().endswith('.bin'):
                reject('不接受加密、外部链接或宏；请使用普通 XLSX 模板。')
            data = archive.read(entry)
            if entry.filename.endswith(('.xml', '.rels')):
                root = fromstring(data)
                for node in root.iter():
                    tag = node.tag.rsplit('}', 1)[-1]
                    if tag == 'Relationship' and node.get('TargetMode') == 'External':
                        reject('文件包含外部链接；请移除后上传。')
                    if tag == 'c':
                        column, _ = coordinate_from_string(node.get('r', 'A1'))
                        if column_index_from_string(column) > 32:
                            reject('第32列以外存在内容；请移除模板外数据后上传。')
                        cells += 1
                        if cells > 20000:
                            reject('文件超过20000个单元格（包括参考表）；请拆分批次。')
                    if tag == 'row' and int(node.get('r', '0')) > 501:
                        reject('模板最多500条资产行；请移除远处的空白格式或拆分批次。')
                    if tag == 'f':
                        reject('不接受公式；请粘贴为值后重新上传。')


def parse(content):
    book = None
    try:
        inspect_archive(content)
        book = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        if 'Assets' not in book.sheetnames or set(book.sheetnames) - {'Assets', 'Sites', 'Materials', 'Instructions'}:
            reject('请使用模板中的 Assets 表，不接受其他业务数据表。')
        sheet = book['Assets']
        # Do not trust user-controlled worksheet dimension hints.
        sheet.reset_dimensions()
        iterator = sheet.iter_rows(max_row=501, max_col=32)
        headers = [cell.value for cell in next(iterator)]
        while headers and headers[-1] is None:
            headers.pop()
        if any(not isinstance(h, str) for h in headers) or len(set(headers)) != len(headers):
            reject('列名为空或重复；请重新下载模板。', 1, 'headers')
        missing = set(REQUIRED) - set(headers)
        if missing:
            reject('缺少必填列：' + ', '.join(sorted(missing)), 1, sorted(missing)[0])
        rows = []
        for n, cells in enumerate(iterator, 2):
            if all(cell.value is None for cell in cells):
                continue
            if any(cell.value is not None for cell in cells[len(headers):]):
                reject('有数据的列必须有列名。', n, 'headers')
            values = {}
            for key, cell in zip(headers, cells):
                value = cell.value
                if isinstance(value, float) and not isfinite(value):
                    reject('单元格数值溢出；请填写有限数值后重新上传。', n, key)
                if isinstance(value, str) and (len(value) > 1000 or '\x00' in value):
                    reject('单元格过长或包含无效字符；最多1000字符。', n, key)
                if isinstance(value, (datetime, date)):
                    # Date cells are not guessed into UTC timestamps; validator rejects timezone-free time.
                    value = value.isoformat()
                values[key] = value
            rows.append({'row': n, 'values': values})
        if not rows:
            reject('Assets 表没有资产数据。')
        return rows
    except WorkbookError:
        raise
    except Exception as error:
        raise WorkbookError([issue(0, 'file', '无法安全读取 XLSX 文件；请重新下载模板并粘贴数据值。')]) from error
    finally:
        if book:
            book.close()


def template(sites, materials):
    book = Workbook()
    sheet = book.active
    sheet.title = 'Assets'
    sheet.append(REQUIRED + OPTIONAL)
    for cell in sheet[1]:
        cell.number_format = '@'
    sheet.freeze_panes = 'A2'
    instructions = book.create_sheet('Instructions')
    for line in (
        'v1：只新增资产，不覆盖、合并或更新已有记录；系统自动生成资产编号。',
        '请在 Assets 表填写数据，最多500条。标识和日期时间请使用文本格式，保留序列号前导零。',
        'record_key 在本批次内不同；parent_record_key 仅引用同一批次。无需按父子顺序排列。',
        '必填：' + ', '.join(REQUIRED),
        'effective_at 示例 2025-01-01T08:00:00Z 或 2025-01-01T08:00:00-06:00，不允许未来时间。',
        'SITE：填写参考表 customer_id/site_id，根类型 INVERTER_UNIT 或 ESS_SYSTEM，状态 IN_SERVICE。',
        'PARENT：填写父记录键，不填客户/现场，状态 IN_SERVICE。子设备时间不得早于父设备。',
        'REPAIR_CENTER：客户/现场/父键留空，状态 SPARE、UNDER_REPAIR 或 RETIRED。',
        'PV：INVERTER_UNIT、INVERTER、TRANSFORMER；ESS：ESS_SYSTEM、PCS_UNIT、PCS、BATTERY_CABINET、TRANSFORMER。',
        'material_number 取已有目录，型号/资产类型由物料决定。目录缺失或冲突需管理员处理。',
        'power_mw/energy_mwh 非负且最多6位小数，PV 的 energy_mwh 留空。commissioning_date 格式 YYYY-MM-DD。',
        '参考表只列前500条，填写时也可使用其他已存在记录的明确ID；参考表不导入。',
        '错误阻止整批发布；重复序列号是警告，需要确认是不同物理设备。修改文件请创建新批次。',
    ):
        instructions.append([line])
    for name, headers, records in (
        ('Sites', ('site_id', 'site_name', 'customer_id', 'customer_name', 'product_line'), sites),
        ('Materials', ('material_number', 'model', 'asset_type'), materials),
    ):
        tab = book.create_sheet(name)
        tab.append(headers)
        for record in records:
            tab.append([str(record[h]) if record[h] is not None else '' for h in headers])
        # Explicit text cells keep source strings from becoming Excel formulas.
        for row in tab:
            for cell in row:
                cell.data_type = 's'
                cell.number_format = '@'
        tab.freeze_panes = 'A2'
    result = BytesIO()
    book.save(result)
    return result.getvalue()
