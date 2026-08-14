"""ARCH-01 S1 migration contract checks.

These tests intentionally inspect the versioned migration rather than the
legacy ``schema.sql``: ARCH-01 must be an upgrade, never a schema rewrite.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "spec/migrations/005_arch_01_pipeline.sql"


def migration_sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_005_declares_enum_phased_runner_contract():
    sql = migration_sql()
    assert "transaction_mode=enum_phased" in sql
    assert "ALTER TYPE lifecycle_status_enum ADD VALUE IF NOT EXISTS 'migration_hold'" in sql
    assert "-- PHASE B" in sql
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql


def test_005_preserves_and_holds_legacy_lifecycle_rows():
    sql = migration_sql()
    for status in ("candidate", "approved", "crawling", "archived", "indexed", "published", "deprecated", "withdrawn"):
        assert f"'{status}'" in sql
    assert "legacy_snapshot_migrations" in sql
    assert "legacy_grandfathered" in sql
    assert "legacy_deprecated_retained" in sql
    assert "legacy_candidate_requires_reapproval" in sql
    assert "migration_hold" in sql


def test_005_replaces_legacy_publish_edge_with_hash_bound_release_gate():
    sql = migration_sql()
    assert "DROP TRIGGER IF EXISTS trg_lifecycle_guard" in sql
    assert "arch01_validate_lifecycle_transition" in sql
    assert "release_decisions" in sql
    assert "gate_matrix_hash" in sql
    assert "arch01_release_idempotency" in sql
    assert "transactional_outbox" in sql
    assert "NEW.lifecycle_status = 'published'" in sql
    assert "current verified artifact/version" in sql
    assert "rd.artifact_id = NEW.artifact_id" in sql
    assert "trg_arch01_released_artifact_immutable" in sql
    assert "object_version_id" in sql
    assert "trg_arch01_published_snapshot_artifact_immutable" in sql
    assert "including after withdrawal" in sql
    assert "NEW.release_state := 'withdrawn'" in sql
    assert "verified artifact state and snapshot/integrity binding are immutable" in sql
    assert "NEW.readback_sha256 IS NULL" in sql
    assert "NEW.readback_sha256 IS DISTINCT FROM NEW.sha256" in sql
    assert "operation IN ('release', 'override', 'withdraw', 'legacy_import')" in sql
    assert "same-transaction authenticated idempotent withdrawal decision" in sql
    assert "snapshot.withdrawn" in sql


def test_005_holds_legacy_depth_and_enforces_revision_only_execution():
    sql = migration_sql()
    assert "crawl_policy_revisions" in sql
    assert "depth_hops BETWEEN 0 AND 2" in sql
    assert "crawl_policy_holds" in sql
    assert "legacy_depth_exceeds_arch01" in sql
    assert "arch01_execution_state" in sql
    assert "arch01_validate_policy_execution" in sql


def test_005_makes_manual_intake_a_provenance_class_not_a_bypass():
    sql = migration_sql()
    assert "candidate_origin_enum" in sql
    assert "legacy_migration" in sql
    assert "manual_review" in sql
    assert "arch01_validate_manual_candidate" in sql
    assert "manual candidate must start uncertain" in sql
