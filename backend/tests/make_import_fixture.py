"""Generate the deterministic XLSX browser input fixture, not user data."""
import sys
from pathlib import Path
from tests.test_asset_import import workbook

if __name__ == '__main__':
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(workbook([dict(record_key='new-spare', serial_number='TX-CURRENT-2002',
        material_number='MAT-TX-41', product_line='PV', machine_type='TRANSFORMER',
        status='SPARE', location_kind='REPAIR_CENTER', effective_at='2025-01-01T08:00:00Z')]))
