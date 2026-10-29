# ENGAGE-MODE — `/hh engage`: scope as data, not location

Design note (2026-10-29, rolo + session). Status: PLANNED — nothing here is
built yet. This is the agreed shape.

## The idea

serverMode's process is bound to a **folder launch** — the context boundary
*is* the directory. Engage-mode inverts that: the **engagement record**
(signed scope, window, accounts, rate limits — already a first-class pack
schema) becomes the boundary, and the process travels with the **pack**.
The pack is installed user-scope, so it runs from anywhere. Scope-as-data
beats scope-as-directory: stronger, and the only version that works for
other users.

## Commands

| Command | Does |
|---|---|
| `/hh engage <engagement-file>` | validate (fail-closed) → write active-engagement state → apply matching lineup → arm gates → print the engagement card |
| `/hh status` | engagement, window remaining, requests vs limits, findings by state, vault hits, gates armed |
| `/hh disengage` | disarm gates, restore previous lineup, write end-state (findings tally, ledger checkpoint), clear state |

Edge behavior: `/hh engage` while another engagement is active → refuse
(require disengage, or an explicit `--switch` that closes one and opens the
other with an audit line). Never two live engagements in one session.
Engagement window that expires mid-session → the hook starts refusing and
says why.

## The walkthrough (user experience)

1. **Launch — nothing special.** Any folder, plain `halo`. The pack is
   present but **passive**: no gates, no posture. Engaging is a deliberate
   act, not a side effect of the launch directory.
2. **`/hh engage engagements/acme.json`** — one command, one card (scope
   summary, window, accounts, limits, vault status), and the session is a
   security team under signed scope.
3. **While engaged:**
   - the action loop: threat-model → strike-check → knowledge lookup
     (vault via ingest tools, playbooks) → **[PROPOSAL] → HALT → "yes"**
     → execute → capture to engagement dir → log → chain-check. Never
     propose-and-execute in one turn.
   - every shell command crosses the pack hook: in-scope low-impact →
     runs, ledgered; in-scope above low-impact → approval required (the
     playbook schema itself refuses stages above low-impact without
     `requires_approval: true`); out-of-scope → refused, naming the
     violated scope line; rate limits enforced mechanically.
   - findings cannot skip the pipeline: tester candidates → independent
     validator → evidence-citing judge → reporter drafts from confirmed
     records only. Scanner output enters as candidates.
   - the KB is consulted with trust tiers (first-party = owned source;
     web = corroborating lead).
4. **`/hh disengage`** — normal session again; evidence and engagement
   tree stay on disk under the engagement's own directory.

## Runtime anatomy

| Piece | Executes it | When |
|---|---|---|
| `/hh` commands | pack-contributed command | on invocation |
| gates | pack hook (`hooks/hooks.json`, `${halo_python}`, reads the state file) | every tool call, while armed |
| team | halo lineups (pack bios/teams) | applied at engage, restored at disengage |
| KB | `mcp:ingest` server | queried during work |
| evidence | findings store + hash-chained ledger | every captured output |
| visibility | Studio panels + files watcher; TUI theme from config | live |

## Design invariants

1. **One state file, everything derived.** Command, hook, theme, panels all
   read the same active-engagement record. Arm, see it, get gates — or none
   of the above. No combination where visuals and enforcement disagree.
   (The flag-and-derived-guard-must-move-together rule.)
2. **Fail-closed engage.** No `/hh engage` without a signed, in-window
   engagement record — same pattern as the vault guard.
3. **Nothing resolves relative to cwd.** Engagement records, vault,
   output capture: absolute paths or pack-data locality (`locality:
   pack-data`). The engagement record names its own working directory.
4. **User-scope install only** for the anywhere-model (`--project` jails
   the pack to one directory).
5. **Pack loads at session start** — enable before launching, or restart.

## What needs upstream (filed when ready)

- CR-4 proper (tool-action broker: structured policy verdicts) — the
  pack-hook interim is the enforcement point; the broker is the end state.
- Studio **chrome** theming (red mode) — not declarable by a pack today;
  requirement to file into halo 3.3.7.0 "Themes and parity" while it is
  still malleable.
- CR-5 supervisor adapter (durable engagement workflows), CR-6 Caido
  interface.

Everything else in this document is buildable **today** with the shipped
pack surface: commands, hooks, lineups, MCP, Studio sections/panels
(markdown/table/form/links/events), artifacts, events.

## Relationship to serverMode

serverMode stays the private superset (smhh-* overlay, client data,
wired machines). Engage-mode is the productized subset — the process
without the private parts. Developing the pack still happens from the
repo folder (dev CLAUDE.md context); using it happens from anywhere.
