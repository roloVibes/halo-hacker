# CLAUDE.md — halo-hacker dev context

You are working in the **halo-hacker repo** — the distributable
authorized-security-assessment capability pack for
[Halo Harness](https://github.com/roloVibes/Halo-Harness). Launch `halo`
here to develop the pack.

**Read `HALO-PACK.md` first** — it is the pack's own contract page (what the
pack is, the change loop, the rules). This file only adds repo-specific notes.

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

## The layout (pack at the repo root)

The repo root **is** the installable pack, so `halo pack sources add
https://github.com/roloVibes/halo-hacker` + `halo pack install halo-hacker`
works. Do not introduce a nested pack folder.

```
vibes/appDev/halo-hacker/       the pack (pack.yaml, agents/, tools/, mcp/, ...)
~/.venvs/halo-hacker/           the dev venv — OUTSIDE the pack, on purpose
~/halo-hacker-ops/              check_drift.py — OUTSIDE the pack, on purpose
```

A pack folder is scanned and copied whole by `halo pack test` / `halo pack
install` (only `.git` and `__pycache__` are skipped). Anything cache-shaped or
private inside it — a venv, a personal-path script — is copied into the install
and trips the privacy scan. Keep them out.

## The dev loop

```
halo pack test .                                       # must stay 0 failed (skips are fine, read them)
~/.venvs/halo-hacker/bin/python -m pytest tests -q     # the behaviour suite (py3.12 — never macOS python3)
halo pack inspect .                                    # must stay: problems: none
halo pack update halo-hacker                           # from vibes/appDev (the recorded source's parent)
start a NEW halo session                               # packs load at session start, never mid-session
```

- The installed pack's recorded source is **relative** (`./halo-hacker`): run
  `halo pack` commands from the directory holding the pack repos
  (`vibes/appDev`). It used to be `./halo-hacker/pack` — reinstall once after
  the root move.
- The vault for local testing: `HALO_HACKER_VAULT=<your-vault-dir>`
  (headless CLI needs the env var; the MCP server reads pack settings).
- Rollback an installed experiment: `halo pack rollback halo-hacker`.

## Where truth lives

- **Harness facts → GitHub, `roloVibes/Halo-Harness`** (fetch + read
  `origin/master:...`, or `gh`), or the installed package
  (`~/.local/share/uv/tools/halo-harness/lib/*/site-packages/halo_harness/`).
  NEVER the `appDev/Halo-Harness` folder — that is the PC's dev workspace, a
  partial synced snapshot that has already misled sessions. Do not modify,
  "clean up", or fast-forward either tree without asking.
- Pack contract: `COMPATIBILITY.md`, `docs/CORE_REQUESTS.md`
  (what harness surfaces exist vs are needed), and halo's
  `docs/EXTENSION_API.md` on GitHub.

## Never-do list

- `_research/` is committed dev planning; never move client-identifying or
  personal-path content into it (it ships).
- `check_drift.py` lives in `~/halo-hacker-ops/`, not here — a personal path
  inside the pack folder fails the privacy scan.
- No personal paths, client data, or rolo-identifying info anywhere in this
  repo — it is PUBLIC; leakcheck before every push.
- Fixture dates: never hardcode an engagement window. A shipped fixture that
  expires turns the pack's own tests into a time bomb (that is exactly what
  0.9.0 fixed). Derive the window from the clock, or make it deliberately wide.
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

- `HALO-PACK.md` — the pack contract page (read first)
- `docs/ENGAGE-MODE.md` — the `/halo-hacker:hh` engage design (scope as data)
- `docs/REPORTING.md` — findings view + selection → email/report
- `skills/communicate-findings/` — the baked-in reporting doctrine
  (kept in sync with serverMode's copy: change both together)
- `resources/SOURCES-comm.md` — provenance for the doctrine
