"""Small Chinese MVP report renderer driven only by snapshot v1."""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


_FONT = 'STSong-Light'


def render_report_pdf(snapshot: dict, generated_at: datetime) -> bytes:
    """Render a concise current report without inventing rules or formal standards."""
    if snapshot.get('schema_version') != 1 or generated_at.tzinfo is None:
        raise ValueError('unsupported_report_snapshot')
    sample = snapshot['sample']
    output = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))
    document = canvas.Canvas(
        output,
        pagesize=A4,
        pageCompression=0,
        invariant=1,
    )
    width, height = A4
    left, right = 18 * mm, width - 18 * mm
    y = height - 18 * mm

    def new_page():
        nonlocal y
        document.showPage()
        y = height - 18 * mm
        header()

    def header():
        nonlocal y
        document.setFillColor(colors.HexColor('#F47B20'))
        document.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
        document.setFillColor(colors.white)
        document.setFont(_FONT, 15)
        document.drawString(left, height - 11.5 * mm, 'SUNGROW 阳光电源')
        document.setFillColor(colors.HexColor('#202B33'))
        document.setFont(_FONT, 16)
        y = height - 29 * mm
        document.drawString(left, y, '油样检测报告')
        y -= 9 * mm

    def line(label, value):
        nonlocal y
        value_x = left + 38 * mm
        lines = _wrapped_lines(_safe(value), right - value_x, _FONT, 9)
        for index, rendered in enumerate(lines):
            if y < 24 * mm:
                new_page()
            document.setFont(_FONT, 9)
            if index == 0:
                document.setFillColor(colors.HexColor('#52606A'))
                document.drawString(left, y, f'{label}：')
            document.setFillColor(colors.HexColor('#17242D'))
            document.drawString(value_x, y, rendered)
            y -= 6.2 * mm

    def section(title):
        nonlocal y
        if y < 30 * mm:
            new_page()
        y -= 2 * mm
        document.setFillColor(colors.HexColor('#F2F4F5'))
        document.rect(left, y - 5 * mm, right - left, 7 * mm, fill=1, stroke=0)
        document.setFillColor(colors.HexColor('#17242D'))
        document.setFont(_FONT, 10)
        document.drawString(left + 3 * mm, y - 2.5 * mm, title)
        y -= 10 * mm

    header()
    line('条码号', sample['barcode'])
    line('采样时间', sample['sampled_at'])
    line('收样时间', sample['received_at'])
    line('现场名称', sample['site_name'])
    line('设备序列号', sample['equipment_serial'])
    if sample.get('notes'):
        line('样品备注', sample['notes'])

    asset = sample.get('asset_snapshot') or {}
    section('收样时资产快照')
    line('客户名称', asset.get('customer_name'))
    line('现场位置', asset.get('site_location'))
    equipment = asset.get('equipment_path') or []
    line(
        '设备路径',
        ' / '.join(
            f"{item.get('asset_type', '')} {item.get('serial_number', '')}".strip()
            for item in equipment
        ),
    )

    section('检测结果')
    if not snapshot.get('selected_results'):
        line('结果', '无')
    for result in snapshot.get('selected_results', []):
        method = result['method']
        line('检测类型', _test_type(result['test_type']))
        line('检测方法', method.get('display_name'))
        if method.get('method_code'):
            line('标准参考', method['method_code'])
        line('检测时间', result.get('measured_at'))
        if result.get('instrument_name'):
            line('仪器', result['instrument_name'])
        fields = {item['code'].lower(): item for item in method.get('fields', [])}
        for code, measurement in result.get('result', {}).items():
            field = fields.get(code.lower(), {})
            label = field.get('display_name') or code.upper()
            unit = field.get('unit_code')
            line(label, _measurement(measurement, unit))

    section('报告信息')
    finalization = snapshot['finalization']
    line('整体检测定稿时间', finalization['finalized_at'])
    line('定稿人', finalization['finalized_by_display_name'])
    line('报告生成时间', generated_at.isoformat())
    warnings = snapshot.get('acknowledged_warning_codes') or []
    if warnings:
        line('已确认警示', '、'.join(warnings))

    document.setFillColor(colors.HexColor('#77848D'))
    document.setFont(_FONT, 7)
    document.drawRightString(right, 11 * mm, f"条码 {sample['barcode']}")
    document.save()
    return output.getvalue()


def _safe(value) -> str:
    if value is None or value == '':
        return '—'
    return str(value).replace('\r', ' ').replace('\n', ' ')


def _wrapped_lines(value: str, maximum_width: float, font_name: str, font_size: int):
    lines = []
    current = ''
    for character in value:
        candidate = current + character
        if current and pdfmetrics.stringWidth(
            candidate, font_name, font_size
        ) > maximum_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    lines.append(current or '—')
    return tuple(lines)


def _test_type(value: str) -> str:
    return {
        'DGA': '溶解气体分析（DGA）',
        'MOISTURE': '微水',
        'BREAKDOWN_VOLTAGE': '击穿电压',
    }.get(value, value)


def _measurement(value: dict, unit: str | None) -> str:
    qualifier = value.get('qualifier')
    number = value.get('value')
    if qualifier == 'ND':
        rendered = '未检出'
    else:
        prefix = {'EQ': '', 'LT': '< ', 'GT': '> '}.get(qualifier, '')
        rendered = f'{prefix}{number if number is not None else "—"}'
    return f'{rendered} {unit}'.strip() if unit else rendered
