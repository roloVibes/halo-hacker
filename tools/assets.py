#!/usr/bin/env python3
"""Halo Hacker asset + coverage ledger (G1, from _research/ARTEX-REVIEW.md).

The asset model sits beside the findings store on the engagement tree:

    <state>/engagements/<eng-id>/
      assets/assets.jsonl      one record per asset, keyed by derived asset_id
      assets/coverage.jsonl    one coverage entry per (surface, risk_area) test

Hard rules, consistent with the findings store:
- Agents submit OBSERVATIONS; this module computes identity (dedupe key),
  parentage (containment), and the coverage ledger. Agents never write
  graph structure directly.
- Append-only, no delete verb. Re-observing the same surface updates
  last_seen/attributes in place (keyed upsert), never duplicates.
- jsonschema is a hard dependency — fail closed, no degraded mode.
- The coverage ledger PROVES its gaps: build_ledger() reports N entries ->
  M gaps, and a negative outcome without evidence/reason is a named gap,
  never silently dropped.

The ARTEX lineage (AGPL) is design-only; this is an independent
stdlib-only implementation over the pack's own schemas.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import jsonschema  # MANDATORY — fail closed

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_ASSET_SCHEMA = json.loads((_SCHEMA_DIR / "asset.schema.json").read_text())
_COVERAGE_SCHEMA = json.loads((_SCHEMA_DIR / "coverage.schema.json").read_text())

# Outcomes that require an evidence_ref / reason to not be counted a gap.
_NEEDS_EVIDENCE = {"no_issue_found"}
_NEEDS_REASON = {"ruled_out", "not_applicable"}


class AssetStoreError(Exception):
    """Refusals are the store working, not failing."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _atomic_append(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".al-")
    with os.fdopen(fd, "w") as f:
        if path.exists():
            f.write(path.read_text())
        f.write(json.dumps(obj) + "\n")
    os.replace(tmp, path)


def derive_asset_id(asset_type: str, identity: dict) -> str:
    """The dedupe key for one asset, derived from type+identity — never
    chosen by the agent. Format: <type>:<type-specific-key>."""
    if asset_type in ("root_domain", "subdomain"):
        key = (identity.get("domain") or "").lower().strip()
    elif asset_type == "ip":
        key = (identity.get("ip") or "").strip()
    elif asset_type == "service":
        key = "%s:%s:%s" % (
            (identity.get("host") or "").lower(),
            identity.get("port") or "",
            identity.get("scheme") or "http",
        )
    elif asset_type == "endpoint":
        key = "%s %s" % (
            (identity.get("method") or "GET").upper(),
            (identity.get("url") or "").lower().strip(),
        )
    elif asset_type == "app":
        key = identity.get("bundle_id") or (identity.get("name") or "").lower()
    else:
        raise AssetStoreError(f"unknown asset type: {asset_type!r}")
    if not key or key in (":", " ", "::http"):
        raise AssetStoreError(
            f"identity for {asset_type!r} is missing its key fields: {identity!r}")
    return f"{asset_type}:{key}"


def _parent_of(asset: dict) -> Optional[str]:
    """Containment: root_domain→subdomain→service→endpoint. Computed here,
    never set by the agent. Returns the parent's asset_id, or None."""
    t, ident = asset["type"], asset.get("identity", {})
    if t == "subdomain":
        dom = (ident.get("domain") or "").lower()
        parts = dom.split(".")
        if len(parts) > 2:
            return derive_asset_id("root_domain", {"domain": ".".join(parts[-2:])})
    elif t == "service":
        host = (ident.get("host") or "").lower()
        if host:
            return derive_asset_id("subdomain", {"domain": host})
    elif t == "endpoint":
        url = (ident.get("url") or "").lower()
        # host[:port] from scheme://host[:port]/path
        without_scheme = url.split("://", 1)[-1]
        hostport = without_scheme.split("/", 1)[0]
        host, _, port = hostport.partition(":")
        scheme = url.split("://", 1)[0] if "://" in url else "http"
        if host:
            return derive_asset_id("service", {
                "host": host,
                "port": int(port) if port.isdigit() else (443 if scheme == "https" else 80),
                "scheme": scheme if scheme in ("http", "https") else "http",
            })
    return None


class AssetStore:
    """Asset observations + coverage ledger for one engagement."""

    def __init__(self, engagement_root: Path):
        self.root = Path(engagement_root)
        self.dir = self.root / "assets"
        self.assets_file = self.dir / "assets.jsonl"
        self.coverage_file = self.dir / "coverage.jsonl"

    # -- assets ----------------------------------------------------------

    def _read_assets(self) -> dict:
        out = {}
        if self.assets_file.exists():
            for line in self.assets_file.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    out[rec["asset_id"]] = rec
        return out

    def _write_assets(self, assets: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), prefix=".assets-")
        with os.fdopen(fd, "w") as f:
            for rec in assets.values():
                f.write(json.dumps(rec) + "\n")
        os.replace(tmp, self.assets_file)

    def record_observation(self, asset_type: str, identity: dict, *,
                           engagement_id: str,
                           attributes: Optional[dict] = None,
                           source: str = "recon") -> dict:
        """Submit one asset observation. Dedupes by derived asset_id:
        re-observation updates last_seen/attributes in place. Computes
        parentage. Returns the stored record."""
        asset_id = derive_asset_id(asset_type, identity)
        rec = {
            "asset_id": asset_id,
            "engagement_id": engagement_id,
            "type": asset_type,
            "identity": identity,
            "attributes": attributes or {},
            "source": source,
            "first_seen": _now(),
            "last_seen": _now(),
        }
        parent = _parent_of(rec)
        if parent:
            rec["parent_ref"] = parent
        jsonschema.validate(rec, _ASSET_SCHEMA)

        assets = self._read_assets()
        if asset_id in assets:
            existing = assets[asset_id]
            existing["last_seen"] = rec["last_seen"]
            existing["attributes"].update(rec["attributes"])
            rec = existing
        else:
            assets[asset_id] = rec
        self._write_assets(assets)
        return rec

    def list_assets(self, asset_type: Optional[str] = None) -> list:
        out = list(self._read_assets().values())
        return [a for a in out if asset_type is None or a["type"] == asset_type]

    # -- coverage ledger ---------------------------------------------------

    def record_coverage(self, entry: dict) -> dict:
        """Append one coverage entry. Sets the timestamp; validates against
        coverage.schema.json. Missing evidence/reason is NOT blocked — it is
        recorded and then surfaced by build_ledger() as a named gap."""
        entry = dict(entry)
        entry.setdefault("timestamp", _now())
        jsonschema.validate(entry, _COVERAGE_SCHEMA)
        _atomic_append(self.coverage_file, entry)
        return entry

    def coverage_entries(self) -> list:
        if not self.coverage_file.exists():
            return []
        return [json.loads(l) for l in
                self.coverage_file.read_text().splitlines() if l.strip()]

    def build_ledger(self) -> dict:
        """Roll coverage entries into the planner-facing ledger.

        PROVES its gaps: reports N entries and M gaps, and names each gap.
        A negative outcome (no_issue_found / ruled_out / not_applicable)
        without its required evidence_ref / reason is a gap. Surfaces seen
        for some risk classes but not others are NOT auto-gaps (that is the
        planner's cross-product judgment); this ledger only flags entries
        whose own evidence discipline is missing.
        """
        entries = self.coverage_entries()
        gaps: list[dict] = []
        counts: dict[str, int] = {}
        for e in entries:
            counts[e["outcome"]] = counts.get(e["outcome"], 0) + 1
            if e["outcome"] in _NEEDS_EVIDENCE and not e.get("evidence_ref"):
                gaps.append({
                    "kind": "no_issue_found_without_evidence",
                    "surface": e["surface"],
                    "risk_area": e["risk_area"],
                })
            if e["outcome"] in _NEEDS_REASON and not e.get("reason"):
                gaps.append({
                    "kind": f"{e['outcome']}_without_reason",
                    "surface": e["surface"],
                    "risk_area": e["risk_area"],
                })
        return {
            "entry_count": len(entries),
            "gap_count": len(gaps),
            "counts": counts,
            "gaps": gaps,
        }


def main(argv=None) -> int:  # pragma: no cover - thin CLI
    import argparse
    p = argparse.ArgumentParser(description="halo-hacker asset + coverage ledger")
    p.add_argument("engagement_root")
    p.add_argument("--ledger", action="store_true", help="print the coverage ledger")
    args = p.parse_args(argv)
    store = AssetStore(Path(args.engagement_root))
    if args.ledger:
        print(json.dumps(store.build_ledger(), indent=2))
    else:
        print(json.dumps(store.list_assets(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
