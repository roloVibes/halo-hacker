# COMPATIBILITY.md — supported Halo versions and API requirements

## Current status

| Halo version | Support | Path |
|---|---|---|
| 3.0.x – 3.1.x (released) | Compat adapter only | `scripts/install-compat.sh` — bios/teams through `~/.halo/agents|teams/` |
| 3.2.0.0+ (pack registry, unreleased) | Native target | `halo pack install <this-dir>` once R1 ships |

## Interfaces the pack depends on (all verified against master @ 90cd137)

| Interface | Where | Status | Pack use |
|---|---|---|---|
| Agent bio YAML grammar | `halo_harness/agents_yaml.py` | stable (since 2.0.4 r4) | `agents/*.yaml` — every bio passes the REAL validator (pinned by `tests/test_pack.py::test_bios_pass_the_real_harness_validator`) |
| Team template grammar | `halo_harness/teams_yaml.py` | stable (since 2.0.6) | `teams/*.yaml` — same pin |
| Unknown top-level keys tolerated | `validate_agent_bio` | verified | the `hh:` pack-extension block round-trips untouched |
| User bios/teams dirs | `~/.halo/agents/`, `~/.halo/teams/` | stable | compat adapter install target |
| `halo teams use <name>` | `teams_cli.py` | stable | lineup activation |
| KNOWN_KINDS | main, subagent, researcher, judge, reviewer, custom, media | stable | role kinds in bios |
| Model refs | `default` or `<route>:<id>` | stable | pack hardcodes NO models (`default` everywhere) |

## Hard rules

- The pack never imports `halo_harness` internals at runtime; only the
  test suite does (compatibility pin, skipped loudly when no checkout).
- The pack never patches Halo files, never writes outside
  `~/.halo/{agents,teams}/` (adapter) or the future pack state dir.
- `models.preference` in shipped bios is `default` or absent — routing is
  the user's lineup decision, per the no-hardcoded-models rule. The
  validator enforces this mechanically.
