"""Public SDK access to isolated test stores; never accepts production endpoints."""

import os
from dataclasses import dataclass
from uuid import uuid4

import pytest
from azure.storage.blob import ContainerClient
from azure.core.credentials import AzureNamedKeyCredential

from dga.shared.config import Settings
from dga.shared.file_store_factory import create_file_store
from dga.shared.files import FileStore


EMULATOR_KEY = 'YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE='


@dataclass
class StorageCase:
    settings: Settings
    store: FileStore
    container: ContainerClient | None
    prefix: str


@pytest.fixture(params=['s3', 'azure'])
def storage_case(request, database_url):
    if os.getenv('RUN_STORAGE_CONTRACT_TESTS') != '1':
        pytest.skip('Use compose.storage-test.yaml for isolated MinIO/Azurite tests')
    prefix = f'contract-{uuid4().hex}'
    common = dict(database_url=database_url, object_store_provider=request.param,
                  cookie_secure=False, auth_allowed_origins='http://testserver')
    container = None
    if request.param == 'azure':
        settings = Settings(**common, azure_blob_account_url='http://storage-azure:10000/dgatest',
                            azure_blob_container=prefix, azure_blob_emulator_key=EMULATOR_KEY)
        container = ContainerClient(settings.azure_blob_account_url, prefix,
                                    credential=AzureNamedKeyCredential('dgatest', EMULATOR_KEY))
        container.create_container()
    else:
        settings = Settings(**common, object_store_endpoint='http://storage-minio:9000',
            object_store_bucket='dga-storage-tests', object_store_access_key='dga-storage-test',
            object_store_secret_key='isolated-storage-tests-only')
    store = create_file_store(settings)
    try:
        yield StorageCase(settings, store, container, prefix)
    finally:
        if container is not None:
            container.delete_container()
            container.close()
