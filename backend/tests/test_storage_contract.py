import pytest
from pydantic import SecretStr

from dga.shared.files import ObjectStorageError
from dga.shared.file_store_factory import create_file_store
from tests.storage_fixtures import storage_case


def test_selected_provider_preserves_bytes_and_object_names(storage_case):
    case = storage_case
    key = f'{case.prefix}/原始 evidence +%/file.bin'
    content = b'\x00\xfforiginal evidence\r\n'
    try:
        case.store.put(object_key=key, content=content, content_type='application/x-dga-evidence')
        assert case.store.get(object_key=key) == content
        case.store.delete(object_key=key)
        with pytest.raises(ObjectStorageError):
            case.store.get(object_key=key)
    finally:
        case.store.delete(object_key=key)


@pytest.mark.parametrize('operation', ['put', 'get', 'delete'])
def test_provider_permission_failures_are_safe(storage_case, operation):
    case = storage_case
    key = f'{case.prefix}/protected.txt'
    case.store.put(object_key=key, content=b'keep this', content_type='text/plain')
    field = 'azure_blob_emulator_key' if case.container is not None else 'object_store_secret_key'
    wrong = SecretStr('YmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmI=')
    denied = create_file_store(case.settings.model_copy(update={field: wrong}))
    try:
        with pytest.raises(ObjectStorageError, match='object_storage_unavailable') as failure:
            if operation == 'put':
                denied.put(object_key=key, content=b'wrong', content_type='text/plain')
            else:
                getattr(denied, operation)(object_key=key)
        assert wrong.get_secret_value() not in str(failure.value)
        assert case.store.get(object_key=key) == b'keep this'
    finally:
        case.store.delete(object_key=key)


def test_content_type_is_preserved_by_the_storage_service(storage_case, monkeypatch):
    from urllib.request import urlopen

    case = storage_case
    key = f'{case.prefix}/typed.txt'
    response_types = []

    def observe_response(request, timeout):
        response = urlopen(request, timeout=timeout)
        if request.method == 'GET':
            response_types.append(response.headers['Content-Type'])
        return response

    # Observe the real S3 service's public HTTP response, not adapter internals.
    monkeypatch.setattr('dga.shared.files.urlopen', observe_response)
    try:
        case.store.put(object_key=key, content=b'content', content_type='application/x-dga-evidence')
        assert case.store.get(object_key=key) == b'content'
        if case.container is not None:
            assert case.container.get_blob_client(key).get_blob_properties().content_settings.content_type == 'application/x-dga-evidence'
        else:
            assert response_types == ['application/x-dga-evidence']
    finally:
        case.store.delete(object_key=key)
