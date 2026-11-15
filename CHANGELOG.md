# Changelog: Halo Hacker (halo-hacker)

Each release of the pack, newest first: the version (pack.yaml's `version`), the date, what changed for the person
who runs it. A change they must act on also gets a `migrations` entry in pack.yaml, which `halo pack update` prints
before it replaces anything.

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
