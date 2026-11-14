#!/usr/bin/env python3
"""Attack path graph — the data layer for studio/attack-paths.js.

Reads the findings store and projects every finding's `requires` / `grants`
capability tokens into a node/edge graph, plus MITRE ATT&CK / ATLAS technique
mapping. Writes data/attack-paths.json the panel renders.

The graph is a PROJECTION over requires/grants, never a stored graph: a
finding's `grants` tokens connect to any other finding whose `requires`
lists the same token. Confirmed findings are solid; candidates are dashed.

Read-only. Stdlib-only. Best-effort import of the store and the harness.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def data_dir() -> Path:
    env = os.environ.get("HALO_HACKER_DATA_DIR")
    if env:
        return Path(env)
    try:
        from halo_harness.ext import data_dir as _dd
        return Path(_dd("halo-hacker"))
    except Exception:
        return Path(os.path.expanduser("~/.halo/packs/.data/halo-hacker"))


def _load_findings() -> list[dict]:
    """Return every finding document (best-effort)."""
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    try:
        from findings_store import FindingStore
        from findings_view import engagement_root
        store = FindingStore(engagement_root())
        return store.all_findings()
    except Exception:
        return []


def build(findings: list[dict] | None = None) -> dict:
    if findings is None:
        findings = _load_findings()

    nodes: list[dict] = []
    edges: list[dict] = []
    techniques: list[dict] = []

    # Index grants: token -> [finding_ids that grant it]
    grants_index: dict[str, list[str]] = {}
    for f in findings:
        fid = f.get("finding_id", "")
        for token in f.get("grants") or []:
            grants_index.setdefault(token, []).append(fid)

    for f in findings:
        fid = f.get("finding_id", "")
        confirmed = (f.get("status") == "confirmed") or (f.get("display_state") == "confirmed")
        nodes.append({
            "id": fid,
            "title": f.get("title", ""),
            "severity": f.get("severity", ""),
            "state": f.get("status") or f.get("display_state", ""),
            "confirmed": confirmed,
            "requires": f.get("requires") or [],
            "grants": f.get("grants") or [],
        })
        for tid in f.get("technique_ids") or []:
            techniques.append({"finding_id": fid, "technique_id": tid, "confirmed": confirmed})

    # Edges: finding B requires token T that finding A grants.
    for f in findings:
        fid = f.get("finding_id", "")
        confirmed_f = (f.get("status") == "confirmed") or (f.get("display_state") == "confirmed")
        for token in f.get("requires") or []:
            for granter in grants_index.get(token, []):
                if granter == fid:
                    continue
                granter_confirmed = any(
                    g.get("finding_id") == granter and (g.get("status") == "confirmed" or g.get("display_state") == "confirmed")
                    for g in findings
                )
                edges.append({
                    "from": granter,
                    "to": fid,
                    "token": token,
                    # an edge is demonstrated only if BOTH ends are confirmed
                    "demonstrated": confirmed_f and granter_confirmed,
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "techniques": techniques,
        "generated": _now(),
    }


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "attack-paths.json").write_text(json.dumps(build(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(build(), indent=2))
    else:
        sys.exit(main())
