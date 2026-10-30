# CLAUDE.md — halo-hacker dev context

You are working in the **halo-hacker repo** — the distributable
authorized-security-assessment capability pack for
[Halo Harness](https://github.com/roloVibes/Halo-Harness). Launch `halo`
here to develop the pack; this file is the context that comes with the
folder.

## What this repo is (and is not)

- It is **the product**: methodology, schemas, ingestion engine, skills —
  the machine users install into their own halo. It ships **EMPTY**: no
  corpus, no findings, no client data, ever. The vault is the user's own
  data and lives OUTSIDE this repo (e.g. `~/halo-hacker-kb`).
- It is **not** an engagement workspace. Testing happens through a real
  install (below), never by running pack code against live targets from
  this folder.
- The private superset (overlay, engagements, client data) lives in
  serverMode and is never referenced from here.

## The dev loop

```
edit under pack/                      # pack/ is the installable unit
pytest pack/tests -q                  # .venv is py3.12 — always it, not macOS python3
halo pack inspect pack                # must stay: problems: none
halo pack update halo-hacker          # from vibes/appDev (the recorded source's parent)
start a NEW halo session              # packs load at session start, never mid-session
```

- The installed pack's recorded source is **relative** (`./halo-hacker/pack`):
  run `halo pack` commands from the directory holding the pack repos (`vibes/appDev`).
- The vault for local testing: `HALO_HACKER_VAULT=<your-vault-dir>`
  (headless CLI needs the env var; the MCP server reads pack settings).
- Rollback an installed experiment: `halo pack rollback halo-hacker`.

## Where truth lives

- **Harness facts → GitHub, `roloVibes/Halo-Harness`** (fetch + read
  `origin/master:...`, or `gh`). NEVER the `appDev/Halo-Harness` folder —
  that is the PC's dev workspace, a partial synced snapshot that has
  already misled sessions. Do not modify, "clean up", or fast-forward
  either tree without asking.
- Pack contract: `pack/COMPATIBILITY.md`, `pack/docs/CORE_REQUESTS.md`
  (what harness surfaces exist vs are needed), and halo's
  `docs/EXTENSION_API.md` on GitHub.

## Never-do list

- `_research/` stays local (dev planning; halo-re's precedent keeps such
  dirs unpublished content, but ours is committed — still: never move
  client-identifying or personal-path content into it).
- `scripts/check_drift.py` is gitignored on purpose — never re-add it.
- No personal paths, client data, or rolo-identifying info in anything
  under `pack/` — the repo is PUBLIC; leakcheck before every push.
- Never `halo pack install --project` for an id already installed
  user-scope — it clobbers the user state record (see knowledge base
  finding f-20261029-e5fca6).

## Sub-agent model rules (standing)

Quality-critical sub-agent work (distillation, doctrine, shipped code):
explicit Claude (`or:anthropic/claude-opus-4.8` / `-5`) or
`or:z-ai/glm-5.3-flash`. Vision (video/frames) → an Opus model. Local LAN
models: not trusted for quality-critical work. Judge landed output before
redoing — routing trust, not blanket re-runs.

## Key docs in this repo

- `pack/docs/ENGAGE-MODE.md` — the `/hh engage` design (scope as data)
- `pack/docs/REPORTING.md` — findings view + selection → email/report
- `pack/skills/communicate-findings/` — the baked-in reporting doctrine
  (kept in sync with serverMode's copy: change both together)
- `pack/resources/SOURCES-comm.md` — provenance for the doctrine
