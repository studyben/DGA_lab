# PR #30 — CI image availability repair

User authorized resolving the CI image blocker, then continuing publication and merge.

## Reproduction and diagnosis

GitHub Actions run 34670298133 fails before application tests: `pull access denied for minio/mc`.

Minimal remote probe (does not accept local image cache as evidence):

```powershell
docker manifest inspect minio/mc:RELEASE.2025-04-16T18-13-26Z
```

Result: denied / authentication required, exit 1. Repeated with an empty temporary Docker configuration to eliminate local credential effects. Both Docker Hub server and client tags fail anonymously. The same versions under Quay return manifests including linux/amd64 and linux/arm64. Local Docker Hub images were already cached, explaining why earlier local startup did not expose remote availability failure.

Ranked hypotheses: unavailable Docker Hub repository/tag; local credential interference; same release available through official alternate registry. Credential interference is ruled out by anonymous probes. No claim is made about the registry operator's reason for denial.

## Minimal fix

Change only the two registry-qualified image references in compose.yaml to `quay.io/minio/minio` and `quay.io/minio/mc`, retaining the exact release tags. No data migration, volume change, permission change, third-party repackaging or product-version upgrade.

Official provenance: [MinIO server Docker documentation](https://github.com/minio/minio/blob/master/docs/docker/README.md) and [MinIO client publishing script](https://github.com/minio/mc/blob/master/docker-buildx.sh).

## Regression seam

The actual seam is remote image pull plus Compose startup/bucket initialization, followed by the existing Foundation checks. A static string assertion would not detect this outage. Validate with `docker compose -p dga-issue10-ci-fix pull object-store object-store-init`, isolated full stack startup, and GitHub CI before merging. Do not bypass CI or change branch protections.

Local results: explicit Compose pull passed for both Quay images; `DGA_PORT=18091 docker compose -p dga-issue10-ci-fix up --build -d --wait` passed, including migrations, bucket initialization and API/frontend health. Existing preview stacks were not changed. No debug instrumentation was added.
