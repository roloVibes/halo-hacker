#!/usr/bin/env python3
"""Halo Hacker field-user findings import pipeline.

Accepts findings from three sources and funnels them into the engagement
FindingStore as schema-valid CANDIDATES:

- manual: a field user types one finding in.
- json: a batch of finding-shaped records (the pack's own schema).
- scanner: normalized output from Nuclei or Semgrep.

Hard rules, mechanically enforced:
- Imports are NEVER confirmed. Any claim of confirmation is downgraded to
  candidate and the validation/reviewer_decision fields are stripped.
- Every finding MUST have at least one real evidence ledger row before it is
  written; the artifact is content-addressed and chain-verifiable.
- finding_id collisions are detected and avoided.
- The engagement must exist and be active; otherwise nothing is written.

Stdlib-only in this file; jsonschema validation is delegated to the store's
already-required dependency (the store refuses invalid records).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import jsonschema  # store already hard-depends on this — fail closed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from findings_store import FindingStore, FindingStoreError  # noqa: E402
from normalizers import _slug, normalize_nuclei, normalize_semgrep  # noqa: E402

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_FINDING_SCHEMA = json.loads((_SCHEMA_DIR / "finding.schema.json").read_text())


class ImportFindingError(Exception):
    """An import refusal is the pipeline working, not failing."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _import_audit(actor: str, detail: str) -> dict:
    return {"timestamp": _now(), "actor": actor, "action": "imported", "detail": detail}


def _existing_ids(store: FindingStore) -> set[str]:
    return {f["finding_id"] for f in store.list_findings()}


def _unique_import_id(store: FindingStore, slug: str) -> str:
    """imp-NN-slug, bumping the sequence until no collision."""
    existing = _existing_ids(store)
    for seq in range(1, 1000):
        fid = f"imp-{seq:02d}-{slug}"
        if fid not in existing:
            return fid
    raise ImportFindingError("exhausted import id sequence space")


def _ensure_unique_id(store: FindingStore, fid: str) -> str:
    """Keep an existing id shape but avoid collisions by bumping the sequence."""
    existing = _existing_ids(store)
    if fid not in existing:
        return fid
    parts = fid.split("-", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        raise ImportFindingError(f"cannot make collision-safe id from {fid!r}")
    prefix, seq_str, slug = parts
    seq = int(seq_str)
    for seq in range(seq + 1, 1000):
        new_fid = f"{prefix}-{seq:02d}-{slug}"
        if new_fid not in existing:
            return new_fid
    raise ImportFindingError(f"exhausted sequence space for {fid!r}")


def _add_note_evidence(store: FindingStore, finding_id: str, note: str,
                       actor: str, action: str) -> dict:
    """Store the note as an artifact and return a schema-shaped evidence entry."""
    row = store.add_evidence(
        note.encode(),
        actor=actor,
        action=action,
        finding_id=finding_id,
        meta={"kind": "note"},
    )
    return {
        "ledger_ref": f"evidence/ledger.jsonl#{row['seq']:04d}",
        "artifact_sha256": row["artifact_sha256"],
        "kind": "note",
        "sanitized": True,
    }


def _validate_finding(item: dict, index: int | None = None) -> None:
    """Fail closed on schema violations; index is used for batch reporting."""
    try:
        jsonschema.validate(item, _FINDING_SCHEMA)
    except jsonschema.ValidationError as exc:
        prefix = f"item {index}: " if index is not None else ""
        raise ImportFindingError(f"{prefix}schema validation failed: {exc.message}")


def import_manual(store: FindingStore, *, title: str, description: str,
                  target_ref: str, severity: str, actor: str,
                  evidence_note: str, **kw: Any) -> dict:
    """Import a single manually entered finding as a candidate.

    A real evidence ledger row is created from ``evidence_note`` before the
    finding record is written.
    """
    if len(title) < 5:
        raise ImportFindingError("title must be at least 5 characters")
    slug = _slug(title)
    fid = _unique_import_id(store, slug)
    ev = _add_note_evidence(store, fid, evidence_note, actor, "imported-manual")
    finding = {
        "finding_id": fid,
        "engagement_id": store.engagement()["engagement_id"],
        "title": title,
        "category": kw.get("category") or "import:manual",
        "description": description,
        "target_ref": target_ref,
        "severity": severity,
        "source": "import",
        "status": "candidate",
        "evidence": [ev],
        "audit_history": [_import_audit(actor, f"manual import by {actor}")],
    }
    # Drop empty optional values so the schema never sees an invalid enum.
    finding = {k: v for k, v in finding.items() if v not in (None, "")}
    store.put_finding(finding)
    return finding


def import_json(store: FindingStore, payload: list[dict] | dict, *,
                actor: str) -> dict:
    """Import one or more finding-shaped records.

    - Records are validated against finding.schema.json.
    - status is forced to "candidate".
    - validation/reviewer_decision are stripped (an import cannot arrive
      confirmed or pre-judged).
    - source is forced to "import".
    - finding_id is re-keyed to a fresh import-prefixed id.
    - A real evidence ledger row is created from the description.

    Returns {"imported": n, "finding_ids": [...], "rejected": [...]}.
    """
    items = payload if isinstance(payload, list) else [payload]
    imported_ids: list[str] = []
    rejected: list[dict] = []

    for idx, raw in enumerate(items):
        item = dict(raw)
        try:
            _validate_finding(item, index=idx)
        except ImportFindingError as exc:
            rejected.append({"index": idx, "reason": str(exc)})
            continue

        # Imports are never confirmed, even if the payload claims it.
        if item.get("status") == "confirmed":
            item["status"] = "candidate"
        item.pop("validation", None)
        item.pop("reviewer_decision", None)
        item["status"] = "candidate"
        item["source"] = "import"

        slug = _slug(item.get("title", "unknown"))
        fid = _unique_import_id(store, slug)
        item["finding_id"] = fid
        item["engagement_id"] = store.engagement()["engagement_id"]

        note = item.get("description") or item.get("observed_behavior") or "imported finding"
        ev = _add_note_evidence(store, fid, note, actor, "imported-json")
        item["evidence"] = [ev]
        item.setdefault("audit_history", []).append(
            _import_audit(actor, f"json import by {actor}")
        )

        store.put_finding(item)
        imported_ids.append(fid)

    return {"imported": len(imported_ids), "finding_ids": imported_ids, "rejected": rejected}


def import_scanner_output(store: FindingStore, kind: str, raw_text: str, *,
                          actor: str) -> dict:
    """Import normalized Nuclei or Semgrep output as candidate findings.

    source is forced to "scanner", each candidate gets a real evidence ledger
    row, and finding_id collisions are resolved.
    """
    if kind not in {"nuclei", "semgrep"}:
        raise ImportFindingError(f"unsupported scanner kind: {kind!r}")

    engagement_id = store.engagement()["engagement_id"]
    suffix = ".jsonl" if kind == "nuclei" else ".json"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(raw_text)
        tmp_path = f.name
    try:
        if kind == "nuclei":
            candidates = normalize_nuclei(Path(tmp_path), engagement_id)
        else:
            candidates = normalize_semgrep(Path(tmp_path), engagement_id)
    finally:
        os.unlink(tmp_path)

    imported_ids: list[str] = []
    rejected: list[dict] = []
    for idx, raw in enumerate(candidates):
        c = dict(raw)
        try:
            _validate_finding(c, index=idx)
        except ImportFindingError as exc:
            rejected.append({"index": idx, "reason": str(exc)})
            continue

        c["source"] = "scanner"
        c["status"] = "candidate"
        c.pop("validation", None)
        c.pop("reviewer_decision", None)
        c["finding_id"] = _ensure_unique_id(store, c["finding_id"])

        note = c.get("description") or c.get("observed_behavior") or f"{kind} scanner result"
        ev = _add_note_evidence(store, c["finding_id"], note, actor, f"imported-{kind}")
        c["evidence"] = [ev]
        c.setdefault("audit_history", []).append(
            _import_audit(actor, f"{kind} scanner import by {actor}")
        )

        store.put_finding(c)
        imported_ids.append(c["finding_id"])

    return {"imported": len(imported_ids), "finding_ids": imported_ids, "rejected": rejected}


def _parse_manual(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in text.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _fail(message: str, detail: str = "") -> None:
    print(json.dumps({"error": message, "detail": detail}), file=sys.stdout)
    sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Halo Hacker field-user findings import pipeline")
    parser.add_argument("engagement_root", help="path to the engagement tree")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", metavar="FILE", help="JSON file with finding(s)")
    group.add_argument("--manual", metavar="K=V;...",
                       help="semicolon-separated key=value pairs")
    group.add_argument("--scanner", choices=["nuclei", "semgrep"],
                       help="scanner kind")
    parser.add_argument("--file", metavar="FILE",
                        help="scanner output file (required with --scanner)")
    parser.add_argument("--actor", required=True, help="importing actor")
    args = parser.parse_args(argv)

    root = Path(args.engagement_root)
    if not (root / "engagement.json").exists():
        _fail("engagement-not-found", str(root / "engagement.json"))

    store = FindingStore(root)
    try:
        store.check_authorization()
    except FindingStoreError as exc:
        _fail("engagement-not-authorized", str(exc))

    result: dict
    if args.json:
        payload = json.loads(Path(args.json).read_text())
        result = import_json(store, payload, actor=args.actor)
    elif args.manual:
        kwargs = _parse_manual(args.manual)
        result = import_manual(store, actor=args.actor, **kwargs)
    elif args.scanner:
        if not args.file:
            _fail("missing-scanner-file", "--file is required with --scanner")
        raw_text = Path(args.file).read_text()
        result = import_scanner_output(store, args.scanner, raw_text, actor=args.actor)
    else:  # pragma: no cover
        parser.print_help(sys.stderr)
        return 2

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
