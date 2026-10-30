# CORE_REQUESTS.md — Halo capabilities Halo Hacker needs that do not exist yet

Audited against Halo-Harness master (re-verified 2026-10-29 against the
shipped pack schema + installed halo 3.3.4.0; first audit was master @
90cd137, 2026-10-21). Each request cites where the roadmap promises it.
Nothing here is implemented by patching Halo internals; until a request
ships, the pack stays without that surface.

## CR-1 — The pack registry (`halo pack install|list|enable|…`)

- **Status:** SHIPPED — halo 3.2.0.0 R1 (validated against the shipped
  `halo pack` implementation in 3.2.1.0 on 2026-10-25; current halo runs
  the full lifecycle: install/enable/grant/update/rollback/remove).
- **Needed by:** the entire install/enable/disable/remove lifecycle.
- **Pack state:** native install is the only path
  (`halo pack install <repo>/pack`); the pre-3.2.0.0 compatibility adapter
  (`pack/scripts/install-compat.sh`) was REMOVED 2026-10-27 per its own
  removal condition — the manifest's floor (halo ≥ 3.2.0.0) already
  excluded the versions it served.

## CR-2 — Studio contribution registry

- **Status:** SHIPPED (declarative surface) — 3.2.0.0 R3, verified against
  the pack schema on current master (2026-10-29): `contributes.studio`
  accepts **sections** (a pack's own Studio sections, placed after
  Orchestra), **panels in core sections**, palette actions, a config form,
  event lines and attention rows. Panel kinds: `markdown`, `table`,
  `form`, `links`, `events`, `bundle`, `artifact`; sources are pack files
  or `data:<path>` in the pack's data folder. A `studio-script` permission
  exists in the schema (its exact surface still needs verification against
  docs/EXTENSION_API.md).
- **Needed by:** Phase 8 (the Engagements workspace, Roles pack grouping,
  Session assessment events, Orchestra visualization, Fleet badges).
- **Adapter shipped:** none yet — the pack's findings-view panels are in
  the build queue (docs/REPORTING.md). The discipline holds: declarative
  panels only, rendered by Studio's own components, no private-Studio
  hacks.
- **Still open (honest gaps):** interactive master-detail (row
  click-through to a detail view) is NOT confirmed for declarative table
  panels — verify before promising click-into-finding UX; `studio-script`
  capabilities unverified; pack-declared chrome/posture theming does not
  exist (see the 3.3.7.0 "Themes and parity" ask).

## CR-3 — Fleet capability registration from packs

- **Status:** SHIPPED (declarative surface) — 3.2.0.0 R4, verified against
  the pack schema on current master (2026-10-29): `contributes.fleet`
  accepts **worker capabilities** (name, description, `requires`: tools /
  runtimes / platform / hardware / models / grants / locality, plus
  `capacity.parallel`), **mission inspector lines**, and **mission
  metadata**.
- **Needed by:** Phase 9 (engagement-aware worker assignment, worker-side
  independent authorization).
- **Adapter shipped:** none yet — declaring the pack's assessment-worker
  capabilities is in the build queue.

## CR-4 — Tool-action broker hook (pre-tool-call enforcement point)

- **Status:** NOT ON THE ROADMAP in pack form. Halo has permission rules
  (deny/ask lists) per bio/team, and the Governor for rate pacing, but no
  hook where a pack can validate a tool call against engagement policy
  (scope, window, rate, activity class) before execution, enforced
  independently of the model.
- **Needed by:** Phase 5 (the Security Tool Broker). This is the legal
  spine of the pack: deny-by-default scope enforcement the LLM cannot talk
  its way past.
- **Interim:** bios carry `tools.rules` deny-lines mirroring the policy,
  and the roadmap's R5 `tools.capabilities` (declared capability lists)
  covers part of the need. Prompt wording is NOT relied on as enforcement
  (Phase 11 rule) — until CR-4 exists, active-validation stages are
  human-gated in the playbook schema itself (`requires_approval: true` is
  the default for any stage above low-impact).

## CR-5 — Persistent supervisor API

- **Status:** ROADMAP — 3.1.8.0 R1 (the supervisor, added 2026-10-20).
- **Needed by:** Phase 10 (durable assessment workflows).
- **Adapter shipped:** none; Phase 10 waits.

## Requested additions for the R1 contract review

None beyond the above. The manifest fields 3.2.0.0 R1 specifies (id,
namespace, halo_api, contributions, permissions.requested, migrations)
are sufficient for everything Halo Hacker ships in Milestones 1–4.

## CR-6 — Documented Caido MCP/API interface

- **Status:** CLOSED 2026-10-30 — an MCP interface exists:
  **github.com/roloVibes/caido-mcp-extended** (verified live against Caido
  on macOS 2026-10-29: token extraction, GraphQL, 25-tool stdio server)
  — and as of `85a9f52` it also carries **Burp Suite support** (REST scan/
  issues/proxy-history tools, hard ceilings documented, `burp_status`
  always registered). It stays a SEPARATE repo: it is a Node/TypeScript
  server, deliberately outside the pack's stdlib-Python convention.
- **Needed by:** Phase 6 traffic analysis without export/import round trips.
- **Pack posture:** wire it as a user-side MCP server when doing live
  traffic work; the pack's `tools/caido_adapter.py` remains the
  read-only normalization + redaction layer (fixture-pinned, transport
  fail-loud until verified live per engagement).
