# COMPATIBILITY.md — supported Halo versions and API requirements

## Current status

| Halo version | Support | Path |
|---|---|---|
| 3.2.0.0+ (pack registry, RELEASED) | Native only | `halo pack install <this-dir>` — validated 2026-10-25 against halo 3.2.1.0 (`problems: none`, installs clean, 8 bios + 5 lineups offered) and 2026-10-27 against halo 3.3.2.0 (ingestion MCP server, `mcp:ingest` permission and `vault` config key all recognized by `halo pack inspect`) |
| 3.0.x – 3.1.x | NOT supported | the pre-3.2.0.0 compatibility adapter was REMOVED 2026-10-27 — the manifest floor (halo ≥ 3.2.0.0) already excluded those versions |

## Interfaces the pack depends on (pack contract verified 2026-10-25 against halo 3.2.1.0 @ a7b2c15; bio/team grammar originally verified against master @ 90cd137; MCP wiring re-verified 2026-10-27 against halo 3.3.2.0)

| Interface | Where | Status | Pack use |
|---|---|---|---|
| Agent bio YAML grammar | `halo_harness/agents_yaml.py` | stable (since 2.0.4 r4) | `agents/*.yaml` — every bio passes the REAL validator (pinned by `tests/test_pack.py::test_bios_pass_the_real_harness_validator`) |
| Team template grammar | `halo_harness/teams_yaml.py` | stable (since 2.0.6) | `teams/*.yaml` — same pin |
| Unknown top-level keys tolerated | `validate_agent_bio` | verified | the `hh:` pack-extension block round-trips untouched |
| Pack manifest (`.mcp.json`, `pack.yaml` contributes/permissions/config) | `halo_harness/packs/` | stable (3.2.0.0+) | the ingestion MCP server (`mcp/ingest_server.py`), the `mcp:ingest` grant, the `vault` settings key |
| `halo_harness.ext.get_config` | extension API 1.0 | stable | the server reads `packs.settings.halo-hacker.vault` (falls back to `HALO_HACKER_VAULT`, then refuses) |
| `halo teams use <name>` | `teams_cli.py` | stable | lineup activation |
| KNOWN_KINDS | main, subagent, researcher, judge, reviewer, custom, media | stable | role kinds in bios |
| Model refs | `default` or `<route>:<id>` | stable | pack hardcodes NO models (`default` everywhere) |

Note on the MCP wire: the ingestion server is a hand-rolled stdio JSON-RPC
server (standard library only), like the one in Halo's own doc-review
template pack — it does NOT depend on the `mcp` SDK, whose 1.x→2.x
renamed `FastMCP` and broke pack servers that imported it.

## Hard rules

- The pack never imports `halo_harness` internals at runtime; only the
  test suite does (compatibility pin, skipped loudly when no checkout),
  and the MCP server's optional `halo_harness.ext` import is the
  documented extension API with a standalone fallback.
- The pack never patches Halo files, never writes outside the pack state
  dir (`~/.halo/packs/halo-hacker/`) or the vault the user points it at.
- `models.preference` in shipped bios is `default` or absent — routing is
  the user's lineup decision, per the no-hardcoded-models rule. The
  validator enforces this mechanically.
