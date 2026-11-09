# Changelog: Halo Hacker (halo-hacker)

Each release of the pack, newest first: the version (pack.yaml's `version`), the date, what changed for the person
who runs it. A change they must act on also gets a `migrations` entry in pack.yaml, which `halo pack update` prints
before it replaces anything.

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
