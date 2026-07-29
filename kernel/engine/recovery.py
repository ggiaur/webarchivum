import os
import json
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHECKPOINT_BASE_DIR = os.path.join(WORKSPACE_ROOT, "checkpoint")


class RecoveryEngine:
    """
    Handles Checkpointing & Rollback Recovery Loop.
    Creates state.json snapshots and restores system to specific checkpoint.
    """

    def __init__(self, checkpoint_dir: str = CHECKPOINT_BASE_DIR):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def get_current_git_commit_sha(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=WORKSPACE_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "unknown-commit-sha"

    def create_checkpoint(
        self,
        checkpoint_id: str,
        pipeline_state: str,
        active_sprint: str = "SPRINT_001",
        active_work_package: str = "WP-001",
        token_consumption_total: int = 0,
        consecutive_failures: int = 0,
        total_retries: int = 0,
    ) -> Dict[str, Any]:
        chk_folder = os.path.join(self.checkpoint_dir, checkpoint_id)
        os.makedirs(chk_folder, exist_ok=True)

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        git_sha = self.get_current_git_commit_sha()

        state_data = {
            "checkpoint_id": checkpoint_id,
            "timestamp": now_iso,
            "pipeline_state": pipeline_state,
            "active_sprint": active_sprint,
            "active_work_package": active_work_package,
            "git_commit_sha": git_sha,
            "token_consumption_total": token_consumption_total,
            "circuit_breaker_counters": {
                "consecutive_failures": consecutive_failures,
                "total_retries": total_retries,
            },
        }

        state_file = os.path.join(chk_folder, "state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)

        # Also write latest state link in root checkpoint dir
        latest_file = os.path.join(self.checkpoint_dir, "state.json")
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)

        return state_data

    def load_checkpoint(self, checkpoint_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if checkpoint_id:
            state_file = os.path.join(self.checkpoint_dir, checkpoint_id, "state.json")
        else:
            state_file = os.path.join(self.checkpoint_dir, "state.json")

        if not os.path.exists(state_file):
            return None

        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def restore_checkpoint(self, checkpoint_id: str, hard_reset_git: bool = False) -> Dict[str, Any]:
        data = self.load_checkpoint(checkpoint_id)
        if not data:
            raise FileNotFoundError(f"Checkpoint '{checkpoint_id}' not found.")

        git_sha = data.get("git_commit_sha")
        if hard_reset_git and git_sha and git_sha != "unknown-commit-sha":
            try:
                subprocess.run(
                    ["git", "reset", "--hard", git_sha],
                    cwd=WORKSPACE_ROOT,
                    check=True,
                    capture_output=True,
                )
            except Exception as e:
                data["git_reset_error"] = str(e)

        data["status"] = "RESTORED"
        data["action"] = "RESUME_FROM_CHECKPOINT"
        return data
