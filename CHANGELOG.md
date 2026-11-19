# Changelog: Halo Hacker (halo-hacker)

Each release of the pack, newest first: the version (pack.yaml's `version`), the date, what changed for the person
who runs it. A change they must act on also gets a `migrations` entry in pack.yaml, which `halo pack update` prints
before it replaces anything.

## 1.2.0 - 2026-11-18

**Agentic-AI technique library, and the Bug Bounty panel stops crying wolf.**

- **New `resources/payloads/agentic-ai.json`** — a technique-indexed attack library for testing LLM applications and
  agents: 12 classes (direct override, separator spoofing, system-prompt extraction, encoding smuggling, indirect
  injection, multi-turn persistence, persona framing, tool-boundary escape, approval-policy manipulation,
  confirmation reuse, memory poisoning, cross-agent trust), 31 techniques, every payload a canary-templated test
  with its success signal and OWASP/ATLAS refs. Provenance in `resources/SOURCES-agentic-ai.md` — original prose
  distilled from public research (OWASP LLM Top 10, MITRE ATLAS, Rehberger, Greshake et al., Zenity Labs, Bargury).
- **Agents and playbooks wire it in.** `hh-prompt-injection` gains memory poisoning (with a fresh-session verification
  requirement); `hh-tool-abuse` gains the agentic trust plane: approval-policy manipulation, confirmation reuse,
  cross-agent trust. `discovery.llm-prompt-injection` 1.1 adds a memory-persistence stage; `discovery.llm-tool-boundaries`
  1.1 adds an approval-plane stage.
- **Bug Bounty panel: failed H1 AI checks read as what they are.** Raw Hai job names ("analyze_bug_class_completeness")
  rendered as red "Failed AI jobs" made HackerOne's own pipeline hiccups look like pack errors. The panel now shows
  human labels ("Bug-class completeness check"), says plainly these are HackerOne's checks on the intent, and tells
  you how to re-run them (edit and re-save the intent on H1).

## 1.1.1 - 2026-11-17

**Studio tab-bar overflow fix: 12 tabs -> 8.** The pack contributed one Studio tab per panel; with the two new
bounty panels the section bar ran off the browser. Merged the three redundant findings panels (Counts, Findings
table, Lifecycle — all already inside the findings browser) into it, and merged the two bug-bounty panels into one
tabbed "Bug Bounty" panel (Overview / Reports / Intents / Programs) with a horizontally-scrolling in-panel tab bar.
No feature lost; a regression test caps the panel count so the tab bar can't silently overflow again.

## 1.1.0 - 2026-11-17

**Bug bounty operations: a HackerOne dashboard, program browser, and AI-reviewed submission pipeline.**

- **New `h1` MCP server** — wraps the HackerOne Hacker API v1 (18 tools: reports, programs, structured scopes,
  weaknesses, balance/earnings/payouts, hacktivity, and the full report-intent lifecycle). Stdlib-only, HTTP Basic
  auth via the `h1_api_user` / `h1_api_token` config keys (or `H1_API_USER` / `H1_API_TOKEN` env), client-side rate
  pacer with one 429 retry, and the H1 quirk documented: nonexistent paths return 401, so the server never treats a
  bare 401 as proof of bad credentials.
- **`tools/h1_sync.py`** — normalizes captured API JSON into the pack data dir (`h1/reports.json`, `programs.json`,
  `earnings.json`, `intents.json`, per-report `report_details/<id>.json` with the full activity timeline). Detects
  report state transitions and new program activity between syncs and emits an `hh.h1.update` event (or queues to
  `h1/pending_events.json` when the harness isn't importable).
- **Two new Studio panels.** *Bug bounty* — stats strip (balance, earned, report states), an attention strip for
  what changed since last sync, the report-intent queue with H1's AI job status, and reports grouped by program with
  a click-through timeline (comments, bounties) plus a retest checklist on resolved reports. *Bounty programs* —
  your programs sorted by bounty earned, with scope and weakness viewers, and the public directory.
- **`hh-bounty-submit` agent + `/halo-hacker:hh-bounty` command** — takes a confirmed finding, drafts the report,
  runs it through H1's Report Assistant (report_intents) AI pipeline, surfaces the analysis, and submits only on
  explicit human approval. `sync`, `intents`, `submit`, `retest`, and `status` subcommands.
- **Verified live against a real account**: 22 reports, $500 earned, 9 report intents, per-program scopes and ROI
  all render correctly. 21 new tests (server, sync, panel CSP/syntax) plus a jsdom render harness.

## 1.0.7 - 2026-11-16

**Two live-use bugs found by actually exercising the pack on Halo 3.6.0.0, both fixed and regression-pinned.**

- **`kev_check` never worked — now it does.** The handler referenced the `any(...)` generator's loop variable
  outside its scope (`results.append(found_item)` after the generator had closed), so every online call raised
  `NameError` and the blanket `except` masked it as `{"ok": false, "error": "network"}` — a 100% silent failure
  that looked like CISA being unreachable. The result list is now built from an id-indexed dict, and a new test
  exercises the happy path (a known-exploited CVE and a non-KEV id through the real handler) so it can't regress
  behind offline-only coverage.
- **A missing local model no longer fails as N cryptic 404s.** The default distill lane points at
  `qwen3-coder:30b`; on a host without it, every document failed with a bare `HTTP Error 404: Not Found` and the
  batch reported N unrelated errors. The ingest tools now preflight the Ollama lane once (host reachable, model
  present) and refuse the whole call up front with an actionable message that names the available models and the
  `HALO_HACKER_MODEL` override.

## 1.0.6 - 2026-11-15

**The Studio section actually works, top to bottom.** Three panels that misbehaved on a fresh install now behave,
and the section reads in the order a tester uses it.

- **The Live panel renders.** Its `initialize()` wiped its own containers with `rootElement.innerHTML = ''` before
  `loadList()` looked them up by id — a successful fetch had nowhere to draw, so the panel sat on "Loading..."
  forever. The loading state now goes inside the sessions container.
- **Projects treats zero projects as empty, not an error.** `projects.json` is only written once the first project
  is created, so a fresh install returned HTTP 404 and the panel showed an error — and refired it on every
  live-update tick. A 404 now renders the normal "No projects yet" state, and a failing endpoint is retried by the
  Refresh/Retry button, not by every poll or SSE event.
- **The section reads in the order you use it.** A new **How this works** guide opens the section (step-by-step:
  enable and grant, set the vault, describe the engagement, then Live / Findings / Projects / Ingest / Attack
  paths); Settings & engagement is second (renamed from "Engagement setup" — a form panel always shows the whole
  settings schema, vault and proxy first, the engagement fields after), then Live, the findings panels, Projects,
  Ingest and Attack paths. The palette leads with the guide.

## 1.0.0 - 2026-11-14

**The team you compose.** Methodology became agents: 40 single-responsibility tester templates replace the 8
monolithic roles, so you compose a testing team per engagement instead of picking from a fixed lineup. Plus live
proxy traffic analysis, multi-project tracking for bug bounty workflows, real-time alerts, attack-path mapping, and
the findings review/judge pipeline, all in Studio. **Action required: reinstall** (halo_api floor is now 1.4, Halo 3.5+).

- **40 methodology agent templates** (`agents/hh-*.yaml`): one per testing technique — recon (subdomain, port, tech
  fingerprint, endpoint, parameter, content), auth/session (auth flow, session, JWT, OAuth, credential), injection
  (SQLi, XSS, command, SSTI, XXE, deserialization), business logic (IDOR, access control, race condition, payment,
  workflow), API (REST, GraphQL, rate limit, SSRF, CORS), AI/LLM (prompt injection, tool abuse, data exposure, model
  manipulation), infrastructure (cloud, CI/CD, network), and the review pipeline (validator, judge, communicator,
  traffic analyst) plus coordination (manager, reporter). Each is a Builder starting point — `is_template: true`,
  `models.preference: default`, never a pinned model.
- **5 pre-built workflows** (`workflows/*.yaml`): web-app-assessment, api-security-review, ai-security-review,
  bug-bounty-hunt, and pack-dev. Every one flows candidates through independent validation → judging before anything
  may confirm. `builder-hints.yaml` maps natural language ("make me an agent that tests for IDOR") to the right
  template so the 3.6 Builder can draft from them.
- **Real-time proxy traffic analysis** (MCP server `traffic`): `traffic_start` / `traffic_stop` / `traffic_status` /
  `traffic_candidates` / `traffic_suggest`. Wraps the passive traffic observer with a stateful stdio server and a
  correlation engine (parameter reuse, auth-boundary crossings). Runs as a pack service (`traffic-watch`).
- **Multi-project tracking** (`tools/project_manager.py`, `/halo-hacker:projects`, Studio Projects section): bug
  bounty hunters can jump between programs; each has its own findings, evidence, and state. The active project is
  what the whole cockpit renders.
- **Engagement setup** (Studio Engagement section): objective, scope, test type, rules of engagement, X-header for
  traffic marking, test window, and tester name/email — persisted per project.
- **Live agent dashboard** (Studio Live section, `tools/live_view.py`): every live session with status and cwd, the
  live-lines feed, and traffic-watch status, SSE-updated.
- **Ingest visualization** (Studio Ingest section, `tools/ingest_view.py`): source breakdown, trust tiers, topic
  routing to testing lanes, and a recent-ingest log.
- **Findings review/judge pipeline** (Studio Findings section, upgraded): a per-finding pipeline stepper (Identified →
  Under review → Validated → Judged → Confirmed → Reported), filter presets (needs review / needs judgment /
  confirmed), the existing validator verdict + judge decision + evidence chain.
- **Attack paths** (Studio Attack Paths section, `tools/attack_path_graph.py`): findings as a graph connected by
  requires/grants capability tokens — demonstrated (solid) vs projected (dashed) paths — plus MITRE ATT&CK/ATLAS
  technique mapping.
- **Real-time alerts** (5 `hh.alert.*` attention kinds): critical finding, traffic hit, playbook limit, scope
  boundary, and agent suggestion, each with its own action keys, plus 6 event kinds with schemas and sample fixtures.
- **170 behaviour tests** green, including new coverage for the traffic MCP, the data-layer tools, and the
  template/workflow/builder-hints consistency gate.

## 0.9.0 - 2026-11-08

**Framework conformance.** The pack now uses the Halo pack template
(https://github.com/roloVibes/halo-pack-template) end to end. **Action required: reinstall.**

- **The repo root is now the pack.** The installable unit moved from `pack/` to the repository root, so
  `halo pack sources add https://github.com/roloVibes/halo-hacker` + `halo pack install halo-hacker` works. An
  existing install recorded from `./halo-hacker/pack` must be updated or reinstalled once; the recorded source
  changes with it.
- `pack.yaml`: `halo_api` is now a `{min, max}` range (1.1 - 1.9) and `halo.min` is `3.3`; `capabilities` lists the
  pack's fleet capability; `contributes.fleet` declares `halo-hacker.assessment`; `contributes.commands` is
  declared. Everything else the pack contributes is unchanged.
- The template's project files are in place: `HALO-PACK.md` (how to work on the pack), `CHANGELOG.md`, `tests/`
  (the pack's own test entry plus the samples its event schema is exercised against), `.claude-plugin/plugin.json`,
  `.gitattributes`, and `.github/workflows/pack-test.yml` (`halo pack test .` on Linux and Windows per push).
- `/halo-hacker` entry command added -- what the pack is, its commands and lineups, and its default action.
- `/halo-hacker:hh` added. Engage/status/disengage was described in the README and the skills but had no command;
  it now wraps `tools/engage.py` instead of being prose.
- `fleet/notes.md` -- one line per part and what it needs on the harness that runs it.
- Privacy: the example and test fixtures no longer carry values the pack's own privacy scan flags (a placeholder
  email, LAN addresses, token-shaped strings). The fixtures were always synthetic; the scan is now clean.
- The pack's own test suite no longer time-bombs: its engagement fixtures used a hardcoded test window that expired
  on 2026-11-04, which turned 39 behaviour tests into failures. The fixtures now derive their window from the run.

## 0.8.0 - 2026-10-29

- Studio findings browser: every finding clickable (full detail, evidence, validation, reviewer decision), filters,
  search and live refresh; the counts strip, findings table and lifecycle feed read the pack's data folder.

## 0.7.1 - 2026-10-27

- Passive traffic observer: while a human tester works through Caido or Burp, the pack reads their proxy traffic
  read-only and surfaces candidate findings as they test. Scope-gated, redacted, deduped; never sends anything.

## 0.7.0 - 2026-10-26

- Reporting and engage-mode wave: `/hh-report`, the report engine, the findings view, and engagement control with
  the scope guard hook.

## 0.6.0 - 2026-10-21

- `communicate-findings` skill (the baked-in reporting doctrine), plus the engage-mode and reporting design notes.
