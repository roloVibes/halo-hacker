#!/usr/bin/env python3
"""Halo Hacker findings view — the data layer for the pack's Studio panels.

Reads a FindingStore (an engagement tree) and writes two files into the
pack's data folder for the Studio panels declared in pack.yaml:

- findings/summary.json — the findings table: one row per finding
  (finding_id, title, severity, state, target_ref, source, updated).
  NOTE (VERIFY against a live Studio panel): the table panel's expected
  row shape is assumed to be a JSON array of objects with the columns
  declared on the panel. If Studio wants {"columns":..., "rows":...},
  change write_summary()'s payload — one place, tested.
- findings/counts.md — the counts strip (markdown panel): a one-line
  summary "N identified · N reviewed · N confirmed" per engagement.

Display-state mapping (REPORTING.md): candidate→identified,
validated→reviewed, confirmed→confirmed; rejected/duplicate/withdrawn
are terminal and excluded from the strip but kept in the table rows.

Nothing here sends anything, reads anything outside the engagement tree
and the pack data dir, or writes the store — this is a read-only view
layer. Stdlib-only by pack convention.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from findings_store import FindingStore  # noqa: E402

# Finding.status enum: candidate, needs_validation, confirmed, not_reproduced,
# duplicate, rejected, requires_human_review, withdrawn.
# Display mapping (REPORTING.md): identified / reviewed / confirmed, where
# "reviewed" = independent reproduction done (validation.status=reproduced)
# but the judge has not confirmed yet.
TERMINAL_STATES = {"not_reproduced", "duplicate", "rejected", "withdrawn"}


def display_state(f: dict) -> str:
    status = str(f.get("status", "")).lower()
    if status == "confirmed":
        return "confirmed"
    if status in TERMINAL_STATES:
        return status
    val = f.get("validation") or {}
    if isinstance(val, dict) and str(val.get("status", "")).lower() == "reproduced":
        return "reviewed"
    return "identified"


def data_dir() -> Path:
    """The pack's OWN data folder — Studio `data:` panel sources must live
    inside the pack's folder (the inspector enforces this). For an installed
    pack that is ~/.halo/packs/halo-hacker/data/. Env override for tests."""
    d = Path(os.environ.get("HALO_HACKER_DATA_DIR")
             or (Path(__file__).resolve().parent.parent / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _severity(f: dict) -> str:
    return str(f.get("severity") or "info").lower()


def _source(f: dict) -> str:
    return str(f.get("source") or "tester")


def _updated(f: dict) -> str:
    hist = f.get("audit_history") or []
    if hist and isinstance(hist[-1], dict) and hist[-1].get("timestamp"):
        return str(hist[-1]["timestamp"])
    return ""


def summary_rows(store: FindingStore) -> list[dict]:
    """One table row per finding, display states applied."""
    rows = []
    for f in store.list_findings():
        rows.append({
            "finding_id": f.get("finding_id"),
            "title": f.get("title"),
            "severity": _severity(f),
            "state": display_state(f),
            "target_ref": f.get("target_ref", ""),
            "source": _source(f),
            "updated": _updated(f),
        })
    rows.sort(key=lambda r: (r["state"] != "confirmed", r["severity"], str(r["finding_id"])))
    return rows


def counts_markdown(engagement: dict, rows: list[dict]) -> str:
    """The counts strip: live states only, terminal states excluded."""
    n = {s: 0 for s in ("identified", "reviewed", "confirmed")}
    for r in rows:
        if r["state"] in n:
            n[r["state"]] += 1
    eng = engagement.get("engagement_id") or engagement.get("id") or ""
    return (f"**{n['identified']} identified · {n['reviewed']} reviewed · "
            f"{n['confirmed']} confirmed** — engagement `{eng}`\n")


def write_summary(engagement_root: Path, *, out_dir: Path | None = None) -> dict:
    """Write both panel files; returns what was written (for tests/CLI)."""
    store = FindingStore(Path(engagement_root))
    out = Path(out_dir) if out_dir else data_dir() / "findings"
    out.mkdir(parents=True, exist_ok=True)
    rows = summary_rows(store)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out / "summary.json").write_text(json.dumps(
        {"engagement_id": store.engagement().get("engagement_id")
                         or store.engagement().get("id") or "",
         "generated": generated, "rows": rows}, indent=1))
    (out / "counts.md").write_text(counts_markdown(store.engagement(), rows))
    return {"rows": len(rows), "dir": str(out), "generated": generated}


def finding_event(f: dict, *, actor: str = "") -> dict:
    """The hh.finding event payload for a finding state moment."""
    return {
        "finding_id": f.get("finding_id"),
        "engagement_id": f.get("engagement_id"),
        "title": f.get("title"),
        "severity": _severity(f),
        "state": display_state(f),
        "source": _source(f),
        "target_ref": f.get("target_ref", ""),
        "actor": actor,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: findings_view.py <engagement_root> [--data-dir <path>]", file=sys.stderr)
        sys.exit(2)
    root = Path(sys.argv[1])
    out = None
    if "--data-dir" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--data-dir") + 1]) / "findings"
    result = write_summary(root, out_dir=out)
    print(json.dumps(result))
