import os
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WORKFLOW_PATH = os.path.join(WORKSPACE_ROOT, "kernel", "workflows", "main_pipeline.yaml")
STATE_LOG_PATH = os.path.join(WORKSPACE_ROOT, "STATE_CHANGE.md")


class StateMachine:
    """
    Deterministic State Machine for AI-SD-OS Kernel.
    Enforces allowed state transitions and records audit trail in STATE_CHANGE.md.
    """

    def __init__(self, current_state: str = "DISCOVERY", workflow_file: str = WORKFLOW_PATH):
        self.workflow_file = workflow_file
        self.config = self._load_workflow_config()
        self.states = self.config.get("states", {})
        self.current_state = current_state if current_state in self.states else "DISCOVERY"
        self._ensure_log_file_exists()

    def _load_workflow_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.workflow_file):
            # Fallback default configuration
            return {
                "states": {
                    "DISCOVERY": {"allowed_next": ["VISION"], "rollback_to": "NONE"},
                    "VISION": {"allowed_next": ["SPEC"], "rollback_to": "DISCOVERY"},
                    "SPEC": {"allowed_next": ["ARCHITECTURE"], "rollback_to": "VISION"},
                    "ARCHITECTURE": {"allowed_next": ["ROADMAP"], "rollback_to": "SPEC"},
                    "ROADMAP": {"allowed_next": ["BOOTSTRAP"], "rollback_to": "ARCHITECTURE"},
                    "BOOTSTRAP": {"allowed_next": ["SPRINT_ACTIVE"], "rollback_to": "ROADMAP"},
                    "SPRINT_ACTIVE": {"allowed_next": ["REVIEW", "HUMAN_REQUIRED", "SPRINT_ABORTED"], "rollback_to": "SPRINT_ACTIVE"},
                    "REVIEW": {"allowed_next": ["RELEASE", "SPRINT_ACTIVE"], "rollback_to": "SPRINT_ACTIVE"},
                    "RELEASE": {"allowed_next": ["SPRINT_ACTIVE", "DISCOVERY"], "rollback_to": "SPRINT_ACTIVE"},
                    "HUMAN_REQUIRED": {"allowed_next": ["SPEC", "ARCHITECTURE", "SPRINT_ACTIVE", "DISCOVERY"], "rollback_to": "NONE"},
                    "SPRINT_ABORTED": {"allowed_next": ["SPEC", "ARCHITECTURE", "DISCOVERY"], "rollback_to": "NONE"},
                }
            }
        with open(self.workflow_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _ensure_log_file_exists(self) -> None:
        if not os.path.exists(STATE_LOG_PATH):
            with open(STATE_LOG_PATH, "w", encoding="utf-8") as f:
                f.write("# STATE CHANGE LOG\n\n")

    def can_transition_to(self, target_state: str) -> bool:
        state_info = self.states.get(self.current_state, {})
        allowed = state_info.get("allowed_next", [])
        return target_state in allowed

    def transition_to(
        self,
        target_state: str,
        trigger_agent: str,
        reason: str,
        is_rollback: bool = False,
        checkpoint_id: Optional[str] = None,
    ) -> bool:
        if not is_rollback and not self.can_transition_to(target_state):
            raise ValueError(
                f"Invalid transition from '{self.current_state}' to '{target_state}'. "
                f"Allowed transitions: {self.states.get(self.current_state, {}).get('allowed_next', [])}"
            )

        from_state = self.current_state
        self.current_state = target_state

        # Log transition in STATE_CHANGE.md
        evt_id = f"EVT-{int(datetime.now(timezone.utc).timestamp() * 1000) % 100000:05d}"
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        log_entry = (
            f"## {evt_id}\n"
            f"- **TIMESTAMP:** {now_iso}\n"
            f"- **FROM_STATE:** {from_state}\n"
            f"- **TO_STATE:** {target_state}\n"
            f"- **TYPE:** {'ROLLBACK' if is_rollback else 'FORWARD'}\n"
            f"- **TRIGGER_AGENT:** {trigger_agent}\n"
            f"- **REASON:** {reason}\n"
        )
        if checkpoint_id:
            log_entry += f"- **CHECKPOINT_RESTORED:** {checkpoint_id}\n"
        log_entry += "\n"

        with open(STATE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)

        return True

    def rollback(self, trigger_agent: str, reason: str, checkpoint_id: Optional[str] = None) -> str:
        state_info = self.states.get(self.current_state, {})
        target_state = state_info.get("rollback_to", "DISCOVERY")
        if target_state == "NONE":
            target_state = "DISCOVERY"

        self.transition_to(
            target_state=target_state,
            trigger_agent=trigger_agent,
            reason=f"ROLLBACK: {reason}",
            is_rollback=True,
            checkpoint_id=checkpoint_id,
        )
        return target_state
