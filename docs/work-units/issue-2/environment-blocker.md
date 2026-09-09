# Issue #2 — execution environment blocker

- Recorded from local system clock: 20260908-212246
- Gate: implementation, S1
- Artifact: docs/work-units/issue-2/environment-blocker.md
- Completion: RESOLVED during user-authorized Docker repair; historical evidence below retained.

## Resolution

Both runtime socket directories had inaccessible zero-byte reparse files. Renaming the parent directories preserves those files while allowing Docker to recreate working sockets. After stopping failed Desktop processes and rebuilding both directories together, `docker version` returned Linux Server 29.4.3 and real PostgreSQL containers ran successfully. Backups remain under Docker/run.issue2-backup-* and docker-secrets-engine.issue2-backup-* in the user's local AppData. No volumes or persistent container data were deleted by this agent. Related upstream report: https://github.com/docker/desktop-feedback/issues/460 .

## Evidence

Docker CLI 29.4.3 and Compose 5.1.3 exist. Docker Desktop startup was attempted through its CLI and the installed desktop executable. Both default and desktop-linux engine endpoints were checked; neither produced a running engine.

Docker backend log on the second launch reports:

```text
starting services: initializing Inference manager:
... AppData\Local\Docker\run\dockerInference:
The file cannot be accessed by the system.
```

The exact file was checked: zero bytes, Archive + ReparsePoint, under the Docker run directory. A targeted reversible rename to a backup filename failed with the same Windows error. `fsutil reparsepoint query` returned Windows error 1920. No socket deletion, factory reset, database deletion, WSL reset or global Docker cleanup was performed. Backup rename did not succeed; no backup was created.

## Decision and limits

The accepted S1 explicitly needs real PostgreSQL and executable red/green evidence. Docker is not simply slow to download images: its backend exits before the Linux engine becomes available. Do not record an environment failure as the intended test red, and do not replace PostgreSQL with SQLite.

Plan and plan review are complete and committed in eb58a15. S1 production implementation and all runtime tests remain unstarted. No scope or business contract question is open.

## Recovery and owner

Restore Docker Desktop until `docker version` includes a Server section and Linux containers can start; then resume directly at S1 of plan.md, without repeating goal confirmation or plan approval. Deeper host-level repair or a Docker reset must not be inferred from the application-development scope. Environment recovery is the remaining decision with the user; implementation remains owned by this work unit. Authentication and deployment risks remain assigned to #3 and #20 respectively.

## Docs decision

Persist this blocker and current entry point locally. Existing user documents remain untouched. This artifact is not an implementation completion or a successful review result.
