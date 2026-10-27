# CORE_REQUESTS.md — Halo capabilities Halo Hacker needs that do not exist yet

Audited against Halo-Harness master @ 90cd137 (fetched 2026-10-21; the
local clone had been 444 commits behind before fetch). Each request cites
where the roadmap already promises it. Nothing here is implemented by
patching Halo internals; until a request ships, the pack stays without
that surface.

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

- **Status:** ROADMAP ONLY — 3.2.0.0 R3 (sections, panels, tabs, event
  renderers, artifact viewers loaded through a declared bundle; "no core
  file patched").
- **Needed by:** Phase 8 (the Engagements workspace, Roles pack grouping,
  Session assessment events, Orchestra visualization, Fleet badges).
- **Adapter shipped:** NONE, deliberately — the spec forbids private-Studio
  hacks. Studio surfaces stay empty until CR-2 lands.

## CR-3 — Fleet capability registration from packs

- **Status:** ROADMAP ONLY — 3.2.0.0 R4 (worker capabilities: tools,
  runtimes, environments, hardware, data locality).
- **Needed by:** Phase 9 (engagement-aware worker assignment, worker-side
  independent authorization).
- **Adapter shipped:** none. Phase 9 work is blocked on CR-3 by design.

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

- **Status:** NOT ON THE ROADMAP. Caido's local API surface (HTTP history,
  site map, request retrieval) has no Halo-side MCP integration, and the
  pack targets Caido via `tools/caido_adapter.py` (draft, read-only).
- **Needed by:** Phase 6 traffic analysis without export/import round trips.
- **Interim:** the adapter's normalization layer is fixture-pinned and the
  transport layer refuses to run unverified (fail loud, fail safe). A
  documented MCP interface, when available, replaces the transport only.
