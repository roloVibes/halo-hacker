# Halo Hacker pack — architecture

```
halo-hacker/                      (repo; everything the pack ships lives in pack/)
  pack/                           THE PACK (this directory — what `halo pack install` copies)
    pack.yaml                     manifest — Halo 3.2.0.0 R1 contract
    .mcp.json                     declares the ingestion MCP server (mcp/ingest_server.py)
    agents/     hh-*.yaml         8 role bios: Halo bio grammar + hh: block
    teams/      hh-*.yaml         5 lineups assigning bios to roles
    ingest/                       the knowledge ingestion library (no policy of its own)
      adapters.py                 notes / PDF (pymupdf) / GitHub / YouTube (yt-dlp) → Documents
      pipeline.py                 privacy filter (proves drops) → classify → distill → gated upsert
      store.py                    provenance ledger, NO DELETE VERB, refusal-biased upsert
      model_client.py             Ollama /api/chat (num_ctx + prompt_eval_count canary); OpenRouter hosted lane
      tools.py                    the 5 ingestion tools — shared by the MCP server and the CLI
    mcp/ingest_server.py          stdio JSON-RPC server (stdlib only, no MCP SDK); --selftest asserts the vault guard
    cli.py                        headless entry — same library, same guards; exit-code gated
    skills/     (M2)              methodology micro-skills
    playbooks/  (M2)              declarative workflows (playbook.schema)
    policies/                     engagement + broker policy definitions
    findings/                     finding model + (M4) store design
    reporting/  (M4)              generators + exporters
    studio/     (blocked CR-2)    no contributions until the registry exists
    examples/   (M12)             controlled demo fixtures
    schemas/                      engagement / scope / finding / playbook
    tools/validate_pack.py        exit-code-gated validator
    tests/                        test_pack (grammar, negatives, REAL-harness pin), test_ingest, test_m3_m4
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
