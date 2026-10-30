"""Laboratory format1 bounded source codecs and explicit-text template output."""
import csv
import json
from io import BytesIO, StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import Workbook
from .import_contracts import XLSX_TYPE, MAX_FILE_BYTES

SAMPLE_COLUMNS = (
    'source_lab_key','source_lab_name','external_sample_id','source_site_name','source_whole_unit_serial',
    'source_transformer_serial','formal_asset_id','system_asset_number','sampled_at','sampled_timezone',
    'sampling_context','physical_received','received_at','received_timezone','container_count',
    'report_filenames','notes','source_note')
TEST_COLUMNS = (
    'source_lab_key','external_sample_id','external_test_id','test_type','measured_at','measured_timezone',
    'source_method','source_method_version','method_version_id','report_selected','source_instrument',
    'source_analyst','source_qa','h2_value','h2_qualifier','h2_unit','ch4_value','ch4_qualifier','ch4_unit',
    'c2h2_value','c2h2_qualifier','c2h2_unit','c2h4_value','c2h4_qualifier','c2h4_unit',
    'c2h6_value','c2h6_qualifier','c2h6_unit','co_value','co_qualifier','co_unit',
    'co2_value','co2_qualifier','co2_unit','result_value','result_qualifier','result_unit','notes','source_note')

EXPLANATIONS = {
    'source_lab_key':'批次内来源别名：字母开头、字母数字下划线/短横线，最多80；须显式新增或引用稳定来源身份。',
    'source_lab_name':'来源实验室原名，最多200；名称不自动匹配或新建来源。',
    'external_sample_id':'来源油样标识，文本1–160；保留大小写和前导零，检测表使用同一来源别名及标识。',
    'external_test_id':'来源检测标识，文本1–160；每次完整检测或复测不同，不使用数值/日期替代。',
    'source_site_name':'来源现场陈述，最多200；不代表历史归属已核实。',
    'source_whole_unit_serial':'来源整机序列号，文本最多160；不自动绑定正式资产。',
    'source_transformer_serial':'来源变压器序列号，文本最多160；不按序列号与日期合并。',
    'formal_asset_id':'可选正式物理变压器UUID；未知留空，不创建临时资产。',
    'system_asset_number':'可选正式系统资产编号，最多80；不替代油样外部标识。',
    'sampled_at':'采样原时间文本<=80：YYYY-MM-DD或ISO完整时刻；DATE不补午夜。',
    'measured_at':'测量原时间文本<=80：YYYY-MM-DD或ISO完整时刻；缺失保持空白。',
    'received_at':'真实收到实物时的完整ISO时刻；未收实物留空，不能填上传时间。',
    'sampled_timezone':'明确IANA来源时区<=100；不默认浏览器/系统时区。',
    'measured_timezone':'明确IANA来源时区<=100；夏令时重复小时须显式偏移。',
    'received_timezone':'真实收样原时区<=100；无实物不补造。',
    'sampling_context':'SITE / REPAIR_CENTER / OTHER；未知留空待核对。',
    'physical_received':'TRUE/FALSE，明确是否收到实物；不从日期自动判断。',
    'container_count':'未收实物空或0；收到则真实1–20；暂存不创建容器。',
    'report_filenames':'可空或JSON数组（最多100文件名，每名255）；拒绝路径，仅声明PDF，文件始终未提供。',
    'test_type':'DGA / MOISTURE / BREAKDOWN_VOLTAGE；未知类型仍须保留原行。',
    'source_method':'原始方法文本<=160；不猜ASTM兼容性。',
    'source_method_version':'来源方法版本原文<=80；不自动关联系统版本。',
    'method_version_id':'明确批准配置的方法UUID；未知留空，不使用MVP占位方法。',
    'report_selected':'可空或TRUE/FALSE；多条同类检测须明确选择，不自动平均/取最新。',
    'source_instrument':'第三方原仪器文本<=160；不替换为本地仪器或校准通过。',
    'source_analyst':'原分析员文本<=150；未知留空，不替换为上传/核对人。',
    'source_qa':'原质量资料文本<=2000；缺失不推导PASS。',
    'notes':'普通业务备注，可空<=2000字符；与来源备注分别保存。',
    'source_note':'本行资料依据，可空<=2000字符；不作为身份或重复键。'
}


def instructions(example):
    fields = dict(EXPLANATIONS)
    for code in TEST_COLUMNS:
        if code.endswith('_value'):
            fields[code] = '十进制原值；0有效，空白不是ND；全局小于1e12/最多6位小数，仍须批准方法的更严格精度。'
        elif code.endswith('_qualifier'):
            fields[code] = 'EQ / ND / LT / GT；ND无数值，EQ/LT/GT须有有限非负值/边界。'
        elif code.endswith('_unit'):
            fields[code] = '原单位文本<=40；必须与批准方法字段一致，不做转换或兼容推断。'
    return dict(version=1, format='LABORATORY', example_is_synthetic=example,
        columns=dict(samples=list(SAMPLE_COLUMNS), tests=list(TEST_COLUMNS)), fields=fields,
        rules=[
            '仅暂存资料，不创建正式油样、检测、容器或有效结果；PDF仅声明未提供。',
            'DGA每行完整H2/CH4/C2H2/C2H4/C2H6/CO/CO2；微水/击穿用result三列，复测另行。',
            '两份CSV同批UTF-8提交；所有表头必须完整，不能映射任意第三方列。',
            '500油样/2000完整检测；XLSX10MiB；每CSV10MiB、两份20MiB；展开50MiB/200成员/150000单元格。',
            '编号和日期使用文本，保留大小写及前导零；不执行公式、宏或外部链接。',
            '原件私有保留；批次用途HISTORICAL/DAILY、来源身份和来源时区在页面显式确认。',
            '示例为虚构资料；资产、批准方法及单位故意未确认，不能当作科学配置或正式有效结果。'
        ])


def example_rows():
    sample = dict(source_lab_key='LAB_A', source_lab_name='虚构示例实验室', external_sample_id='00017',
                  source_site_name='示例现场（未核实）', sampled_at='2026-01-15',
                  sampling_context='OTHER', physical_received='FALSE', container_count='0',
                  notes='虚构示例，含逗号, 引号"与换行\n请核对原始资料', source_note='示例资料，不是正式证据')
    tests = []
    for index in (1, 2):
        row = dict(source_lab_key='LAB_A', external_sample_id='00017', external_test_id=f'DGA-0{index}',
                   test_type='DGA', measured_at='2026-01-16', source_note='独立复测示例；方法与单位待确认')
        for code in ('h2','ch4','c2h2','c2h4','c2h6','co','co2'):
            row[code+'_value'], row[code+'_qualifier'] = '1.25', 'EQ'
        row['h2_value'], row['h2_qualifier'] = '0', 'EQ'
        row['ch4_value'], row['ch4_qualifier'] = '', 'ND'
        tests.append(row)
    return [sample], tests


def build_template(format, example=False):
    info = instructions(example)
    samples, tests = example_rows() if example else ([], [])
    if format == 'CSV_PAIR':
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name, columns, rows in (('samples.csv', SAMPLE_COLUMNS, samples), ('tests.csv', TEST_COLUMNS, tests)):
                stream = StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(columns)
                writer.writerows([[row.get(c, '') for c in columns] for row in rows])
                archive.writestr(name, stream.getvalue().encode('utf-8'))
            archive.writestr('instructions.json', json.dumps(info, ensure_ascii=False, indent=2).encode('utf-8'))
        return dict(content=output.getvalue(), content_type='application/zip',
                    filename='laboratory-import-v1'+('-example' if example else '')+'-csv.zip')
    book = Workbook()
    book.active.title = 'Format'
    book.active.append(['version', 'format'])
    book.active.append([1, 'LABORATORY'])
    for name, columns, rows in (('油样信息', SAMPLE_COLUMNS, samples), ('检测结果', TEST_COLUMNS, tests)):
        sheet = book.create_sheet(name)
        sheet.append(columns)
        for row in rows:
            sheet.append([row.get(c, '') for c in columns])
        sheet.freeze_panes = 'A2'
        for row in sheet:
            for cell in row:
                cell.data_type, cell.number_format = 's', '@'
    sheet = book.create_sheet('Instructions')
    for rule in info['rules']:
        sheet.append([rule])
    for code, explanation in info['fields'].items():
        sheet.append([code, explanation])
    for row in sheet:
        for cell in row:
            if cell.value is not None:
                cell.data_type = 's'
    result = BytesIO()
    book.save(result)
    return dict(content=result.getvalue(), content_type=XLSX_TYPE,
                filename='laboratory-import-v1'+('-example' if example else '')+'.xlsx')



# Reader DTOs are laboratory-owned; neither asset codecs nor float-converted workbooks
# participate in preserving laboratory source evidence.
from dataclasses import dataclass
from threading import Lock

MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 200
MAX_CELLS = 150000
MAX_CELL_CHARS = 32767
_CSV_LIMIT_LOCK = Lock()


@dataclass(frozen=True)
class RawRow:
    file_id: str
    sheet: str
    row_number: int
    values: dict[str, str | bool | None]
    cell_types: dict[str, str]
    problems: tuple[dict, ...] = ()


@dataclass(frozen=True)
class RawTable:
    file_id: str
    sheet: str
    columns: tuple[str, ...]
    rows: tuple[RawRow, ...]


class ImportFileError(Exception):
    def __init__(self, code, *, file_id=None, sheet=None, row_number=None, field=None):
        self.code, self.file_id, self.sheet = code, file_id, sheet
        self.row_number, self.field = row_number, field
        super().__init__(code)


def _controls(value):
    import unicodedata
    return any(unicodedata.category(char) == 'Cc' and char not in '\t\r\n' for char in value)


def _header(values, columns, **where):
    if len(values) != len(columns) or len(set(values)) != len(values) or set(values) != set(columns):
        raise ImportFileError('schema_invalid', **where)
    return tuple(values)


def _csv_quotes(source, **where):
    # csv.reader(strict=True) still accepts a quote inside an unquoted field.
    # Reject that ambiguous non-dialect input before consuming any business rows.
    state='START'
    for char in source:
        if state=='QUOTED':
            if char=='"':
                state='CLOSED'
        elif state=='CLOSED':
            if char=='"':
                state='QUOTED'
            elif char in ',\r\n':
                state='START'
            else:
                raise ImportFileError('invalid_csv',**where)
        elif state=='START':
            if char=='"':
                state='QUOTED'
            elif char not in ',\r\n':
                state='UNQUOTED'
        elif char=='"':
            raise ImportFileError('invalid_csv',**where)
        elif char in ',\r\n':
            state='START'
    if state=='QUOTED':
        raise ImportFileError('invalid_csv',**where)


def _csv_table(content, file_id, sheet, columns, maximum):
    where = dict(file_id=str(file_id), sheet=sheet)
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE_BYTES:
        raise ImportFileError('import_file_size', **where)
    try:
        source = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ImportFileError('invalid_utf8', **where) from None
    if _controls(source):
        raise ImportFileError('invalid_control_character', **where)
    _csv_quotes(source, **where)
    rows = []
    with _CSV_LIMIT_LOCK:
        previous = csv.field_size_limit()
        csv.field_size_limit(MAX_CELL_CHARS)
        try:
            reader = csv.reader(StringIO(source, newline=''), strict=True)
            try:
                header = _header(next(reader), columns, **where)
            except StopIteration:
                raise ImportFileError('schema_invalid', **where) from None
            for number, cells in enumerate(reader, 2):
                if not cells or all(value == '' for value in cells):
                    continue
                if len(cells) != len(header):
                    raise ImportFileError('schema_invalid', row_number=number, **where)
                if len(rows) >= maximum:
                    raise ImportFileError('business_row_limit', row_number=number, **where)
                values = dict(zip(header, cells))
                problems = tuple(dict(code='formula_not_allowed', field=key, raw_value=value)
                                 for key, value in values.items() if value.startswith('='))
                rows.append(RawRow(str(file_id), sheet, number, values,
                                   {key: 'TEXT' for key in values}, problems))
        except csv.Error as error:
            code = 'cell_text_limit' if 'field larger than field limit' in str(error) else 'invalid_csv'
            raise ImportFileError(code, **where) from None
        finally:
            csv.field_size_limit(previous)
    return RawTable(str(file_id), sheet, tuple(columns), tuple(rows))


def read_csv_pair(samples, tests, *, sample_file_id, test_file_id):
    """Read both complete logical tables or raise; never return a partial pair."""
    return (_csv_table(samples, sample_file_id, '油样信息', SAMPLE_COLUMNS, 500),
            _csv_table(tests, test_file_id, '检测结果', TEST_COLUMNS, 2000))




# OOXML input is read from bounded XML tokens, never from openpyxl's numeric/date
# conversion layer. The latter remains an output-only dependency above.
import posixpath
import re
import stat
import zlib
from urllib.parse import unquote
from zipfile import BadZipFile, ZIP_STORED
from defusedxml import ElementTree as SafeXML
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError

_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_OFFICE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PACKAGE_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
_COORDINATE = re.compile(r'([A-Z]{1,3})([1-9][0-9]{0,6})')
_BLOCKED_PARTS = ('vbaproject', 'externallinks', 'activex', 'oleobject', 'macroenabled')


def _local(tag):
    return tag.rsplit('}',1)[-1]


def _events(data, *, file_id):
    depth = 0
    stream = BytesIO(data)
    try:
        for event, element in SafeXML.iterparse(stream, events=('start','end'),
                forbid_dtd=True, forbid_entities=True, forbid_external=True):
            if event == 'start':
                depth += 1
                if depth > 64:
                    raise ImportFileError('unsafe_xml', file_id=file_id)
            yield event, element
            if event == 'end':
                depth -= 1
    except (ParseError, DefusedXmlException, UnicodeError, ValueError):
        raise ImportFileError('invalid_xlsx', file_id=file_id) from None
    finally:
        stream.close()


def inspect_xlsx_archive(content, *, file_id=None):
    """Bound declared and actual archive bytes before interpreting any part."""
    if not isinstance(content,bytes) or not 0 < len(content) <= MAX_FILE_BYTES:
        raise ImportFileError('import_file_size',file_id=file_id)
    result = {}
    try:
        with ZipFile(BytesIO(content)) as package:
            members = package.infolist()
            if len(members)>MAX_ARCHIVE_MEMBERS:
                raise ImportFileError('archive_member_limit',file_id=file_id)
            folded = set()
            declared = 0
            actual = 0
            for info in members:
                name = info.filename
                parts = name.rstrip('/').split('/')
                if (not name or name.startswith(('/','\\')) or '\\' in name or ':' in name
                        or '%' in name or any(part in ('','.','..') for part in parts)
                        or _controls(name) or name.casefold() in folded
                        or stat.S_ISLNK(info.external_attr>>16)
                        or info.flag_bits & 1
                        or info.compress_type not in (ZIP_STORED,ZIP_DEFLATED)
                        or name.casefold().endswith('.bin')
                        or any(marker in name.casefold() for marker in _BLOCKED_PARTS)):
                    raise ImportFileError('unsafe_archive',file_id=file_id)
                folded.add(name.casefold())
                declared += info.file_size
                if declared>MAX_EXPANDED_BYTES:
                    raise ImportFileError('archive_expanded_limit',file_id=file_id)
                if info.is_dir():
                    continue
                chunks = []
                member_bytes = 0
                with package.open(info) as member:
                    while True:
                        chunk = member.read(min(65536,MAX_EXPANDED_BYTES-actual+1))
                        if not chunk:
                            break
                        member_bytes += len(chunk)
                        actual += len(chunk)
                        if actual>MAX_EXPANDED_BYTES:
                            raise ImportFileError('archive_expanded_limit',file_id=file_id)
                        chunks.append(chunk)
                if member_bytes!=info.file_size:
                    raise ImportFileError('invalid_xlsx',file_id=file_id)
                result[name] = b''.join(chunks)
    except (BadZipFile, RuntimeError, OSError, NotImplementedError, EOFError, zlib.error):
        raise ImportFileError('invalid_xlsx',file_id=file_id) from None
    return result


def _relation_target(owner, target, *, file_id):
    if not isinstance(target,str) or not target or _controls(target) or '\\' in target or ':' in target or '?' in target or '#' in target:
        raise ImportFileError('unsafe_relationship',file_id=file_id)
    target=unquote(target)
    if '%' in target or '\\' in target or ':' in target or _controls(target):
        raise ImportFileError('unsafe_relationship',file_id=file_id)
    path=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(owner),target))
    if path in ('','.','..') or path.startswith('../') or path.startswith('/'):
        raise ImportFileError('unsafe_relationship',file_id=file_id)
    return path


def _relationships(parts, *, file_id):
    by_owner = {}
    for name,data in parts.items():
        if not name.endswith('.rels'):
            continue
        if name=='_rels/.rels':
            owner=''
        else:
            path=name.split('/')
            if len(path)<2 or path[-2]!='_rels' or not path[-1].endswith('.rels'):
                raise ImportFileError('unsafe_relationship',file_id=file_id)
            owner='/'.join(path[:-2]+[path[-1][:-5]])
            if owner not in parts:
                raise ImportFileError('unsafe_relationship',file_id=file_id)
        entries={}
        for event,element in _events(data,file_id=file_id):
            if event=='start' and _local(element.tag)=='Relationships' and element.tag!='{'+_PACKAGE_REL+'}Relationships':
                raise ImportFileError('unsafe_relationship',file_id=file_id)
            if event=='end' and _local(element.tag)=='Relationship':
                attrs=element.attrib
                kind=attrs.get('Type','')
                if attrs.get('TargetMode','').casefold()=='external' or any(token in kind.casefold() for token in _BLOCKED_PARTS):
                    raise ImportFileError('unsafe_relationship',file_id=file_id)
                identifier=attrs.get('Id')
                if not identifier or identifier in entries:
                    raise ImportFileError('unsafe_relationship',file_id=file_id)
                target=_relation_target(owner,attrs.get('Target'),file_id=file_id)
                if target not in parts:
                    raise ImportFileError('unsafe_relationship',file_id=file_id)
                entries[identifier]=(kind,target)
                element.clear()
        by_owner[owner]=entries
    return by_owner


def _validate_parts(parts, *, file_id, xml_parts=()):
    cells=0
    roots={}
    for name,data in parts.items():
        if name not in xml_parts and not (name.casefold().endswith('.xml') or name.casefold().endswith('.rels')):
            continue
        root=None
        for event,element in _events(data,file_id=file_id):
            if root is None:
                root=element.tag
            if event=='start':
                if _local(element.tag)=='f':
                    raise ImportFileError('formula_not_allowed',file_id=file_id)
                if element.tag=='{'+_MAIN+'}c':
                    cells+=1
                    if cells>MAX_CELLS:
                        raise ImportFileError('cell_limit',file_id=file_id)
                if _local(element.tag) in ('Override','Default'):
                    kind=element.attrib.get('ContentType','').casefold()
                    if any(token in kind for token in _BLOCKED_PARTS):
                        raise ImportFileError('unsafe_archive',file_id=file_id)
            else:
                element.clear()
        roots[name]=root
    return roots


def _string(element, *, file_id, sheet=None, row_number=None):
    pieces=[]
    size=0
    for child in element:
        texts=([child] if _local(child.tag)=='t' else
               [part for part in child if _local(part.tag)=='t'] if _local(child.tag)=='r' else [])
        for part in texts:
            value=part.text or ''
            size+=len(value)
            if size>MAX_CELL_CHARS:
                raise ImportFileError('cell_text_limit',file_id=file_id,sheet=sheet,row_number=row_number)
            if _controls(value):
                raise ImportFileError('invalid_control_character',file_id=file_id,sheet=sheet,row_number=row_number)
            pieces.append(value)
    return ''.join(pieces)


def _styles(data, *, file_id):
    if data is None:
        return [0],{}
    formats={}
    xfs=[]
    path=[]
    for event,element in _events(data,file_id=file_id):
        local=_local(element.tag)
        if event=='start':
            path.append(local)
        else:
            try:
                if local=='numFmt':
                    identifier=int(element.attrib['numFmtId'])
                    if identifier in formats:
                        raise ValueError()
                    formats[identifier]=element.attrib['formatCode']
                elif local=='xf' and len(path)>1 and path[-2]=='cellXfs':
                    xfs.append(int(element.attrib.get('numFmtId','0')))
            except (KeyError,ValueError):
                raise ImportFileError('invalid_xlsx',file_id=file_id) from None
            path.pop()
            element.clear()
    return xfs or [0],formats


def _date_style(number_format, formats):
    if number_format in set(range(14,23))|set(range(27,37))|{45,46,47}|set(range(50,59)):
        return True
    code=formats.get(number_format,'')
    code=re.sub(r'"[^"]*"|\\.|_.|\*.','',code)
    code=re.sub(r'\[([^\]]*)\]',lambda match:match.group(0) if re.fullmatch('[hmsHMS]+',match.group(1)) else '',code)
    return re.search('[ymdhs]',code,re.I) is not None


def _shared_strings(data, *, file_id):
    if data is None:
        return []
    strings=[]
    for event,element in _events(data,file_id=file_id):
        if event=='end' and _local(element.tag)=='si':
            if len(strings)>=MAX_CELLS:
                raise ImportFileError('cell_limit',file_id=file_id)
            strings.append(_string(element,file_id=file_id))
            element.clear()
    return strings


def _cell(element, strings, xfs, formats, *, file_id, sheet, row_number):
    where=dict(file_id=file_id,sheet=sheet,row_number=row_number)
    kind=element.attrib.get('t','n')
    if kind=='inlineStr':
        nodes=[node for node in element if _local(node.tag)=='is']
        if len(nodes)>1 or any(_local(node.tag)=='v' for node in element):
            raise ImportFileError('invalid_xlsx',**where)
        return (_string(nodes[0],**where) if nodes else ''),'TEXT'
    values=[node for node in element if _local(node.tag)=='v']
    if len(values)>1:
        raise ImportFileError('invalid_xlsx',**where)
    raw=values[0].text if values else None
    if raw is not None and (len(raw)>MAX_CELL_CHARS or _controls(raw)):
        raise ImportFileError('cell_text_limit' if len(raw)>MAX_CELL_CHARS else 'invalid_control_character',**where)
    if kind=='s':
        try:
            if raw is None or not re.fullmatch(r'[0-9]+',raw):
                raise ValueError()
            index=int(raw)
            if index>=len(strings):
                raise ValueError()
            return strings[index],'TEXT'
        except (ValueError,IndexError):
            raise ImportFileError('invalid_xlsx',**where) from None
    if kind=='b':
        if raw not in ('0','1'):
            raise ImportFileError('invalid_xlsx',**where)
        return raw=='1','BOOLEAN'
    if kind=='str':
        return raw or '','TEXT'
    if kind=='d':
        return raw,'DATE_NUMBER'
    if kind!='n':
        raise ImportFileError('unsupported_cell_type',**where)
    try:
        style=int(element.attrib.get('s','0'))
        if style<0 or style>=len(xfs):
            raise ValueError()
    except ValueError:
        raise ImportFileError('invalid_xlsx',**where) from None
    return raw,('DATE_NUMBER' if _date_style(xfs[style],formats) else 'NUMBER')


def _worksheet(data, strings, xfs, formats, *, file_id, sheet, retain=True):
    rows={}
    seen=set()
    seen_rows=set()
    current=None
    current_values={}
    sheet_data_count=0
    maxrow=maxcol=0
    path=[]
    for event,element in _events(data,file_id=file_id):
        local=_local(element.tag)
        if event=='start':
            path.append(local)
            if len(path)==1 and element.tag!='{'+_MAIN+'}worksheet':
                raise ImportFileError('invalid_xlsx',file_id=file_id,sheet=sheet)
            if local in ('row','col') and element.attrib.get('hidden','0').casefold() not in ('0','false'):
                raise ImportFileError('hidden_input',file_id=file_id,sheet=sheet)
            if local in ('row','col','c','sheetData') and element.tag!='{'+_MAIN+'}'+local:
                raise ImportFileError('invalid_xlsx',file_id=file_id,sheet=sheet)
            if local=='sheetData':
                sheet_data_count+=1
                if len(path)!=2 or sheet_data_count!=1:
                    raise ImportFileError('invalid_xlsx',file_id=file_id,sheet=sheet)
            if local=='row':
                if len(path)!=3 or path[-2]!='sheetData':
                    raise ImportFileError('invalid_xlsx',file_id=file_id,sheet=sheet)
                try:
                    number=int(element.attrib['r'])
                    if number<1 or number>1048576 or number in seen_rows:
                        raise ValueError()
                except (KeyError,ValueError):
                    raise ImportFileError('invalid_cell_coordinate',file_id=file_id,sheet=sheet) from None
                current=number
                current_values={}
                seen_rows.add(number)
        else:
            if local=='c':
                coordinate=element.attrib.get('r','')
                match=_COORDINATE.fullmatch(coordinate)
                if match is None or current is None or len(path)<2 or path[-2]!='row' or coordinate in seen:
                    raise ImportFileError('invalid_cell_coordinate',file_id=file_id,sheet=sheet)
                column=0
                for char in match.group(1):
                    column=column*26+ord(char)-64
                row=int(match.group(2))
                if row!=current or row>1048576 or column>16384:
                    raise ImportFileError('invalid_cell_coordinate',file_id=file_id,sheet=sheet)
                seen.add(coordinate)
                maxrow,maxcol=max(maxrow,row),max(maxcol,column)
                if maxrow*maxcol>MAX_CELLS:
                    raise ImportFileError('sparse_cell_limit',file_id=file_id,sheet=sheet,row_number=row)
                current_values[column]=_cell(element,strings,xfs,formats,file_id=file_id,sheet=sheet,row_number=row)
                element.clear()
            elif local=='row':
                if retain and any(value not in (None,'') for value,_ in current_values.values()):
                    rows[current]=current_values
                current=None
                element.clear()
            path.pop()
    if sheet_data_count!=1:
        raise ImportFileError('invalid_xlsx',file_id=file_id,sheet=sheet)
    return rows


def _business_table(rows, file_id, sheet, columns, maximum):
    where=dict(file_id=file_id,sheet=sheet)
    header_cells=rows.get(1,{})
    if any(column>len(columns) for column in header_cells):
        raise ImportFileError('schema_invalid',row_number=1,**where)
    header=_header([header_cells.get(index,('', 'TEXT'))[0] for index in range(1,len(columns)+1)],
                   columns,row_number=1,**where)
    result=[]
    for number,cells in sorted(rows.items()):
        if number==1:
            continue
        if any(column>len(columns) for column in cells):
            raise ImportFileError('schema_invalid',row_number=number,**where)
        if len(result)>=maximum:
            raise ImportFileError('business_row_limit',row_number=number,**where)
        values={key:cells.get(index,(None,'TEXT'))[0] for index,key in enumerate(header,1)}
        kinds={key:cells.get(index,(None,'TEXT'))[1] for index,key in enumerate(header,1)}
        result.append(RawRow(str(file_id),sheet,number,values,kinds))
    return RawTable(str(file_id),sheet,tuple(columns),tuple(result))


def read_xlsx_tables(content, *, file_id):
    file_id=str(file_id)
    parts=inspect_xlsx_archive(content,file_id=file_id)
    if '[Content_Types].xml' not in parts:
        raise ImportFileError('invalid_xlsx',file_id=file_id)
    relations=_relationships(parts,file_id=file_id)
    xml_parts={target for entries in relations.values() for kind,target in entries.values()
               if kind.rsplit('/',1)[-1] in ('officeDocument','worksheet','styles','sharedStrings')}
    roots=_validate_parts(parts,file_id=file_id,xml_parts=xml_parts)
    documents=[target for kind,target in relations.get('',{}).values() if kind.endswith('/officeDocument')]
    if len(documents)!=1:
        raise ImportFileError('invalid_xlsx',file_id=file_id)
    workbook=documents[0]
    if roots.get(workbook)!='{'+_MAIN+'}workbook':
        raise ImportFileError('invalid_xlsx',file_id=file_id)
    sheets=[]
    for event,element in _events(parts[workbook],file_id=file_id):
        if event=='end' and _local(element.tag)=='sheet':
            if element.attrib.get('state','visible')!='visible':
                raise ImportFileError('hidden_input',file_id=file_id)
            sheets.append((element.attrib.get('name'),element.attrib.get('{'+_OFFICE_REL+'}id')))
            element.clear()
    names=[name for name,_ in sheets]
    if len(names)!=4 or set(names)!={'Format','Instructions','油样信息','检测结果'}:
        raise ImportFileError('schema_invalid',file_id=file_id)
    own=relations.get(workbook,{})
    locations={}
    for name,identifier in sheets:
        kind,target=own.get(identifier,('',''))
        if not kind.endswith('/worksheet') or target in locations.values():
            raise ImportFileError('invalid_xlsx',file_id=file_id)
        locations[name]=target
    extras=[name for name,root in roots.items() if _local(root or '')=='worksheet' and name not in locations.values()]
    if extras:
        raise ImportFileError('schema_invalid',file_id=file_id)
    style_parts=[target for kind,target in own.values() if kind.endswith('/styles')]
    shared_parts=[target for kind,target in own.values() if kind.endswith('/sharedStrings')]
    if len(style_parts)>1 or len(shared_parts)>1:
        raise ImportFileError('invalid_xlsx',file_id=file_id)
    xfs,formats=_styles(parts[style_parts[0]] if style_parts else None,file_id=file_id)
    strings=_shared_strings(parts[shared_parts[0]] if shared_parts else None,file_id=file_id)
    tables={}
    for name,target in locations.items():
        tables[name]=_worksheet(parts[target],strings,xfs,formats,file_id=file_id,sheet=name,retain=name!='Instructions')
    version=tables['Format']
    if (set(version)!={1,2} or {k:v[0] for k,v in version[1].items()}!={1:'version',2:'format'}
            or {k:v[0] for k,v in version[2].items()}!={1:'1',2:'LABORATORY'}):
        raise ImportFileError('schema_invalid',file_id=file_id,sheet='Format')
    return (_business_table(tables['油样信息'],file_id,'油样信息',SAMPLE_COLUMNS,500),
            _business_table(tables['检测结果'],file_id,'检测结果',TEST_COLUMNS,2000))
