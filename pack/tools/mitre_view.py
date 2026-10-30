#!/usr/bin/env python3
"""Halo Hacker MITRE view — ATLAS (shipped) + ATT&CK (cached on first use).

Frameworks data for the attack-flow skill: technique lookup, tactic
listing, text search, and per-engagement mapping support.

- ATLAS ships IN the pack: pack/resources/atlas/atlas.json (MITRE ATLAS
  2026.10, atlas-data v6 dist — 16 tactics, 221 techniques, 44
  mitigations; original prose trimmed to 400-600 chars per entry, full
  data at github.com/mitre-atlas/atlas-data).
- ATT&CK Enterprise is ~53 MB of STIX — too big to vendor and freshness
  matters, so it CACHES on first use into the pack's data folder as a
  compact index (id, name, tactics, trimmed description) and refreshes
  when older than the TTL. Offline with no cache: ATT&CK queries answer
  {"ok": false, "error": "attack index not cached and offline"} — never
  raise.

Read-only; the only network call is the ATT&CK index build, which asks
before downloading (CLI flag --yes to skip the question). Stdlib-only by
pack convention.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

_ATLAS_PATH = Path(__file__).resolve().parent.parent / "resources" / "atlas" / "atlas.json"
_ATTACK_STIX_URL = ("https://raw.githubusercontent.com/mitre-attack/"
                    "attack-stix-data/master/enterprise-attack/enterprise-attack.json")
_ATTACK_TTL_DAYS = 30

_TECHNIQUE_ID = re.compile(r"^(T\d{4}(\.\d{3})?|AML\.T\d{4}(\.\d{3})?)$")


def _data_dir() -> Path:
    d = Path(os.environ.get("HALO_HACKER_DATA_DIR")
             or (Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _attack_index_path() -> Path:
    return _data_dir() / "attack-index.json"


def load_atlas() -> dict:
    return json.loads(_ATLAS_PATH.read_text())


def attack_index(*, allow_fetch: bool = False) -> dict:
    """The compact ATT&CK index; builds from STIX on first use."""
    path = _attack_index_path()
    if path.exists():
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days < _ATTACK_TTL_DAYS:
            return json.loads(path.read_text())
    if not allow_fetch:
        if path.exists():
            return json.loads(path.read_text())  # stale is better than nothing
        return {"ok": False, "error": "attack index not cached (run: python pack/tools/mitre_view.py build-attack-index --yes)"}
    raw = _download(_ATTACK_STIX_URL)
    stix = json.loads(raw)
    techniques = {}
    for obj in stix.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        ext_id = None
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                ext_id = ref["external_id"]
                break
        if not ext_id:
            continue
        tactics = [p["phase_name"] for p in obj.get("kill_chain_phases", [])
                   if p.get("kill_chain_name") == "mitre-attack"]
        techniques[ext_id] = {
            "name": obj.get("name", ""),
            "tactics": tactics,
            "description": (obj.get("description") or "")[:600],
        }
    index = {"source": "MITRE ATT&CK Enterprise", "built": time.strftime("%Y-%m-%d"),
             "techniques": techniques}
    path.write_text(json.dumps(index))
    return index


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "halo-hacker-mitre-view/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def lookup(tech_id: str) -> dict:
    """One technique by id, across both frameworks."""
    if not _TECHNIQUE_ID.match(tech_id):
        return {"ok": False, "error": f"not a technique id: {tech_id}"}
    if tech_id.startswith("AML."):
        atlas = load_atlas()
        t = atlas["techniques"].get(tech_id)
        if not t:
            return {"ok": False, "error": f"unknown ATLAS technique: {tech_id}"}
        return {"ok": True, "framework": "ATLAS", "id": tech_id, **t}
    idx = attack_index()
    if not idx.get("techniques"):
        return {"ok": False, "error": "attack index not cached and offline"}
    t = idx["techniques"].get(tech_id)
    if not t:
        return {"ok": False, "error": f"unknown ATT&CK technique: {tech_id}"}
    return {"ok": True, "framework": "ATT&CK", "id": tech_id, **t}


def search(text: str, *, framework: str = "both") -> dict:
    """Case-insensitive substring search over names (and descriptions for ATLAS)."""
    needle = text.lower()
    hits = []
    if framework in ("both", "atlas"):
        for tid, t in load_atlas()["techniques"].items():
            if needle in t["name"].lower() or needle in t["description"].lower():
                hits.append({"framework": "ATLAS", "id": tid, "name": t["name"]})
    if framework in ("both", "attack"):
        idx = attack_index()
        for tid, t in (idx.get("techniques") or {}).items():
            if needle in t["name"].lower():
                hits.append({"framework": "ATT&CK", "id": tid, "name": t["name"]})
    return {"ok": True, "hits": hits}


def list_tactics(framework: str = "atlas") -> dict:
    if framework == "atlas":
        return {"ok": True, "framework": "ATLAS",
                "tactics": {k: v["name"] for k, v in load_atlas()["tactics"].items()}}
    idx = attack_index()
    tactics: dict = {}
    for t in (idx.get("techniques") or {}).values():
        for tac in t["tactics"]:
            tactics[tac.replace("-", " ")] = tac
    return {"ok": True, "framework": "ATT&CK", "tactics": tactics}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: mitre_view.py lookup <id> | search <text> [--framework atlas|attack|both] "
              "| tactics [atlas|attack] | build-attack-index [--yes]", file=sys.stderr)
        sys.exit(2)
    cmd, rest = args[0], args[1:]
    if cmd == "lookup" and rest:
        out = lookup(rest[0])
    elif cmd == "search" and rest:
        fw = "both"
        if "--framework" in rest:
            i = rest.index("--framework")
            fw = rest[i + 1]
            rest = rest[:i]
        out = search(" ".join(rest), framework=fw)
    elif cmd == "tactics":
        out = list_tactics(rest[0] if rest else "atlas")
    elif cmd == "build-attack-index":
        if "--yes" not in rest:
            print("downloads ~53 MB from mitre-attack/attack-stixdata — rerun with --yes",
                  file=sys.stderr)
            sys.exit(2)
        out = attack_index(allow_fetch=True)
        out = {"ok": True, "built": out.get("built"), "techniques": len(out.get("techniques", {}))}
    else:
        out = {"ok": False, "error": f"unknown command: {cmd}"}
    print(json.dumps(out))
