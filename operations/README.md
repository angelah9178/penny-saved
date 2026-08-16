# Production Operations Runbook

This runbook is an executable design for the future Oracle VPS deployment of A Penny
Saved. It does not authorize a deployment or a production-data operation. Replace
placeholders, record the operator and ticket, and review every command against the
actual host before running it.

For the final ordered release-window checklist, use
[`RELEASE.md`](RELEASE.md). Its production actions still require separate authorization.

## Approved Topology

```text
Internet
  → Nginx on ports 80/443 (TLS and frontend files)
  → FastAPI on 127.0.0.1:8000 (/api only)
  → PostgreSQL on 127.0.0.1:5432

Private host access
  → FastAPI on 127.0.0.1:8000/internal/metrics
```

Only SSH, HTTP, and HTTPS may be exposed by the host firewall. PostgreSQL and FastAPI
must listen on loopback or an explicitly private local container network. Nginx is
the only trusted HTTP proxy. The application service runs as the non-root
`penny-saved` account; the database uses separate least-privilege application and
backup roles.

## Required Decisions Before Release

DEV-024 must record owners and evidence for these unresolved production choices:

- supported Oracle VPS operating-system image and patch policy;
- installed Nginx, PostgreSQL, Python, and systemd versions;
- deployment account, service account, filesystem paths, and file ownership;
- secret-delivery mechanism and who may read `/etc/penny-saved/backend.env`;
- TLS/ACME client, renewal owner, expiry monitoring, and renewal dry run;
- firewall/SSH policy and recovery access;
- backup destination, encryption, off-host transfer, retention, and restore owner;
- log retention, journal limits, metrics collector, scrape interval, and access;
- immutable release/artifact layout and application rollback owner; and
- incident contact, escalation path, response expectations, and maintenance window.

Any undecided item needed by a release is a blocker, not an implicit default.

## Production Configuration

Start from `operations/production.env.example`. Store the populated file outside the
repository at `/etc/penny-saved/backend.env`, owned by root and readable only by the
service group as narrowly as the chosen secret-delivery design permits. A typical
target is mode `0640`; use `0600` when the service starts through a credential-loading
mechanism that does not require group access.

Replace both `REPLACE_WITH` values. Generate independent high-entropy database and
rate-limit secrets; do not reuse a login password. Confirm the complete environment
constructs the application before installing or restarting the service. Never put the
environment file in a release directory, shell history, ticket, log, or backup that
does not have secret-grade access controls.

The example deliberately uses:

- `https://stopimpulsebuying.online` and secure cookies;
- exact hostnames and loopback-only trusted proxy networks;
- newline-delimited JSON logs at `INFO`;
- a one-megabyte request limit at both Nginx and FastAPI;
- a two-second readiness probe; and
- opt-in metrics that remain reachable only through backend loopback.

Run the repository-owned static checks before review:

```bash
make operations-check
```

## Reverse Proxy and TLS

`operations/nginx/penny-saved.conf.example` is an Nginx candidate, not an installed
configuration. Confirm the actual frontend and certificate paths, then validate the
assembled Nginx configuration with the installed binary before reload:

```bash
sudo nginx -t
```

The example redirects HTTP and `www` traffic to the canonical HTTPS origin, serves
the built React application, uses SPA fallback, proxies only `/api/` to loopback, and
returns `404` for public `/internal/metrics` requests. Nginx forwards the original
host and proxy chain. FastAPI trusts forwarded addresses only when the direct peer is
in `TRUSTED_PROXY_NETWORKS`.

Choose and document the ACME client before release. Verify initial issuance, renewal
timer state, a renewal dry run, certificate permissions, both hostnames in the
certificate, HTTPS redirect behavior, and days until expiry. A named operator must
own renewal failures. Do not weaken TLS or bypass certificate validation to make a
check pass.

## Process Supervisor

`operations/systemd/penny-saved.service.example` runs Uvicorn over loopback as a
non-root account, loads secrets from `/etc`, restarts unexpected failures, sends
standard output/error to the journal, and gives graceful shutdown 30 seconds before
systemd's 40-second outer deadline. It intentionally does not run migrations in
`ExecStart`; migrations are an explicit backup-first release step.

After confirming paths, users, environment delivery, and supported hardening options,
validate the installed unit before enabling it:

```bash
sudo systemd-analyze verify /etc/systemd/system/penny-saved.service
sudo systemctl daemon-reload
```

Starting, enabling, restarting, or stopping the real service is a separately
authorized production action. Before release, rehearse start, readiness, SIGTERM,
unready transition, clean database disposal, restart-on-failure, and timeout behavior
in a disposable environment.

## Health, Metrics, and Logs

From the VPS, liveness and readiness are checked independently:

```bash
curl --fail --silent --show-error https://stopimpulsebuying.online/api/health
curl --fail --silent --show-error https://stopimpulsebuying.online/api/ready
```

A `200` liveness response with `503` readiness means the process is alive but cannot
serve normal database-backed traffic. Inspect PostgreSQL and application logs before
restarting anything. Repeated process restarts do not repair a separate database
outage.

Metrics are read directly over loopback and must not pass through public Nginx:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/internal/metrics
```

The future collector must run locally or use an authenticated private channel. It
must not add user IDs, request IDs, emails, IPs, raw paths, or other unbounded labels.

Application JSON logs go to stdout/stderr and the systemd journal. Use the request ID
shown in a safe client error to find related server events:

```bash
sudo journalctl -u penny-saved --since "15 minutes ago" -o cat | grep --fixed-strings 'REPLACE_WITH_REQUEST_ID'
```

Restrict journal access, configure explicit size/time retention, and monitor disk
growth. Logs contain operational metadata and user IDs when authentication has been
resolved, so they are not public data even though secrets are redacted.

## Database-Outage Response

1. Confirm `/api/health` succeeds and `/api/ready` returns `503`.
2. Record the UTC start time, request ID if present, release revision, and operator.
3. Inspect the application journal for a readiness transition; do not paste secrets.
4. Check PostgreSQL service state, disk space, connection capacity, and its protected
   logs using host-approved commands.
5. Do not reset, reinstall, promote, restore, or restart repeatedly without identifying
   the failure and confirming backup state.
6. Escalate to `REPLACE_WITH_INCIDENT_CONTACT` when the documented threshold is met.
7. Confirm readiness recovery and representative authenticated behavior, then record
   the end time, cause, corrective action, and follow-up.

## Backup Procedure

Back up before every production migration and on the approved schedule. Use a
restricted backup role and a protected PostgreSQL service file or `.pgpass`; never
place a password on the command line. Confirm the target filesystem is encrypted or
otherwise approved, is not the same failure domain as the database, and has enough
free space.

The following names illustrate the required commands. Resolve the timestamp and paths
deliberately in the operator shell and record them in the release evidence:

```bash
umask 077
backup_directory=/var/backups/penny-saved
backup_timestamp=REPLACE_WITH_UTC_TIMESTAMP
backup_file="$backup_directory/penny_saved_$backup_timestamp.dump"

df -h "$backup_directory"
pg_dump --dbname=penny_saved_backup_service --format=custom --no-owner --no-acl --file="$backup_file"
pg_restore --list "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
sha256sum --check "$backup_file.sha256"
```

Stop immediately on any nonzero exit. Record PostgreSQL version, database name,
backup path, byte size, checksum, UTC time, operator, release revision, retention
class, and off-host copy result. A checksum and `pg_restore --list` detect some
failures but do not prove restorability.

## Isolated Restore Verification

Restore only into an explicitly named disposable database on a non-production target
or an isolated local cluster. Never use the production database name as the restore
target.

```bash
restore_database=penny_saved_restore_verify
backup_file=REPLACE_WITH_REVIEWED_BACKUP_PATH

createdb "$restore_database"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$restore_database" "$backup_file"
psql --dbname="$restore_database" --command='SELECT version_num FROM alembic_version;'
psql --dbname="$restore_database" --command='SELECT count(*) FROM users;'
psql --dbname="$restore_database" --command='SELECT count(*) FROM impulse_purchase_entries;'
psql --dbname="$restore_database" --command='SELECT count(*) FROM sessions;'
```

Compare migration revision and representative counts with the backup evidence. Check
constraints and a small approved sample without exporting personal data. Record the
restore duration, PostgreSQL version, results, and operator. After review, remove only
the explicitly named disposable target:

```bash
dropdb --if-exists penny_saved_restore_verify
```

Backup success is not accepted until this isolated restore verification passes.

For the repository's local PostgreSQL Compose service, the guarded rehearsal uses the
PostgreSQL 16 client tools inside that container so the dump/restore client major
matches the server. The host's PostgreSQL client may be newer and is not assumed to
be archive-compatible:

```bash
make rehearse-restore
```

This command accepts only a loopback `TEST_DATABASE_URL` whose database name ends in
`_test`, refuses to overwrite an existing target, creates only
`penny_saved_dev022_restore_verify`, compares the Alembic revision and representative
table counts, and removes the disposable target in a `finally` cleanup.

## Rollback Boundary

Application rollback means directing `current` to a retained, immutable prior release
whose code is compatible with the already-applied database schema, then restarting
and verifying health and the browser journey. Database rollback is different: never
run `alembic downgrade` or restore an older database in production merely because an
application rollback is requested. Schema reversal or data restore requires its own
reviewed incident plan and explicit authorization.

## Routine Operational Checks

- Check readiness, request-error/latency trends, database-pool utilization, filesystem
  space, journal growth, PostgreSQL space, backup age, off-host copy state, and last
  verified restore.
- Check TLS expiry, renewal timer results, and external HTTPS behavior.
- Review repeated authentication failures and lifecycle conflicts as aggregate trends;
  do not attempt to identify users from metrics.
- Patch the supported OS and pinned application dependencies through reviewed release
  work, with a backup and rollback plan.
- Record incidents and follow-ups without copying credentials, cookies, bodies, raw
  database URLs, or personal data into tickets.

## Production Actions Not Performed by DEV-022

No file in `operations/` provisions infrastructure or changes production state.
DEV-022 does not connect to Oracle Cloud, install packages, create accounts, modify
DNS/firewalls, issue certificates, write `/etc`, enable/restart services, run a
production migration, create a production backup, restore data, or deploy a release.
