# halo-hacker

**A portable, evidence-driven security assessment methodology executed through
[Halo Harness](https://github.com/roloVibes/Halo-Harness)'s multi-model agent
architecture.**

halo-hacker is a capability pack for authorized, professional security
assessment work: specialized agent roles, assessment team lineups, structured
playbooks, engagement scope policy, finding schemas, and evidence-driven
reporting — added ON TOP of Halo, never replacing its runtime. Halo owns
routing, delegation, budgets, Studio and memory; halo-hacker owns the security
methodology.

> **Authorization is the spine.** Everything here assumes a signed, in-scope,
  in-window engagement. Scope is enforced deny-by-default at the policy layer —
  an agent cannot widen it by changing its own instructions, picking a
  different model, or delegating elsewhere. Nothing in this repository is a
  tool for attacking systems you are not explicitly authorized to test.

## What's in the box

| Piece | Where | What it is |
|---|---|---|
| **Capability pack** | `pack/` | The installable unit: manifest, agents, teams, playbooks, schemas, policies |
| Agent roles | `pack/agents/` | 8 bios in Halo's native grammar: orchestrator, recon, web, api, ai-security, validator, judge, reporter |
| Team lineups | `pack/teams/` | 5 assessment teams (web / API / AI / cloud config / validation+reporting) |
| Playbooks | `pack/playbooks/` | 16 versioned, model-independent workflows (OWASP WSTG, API Top 10, LLM Top 10, cloud config guides) |
| Schemas | `pack/schemas/` | engagement, scope-targets, finding, playbook (JSON Schema) |
| Ingestion engine | `ingest/` | Fill your own knowledge base: notes/PDF/GitHub/YouTube → privacy-filtered, trust-tiered, no-delete store |
| MCP surface | `mcp_server.py` | In-session tools for the ingestion engine (`--selftest`) |
| Headless CLI | `cli.py` | Same library, exit-code-gated, refuses on error |

## Install

**Requires Halo 3.2.0.0+ (pack registry).** Until that ships, the documented
compatibility adapter installs the pack's bios and teams through Halo's stable
user directories:

```bash
pack/scripts/install-compat.sh          # validates first, refuses on failure
halo teams use hh-web-app-assessment    # activate a lineup
pack/scripts/uninstall-compat.sh        # removes exactly what it installed
```

No Halo files are patched; the adapter only writes `hh-*` files into
`~/.halo/agents/` and `~/.halo/teams/`.

## The finding lifecycle (no glazing, mechanically enforced)

```
raw observation → validated finding → report section
      ↑ gate            ↑ gate             ↑ gate
```

- A tester produces **candidates**, never confirmed findings.
- An independent **validator** reproduces from the record alone (not the
  tester's narrative).
- A **judge** gates on evidence quality, confidence, and duplication.
- The **reporter** generates from confirmed records — every claim carries an
  evidence reference.
- The schema itself refuses a "confirmed" finding without validation and
  review; attack paths are a projection over `requires`/`grants`, never a
  stored graph.

## Development

```bash
# validate the pack (exit-code gated)
uv run --python 3.12 --with pyyaml --with jsonschema python pack/tools/validate_pack.py

# full test suite (grammar, negatives, schema fixtures, real-harness pin)
uv run --python 3.12 --with pyyaml --with pytest --with jsonschema pytest pack/tests/
```

Status, roadmap, and compatibility tracking live in
`pack/IMPLEMENTATION_STATUS.md`, `pack/COMPATIBILITY.md`, and
`pack/CORE_REQUESTS.md`.

## License

Proprietary, unreleased. Distribution decision pending the leakcheck gate.
