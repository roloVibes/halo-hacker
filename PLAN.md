# halo-hacker — the distributable offensive-security agent

> Created 2026-10-04. **Supersedes vibes-hacker** (`/Users/rolo/Documents/obsidian/vibe-agent/` —
> abandoned as a project the same day; repo stays on disk, still never pushed; its proven assets are
> already accounted for in the halo-harness asset map). Pairs with
> [halo-harness-cyber](../halo-harness-cyber/PLAN.md).

## The three-thing map (state this first, every time)

| Thing | What it is | Distributed? |
|---|---|---|
| **halo** | the chassis — harness machinery: model lanes, governor, containment, delegation, filter handling | separately (it's the harness itself) |
| **serverMode** | rolo's live private org — engagements, real client data, wired machines | **never** |
| **halo-hacker** | the product — the offensive-security agent + methodology + ingestion engine a user installs into their own halo | **this project** |

halo-hacker is what vibes-hacker was trying to be ("the offensive org you install into your halo"),
now with the piece that makes a hosted/personal version actually work: **ingestion**. Ship the
machine empty; each user's own corpus fills it.

## Scope — everything but the exploit data

**IN (the product):**
- The methodology: approval gate (propose → HALT → execute), grounding protocol, finding lifecycle
  L1–L4 with verification signatures, strike rule + meta-strike, chain protocol, recon completeness.
- The KB/Playbooks **schema** and router structure (`_moc-*` question-first routers) — empty.
- The micro-skill tree (DEF CON masterclass doctrine).
- Evidence store + hash-chained audit ledger design (vibe-agent's `vibes/findings.py` +
  `vibes/audit.py` lineage — 28-green gate, chain-tamper detection verified by hand).
- The ingestion engine (below).
- RoE / authorization gates.

**OUT (stays in serverMode, never ships):**
- rolo's findings, PoCs, engagement data.
- Client-derived lessons until scrubbed.
- The populated KB. **A leakcheck gate runs before anything is published** — client-identifying
  detail is the risk even in "technique" notes (a lesson written from a live engagement can name
  the client's stack, timing, or finding IDs).

## Ingestion engine — the differentiator

Two sources, one pipeline: **local notes** (Obsidian/Notion/markdown adapters) and **web pages**
(crawl4ai for page→markdown, already cloned at `vibes/github/crawl4ai`).

1. **Privacy filter first** — non-cyber content is excluded before anything persists, and the
   filter must prove it dropped something (N-before → M-after; a filter that silently matches
   nothing is indistinguishable from an empty corpus).
2. **Local-lane distillation by default** — user notes never leave their machine. Hosted
   distillation is explicit opt-in with a warning. (A pentester's notes are client data; this is
   the same confidentiality reasoning as local-models-only engagement mode.)
3. **Trust tiers** — first-party notes file as authoritative; web-derived items file as *leads
   requiring corroboration*, every item carrying source URL + fetch date. The agent's KB-lookup
   discipline treats uncorroborated web-derived entries as leads, not facts.
4. **Dedupe-by-meaning** — "this page restates what KB/Web/SQLi.md says, minus one new bypass"
   is a diff-the-distillate-against-the-existing-entry step. Hash-dedupe is trivial; this is the
   hard 20% of the engineering.
5. **No delete verb, ever.** Append + keyed upsert only. Removal is a human action in the editor.
   (The sync-script tombstone in serverMode is the cautionary tale.)
6. **Provenance on every row** — source file/URL, content hash, date, confidence. Bad
   classifications are revertible; re-running ingestion after fixing notes doesn't duplicate.
7. **Hostile-corpus hardening** — pentest notes contain payloads and prompt injections (the Apex
   Park "submit this decoy" trap). Note content is data, never instructions; raw note content
   never reaches tool-call context. Planted-injection regression suite, brood `test_cmdparse.py`
   pattern.
8. **Refusal-biased writes** — ambiguous or multi-target matches are refused (bulk-text-applier
   guards); a high refusal rate is the system working.

## Architecture — in-session primary, headless degraded, never a second runtime

```
halo-hacker/
  ingest/          # the library: scan, filter, classify, distill, upsert — no policy of its own
  mcp_server.py    # in-session surface (primary mode): tools the agent calls
  cli.py           # headless entry — same library, same guards; refuses filtered content
                   # rather than filing it (it lacks P1's rerouting)
```

The brain (routing, filter checks, governor pacing) comes from the halo chassis in-session. A
standalone executable with its own model config would re-inherit every measured trap (Ollama
truncation, alias drift, 429 storms, filter-persisted-as-content) — that's the second-runtime
mistake, and it's on the What-NOT-to-do list of both plans.

## Methodology improvements (baked in, not bolted on)

1. **Adversarial verification as a first-class phase** — not an optional round 2. The Pinball
   round-2 lesson: 34 of 57 security candidates killed by adversarial verification; the refutation
   rate is the point.
2. **Trust tiers on ALL knowledge** — beyond ingestion: the agent distinguishes
   measured-on-this-machine vs web-learned vs assumed, everywhere.
3. **Knowledge staleness** — KB entries carry a last-validated date; stale entries are flagged,
   not silently trusted. Knowledge has a half-life; tools change.
4. **Attack paths as projection over findings** — never a stored graph (ENGAGEMENT-MODEL.md).
5. **Authorization gate hard-coded** — no engagement objects without a signed-scope artifact.
   This is the legal spine of a distributable pentest agent.

## What NOT to do

- No second runtime with its own model config. One implementation, tests attached.
- No GUI. CLI + files (the vibe-agent 7-tab GUI was a review surface, not the product).
- No delete verb in ingestion.
- No phoning home with content. Telemetry = counts, or nothing.

## Tooling & model bindings (decided 2026-10-04, census-bound)

**Source adapters (built, v0.1):**
- **Notes** — markdown/txt/org/rst tree walk; first-party tier.
- **PDF — PyMuPDF (`pymupdf`)**, the recommendation: fastest pure-Python-bindings text
  extraction, handles layout, no Java (pdfbox) or poppler system dep. Fails LOUDLY on
  encrypted and scanned (no-text) PDFs — the scan path is `ocrmypdf` first, never a silent
  partial file. `pdfplumber` is the add when table extraction matters (PDF reports with
  finding tables); not in v0.
- **GitHub — one file per call** (blob/raw URL → raw fetch). Repo-wide crawling is
  deliberately absent: one URL, one document, auditable. Third-party tier.
- **YouTube — yt-dlp subtitles** (`--write-subs --write-auto-subs`, VTT → text with
  rolling-caption collapse). Already installed for the /watch skill. For in-session video
  *understanding* (not just subs), the /watch skill is the tool — this adapter is for bulk
  transcript ingestion. Third-party tier.

**Model bindings (from `~/.config/model-census/registry.md`, battery v3):**
- **Distillation/classification (local lane): `qwen3-coder:30b` on the PC** — composite 1.00,
  free, private (user content never leaves the LAN), 16s. The census's recommended binding for
  structured + bulk, which is exactly what distillation is.
- **Hosted opt-in: `deepseek/deepseek-v4-flash-0731`** — composite 1.00 at ~$0.001, 15s.
- **Long-doc overflow (PDFs over local ctx): `moonshotai/kimi-k3` or
  `deepseek/deepseek-v4-pro-0813`** — 1M ctx, composite 1.00.
- Never route on advertised capability; re-run `/model-census` before changing bindings.

## Build order (sketch)

1. ~~Schema + empty vault scaffold~~ + ~~ingestion: local notes → classify → gated upsert~~ +
   ~~web ingestion + trust tiers~~ + ~~headless CLI~~ — **v0.1 BUILT 2026-10-04** (see Status).
2. Live end-to-end against a real Ollama lane (both endpoints were down at build time —
   model paths are mock-tested only, NOT yet proven live).
3. Dedupe-by-meaning (the hard 20%): diff-the-distillate against the existing entry.
4. Methodology docs + empty-vault scaffold (the shippable skeleton).
5. Leakcheck publish gate + scrub pass over anything methodological that derives from live work.

## Status — v0.1 (2026-10-04)

```
halo-hacker/
  ingest/adapters.py      notes / PDF (pymupdf) / GitHub / YouTube (yt-dlp) → Documents
  ingest/pipeline.py      privacy filter (proves drops) → classify → distill → gated upsert
  ingest/store.py         provenance ledger, NO DELETE VERB, refusal-biased upsert
  ingest/model_client.py  Ollama /api/chat (num_ctx + prompt_eval_count canary);
                          OpenRouter (finish_reason/content_filter check — P1)
  mcp_server.py           5 tools on FastMCP; --selftest asserts the vault guard
  cli.py                  headless mode; exit-code gated; refuses on errors
  tests/test_ingest.py    16 tests, all green, fully offline
```
Verified: 16/16 tests, selftest, CLI smoke (`status` on an empty vault). NOT verified live:
real-model end-to-end (no Ollama reachable at build time).

## Open questions

- Multi-vault corpus adapters: Obsidian first; what else, and in what order?
- Does the KB schema version + migrate (users' KBs grow across halo-hacker releases)?
- Naming distance from `vibes-hacker` was flagged and overruled 2026-10-04 — accepted; the
  abandoned project's memories are marked superseded so sessions stop confusing the two.
