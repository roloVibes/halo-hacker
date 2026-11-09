---
description: Engage, check status, or disengage the active assessment (scope as data, fail-closed inside the test window).
argument-hint: "engage <engagement-root> [--lineup <name>] | status | disengage"
---

# /hh -- engagement control

The engagement record is the boundary: one state file, written by `tools/engage.py`, read by the pack's hooks and
its findings store. Everything active is refused outside the engagement window.

Run the subcommand in `$ARGUMENTS` through the pack's own tool (never reimplement its checks in prose):

- `engage <engagement-root> [--lineup <name>]` -- validate the engagement record at that root against
  `schemas/engagement.schema.json`, refuse unless it is inside its test window and authorized, then record the
  active engagement and its lineup. Fail closed: a record that does not read, or a window that has not opened or
  has expired, refuses with the reason.
- `status` -- print the active engagement (root, window, lineup, targets) or say plainly that none is active.
- `disengage` -- close the engagement and clear the active state.

Command:

```
python "${CLAUDE_PLUGIN_ROOT}/tools/engage.py" <subcommand> [args]
```

Print the tool's JSON output to the user as-is (it is the evidence), and never edit the state file by hand. When
the tool refuses, say why and stop -- do not work around the gate.
