#!/usr/bin/env python3
"""Halo Hacker pack validator.

Validates the pack against (a) the Halo 3.2.0.0 R1 pack.yaml contract as
documented in the harness roadmap and (b) the Halo agent-bio / team-template
YAML grammar as implemented in halo_harness/agents_yaml.py +
teams_yaml.py (mirrored here field-for-field so validation works without a
harness checkout; tests/test_pack.py ALSO runs the real harness validators
against this pack when a checkout exists).

Exit code is the gate: 0 = valid, 1 = any problem (one plain line each).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

PACK_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_REQUIRED = ("id", "namespace", "name", "version", "description",
                     "author", "license", "halo_api", "capabilities",
                     "requires", "contributions")
# Mirrored from halo_harness/agents_yaml.py (verified 2026-10-21 against
# master 90cd137).
BIO_SECTIONS = ("models", "tools", "context", "limits", "output",
                "environment", "acceptance", "hooks", "schedule", "triggers")
KNOWN_KINDS = ("main", "subagent", "researcher", "judge", "reviewer",
               "custom", "media")
# Halo model refs: a route prefix (or:, ol:, xp:, hf:, dbx:, oai:, ...) or
# the literal `default` (session model). The pack hardcodes nothing.
MODEL_REF_OK = re.compile(r"^(default|[a-z]{2,}:.+)")

HH_REQUIRED = ("responsibility", "boundaries", "inputs", "outputs",
               "evidence_requirements", "completion_criteria")

ACTIVITIES = {"read-only-analysis", "traffic-review", "code-review",
              "config-review", "low-impact-validation", "active-validation",
              "disruptive-testing"}

problems: list[str] = []


def p(msg: str) -> None:
    problems.append(msg)


def load_yaml(path: Path) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        p(f"{path.name}: YAML parse error: {e}")
        return None
    if not isinstance(data, dict):
        p(f"{path.name}: top level must be a YAML mapping")
        return None
    return data


def validate_manifest() -> dict | None:
    m = load_yaml(PACK_ROOT / "pack.yaml")
    if m is None:
        return None
    for key in MANIFEST_REQUIRED:
        if key not in m:
            p(f"pack.yaml: missing required key {key!r}")
    halo_api = m.get("halo_api")
    if not isinstance(halo_api, dict) or "min" not in halo_api:
        p("pack.yaml: halo_api must be a mapping with at least 'min'")
    else:
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", str(halo_api.get("min", ""))):
            p("pack.yaml: halo_api.min must be a Halo four-part version")
        mx = halo_api.get("max", "")
        if mx and not re.match(r"^\d+\.\d+\.\d+\.\d+$", str(mx)):
            p("pack.yaml: halo_api.max must be a four-part version or empty")
    if m.get("id") != "halo-hacker":
        p("pack.yaml: id must be 'halo-hacker'")
    if m.get("namespace") != "hh":
        p("pack.yaml: namespace must be 'hh'")
    return m


def validate_bio(path: Path) -> dict:
    data = load_yaml(path) or {}
    if path.stem != data.get("name"):
        p(f"{path.name}: bio 'name' ({data.get('name')!r}) must match filename stem {path.stem!r}")
    kind = data.get("kind")
    if kind not in KNOWN_KINDS:
        p(f"{path.name}: kind {kind!r} not one of {', '.join(KNOWN_KINDS)}")
    for section in BIO_SECTIONS:
        if section in data and data[section] is not None and not isinstance(data[section], dict) \
                and section != "triggers":
            p(f"{path.name}: {section!r} must be a mapping")
    models = data.get("models") or {}
    pref = models.get("preference") if isinstance(models, dict) else None
    if pref is not None and not MODEL_REF_OK.match(str(pref)):
        p(f"{path.name}: models.preference {pref!r} is neither 'default' nor a route ref -- the pack hardcodes no models")
    if pref is not None and str(pref).startswith(("cc:", "cx:")):
        p(f"{path.name}: models.preference {pref!r} uses a removed/consent-gated route")
    hh = data.get("hh")
    if not isinstance(hh, dict):
        p(f"{path.name}: missing 'hh:' pack-extension block")
    else:
        for key in HH_REQUIRED:
            if key not in hh:
                p(f"{path.name}: hh.{key} is required")
    return data


def validate_team(path: Path, bio_names: set[str]) -> None:
    data = load_yaml(path) or {}
    if path.stem != data.get("name"):
        p(f"{path.name}: template 'name' ({data.get('name')!r}) must match filename stem {path.stem!r}")
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        p(f"{path.name}: 'agents' must be a non-empty list")
        return
    main_count = 0
    aliases: set[str] = set()
    for i, entry in enumerate(agents):
        if not isinstance(entry, dict):
            p(f"{path.name}: agents[{i}] must be a mapping")
            continue
        name = entry.get("agent")
        if not name:
            p(f"{path.name}: agents[{i}]: 'agent' is required")
        elif name not in bio_names:
            p(f"{path.name}: agents[{i}]: no such agent bio: {name!r}")
        role = entry.get("role")
        if not role:
            p(f"{path.name}: agents[{i}]: 'role' is required")
        elif role == "main":
            main_count += 1
        alias = entry.get("as")
        if alias:
            if alias in aliases:
                p(f"{path.name}: duplicate alias {alias!r}")
            aliases.add(alias)
        for key in ("models", "tools", "limits", "hooks"):
            if key in entry and entry[key] is not None and not isinstance(entry[key], dict):
                p(f"{path.name}: agents[{i}]: {key!r} override must be a mapping")
    if main_count != 1:
        p(f"{path.name}: exactly one agents[] entry must have role: main (found {main_count})")
    routing = data.get("routing") or {}
    if isinstance(routing, dict):
        for kind, target in routing.items():
            if target not in aliases and target != "orchestrator":
                p(f"{path.name}: routing.{kind} names an unknown alias: {target!r}")


def validate_playbooks() -> "tuple[int, set[str]]":
    """Validate every playbook against schemas/playbook.schema.json when
    jsonschema is importable; without it, structural checks only (the
    test suite always runs the full schema validation)."""
    pb_dir = PACK_ROOT / "playbooks"
    ids: set[str] = set()
    files = sorted(pb_dir.glob("*.yaml"))
    schema = None
    try:
        import jsonschema  # noqa: F401
        schema = json.loads((PACK_ROOT / "schemas" / "playbook.schema.json").read_text())
    except ImportError:
        pass
    for path in files:
        data = load_yaml(path) or {}
        pid = data.get("playbook_id")
        if pid != path.stem:
            p(f"{path.name}: playbook_id {pid!r} must match filename stem {path.stem!r}")
        if pid in ids:
            p(f"{path.name}: duplicate playbook_id {pid!r}")
        if pid:
            ids.add(pid)
        # Structural rules enforced regardless of jsonschema availability:
        # the approval gate -- any stage above low-impact must require
        # approval (or the playbook must be an active-validation one that
        # gates at plan time AND execution, never silently).
        stages = data.get("stages") or []
        for st in stages:
            if not isinstance(st, dict):
                continue
            if st.get("impact") in ("active", "disruptive") and not st.get("requires_approval"):
                p(f"{path.name}: stage {st.get('name')!r} has impact {st.get('impact')!r} but requires_approval is not true")
        if schema is not None:
            import jsonschema
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                p(f"{path.name}: schema violation at {'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}")
    # Every stage the catalog names must exist (prove the filter matched).
    catalog = (PACK_ROOT / "PLAYBOOK_CATALOG.md").read_text()
    missing = [i for i in ids if i not in catalog]
    if missing:
        p(f"PLAYBOOK_CATALOG.md is missing entries for: {', '.join(sorted(missing))}")
    return len(files), ids


def main() -> int:
    manifest = validate_manifest()
    bio_dir = PACK_ROOT / "agents"
    team_dir = PACK_ROOT / "teams"
    schema_dir = PACK_ROOT / "schemas"

    bios = sorted(bio_dir.glob("*.yaml"))
    teams = sorted(team_dir.glob("*.yaml"))
    bio_names = set()
    for path in bios:
        data = validate_bio(path)
        if data.get("name"):
            bio_names.add(data["name"])
    for path in teams:
        validate_team(path, bio_names)
    pb_count, _ = validate_playbooks()

    for path in sorted(schema_dir.glob("*.json")):
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as e:
            p(f"{path.name}: invalid JSON: {e}")

    # Manifest contribution counts must match reality (prove the filter
    # counted something: N-before -> M-after).
    if manifest:
        c = manifest.get("contributions") or {}
        agents_c = c.get("agents") or {}
        if agents_c.get("count") != len(bios):
            p(f"pack.yaml: contributions.agents.count {agents_c.get('count')} != {len(bios)} bio files found")
        teams_c = c.get("teams") or {}
        if teams_c.get("count") != len(teams):
            p(f"pack.yaml: contributions.teams.count {teams_c.get('count')} != {len(teams)} team files found")
        pb_c = c.get("playbooks") or {}
        if pb_c.get("count", 0) != pb_count:
            p(f"pack.yaml: contributions.playbooks.count {pb_c.get('count')} != {pb_count} playbook files found")

    print(f"validated: {len(bios)} bios, {len(teams)} teams, {pb_count} playbooks, "
          f"{len(list(schema_dir.glob('*.json')))} schemas")
    if problems:
        for line in problems:
            print(f"PROBLEM: {line}")
        print(f"FAIL: {len(problems)} problem(s)")
        return 1
    print("OK: pack is valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
