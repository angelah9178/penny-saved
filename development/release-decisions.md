# DEV-024 Release Control Sheet

Last reviewed: 2026-08-12

This is the human-readable and machine-validated source of truth for production
decisions. Allowed statuses are `ready`, `deferred`, and `blocked`. A blocked item must
be resolved before release authorization; it is not permission to guess an answer.

## oracle-vps-os — Which supported Oracle VPS operating system and patch policy will production use?

- Owner: DEV-024 release owner
- Decision: No production host image or patch policy has been approved.
- Evidence: Record the installed supported OS version and named patch owner.
- Source: DEV-022 infrastructure decisions
- Deadline: before-release-authorization
- Status: blocked

## domain-dns — Who owns the production domain and DNS changes?

- Owner: Product owner
- Decision: stopimpulsebuying.online is the configured canonical origin, but DNS ownership and records are unverified.
- Evidence: Named owner plus verified production DNS records and rollback values.
- Source: operations/production.env.example and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## reverse-proxy — Which reverse proxy and version will terminate public traffic?

- Owner: DEV-024 release owner
- Decision: Nginx is the documented candidate; no installed production version is approved.
- Evidence: Installed version, reviewed configuration, and successful nginx -t output.
- Source: operations/nginx/penny-saved.conf.example and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## service-supervisor — Which supervisor and unprivileged service account will run the backend?

- Owner: DEV-024 release owner
- Decision: systemd and penny-saved are documented candidates; the real account, paths, and unit are unverified.
- Evidence: Installed unit validation plus graceful start, stop, restart, and permission tests.
- Source: operations/systemd/penny-saved.service.example and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## tls-renewal — Which TLS client renews the certificate and who responds to renewal failure?

- Owner: DEV-024 release owner
- Decision: No ACME client, renewal schedule, or renewal owner is approved.
- Evidence: Certificate issuance evidence, renewal dry run, expiry alert, and named owner.
- Source: DEV-022 infrastructure decisions
- Deadline: before-release-authorization
- Status: blocked

## secret-delivery — How are production secrets delivered and who may read them?

- Owner: DEV-024 release owner
- Decision: A placeholder-only environment file is documented; no real delivery mechanism or reader set is approved.
- Evidence: Secret source, rotation owner, file permissions, service access, and recovery procedure without secret values.
- Source: operations/production.env.example and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## postgresql-ownership — Which PostgreSQL version, host, role, and operator own production data?

- Owner: DEV-024 release owner
- Decision: PostgreSQL 16 on a non-public local interface is the V1 target; production roles and operator are unverified.
- Evidence: Version, local binding, least-privilege role review, disk ownership, and named database operator.
- Source: DEV-005, DEV-022, and the PostgreSQL 16 CI/service configuration
- Deadline: before-release-authorization
- Status: blocked

## backup-retention — Where are encrypted backups stored, for how long, and who verifies restores?

- Owner: DEV-024 release owner
- Decision: The guarded PostgreSQL 16 restore procedure passes locally; destination, encryption, off-host copy, retention, RPO, and RTO are unapproved.
- Evidence: Approved policy plus an isolated restore from the selected destination.
- Source: operations/README.md and DEV-022 restore rehearsal
- Deadline: before-release-authorization
- Status: blocked

## log-retention — Where are production logs retained and who may read them?

- Owner: DEV-024 release owner
- Decision: Structured journal logging is the candidate; retention limits, storage budget, and readers are unapproved.
- Evidence: Rotation/retention configuration, disk threshold, access review, and redaction check.
- Source: operations/README.md and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## metrics-access — Which private collector reads metrics and who responds to alerts?

- Owner: DEV-024 release owner
- Decision: The bounded metrics endpoint is loopback-only; no collector, retention, alerts, or responders are approved.
- Evidence: Private scrape test, collector identity, retention, thresholds, and named responder.
- Source: operations/nginx/penny-saved.conf.example and DEV-022
- Deadline: before-release-authorization
- Status: blocked

## incident-escalation — Who owns incidents and what conditions trigger escalation or rollback?

- Owner: Product owner
- Decision: No production incident contact, response window, or escalation threshold is approved.
- Evidence: Validated contact path, response threshold, rollback authority, and backup contact.
- Source: DEV-022 infrastructure decisions
- Deadline: before-release-authorization
- Status: blocked

## usd-scope — Which currency does V1 accept and display?

- Owner: Product owner
- Decision: V1 accepts and displays USD only; multi-currency behavior is out of scope.
- Evidence: Integer-cent API/model constraints, USD frontend formatting tests, and V1 roadmap scope.
- Source: DEV-001 product contract and DEV-010/DEV-018 implementation evidence
- Deadline: approved-for-v1
- Status: ready

## session-policy — How long do sessions last and how are expired sessions retained or removed?

- Owner: DEV-024 release owner
- Decision: Sessions have a 30-day absolute lifetime, secure SameSite=Lax production cookies, and delete on resolution after expiry; a scheduled stale-session cleanup owner and retention policy are unapproved.
- Evidence: SESSION_TTL_SECONDS=2592000, cookie/config tests, expiry tests, and an approved cleanup schedule/owner.
- Source: operations/production.env.example, DEV-008, and DEV-021
- Deadline: before-release-authorization
- Status: blocked

## email-feature-scope — Which email-dependent account features are included in V1?

- Owner: Product owner
- Decision: V1 has no password reset, email verification, MFA, outbound account email, or email-dependent recovery promise.
- Evidence: V1 roadmap and DEV-021 out-of-scope contract.
- Source: DEV-021 security scope and DEV-024 release rules
- Deadline: approved-for-v1
- Status: ready

## react-router-advisory — How is GHSA-qwww-vcr4-c8h2 handled for the release candidate?

- Owner: DEV-024 release owner
- Decision: Temporarily accepted only because this client-rendered SPA does not import or enable the affected unstable RSC APIs; React Router 7.18.1 has no patched 7.x release.
- Evidence: Current dependency scan, absence of RSC imports/configuration, official advisory review, and upgrade or renewed risk decision.
- Source: development/security-advisory-triage.json and GitHub Advisory Database
- Deadline: 2026-09-07
- Status: deferred
