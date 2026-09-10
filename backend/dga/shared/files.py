"""Shared object-file port and S3-compatible HTTP adapter."""

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class FileStore(Protocol):
    def put(self, *, object_key: str, content: bytes, content_type: str) -> None: ...
    def delete(self, *, object_key: str) -> None: ...


class ObjectStorageError(Exception):
    pass


class UnavailableFileStore:
    def put(self, *, object_key: str, content: bytes, content_type: str) -> None:
        raise ObjectStorageError('object_storage_not_configured')

    def delete(self, *, object_key: str) -> None:
        raise ObjectStorageError('object_storage_not_configured')


class S3CompatibleFileStore:
    """Minimal path-style S3 adapter; bucket provisioning stays in deployment."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, *, region: str = 'us-east-1'):
        self._endpoint = endpoint.rstrip('/')
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region

    def put(self, *, object_key: str, content: bytes, content_type: str) -> None:
        self._request('PUT', object_key, content, content_type)

    def delete(self, *, object_key: str) -> None:
        self._request('DELETE', object_key, b'', 'application/octet-stream')

    def _request(self, method: str, object_key: str, content: bytes, content_type: str) -> None:
        encoded_key = '/'.join(quote(part, safe='') for part in object_key.split('/'))
        url = f'{self._endpoint}/{quote(self._bucket, safe="")}/{encoded_key}'
        parsed = urlsplit(url)
        now = datetime.now(timezone.utc)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = {
            'content-type': content_type,
            'host': parsed.netloc,
            'x-amz-content-sha256': payload_hash,
            'x-amz-date': amz_date,
        }
        signed_headers = ';'.join(sorted(headers))
        canonical_headers = ''.join(f'{name}:{headers[name]}\n' for name in sorted(headers))
        canonical_request = '\n'.join(
            [method, parsed.path, '', canonical_headers, signed_headers, payload_hash]
        )
        scope = f'{date_stamp}/{self._region}/s3/aws4_request'
        string_to_sign = '\n'.join(
            ['AWS4-HMAC-SHA256', amz_date, scope, hashlib.sha256(canonical_request.encode()).hexdigest()]
        )
        key = self._sign(('AWS4' + self._secret_key).encode(), date_stamp)
        key = self._sign(key, self._region)
        key = self._sign(key, 's3')
        key = self._sign(key, 'aws4_request')
        signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        authorization = (
            f'AWS4-HMAC-SHA256 Credential={self._access_key}/{scope}, '
            f'SignedHeaders={signed_headers}, Signature={signature}'
        )
        request = Request(
            url,
            data=content if method == 'PUT' else None,
            method=method,
            headers={**headers, 'authorization': authorization},
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status not in {200, 204}:
                    raise ObjectStorageError(f'object_storage_status_{response.status}')
        except (HTTPError, URLError, TimeoutError) as error:
            raise ObjectStorageError('object_storage_unavailable') from error

    @staticmethod
    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode(), hashlib.sha256).digest()
