#!/usr/bin/env python3
"""Halo Hacker findings store — the engagement-tree runtime (Milestone 4).

Implements the ENGAGEMENT-MODEL.md design (halo-harness-cyber lineage):

    <state>/engagements/<eng-id>/
      engagement.json        scope + authorization (schema-validated)
      evidence/
        ledger.jsonl         append-only, HASH-CHAINED
        artifacts/<sha256>/  content-addressed blobs
      findings/<finding-id>/finding.json
      report/report.md       GENERATED, never hand-written

Hard rules, mechanically enforced:
- NO DELETE VERB. The store refuses to remove findings, evidence rows or
  artifacts. Removal is a human action in the editor.
- Chain tampering is detectable: verify_chain() re-walks the ledger.
- A finding that does not pass finding.schema.json never lands.
- Findings persist across sessions and model changes (plain JSON on disk).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

try:
    import jsonschema
except ImportError:  # tests always run with it; store degrades to no gate
    jsonschema = None

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / f"{name}.schema.json").read_text())


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FindingStoreError(Exception):
    """Refusals are the store working, not failing."""


class FindingStore:
    def __init__(self, engagement_root: Path):
        self.root = Path(engagement_root)
        self.evidence = self.root / "evidence"
        self.ledger = self.evidence / "ledger.jsonl"
        self.artifacts = self.evidence / "artifacts"
        self.findings_dir = self.root / "findings"
        self.report_dir = self.root / "report"

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def create(cls, engagement_root: Path, engagement: dict) -> "FindingStore":
        """Create the engagement tree. The engagement record MUST pass
        engagement.schema.json — no engagement object without a valid,
        signed-scope-shaped record."""
        root = Path(engagement_root)
        if (root / "engagement.json").exists():
            raise FindingStoreError(f"engagement already exists at {root}")
        if jsonschema is not None:
            jsonschema.validate(engagement, _load_schema("engagement"))
        for d in (root, root / "evidence" / "artifacts", root / "findings",
                  root / "report", root / "context"):
            d.mkdir(parents=True, exist_ok=True)
        (root / "engagement.json").write_text(json.dumps(engagement, indent=2))
        return cls(root)

    def engagement(self) -> dict:
        return json.loads((self.root / "engagement.json").read_text())

    # -- evidence (hash-chained ledger + content-addressed artifacts) ------

    def add_evidence(self, content: bytes, *, actor: str, action: str,
                     finding_id: Optional[str] = None,
                     meta: Optional[dict] = None) -> dict:
        """Store an artifact (content-addressed) and append a chained row.
        Identical content dedupes naturally (same sha256 dir)."""
        sha = _sha256(content)
        art_dir = self.artifacts / sha
        if not art_dir.exists():
            art_dir.mkdir(parents=True)
            (art_dir / "artifact.bin").write_bytes(content)
        rows = self._read_rows()
        prev = rows[-1]["hash"] if rows else "0" * 64
        row = {
            "seq": len(rows),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "actor": actor,
            "action": action,
            "artifact_sha256": sha,
            "finding_id": finding_id,
            "meta": meta or {},
            "prev_hash": prev,
        }
        row["hash"] = _sha256(_canonical(row).encode())
        with self.ledger.open("a") as f:
            f.write(json.dumps(row) + "\n")
        return row

    def _read_rows(self) -> list:
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in
                self.ledger.read_text().splitlines() if line.strip()]

    def verify_chain(self) -> list[str]:
        """Re-walk the ledger. Returns a empty list if intact; one plain
        line per problem otherwise (tampering/removal is detectable)."""
        problems: list[str] = []
        rows = self._read_rows()
        prev = "0" * 64
        for expect_seq, row in enumerate(rows):
            if row.get("seq") != expect_seq:
                problems.append(f"row {expect_seq}: bad seq {row.get('seq')}")
            if row.get("prev_hash") != prev:
                problems.append(f"row {expect_seq}: prev_hash mismatch "
                                f"(chain broken or a row was removed)")
            claimed = row.get("hash")
            body = {k: v for k, v in row.items() if k != "hash"}
            if _sha256(_canonical(body).encode()) != claimed:
                problems.append(f"row {expect_seq}: hash mismatch (row tampered)")
            prev = claimed
            # artifact integrity
            sha = row.get("artifact_sha256")
            if sha:
                p = self.artifacts / str(sha) / "artifact.bin"
                if not p.exists():
                    problems.append(f"row {expect_seq}: artifact {sha[:12]}… missing")
                elif _sha256(p.read_bytes()) != sha:
                    problems.append(f"row {expect_seq}: artifact {sha[:12]}… hash mismatch")
        return problems

    def evidence_rows(self, finding_id: Optional[str] = None) -> list:
        rows = self._read_rows()
        return [r for r in rows if finding_id is None or r.get("finding_id") == finding_id]

    # -- findings (gated, no delete) ---------------------------------------

    def put_finding(self, finding: dict) -> Path:
        """Insert or update a finding. MUST pass finding.schema.json.
        There is no delete: supersede by status change, never removal."""
        if jsonschema is not None:
            jsonschema.validate(finding, _load_schema("finding"))
        d = self.findings_dir / finding["finding_id"]
        d.mkdir(parents=True, exist_ok=True)
        path = d / "finding.json"
        path.write_text(json.dumps(finding, indent=2))
        return path

    def get_finding(self, finding_id: str) -> dict:
        p = self.findings_dir / finding_id / "finding.json"
        if not p.exists():
            raise FindingStoreError(f"no such finding: {finding_id}")
        return json.loads(p.read_text())

    def list_findings(self, status: Optional[str] = None) -> list[dict]:
        out = []
        if not self.findings_dir.exists():
            return out
        for p in sorted(self.findings_dir.glob("*/finding.json")):
            f = json.loads(p.read_text())
            if status is None or f.get("status") == status:
                out.append(f)
        return out

    def mark_duplicate(self, finding_id: str, duplicate_of: str, actor: str) -> dict:
        """Judge operation: mark a finding as a duplicate of another,
        recording the audit entry. Refuses self-duplicates."""
        if finding_id == duplicate_of:
            raise FindingStoreError("a finding cannot duplicate itself")
        f = self.get_finding(finding_id)
        self.get_finding(duplicate_of)  # must exist
        f["status"] = "duplicate"
        f["duplicate_of"] = duplicate_of
        f.setdefault("audit_history", []).append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "actor": actor, "action": "marked-duplicate",
            "detail": f"duplicate of {duplicate_of}"})
        self.put_finding(f)
        return f

    # -- the rule that has no method --------------------------------------

    def delete_finding(self, *args, **kwargs):  # pragma: no cover
        raise FindingStoreError(
            "no delete verb, ever — removal is a human action in the editor")
