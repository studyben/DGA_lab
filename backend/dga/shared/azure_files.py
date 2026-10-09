"""Azure SDK adapter for the shared file-storage contract."""

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import ContainerClient, ContentSettings

from dga.shared.files import ObjectStorageError


class AzureBlobFileStore:
    def __init__(self, container: ContainerClient):
        self._container = container

    def put(self, *, object_key: str, content: bytes, content_type: str) -> None:
        try:
            self._container.upload_blob(
                name=object_key, data=content, overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError:
            raise ObjectStorageError('object_storage_unavailable') from None

    def get(self, *, object_key: str) -> bytes:
        try:
            return self._container.download_blob(object_key).readall()
        except AzureError:
            raise ObjectStorageError('object_storage_unavailable') from None

    def delete(self, *, object_key: str) -> None:
        try:
            self._container.delete_blob(object_key)
        except ResourceNotFoundError:
            # Match S3 DELETE: an already absent object is a successful cleanup.
            return
        except AzureError:
            raise ObjectStorageError('object_storage_unavailable') from None
