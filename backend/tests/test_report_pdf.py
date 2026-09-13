from datetime import datetime, timezone

from reportlab.pdfbase import pdfmetrics
from reportlab.lib.rl_accel import escapePDF
import pytest

from dga.laboratory.report_pdf import _FONT, _wrapped_lines, render_report_pdf


def test_renderer_creates_chinese_pdf_from_snapshot_without_invented_fields(tmp_path):
    snapshot = {
        'schema_version': 1,
        'sample': {
            'barcode': 'DGA-20260802-000001',
            'sampled_at': '2026-08-01T12:00:00+00:00',
            'received_at': '2026-08-02T09:00:00+00:00',
            'site_name': 'Prairie Sun',
            'equipment_serial': 'TX-CURRENT-2002',
            'notes': 'annual sample',
            'identity_status': 'ASSOCIATED',
            'asset_snapshot': {
                'customer_name': 'Prairie Solar LLC',
                'site_name': 'Prairie Sun',
                'site_location': 'Texas, USA',
                'equipment_path': [
                    {'asset_type': 'TRANSFORMER', 'serial_number': 'TX-CURRENT-2002'}
                ],
            },
        },
        'selected_results': [
            {
                'test_id': '77000000-0000-0000-0000-000000000001',
                'test_type': 'DGA',
                'method': {
                    'method_code': None,
                    'display_name': 'DGA（待配置）',
                    'fields': [
                        {'code': 'H2', 'display_name': 'H2', 'unit_code': None}
                    ],
                },
                'measured_at': '2026-08-03T15:30:00+00:00',
                'instrument_name': 'GC-01',
                'notes': None,
                'result': {'h2': {'qualifier': 'EQ', 'value': '10.125000'}},
            }
        ],
        'acknowledged_warning_codes': [],
        'finalization': {
            'token': '88000000-0000-0000-0000-000000000001',
            'finalized_at': '2026-08-05T10:00:00+00:00',
            'finalized_by_user_id': '99000000-0000-0000-0000-000000000001',
            'finalized_by_display_name': 'Lab Admin',
        },
    }

    content = render_report_pdf(
        snapshot,
        generated_at=datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc),
    )
    path = tmp_path / 'report.pdf'
    path.write_bytes(content)

    assert content.startswith(b'%PDF-')
    assert len(content) > 1000
    assert b'ASTM D' not in content


def test_long_mixed_text_wraps_within_the_available_pdf_width():
    text = '超长现场名称' * 40 + ' LONG-SITE-NAME-' * 20

    lines = _wrapped_lines(text, 220, _FONT, 9)

    assert len(lines) > 2
    assert ''.join(lines) == text
    assert all(pdfmetrics.stringWidth(line, _FONT, 9) <= 220 for line in lines)


@pytest.mark.parametrize('kind,code,result_key', [('MOISTURE','MOISTURE','result'),
    ('BREAKDOWN_VOLTAGE','BREAKDOWN_VOLTAGE','result'), ('DGA','H2','h2')])
def test_rendered_pdf_uses_saved_field_unit_and_decimal_places(kind, code, result_key):
    snapshot = {'schema_version': 1, 'sample': dict(barcode='TEST', sampled_at='2026-08-01',
        received_at='2026-08-02', site_name='Test', equipment_serial='TX1'),
        'selected_results': [dict(test_type=kind, method=dict(display_name='Test method',
            fields=[dict(code=code, display_name='Saved label', unit_code='TEST-UNIT', display_decimal_places=2)]),
            result={result_key: dict(qualifier='EQ', value='8.500000')})],
        'finalization': dict(finalized_at='2026-08-03', finalized_by_display_name='Tester')}
    pdf = render_report_pdf(snapshot, datetime(2026,8,4,tzinfo=timezone.utc))
    # PDF text-string escaping only; expected business value is a fixed literal.
    assert escapePDF('8.50 TEST-UNIT'.encode('utf-16-be')).encode('latin1') in pdf
    assert escapePDF('Saved label：'.encode('utf-16-be')).encode('latin1') in pdf
