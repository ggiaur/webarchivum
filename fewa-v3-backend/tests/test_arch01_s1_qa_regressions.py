"""Adversarial ARCH-01 S1 database regression tests.

Run against an isolated database after schema.sql and migrations 001--005:

    ARCH01_QA_DATABASE_URL=postgresql://... pytest -q \
        tests/test_arch01_s1_qa_regressions.py

The suite is opt-in so ordinary unit runs never touch a developer database.
"""

import os
import uuid

import asyncpg
import pytest


QA_DSN = os.environ.get("ARCH01_QA_DATABASE_URL")
TENANT_ID = "00000000-0000-0000-0000-000000000001"
CURATOR_ID = "550e8400-e29b-41d4-a716-446655440000"
ADMIN_ID = "00000000-0000-0000-0000-000000000099"


@pytest.fixture
async def qa_conn():
    if not QA_DSN:
        pytest.skip("ARCH01_QA_DATABASE_URL is required for destructive isolated-DB QA")
    conn = await asyncpg.connect(QA_DSN)
    transaction = conn.transaction()
    await transaction.start()
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()


async def _site(conn: asyncpg.Connection) -> uuid.UUID:
    token = uuid.uuid4().hex
    return await conn.fetchval(
        """
        INSERT INTO sites (tenant_id, domain, base_url, display_name)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        TENANT_ID,
        f"arch01-qa-{token}.example",
        f"https://arch01-qa-{token}.example",
        "ARCH-01 QA",
    )


async def _verified_artifact(
    conn: asyncpg.Connection, snapshot_id: uuid.UUID
) -> uuid.UUID:
    token = uuid.uuid4().hex
    artifact_id = await conn.fetchval(
        """
        INSERT INTO artifacts
            (snapshot_id, object_key, object_version_id, sha256, filesize_bytes,
             readback_sha256, validator_report_sha256, verified_at)
        VALUES ($1, $2, $3, repeat('b', 64), 1,
                repeat('b', 64), repeat('e', 64), now())
        RETURNING id
        """,
        snapshot_id,
        f"qa/{token}.wacz",
        token,
    )
    await conn.execute(
        "UPDATE archived_snapshots SET artifact_id=$2 WHERE id=$1",
        snapshot_id,
        artifact_id,
    )
    return artifact_id


async def _active_policy(conn: asyncpg.Connection, site_id: uuid.UUID) -> uuid.UUID:
    """Create the minimal authenticated, active ARCH-01 policy revision."""
    policy_id = await conn.fetchval(
        """
        INSERT INTO crawl_policies (site_id, name, depth, is_active)
        VALUES ($1, $2, 2, true)
        RETURNING id
        """,
        site_id,
        f"approved-{uuid.uuid4()}",
    )
    revision_id = await conn.fetchval(
        """
        INSERT INTO crawl_policy_revisions
            (policy_id, revision, config_json, config_hash, depth_hops, source,
             created_by, reviewed_by, reviewed_at, review_reason)
        VALUES ($1, 1, '{}'::jsonb, repeat('f', 64), 2, 'arch01',
                $2, $2, now(), 'QA approved revision')
        RETURNING id
        """,
        policy_id,
        CURATOR_ID,
    )
    await conn.execute(
        """
        UPDATE crawl_policies
        SET arch01_execution_state='active', active_revision_id=$2
        WHERE id=$1
        """,
        policy_id,
        revision_id,
    )
    return revision_id


@pytest.mark.asyncio
async def test_direct_insert_cannot_create_an_already_published_snapshot(qa_conn):
    """The DB state machine must guard INSERT as well as lifecycle UPDATE."""
    site_id = await _site(qa_conn)

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            """
            INSERT INTO archived_snapshots
                (tenant_id, site_id, seed_url, lifecycle_status, release_state)
            VALUES ($1, $2, $3, 'published', 'released')
            """,
            TENANT_ID,
            site_id,
            "https://direct-published.example",
        )


@pytest.mark.asyncio
async def test_null_actor_legacy_import_cannot_authorize_new_publication(qa_conn):
    """Grandfathering is migration-only, not a null-actor release bypass."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://null-actor.example",
    )
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome,
             gate_matrix_hash, artifact_sha256, import_hash)
        VALUES ($1, 'legacy_import', 'legacy_grandfathered', 'released',
                repeat('1', 64), repeat('2', 64), repeat('3', 64))
        """,
        snapshot_id,
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
            snapshot_id,
        )


@pytest.mark.asyncio
async def test_publish_requires_same_transaction_outbox_and_release_state(qa_conn):
    """A lifecycle-only UPDATE must not publish without the atomic effects."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://atomic-release.example",
    )
    artifact_id = await _verified_artifact(qa_conn, snapshot_id)
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             curator_id, admin_id, curator_reason, admin_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                $2, repeat('b', 64), $3, 'authenticated release',
                $3, $4, 'curator approval', 'admin approval', $5,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        ADMIN_ID,
        f"qa-{uuid.uuid4()}",
    )

    await qa_conn.execute(
        "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
        snapshot_id,
    )
    row = await qa_conn.fetchrow(
        """
        SELECT s.release_state,
               (SELECT count(*) FROM transactional_outbox o
                WHERE o.aggregate_id=s.id) AS outbox_count
        FROM archived_snapshots s WHERE s.id=$1
        """,
        snapshot_id,
    )
    assert row["release_state"] == "released"
    assert row["outbox_count"] == 1


@pytest.mark.asyncio
async def test_release_must_bind_the_snapshots_current_verified_artifact(qa_conn):
    """A caller-provided hash without the referenced DB artifact is not a gate."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://unbound-artifact.example",
    )
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_sha256, actor_id, actor_reason, curator_id, admin_id,
             curator_reason, admin_reason, idempotency_key, request_hash,
             response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                repeat('b', 64), $2, 'release', $2, $3,
                'curator approval', 'admin approval', $4,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        CURATOR_ID,
        ADMIN_ID,
        f"qa-{uuid.uuid4()}",
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
            snapshot_id,
        )


@pytest.mark.asyncio
async def test_first_domain_release_cannot_use_one_principal(qa_conn):
    """The first snapshot of a domain requires distinct curator/admin review."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://first-domain.example",
    )
    artifact_id = await _verified_artifact(qa_conn, snapshot_id)
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                $2, repeat('b', 64), $3, 'single curator', $4,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        f"qa-{uuid.uuid4()}",
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
            snapshot_id,
        )


@pytest.mark.asyncio
async def test_released_artifact_version_reference_is_immutable(qa_conn):
    """A released decision must not silently point at a mutated object version."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://immutable-artifact.example",
    )
    artifact_id = await _verified_artifact(qa_conn, snapshot_id)
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             curator_id, admin_id, curator_reason, admin_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                $2, repeat('b', 64), $3, 'release',
                $3, $4, 'curator approval', 'admin approval', $5,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        ADMIN_ID,
        f"qa-{uuid.uuid4()}",
    )
    await qa_conn.execute(
        "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
        snapshot_id,
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE artifacts SET object_version_id=$2 WHERE id=$1",
            artifact_id,
            f"changed-after-release-{uuid.uuid4()}",
        )


@pytest.mark.asyncio
async def test_withdrawal_preserves_released_artifact_identity(qa_conn):
    """Withdrawal must not make immutable historical release evidence mutable."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://withdrawn-evidence.example",
    )
    artifact_id = await _verified_artifact(qa_conn, snapshot_id)
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             curator_id, admin_id, curator_reason, admin_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                $2, repeat('b', 64), $3, 'release',
                $3, $4, 'curator approval', 'admin approval', $5,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        ADMIN_ID,
        f"qa-{uuid.uuid4()}",
    )
    await qa_conn.execute(
        "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
        snapshot_id,
    )
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'withdraw', 'arch01_gate', 'withdrawn', repeat('a', 64),
                $2, repeat('b', 64), $3, 'legal withdrawal', $4,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        f"withdraw-{uuid.uuid4()}",
    )
    await qa_conn.execute(
        "UPDATE archived_snapshots SET lifecycle_status='withdrawn' WHERE id=$1",
        snapshot_id,
    )
    release_state = await qa_conn.fetchval(
        "SELECT release_state FROM archived_snapshots WHERE id=$1", snapshot_id
    )
    assert release_state == "withdrawn"
    assert await qa_conn.fetchval(
        "SELECT count(*) FROM transactional_outbox WHERE aggregate_id=$1 AND event_type='snapshot.withdrawn'",
        snapshot_id,
    ) == 1

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE artifacts SET object_version_id=$2 WHERE id=$1",
            artifact_id,
            f"changed-after-withdrawal-{uuid.uuid4()}",
        )


@pytest.mark.asyncio
async def test_withdrawal_rejects_null_actor_and_missing_atomic_decision(qa_conn):
    """Withdrawal requires authenticated, idempotent DB evidence and outbox."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        """
        INSERT INTO archived_snapshots
            (tenant_id, site_id, seed_url, lifecycle_status, release_state)
        VALUES ($1, $2, $3, 'qc_passed_pending_release', 'release_pending')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        "https://null-actor-withdrawal.example",
    )
    artifact_id = await _verified_artifact(qa_conn, snapshot_id)
    await qa_conn.execute(
        """
        INSERT INTO release_decisions
            (snapshot_id, operation, decision_origin, outcome, gate_matrix_hash,
             artifact_id, artifact_sha256, actor_id, actor_reason,
             curator_id, admin_id, curator_reason, admin_reason,
             idempotency_key, request_hash, response_hash)
        VALUES ($1, 'release', 'arch01_gate', 'released', repeat('a', 64),
                $2, repeat('b', 64), $3, 'release',
                $3, $4, 'curator approval', 'admin approval', $5,
                repeat('c', 64), repeat('d', 64))
        """,
        snapshot_id,
        artifact_id,
        CURATOR_ID,
        ADMIN_ID,
        f"qa-{uuid.uuid4()}",
    )
    await qa_conn.execute(
        "UPDATE archived_snapshots SET lifecycle_status='published' WHERE id=$1",
        snapshot_id,
    )
    await qa_conn.execute("SELECT set_config('arch01.actor_id', '', true)")

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            """
            UPDATE archived_snapshots
            SET lifecycle_status='withdrawn', lifecycle_reason='legal withdrawal'
            WHERE id=$1
            """,
            snapshot_id,
        )


@pytest.mark.asyncio
async def test_candidate_direct_approval_requires_authenticated_policy_gate(qa_conn):
    """Discovery/legacy candidates cannot gain curator approval by direct SQL."""
    site_id = await _site(qa_conn)
    candidate_id = await qa_conn.fetchval(
        """
        INSERT INTO discovery_candidates
            (tenant_id, site_id, landing_url, canonical_url, state,
             candidate_origin, decision_source, reason_code)
        VALUES ($1, $2, $3, $3, 'uncertain', 'discovery',
                'deterministic', 'content_uncertain')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        f"https://candidate-{uuid.uuid4().hex}.example",
    )
    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE discovery_candidates SET state='curator_approved' WHERE id=$1",
            candidate_id,
        )


@pytest.mark.asyncio
async def test_candidate_approval_rejects_actor_without_active_policy_revision(qa_conn):
    """An authenticated curator alone cannot choose or bypass crawl policy."""
    site_id = await _site(qa_conn)
    candidate_id = await qa_conn.fetchval(
        """
        INSERT INTO discovery_candidates
            (tenant_id, site_id, landing_url, canonical_url, state,
             candidate_origin, decision_source, reason_code)
        VALUES ($1, $2, $3, $3, 'uncertain', 'legacy_migration',
                'legacy_migration', 'legacy_candidate_requires_reapproval')
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        f"https://legacy-candidate-{uuid.uuid4().hex}.example",
    )
    await qa_conn.execute("SELECT set_config('arch01.actor_id', $1, true)", CURATOR_ID)
    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE discovery_candidates SET state='curator_approved' WHERE id=$1",
            candidate_id,
        )


@pytest.mark.asyncio
async def test_manual_candidate_legitimate_approval_creates_snapshot_and_outbox(qa_conn):
    """The only manual approval route is authenticated, policy-bound and atomic."""
    site_id = await _site(qa_conn)
    policy_revision_id = await _active_policy(qa_conn, site_id)
    candidate_id = await qa_conn.fetchval(
        """
        INSERT INTO discovery_candidates
            (tenant_id, site_id, landing_url, canonical_url, state, candidate_origin,
             decision_source, reason_code, submitted_by, submitted_at,
             submitter_rationale, immutable_submission_evidence)
        VALUES ($1, $2, $3, $3, 'uncertain', 'manual', 'manual', 'manual_review',
                $4, now(), 'QA manual submission', '{}'::jsonb)
        RETURNING id
        """,
        TENANT_ID,
        site_id,
        f"https://manual-approve-{uuid.uuid4().hex}.example",
        CURATOR_ID,
    )
    await qa_conn.execute("SELECT set_config('arch01.actor_id', $1, true)", CURATOR_ID)
    await qa_conn.execute(
        "SELECT set_config('arch01.policy_revision_id', $1, true)", str(policy_revision_id)
    )
    await qa_conn.execute(
        "UPDATE discovery_candidates SET state='curator_approved' WHERE id=$1",
        candidate_id,
    )
    assert await qa_conn.fetchval(
        "SELECT lifecycle_status FROM archived_snapshots WHERE discovery_candidate_id=$1",
        candidate_id,
    ) == "approved"
    assert await qa_conn.fetchval(
        "SELECT count(*) FROM transactional_outbox WHERE aggregate_id=$1 AND event_type='candidate.approved'",
        candidate_id,
    ) == 1


@pytest.mark.asyncio
async def test_verified_artifact_cannot_be_rebound_before_release(qa_conn):
    """Verification freezes the crawl-to-snapshot binding before publication."""
    first_site, second_site = await _site(qa_conn), await _site(qa_conn)
    first_snapshot = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID, first_site, f"https://artifact-a-{uuid.uuid4().hex}.example",
    )
    second_snapshot = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID, second_site, f"https://artifact-b-{uuid.uuid4().hex}.example",
    )
    artifact_id = await _verified_artifact(qa_conn, first_snapshot)
    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute("UPDATE artifacts SET snapshot_id=$2 WHERE id=$1", artifact_id, second_snapshot)


@pytest.mark.asyncio
async def test_verified_artifact_cannot_be_unverified_then_rebound(qa_conn):
    """Clearing verified_at must not reopen the frozen cross-snapshot binding."""
    first_site, second_site = await _site(qa_conn), await _site(qa_conn)
    first_snapshot = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID,
        first_site,
        f"https://artifact-unverify-a-{uuid.uuid4().hex}.example",
    )
    second_snapshot = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID,
        second_site,
        f"https://artifact-unverify-b-{uuid.uuid4().hex}.example",
    )
    artifact_id = await _verified_artifact(qa_conn, first_snapshot)

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE artifacts SET verified_at=NULL WHERE id=$1", artifact_id
        )


@pytest.mark.asyncio
async def test_verification_rejects_null_readback_evidence(qa_conn):
    """SQL NULL must not turn incomplete integrity evidence into verified."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID, site_id, f"https://null-readback-{uuid.uuid4().hex}.example",
    )
    artifact_id = await qa_conn.fetchval(
        """
        INSERT INTO artifacts (snapshot_id, object_key, object_version_id, sha256, filesize_bytes,
                               validator_report_sha256)
        VALUES ($1, $2, $3, repeat('b', 64), 1, repeat('e', 64))
        RETURNING id
        """,
        snapshot_id, f"qa/null-readback-{uuid.uuid4()}.wacz", uuid.uuid4().hex,
    )
    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute("UPDATE artifacts SET verified_at=now() WHERE id=$1", artifact_id)


@pytest.mark.asyncio
async def test_verification_rejects_missing_readback_hash(qa_conn):
    """SQL NULL must not satisfy the required readback-SHA equality gate."""
    site_id = await _site(qa_conn)
    snapshot_id = await qa_conn.fetchval(
        "INSERT INTO archived_snapshots (tenant_id, site_id, seed_url) VALUES ($1, $2, $3) RETURNING id",
        TENANT_ID,
        site_id,
        f"https://artifact-null-readback-{uuid.uuid4().hex}.example",
    )
    artifact_id = await qa_conn.fetchval(
        """
        INSERT INTO artifacts
            (snapshot_id, object_key, object_version_id, sha256, filesize_bytes)
        VALUES ($1, $2, $3, repeat('b', 64), 1)
        RETURNING id
        """,
        snapshot_id,
        f"qa/{uuid.uuid4().hex}.wacz",
        uuid.uuid4().hex,
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            """
            UPDATE artifacts
            SET validator_report_sha256=repeat('e', 64), verified_at=now()
            WHERE id=$1
            """,
            artifact_id,
        )


@pytest.mark.asyncio
async def test_manual_candidate_urls_and_content_identity_are_immutable(qa_conn):
    """A manual submission's reviewed target cannot be silently swapped."""
    candidate_id = await qa_conn.fetchval(
        """
        INSERT INTO discovery_candidates
            (tenant_id, landing_url, canonical_url, host, etld_plus_one, content_sha256,
             state, candidate_origin, decision_source, reason_code, submitted_by,
             submitted_at, submitter_rationale, immutable_submission_evidence)
        VALUES ($1, $2, $2, 'manual.example', 'manual.example', repeat('a', 64),
                'uncertain', 'manual', 'manual', 'manual_review', $3, now(),
                'QA manual identity', '{}'::jsonb)
        RETURNING id
        """,
        TENANT_ID,
        f"https://manual-immutable-{uuid.uuid4().hex}.example",
        CURATOR_ID,
    )
    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            "UPDATE discovery_candidates SET canonical_url='https://swapped.example/' WHERE id=$1",
            candidate_id,
        )


@pytest.mark.asyncio
async def test_manual_candidate_origin_and_state_cannot_be_rewritten_directly(qa_conn):
    """Manual provenance must stay immutable and approval must use the DB gate."""
    candidate_id = await qa_conn.fetchval(
        """
        INSERT INTO discovery_candidates
            (tenant_id, landing_url, canonical_url, state, candidate_origin,
             decision_source, reason_code, submitted_by, submitted_at,
             submitter_rationale, immutable_submission_evidence)
        VALUES ($1, $2, $2, 'uncertain', 'manual', 'manual', 'manual_review',
                $3, now(), 'QA evidence', '{}'::jsonb)
        RETURNING id
        """,
        TENANT_ID,
        f"https://manual-{uuid.uuid4().hex}.example",
        CURATOR_ID,
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            """
            UPDATE discovery_candidates
            SET candidate_origin='discovery', state='curator_approved'
            WHERE id=$1
            """,
            candidate_id,
        )


@pytest.mark.asyncio
async def test_depth_hold_cannot_be_activated_without_curator_reapproval(qa_conn):
    """A hold plus an unauthenticated legacy_normalized revision stays inert."""
    site_id = await _site(qa_conn)
    policy_id = await qa_conn.fetchval(
        """
        INSERT INTO crawl_policies (site_id, name, depth, is_active)
        VALUES ($1, $2, 3, true)
        RETURNING id
        """,
        site_id,
        f"held-{uuid.uuid4()}",
    )
    await qa_conn.execute(
        """
        INSERT INTO crawl_policy_holds
            (policy_id, legacy_depth, legacy_config_hash, legacy_is_active,
             hold_reason)
        VALUES ($1, 3, repeat('e', 64), true, 'legacy_depth_exceeds_arch01')
        """,
        policy_id,
    )
    revision_id = await qa_conn.fetchval(
        """
        INSERT INTO crawl_policy_revisions
            (policy_id, revision, config_json, config_hash, depth_hops,
             source, review_reason)
        VALUES ($1, 1, '{}'::jsonb, repeat('f', 64), 2,
                'legacy_normalized', 'no authenticated curator')
        RETURNING id
        """,
        policy_id,
    )

    with pytest.raises(asyncpg.PostgresError):
        await qa_conn.execute(
            """
            UPDATE crawl_policies
            SET arch01_execution_state='active', active_revision_id=$2
            WHERE id=$1
            """,
            policy_id,
            revision_id,
        )
