---
name: communicate-findings
description: >-
  The pack's baked-in doctrine for communicating security findings: how to
  write the short leadership email and the full findings report so they are
  read, believed, and acted on. Distilled from SANS cybersecurity-writing
  training (Lenny Zeltser's threat-reporting and SEC402 material — see
  resources/SOURCES-comm.md). The reporter role consults this skill for
  EVERY outgoing artifact — email or report — and any role drafting
  finding prose runs its checklist before release.
license: All rights reserved — Pinball Genie LLC
metadata:
  author: rolo (roloVibes)
  version: "1.0"
  sources: resources/SOURCES-comm.md
---

# Communicating findings

Security writing fails for one root reason: the writer organizes what
they want to say instead of what the reader needs to know. Everything
below is that principle made mechanical.

## The reader model (assume this always)

- **Readers skim.** A busy executive reads the subject line, the first
  sentence of each paragraph, headings, and bullets — often nothing else.
- **~19 seconds of attention** before distraction. If they only ever see
  the title, they must still walk away with the key point.
- **Readers cannot judge technical quality**, so they judge surface
  clues. Sloppy formatting reads as sloppy analysis and voids your
  credibility.
- **Readers blame themselves for impenetrable writing** ("I'm not smart
  enough for this") and dismiss the report — they do not suspect the
  writing. Don't over-assume competence: state the IP, name the tool,
  spell out what the evidence means.

The consequence: certain surfaces are *preview surfaces* — subject line,
title, executive summary, headings, first sentences, bullet items, table
of contents. **Each must stand alone as a gist.** Seed every one with
the takeaway, because some reader reads nothing else. Zeltser calls this
"hacking the reader": finding where attention naturally lands and
delivering the message there.

## The ten rules (each fixes a classic mistake)

1. **Lead with the main point.** Never walk the reader through reasoning
   to a delayed conclusion. Move the conclusion to sentence one; it
   becomes a topic sentence. This is a structural flaw no automated
   checker catches — do it deliberately, at every level (sentence →
   paragraph → section → document → subject line).
2. **One idea per paragraph, short.** Split walls of text. Method: dump
   thoughts freely, cluster related sentences, make each cluster a
   paragraph with its summarizing sentence in front. More paragraphs =
   more topic sentences = more of your ideas reaching a skimmer.
3. **Graphics that explain at a glance, or none.** Three-second test: if
   a reader can't grasp it without effort, redesign it or use a table.
   Prefer bars over pies; label data directly, not via a legend hunt;
   full-sentence captions that state the conclusion; reference every
   graphic from the body text.
4. **Consistent formatting — it is not cosmetic.** Max two typefaces, two
   colors, one or two emphasis forms; uniform spacing; one spelling per
   tool name (defer to the vendor's); inspect pasted text for carried
   formatting. Deliberate emphasis is fine; random emphasis is the sin.
5. **Minimum words.** After drafting any paragraph, cut it by at least
   20% — the demonstrated cuts run 39–41% with no information lost.
   "When in doubt, cut it out." But never cut detail the reader needs;
   brevity is not omission.
6. **Parallel structure.** Every list item starts with the same word
   form — imperative verbs ("Confirm… Check… Use… Share…"). A mixed-form
   list is a staircase with one short step: readers trip. Applies to
   series inside sentences and to headings (don't mix sentence headings
   with fragment headings).
7. **No FUD.** Fear is specific and has a countermeasure; anxiety is
   vague and paralyzes. Name the concrete risk, why it matters to THIS
   reader, and the practical mitigation. Vague alarmism reads as vendor
   marketing and trains readers to ignore you (boy who cried wolf).
8. **Don't escalate tone.** Under frustration: state impact, specify
   what you need and by when, propose next steps; criticize actions, not
   people. Cool off five minutes before sending. If three emails go
   ignored, follow up in person or by phone — don't get louder in text.
9. **Detail goes to appendices.** Raw tool output, packet captures,
   request/response bodies, full logs: appendix, referenced from the
   body ("see Appendix B"). Never make the main narrative a proof-of-work
   display. Every included detail must answer a question the reader
   actually has.
10. **Credit and provenance.** Name who did the work — "the validator
    independently reproduced…" not "it was confirmed." Passive voice that
    obscures the actor undermines trust. Be explicit about reliability
    and uncertainty: honest caveats read as professionalism, not
    weakness.

## The four questions every findings artifact answers

1. What is it? (the vulnerability/threat — precisely)
2. What can it do? (capabilities, business impact)
3. What lets it succeed? (conditions, exposure, prerequisites)
4. What do we do about it? (countermeasures, remediation, the ask)

## The leadership email (short, senior audience)

Shape — five parts, nothing else:

1. **Subject = the takeaway.** "3 confirmed findings in the payment API —
   patching decision needed by Friday" — never "Assessment update #4".
2. **Opening paragraph = the whole story in 2–3 sentences.** What was
   found, in business terms, and what you're asking for.
3. **Impact.** What it means for the organization, concretely (data,
   money, compliance, downtime).
4. **The ask.** One clear, bounded recommendation with a decision or
   timeframe attached.
5. **Pointer.** Where the full report lives; offer to walk through it.

Hard rules: no introduction throat-clearing ("I wanted to reach out to
let you know…"), no FUD, no raw tool output in the body, bullets start
with verbs, one form of emphasis at most, strip paste artifacts, state
who confirmed each claim. Target: readable in under a minute; every
claim survives if ONLY the subject and first paragraph are read.

## The full report

- **Title = the finding.** "SQL Injection in /api/users Allows Full
  Database Exfiltration" — not "Vulnerability Report".
- **Executive summary on page one.** No decorative title page, no
  introduction section. If a title page is mandatory, the title itself
  states the most important finding.
- **Headings are complete sentences** ("The Application Fails to
  Sanitize User Input Before Database Queries") — the table of contents
  then reads as a summary on its own.
- **Per finding, one template, enforced:** finding title (parallel form
  across all findings, e.g. "Authenticated <vuln> in <component>") →
  summary → impact → conditions → remediation → references → evidence
  (appendix).
- **First sentence of every paragraph carries its point.**
- **Five golden elements, in priority order:** right structure, right
  look, right words (audience's jargon, no pretension — no
  "aforementioned"), right tone (urgent only when action is genuinely
  immediate; measured otherwise), right information (the four
  questions answered).
- **Confirmed-only.** Candidates and unreviewed findings never appear in
  outgoing artifacts — the finding schema enforces this; so does this
  skill.

## The pre-send checklist (run mechanically, every artifact)

- [ ] Subject/title states the takeaway alone
- [ ] First paragraph answers what/impact/ask
- [ ] Each paragraph: one idea, point first
- [ ] Every list parallel (same opening word form)
- [ ] Cut pass done (target −20%, no filler)
- [ ] No FUD words; every risk is specific + has a mitigation
- [ ] Every claim has a named actor (no actor-hiding passive voice)
- [ ] Uncertainty stated where it exists
- [ ] Raw evidence in appendices, referenced from the body
- [ ] Two typefaces / two colors / ≤2 emphasis forms; uniform spacing;
      tool names one spelling; paste artifacts stripped
- [ ] The four questions answered
- [ ] Only confirmed findings included

Even experts use checklists — surgeons do. The checklist is not an
insult; it is the discipline that makes the output reliable.

## Provenance

Original-prose distillation of SANS training material (Lenny Zeltser's
"Hack the Reader" CTI Summit talk, his SEC402 "Top 10 Writing Mistakes"
in two recordings, and the ten SEC402 companion shorts). Techniques,
rules, and worked examples only; nothing reproduced verbatim. Source
list with dates and IDs: [resources/SOURCES-comm.md](../../resources/SOURCES-comm.md).
