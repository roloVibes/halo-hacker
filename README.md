# halo-hacker

An authorized security assessment capability pack for
[Halo Harness](https://github.com/roloVibes/Halo-Harness): specialized
agent roles, assessment team lineups, structured playbooks, engagement
scope policy, finding schemas, an evidence-driven finding lifecycle, and
a knowledge ingestion engine (notes, PDFs, GitHub, YouTube → a
provenance-ledger knowledge base you own).

```
halo pack install <this-repo>/pack
halo pack enable halo-hacker --grant mcp:ingest
```

**Security testing works better as a team. Your models. Your methodology.
Your security testing team.** Instead of relying on a single model to find
something interesting and call it a vulnerability, halo-hacker is designed
around how real assessments work: understand the target, investigate a
hypothesis, reproduce the behavior, review the evidence, and write a
finding someone else can verify.

## What it adds to Halo

| Piece | What it is |
|---|---|
| **8 agent roles** (`pack/agents/`) | orchestrator, recon, web tester, API tester, AI security tester, validator (independent repro), judge (evidence review), reporter — Halo bio grammar + an `hh:` security-role contract block, model-agnostic (`default` everywhere). |
| **5 team lineups** (`pack/teams/`) | web-app assessment, API security review, AI security review, cloud config assessment, finding validation + reporting. |
| **16 playbooks** (`pack/playbooks/`) | Declarative, schema-validated workflows across recon, discovery, validation, evidence, and reporting — with the approval gate mechanically enforced (any stage above `low-impact` must set `requires_approval: true`). Catalog: [pack/PLAYBOOK_CATALOG.md](pack/PLAYBOOK_CATALOG.md). |
| **Schemas** (`pack/schemas/`) | Engagement (signed scope, test window, accounts, rate limits, data locality), scope-targets, playbook, and finding — where `status: confirmed` is structurally impossible without independent reproduction and a reviewer decision citing evidence. |
| **Findings store + reporting** (`pack/tools/`) | Hash-chained evidence ledger with tamper detection and checkpoints, fail-closed writes, controlled withdrawal, and draft report generation from confirmed records only. |
| **Scanner normalizers** (`pack/tools/normalizers.py`) | Nuclei and Semgrep output → schema-valid **candidate** findings — scanner output is a candidate, never a confirmation. |
| **Knowledge ingestion** (`pack/ingest/`, `pack/mcp/ingest_server.py`) | The ingestion MCP server (declared in `pack/.mcp.json`, granted with `mcp:ingest`) plus the headless CLI (`pack/cli.py`): local notes/Obsidian vaults, PDFs, GitHub files, YouTube subtitles → classify → distill → gated upsert into a provenance-ledger KB. Local model lane by default; hosted is explicit opt-in. |

## A security team, not a single prompt

A useful assessment takes different kinds of thinking. Mapping an
application is different from evaluating an authorization boundary.
Reproducing a finding is different from reviewing its evidence. Writing a
clear report is another skill entirely. halo-hacker divides that work
among specialized agents:

| Agent | Responsibility |
|---|---|
| Orchestrator | Plans the engagement and coordinates the work |
| Recon | Builds an understanding of the approved attack surface |
| Web Tester | Applies web application assessment playbooks |
| API Tester | Reviews API behavior, access controls, and input handling |
| AI Security Tester | Evaluates AI application boundaries and integrations |
| Validator | Independently checks suspected findings |
| Judge | Reviews evidence, confidence, and duplicates |
| Reporter | Turns confirmed findings into reviewable draft reports |

Halo Harness supplies the runtime, model routing, delegation, sessions,
and tools; the roles are model-agnostic, so the team does not depend on
any single provider. The intended workflow:
**Discover → Investigate → Validate → Review → Report** — a tester
proposes a candidate, a validator checks it independently, a judge
examines the evidence, and a reporter produces a draft a human reviews
before submission.

## The vault: yours, never shipped

The ingestion engine writes into a knowledge base you point it at — the
pack ships no corpus, no notes, no findings. Until a vault is set, every
ingestion tool refuses (the vault guard):

```bash
halo config set packs.settings.halo-hacker.vault <path-to-your-kb>
# or, per launch: HALO_HACKER_VAULT=<path>
```

Runtime dependencies the pack does not bundle: `pymupdf` (PDFs) and
`yt-dlp` (YouTube subtitles), loaded only when those sources are used;
the MCP server itself is standard-library-only (no MCP SDK — the SDK's
1.x→2.x `FastMCP` rename broke pack servers that imported it).

## What is NOT in this pack

- No private notes, client findings, or populated knowledge base — you
  bring the sources you trust, and you decide where they are processed.
- No runtime, routing, or orchestration of its own — Halo Harness
  supplies all of that. The pack never imports `halo_harness` internals
  (the documented extension API excepted) and patches no Halo file.
- No active/dynamic testing without human control: the execution-time
  Security Tool Broker is not yet available, so active testing needs
  human control and appropriate external safeguards. Declarative policy
  is not a substitute for runtime enforcement.

## Status

0.5.0 — validated against the shipped `halo pack` implementation:
`halo pack inspect` reports `problems: none` (halo 3.2.1.0, 2026-10-25;
halo 3.3.2.0, 2026-10-27). The ingestion MCP server is smoke-tested
end-to-end over stdio JSON-RPC (initialize + tools/list + vault guard).
The role and team compatibility path is implemented, but a complete live
assessment running through Halo has not yet been demonstrated in the
published test results. See
[pack/IMPLEMENTATION_STATUS.md](pack/IMPLEMENTATION_STATUS.md),
[pack/COMPATIBILITY.md](pack/COMPATIBILITY.md), and
[pack/TEST_RESULTS.md](pack/TEST_RESULTS.md).

## License

Copyright © 2026 **Pinball Genie LLC**. All rights reserved — no
open-source reuse rights are granted. See `/LICENSE`. Pinball Genie LLC
is the holding entity for all of roloVibes' development projects.

---

# Technical documentation

*The sections below are the substance behind the pitch above: how the
pieces actually work, with the real schemas and code paths.*

## How an assessment runs

```
you ──install pack──▶ Halo ──activates a lineup──▶ a security team
                                                    │
your notes/PDFs/videos ──ingest──▶ your knowledge base ◀── agents consult it
                                                    │
an engagement (signed scope) ──▶ playbooks execute ──▶ candidates
                                                    │
                       independent validation ──▶ judge gate ──▶ report
```

1. Install the pack and grant the ingestion server
   (`halo pack enable halo-hacker --grant mcp:ingest`). Activate a
   lineup (`halo teams use halo-hacker--hh-web-app-assessment`). The
   session now has an orchestrator, recon, testers, a validator, a
   judge, and a reporter.
2. Create an **engagement** — a signed authorization record, exact
   in-scope targets, the testing window, approved test accounts, rate
   limits, and data-handling locality
   (`pack/schemas/engagement.schema.json`).
3. The orchestrator decomposes the engagement into **playbook** tasks and
   delegates each to the right specialist role.
4. Testers produce **candidate findings** — never confirmed ones.

## Agent bios: the real grammar

The eight roles (`pack/agents/hh-*.yaml`) are written in Halo's native
agent-bio grammar, so Halo's own loaders, editors, Studio Roles view, and
doctor handle them like any other agent. Each declares its model policy
(`default` — never a hardcoded model; your lineup decides the lane), tool
allow/deny lists, budgets, and a pack extension block (`hh:`) carrying the
security role contract: responsibility, boundaries, inputs/outputs,
evidence requirements, and completion criteria. The Halo loader tolerates
the unknown top-level `hh:` key (verified against the harness's own
validator), so the block round-trips through the real editor untouched.

## Playbook anatomy

A playbook is versioned, declarative YAML validated against
`pack/schemas/playbook.schema.json`, model-independent (a test rejects any
playbook naming a model or vendor). Real example:

```yaml
playbook_id: discovery.authz-object-level
version: "1.0"
objective: >
  Detect broken object-level authorization: can approved test account A
  read or modify objects it should not own (OWASP API1)?
assigned_role: api
methodology_refs: [OWASP API1:2023, OWASP WSTG-ATHZ-02]
prerequisites:
  - {kind: inventory, detail: recon.endpoint-discovery output}
  - {kind: test_accounts, detail: two accounts with different ownership}
scope_requirements:
  required_activities: [low-impact-validation]
stages:
  - name: cross-account-read-probe
    impact: low-impact
    limits: {max_requests: 50}
    expected_observations: [403/404 expected; 200 with foreign data is a candidate]
    evidence_requirements: [sanitized request/response pair per probe]
```

Mechanically enforced on every playbook: ordered stages with rising impact;
**the approval gate** (any stage above `low-impact` must set
`requires_approval: true` — enforced by validator and test, never by prompt
wording); per-stage resource limits; judge requirements.

## The finding lifecycle — enforced, not aspirational

```
raw observation → validated finding → report section
      ↑ gate            ↑ gate             ↑ gate
```

- The finding **schema** (`pack/schemas/finding.schema.json`) carries a
  conditional constraint: `status: confirmed` is structurally impossible
  without `validation.status: reproduced`, `validation.independent: true`,
  and a `reviewer_decision` citing evidence refs. An agent asserting a
  finding is true cannot satisfy the schema.
- `pack/tools/findings_store.py` additionally **resolves every confirmed
  finding's evidence references against the actual ledger rows** — a
  confirmed finding citing evidence that doesn't exist is refused, and a
  mismatched artifact hash is refused.
- The store is **fail-closed**: jsonschema is a hard dependency (no
  validation, no store); writes outside the engagement's authorization
  window or status are refused.
- The evidence ledger is **hash-chained** with tamper, row-removal, and
  artifact-corruption detection; **checkpoints** are the external anchor
  (copy one off-box and `verify_against_checkpoint()` catches a local
  rewrite); all writes are atomic (temp + rename).
- **Controlled withdrawal** exists for sensitive content
  (`withdraw_finding` leaves a tombstone with the original record's hash;
  `purge_artifact` removes bytes but keeps a recorded PURGED marker) —
  audit history survives, content doesn't have to.
- **Attack paths are a projection** over findings (`requires`/`grants`
  capability tokens), never a stored graph.

## The ingestion engine

`pack/ingest/` — one pipeline, four source adapters:

| Source | Adapter | Trust tier |
|---|---|---|
| Local notes (markdown/org/rst, Obsidian vaults) | filesystem walk | first-party — an owned source |
| PDFs | PyMuPDF (fails loudly on encrypted/scanned) | first-party |
| GitHub pages | one file per fetch — auditable | third-party — lead, needs corroboration |
| YouTube | yt-dlp subtitles | third-party — lead |

Pipeline stages: **privacy filter** (two independent judgements —
relevance via cyber signals, sensitivity via structured secret/PII
patterns; secrets drop a document ALWAYS, even a relevant one; a life-word
alone never discards a technical note; the filter proves it dropped
something: N-before → M-after) → **classify** into the KB's question-first
router structure → **distill** (local model lane by default; hosted is
explicit opt-in) → **gated upsert** into a provenance ledger (source,
content hash, date, confidence, trust tier). **No delete verb** — append
and keyed upsert only. First-party entries are trusted as owned sources,
never automatically authoritative as technical conclusions. Note content
is data, never instructions (planted-injection regression suite); ambiguous
writes are refused (refusal-biased).

Entry points: `pack/mcp/ingest_server.py` (the in-session MCP tools,
`--selftest` — a stdio JSON-RPC server with no MCP SDK dependency) and
`pack/cli.py` (headless, exit-code gated, refuses on error). Both share
`pack/ingest/tools.py`; the vault resolves env var → pack config → refuse.

## Scanner normalizers

`pack/tools/normalizers.py` turns Nuclei (`-jsonl`) and Semgrep (`--json`)
output into schema-valid **candidate** findings — deduped, provenance
labeled, each carrying "scanner output is a candidate, never confirmation."
They enter the same validation → judge → report pipeline as human
candidates.

## The harness boundary

> If it moves bytes between machines or gates what crosses a boundary →
> **Halo Harness**. If it's about what the agent knows or does with
> knowledge → **halo-hacker**.

Upstream gaps this pack depends on are tracked with rationale and interim
workarounds in [pack/CORE_REQUESTS.md](pack/CORE_REQUESTS.md): the pack
registry (CR-1 — SHIPPED in halo 3.2.0.0), Studio contribution registry
(CR-2), fleet capabilities (CR-3), the tool-action broker hook (CR-4), the
persistent supervisor (CR-5), a documented Caido interface (CR-6). Nothing
is hacked around with private APIs, and no Halo file is patched.

## What's next

1. Connect the knowledge ingestion engine to agent workflows and finish
   live tool integrations.
2. Demonstrate an end to end assessment against a controlled local lab,
   from candidate finding to reviewed report.
3. Add an Engagements workspace to Halo Studio for scope, progress,
   evidence, findings, and approvals.
4. Extend Halo Fleet so compatible workers can contribute to the same
   authorized assessment.
5. Integrate an independent Security Tool Broker for execution time scope
   checks and approvals before unattended active testing.

---

**Halo Harness runs the agents. halo-hacker gives them a security
methodology worth running.**
