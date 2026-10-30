"""Attested legacy owner-storage arrangement; assertions use public interfaces."""
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from argon2 import PasswordHasher
from sqlalchemy import text
from dga.shared.auth.public import IdentityService

ROOT = Path(__file__).parent / 'fixtures/finalization_legacy/v1'
PASSWORD = 'Isolated attested loader passphrase 51!'


def corpus():
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    payload = (ROOT / 'cases.json').read_text(encoding='utf-8')
    # Git may convert CRLF/LF. Semantic text digest is portable; captured raw byte
    # digest is provenance only, not a current-checkout equality requirement.
    assert sha256(payload.encode()).hexdigest() == manifest['cases_text_sha256']
    for filename, digest in manifest['pdfs'].items():
        assert sha256((ROOT / 'pdfs' / filename).read_bytes()).hexdigest() == digest
    return json.loads(payload)


def insert_rows(connection, table, rows):
    columns = {r['column_name']: r['data_type'] for r in connection.execute(text(
        """SELECT column_name,data_type FROM information_schema.columns
        WHERE table_schema=current_schema() AND table_name=:table"""), {'table': table}).mappings()}
    if not columns:
        if rows:
            raise AssertionError('Wrong historical fixture schema for ' + table)
        return
    for original in rows:
        row = {key: value for key, value in original.items() if key in columns}
        expressions = []
        for key, value in row.items():
            kind = columns[key]
            if value is not None:
                if kind in ('json', 'jsonb'):
                    row[key] = json.dumps(value)
                elif kind == 'uuid':
                    row[key] = UUID(value) if isinstance(value, str) else value
                elif kind.startswith('timestamp'):
                    row[key] = datetime.fromisoformat(value) if isinstance(value, str) else value
                elif kind == 'date':
                    row[key] = date.fromisoformat(value) if isinstance(value, str) else value
                elif kind == 'numeric':
                    row[key] = Decimal(str(value))
            expressions.append(f'CAST(:{key} AS {kind})' if kind in ('json', 'jsonb') else ':' + key)
        connection.execute(text(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join(expressions)}) ON CONFLICT DO NOTHING"), row)


def load_case(engine, name, files, *, finalized=True):
    if (engine.url.host, engine.url.database, engine.url.username) != ('test-db', 'dga_test', 'dga_test'):
        raise RuntimeError('Legacy loader requires isolated Compose test identity')
    data = corpus()
    case = next(c for c in data['cases'] if c['name'] == name)
    sample_id = case['sample_id']
    tables = data['tables']
    tests = [r for r in tables['laboratory_tests'] if r['oil_sample_id'] == sample_id]
    test_ids = {r['id'] for r in tests}
    method_ids = {r['method_version_id'] for r in tests}
    attachments = [r for r in tables['laboratory_test_attachments'] if r['test_id'] in test_ids]
    object_ids = {r['stored_object_id'] for r in attachments}
    with engine.begin() as c:
        user = data['actor']
        c.execute(text("""INSERT INTO users(id,username,display_name,password_hash,must_change_password)
            VALUES (:id,:name,:display,:password,FALSE) ON CONFLICT(id) DO NOTHING"""),
            dict(id=UUID(user['id']), name=user['username'], display=user['display_name'],
                 password=PasswordHasher().hash(PASSWORD)))
        c.execute(text("""INSERT INTO user_roles(user_id,role_id) SELECT :user,id FROM roles
            WHERE role_code='system_admin' ON CONFLICT DO NOTHING"""), {'user': UUID(user['id'])})
        for table in ('customers', 'sites', 'formal_assets', 'asset_installations'):
            insert_rows(c, table, tables[table])
        insert_rows(c, 'test_method_versions', [r for r in tables['test_method_versions'] if r['id'] in method_ids])
        insert_rows(c, 'test_method_fields', [r for r in tables['test_method_fields'] if r['method_version_id'] in method_ids])
        samples = [dict(r) for r in tables['oil_samples'] if r['id'] == sample_id]
        if not finalized:
            for row in samples:
                row.update(testing_status='OPEN', testing_finalized_by=None, testing_finalized_at=None,
                           testing_finalization_token=None)
        insert_rows(c, 'oil_samples', samples)
        insert_rows(c, 'sample_containers', [r for r in tables['sample_containers'] if r['oil_sample_id'] == sample_id])
        insert_rows(c, 'laboratory_tests', tests)
        for table in ('dga_test_results', 'moisture_test_results', 'breakdown_voltage_test_results'):
            insert_rows(c, table, [r for r in tables[table] if r['test_id'] in test_ids])
        insert_rows(c, 'stored_objects', [r for r in tables['stored_objects'] if r['id'] in object_ids])
        insert_rows(c, 'laboratory_test_attachments', attachments)
        if finalized:
            insert_rows(c, 'laboratory_finalization_events',
                        [r for r in tables['laboratory_finalization_events'] if r['oil_sample_id'] == sample_id])
            reports = [r for r in tables['laboratory_reports'] if r['oil_sample_id'] == sample_id]
            if reports[0]['finalization_token'] != case['token']:
                raise ValueError('Historical observation is not a retained current case')
            insert_rows(c, 'laboratory_reports', reports)
    for key, filename in data['objects'].items():
        files.put(object_key=key, content=(ROOT / filename).read_bytes(), content_type='application/pdf')
    actor = IdentityService(engine).login(data['actor']['username'], PASSWORD).actor
    return case, actor

