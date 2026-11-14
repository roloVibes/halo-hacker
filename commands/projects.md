---
description: "List, create, switch, or archive bug bounty programs (multi-project tracking)"
argument-hint: "list | create <id> <name> <platform> | switch <id> | active | archive <id>"
---

# /projects -- multi-project tracking

Each bug bounty program or engagement is a project: its own findings, evidence, and state, isolated from every
other. The active project is what the whole cockpit (findings, ingest, attack paths, traffic) renders.

Run the subcommand in `$ARGUMENTS` through the pack's own tool (never reimplement its checks in prose):

- `list` -- every project (id, name, platform, state, created), newest first.
- `create <id> <name> <platform>` -- a new project. `platform` is one of `hackerone`, `bugcrowd`, `intigriti`,
  or `custom`. An `engagement_id` is optional and can be set later via the Studio form.
- `switch <id>` -- set the active project. The whole cockpit re-renders for that program.
- `active` -- the active project, or say plainly that none is set.
- `archive <id>` -- mark a project archived (read-only, keeps all data).

Command:

```
python "${CLAUDE_PLUGIN_ROOT}/tools/project_manager.py" <subcommand> [args]
```

Print the tool's JSON output to the user as-is (it is the evidence). When the tool refuses, say why and stop --
do not work around the gate. When no subcommand is given, default to `list`.