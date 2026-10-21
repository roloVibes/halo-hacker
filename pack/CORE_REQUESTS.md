# CORE_REQUESTS.md — Halo capabilities Halo Hacker needs that do not exist yet

Audited against Halo-Harness master @ 90cd137 (fetched 2026-10-21; the
local clone had been 444 commits behind before fetch). Each request cites
where the roadmap already promises it. Nothing here is implemented by
patching Halo internals; until a request ships, the pack either ships a
clearly-labeled compatibility adapter or stays without that surface.

## CR-1 — The pack registry (`halo pack install|list|enable|…`)

- **Status:** ROADMAP ONLY — 3.2.0.0 R1 (plans/ROADMAP.md, added
  2026-10-21). No `halo_harness/ext/`, no `pack.yaml` loader, no pack CLI
  exists in any released Halo (current unreleased: 3.1.7.0).
- **Needed by:** the entire install/enable/disable/remove lifecycle.
- **Adapter shipped:** `scripts/install-compat.sh` /
  `uninstall-compat.sh` install the pack's bios/teams through the stable
  user directories (`~/.halo/agents/`, `~/.halo/teams/`), which all Halo
  surfaces (wizard Team step, `halo agents|teams`, Studio Roles) read
  natively. Namespaced `<pack>/<name>` ids degrade to `hh-` filename
  prefixes.
- **Removal condition:** delete both adapters the day `halo pack install`
  ships; `pack.yaml` already follows the R1 contract.

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
