import os
import pytest
import shutil
import tempfile
from kernel.engine.state_machine import StateMachine
from kernel.engine.ipc_router import IPCRouter
from kernel.engine.recovery import RecoveryEngine
from kernel.engine.memory_indexer import MemoryIndexer
from kernel.engine.scheduler import Scheduler


def test_state_machine_valid_transitions(tmp_path):
    wf_file = tmp_path / "main_pipeline.yaml"
    wf_file.write_text("""
states:
  DISCOVERY:
    allowed_next: [VISION]
    rollback_to: NONE
  VISION:
    allowed_next: [SPEC]
    rollback_to: DISCOVERY
  SPEC:
    allowed_next: [ARCHITECTURE]
    rollback_to: VISION
  ARCHITECTURE:
    allowed_next: [ROADMAP]
    rollback_to: SPEC
""")
    sm = StateMachine(current_state="DISCOVERY", workflow_file=str(wf_file))
    assert sm.current_state == "DISCOVERY"

    assert sm.can_transition_to("VISION") is True
    assert sm.can_transition_to("SPEC") is False

    res = sm.transition_to("VISION", trigger_agent="DiscoveryAgent", reason="Vision completed")
    assert res is True
    assert sm.current_state == "VISION"


def test_state_machine_invalid_transition_raises():
    sm = StateMachine(current_state="DISCOVERY")
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.transition_to("SPRINT_ACTIVE", trigger_agent="DeveloperAgent", reason="Unallowed jump")


def test_state_machine_rollback():
    sm = StateMachine(current_state="ARCHITECTURE")
    rolled_state = sm.rollback(trigger_agent="ArchitectureAgent", reason="SQLite not viable", checkpoint_id="CHK-SPEC-002")
    assert rolled_state == "SPEC"
    assert sm.current_state == "SPEC"


def test_ipc_router_validation_and_routing(tmp_path):
    ipc_dir = tmp_path / "ipc"
    router = IPCRouter(ipc_base=str(ipc_dir))

    valid_envelope = {
        "MESSAGE_ID": "MSG-20260729-001",
        "CORRELATION_ID": "WP-001",
        "SENDER": "DeveloperAgent",
        "RECIPIENT": "TestAgent",
        "TIMESTAMP": "2026-07-29T15:30:00Z",
        "STATE_AT_SEND": "SPRINT_ACTIVE",
        "STATUS_CODE": "READY_FOR_TEST",
        "PAYLOAD": {"SUMMARY": "JWT implemented"},
    }

    is_valid, msg = router.validate_envelope(valid_envelope)
    assert is_valid is True

    # Test invalid envelope
    invalid_envelope = {"SENDER": "Dev"}
    is_valid, msg = router.validate_envelope(invalid_envelope)
    assert is_valid is False
    assert "Missing required field" in msg

    # Create outbox message file and route it
    outbox_file = os.path.join(router.outbox, "msg1.yaml")
    import yaml
    with open(outbox_file, "w", encoding="utf-8") as f:
        yaml.dump(valid_envelope, f)

    results = router.process_outbox()
    assert len(results) == 1
    assert results[0]["status"] == "routed"
    assert results[0]["recipient"] == "TestAgent"
    assert os.path.exists(results[0]["inbox_path"])
    assert os.path.exists(results[0]["archive_path"])


def test_recovery_engine_checkpoint(tmp_path):
    rec_dir = tmp_path / "checkpoint"
    rec = RecoveryEngine(checkpoint_dir=str(rec_dir))

    data = rec.create_checkpoint(
        checkpoint_id="CHK-001",
        pipeline_state="SPEC",
        active_sprint="SPRINT_001",
        active_work_package="WP-001",
    )

    assert data["checkpoint_id"] == "CHK-001"
    assert data["pipeline_state"] == "SPEC"

    loaded = rec.load_checkpoint("CHK-001")
    assert loaded is not None
    assert loaded["pipeline_state"] == "SPEC"

    restored = rec.restore_checkpoint("CHK-001", hard_reset_git=False)
    assert restored["status"] == "RESTORED"
    assert restored["action"] == "RESUME_FROM_CHECKPOINT"


def test_memory_indexer(tmp_path):
    mem_dir = tmp_path / "memory"
    indexer = MemoryIndexer(memory_dir=str(mem_dir))

    # Create dummy pattern
    pat_file = mem_dir / "patterns" / "PAT-002-test-pattern.md"
    pat_file.write_text("# PAT-002 Test Pattern\n\nKulcsszavak: `pytest, testing, unit`")

    entries = indexer.scan_memory_files()
    assert len(entries) >= 1

    content = indexer.rebuild_index()
    assert "# MEMORY INDEX" in content
    assert "PAT-002" in content


def test_scheduler_governance_limits_and_escalation():
    sched = Scheduler()

    # Success records reset consecutive failures
    sched.record_failure()
    assert sched.consecutive_failures == 1
    sched.record_success()
    assert sched.consecutive_failures == 0

    # L1 Escalation
    r1 = sched.record_failure()
    assert r1["escalation_level"] == "LEVEL_1_SELF_HEALING"

    # L2 Escalation (4th failure)
    sched.consecutive_failures = 3
    r2 = sched.record_failure()
    assert r2["escalation_level"] == "LEVEL_2_PEER_REPAIR"

    # L3 Escalation (5th failure)
    r3 = sched.record_failure()
    assert r3["escalation_level"] == "LEVEL_3_AI_REVIEW_BOARD"

    # L4 Escalation (6th failure)
    r4 = sched.record_failure()
    assert r4["escalation_level"] == "LEVEL_4_HUMAN_INTERVENTION"
    assert sched.state_machine.current_state == "HUMAN_REQUIRED"

    # Test Governance limits violation
    sched_gov = Scheduler()
    res = sched_gov.check_governance_limits(tokens_added=300000)
    assert res["status"] == "SPRINT_ABORTED"
    assert res["escalation_level"] == "LEVEL_4_HUMAN_INTERVENTION"
