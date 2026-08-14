# ADR-0002: ARCH-01 release state machine, evidence and executor boundary

**Status:** Accepted for ARCH-01 implementation only after the targeted Sonnet
re-review is `ELFOGADVA`.

**Date:** 2026-08-13

## Context

ARCH-01 introduces discovery, a bounded H0/H1/H2 crawl, WACZ retention and
replay QA.  The legacy application can move a snapshot from `indexed` to
`published` without a release record; `record_qc_result()` and
`decide_quality_review()` are therefore incompatible legacy paths.  The
existing Browsertrix `pages.jsonl` is capture output, not a complete traversal
or edge log, and the existing worker wrapper assumes a Docker CLI/sibling path
that is not a permitted executor boundary.

The decision below is normative for the ARCH-01 migration, API contract,
workers, Compose topology and acceptance tests.  It does not authorise a
production deploy, Nginx change or secret change.

## Decision

### 1. Database-authoritative release machine

`discovery_candidate.state`, `archived_snapshot.lifecycle_status`, and
`archived_snapshot.release_state` are separate enums.  API code may request a
transition, but PostgreSQL is the final authority and writes the lifecycle,
release and audit event in the same transaction.

| Record | Allowed terminal/publish-relevant values | Rule |
|---|---|---|
| Candidate | `discovered`, `prequalified`, `uncertain`, `rejected`, `suppressed`, `curator_approved`, `curator_rejected` | Only `curator_approved` may create or attach a crawlable snapshot. |
| Snapshot lifecycle | `approved`, `crawling`, `archived_pending_qc`, `qc_passed_pending_release`, `qc_review_required`, `integrity_failed`, `withdrawn`, `published` | `published` is reachable only by the database release transition below. |
| Release | `not_ready`, `review_required`, `release_pending`, `released`, `held`, `withdrawn` | A lifecycle state alone never authorises publication. |

Migration `005_arch_01_pipeline.sql` SHALL replace or tighten the legacy
`trg_lifecycle_guard`, not merely add application-side checks.  It SHALL reject
`indexed -> published` and every other legacy publish edge unless the same
transaction supplies a valid, hash-bound `release_decisions` record with all
G0--G4 inputs.  It SHALL remove the publish effect from
`record_qc_result()` and `decide_quality_review(accept=true)`; the legacy
ingest endpoint may at most create a `manual_candidate`, never approve, enqueue
or publish it.  `user_id IS NULL` is rejected for every curation, hold,
withdrawal, override and release decision.

`release_decisions` SHALL contain an immutable `gate_matrix_hash`, actor IDs,
reason, policy revision, artifact/version reference, request idempotency key,
decision timestamp and decision outcome.  A unique constraint scopes an
idempotency key to `(snapshot_id, operation, actor_id)` and stores the original
response hash.  Repeating the same request returns the original outcome;
reusing a key with different material input is a conflict.  Snapshot transition
uses compare-and-set/row locking.  A transactional outbox row is inserted in
that same commit; a dispatcher may deliver it at least once, but consumers must
deduplicate by the outbox event ID.  No acknowledgement may precede the commit.
Crash recovery and a reconciler may only retain/restore a visible hold or retry
an idempotent task; they cannot infer release or publication.

G0--G3 hard failures are never overridable.  G4 may override only a
non-integrity `review_required` caused by live drift or documented insufficient
sampling: it requires two distinct active principals, one `curator` and one
`admin`, distinct authenticated user IDs, distinct non-empty reasons, and a
single gate-matrix/artifact hash.  The first snapshot of a new eTLD+1/domain
also requires this two-person review even when all hard gates pass.  No user,
role alias, retry or repeated idempotency request can satisfy both signatures.

### 2. Discovery decision provenance

The isolated discovery LLM adapter is the only meaning of “real AI service” in
ARCH-01.  Existing RAG, embedding and summarisation components are neither
discovery evidence nor a release dependency.

`discovery_candidates.decision_source` is exactly one of
`deterministic`, `llm`, `provider_failure`, `budget_exhausted`,
`model_failure`, `security_rejected`, or `manual`.  `reason_code` is a
versioned enum: `locality_match`, `non_local`, `content_uncertain`,
`duplicate`, `prior_suppression`, `provider_failed`, `budget_exhausted`,
`model_timeout`, `model_invalid_output`, `evidence_invalid`,
`prompt_injection_signal`, `security_rejected`, `policy_rejected`, or
`manual_review`.  Unknown source/reason values fail validation and cause
`uncertain`/hold, not fallback approval.

Each LLM decision retains immutable provenance: provider result identifiers,
canonical source/inspection URL and retrieval time; Unicode-normalisation and
truncation algorithm versions; an immutable normalised inference-input artifact
or a content-addressed artifact plus exact byte spans; `input_sha256`,
`prompt_sha256`, prompt-template version, schema-validator version, model ID and
digest, parameters, output JSON and output hash.  Every quoted evidence item
must resolve to an exact recorded input span.  Budget, provider and model
failures are visibly distinguishable per candidate and make the run `partial`
or `failed`; they cannot masquerade as ordinary content uncertainty.

### 3. URL security and executor network boundary

For each original seed, redirect and fetched subresource, the resolver validates
the complete A/AAAA and CNAME result set before use.  Any private, loopback,
link-local, CGNAT, ULA, IPv4-mapped IPv6, metadata or mixed public/private
answer rejects the URL.  Userinfo, alternative numeric IP notation, non-default
ports and non-HTTP(S) schemes are rejected.  The selected public address is
stored as `pinned_ip` in the immutable plan/event and is the socket-connect
target for that request.  TLS SNI and HTTP Host retain the validated hostname,
but downstream code and the egress gateway SHALL NOT independently resolve that
hostname at connect time.  A redirect obtains a new full validation and a new
pinned IP; it never inherits permission from its parent.

Discovery inspection, Chromium navigation, redirects and all subresources pass
through the same policy-enforcing egress path.  The discovery/crawl/QA executor
has no direct route to the host, Docker socket, Compose/cluster networks or
metadata addresses.  Tests prove zero prohibited connections for mixed DNS,
CNAME chains, rebinding/TTL changes, IPv4-mapped IPv6, numeric forms, userinfo,
non-default ports and public-to-private redirects.

The executor is a separate, non-root, digest-pinned Browsertrix runtime image.
Its queue consumer invokes the version-pinned Browsertrix CLI inside that
executor container with a per-job isolated work directory and no Docker CLI,
Docker socket, host mount or sibling-repository import.  The API never executes
`docker run`.  The runtime image digest, CLI arguments, egress-policy version
and work-plan hash are recorded in the crawl manifest.

### 4. Normative crawl evidence source

Browsertrix `pages.jsonl` is supplemental capture telemetry only.  It is not a
normative source for hop, parent, eligibility or skip reason.  Before Browsertrix
is invoked, the executor's versioned BFS/edge adapter emits an append-only,
content-addressed `crawl_edge_events.v1` stream.  For every observed link it
records original URL, normalised canonical URL, final URL when known, parent
canonical URL, discovered hop, edge source page, eligibility decision, policy/
robots/security/scope decision, skip reason, timestamp and plan hash.  The
adapter deduplicates canonical URLs deterministically: the smallest-hop edge
wins; equal-hop parents are retained as aliases; capture attempts are aggregated
under one `(crawl_run_id, canonical_url, hop)` page record.

`crawl_manifest.v1` is derived from this stream plus capture telemetry.  H0 is
the validated final seed; H1 can only have H0 as its discovered parent; H2 can
only have an H1 parent; H3 and external hosts are recorded but not captured.  A
manifest may assert `eligible_count=0` only if the complete edge stream has no
eligible H1/H2 edge after deterministic canonicalisation.  Missing, malformed,
duplicate-without-aggregation or plan-hash-mismatched edge/capture data makes
the run `crawl_incomplete` and `review_required`; it cannot be treated as a
successful zero-page crawl.

### 5. Configuration, migration and deployment contract

Trusted proxy networks come only from the required typed `TRUSTED_PROXY_CIDRS`
Settings value.  Startup fails when it is empty in proxied production mode,
cannot parse as a CIDR list, contains `0.0.0.0/0`, `::/0`, a loopback, link-local
or an address range broader than the reviewed deployment allow-list.  Forwarded
headers are ignored unless the immediate peer belongs to that validated list.
This inbound trust contract is independent of the outbound egress gateway and
the external Nginx black-box contract test remains mandatory.

ARCH-01 uses a versioned migration runner, not a bare SQL mount.  The runner
maintains an immutable applied-version/checksum ledger, obtains a database
advisory lock, applies pending migrations in lexical/version order in a
transaction where supported, and refuses checksum drift or out-of-order state.
Compose runs the runner before API/workers become ready.  Acceptance must prove
both an empty database and an upgrade from the pre-ARCH-01 `004` state; neither
may rely on a pre-existing Docker volume or manual SQL execution.  Failed
migration leaves the service unready and requires explicit operator remediation,
not automatic schema repair.

## Consequences

- Production code must implement this ADR through small, independently reviewed
  slices; no legacy route may be retained as an alternate publication path.
- A limited crawl, incomplete QA, invalid artifact or unknown evidence stays
  preserved for audit but is release-held.
- The first build slice is database/contract/migration work.  Executor and
  integration work are sequenced only after its acceptance and required file
  ownership handoff.

## Verification

At minimum the ARCH-01 test suite proves: legacy auto-publish and one-person
bypass rejection at DB level; idempotent release/outbox recovery; two-person
new-domain and permissible override gates; pinned-IP connection behaviour;
complete edge evidence for H0/H1/H2; candidate provenance/reason enums;
trusted-proxy startup failure; fresh and upgrade migration paths; and the
separate executor runtime boundary.

## Addendum — S1 legacy upgrade, policy hold and migration execution (2026-08-13)

This addendum is normative and resolves the S1 decisions that must not be
invented by an implementer.  It supplements, and where it is more specific
than, the earlier Decision text.

### 6. Lossless legacy lifecycle upgrade

Migration `005` SHALL retain every existing `archived_snapshots` row, all of
its existing columns, object references and historical `lifecycle_events`.  It
SHALL add an immutable `legacy_snapshot_migrations` row per pre-005 snapshot,
containing `snapshot_id`, `legacy_lifecycle_status`, migration version/time,
disposition, and (where applicable) a `resumable_candidate_id`.  The original
status is therefore never inferred from a rewritten current status.

| Pre-005 `lifecycle_status` | Post-005 lifecycle / release | Mandatory disposition |
|---|---|---|
| `candidate` | `migration_hold` / `held` | Create or deduplicate an `uncertain` `legacy_migration` candidate, linked to the retained snapshot; a curator must approve it again before a **new** capture can start. |
| `approved` | `migration_hold` / `held` | Same as `candidate`; former approval is evidence only, never an executable approval. |
| `crawling` | `migration_hold` / `held` | Cancel/ignore the old in-flight work; create the same reapproval candidate. It may not be resumed or completed after the migration. |
| `archived`, `indexed` | `migration_hold` / `held` | Retain the artifact and metadata, but create no executable candidate and do not infer QA/release. A curator may request a fresh manual candidate, linked as provenance, for a new ARCH-01 capture. |
| `published` | `published` / `released` | Keep publicly visible. Insert exactly one immutable import release record with `decision_origin=legacy_grandfathered`, the original publication timestamp and an import hash. This records an already-public historical fact; it is not a G0--G4 pass and cannot authorise any later transition. |
| `deprecated` | `migration_hold` / `held` | Retain as `legacy_deprecated_retained`; it remains non-public and may not be republished. |
| `withdrawn` | `withdrawn` / `withdrawn` | Retain as withdrawn, with no candidate, enqueue or release path. |

`migration_hold` is a new lifecycle value usable only by the migration and
read-only retention/audit paths.  No normal transition leaves it.  A resumed
business action always starts from the linked, separately reviewed candidate;
it never mutates a retained legacy snapshot back into the new workflow.  The
migration trigger SHALL reject all legacy lifecycle edges, including
`deprecated -> published`, after `005` is applied.  Thus no data is deleted,
and no historic approval, QC result, in-flight worker or synthetic import can
become a new publish or crawl bypass.

`decision_source` is extended with `legacy_migration`, and `reason_code` with
`legacy_candidate_requires_reapproval`, `legacy_approval_requires_reapproval`,
`legacy_inflight_requires_reapproval`, `legacy_artifact_retained`, and
`legacy_deprecated_retained`.  These values are visible provenance, not a
fallback to `manual` or `content_uncertain`.

### 7. Schema-level depth-3--5 policy hold and reapproval

The legacy `crawl_policies.depth` column is historical input and SHALL NOT be
silently clamped or overwritten.  `005` adds:

- `crawl_policies.arch01_execution_state` (`active`, `on_hold`, `retired`) and
  nullable `active_revision_id`;
- append-only `crawl_policy_revisions` with `(policy_id, revision)` unique,
  immutable `config_json`, `config_hash`, `depth_hops SMALLINT CHECK
  (depth_hops BETWEEN 0 AND 2)`, `source`, `supersedes_revision_id`, creator,
  reviewer, review time and non-empty review reason; and
- append-only `crawl_policy_holds` with `policy_id`, `legacy_depth`,
  `legacy_config_hash`, `legacy_is_active`, `hold_reason`, opener and opener
  time, plus a nullable cleared-by/at/reason reference to the approving
  revision.

For every pre-005 policy whose `depth IN (3,4,5)`, the migration SHALL insert a
hold with `hold_reason=legacy_depth_exceeds_arch01`, set
`arch01_execution_state='on_hold'`, and leave the legacy row and depth intact.
No plan, queue request, retry or executor claim may reference an `on_hold`
policy; this is enforced by database trigger/foreign-key-visible validation,
not only by API filtering.  A legacy depth 1 or 2 policy receives an immutable
`legacy_normalized` revision with the same hop value and may be `active` only
if its legacy `is_active` was true.  New execution always reads the approved
revision, never the legacy `depth` column.

Reapproval is one authenticated curator decision: it creates a new revision
with a deliberately chosen `depth_hops` in `0..2`, a fresh config hash and a
non-empty rationale, links it to the hold, marks the former revision
superseded, and atomically changes the policy to `active`.  It cannot edit or
erase the 3--5 historical value.  Rejection/retirement leaves the hold in
place.  The API accepts only an approved policy/revision identifier; it never
accepts depth or other crawl limits from the caller.

### 8. `manual_candidate` is a provenance class, not a state or bypass

`manual_candidate` is not an extra `discovery_candidates.state`.  It is a
candidate whose immutable `candidate_origin='manual'`; the source enum records
the classifier/decision that produced the current state.  The origin enum is
exactly `discovery`, `manual`, or `legacy_migration`.  The decision-source enum
is exactly `deterministic`, `llm`, `provider_failure`, `budget_exhausted`,
`model_failure`, `security_rejected`, `manual`, or `legacy_migration`.

A valid manual submission creates only this initial tuple:
`candidate_origin='manual'`, `state='uncertain'`,
`decision_source='manual'`, `reason_code='manual_review'`,
`submitted_by IS NOT NULL`, `submitted_at`, non-empty submitter rationale and
immutable submission evidence.  The submitter cannot supply state, approval,
policy/revision, snapshot ID, job ID or release fields.  URL canonicalisation,
tenant deduplication and the same SSRF/security validation apply before it can
be approved; a failed validation is retained as `state='rejected'` with
`decision_source='security_rejected'` and does not lose `candidate_origin`.

Only the DB-authorised curator transition from `uncertain` to
`curator_approved`, with a non-null authenticated curator ID and an active
approved policy revision, may atomically create a new snapshot and its
post-commit crawl outbox request.  Direct insert/update of a snapshot, queue
or release from manual ingest is rejected.  Therefore manual intake is an
auditable discovery channel, never auto-approve, auto-crawl, policy selection
or release bypass.

### 9. PostgreSQL enum migration and runner transaction contract

`005` SHALL declare `transaction_mode=enum_phased`.  PostgreSQL enum values
added by `ALTER TYPE ... ADD VALUE` cannot safely be used by later DML in the
same transaction, so `005` SHALL NOT be wrapped in a runner-wide outer
transaction.  The runner holds one session-level advisory lock and uses a
fresh runner-owned connection; it rejects invocation from an existing caller
transaction.

Phase A is autocommit-only and contains solely idempotent
`ALTER TYPE ... ADD VALUE IF NOT EXISTS` statements.  It adds the required new
lifecycle and provenance values but changes no rows, trigger, visibility or
migration ledger.  After those commits, Phase B runs all tables, constraints,
triggers, lossless mappings and the `005` checksum-ledger insert in one normal
database transaction.  If Phase B fails, no service becomes ready and the
ledger remains at `004`; the committed enum labels are harmless, and a rerun
repeats Phase A idempotently before retrying all of Phase B.  A checksum or
unexpected partially applied Phase-B object fails closed rather than being
repaired heuristically.

All ordinary migrations are runner-owned, one migration per transaction with
their ledger insert in that same commit.  The runner never opens a transaction
around a batch or accepts an application/Compose outer transaction.  Compose
starts it before API and workers; fresh and `004 -> 005` tests must prove the
enum-phased retry behaviour as well as the normal successful paths.

## Addendum — DB authority requires role separation and an executable runner (2026-08-13)

### 10. Least-privilege PostgreSQL role topology

The API/worker database principal MUST NOT be a PostgreSQL superuser.  The
official Postgres image creates `POSTGRES_USER` as a superuser; therefore that
bootstrap identity is never an application credential.  An app principal that
can execute `SET session_replication_role = replica` can bypass ordinary row
triggers and destroys the database-authoritative release guarantee.

The deployment uses exactly these independent principals.  Passwords are
separate secrets; no API, worker, frontend or executor container receives the
bootstrap or migrator secret.

| Principal | Attributes and ownership | Permitted use |
|---|---|---|
| `fewa_bootstrap` | Image `POSTGRES_USER`; superuser exists only to initialise/upgrade a cluster. It owns no ARCH-01 application table after hand-off and is `NOLOGIN` or stored outside the application deployment after provisioning. | One-shot role provisioning, ownership transfer and break-glass operator recovery with an auditable human procedure. Never Compose API/worker/migrator connection. |
| `fewa_migrator` | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT`; owns the `public` application schema, all application tables/types/sequences/functions and the migration ledger. | Only the one-shot migration-runner service. It may perform versioned migration DDL and the narrowly specified migration DML; it is not configured in the application containers. |
| `fewa_app` | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT`; owns no schema object and is not a member of `fewa_migrator` or `fewa_bootstrap`. | API and all workers only. It receives only runtime DML permissions. |

`fewa_app` receives `USAGE` on the application schema; `SELECT, INSERT,
UPDATE` only on the explicitly enumerated runtime tables/views; and `USAGE,
SELECT` only on required sequences.  It receives neither `CREATE` on any
schema nor `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`, `EXECUTE` on
unreviewed functions, membership in an owner role, database ownership, nor any
role-administration grant.  The provisioning migration revokes `ALL` on the
database, application schema, all application tables, sequences and functions
from `PUBLIC`, then grants the above allow-list to `fewa_app`.  It also executes
`ALTER DEFAULT PRIVILEGES FOR ROLE fewa_migrator IN SCHEMA public REVOKE ALL
ON TABLES, SEQUENCES, FUNCTIONS FROM PUBLIC` and corresponding default grants
to `fewa_app`, so future migrations do not silently widen the role.

Every ARCH-01 guard/audit/outbox trigger that enforces publication, curation,
artifact binding, policy hold, or candidate state MUST be `ENABLE ALWAYS
TRIGGER`.  This is defence in depth: `fewa_app` cannot set replication role or
alter/disable triggers because it is not superuser and does not own tables;
`ENABLE ALWAYS` also prevents a replication-role setting from suppressing the
guard.  Only the migration principal may alter trigger definitions, and a
migration that temporarily changes such a trigger must restore `ENABLE ALWAYS`
before its ledger entry commits.

For tenant-owned runtime tables, `005/006` MUST enable and force RLS once the
tenant policies are introduced; `fewa_app` remains `NOBYPASSRLS` and no app
role owns an RLS table.  Policy predicates must use a transaction-local,
server-set tenant context and fail closed when absent.  RLS is tenant
segmentation, not a substitute for the role boundary: a compromised app
principal remains able to perform only its granted DML and remains subject to
the `ENABLE ALWAYS` business guards.

### 11. Backward-compatible role rollout and migration runner slice

`005` has an immutable applied checksum and SHALL NOT be rewritten.  This
correction is a new `006_arch_01_db_roles.sql` migration plus a separate,
reviewable provisioning/runner implementation.  On an existing cluster,
operators first drain API/workers, take a verified backup and run an idempotent
bootstrap-only provisioner as the existing image superuser.  It creates the
three principals, transfers the application database/schema/object ownership
to `fewa_migrator`, revokes legacy/public privileges, establishes the explicit
app grants/default privileges and records no application business decision.
It preserves all data, existing migration ledger entries and object identity.
The old `fewa_user` credential is removed from all runtime services and made
`NOLOGIN` only after the new app connection and runner path are proven; a
documented rollback before that final revocation restores the previous Compose
credential without data rewrite.

Fresh deployments use `POSTGRES_USER=fewa_bootstrap` only for initial role
provisioning; the backend/worker environment uses `POSTGRES_USER=fewa_app`.
The migration runner uses a distinct `MIGRATOR_DATABASE_URL`/secret, while all
runtime services have only `APP_DATABASE_URL` (or the equivalent separated
app role fields).  No `MIGRATOR_*` or bootstrap variable may be injected into
API/worker containers, logs, health checks or test fixtures that exercise app
behaviour.

The missing runner is a blocking implementation slice, not a future S2/S3
detail.  It owns the existing ADR §5/§9 contract: fresh connection, session
advisory lock, checksum/order ledger, `enum_phased` Phase A autocommit then
Phase B transaction, rollback/error exit and readiness gate.  `006` also makes
the ARCH-01 guard triggers `ENABLE ALWAYS`; its ledger insert is committed only
after that enforcement is restored.

| Slice / owner | Exact files | Ordering |
|---|---|---|
| S1 corrective DB builder | New `spec/migrations/006_arch_01_db_roles.sql`; new `fewa-v3-backend/tests/test_arch01_db_roles.py`; existing S1 DB-regression test only for new DB assertions. | After the Sonnet finding, before any QA/SG-S1 re-review. It must not rewrite `005`. |
| R1 DevOps migration-runner owner | New `infra/postgres/bootstrap_roles.sql`, `infra/migrations/runner.py`, `infra/migrations/Dockerfile`, and runner-focused tests under `infra/migrations/tests/`. | Starts with S1 corrective DB work; R1 is complete only when the runner executes `005/006`, not when SQL is manually fed to `psql`. |
| S3 integration owner, only after current-owner checkpoint | Existing `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `fewa-v3-backend/app/core/config.py`, backend Dockerfile and new Compose integration tests. | Wires bootstrap/migrator/app secrets and `migration-runner` completion before API/worker startup. Existing in-flight API/worker files remain owned by their current owners and are not touched for this correction. |

`fewa-v3-backend/app/api/v1/jobs.py` and `app/workers/arq_worker.py` remain
out of this role-correction slice: they must use only the runtime app pool,
must never issue DDL, `SET session_replication_role`, `ALTER ... DISABLE
TRIGGER`, or migration SQL, and need no new migrator credential.  Any later
change to those currently in-flight files requires their existing explicit
handoff.

### 12. Required executable acceptance

QA must use the Compose-wired principals, not a `POSTGRES_USER` superuser test
container, and record raw output for all of the following:

```bash
# Runtime role attributes: all three values must be false.
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT rolsuper, rolbypassrls, rolreplication FROM pg_roles WHERE rolname=current_user"

# Each command must fail for `fewa_app`.
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c 'SET session_replication_role = replica'
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  'ALTER TABLE public.archived_snapshots DISABLE TRIGGER ALL'
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  'ALTER TABLE public.archived_snapshots ADD COLUMN arch01_must_not_exist integer'
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  'CREATE TABLE public.arch01_must_not_exist (id integer)'

# Even a hypothetical replication setting may not suppress critical guards.
# This runs only as the migration/QA principal in an isolated DB and must still
# reject the documented direct-SQL legacy publish/curation bypass fixtures.

# Real runner, not manual `psql -f`: fresh and 004->006 upgrade paths.
docker compose -f docker-compose.test.yml run --rm migration-runner
psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT version, checksum FROM schema_migrations WHERE version IN ('005','006') ORDER BY version"
```

The app attempts must return permission/ownership errors and leave no schema
object behind.  The runner must exit successfully once, reject a concurrent
runner by its advisory lock, detect checksum/order drift, prove Phase-A/Phase-B
retry, and produce both `005` and `006` ledger rows.  After runner completion,
Compose must demonstrate API and worker readiness using `fewa_app`; before it,
they must not become ready.  QA then repeats all S1 adversarial DB invariants
under `fewa_app`, including direct-SQL trigger-bypass attempts, and Sonnet
re-reviews both the role topology and the executable evidence.

## Addendum — immutable 005 server-file checksum compatibility (2026-08-13)

### 13. Decision: bootstrap-only 005 stage; no server-file grant to migrator

The checked-and-ledgered `005_arch_01_pipeline.sql` directly invokes
`pg_read_binary_file(source_path)`.  PostgreSQL executes that read in the
database-server process, so a non-superuser needs `pg_read_server_files` to
run that SQL.  Granting this predefined role to `fewa_migrator` contradicts
the final least-privilege topology and is not acceptable, even temporarily if
the eventual revocation depends on a different grantor.

**The approved remediation is a bootstrap-only compatibility stage, not a
replacement checksum mechanism.** `005` bytes, its declared SHA-256 and its
existing ledger semantics remain immutable.  `fewa_migrator` and `fewa_app`
MUST NEVER be granted membership in `pg_read_server_files`, nor an equivalent
server-file capability.  The previously contemplated bridge grant/function is
prohibited and MUST be removed from the R1 candidate before QA.

The actual image-created superuser is named `fewa_bootstrap` for fresh
clusters.  It remains a `LOGIN SUPERUSER` principal only in an external,
short-lived bootstrap job; its credential is absent from normal Compose
services, application images, workers, logs and runtime environments.  For an
existing cluster whose image superuser is the legacy `fewa_user`, an operator
first creates a distinct `fewa_bootstrap` superuser using an externally held
secret, verifies it, and only after the successful application cutover makes
`fewa_user NOLOGIN`.  `fewa_bootstrap` owns no application schema object after
the normalisation step below.

### 14. Exact stage order and ownership normalisation

Runtime services are drained and remain unready throughout this sequence; a
verified backup precedes it.  All stages fail closed, emit a durable
`arch01_bootstrap_operations` audit row (operation ID, bootstrap session user,
stage, source SHA-256, started/completed times, role-membership before/after,
result/error), and use the same migration advisory-lock namespace.  A failed
or missing audit row prevents the next stage.

1. **Bootstrap provision.** The external bootstrap job creates/validates
   `fewa_bootstrap`, `fewa_migrator` and `fewa_app`, sets their distinct
   passwords/attributes, removes role inheritance, transfers all pre-005
   public objects to `fewa_migrator`, and configures revoke/default-privilege
   policy. It grants neither `pg_read_server_files` nor `pg_read_binary_file`
   privilege to migrator/app.
2. **Migrator pre-stage.** The ordinary runner, authenticated only as
   `fewa_migrator`, applies or validates migrations through `004` and stops.
   It cannot advance to `005` in this invocation.
3. **Bootstrap `005` compatibility stage.** A separate, deliberately narrow
   bootstrap executor accepts only migration version `005`; it obtains the
   session advisory lock, verifies the local immutable `005` SHA-256, sets the
   fixed server-visible path, then applies the prescribed Phase A autocommit
   and Phase B transaction. If ledger `005` already exists, it validates its
   checksum and does not reapply it. The Postgres container and this bootstrap
   executor mount the same immutable source directory read-only at a fixed
   path; neither an application variable nor a caller-supplied path can select
   another server file.
4. **Bootstrap post-005 cleanup.** In the same bootstrap job, after a
   successful/validated `005`, it transfers every public object newly created
   by `005` (including functions, types, sequences and `schema_migrations`) to
   `fewa_migrator` without changing data or object IDs. It revokes any legacy
   `pg_read_server_files` membership and direct file-function grant from both
   migrator and app, verifies both memberships are false, and writes the
   successful cleanup audit row. This step is idempotent and is also mandatory
   for a candidate cluster where an earlier attempted bridge was granted.
5. **Migrator post-stage.** Only after cleanup succeeds, the ordinary
   `fewa_migrator` runner applies `006` and later migrations. `006` asserts
   that neither runtime role is a member of `pg_read_server_files`, restores
   `ENABLE ALWAYS` guards and records its ledger entry in its normal transaction.
6. **Runtime cutover.** Compose may inject only `APP_DATABASE_URL` into API
   and workers after runner completion. It proves `fewa_app` connectivity and
   then the external operator may revoke legacy `fewa_user` LOGIN. A rollback
   before this final step restores only the old runtime credential; it never
   rewrites `005`, its ledger record or application data.

The two runners are intentionally separate binaries/entry points. The normal
runner accepts only `MIGRATOR_DATABASE_URL` and may never receive a bootstrap
URL. The bootstrap executor accepts only `BOOTSTRAP_DATABASE_URL`, is limited
to version `005` plus ownership/audit cleanup, and exits before the migrator
post-stage begins. This separation prevents a future generic runner feature
from silently retaining superuser file-read authority.

### 15. Ownership and acceptance correction

| Owner | Permitted files | Required result |
|---|---|---|
| R1 Builder | `infra/postgres/bootstrap_roles.sql`, new `infra/migrations/bootstrap_runner.py` and its Dockerfile/tests, `infra/migrations/runner.py` plus tests, `spec/migrations/006_arch_01_db_roles.sql`, and `test_arch01_db_roles.py`. | Remove the bridge grant/definer cleanup approach; implement stages 1--5 and `006` no-membership assertion. `005` is not edited. |
| S3 integration owner after checkpoint | Compose/config/Dockerfile and new Compose acceptance tests only. | Wire sequential bootstrap-prestage → migrator-through-004 → bootstrap-005-cleanup → migrator-poststage; no API/worker readiness or bootstrap secret before completion. |

In a fresh and a `004 -> 006` upgrade fixture, QA/Sonnet must record all of:

```bash
# Membership and file-read capability must be absent before and after 006.
psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_has_role('fewa_migrator','pg_read_server_files','member'),
          pg_has_role('fewa_app','pg_read_server_files','member')"
psql "$APP_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT pg_read_binary_file('/fixed/read-only/migrations/005_arch_01_pipeline.sql')"

# The special executor refuses any version other than 005 and any mutable or
# caller-selected server source; a failed cleanup blocks the migrator post-stage.
bootstrap-migration-runner --only 005
migration-runner --through 004
migration-runner --from 006

# 005 and 006 ledger rows must exist with source-matching checksums; the audit
# must show successful provision, 005, ownership-normalise and cleanup stages.
psql "$MIGRATOR_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c \
  "SELECT version, checksum FROM schema_migrations WHERE version IN ('005','006') ORDER BY version"
```

Both `pg_has_role` values must be `false`; the app file-read query must fail;
the bootstrap executor must be the only process that can execute `005`'s
server-side read; and a deliberately left-over legacy bridge membership must
be removed and auditable before `006`. QA repeats the app trigger/DDL/replica
negative tests after this sequence and verifies the bootstrap audit is
append-only and inaccessible to `fewa_app`. Manual `psql -f 005` does not meet
acceptance, and no checksum replacement or migration-history rewrite is
authorised.
