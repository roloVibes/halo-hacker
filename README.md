# Halo Hacker

**Security testing works better as a team.**

**Your models. Your methodology. Your security testing team.**

Halo Hacker brings specialized security agents, reusable testing playbooks,
and evidence-driven workflows to [Halo Harness](https://github.com/roloVibes/Halo-Harness).

Instead of relying on a single model to find something interesting and call
it a vulnerability, Halo Hacker is designed around how real assessments
work: understand the target, investigate a hypothesis, reproduce the
behavior, review the evidence, and write a finding someone else can verify.

Bring your own models. Bring your own knowledge. Keep control of the
assessment.

> **Early development:** The agent templates, playbook catalog, knowledge
> ingestion engine, and offline findings tools exist today. Full Studio
> integration, distributed Fleet workflows, and execution-time scope
> enforcement are still in development.

## A security team, not a single prompt

A useful assessment takes different kinds of thinking. Mapping an
application is different from evaluating an authorization boundary.
Reproducing a finding is different from reviewing its evidence. Writing a
clear report is another skill entirely.

Halo Hacker divides that work among specialized agents:

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

Halo Harness supplies the runtime, model routing, delegation, sessions, and
tools. Halo Hacker supplies the security methodology.

The roles are model agnostic, so the team does not depend on any single
provider.

## Methodology you can actually reuse

Security testing shouldn't begin from a blank prompt every time.

Halo Hacker includes 16 versioned playbooks across reconnaissance,
discovery, validation, evidence collection, and reporting, along with five
team lineups for web applications, APIs, AI security, cloud configuration
review, and findings validation.

Playbooks describe prerequisites, expected observations, evidence
requirements, impact levels, and approval gates. They are structured to be
inspected, improved, and executed consistently as the Halo integration
matures.

The long term goal is simple: make your methodology portable across models,
sessions, and authorized engagements.

## Evidence over confidence

An agent's suspicion is not a confirmed finding.

Halo Hacker's finding model separates candidates from independently
reproduced and reviewed results. Its offline tooling includes structured
findings, an evidence ledger, scanner result normalization, deduplication,
and draft reporting from confirmed records.

The intended workflow is:

**Discover → Investigate → Validate → Review → Report**

A tester proposes a candidate. A validator checks it independently. A judge
examines the evidence and duplication. A reporter produces a draft that a
human reviews before submission.

That is the standard the product is being built toward, not a claim that
the full live workflow is already integrated.

## Your knowledge belongs in the workflow

A security agent is more useful when it can work from the same methodology
and notes as its operator.

Halo Hacker includes a knowledge ingestion engine for local notes and
Obsidian vaults, PDFs, GitHub content, and YouTube transcripts. It records
source provenance and supports local model processing by default, with
hosted processing as an explicit choice.

The repository does not ship anyone's private notes, client findings, or
populated knowledge base. You bring the sources you trust, and you decide
where they are processed.

## Built on Halo Harness

Halo Hacker is an expansion pack, not a competing agent runtime.

| Halo Harness provides | Halo Hacker contributes |
|---|---|
| Model routing and agent execution | Security specific agent roles |
| Teams and orchestration | Assessment lineups and playbooks |
| Tools, skills, and MCP integration | Security tool adapters and knowledge ingestion |
| Sessions, permissions, and budgets | Engagement requirements and finding lifecycle |
| Studio and Fleet infrastructure | Future assessment workspace and distributed workflows |

The separation matters. It lets Halo continue improving as a general
purpose agent platform while Halo Hacker develops as a focused security
assessment product.

## What works today

The current repository includes:

- Eight Halo compatible agent definitions and five team templates.
- Sixteen schema validated testing playbooks.
- Engagement, scope, playbook, and finding schemas.
- Offline findings storage, evidence tracking, and draft report generation.
- Nuclei and Semgrep output normalizers that treat scanner results as
  candidates, not confirmed findings.
- A knowledge ingestion engine with CLI and MCP entry points.
- A compatibility installer for existing Halo versions.

The Caido adapter is currently a read only draft with unverified live
transport. The native Halo pack registry, Studio Engagements workspace,
Fleet specific extensions, and execution time Security Tool Broker are not
yet available as integrated production features.

See [pack/IMPLEMENTATION_STATUS.md](pack/IMPLEMENTATION_STATUS.md),
[pack/COMPATIBILITY.md](pack/COMPATIBILITY.md), and
[pack/TEST_RESULTS.md](pack/TEST_RESULTS.md) for details.

## Try the current pack

Install Halo Harness first.

On currently released Halo versions, use the compatibility installer from
the Halo Hacker repository root:

```bash
pack/scripts/install-compat.sh
halo teams use hh-web-app-assessment
```

The installer adds the pack's role bios and team templates through Halo's
existing configuration directories without patching Halo itself. A native
`halo pack install` workflow is planned for a future Halo release.

To validate the pack and run its offline tests:

```bash
uv run --python 3.12 --with pyyaml --with jsonschema python pack/tools/validate_pack.py
uv run --python 3.12 --with pyyaml --with pytest --with jsonschema pytest pack/tests/
```

> **Note:** The role and team compatibility path is implemented, but a
> complete live assessment running through Halo has not yet been
> demonstrated in the published test results.

## What's next

The next milestones focus on turning the existing components into one
working experience:

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

## Built for authorized assessments

Halo Hacker is intended for systems you own or are explicitly authorized
to assess. Engagement definitions and playbook approval requirements are
part of the design, but declarative policy is not a substitute for runtime
enforcement.

Until the execution broker is available and verified, active testing needs
human control and appropriate external safeguards.

## License

A license has not yet been selected. The repository is currently private
while the upstream Halo Harness extension interfaces land; visibility may
change once a license is chosen. No open-source reuse rights are granted
until then.

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

1. Install the pack and activate a lineup (`halo teams use
   hh-web-app-assessment`). The session now has an orchestrator, recon,
   testers, a validator, a judge, and a reporter.
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

`ingest/` — one pipeline, four source adapters:

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

Entry points: `mcp_server.py` (in-session MCP tools, `--selftest`) and
`cli.py` (headless, exit-code gated, refuses on error).

## Scanner normalizers

`pack/tools/normalizers.py` turns Nuclei (`-jsonl`) and Semgrep (`--json`)
output into schema-valid **candidate** findings — deduped, provenance
labeled, each carrying "scanner output is a candidate, never confirmation."
They enter the same validation → judge → report pipeline as human
candidates.

## The harness boundary

> If it moves bytes between machines or gates what crosses a boundary →
> **Halo Harness**. If it's about what the agent knows or does with
> knowledge → **Halo Hacker**.

Upstream gaps this pack depends on are tracked with rationale and interim
workarounds in [pack/CORE_REQUESTS.md](pack/CORE_REQUESTS.md): the pack
registry (CR-1), Studio contribution registry (CR-2), fleet capabilities
(CR-3), the tool-action broker hook (CR-4), the persistent supervisor
(CR-5), a documented Caido interface (CR-6). Nothing is hacked around with
private APIs, and no Halo file is patched.

---

**Halo Harness runs the agents. Halo Hacker gives them a security
methodology worth running.**
