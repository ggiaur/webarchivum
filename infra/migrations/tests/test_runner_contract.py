"""Fast contract checks for the executable ARCH-01 migration boundary.

The destructive PostgreSQL acceptance companion is run_pg_acceptance.sh.  These
checks intentionally do not require a local database or migration credentials.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = (ROOT / "infra/migrations/runner.py").read_text()
BOOTSTRAP_RUNNER = (ROOT / "infra/migrations/bootstrap_runner.py").read_text()
BOOTSTRAP = (ROOT / "infra/postgres/bootstrap_roles.sql").read_text()
MIGRATION = (ROOT / "spec/migrations/006_arch_01_db_roles.sql").read_text()


def test_runner_is_advisory_locked_and_checksum_ordered() -> None:
    assert "pg_try_advisory_lock" in RUNNER
    assert "checksum drift" in RUNNER
    assert "out-of-order ledger" in RUNNER
    assert "enum_phased" in RUNNER
    assert "PHASE B" in RUNNER
    assert "MIGRATOR_DATABASE_URL" in RUNNER
    assert "MIGRATION_THROUGH=004" in RUNNER
    assert "MIGRATION_FROM=006" in RUNNER
    assert "bootstrap-executor only" in RUNNER
    assert 'selector.add_argument("--through"' in RUNNER


def test_normal_runner_fails_closed_on_leaked_bootstrap_credential() -> None:
    assert "BOOTSTRAP_DATABASE_URL" in RUNNER
    assert "MIGRATOR_DATABASE_URL only is required" in RUNNER


def test_bootstrap_and_runtime_credentials_are_separated() -> None:
    assert "fewa_bootstrap" in BOOTSTRAP
    assert "dedicated fewa_bootstrap principal" in BOOTSTRAP
    assert "fewa_migrator LOGIN NOSUPERUSER" in BOOTSTRAP
    assert "fewa_app LOGIN NOSUPERUSER" in BOOTSTRAP
    assert "NOREPLICATION NOBYPASSRLS NOINHERIT" in BOOTSTRAP
    assert "app_password" in BOOTSTRAP
    assert "migrator_password" in BOOTSTRAP
    assert "GRANT SELECT, INSERT, UPDATE" in MIGRATION
    assert "schema_migrations is deliberately absent" in MIGRATION
    assert "REVOKE pg_read_server_files FROM fewa_migrator" in BOOTSTRAP
    assert "GRANT pg_read_server_files" not in BOOTSTRAP
    assert "SECURITY DEFINER" not in BOOTSTRAP
    assert "OWNER TO fewa_bootstrap" in BOOTSTRAP
    assert "GRANT SELECT ON TABLE public.arch01_bootstrap_operations TO fewa_migrator" in BOOTSTRAP
    assert "REVOKE ALL ON TABLE public.arch01_bootstrap_operations FROM PUBLIC, fewa_app, fewa_migrator" in BOOTSTRAP


def test_bootstrap_executor_is_fixed_to_005_and_performs_audited_cleanup() -> None:
    assert "BOOTSTRAP_DATABASE_URL" in BOOTSTRAP_RUNNER
    assert "MIGRATOR_DATABASE_URL" in BOOTSTRAP_RUNNER
    assert "BOOTSTRAP_DATABASE_URL only is required" in BOOTSTRAP_RUNNER
    assert "FIXED_DB_SOURCE" in BOOTSTRAP_RUNNER
    assert "bootstrap executor accepts only --only 005" in BOOTSTRAP_RUNNER
    assert "ownership_normalise" in BOOTSTRAP_RUNNER
    assert "cleanup" in BOOTSTRAP_RUNNER
    assert "REVOKE pg_read_server_files FROM fewa_migrator" in BOOTSTRAP_RUNNER
    assert "arch01_bootstrap_operations" in BOOTSTRAP_RUNNER
    assert "arch01_bootstrap_operations'" in BOOTSTRAP_RUNNER
    assert 'parser.add_argument("--only"' in BOOTSTRAP_RUNNER


def test_006_fails_closed_without_bootstrap_cleanup_evidence() -> None:
    assert "pg_has_role('fewa_migrator', 'pg_read_server_files', 'member')" in MIGRATION
    assert "pg_has_role('fewa_app', 'pg_read_server_files', 'member')" in MIGRATION
    assert "bootstrap cleanup audit is required" in MIGRATION
    assert "bootstrap audit authority must remain bootstrap-owned" in MIGRATION
    assert "forbidden bootstrap audit write/read privilege" in MIGRATION


def test_006_makes_every_arch01_business_guard_always_enabled() -> None:
    expected = {
        "trg_arch01_migration_ledger_immutable",
        "trg_arch01_snapshot_insert_guard",
        "trg_lifecycle_guard",
        "trg_arch01_release_state_guard",
        "trg_arch01_published_snapshot_artifact_immutable",
        "trg_arch01_release_decision_guard",
        "trg_arch01_release_decision_immutable",
        "trg_arch01_released_artifact_immutable",
        "trg_arch01_verified_artifact_binding_immutable",
        "trg_arch01_policy_activation_guard",
        "trg_arch01_policy_revision_immutable",
        "trg_arch01_policy_hold_guard",
        "trg_arch01_policy_execution",
        "trg_arch01_manual_candidate",
        "trg_arch01_candidate_transition_guard",
        "trg_arch01_legacy_mapping_immutable",
    }
    for trigger in expected:
        assert f"ENABLE ALWAYS TRIGGER {trigger}" in MIGRATION
