"""Configure the same file store for API and background processes."""

import base64
from urllib.parse import urlsplit

from azure.core.credentials import AzureNamedKeyCredential, TokenCredential
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient

from dga.shared.azure_files import AzureBlobFileStore
from dga.shared.config import Settings
from dga.shared.files import FileStore, S3CompatibleFileStore, UnavailableFileStore


def create_file_store(settings: Settings, *, azure_credential: TokenCredential | None = None) -> FileStore:
    if settings.object_store_provider == 'azure':
        endpoint, container = settings.azure_blob_account_url, settings.azure_blob_container
        if not endpoint or not container or not container.strip():
            raise ValueError('Azure storage requires AZURE_BLOB_ACCOUNT_URL and AZURE_BLOB_CONTAINER')
        try:
            url = urlsplit(endpoint)
            valid_url = bool(url.hostname) and not (url.username or url.password or url.query or url.fragment)
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError('AZURE_BLOB_ACCOUNT_URL must be an account URL without credentials or query parameters')
        credential: TokenCredential | AzureNamedKeyCredential
        if settings.azure_blob_emulator_key:
            if url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1', 'storage-azure', 'azurite'}:
                raise ValueError('AZURE_BLOB_EMULATOR_KEY is only supported for local HTTP Azurite endpoints')
            account = url.path.strip('/')
            if not account or '/' in account:
                raise ValueError('Local Azurite account URL must include its account name')
            emulator_key = settings.azure_blob_emulator_key.get_secret_value()
            try:
                if not base64.b64decode(emulator_key, validate=True):
                    raise ValueError()
            except ValueError:
                raise ValueError('AZURE_BLOB_EMULATOR_KEY must contain a valid base64 test key') from None
            credential = AzureNamedKeyCredential(account, emulator_key)
        else:
            if url.scheme != 'https':
                raise ValueError('AZURE_BLOB_ACCOUNT_URL must use HTTPS outside the local emulator')
            credential = azure_credential if azure_credential is not None else DefaultAzureCredential()
        try:
            client = ContainerClient(endpoint, container, credential=credential,
                                     retry_total=0, connection_timeout=3, read_timeout=10)
        except ValueError:
            raise ValueError('Invalid Azure Blob account or container configuration') from None
        return AzureBlobFileStore(client)
    if (settings.object_store_endpoint and settings.object_store_bucket
            and settings.object_store_access_key and settings.object_store_secret_key):
        return S3CompatibleFileStore(
            settings.object_store_endpoint,
            settings.object_store_bucket,
            settings.object_store_access_key.get_secret_value(),
            settings.object_store_secret_key.get_secret_value(),
            region=settings.object_store_region,
        )
    if settings.object_store_provider is not None:
        raise ValueError('S3 storage requires OBJECT_STORE_ENDPOINT, OBJECT_STORE_BUCKET, '
                         'OBJECT_STORE_ACCESS_KEY and OBJECT_STORE_SECRET_KEY')
    return UnavailableFileStore()
