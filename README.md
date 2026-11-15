# halo-hacker

An authorized security assessment capability pack for
[Halo Harness](https://github.com/roloVibes/Halo-Harness): 40
single-responsibility methodology agent templates you compose into a
testing team, pre-built workflows, real-time proxy traffic analysis
(Caido/Burp), multi-project tracking for bug bounty, attack-path mapping
(MITRE ATT&CK/ATLAS), and an evidence-driven finding lifecycle with
independent validation and judging — plus a knowledge ingestion engine
(notes, PDFs, GitHub, YouTube → a provenance-ledger knowledge base you own).

**Community:** questions, ideas and help on the [Halo Harness Discord server](https://discord.gg/NXWXdg7B6v).

## Installation

Four steps, about two minutes. Every command below was run and verified
against halo 3.5.0.0.

### Before you start

- **[Halo Harness](https://github.com/roloVibes/Halo-Harness) 3.5 or
  newer, already installed and initialized.** This is a Halo pack, not a
  standalone program — without Halo there is nothing to install it into.
  If you don't have Halo yet:

  ```sh
  curl -fsSL https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/scripts/install-halo.sh | bash
  halo init        # the wizard: provider, model, permission mode
  ```

  (Windows and no-installer options:
  [Halo-Harness docs/INSTALL.md](https://github.com/roloVibes/Halo-Harness/blob/master/docs/INSTALL.md))

### Step 1 — install the pack

The repository root **is** the pack, so Halo can install it straight from
GitHub. Run this in your **terminal** — the same place you run `halo`. You do
not need a Halo session open; the pack only loads in sessions started *after*
step 2 (Halo reads enabled packs when a session starts).

```sh
halo pack sources add https://github.com/roloVibes/halo-hacker
halo pack install halo-hacker
```

Expected output:

```
installed halo-hacker 0.9.0 at ~/.halo/packs/halo-hacker (disabled)
it offers: 8 bios, 5 lineups, 2 skills, 3 commands, 2 MCP servers, 1 hook event
it requests: mcp:ingest, mcp:cve, bash, hooks, studio-script
enable it: halo pack enable halo-hacker --grant mcp:ingest --grant mcp:cve --grant bash --grant hooks --grant studio-script
```

From a clone instead (`git clone https://github.com/roloVibes/halo-hacker.git`,
then `halo pack install ./halo-hacker`) works the same way.

The pack arrives **disabled** — that is normal; step 2 turns it on.
(If you see `halo-hacker is already installed ... (halo pack update
halo-hacker)`, you already did this — continue at step 2.)

### Step 2 — enable it and grant what it asks for

```sh
halo pack enable halo-hacker --grant-all
```

`--grant-all` gives it the two MCP servers (`ingest`, `cve`), `bash` (the
scope guard classifies Bash commands against the engagement's scope), `hooks`
(the PreToolUse scope guard) and `studio-script` (the findings browser panel).
Granting them one at a time works too:
`halo pack enable halo-hacker --grant mcp:ingest --grant mcp:cve --grant bash --grant hooks --grant studio-script`.

### Step 3 — point it at your knowledge base

The knowledge base is yours; the pack ships no corpus. Until a vault is
set, every ingestion tool refuses to run (the vault guard):

```sh
mkdir -p ~/halo-hacker-kb
halo config set packs.settings.halo-hacker.vault ~/halo-hacker-kb
```

(Or per launch: `HALO_HACKER_VAULT=<path>`.) Optional, and only if you
ingest those sources: `pymupdf` (PDFs) and `yt-dlp` (YouTube subtitles)
in the Python Halo runs under. The MCP server itself is
standard-library-only.

### Step 4 — verify, then start a new session

```sh
halo pack list                  # → halo-hacker  0.9.0  enabled  user
halo pack inspect halo-hacker   # → problems: none
```

Then start Halo (`halo`) — a session that was already open when you
enabled the pack will not have it. Inside a session, activate a team:

```sh
halo teams use halo-hacker--hh-web-app-assessment
```

### Updating and removing

```sh
halo pack update halo-hacker    # from its source: shows what changes, asks before applying
halo pack rollback halo-hacker  # back to the version the last update replaced
halo pack remove halo-hacker    # the pack's files only; your config and vault stay
```

### Working on the pack itself

See **[HALO-PACK.md](HALO-PACK.md)** — the pack's contract page: what every
part is, the change loop (`halo pack test .` must stay at `0 failed`), and the
rules this repo holds to. `CHANGELOG.md` says what changed per version.


## The design idea

**Security testing works better as a team. Your models. Your methodology.
Your security testing team.** Instead of relying on a single model to find
something interesting and call it a vulnerability, halo-hacker is designed
around how real assessments work: understand the target, investigate a
hypothesis, reproduce the behavior, review the evidence, and write a
finding someone else can verify.

## What it adds to Halo

| Piece | What it is |
|---|---|
| **40 methodology agent templates** (`agents/`) | Single-responsibility testers: recon (subdomain, port, tech fingerprint, endpoint, parameter, content), auth/session (auth flow, session, JWT, OAuth, credential), injection (SQLi, XSS, command, SSTI, XXE, deserialization), business logic (IDOR, access control, race condition, payment, workflow), API (REST, GraphQL, rate limit, SSRF, CORS), AI/LLM (prompt injection, tool abuse, data exposure, model manipulation), infrastructure (cloud, CI/CD, network), plus the review pipeline (validator, judge, communicator, traffic analyst) and coordination (manager, reporter). Each is a Builder starting point — `is_template: true`, `models.preference: default`, never a pinned model. The original 8 monolithic roles stay as `hh-orchestrator`, `hh-recon`, etc. |
| **5 pre-built workflows** (`workflows/`) | web-app-assessment, api-security-review, ai-security-review, bug-bounty-hunt, pack-dev — every one flows candidates through independent validation → judging before anything may confirm. `builder-hints.yaml` maps natural language to the right template for the 3.6 Builder. |
| **5 team lineups** (`teams/`) | web-app assessment, API security review, AI security review, cloud config assessment, finding validation + reporting. |
| **16 playbooks** (`playbooks/`) | Declarative, schema-validated workflows across recon, discovery, validation, evidence, and reporting — with the approval gate mechanically enforced (any stage above `low-impact` must set `requires_approval: true`). Catalog: [PLAYBOOK_CATALOG.md](PLAYBOOK_CATALOG.md). |
| **Real-time proxy traffic MCP** (`mcp/traffic_server.py`) | A third MCP server (granted with `mcp:traffic`): start/stop watching Caido or Burp, fetch recent sanitized pairs, list passive-check candidates, and get correlation suggestions (parameter reuse, auth-boundary crossings). Runs as a pack service (`traffic-watch`). |
| **Multi-project tracking** (`tools/project_manager.py`, `/halo-hacker:projects`) | Bug bounty hunters jump between programs; each project has its own findings, evidence, and state. The active project is what the whole cockpit renders. |
| **Live agent dashboard** (`studio/live.js`, `tools/live_view.py`) | Studio Live section: every live session with status and cwd, the live-lines feed, traffic-watch status — SSE-updated. |
| **Ingest visualization** (`studio/ingest.js`, `tools/ingest_view.py`) | Studio Ingest section: source breakdown, trust tiers, topic routing to testing lanes, recent-ingest log. |
| **Attack paths** (`studio/attack-paths.js`, `tools/attack_path_graph.py`) | Studio Attack Paths section: findings as a graph connected by requires/grants capability tokens — demonstrated (solid) vs projected (dashed) — plus MITRE ATT&CK/ATLAS technique mapping. |
| **Real-time alerts** (5 `hh.alert.*` attention kinds) | Critical finding, traffic hit, playbook limit, scope boundary, and agent suggestion — each with action keys, plus 6 event kinds with schemas and sample fixtures. |
| **Schemas** (`schemas/`) | Engagement (signed scope, test window, accounts, rate limits, data locality), scope-targets, playbook, and finding — where `status: confirmed` is structurally impossible without independent reproduction and a reviewer decision citing evidence. |
| **Findings store + reporting** (`tools/`) | Hash-chained evidence ledger with tamper detection and checkpoints, fail-closed writes, controlled withdrawal, and draft report generation from confirmed records only. |
| **Scanner normalizers** (`tools/normalizers.py`) | Nuclei and Semgrep output → schema-valid **candidate** findings — scanner output is a candidate, never a confirmation. |
| **Knowledge ingestion** (`ingest/`, `mcp/ingest_server.py`) | The ingestion MCP server (declared in `.mcp.json`, granted with `mcp:ingest`) plus the headless CLI (`cli.py`): local notes/Obsidian vaults, PDFs, GitHub files, YouTube subtitles → classify → distill → gated upsert into a provenance-ledger KB. Local model lane by default; hosted is explicit opt-in. |
| **Communicate-findings skill** (`skills/communicate-findings/`) | The baked-in reporting doctrine (distilled SANS training, 13 sources — provenance in `resources/SOURCES-comm.md`): the reader model, ten rules, the four questions, the leadership-email shape, the full-report shape, and a mechanical pre-send checklist. No ingestion needed. |
| **CVE enrichment** (`mcp/cve_server.py`) | A second MCP server (granted with `mcp:cve`): NVD 2.0 lookup with an unauthenticated rate pacer, CISA KEV checks (24 h cached), FIRST EPSS scores. Thin, stdlib-only, fail-never. |
| **CVSS 3.1 scoring** (`tools/cvss31.py`) | Local, deterministic scoring: parse/validate vectors, base score + severity, one-call `score_vector`. Differential-verified 380/380 against the reference implementation. Findings store the vector; the score is always derived. |
| **MITRE layer** (`tools/mitre_view.py`, `skills/attack-flow/`) | ATLAS 2026.10 ships in the pack; ATT&CK Enterprise caches on first use. Technique lookup/search, `technique_ids` on findings, and the attack-flow skill: per-finding mapping, the holistic engagement narrative, Navigator layer export, and capability-token chain candidates (projected vs demonstrated, always labeled). |
| **Studio findings view** (`pack.yaml` studio, `tools/findings_view.py`) | A pack-declared Studio section: counts strip, findings table, a review-pipeline stepper (Identified → Under review → Validated → Judged → Confirmed → Reported), filter presets, and a lifecycle feed (`hh.finding` events). Display states: identified / reviewed / confirmed. |
| **Report engine** (`reporting/`, `commands/hh-report.md`, `commands/communicate.md`) | Leadership email (5-part shape, mailto link — the pack generates, never sends) and full findings report (exec summary first, parallel per-finding template, evidence appendices) — confirmed findings only, driven by the communicate-findings doctrine. |
| **Engage-mode** (`tools/engage.py`, `hooks/`) | `/hh` engage/status/disengage: the engagement record as the boundary — one state file, fail-closed engage inside the test window, a pack hook gating shell commands against engagement scope. Scope as data, not location. |
| **Findings import** (`tools/import_findings.py`) | Field-user intake: manual entry, pack-schema JSON, and scanner output (Nuclei/Semgrep) — everything enters as a **candidate** with provenance (source: import/scanner) and real ledger rows; an import can never arrive confirmed. |
| **Passive traffic observer** (`tools/passive_checks.py`, `tools/traffic_observer.py`) | While a human tester works through Caido or Burp, the pack reads their proxy traffic (read-only polling) and surfaces **candidate** findings as they test: declarative checks (missing security headers, verbose banners, stack traces, internal IPs, cookie flags, reflected params), scope-gated, redaction applied before evidence, deduped, never sends anything. The tester tests; the pack watches. |

## What you supply — never bundled

The knowledge base is yours; the pack ships no corpus, no notes, no
findings. The vault (set in [Installation](#installation) step 4) can
also be given per launch: `HALO_HACKER_VAULT=<path>`.

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

1.0.0 — **the team you compose**. Methodology became agents: 40
single-responsibility tester templates replace the 8 monolithic roles, so you
compose a testing team per engagement instead of picking from a fixed lineup.
Plus live proxy traffic analysis, multi-project tracking for bug bounty,
real-time alerts, attack-path mapping, the findings review/judge pipeline in
Studio, and 5 pre-built workflows. The original 8 roles stay as
`hh-orchestrator`, `hh-recon`, etc. **Reinstall once** — the `halo_api` floor
moved to 1.4 and `halo.min` to 3.5.

Verified on this tree at 1.0.0: `halo pack test .` → **103 checks passed**
(1 skip: this machine has no python runtime registered for the fleet
capability; 8 "own test" smoke checks fail locally because Halo's Python lacks
pytest — CI installs it with `--with pytest` and the behaviour suite below is
the real gate), and the pack's own behaviour suite → **170 passed**.

Everything from the earlier releases still stands: the CVE enrichment server,
local CVSS 3.1 scoring (differential-verified against the reference
implementation), the MITRE layer (ATLAS shipped + ATT&CK cached, the
attack-flow skill, technique_ids), the Studio findings view with `hh.finding`
events, the report engine, engage-mode with the scope-guard hook, findings
import, and the communicate-findings doctrine it all reports through. The
ingestion MCP server is smoke-tested end-to-end over stdio JSON-RPC. A
complete live assessment running through Halo has not yet been demonstrated in
the published test results. See
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md),
[COMPATIBILITY.md](COMPATIBILITY.md), and
[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

## License

Copyright © 2026 **Pinball Genie LLC**. All rights reserved — no
open-source reuse rights are granted. See `/LICENSE`. Pinball Genie LLC
is the holding entity for all of roloVibes' development projects.

---

# Technical documentation

*The sections below are the substance behind the pitch above: how the
pieces actually work, with the real schemas and code paths.*

## The team, not a single prompt

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

1. [Install the pack](#installation) (clone → `halo pack install
   ./pack` → `halo pack enable halo-hacker --grant mcp:ingest`). Activate
   a lineup (`halo teams use halo-hacker--hh-web-app-assessment`). The
   session now has an orchestrator, recon, testers, a validator, a
   judge, and a reporter.
2. Create an **engagement** — a signed authorization record, exact
   in-scope targets, the testing window, approved test accounts, rate
   limits, and data-handling locality
   (`schemas/engagement.schema.json`).
3. The orchestrator decomposes the engagement into **playbook** tasks and
   delegates each to the right specialist role.
4. Testers produce **candidate findings** — never confirmed ones. The
   workflow is **Discover → Investigate → Validate → Review → Report**:
   a tester proposes a candidate, a validator checks it independently, a
   judge examines the evidence, and a reporter produces a draft a human
   reviews before submission.

## Agent bios: the real grammar

The eight roles (`agents/hh-*.yaml`) are written in Halo's native
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
`schemas/playbook.schema.json`, model-independent (a test rejects any
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

- The finding **schema** (`schemas/finding.schema.json`) carries a
  conditional constraint: `status: confirmed` is structurally impossible
  without `validation.status: reproduced`, `validation.independent: true`,
  and a `reviewer_decision` citing evidence refs. An agent asserting a
  finding is true cannot satisfy the schema.
- `tools/findings_store.py` additionally **resolves every confirmed
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

Entry points: `mcp/ingest_server.py` (the in-session MCP tools,
`--selftest` — a stdio JSON-RPC server with no MCP SDK dependency) and
`cli.py` (headless, exit-code gated, refuses on error). Both share
`ingest/tools.py`; the vault resolves env var → pack config → refuse.

## Scanner normalizers

`tools/normalizers.py` turns Nuclei (`-jsonl`) and Semgrep (`--json`)
output into schema-valid **candidate** findings — deduped, provenance
labeled, each carrying "scanner output is a candidate, never confirmation."
They enter the same validation → judge → report pipeline as human
candidates.

## The harness boundary

> If it moves bytes between machines or gates what crosses a boundary →
> **Halo Harness**. If it's about what the agent knows or does with
> knowledge → **halo-hacker**.

Upstream gaps this pack depends on are tracked with rationale and interim
workarounds in [docs/CORE_REQUESTS.md](docs/CORE_REQUESTS.md):
the pack registry (CR-1 — SHIPPED in halo 3.2.0.0), Studio contribution
registry (CR-2), fleet capabilities (CR-3), the tool-action broker hook
(CR-4), the persistent supervisor (CR-5), a documented Caido interface
(CR-6). Nothing is hacked around with private APIs, and no Halo file is
patched.

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
