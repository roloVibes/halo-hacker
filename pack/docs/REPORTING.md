# REPORTING — findings visualization, selection, and leadership communication

Design note (2026-10-29, rolo + session). Status: PLANNED. Requirements
from rolo, verbatim intent:

- **Baked in** — the communication capability ships WITH the pack; no
  ingestion needed unless a user wants to add more.
- **Packs tab visualization** of findings: identified / reviewed /
  confirmed.
- **Select one or multiple confirmed findings** → send a **professional
  email, short and clear, intended for senior leadership**.
- Also generate a **fuller report** of the selected findings.
- The quality of the communication is driven by a **distilled
  communicating-findings guide** (SANS sources, see
  `resources/SOURCES-comm.md`) baked into the pack as a skill.

## What exists to build on

- The findings lifecycle is already enforced: candidate → validated
  (independently reproduced) → confirmed (reviewer decision citing
  evidence); the reporter drafts from **confirmed records only**
  (`pack/reporting/`).
- The pack schema (halo 3.2.0.0+ extension API 1.x) supports
  `contributes.studio`: **sections, panels** (kinds: markdown, table,
  form, links, events, bundle, artifact), palette actions, a config form,
  event lines. Panel sources can be pack files or `data:<path>` in the
  pack's data folder.
- Studio's files watcher re-reads panels when the session changes their
  source files — live updates with no new plumbing.
- The `studio-script` permission exists in the pack schema; its exact
  surface (what a pack script may do in Studio) must be verified against
  docs/EXTENSION_API.md on GitHub before relying on it.

## State mapping (display names)

| Finding state (schema) | Displays as | Meaning |
|---|---|---|
| candidate | **Identified** | a tester or scanner proposed it |
| validated | **Reviewed** | independently reproduced by the validator |
| confirmed | **Confirmed** | judge reviewed the evidence and confirmed |

## Component 1 — the findings view (Studio)

A pack-declared Studio presence (its own section, and/or panels targeted
at the Packs area where the pack is shown — exact placement per
EXTENSION_API.md):

- **Counts strip** (markdown panel): `12 identified · 4 reviewed ·
  2 confirmed` for the active or selected engagement.
- **Findings table** (table panel, `data:` source): id, title, severity,
  state, target, discovered, validated-by, evidence refs. Rows are live
  (files watcher).
- **Lifecycle feed** (events panel): the pack declares `hh.finding`
  events (mirroring halo-re's `re.finding` precedent) — every state
  change appears as it happens.

Data flow: the findings store (or the reporter role) writes a summary
JSON into the pack's data folder on every state change → panels read it.
No vault, no ingestion — pure pack data.

## Component 2 — selection → two outputs

**v1 (command-driven, buildable now):**

```
/hh report --findings HH-003,HH-007 --for leadership    → email draft
/hh report --findings HH-003,HH-007 --for full          → full report
/hh report --confirmed                                  → everything confirmed
```

The command validates every listed finding is `confirmed` (fail-closed —
candidates and reviewed-only findings cannot reach leadership), renders
both artifacts into the engagement directory, and returns paths.

**v1.5 (form panel):** a Studio form panel (kind: `form`) with a findings
multi-select (populated from the same data file), an audience picker
(leadership email / full report), and a Generate action — same
validation, same outputs.

**v2 (if `studio-script` allows):** native multi-select on the table
panel rows + a Send button. Blocked on verifying the studio-script
surface; not required for v1.

## Component 3 — the leadership email

Template driven by the baked-in communicating-findings skill. Shape
(distilled from the SANS sources):

1. **Subject**: what + where + urgency in one line, no FUD.
2. **Opening**: the main point FIRST — what was found, in business terms,
   one short paragraph. (Burying the main point is mistake #1.)
3. **Impact**: what it means for the organization, concretely.
4. **What we recommend**: the ask — one clear, bounded recommendation
   with a decision or timeframe attached.
5. **Where the detail lives**: pointer to the full report, offer to walk
   through it.

Hard rules from the guide, enforced in the template: minimum words, no
FUD/anxiety language, parallel structure, consistent formatting, credit
where due, no unexplained graphics.

**Delivery:** the pack GENERATES, it does not SEND. Default = `mailto:`
link (opens the user's own client with subject+body, zero credentials in
the pack). Optional: if the user has a mail MCP connector configured,
offer to send through it. The pack never holds SMTP credentials — a
deliberate security boundary.

## Component 4 — the full report

Per selected finding: title, severity, affected target, description,
business impact, evidence summary (ledger refs, sanitized), remediation
with effort estimate, references. Preceded by a one-page executive
summary (same discipline as the email). Generated from confirmed records
only, evidence refs resolved against the ledger (existing store
guarantee).

## Component 5 — the baked-in guide (no ingestion)

`pack/skills/communicate-findings/` — the distilled doctrine from the
SANS corpus (see `resources/SOURCES-comm.md` for the source list):
original prose, techniques and rules of thumb only, no verbatim
reproduction (the halo-re precedent for course-derived material). The
reporter role consults this skill when drafting ANY output — email or
report. Users who want more can ingest their own writing guides into the
vault; the baked-in baseline works out of the box.

## Build order

1. ~~The skill + sources~~ **DONE 2026-10-29** — `skills/communicate-findings/`
   (13 SANS sources distilled; provenance in `resources/SOURCES-comm.md`).
2. `/hh report` command + templates (extends `pack/reporting/`).
3. Counts + table + events panels, `hh.finding` events.
4. Form panel for selection.
5. studio-script verification → v2 select-and-send if the surface allows.
