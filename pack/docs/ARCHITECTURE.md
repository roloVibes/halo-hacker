# Halo Hacker pack — architecture

```
halo-hacker/                      (repo; the ingestion engine is untouched)
  pack/                           THE PACK (this directory)
    pack.yaml                     manifest — Halo 3.2.0.0 R1 contract
    agents/     hh-*.yaml         8 role bios: Halo bio grammar + hh: block
    teams/      hh-*.yaml         5 lineups assigning bios to roles
    skills/     (M2)              methodology micro-skills
    playbooks/  (M2)              declarative workflows (playbook.schema)
    policies/                     engagement + broker policy definitions
    findings/                     finding model + (M4) store design
    reporting/  (M4)              generators + exporters
    studio/     (blocked CR-2)    no contributions until the registry exists
    examples/   (M12)             controlled demo fixtures
    schemas/                      engagement / scope / finding / playbook
    tools/validate_pack.py        exit-code-gated validator
    tests/test_pack.py            grammar, negatives, REAL-harness pin
    scripts/install-compat.sh     pre-3.2.0.0 adapter (stable user dirs)
```

## What the pack owns vs borrows

- **Owns:** security methodology, role definitions, playbooks, engagement
  + finding schemas, evidence/reporting workflows, tool adapters (M3).
- **Borrows from Halo (never duplicated):** model routing, agent runtime,
  delegation/teams, permissions, Studio, memory, budgets, cost tracking.
- **Boundary rule** (halo-hacker PLAN.md, 2026-10-04): bytes that cross
  machines or gate boundaries = harness; what the agent knows/does with
  knowledge = this pack. The pack contains no runtime of its own.

## The hh: extension block

Bios speak the exact Halo grammar; pack-specific role contract data
(responsibility, boundaries, inputs/outputs, evidence requirements,
completion criteria) rides under one top-level `hh:` key. Verified
2026-10-21: `halo_harness/agents_yaml.py::validate_agent_bio` tolerates
unknown top-level keys, so the block round-trips through the real loader,
editor and doctor untouched. When 3.2.0.0 R2 lands namespaced ids
(`<pack>/<name>`), `hh:` is already the namespace.
