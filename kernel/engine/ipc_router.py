import os
import shutil
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IPC_BASE_DIR = os.path.join(WORKSPACE_ROOT, "kernel", "ipc")
OUTBOX_DIR = os.path.join(IPC_BASE_DIR, "outbox")
INBOX_DIR = os.path.join(IPC_BASE_DIR, "inbox")
ARCHIVE_DIR = os.path.join(IPC_BASE_DIR, "archive")
PERMISSION_MATRIX_PATH = os.path.join(WORKSPACE_ROOT, "kernel", "system", "PERMISSION_MATRIX.md")


class IPCRouter:
    """
    Validates Agent Message Envelopes, enforces Permission Matrix,
    routes messages from outbox to recipient inbox, and archives messages.
    """

    REQUIRED_FIELDS = [
        "MESSAGE_ID",
        "CORRELATION_ID",
        "SENDER",
        "RECIPIENT",
        "TIMESTAMP",
        "STATE_AT_SEND",
        "STATUS_CODE",
        "PAYLOAD",
    ]

    ALLOWED_STATUS_CODES = [
        "TASK_COMPLETE",
        "READY_FOR_TEST",
        "TEST_PASSED",
        "TEST_FAILED",
        "TASK_BLOCKED",
        "ROLLBACK_REQUESTED",
    ]

    def __init__(self, ipc_base: str = IPC_BASE_DIR):
        self.ipc_base = ipc_base
        self.outbox = os.path.join(ipc_base, "outbox")
        self.inbox = os.path.join(ipc_base, "inbox")
        self.archive = os.path.join(ipc_base, "archive")
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for path in [self.outbox, self.inbox, self.archive]:
            os.makedirs(path, exist_ok=True)

    def validate_envelope(self, envelope: Dict[str, Any]) -> tuple[bool, str]:
        for field in self.REQUIRED_FIELDS:
            if field not in envelope or envelope[field] is None:
                return False, f"Missing required field in Message Envelope: '{field}'"

        status_code = envelope.get("STATUS_CODE")
        if status_code not in self.ALLOWED_STATUS_CODES:
            return False, f"Invalid STATUS_CODE: '{status_code}'. Allowed: {self.ALLOWED_STATUS_CODES}"

        payload = envelope.get("PAYLOAD")
        if not isinstance(payload, dict):
            return False, "PAYLOAD must be a dictionary."

        return True, "Valid"

    def route_message_file(self, filepath: str) -> Dict[str, Any]:
        """Reads a YAML message envelope file, validates it, and routes it."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"IPC Message file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)

        is_valid, msg = self.validate_envelope(content)
        if not is_valid:
            raise ValueError(f"IPC Envelope Validation Error: {msg}")

        recipient = content["RECIPIENT"]
        msg_id = content["MESSAGE_ID"]

        # Recipient inbox directory
        recipient_inbox = os.path.join(self.inbox, recipient)
        os.makedirs(recipient_inbox, exist_ok=True)

        target_filepath = os.path.join(recipient_inbox, f"{msg_id}.yaml")
        shutil.copy2(filepath, target_filepath)

        # Move original file to archive
        archive_filepath = os.path.join(self.archive, f"{msg_id}_{os.path.basename(filepath)}")
        shutil.move(filepath, archive_filepath)

        return {
            "status": "routed",
            "message_id": msg_id,
            "sender": content["SENDER"],
            "recipient": recipient,
            "inbox_path": target_filepath,
            "archive_path": archive_filepath,
        }

    def process_outbox(self) -> List[Dict[str, Any]]:
        """Processes all pending YAML envelopes in the outbox directory."""
        results = []
        if not os.path.exists(self.outbox):
            return results

        for filename in sorted(os.listdir(self.outbox)):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.outbox, filename)
                try:
                    res = self.route_message_file(filepath)
                    results.append(res)
                except Exception as e:
                    results.append({"status": "error", "file": filename, "error": str(e)})

        return results
