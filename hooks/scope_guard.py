#!/usr/bin/env python3
"""PreToolUse scope guard for halo-hacker engage-mode.

Reads a Claude Code PreToolUse JSON payload from stdin. When no engagement is
active, or the tool is not Bash, exits 0 silently (no gate). When engaged and
the command references an out-of-scope host, prints a JSON decision on stdout
and appends an audit line to the pack data dir gate-log.jsonl.

Contract: exit 0 always; a block is communicated via stdout JSON so the
harness can surface the reason without failing the hook process.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure the pack tools are importable regardless of how the hook is invoked.
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from engage import (  # noqa: E402
    _append_jsonl,
    _gate_log_path,
    _utc_now,
    classify,
    current,
    load_engagement,
)


def _load_targets(engagement_root: Path, engagement: dict) -> dict:
    targets_file = engagement.get("targets_file", "scope/targets.json")
    path = Path(engagement_root) / targets_file
    if not path.is_file():
        return {"includes": [], "exclusions": []}
    return json.loads(path.read_text(encoding="utf-8"))


def decide(payload: dict) -> dict:
    """Return the guard decision for a PreToolUse payload."""
    if payload.get("tool_name") != "Bash":
        return {"decision": "allow"}

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or not command.strip():
        return {"decision": "allow"}

    state = current()
    if not state:
        return {"decision": "allow"}

    root = Path(state["engagement_root"])
    try:
        engagement = load_engagement(root)
        targets = _load_targets(root, engagement)
    except Exception as e:
        # Fail-closed: if we cannot read scope, block with a clear reason.
        return {"decision": "block", "reason": f"cannot load scope: {e}"}

    decision = classify(command, targets)
    if decision.get("decision") == "block":
        eng_id = engagement.get("engagement_id")
        reason = decision.get("reason", "")
        decision["reason"] = f"{reason} (engagement {eng_id})"
        decision["engagement_id"] = eng_id
        _append_jsonl(_gate_log_path(), {
            "timestamp": _utc_now(),
            "engagement_id": eng_id,
            "command": command,
            "reason": decision.get("reason"),
        })
    return decision


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    decision = decide(payload)
    if decision.get("decision") == "block":
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())
