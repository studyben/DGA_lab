import io
import pytest
from urllib.request import Request

from dga.shared.files import S3CompatibleFileStore


def test_configured_store_preserves_s3_reads_and_unconfigured_failure(monkeypatch):
    from dga.shared.config import Settings
    from dga.shared.file_store_factory import create_file_store
    from dga.shared.files import ObjectStorageError

    base = {'database_url': 'postgresql+psycopg://test:test@test-db/dga_test'}
    monkeypatch.setattr('dga.shared.files.urlopen', lambda request, timeout: FakeResponse(b'original bytes'))
    store = create_file_store(Settings(**base, object_store_provider='s3', object_store_endpoint='http://object-store:9000',
        object_store_bucket='test', object_store_access_key='test', object_store_secret_key='test'))
    assert store.get(object_key='original.xlsx') == b'original bytes'
    with pytest.raises(ObjectStorageError, match='object_storage_not_configured'):
        create_file_store(Settings(**base)).get(object_key='missing')


@pytest.mark.parametrize('provider', ['unknown-secret-value', 's3'])
def test_explicit_invalid_storage_configuration_fails_without_echoing_secrets(provider):
    from dga.shared.config import Settings
    from dga.shared.file_store_factory import create_file_store

    with pytest.raises(ValueError) as failure:
        create_file_store(Settings(database_url='postgresql+psycopg://test:test@test-db/dga_test',
            object_store_provider=provider, object_store_secret_key='do-not-print-this'))
    assert 'do-not-print-this' not in str(failure.value)
    assert 'unknown-secret-value' not in str(failure.value)


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_s3_adapter_get_signs_request_and_returns_bytes(monkeypatch):
    captured = {}

    def fake_open(request: Request, timeout):
        captured['request'] = request
        captured['timeout'] = timeout
        return FakeResponse(b'pdf bytes')

    monkeypatch.setattr('dga.shared.files.urlopen', fake_open)
    store = S3CompatibleFileStore(
        'http://object-store:9000', 'dga-lab', 'access', 'secret'
    )

    content = store.get(object_key='laboratory/reports/a report.pdf')

    assert content == b'pdf bytes'
    assert captured['request'].method == 'GET'
    assert captured['request'].full_url.endswith('/dga-lab/laboratory/reports/a%20report.pdf')
    assert captured['timeout'] == 10
