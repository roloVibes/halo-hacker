# Halo Hacker pack — architecture

```
halo-hacker/                      THE PACK — the repo root IS the pack, what `halo pack install` copies
  pack.yaml                       manifest — the pack contract
  .mcp.json                       declares the ingestion + CVE MCP servers (mcp/*.py)
  agents/     hh-*.yaml           8 role bios: Halo bio grammar + hh: block
  teams/      hh-*.yaml           5 lineups assigning bios to roles
  ingest/                         the knowledge ingestion library (no policy of its own)
    adapters.py                   notes / PDF (pymupdf) / GitHub / YouTube (yt-dlp) → Documents
    pipeline.py                   privacy filter (proves drops) → classify → distill → gated upsert
    store.py                      provenance ledger, NO DELETE VERB, refusal-biased upsert
    model_client.py               Ollama /api/chat (num_ctx + prompt_eval_count canary); OpenRouter hosted lane
    tools.py                      the 5 ingestion tools — shared by the MCP server and the CLI
  mcp/ingest_server.py            stdio JSON-RPC server (stdlib only, no MCP SDK); --selftest asserts the vault guard
  cli.py                          headless entry — same library, same guards; exit-code gated
  skills/                         methodology micro-skills (communicate-findings, attack-flow)
  playbooks/                      declarative workflows (playbook.schema)
  policies/                       engagement + broker policy definitions
  findings/                       finding model + store design
  reporting/                      generators + exporters
  studio/                         the Studio panels (bundle sources + notes)
  examples/                       controlled demo fixtures
  schemas/                        engagement / scope / finding / playbook
  tools/validate_pack.py          exit-code-gated validator
  tests/                          the pack's behaviour suite + tests/pack_test.py (the standard checks)
```

> **Layout change (0.9.0, 2026-11-08):** the pack moved from `pack/` to the
> repository root, so `halo pack sources add https://github.com/roloVibes/halo-hacker`
> + `halo pack install halo-hacker` works. An install recorded from
> `./halo-hacker/pack` must be updated or reinstalled once.

## What the pack owns vs borrows

- **Owns:** security methodology, role definitions, playbooks, engagement
  + finding schemas, evidence/reporting workflows, tool adapters (M3).
- **Borrows from Halo (never duplicated):** model routing, agent runtime,
  delegation/teams, permissions, Studio, memory, budgets, cost tracking.
- **Boundary rule** (halo-hacker _research/PLAN.md, 2026-10-04): bytes that cross
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
