# TEST_RESULTS.md

## 2026-10-21 — Milestone 1 (pack 0.1.0)

Environment: macOS, Python 3.12.13 via uv (never the 3.9.6 system
python), pytest 9.1.1, PyYAML.

### Validator (exit-code gated)

```
$ uv run --python 3.12 --with pyyaml python tools/validate_pack.py
validated: 8 bios, 5 teams, 4 schemas
OK: pack is valid
$ echo $?
0
```

### Test suite: 14/14 PASSED

```
tests/test_pack.py::test_manifest_present_and_required_keys PASSED
tests/test_pack.py::test_all_bios_valid PASSED
tests/test_pack.py::test_all_teams_valid PASSED
tests/test_pack.py::test_no_hardcoded_models PASSED
tests/test_pack.py::test_every_bio_declares_the_full_role_contract PASSED
tests/test_pack.py::test_schemas_parse_as_json PASSED
tests/test_pack.py::test_validator_green_on_the_pack_itself PASSED
tests/test_pack.py::test_bad_kind_rejected PASSED
tests/test_pack.py::test_hardcoded_model_rejected PASSED
tests/test_pack.py::test_missing_hh_block_rejected PASSED
tests/test_pack.py::test_team_with_unknown_bio_rejected PASSED
tests/test_pack.py::test_team_without_main_rejected PASSED
tests/test_pack.py::test_bios_pass_the_real_harness_validator PASSED
tests/test_pack.py::test_teams_pass_the_real_harness_validator PASSED
14 passed in 0.46s
```

The last two are the compatibility pin: the pack's 8 bios and 5 teams
passed Halo-Harness's OWN validators (`agents_yaml.validate_agent_bio`,
`teams_yaml.validate_team_template`) against master @ 90cd137 — real
loader, not the mirrored grammar.

### Compat adapter, end-to-end in a sandbox HOME

- install: 13 files (8 bios, 5 teams) into `~/.halo/agents|teams/`,
  exit 0; validation runs first and a broken pack refuses to install
  (verified: with system python3 lacking PyYAML the script REFUSED with
  exit 1 before touching anything; fixed to use uv when present).
- uninstall: 13 removed, `find ~/.halo -type f` → 0 leftover files.
- repeat run without --force: SKIP on existing files (no user-modified
  overwrite), exit 0.

### Known gaps (tracked, not hidden)

- Live in-halo run (install on the real `~/.halo`, `halo teams use
  hh-web-app-assessment`, spawn a sub-agent) NOT yet exercised — the
  owner should run the adapter when he wants the lineup live.
- JSON Schemas validated as parseable JSON only; schema-level fixture
  validation (valid/invalid engagement + finding instances) arrives with
  Milestone 2 content.

## 2026-10-21 — Milestone 2 (pack 0.2.0)

### Validator (with jsonschema)

```
$ uv run --python 3.12 --with pyyaml --with jsonschema python tools/validate_pack.py
validated: 8 bios, 5 teams, 16 playbooks, 4 schemas
OK: pack is valid
exit 0
```

Playbook checks now enforced: schema conformance, id==filename, duplicate
ids, PLAYBOOK_CATALOG coverage, and the approval gate (any stage with
impact active/disruptive must set requires_approval: true).

### Test suite: 21/21 PASSED (was 14)

New M2 tests: all playbooks conform to the schema; playbooks never name
models/vendors; active stages require approval; the approval-gate
negative; valid fixtures pass their schemas; all four invalid fixtures
are REJECTED; the anti-glazing pin (a "confirmed" finding without
validation + reviewer_decision + evidence fails the schema).

```
21 passed in 0.53s   (Python 3.12.13, pytest 9.1.1, jsonschema)
```

### Leakcheck before publish (2026-10-21)

Scanned the full repo (own files, not .venv) for personal paths,
client/app names, identity strings, and secret patterns. Actions:
- scripts/check_drift.py excluded from the published repo (.gitignore) —
  it checks drift against the owner's private vault paths.
- PLAN.md sanitized: absolute home paths removed, "rolo" -> "the owner"
  in the distributed copy.
- finding.schema.json: a real finding slug from a past engagement
  replaced with a neutral example (xx-01-slug).
- No secrets, keys, or client-identifying content found anywhere else.
