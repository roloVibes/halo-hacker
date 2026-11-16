# ARTEX review — what halo-hacker should take, adapt, or skip

> 2026-11-16. Source read: local clone at `vibes/github/ARTEX` (shallow,
> upstream `BaaRai/ARTEX`, itself the English continuation of
> `Autumn-27/ARTEX`, AGPL-3.0). This is a *design* review — AGPL means no
> code moves into the pack. What follows is what the code actually does
> (read: `db/schema.sql`, `agent/coverage_ledger.go`, `agent/retester.go`,
> `traffic/evidence.go`, `db/finding_verification.go`, `guard/guard.go`),
> then a gap-assessment against the pack's own state, then a ranked plan.

## What ARTEX actually is (verified, not README claims)

A self-hosted autonomous pentest platform: one Go binary + PostgreSQL +
an embedded Next.js UI, planner/worker agents over the `norma` SDK. The
parts worth studying, with their real mechanics:

### 1. Dual-graph memory (`db/schema.sql` §A/§B)

- **Asset graph** — a `assets` table with a CHECK-constrained type enum
  (`root_domain | ip | subdomain | app | service | endpoint`) and one
  partial unique index per type for dedupe (`uq_av2_endpoint` on
  `(url, method)`, `uq_av2_service_http` on `(url)`, etc.). The program
  computes parentage and dedupe keys; **agents only submit raw
  observations** — they never write graph structure directly.
- **Exploration graph** — `exploration_nodes` with a kind/state machine
  (`goal→met`, `intent→open/running/done/blocked/exhausted`,
  `fact→confirmed/dismissed`, `finding→confirmed/dismissed`, plus
  `hint` and a `digest` kind for cold-node compaction) and
  `exploration_edges` with rel ∈
  `{spawns, derived_from, yields, proves, covers}`.
- **Anchors** — `exploration_anchors(node_id, asset_id)`, a pure join
  table. This is the load-bearing piece: it ties reasoning nodes to
  concrete assets, which is what makes *test coverage* a graph query
  instead of a report-time guess.

### 2. Coverage ledger (`agent/coverage_ledger.go` + `db/coverage_ledger.go`)

A `record_coverage` tool the worker calls per (surface, risk_area) with
an outcome enum: `reported | no_issue_found | ruled_out | not_applicable
| needs_follow_up`. Two design choices worth stealing outright:

- **Negative results are first-class.** `no_issue_found` requires an
  evidence ref (a fact id / intent id / traffic id); `ruled_out` and
  `not_applicable` require a reason. Missing evidence/reason is
  *surfaced as a gap, not blocked*. The point (their comment): "an
  absent finding is never read as a clean target."
- **The planner sees the ledger every round** as a compact counters
  block, and at wrap-up the remaining gaps are listed explicitly so an
  unexamined class can't be silently judged clean.

### 3. Evidence binding + verification (`db/schema.sql` §L, `traffic/evidence.go`)

- `traffic_evidence_snapshots` — hash-pinned request/response captures
  (`req_hash`, `resp_hash`, heads, lengths) stored separately from the
  live traffic store so evidence survives traffic-log cleanup.
- `finding_traffic_bindings(finding_id, snapshot_id, role, position)` —
  a finding binds N ordered captures.
- `findings` carries `poe_level` (0–4), `verification_status`
  (`verified|unverified|blocked|not_assessed|false_positive`),
  `counterevidence` ("what was tested and did NOT work"), and
  `confidence_rationale` — all server-side-whitelisted, no CHECK, so the
  vocabulary can grow without migrations.
- Verification is *machine-checked*: a finding is `verified` only when
  bound evidence carries verbatim quotes present in the captured
  (gzip/deflate-decoded) response.

### 4. Retest lifecycle (`agent/retester.go`, `finding_retests` table)

A dedicated retester agent with a seeded prompt worth reading in full —
its discipline: retest only this finding; a single failed request never
proves "fixed"; every verdict (`reproduced | fixed | inconclusive`) must
cite this run's own requests/responses, and before any verdict the agent
argues the opposite case along five axes (reachability, preconditions,
reproducibility, scope, claimed impact). `finding_retests` keeps verdicts
separate from the finding's human disposition; a `fixed` verdict flips
status automatically, and deleting the retest session stops (not deletes)
the record.

### 5. Autonomy brakes (`guard/guard.go`, `agent/noise_profile.go`, `agent/untrusted_boundary.go`)

- Intercept rules with three match types (`string | regex | argv`); the
  argv form is a JSON token array matched against a *parsed* command
  prefix, so `["git","push"]` covers `git push --force` but not
  `git -C /repo push`, and pipes/subshells/redirections never match —
  a precise, explainable gate. Each decision records `decided_by` ∈
  `human | rule | model | system`.
- `target_pins`: host+port approvals a human grants once per
  task/conversation, recording resolved IPs and revocable (never
  deleted). A name-only mode exists for when an egress proxy chooses the
  address.
- Noise governor: `quiet | balanced | aggressive` profiles → per-host
  rate/burst/in-flight caps, jitter, 429/503 backoff honouring
  Retry-After, short GET caching, and a "low-and-slow" prompt block
  handed to agents with the exact rate flags for the installed scanners.
- Untrusted-output boundary: tool results framed between nonce-tagged
  markers so the model treats them as data — on by default, ~154 bytes
  per result. (halo-hacker already has this as doctrine in
  `_research/PLAN.md` §7 hostile-corpus hardening; ARTEX implements it as
  a harness-level envelope.)

## What halo-hacker already has — correcting my first pass

The first-pass gap list overstated three things. Read against the pack's
own files:

- **The finding schema's confirmation gate is stronger than ARTEX's.**
  `schemas/finding.schema.json` makes `confirmed` structurally impossible
  without an *independent* reproduced validation plus a judge decision
  citing evidence (the `allOf`/`if/then` block, added as "P0 hardening
  2026-10-21"). ARTEX's `poe_level` is a server-side int. Ours is the
  better gate; ARTEX's `counterevidence` + `confidence_rationale` fields
  are the two things to graft on.
- **Evidence binding exists as a concept** — `evidence[].ledger_ref`
  ("hash-chained ledger row reference; must resolve and chain-verify")
  with `artifact_sha256`. What's missing is the *runtime store* that
  makes `ledger_ref` resolvable (Milestone 4, unbuilt, per
  `findings/README.md`) and any binding to captured HTTP traffic.
- **Attack paths are deliberately a projection, never a stored graph**
  (`requires`/`grants` tokens, `skills/attack-flow/SKILL.md`). ARTEX's
  stored exploration graph is *not* a model to import wholesale — it
  would contradict a settled pack doctrine.

## The real gaps (ranked)

### G1 — An asset model + coverage ledger. The biggest one.

The finding schema's `target_ref` is a free string. There is no asset
type, no dedupe, and no way to answer "which in-scope assets have been
tested, and for which risk classes." ARTEX's asset enum + anchors +
coverage ledger is the single most valuable pattern to adopt, and it
fits the pack's own rules: it's *knowledge the agent holds*, not a
runtime, so it belongs in the pack (`schemas/` + `findings/`), not the
harness.

Concretely:
- A new `schemas/asset.schema.json`: the six-type enum, per-type
  identity/dedupe keys, containment (`root_domain → subdomain → service
  → endpoint`). Agents submit observations; a pack tool computes
  parentage — mirroring ARTEX's "agents never write graph structure."
- A new `schemas/coverage.schema.json`: the (surface, risk_area,
  outcome, evidence_ref, reason) record with the same outcome enum and
  the same rule that negative results demand evidence or a reason.
- `target_ref` on findings becomes a ref into the asset model (soft —
  keep the string form working; this is a schema *addition*, not a
  breaking change).
- A pack tool (stdlib Python, same convention as `tools/mitre_view.py`)
  that builds the coverage ledger from recorded entries and emits the
  planner-facing "tested / untested / gaps" summary. Exit-code gated,
  proves its drops (per the pack's own filter-proof rule).

### G2 — Verbatim evidence-quote verification for the validator.

The schema binds evidence by `ledger_ref` + hash, but nothing
*mechanically re-checks* that a quoted string actually appears in the
captured response. ARTEX's quote-check (decode gzip/deflate, assert the
verbatim quote is present before `verified` is reachable) is exactly the
kind of mechanical, exit-code-gated check the pack prefers. This belongs
in the hh-validator flow as a tool, not a prompt instruction — matching
the "doctrine never relies on the model's good behavior" rule.

Depends on G4 for where the captured response comes from.

### G3 — A finding-retest playbook + lifecycle states.

The playbooks cover validate-once (`validation.low-impact-repro`,
`validation.active-approval-gated`); nothing covers re-testing a
confirmed finding later. ARTEX's retester prompt is the best artifact in
the whole repo and maps directly onto the pack's existing validator +
judge roles. Concretely:
- A `playbooks/validation.retest.yaml`.
- Finding-schema addition: a `retest` block (verdict ∈
  `reproduced | fixed | inconclusive`, this-run evidence refs, the
  five-axes counterargument note) kept *separate from* `status`, exactly
  as ARTEX keeps `finding_retests` apart from disposition. A `fixed`
  verdict should move `status` only through the normal judge gate — the
  retest proposes, the judge disposes.

### G4 — Traffic evidence binding, via the existing Caido path.

CR-6 already closed the interface question: `caido-mcp-extended` is the
live traffic surface and `tools/caido_adapter.py` is the pack's read-only
normalization + redaction layer. The ARTEX-shaped addition is narrow:
when a finding's evidence is a request/response, the adapter should be
able to produce a *hash-pinned snapshot* (ARTEX's
`traffic_evidence_snapshots` shape: url/method/status/heads/lengths/
req_hash/resp_hash) that the finding's `evidence[].ledger_ref` resolves
to — so evidence survives the Caido project's own churn. No new MCP
server, no proxy in the pack; reuse what CR-6 already blessed.

### G5 — Durable attack-chain state (adopt cautiously).

ARTEX's planner keeps a per-task todolist across wake-ups, dispatching a
chain step only when prerequisite facts exist. The pack's attack-flow is
a projection *by design*. The compatible version: a persisted
"chain-candidate" record (finding ids + the requires/grants edge that
links them + `projected | demonstrated` label, which the skill already
mandates as a label). That makes chains survivable across sessions
without storing a graph — it stores the *candidate*, the projection
still derives the path. Lowest priority; only worth doing if engagement
sessions actually span multiple halo sessions.

## What to skip / already covered

- **LLM profiles, failover, budgets, token accounting** — the pack
  borrows these from halo by design (`docs/ARCHITECTURE.md` "Owns vs
  borrows"). ARTEX's `llm_profiles` + breaker table is harness territory,
  already covered.
- **The stored exploration graph as-is** — contradicts the "attack paths
  are a projection" doctrine. Take the *anchor* idea (G1), not the graph.
- **The Go runtime / Next.js UI** — AGPL, and Studio panels are the
  pack's surface (CR-2). Nothing to take.
- **The untrusted-output boundary as a pack feature** — already pack
  doctrine (PLAN §7). If it's worth enforcing mechanically it's a halo
  (harness) ask, not a pack one — same boundary rule as the Governor.

## Recommended order

1. **G1 asset + coverage schemas** — foundation; G2 and G3 both want
   refs into it.
2. **G4 Caido evidence snapshots** — unblocks G2; reuses a closed CR.
3. **G2 quote-verification in the validator** — mechanical gate.
4. **G3 retest playbook + lifecycle** — independent, high doctrine value.
5. **G5 chain-candidate persistence** — only if multi-session engagements
   prove to need it.

G1+G4+G2 are coupled and worth doing as one program; G3 stands alone;
G5 is deferred.
