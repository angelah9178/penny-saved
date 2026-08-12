# Release and Rollback Checklist

Use this checklist only after the release-control sheet and manual acceptance record
are complete. It is an operating guide, not permission to deploy. Every step labeled
**PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION** must be approved by the
release owner before an authorized operator runs it.

Record: release version **_; immutable commit SHA _**; operator **_; release owner
_**; incident lead **_; start time _**; observation window **_; change ticket _**

## 1. Pre-Release Checklist

- [ ] Confirm every required decision in `development/release-decisions.md` is ready.
- [ ] Confirm `development/DEV-024-manual-acceptance.md` is signed and passed.
- [ ] Record the full 40-character commit SHA and immutable artifact identifier.
- [ ] Record the previous approved artifact, configuration version, and dependency-lock
      checksum so application rollback has an exact target.
- [ ] Run `make check`, `make security-check`, `make rehearse-restore`, and `make e2e`.
- [ ] Verify the artifact was built from the recorded SHA and cannot be overwritten.
- [ ] Confirm the backup, migration, application, monitoring, and incident owners.
- [ ] Verify DNS resolves to the approved host, the TLS certificate is valid, renewal is
      monitored, and the reverse proxy exposes only the intended public endpoints.
- [ ] Verify the dedicated non-root service user and approved secret-file owner/mode;
      confirm PostgreSQL is not public and private metrics use the approved access path.

### Capacity Stop Check

Before approval, use read-only platform tools (for example, `df -h` and `df -i`) to
record available storage. Stop when any applicable filesystem has less than **20% free bytes**,
less than **20% free inodes**, or insufficient free space for two release
artifacts plus the expected backup. These are conservative defaults; the operations
owner must approve or replace them with measured production thresholds.

## 2. Backup and Migration Preflight

- [ ] Create and identify a fresh database backup; record location **_ and time _**.
- [ ] Verify encryption, access, retention, and restore ownership without exposing secrets.
- [ ] Rehearse restore against a disposable database and record the evidence \_\_\_ .
- [ ] Record exact `alembic current` and `alembic heads` output and confirm the expected
      single migration path before changing the database.
- [ ] Review every pending Alembic upgrade and downgrade, its locks, duration, and data risk.
- [ ] Confirm the old application can run against the post-migration schema, or stop.

## 3. Go or No-Go Decision

Release owner records: GO / NO-GO **_; time _**; approver **_; unresolved blockers _**

Choose NO-GO for a failed gate, missing owner, failed backup/restore evidence, capacity
stop, unknown migration compatibility, unavailable monitoring, or unavailable rollback.

## 4. Release Procedure

1. **PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION:** create the approved backup.
2. **PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION:** apply reviewed migrations
   with the repository's Alembic upgrade procedure.
3. **PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION:** release the immutable
   artifact identified by the recorded full SHA using the future deployment platform.
4. Record each command, operator, timestamp, output location, and resulting artifact.

This repository intentionally provides no generic deployment command. Add exact commands
only after DEV-024 records the hosting platform and an authorized operator has reviewed them.

## 5. Immediate Verification

- [ ] `/health` returns healthy and `/ready` confirms dependencies are ready.
- [ ] The public HTTPS URL loads and the browser smoke journey passes.
- [ ] Login/session behavior, a representative authenticated action, and logout pass.
- [ ] Logs contain no new error burst or secrets; request IDs remain traceable.
- [ ] Metrics show expected traffic, latency, error rate, and resource usage.

## 6. Observation Window and Success Thresholds

Record approved observation duration **_; baseline _**; maximum error rate **_;
maximum p95 latency _**; minimum successful smoke rate **_; resource thresholds _** .

Success requires every immediate check plus all approved thresholds for the complete
observation window. Missing thresholds are a release blocker, not an assumed pass.

## 7. Application Rollback

Trigger rollback for failed health/readiness, failed smoke behavior, breached error or
latency thresholds, data-integrity risk, security regression, or release-owner direction.

1. Stop further rollout and notify the incident lead.
2. **PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION:** restore the last known-good
   immutable application artifact.
3. Verify health, readiness, smoke behavior, logs, and metrics again.
4. Preserve evidence and record the rollback decision, operator, times, and outcome.

## 8. Database Recovery Boundary

Do not automatically run `alembic downgrade` or restore a production backup. Schema
rollback can destroy data and requires a reviewed migration-specific recovery plan,
database-owner approval, a fresh backup, and separate production authorization. When the
old application is schema-compatible, prefer application rollback while retaining the
new schema. Otherwise stop writes and follow the approved recovery plan.

## 9. Incident Escalation

Record incident channel **_; incident lead _**; database owner **_; security contact _**;
customer-communication owner **_; escalation deadline _** . Preserve logs, metrics,
release output, request IDs, and timestamps. Never paste credentials into the record.

## 10. Post-Release Closure

- [ ] Record verification and observation evidence, final artifact SHA, and end time.
- [ ] Confirm alerts and dashboards returned to their approved baseline.
- [ ] Record incidents, rollbacks, customer impact, and follow-up owners.
- [ ] Confirm approved database-backup and application-log retention periods are active.
- [ ] Confirm backup retention and remove only explicitly approved temporary artifacts.
- [ ] Obtain release-owner closure: name **_; decision _**; time \_\_\_ .
