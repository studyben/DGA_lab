"""Synthetic workbook for isolated browser acceptance, never production source data."""
from pathlib import Path
from tests.test_device_material_import import document, equipment

def main():
    materials=[dict(record_key='unit-material',decision='NEW',material_number='NEW:BROWSER/DEVICE-50',model='S3 browser unit',asset_type='WHOLE_UNIT',source_note='Synthetic material approval',reason='Verified new material master')]
    assets=[equipment(record_key='browser-root',serial_number='S3-DEVICE-50',material_ref='NEW:unit-material',site_id='20000000-0000-0000-0000-000000000001',site_name='Wrong source site name',source_note='Synthetic source note: '+ '设备资料依据。'*240)]
    target=Path(__file__).resolve().parents[2]/'frontend/tests/fixtures/device-material-import.xlsx'
    target.write_bytes(document(assets,materials=materials))
if __name__=='__main__': main()
