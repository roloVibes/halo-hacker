---
name: attack-flow
description: >-
  Map findings to MITRE ATT&CK / ATLAS techniques, present the holistic
  attack flow of an engagement (per-finding and all-findings views), and
  propose finding chains from capability tokens. The judge/reporter roles
  consult this when producing the attack-flow narrative; the validator
  tags technique_ids on every confirmed finding. Data comes from
  tools/mitre_view.py — ATLAS ships with the pack, ATT&CK caches on first
  use.
license: All rights reserved — Pinball Genie LLC
metadata:
  author: rolo (roloVibes)
  version: "1.0"
---

# Attack flow — ATT&CK/ATLAS mapping, holistic view, and chaining

## The data layer (always verify ids)

- `python pack/tools/mitre_view.py lookup <id>` — one technique, both
  frameworks. **Never cite a technique id you have not looked up.**
- `search <text> [--framework atlas|attack|both]` — find candidate ids by
  name.
- ATLAS (`AML.T####`) is shipped in the pack (`resources/atlas/atlas.json`,
  MITRE ATLAS 2026.10). ATT&CK (`T####`) caches on first use
  (`build-attack-index --yes`, ~53 MB one-time download); offline +
  uncached, ATT&CK queries fail gracefully — tag ATLAS where possible and
  leave ATT&CK tags for when the index exists.

## Per-finding mapping (validator + judge work)

1. For each finding, ask: what is the adversary DOING here (the technique),
   not just the bug class. A SQL injection is Data Manipulation /
   Exploit Public-Facing Application territory; an SSRF is often a pivot
   toward ML Model Access in AI systems (ATLAS).
2. Search by behavior keywords, verify the id with lookup, then record it
   in the finding's `technique_ids`. 1–3 ids per finding; precision over
   coverage. AI-stack findings should always consider the ATLAS matrix.
3. Technique tags ride the finding through the pipeline — they are display
   and analysis data, never evidence. They do not affect state.

## The holistic view (reporter work — "the attack flow")

Walk ALL confirmed findings on the engagement and produce one narrative an
executive can follow, tactic by tactic:

1. **Entry** — which findings demonstrate initial access / the entry surface.
2. **Movement** — what the findings, taken together, let an attacker reach
   that no single finding does (this is where chaining feeds in).
3. **Objective** — what the combined capabilities are FOR (data exfil,
   privilege, model abuse, persistence).
4. One line per finding, in the communicate-findings voice: complete
   sentence, point first, no FUD.
5. Export an **ATT&CK Navigator layer** (JSON: name, the engagement id,
   techniques: [{techniqueID, score=number of confirmed findings mapping
   it, comment=finding ids}]) as a report artifact — the standard artifact
   blue teams and leadership can open.

## Chaining findings (capability projection)

The finding model carries `requires` / `grants` capability tokens, and
attack paths are a PROJECTION over findings — never a stored graph.

1. **Mechanical pass**: enumerate grants/requires matches — finding A
   grants what finding B requires → chain candidate (A → B). Surface every
   match.
2. **Intelligence pass**: add ATT&CK/ATLAS context — chains usually cross
   tactics (entry → movement → objective); technique tags make the
   narrative legible.
3. **Lifecycle discipline**: a proposed chain is a CANDIDATE, like
   everything else. It enters the normal validate → judge gates, and
   DEMONSTRATING a chain is active testing — it runs under the engagement's
   approval gate. A chain that has not been demonstrated is labeled
   "projected, not demonstrated" in all outputs.
4. Confirmed chains become the spine of the holistic attack-flow view and
   the strongest part of the report.

## Rules

- Never cite an unverified technique id (lookup first, always).
- The holistic view includes CONFIRMED findings only — candidates may be
  mentioned as open questions, never as demonstrated steps.
- Chains: projected vs demonstrated is always labeled.
- The narrative follows the communicate-findings doctrine — the attack flow
  is a leadership artifact, not a scanner dump.
