import time
from typing import Dict, Any, List, Optional
from kernel.engine.state_machine import StateMachine
from kernel.engine.recovery import RecoveryEngine
from kernel.engine.ipc_router import IPCRouter


class Scheduler:
    """
    AI-SD-OS Kernel Scheduler & Governance Engine.
    Enforces Hard Limits and manages Escalation Levels (L1-L4).
    """

    HARD_LIMITS = {
        "MAX_RUNTIME_MINUTES": 480,  # 8 hours
        "MAX_OUTPUT_TOKENS": 250000,
        "MAX_MODIFIED_FILES_PER_WP": 50,
        "MAX_LOC_ADDED": 4000,
        "MAX_LOC_REMOVED": 2000,
        "MAX_CONSECUTIVE_FAILURES": 5,
    }

    def __init__(self, state_machine: Optional[StateMachine] = None):
        self.state_machine = state_machine or StateMachine()
        self.recovery_engine = RecoveryEngine()
        self.ipc_router = IPCRouter()
        self.start_time = time.time()
        self.total_tokens_consumed = 0
        self.consecutive_failures = 0
        self.total_retries = 0

    def check_governance_limits(
        self,
        tokens_added: int = 0,
        modified_files_count: int = 0,
        loc_added: int = 0,
        loc_removed: int = 0,
    ) -> Dict[str, Any]:
        self.total_tokens_consumed += tokens_added
        elapsed_minutes = (time.time() - self.start_time) / 60.0

        violations = []

        if elapsed_minutes > self.HARD_LIMITS["MAX_RUNTIME_MINUTES"]:
            violations.append(f"Max Runtime Exceeded ({elapsed_minutes:.1f}m > {self.HARD_LIMITS['MAX_RUNTIME_MINUTES']}m)")

        if self.total_tokens_consumed > self.HARD_LIMITS["MAX_OUTPUT_TOKENS"]:
            violations.append(f"Max Token Consumption Exceeded ({self.total_tokens_consumed} > {self.HARD_LIMITS['MAX_OUTPUT_TOKENS']})")

        if modified_files_count > self.HARD_LIMITS["MAX_MODIFIED_FILES_PER_WP"]:
            violations.append(f"Max Modified Files Exceeded ({modified_files_count} > {self.HARD_LIMITS['MAX_MODIFIED_FILES_PER_WP']})")

        if loc_added > self.HARD_LIMITS["MAX_LOC_ADDED"]:
            violations.append(f"Max LOC Added Exceeded (+{loc_added} > +{self.HARD_LIMITS['MAX_LOC_ADDED']})")

        if loc_removed > self.HARD_LIMITS["MAX_LOC_REMOVED"]:
            violations.append(f"Max LOC Removed Exceeded (-{loc_removed} > -{self.HARD_LIMITS['MAX_LOC_REMOVED']})")

        if violations:
            # SPRINT_ABORTED -> L4 Escalation
            self.state_machine.transition_to(
                target_state="SPRINT_ABORTED",
                trigger_agent="GovernanceEngine",
                reason=f"HARD_LIMIT_EXCEEDED: {'; '.join(violations)}",
                is_rollback=True,
            )
            return {
                "status": "SPRINT_ABORTED",
                "escalation_level": "LEVEL_4_HUMAN_INTERVENTION",
                "violations": violations,
            }

        return {"status": "OK", "elapsed_minutes": elapsed_minutes, "tokens": self.total_tokens_consumed}

    def record_failure(self) -> Dict[str, Any]:
        self.consecutive_failures += 1
        self.total_retries += 1

        if self.consecutive_failures <= 3:
            escalation = "LEVEL_1_SELF_HEALING"
            action = "DeveloperAgent retry with stack trace"
        elif self.consecutive_failures <= 4:
            escalation = "LEVEL_2_PEER_REPAIR"
            action = "Peer review by TestAgent / ReviewerAgent"
        elif self.consecutive_failures == 5:
            escalation = "LEVEL_3_AI_REVIEW_BOARD"
            action = "Convene AI Review Board (Architect + Reviewer + Dev)"
        else:
            escalation = "LEVEL_4_HUMAN_INTERVENTION"
            action = "Suspend execution and request human operator intervention"
            self.state_machine.transition_to(
                target_state="HUMAN_REQUIRED",
                trigger_agent="GovernanceEngine",
                reason=f"Max Consecutive Failures Exceeded ({self.consecutive_failures})",
                is_rollback=True,
            )

        return {
            "consecutive_failures": self.consecutive_failures,
            "escalation_level": escalation,
            "recommended_action": action,
        }

    def record_success(self) -> None:
        self.consecutive_failures = 0
