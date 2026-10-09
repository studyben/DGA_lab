# Object storage configuration

The API and report worker use the same `FileStore` factory and the existing
`put/get/delete` interface. Configure both processes with the same provider and
namespace. Applications retain their existing object keys and database references.
Switching providers does not copy files; this change contains no migration tool.

## Local MinIO

`compose.yaml` and the browser acceptance configuration select `s3` explicitly:

```dotenv
OBJECT_STORE_PROVIDER=s3
OBJECT_STORE_ENDPOINT=http://object-store:9000
OBJECT_STORE_BUCKET=dga-lab
OBJECT_STORE_ACCESS_KEY=dga-local
OBJECT_STORE_SECRET_KEY=local-object-storage-only
OBJECT_STORE_REGION=us-east-1
```

These are disposable local credentials. Azure settings are unnecessary. Provision
the bucket outside the application (the local Compose initializer does this).

## Azure configuration boundary

```dotenv
OBJECT_STORE_PROVIDER=azure
AZURE_BLOB_ACCOUNT_URL=https://<account>.blob.core.windows.net
AZURE_BLOB_CONTAINER=<existing-private-container>
```

S3 settings are unnecessary. Account URLs must not contain credentials or SAS query
strings. The SDK uses `DefaultAzureCredential`; the factory also accepts an injected
token credential, and the adapter accepts an injected SDK container client. These
boundaries allow testing before IT selects the hosted identity mechanism. This
ticket does not approve a production credential fallback. Leave
`AZURE_BLOB_EMULATOR_KEY` unset outside isolated local tests. Container provisioning,
RBAC, network access, and the final hosted credential configuration are separate
deployment responsibilities under #43/#44.

Unknown providers and incomplete explicitly selected configurations fail at startup
with sanitized errors. Without a provider, complete legacy S3 settings still work;
otherwise the deliberate unavailable store remains, so non-file operations and
tests with an injected store remain usable. File operations return the existing
503 `object_storage_unavailable` response when storage fails. The report worker
requires a configured store. Credentials are not verified during construction.

## Isolated verification

```sh
docker compose -f compose.yaml -f compose.storage-test.yaml --profile test run --build --rm api-test
```

The overlay uses a disposable PostgreSQL database, MinIO bucket, and Azurite
containers with tmpfs data and no host ports. CI runs this command. Without the
overlay, provider integration tests are explicitly skipped; unit and existing
application tests still run. The fixture creates a fresh Azure container per test
and uses a fixed test-only key with `http://storage-azure:10000/dgatest`. The factory
only accepts emulator keys on named local HTTP endpoints, and validates key syntax.

Both providers run the same byte, content-type, Unicode/space-key, deletion,
missing-object and permission-failure checks. HTTP tests submit workbooks and
attachment-backed tests through real provider selection and PostgreSQL; injected
storage failures verify the existing 503 response and no successful database record.
Azure SDK transport failures are tested at the external client boundary.

Azurite evidence is local protocol coverage, not real Azure acceptance. Azure report
lifecycle acceptance belongs to #42. Hosted identity, real Azure smoke tests and
deployment acceptance belong to #44. Production recovery remains part of #20.
