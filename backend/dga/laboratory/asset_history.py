"""Laboratory-owned, read-only summary for asset viewers (no raw results/files)."""
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import text


class AssetHistoryQuery(BaseModel):
    barcode: str = Field(default='', max_length=160)
    test_type: Literal['DGA', 'MOISTURE', 'BREAKDOWN_VOLTAGE'] | None = None
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


def asset_test_history(engine, asset_id: UUID, query: AssetHistoryQuery) -> dict:
    # Snapshot ancestry is authoritative at sampling time, never serial equality.
    predicate = '''FROM oil_samples s WHERE
        (s.formal_asset_id=:asset OR s.asset_snapshot->'equipment_path' @> CAST(:path AS jsonb))
        AND strpos(lower(s.barcode_value),lower(:barcode))>0
        AND (CAST(:test_type AS text) IS NULL OR EXISTS (SELECT 1 FROM laboratory_tests t
             WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE' AND t.test_type=:test_type))'''
    params = {**query.model_dump(), 'asset': asset_id,
              'path': json.dumps([{'id': str(asset_id)}]),
              'offset': (query.page - 1) * query.page_size}
    with engine.connect() as connection:
        total = connection.execute(text('SELECT count(*) ' + predicate), params).scalar_one()
        rows = connection.execute(text('''SELECT s.id,s.barcode_value,s.sampled_at,
            s.equipment_serial,s.formal_asset_id,s.testing_status,
            (SELECT count(*) FROM laboratory_tests t WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE') AS test_count,
            ARRAY(SELECT DISTINCT t.test_type FROM laboratory_tests t
                  WHERE t.oil_sample_id=s.id AND t.record_status='ACTIVE' ORDER BY t.test_type) AS test_types
            ''' + predicate + ' ORDER BY s.sampled_at DESC,s.id LIMIT :page_size OFFSET :offset'), params).mappings().all()
    return {'samples': [dict(row) for row in rows], 'total': total}
