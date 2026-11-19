#!/usr/bin/env python3
"""Telemetry export — an engagement's evidence ledger as a portable bundle.

Some programs and competitions ask not just for findings but for the full
record of what the tester (human or agent) DID: timestamped actions, session
structure, and proof the record was not rewritten after the fact. The
engagement evidence ledger already is that record — append-only, hash-chained,
atomic appends, UTC timestamps, content-addressed artifacts. This tool renders
it as a portable bundle:

    manifest.json      run identity, counts, chain-verification result, file hashes
    actions.jsonl      one row per ledger row, with a per-run correlation id
    sessions.jsonl     contiguous same-actor runs grouped as sessions
    summary.md         the human-readable one-pager
    capture-setup.md   how the evidence was captured and how a third party verifies it

Honesty rule: the chain is verified at export time and the result is written
INTO the manifest, problems included. A bundle that reports a broken chain is
valid output; a bundle that hid it would be worthless.

Stdlib-only by pack convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from findings_store import FindingStore, FindingStoreError  # noqa: E402

_BUNDLE_KIND = "halo-hacker-telemetry"
_BUNDLE_VERSION = "1.0"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pack_version() -> str:
    pack = Path(__file__).resolve().parent.parent / "pack.yaml"
    try:
        for line in pack.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def _sessions(rows: list) -> list:
    """Group contiguous same-actor ledger rows into sessions. A session break
    is an actor change — a cheap, honest proxy for 'one working stretch'."""
    sessions = []
    for row in rows:
        if sessions and sessions[-1]["actor"] == row["actor"]:
            s = sessions[-1]
            s["ended_at"] = row["timestamp"]
            s["actions"] += 1
            s["last_seq"] = row["seq"]
        else:
            sessions.append({
                "session_id": f"s{len(sessions):04d}",
                "actor": row["actor"],
                "started_at": row["timestamp"],
                "ended_at": row["timestamp"],
                "actions": 1,
                "first_seq": row["seq"],
                "last_seq": row["seq"],
            })
    return sessions


def export_bundle(engagement_root: Path, out_dir: Path, run_id: str) -> dict:
    """Build the telemetry bundle under out_dir. Returns the manifest dict.
    Refuses (FindingStoreError) when the engagement tree is not a real store."""
    store = FindingStore(Path(engagement_root))
    engagement = store.engagement()
    rows = store._read_rows()
    chain_problems = store.verify_chain()

    out_dir.mkdir(parents=True, exist_ok=True)

    actions = []
    for row in rows:
        actions.append({
            "seq": row["seq"],
            "timestamp": row["timestamp"],
            "correlation_id": f"{run_id}:{row['seq']:06d}",
            "actor": row["actor"],
            "action": row["action"],
            "artifact_sha256": row["artifact_sha256"],
            "finding_id": row.get("finding_id"),
            "meta": row.get("meta") or {},
            "prev_hash": row["prev_hash"],
            "hash": row["hash"],
        })

    sessions = _sessions(rows)
    findings_referenced = sorted({r["finding_id"] for r in rows if r.get("finding_id")})
    artifacts = sorted({r["artifact_sha256"] for r in rows})

    (out_dir / "actions.jsonl").write_text(
        "".join(json.dumps(a) + "\n" for a in actions), encoding="utf-8")
    (out_dir / "sessions.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in sessions), encoding="utf-8")

    summary = [
        f"# Telemetry summary — {engagement.get('engagement_id', 'unknown')}",
        "",
        f"- Run id: `{run_id}`",
        f"- Generated: {_utc_now()}",
        f"- Engagement owner: {engagement.get('owner', 'unknown')}",
        f"- Window: {engagement.get('window', {}).get('start', '?')} → {engagement.get('window', {}).get('expires', '?')}",
        f"- Actions recorded: {len(actions)} across {len(sessions)} session(s)",
        f"- Findings referenced: {len(findings_referenced)}"
        + (f" ({', '.join(findings_referenced)})" if findings_referenced else ""),
        f"- Evidence artifacts: {len(artifacts)} (content-addressed by sha256)",
        f"- Ledger chain: {'INTACT' if not chain_problems else 'BROKEN — see manifest.json'}",
        "",
        "Every action row carries its ledger hash and prev_hash; re-walking the",
        "chain as described in capture-setup.md independently reproduces the",
        "head hash in manifest.json.",
        "",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")

    capture = "\n".join([
        "# Capture setup",
        "",
        "This bundle was produced by the halo-hacker pack's telemetry export from",
        "an engagement evidence ledger. The capture model:",
        "",
        "- **Append-only ledger.** Every evidence action (a stored transcript, a",
        "  reproduction run, a reviewer decision) appends one JSON row to",
        "  `evidence/ledger.jsonl`. Rows are never edited or deleted.",
        "- **Hash chain.** Each row records `prev_hash` (the previous row's hash) and",
        "  its own `hash` = sha256 of the canonical JSON of the row WITHOUT the hash",
        "  field, where canonical = `json.dumps(row, sort_keys=True, separators=(',', ':'))`.",
        "  The first row chains from 64 zeroes. Rewriting, reordering, or deleting any",
        "  row breaks every later hash.",
        "- **Atomic appends.** Appends write a temp file and rename over the ledger,",
        "  so a crash cannot leave a half-written row.",
        "- **UTC timestamps.** Every row timestamp is `time.strftime` GMT at write time.",
        "- **Content-addressed artifacts.** The bytes each row describes live under",
        "  `evidence/artifacts/<sha256>/artifact.bin`; the row's `artifact_sha256` is",
        "  the sha256 of those bytes, so the artifact cannot be swapped silently.",
        "- **External checkpoints.** `FindingStore.checkpoint()` emits {count, head}",
        "  meant to be copied off-box; a local rewrite cannot forge the off-box head.",
        "",
        "## Verifying this bundle",
        "",
        "1. Re-walk `actions.jsonl`: for each row recompute the hash as above and",
        "   check `prev_hash` links. The last row's hash must equal",
        "   `manifest.json → ledger.head_hash`.",
        "2. Check `manifest.json → ledger.chain_intact` and `chain_problems`; the",
        "   exporter records the verification result at export time and never",
        "   suppresses problems.",
        "3. File hashes for every bundle member are in `manifest.json → files`.",
        "",
    ])
    (out_dir / "capture-setup.md").write_text(capture, encoding="utf-8")

    file_hashes = {}
    for name in ("actions.jsonl", "sessions.jsonl", "summary.md", "capture-setup.md"):
        file_hashes[name] = _sha256((out_dir / name).read_bytes())

    manifest = {
        "schema_version": 1,
        "bundle": _BUNDLE_KIND,
        "bundle_version": _BUNDLE_VERSION,
        "run_id": run_id,
        "generated_at": _utc_now(),
        "generator": {
            "tool": "halo-hacker",
            "version": _pack_version(),
            "component": "tools/telemetry_export.py",
        },
        "engagement": {
            "engagement_id": engagement.get("engagement_id"),
            "owner": engagement.get("owner"),
            "window": engagement.get("window"),
        },
        "counts": {
            "actions": len(actions),
            "sessions": len(sessions),
            "findings_referenced": len(findings_referenced),
            "artifacts": len(artifacts),
        },
        "ledger": {
            "rows": len(rows),
            "head_hash": rows[-1]["hash"] if rows else "0" * 64,
            "chain_intact": not chain_problems,
            "chain_problems": chain_problems,
        },
        "files": file_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="Export an engagement's evidence ledger as a telemetry bundle.")
    ap.add_argument("engagement_root", help="Engagement directory (holds engagement.json + evidence/ledger.jsonl)")
    ap.add_argument("--out", help="Output directory (default: <engagement>/report/telemetry-<UTCts>/)")
    ap.add_argument("--run-id", help="Run identifier embedded in correlation ids (default: telemetry-<UTCts>)")
    ap.add_argument("--zip", action="store_true", help="Also write <out>.zip next to the output directory")
    args = ap.parse_args(argv)

    root = Path(args.engagement_root)
    run_id = args.run_id or time.strftime("telemetry-%Y%m%dT%H%M%SZ", time.gmtime())
    out = Path(args.out) if args.out else root / "report" / time.strftime("telemetry-%Y%m%dT%H%M%SZ", time.gmtime())

    try:
        manifest = export_bundle(root, out, run_id)
    except (FindingStoreError, FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1

    result = {"ok": True, "out": str(out), "run_id": run_id,
              "chain_intact": manifest["ledger"]["chain_intact"],
              "counts": manifest["counts"]}
    if args.zip:
        zip_path = out.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(out.iterdir()):
                zf.write(f, arcname=f.name)
        result["zip"] = str(zip_path)
        result["zip_sha256"] = _sha256(zip_path.read_bytes())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
