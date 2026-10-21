# halo-hacker

**A portable, evidence-driven security assessment methodology executed through
[Halo Harness](https://github.com/roloVibes/Halo-Harness)'s multi-model agent
architecture.**

halo-hacker turns Halo — a general-purpose multi-model agent harness — into a
professional security assessment team. It is **not another agent framework**:
it has no runtime, no model config, no orchestration engine of its own. It is
two things that bolt onto Halo:

1. **A capability pack** (`pack/`) — security agent roles, team lineups,
   testing playbooks, engagement/scope/finding schemas, and reporting rules.
2. **An ingestion engine** (`ingest/`) — fills your own private knowledge base
   from your notes, PDFs, GitHub pages, and YouTube transcripts.

Halo provides the machinery (model routing, delegation, budgets, Studio,
memory, cost tracking). halo-hacker provides everything security-specific.
Nothing is duplicated and nothing in Halo is patched.

> **Authorization is the spine.** Everything here assumes a signed, in-scope,
  in-window engagement. Scope is deny-by-default at the policy layer — an
  agent cannot widen it by changing its own instructions, picking a different
  model, or delegating elsewhere. Nothing in this repository is a tool for
  attacking systems you are not explicitly authorized to test.

---

## The big picture: how an assessment runs

```
you ──install pack──▶ Halo ──activates a lineup──▶ a security team
                                                    │
your notes/PDFs/videos ──ingest──▶ your knowledge base ◀── agents consult it
                                                    │
an engagement (signed scope) ──▶ playbooks execute ──▶ candidates
                                                    │
                       independent validation ──▶ judge gate ──▶ report
```

Concretely:

1. You install the pack into Halo and activate a lineup, e.g.
   `halo teams use hh-web-app-assessment`. The session now has an
   orchestrator, recon, testers, a validator, a judge, and a reporter.
2. You create an **engagement**: a signed authorization record, the exact
   in-scope targets, the testing window, approved test accounts, rate limits,
   and what data may leave the machine (`pack/schemas/engagement.schema.json`).
3. The orchestrator decomposes the engagement into **playbook** tasks and
   delegates each to the right specialist role.
4. Testers produce **candidate findings** — never confirmed ones. An
   independent validator reproduces each from the record alone, a judge gates
   it on evidence quality and duplication, and only then does the reporter
   draft the report, with every claim tracing to evidence.

---

## Part 1 — The ingestion engine (`ingest/`): your data, your machine

A security agent is only as good as what it knows. halo-hacker **ships
empty** — no findings, no populated KB, no methodology corpus — and you fill
it with your own material. That is deliberate: a pentester's notes are client
data, and the whole engine is built around that fact.

**What goes in** (one pipeline, four source adapters):

| Source | Adapter | Trust tier |
|---|---|---|
| Local notes (markdown/txt/org/rst trees, Obsidian vaults) | filesystem walk | **first-party** — authoritative |
| PDFs | PyMuPDF (fails loudly on encrypted/scanned, never a silent partial) | first-party |
| GitHub pages | one file per fetch (blob/raw URL — one URL, one document, auditable) | **third-party** — lead, needs corroboration |
| YouTube videos | yt-dlp subtitles | third-party — lead |

**What happens to it**, in order:

1. **Privacy filter first** — non-security content is excluded before
   anything persists, and the filter must *prove it dropped something*
   (prints N-before → M-after). A filter that silently matches nothing is
   indistinguishable from an empty corpus.
2. **Classification** — each document is sorted into the KB's router
   structure (question-first `_moc-*` routers: "I have a 403, what are my
   options?" style entry points).
3. **Distillation** — the document is condensed into a KB entry. By default
   this runs on a **local model lane** so your notes never leave your
   machine; hosted distillation is explicit opt-in with a warning.
4. **Gated upsert** — the entry lands in a provenance ledger: source
   file/URL, content hash, date, confidence, trust tier. There is **no
   delete verb, ever** — append and keyed upsert only; removal is a human
   action in your editor.
5. **Trust tiers apply at read time too** — first-party entries are treated
   as authoritative; web-derived entries are *leads requiring corroboration*,
   every one carrying its source URL and fetch date. The agents' KB-lookup
   discipline treats uncorroborated web-derived entries as leads, not facts.

**Hardening baked in:** pentest notes contain payloads and prompt injections,
so note content is treated as data, never instructions — raw note content
never reaches tool-call context (there's a planted-injection regression
suite). Ambiguous or multi-target writes are refused rather than guessed
(refusal-biased writes; a high refusal rate is the system working).

**Two ways to drive it:**
- `mcp_server.py` — in-session MCP tools (the primary mode; rides Halo's
  model routing and filter handling). Run with `--selftest`.
- `cli.py` — headless CLI over the same library, exit-code gated, refuses
  on error rather than filing bad content.

---

## Part 2 — The capability pack (`pack/`): the security team

### Agent roles (`pack/agents/`)

Eight role bios written in Halo's native agent-bio grammar, so Halo's own
loaders, editors, Studio Roles view, and doctor handle them like any other
agent. Each declares its model policy (`default` — **never a hardcoded
model**; your lineup decides which lane each role runs on), tool
allow/deny lists, budgets, and a pack extension block (`hh:`) carrying the
security role contract: responsibility, boundaries, inputs/outputs, evidence
requirements, and completion criteria.

| Role | Kind | Job |
|---|---|---|
| `hh-orchestrator` | main | Turns the engagement into a plan, delegates, tracks scope/budget/coverage. Never tests anything itself. |
| `hh-recon` | researcher | Maps the attack surface from *provided* data (traffic, specs, docs). Read-only. |
| `hh-web-tester` | custom | Web app testing per the playbooks (WSTG-aligned). Produces candidates only. |
| `hh-api-tester` | custom | API testing — object/function-level authz, authn, input handling (API Top 10). |
| `hh-ai-security-tester` | custom | AI app testing — prompt injection, tool boundaries, output controls (LLM Top 10). |
| `hh-validator` | custom | Independently reproduces candidates *from the record alone* — does not see the tester's reasoning. |
| `hh-judge` | judge | Gates findings on evidence quality, confidence, duplication. Never confirms on assertion. |
| `hh-reporter` | custom | Generates the report from confirmed records. Drafts only — a human submits. |

### Team lineups (`pack/teams/`)

Five ready-made Halo team templates assigning those bios to roles:

- `hh-web-app-assessment` — recon → web → validate → judge → report
- `hh-api-security-review` — API-focused, spec/traffic driven
- `hh-ai-security-review` — LLM-app focused
- `hh-cloud-config-assessment` — config/IAM review (read-heavy)
- `hh-finding-validation-reporting` — just the quality pipeline (re-checks, report regeneration)

Clone and customize any of them (`halo teams edit …`) without touching the
pack's defaults. Applying a lineup never overwrites your own bios.

### Playbooks (`pack/playbooks/`) — the core of the methodology

A playbook is a **versioned, declarative testing workflow** — structured
YAML, validated against a schema, completely independent of any model or
provider (a test mechanically rejects any playbook that names one). Example:

```yaml
playbook_id: discovery.authz-object-level
version: "1.0"
objective: >
  Detect broken object-level authorization: can approved test account A
  read or modify objects it should not own (OWASP API1)?
assigned_role: api                     # which bio executes it
methodology_refs: [OWASP API1:2023, OWASP WSTG-ATHZ-02]
prerequisites:
  - {kind: inventory, detail: recon.endpoint-discovery output}
  - {kind: test_accounts, detail: two accounts with different ownership}
scope_requirements:
  required_activities: [low-impact-validation]   # checked against the engagement
stages:
  - name: cross-account-read-probe
    impact: low-impact
    limits: {max_requests: 50}
    expected_observations: [403/404 expected; 200 with foreign data is a candidate]
    evidence_requirements: [sanitized request/response pair per probe]
```

The 16 shipped playbooks cover all five phases — **reconnaissance**
(asset inventory, endpoint discovery, tech ID — from provided data, not
active scanning), **discovery** (authn, session handling, object/function
authz, input handling, business logic, LLM prompt injection, LLM tool
boundaries, cloud IAM config), **validation** (independent low-impact repro,
and an approval-gated active-validation playbook), **evidence**
(sanitize-and-store), and **reporting** (draft from confirmed findings).

Rules the schema and validator enforce on every playbook:

- **Ordered stages with rising impact**, each declaring what it expects to
  observe and what evidence it must capture.
- **The approval gate:** any stage above `low-impact` must set
  `requires_approval: true` — enforced mechanically, not by prompt wording.
- **Resource limits per stage** (max requests, timeouts) so a playbook can't
  run away.
- **A judge requirement** — most playbooks require independent validation
  and a judge review before anything counts.

### The finding lifecycle — no glazing, enforced by schema

```
raw observation → validated finding → report section
      ↑ gate            ↑ gate             ↑ gate
```

- Testers produce **candidates** with expected-vs-observed and reproduction
  steps. That's all they're allowed to produce.
- The **validator** reproduces independently — from the candidate record,
  without the tester's session or reasoning — and emits
  reproduced / not-reproduced / needs-more-info.
- The **judge** decides: confirmed / rejected / needs-validation /
  duplicate / requires-human-review, always with a cited rationale, never a
  bare severity.
- The **reporter** generates from confirmed records only; every claim
  carries an evidence reference.
- The finding **schema itself** refuses a "confirmed" finding that lacks
  validation, a reviewer decision, and non-empty evidence — an agent
  asserting something is true is not, structurally, enough (there's a
  test pinning this).
- **Attack paths are a projection over findings** (each finding declares
  capability tokens it `requires` and `grants`), never a stored graph —
  a stored graph goes stale; a projection can't.

### Engagement and scope — the wall

Every engagement is a signed record (`pack/schemas/engagement.schema.json` +
`scope-targets.schema.json`): authorization reference, exact targets
(hostnames/CIDRs/ranges) and exclusions (which outrank inclusions), the
testing window, approved test accounts (credential references only — no
secrets stored), rate/concurrency limits, data-handling locality
(on-box-only / local-models-only if you want engagement content to never
leave your machine), and retention. The design target is a Security Tool
Broker that checks every tool action against this policy before execution,
deny-by-default, at exec time against *resolved* addresses — independent of
any model. The mechanical pre-tool-call hook doesn't exist in Halo yet, so
until it does, active stages are human-gated in the playbook schema itself
(tracked in `pack/CORE_REQUESTS.md` as CR-4). Prompt wording is never the
enforcement mechanism.

---

## How it works with Halo Harness — the exact boundary

Halo Harness ([github.com/roloVibes/Halo-Harness](https://github.com/roloVibes/Halo-Harness))
is the chassis: model routing across OpenRouter/Ollama/Anthropic/OpenAI/
Databricks and more, the agent runtime, delegation and team enforcement,
tool permissions, budgets and cost tracking, Studio visualization, memory,
and the Governor rate limiter. halo-hacker consumes all of it and duplicates
none of it.

The rule that decides where anything lives:

> If it moves bytes between machines or gates what crosses a boundary →
> **Halo Harness**. If it's about what the agent knows or does with
> knowledge → **halo-hacker**.

In practice:

- The pack's bios are ordinary Halo agent bios — your lineup picks each
  role's model, so a role can run on a local Ollama model, an OpenRouter
  route, or the session default, and you can change that any time without
  touching the pack.
- The pack's teams are ordinary Halo team templates — delegation, routing,
  budgets, and escalation all execute through Halo's existing machinery.
- A security "swarm" is just N delegated Halo sub-agents with these roles —
  identical chassis machinery to a coding team; the difference is entirely
  the org definition riding on it.
- The ingestion engine's in-session mode rides Halo's model lanes (so a
  filtered/failed model response is never persisted as an answer).

**Install (requires Halo 3.2.0.0+ pack registry).** Until that version
ships, the documented compatibility adapter installs the pack's bios and
teams through Halo's stable user directories — no Halo files are patched:

```bash
pack/scripts/install-compat.sh          # validates first, refuses on failure
halo teams use hh-web-app-assessment    # activate a lineup
pack/scripts/uninstall-compat.sh        # removes exactly what it installed
```

Upstream gaps that matter to this pack (pack registry, Studio contribution
registry, fleet capabilities, the broker hook, the persistent supervisor)
are tracked with rationale and interim workarounds in
**`pack/CORE_REQUESTS.md`**. Nothing is hacked around with private APIs.

---

## Development

```bash
# validate the pack (exit-code gated)
uv run --python 3.12 --with pyyaml --with jsonschema python pack/tools/validate_pack.py

# full test suite (grammar, negatives, schema fixtures, real-harness pin)
uv run --python 3.12 --with pyyaml --with pytest --with jsonschema pytest pack/tests/
```

The suite includes a compatibility pin: every bio and team is run through
**Halo's own validators** when a Halo-Harness checkout is present, proving
the pack speaks the real grammar — and the ingestion engine has its own
offline test suite (`tests/test_ingest.py`).

Status, roadmap, and compatibility: `pack/IMPLEMENTATION_STATUS.md`,
`pack/COMPATIBILITY.md`, `pack/PLAYBOOK_CATALOG.md`,
`pack/INTEGRATION_STATUS.md`, `pack/TEST_RESULTS.md`.

## License

The repository is public as of 2026-10-21 (leakcheck passed — see
`pack/TEST_RESULTS.md`). No open-source license has been chosen yet; all
rights reserved until one is.
