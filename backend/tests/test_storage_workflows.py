"""Existing HTTP/service contracts, PostgreSQL and real isolated storage providers."""

import base64
import hashlib

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from dga.main import create_app
from dga.shared.config import Settings
from dga.shared.files import UnavailableFileStore
from tests.storage_fixtures import storage_case
from tests.test_asset_import import import_context, new_rows, workbook
from tests.test_sample_reception import CHANGED_PASSWORD as IMPORT_PASSWORD
from tests.test_laboratory_workbench import (
    workbench_context, _dga, make_workbench, TestType, CHANGED_PASSWORD,
)


def login_headers(client, username, password):
    response = client.post('/api/auth/login', headers={'Origin': 'http://testserver'},
                           json={'username': username, 'password': password})
    assert response.status_code == 200
    return {'Origin': 'http://testserver', 'X-CSRF-Token': response.json()['csrf_token']}


def test_workbook_upload_uses_selected_provider_and_remains_previewable(storage_case):
    case = storage_case
    engine, actor, imports, _ = import_context(case.settings.database_url.get_secret_value())
    content = workbook(new_rows())
    key = None
    try:
        with TestClient(create_app(case.settings)) as client:
            headers = login_headers(client, 'reception-admin', IMPORT_PASSWORD)
            headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response = client.post('/api/assets/imports', params={'filename': '原始 workbook.xlsx'},
                                   content=content, headers=headers)
            assert response.status_code == 201, response.text
            batch = response.json()
            key = f"asset-imports/{batch['id']}/source.xlsx"
            assert case.store.get(object_key=key) == content
            assert batch['sha256'] == hashlib.sha256(content).hexdigest()
            assert batch['byte_size'] == len(content)
            assert batch['filename'] == '原始 workbook.xlsx'
            imports.validate_next()
            preview = client.get(f"/api/assets/imports/{batch['id']}")
            assert preview.status_code == 200
            assert preview.json()['state'] == 'VALIDATED'
    finally:
        if key:
            case.store.delete(object_key=key)
        engine.dispose()


def attachment_payload(workbench, actor, sample):
    method = next(m for m in workbench.load(actor, sample.barcode_value).methods if m.test_type == TestType.DGA)
    payload = jsonable_encoder(_dga(method.id))
    payload['result']['kind'] = 'DGA'
    payload['attachment'] = {'filename': '原始 evidence.csv', 'content_type': 'text/csv',
                             'content_base64': base64.b64encode(b'H2,10.125\r\n').decode()}
    return payload


def test_attachment_creation_uses_selected_provider_and_keeps_metadata(storage_case, workbench_context):
    case = storage_case
    engine, _, actor, sample = workbench_context
    workbench = make_workbench(engine, case.store)
    payload = attachment_payload(workbench, actor, sample)
    key = None
    try:
        with TestClient(create_app(case.settings)) as client:
            path = f'/api/laboratory/samples/{sample.barcode_value}/tests'
            assert client.post(path, json=payload).status_code == 403
            headers = login_headers(client, 'workbench-admin', CHANGED_PASSWORD)
            invalid = {**payload, 'result': {**payload['result'], 'kind': 'MOISTURE'}}
            assert client.post(path, json=invalid, headers=headers).status_code == 422
            response = client.post(path, json=payload, headers=headers)
            assert response.status_code == 201, response.text
            record = response.json()
            attachment = record['attachments'][0]
            assert attachment['filename'] == '原始 evidence.csv'
            assert attachment['content_type'] == 'text/csv'
            assert attachment['byte_size'] == len(b'H2,10.125\r\n')
            key = f"laboratory/{record['id']}/{attachment['id']}/{attachment['filename']}"
            assert case.store.get(object_key=key) == b'H2,10.125\r\n'
            saved = workbench.load(actor, sample.barcode_value).tests
            assert len(saved) == 1
            assert str(saved[0].attachments[0].id) == attachment['id']
    finally:
        if key:
            case.store.delete(object_key=key)


def test_injected_storage_failure_does_not_create_an_import_batch(database_url):
    engine, actor, imports, _ = import_context(database_url)
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver',
                        object_store_provider='azure')  # DI works even before hosted configuration exists.
    try:
        with TestClient(create_app(settings, file_store=UnavailableFileStore())) as client:
            headers = login_headers(client, 'reception-admin', IMPORT_PASSWORD)
            headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            before = client.get('/api/assets/imports').json()
            response = client.post('/api/assets/imports?filename=source.xlsx', content=workbook(new_rows()), headers=headers)
            assert response.status_code == 503
            assert response.json() == {'code': 'object_storage_unavailable'}
            assert response.headers['cache-control'] == 'no-store'
            assert client.get('/api/assets/imports').json() == before
    finally:
        engine.dispose()


def test_injected_storage_failure_rolls_back_attachment_backed_test(workbench_context, database_url):
    engine, _, actor, sample = workbench_context
    store = UnavailableFileStore()
    workbench = make_workbench(engine, store)
    settings = Settings(database_url=database_url, cookie_secure=False, auth_allowed_origins='http://testserver')
    with TestClient(create_app(settings, file_store=store)) as client:
        headers = login_headers(client, 'workbench-admin', CHANGED_PASSWORD)
        response = client.post(f'/api/laboratory/samples/{sample.barcode_value}/tests', headers=headers,
                               json=attachment_payload(workbench, actor, sample))
        assert response.status_code == 503
        assert response.json() == {'code': 'object_storage_unavailable'}
        assert response.headers['cache-control'] == 'no-store'
        assert workbench.load(actor, sample.barcode_value).tests == ()
