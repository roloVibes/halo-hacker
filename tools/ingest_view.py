#!/usr/bin/env python3
"""Ingest view — the data layer for studio/ingest.js.

Reads the pack's provenance ledger (<vault>/ingest/ledger.jsonl) and writes
data/ingest/summary.json with the source breakdown, trust-tier distribution,
topic routing, and pipeline health the panel renders.

Read-only: never touches the ledger or the vault. Stdlib-only.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
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


def vault_path() -> Path:
    env = os.environ.get("HALO_HACKER_VAULT")
    if env:
        return Path(env)
    try:
        from halo_harness.ext import get_config
        v = get_config("halo-hacker", "vault", "")
        if v:
            return Path(v)
    except Exception:
        pass
    # Conventional default: the pack's own data folder holds the vault when
    # one is not configured.
    return data_dir()


def collect(vault: Path | None = None) -> dict:
    vault = vault or vault_path()
    ledger = Path(vault) / "ingest" / "ledger.jsonl"

    rows: list[dict] = []
    if ledger.is_file():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    source_types = Counter(r.get("source_type", "unknown") for r in rows)
    trust_tiers = Counter(r.get("trust_tier", "unclassified") for r in rows)
    topics = Counter(r.get("topic", "unrouted") for r in rows)

    # Topic routing: map each topic to a testing lane by convention.
    LANE_MAP = {
        "recon": ["subdomain", "port", "fingerprint", "endpoint", "dns", "tech"],
        "web": ["web", "http", "html", "js", "browser"],
        "api": ["api", "graphql", "rest", "json", "oauth", "jwt"],
        "ai": ["llm", "prompt", "model", "ai", "rag"],
        "infra": ["cloud", "aws", "gcp", "azure", "ci", "network"],
    }
    routing: dict[str, int] = {}
    for topic, count in topics.items():
        lane = "other"
        t = topic.lower()
        for candidate, keys in LANE_MAP.items():
            if any(k in t for k in keys):
                lane = candidate
                break
        routing[lane] = routing.get(lane, 0) + count

    recent = rows[-20:][::-1]  # newest first

    return {
        "vault": str(vault),
        "ledger_exists": ledger.is_file(),
        "total_items": len(rows),
        "source_types": dict(source_types.most_common()),
        "trust_tiers": dict(trust_tiers.most_common()),
        "topics": dict(topics.most_common()),
        "routing": routing,
        "recent": recent,
        "generated": _now(),
    }


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    d = data_dir()
    (d / "ingest").mkdir(parents=True, exist_ok=True)
    (d / "ingest" / "summary.json").write_text(json.dumps(collect(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(collect(), indent=2))
    else:
        sys.exit(main())
