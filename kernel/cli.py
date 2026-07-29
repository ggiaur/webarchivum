import os
import sys
import argparse
from kernel.engine.state_machine import StateMachine
from kernel.engine.ipc_router import IPCRouter
from kernel.engine.recovery import RecoveryEngine
from kernel.engine.memory_indexer import MemoryIndexer
from kernel.engine.scheduler import Scheduler


def main():
    parser = argparse.ArgumentParser(description="AI-SD-OS Kernel Deterministic Runtime CLI")
    subparsers = parser.add_subparsers(dest="command", help="Kernel commands")

    # Status
    subparsers.add_parser("status", help="Show current Kernel state and metrics")

    # Transition
    trans_parser = subparsers.add_parser("transition", help="Trigger a state machine transition")
    trans_parser.add_argument("--to", required=True, help="Target state")
    trans_parser.add_argument("--agent", required=True, help="Trigger agent name")
    trans_parser.add_argument("--reason", required=True, help="Reason for transition")

    # Route IPC
    subparsers.add_parser("route-ipc", help="Process and route all IPC envelopes from outbox to inbox")

    # Checkpoint
    chk_parser = subparsers.add_parser("checkpoint", help="Create a state checkpoint")
    chk_parser.add_argument("--id", required=True, help="Checkpoint ID (e.g. CHK-001)")

    # Restore
    rest_parser = subparsers.add_parser("restore", help="Restore state from checkpoint")
    rest_parser.add_argument("--id", required=True, help="Checkpoint ID to restore")
    rest_parser.add_argument("--git-reset", action="store_true", help="Execute git hard reset to checkpoint SHA")

    # Index Memory
    subparsers.add_parser("index-memory", help="Rebuild MEMORY_INDEX.md from memory/ directory")

    args = parser.parse_args()

    sm = StateMachine()
    ipc = IPCRouter()
    rec = RecoveryEngine()
    mem = MemoryIndexer()
    sched = Scheduler(state_machine=sm)

    if args.command == "status":
        print(f"Kernel Current State: {sm.current_state}")
        chk = rec.load_checkpoint()
        if chk:
            print(f"Latest Checkpoint: {chk.get('checkpoint_id')} ({chk.get('timestamp')})")
            print(f"Git Commit SHA: {chk.get('git_commit_sha')}")
        else:
            print("Latest Checkpoint: None")

    elif args.command == "transition":
        try:
            sm.transition_to(target_state=args.to, trigger_agent=args.agent, reason=args.reason)
            print(f"Successfully transitioned to state: {sm.current_state}")
        except Exception as e:
            print(f"Transition Failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "route-ipc":
        results = ipc.process_outbox()
        print(f"Routed {len(results)} IPC envelope(s):")
        for r in results:
            print(f" - {r}")

    elif args.command == "checkpoint":
        data = rec.create_checkpoint(checkpoint_id=args.id, pipeline_state=sm.current_state)
        print(f"Checkpoint created: {data['checkpoint_id']} (SHA: {data['git_commit_sha']})")

    elif args.command == "restore":
        try:
            data = rec.restore_checkpoint(checkpoint_id=args.id, hard_reset_git=args.git_reset)
            sm.current_state = data["pipeline_state"]
            print(f"Restored checkpoint {args.id} -> Pipeline State: {sm.current_state}")
        except Exception as e:
            print(f"Restore Failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "index-memory":
        content = mem.rebuild_index()
        print("MEMORY_INDEX.md successfully rebuilt:")
        print(content)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
