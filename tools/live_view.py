#!/usr/bin/env python3
"""Live view — the data layer for studio/live.js (the agent dashboard).

Reads Halo's live session state (remote.live_lines / remote.sessions) and
writes data/live.json that the Studio panel fetches. Best-effort: without
the harness, the file is a valid-but-empty snapshot.

Where the data folder is (same precedence as findings_view.py):
1. $HALO_HACKER_DATA_DIR
2. halo_harness.ext.data_dir("halo-hacker")
3. ~/.halo/packs/.data/halo-hacker
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
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


def collect() -> dict:
    sessions: list[dict] = []
    lines: list[str] = []
    harness = False
    try:
        from halo_harness.ext import remote
        if remote.enabled():
            harness = True
            sessions = remote.sessions() or []
            lines = remote.live_lines(limit=30) or []
    except Exception:
        pass

    return {
        "harness": harness,
        "sessions": sessions,
        "lines": lines,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> int:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "live.json").write_text(json.dumps(collect(), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(collect(), indent=2))
    else:
        sys.exit(main())
