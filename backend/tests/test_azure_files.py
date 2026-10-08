import pytest
from azure.core.exceptions import ServiceRequestError

from dga.shared.azure_files import AzureBlobFileStore
from dga.shared.config import Settings
from dga.shared.file_store_factory import create_file_store
from dga.shared.files import ObjectStorageError


@pytest.mark.parametrize('configuration', [
    {},
    {'azure_blob_account_url': 'https://example.blob.core.windows.net'},
    {'azure_blob_account_url': 'https://example.blob.core.windows.net?sig=secret-marker', 'azure_blob_container': 'files'},
    {'azure_blob_account_url': 'http://example.blob.core.windows.net', 'azure_blob_container': 'files'},
    {'azure_blob_account_url': 'https://example.blob.core.windows.net', 'azure_blob_container': 'files', 'azure_blob_emulator_key': 'secret-marker'},
    {'azure_blob_account_url': 'http://azurite:10000/local', 'azure_blob_container': 'files', 'azure_blob_emulator_key': 'secret-marker'},
])
def test_invalid_explicit_azure_configuration_is_actionable_and_safe(configuration):
    with pytest.raises(ValueError) as error:
        create_file_store(Settings(database_url='postgresql+psycopg://test:test@test-db/dga_test',
                                   object_store_provider='azure', **configuration))
    assert 'Azure' in str(error.value) or 'AZURE_' in str(error.value)
    assert 'secret-marker' not in str(error.value)


@pytest.mark.parametrize('operation', ['put', 'get', 'delete'])
def test_sdk_transport_failure_is_translated_without_sdk_details(operation):
    class UnreachableContainer:
        def fail(self, *args, **kwargs):
            raise ServiceRequestError('transport failure with secret-marker')
        upload_blob = download_blob = delete_blob = fail

    store = AzureBlobFileStore(UnreachableContainer())
    with pytest.raises(ObjectStorageError) as error:
        if operation == 'put':
            store.put(object_key='file', content=b'bytes', content_type='text/plain')
        else:
            getattr(store, operation)(object_key='file')
    assert str(error.value) == 'object_storage_unavailable'
    assert error.value.__suppress_context__


def test_hosted_azure_accepts_injected_credential_without_s3_settings():
    class UnavailableCredential:
        def get_token(self, *scopes, **kwargs):
            raise ServiceRequestError('identity unavailable')

    store = create_file_store(Settings(database_url='postgresql+psycopg://test:test@test-db/dga_test',
        object_store_provider='azure', azure_blob_account_url='https://example.blob.core.windows.net',
        azure_blob_container='files'), azure_credential=UnavailableCredential())
    with pytest.raises(ObjectStorageError, match='object_storage_unavailable'):
        store.get(object_key='file')
