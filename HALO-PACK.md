# HALO-PACK.md: working on the Halo Hacker pack

You are working in the folder of a Halo pack. Read this page first, then follow its loop for every change. A person
reads it the same way. The full guide is Halo's `docs/PACK-AUTHORING.md`; the contract is `docs/EXTENSION_API.md`.

## What this pack is

`halo-hacker` (pack.yaml: `id`), "Halo Hacker": Authorized security assessment -- specialized agent roles,
assessment team lineups, structured playbooks, engagement scope policy, finding schemas, and evidence-driven
reporting.

**The repo root IS the pack.** `halo pack sources add https://github.com/roloVibes/halo-hacker` followed by
`halo pack install halo-hacker` reads `pack.yaml` at the repo root -- so nothing may be added above it that would
break that (no nested pack folder).

What it brings now (each part one line; pack.yaml lists them under `contributes`):

- bio `halo-hacker--hh-orchestrator` -- plans the assessment, picks the lineup and owns the engagement narrative
- bio `halo-hacker--hh-recon` -- surface mapping and target inventory
- bio `halo-hacker--hh-web-tester` -- web application testing
- bio `halo-hacker--hh-api-tester` -- API surface testing
- bio `halo-hacker--hh-ai-security-tester` -- AI/LLM surface testing (prompt injection, tool abuse, data exposure)
- bio `halo-hacker--hh-validator` -- independent reproduction of a candidate before it may be called confirmed
- bio `halo-hacker--hh-judge` -- reads the evidence chain and the reviewer decision; a second opinion, not a rubber stamp
- bio `halo-hacker--hh-reporter` -- confirmed-only reporting in the communicate-findings shape
- command `/halo-hacker` -- the entry command: what the pack is, its commands and lineups, and its default action
- command `/halo-hacker:hh` -- engage / status / disengage (scope as data, fail-closed inside the test window)
- command `/halo-hacker:hh-report` -- leadership email or full report, confirmed findings only
- skill `halo-hacker:communicate-findings` -- the baked-in reporting doctrine
- skill `halo-hacker:attack-flow` -- per-finding ATT&CK/ATLAS mapping, the narrative and a Navigator layer
- lineup `halo-hacker--hh-web-app-assessment` -- orchestrator, recon, web tester, validator, judge, reporter
- lineup `halo-hacker--hh-api-security-review` -- the same shape over an API surface
- lineup `halo-hacker--hh-ai-security-review` -- the same shape over an AI/LLM surface
- lineup `halo-hacker--hh-cloud-config-assessment` -- cloud configuration and posture review
- lineup `halo-hacker--hh-finding-validation-reporting` -- validation and reporting over another lineup's findings
- MCP server `ingest` -- knowledge ingestion into the provenance-ledger KB
- MCP server `cve` -- NVD 2.0 lookup, CISA KEV checks, FIRST EPSS scores
- event `hh.finding` -- one finding lifecycle moment, drawn in Studio's live feed
- Studio section `halo-hacker` -- the findings browser, the counts strip, the findings table and the lifecycle feed
- fleet capability `halo-hacker.assessment` -- runs an authorized assessment on a harness that runs the pack

## The contract in one page

- **pack.yaml** is the manifest. `id` is lower-case letters, digits and single hyphens, and is the folder's name.
  `version` is semver. `halo_api: {min: "1.1", max: "1.9"}` is the extension API it is written against.
- **contributes** lists every part. A bio or lineup file that is not listed is a doctor line; a listed file that is
  not there is an install line.
- **The plugin half** lives where a Claude plugin keeps it: `commands/`, `skills/<name>/SKILL.md`,
  `hooks/hooks.json`, `.mcp.json`, `.claude-plugin/plugin.json` (its `name` is the id). Halo reads them in place,
  named `halo-hacker:<name>`; a hook or a server command uses `${halo_python}` (Halo's own Python) and
  `${CLAUDE_PLUGIN_ROOT}` (this folder).
- **Halo's half**: bios in `agents/*.yaml` (read as `halo-hacker--<name>`), lineups in `teams/*.yaml`, workflows in
  `workflows/<name>.yaml`, typed events in `events/<kind>.json`, artifact schemas in `artifacts/<name>.json`, Studio
  panels, fleet capabilities, policy hooks and modes, Setup blocks, themes, a `bundle:` block, and the tools it needs
  under `requires:`.
- **`capabilities:`** is the vocabulary everything else gates on: every workflow's
  `prerequisites.capabilities`, every stage's `needs:`, and every `contributes.fleet.capabilities[].name` must be
  one of those names.
- **Code** imports `halo_harness.ext` and nothing else of Halo (`write_private`, `data_dir`, `publish_event`,
  `get_config`, `set_mode`, `testing`, ...).
- **Permissions**: each part that needs one (`hooks`, `mcp:<server>`, `studio-script`, `bash`, `network`,
  `home-write`) is requested in pack.yaml's `permissions`; the owner grants it with
  `halo pack enable halo-hacker --grant <name>`. Nothing that needs a permission runs until it is granted.

## The loop

```
halo pack test .                      # every check, in a scratch home, no model call, no network
python -m tests.pack_test             # the same checks plus the pack's own (needs `halo` importable)
~/.venvs/halo-hacker/bin/python -m pytest tests -q   # the behaviour tests (py3.12 -- never macOS python3)
halo pack doctor                      # the real home: what is missing on THIS machine
halo pack install . --link           # then enable it and start a NEW halo session (packs load at session start)
```

1. Change the pack. `pack.yaml` is the manifest: every file it names must exist, every permission a part needs must
   be in `permissions:`, and `contributes` is the list of what the pack offers.
2. Run `halo pack test .`. It must print `0 failed`. A `skip` line is a check that needs this machine (a model, a
   tool, a runtime) -- read the reason; a `skip` you cannot explain is a bug in the pack.
3. Run the pack's own tests (`~/.venvs/halo-hacker/bin/python -m pytest tests -q`) -- they cover the behaviour the standard checks
   cannot see.
4. Bump `version` in `pack.yaml` and add the same version to `CHANGELOG.md`. A change the person who runs the pack
   must act on also gets a `migrations` entry, which `halo pack update` prints before it replaces anything.
5. Commit. The GitHub workflow runs `halo pack test .` on Linux and Windows on every push.

## Rules this repo holds to

- **The repo is PUBLIC and ships EMPTY.** No corpus, no findings, no client data, no personal paths, ever. The vault
  is the user's own data and lives outside this repo. `halo pack test .` runs the privacy scan over every file; a
  hit is a failure, not a warning.
- **A finding is never `confirmed` without independent reproduction and a reviewer decision citing evidence.** That
  is structural (`schemas/finding.schema.json`), not a matter of discipline.
- **Never pin a model.** Every bio is `models.preference: default`; a test rejects any other value.
- **`_research/` is authoring notes**, not part of the pack's contract. It ships in this repo, so it must stay free
  of personal paths and client data too.
- **Harness facts come from GitHub, `roloVibes/Halo-Harness`** (or `halo pack --help` and the installed package),
  never from an assumption about what Halo does.

## Before you share it

`halo pack doctor` clean, `halo pack test .` green, the README true to the files, the permissions the least the
parts use, `CHANGELOG.md` and `version` moved together. Written against Halo 3.3.12.0 and the
[Halo pack template](https://github.com/roloVibes/halo-pack-template).
