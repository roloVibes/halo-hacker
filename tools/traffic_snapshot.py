#!/usr/bin/env python3
"""Halo Hacker traffic evidence snapshots (G4, from _research/ARTEX-REVIEW.md).

When a finding's evidence is an HTTP request/response, the live Caido
project's own churn must not be able to invalidate it. This module turns a
normalized exchange (tools/caido_adapter.normalize_exchange output) into a
hash-pinned SNAPSHOT stored on the engagement tree:

    <state>/engagements/<eng-id>/evidence/snapshots/<snapshot_id>.json

A snapshot pins url/method/status, the sanitized heads, body lengths, and
the SHA-256 of each body — the shape ARTEX calls traffic_evidence_snapshots
(design-only lineage; independent implementation). The finding's
evidence[].ledger_ref resolves to the findings-store ledger row; the
snapshot id rides the ledger row's meta so the captured exchange survives
independently of Caido.

Bodies are stored SANITIZED (the adapter's redaction has already run) —
evidence never carries credentials. Stdlib-only; fail-loud.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional


class SnapshotError(Exception):
    """Refusals are the store working, not failing."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".snap-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def snapshot_id_for(exchange: dict) -> str:
    """A stable id for one exchange: sha256 over its canonical request line
    + response status + body hashes. Identical re-captures dedupe."""
    req = exchange.get("request") or {}
    resp = exchange.get("response") or {}
    key = "|".join([
        str(req.get("method") or "").upper(),
        str(req.get("url") or ""),
        str(resp.get("status") or ""),
        _sha256((req.get("body") or "").encode()),
        _sha256((resp.get("body") or "").encode()),
    ])
    return "snap-" + _sha256(key.encode())[:16]


class SnapshotStore:
    """Hash-pinned traffic snapshots on the engagement tree."""

    def __init__(self, engagement_root: Path):
        self.root = Path(engagement_root)
        self.dir = self.root / "evidence" / "snapshots"

    def pin(self, exchange: dict) -> dict:
        """Store a snapshot of one normalized exchange; returns the record.
        The exchange MUST already be sanitized (the adapter sets the flag);
        unsanitized input is refused, never pinned."""
        if exchange.get("sanitized") is not True:
            raise SnapshotError(
                "refusing to pin an unsanitized exchange — run it through "
                "caido_adapter.normalize_exchange first")
        req = exchange.get("request") or {}
        resp = exchange.get("response") or {}
        req_body = (req.get("body") or "").encode()
        resp_body = (resp.get("body") or "").encode()
        snap = {
            "snapshot_id": snapshot_id_for(exchange),
            "captured_at": _now(),
            "method": (req.get("method") or "").upper(),
            "url": req.get("url") or "",
            "status": resp.get("status"),
            "req_head": json.dumps(req.get("headers") or {}, sort_keys=True),
            "resp_head": json.dumps(resp.get("headers") or {}, sort_keys=True),
            "req_hash": _sha256(req_body),
            "resp_hash": _sha256(resp_body),
            "req_len": len(req_body),
            "resp_len": len(resp_body),
            "redactions": exchange.get("redactions") or [],
            "source_exchange_id": exchange.get("source_exchange_id"),
            # The sanitized bodies are kept verbatim so evidence quotes can be
            # re-checked (tools/quote_verify.py) without re-touching Caido.
            # JSON can't hold raw compressed bytes losslessly, so bodies are
            # stored base64; quote_verify decodes (then gunzips) before check.
            "req_body_b64": base64.b64encode(req_body).decode(),
            "resp_body_b64": base64.b64encode(resp_body).decode(),
        }
        _atomic_write(self.dir / f"{snap['snapshot_id']}.json",
                      json.dumps(snap, indent=2))
        return snap

    def get(self, snapshot_id: str) -> dict:
        p = self.dir / f"{snapshot_id}.json"
        if not p.exists():
            raise SnapshotError(f"no such snapshot: {snapshot_id}")
        return json.loads(p.read_text())

    def list(self) -> list:
        if not self.dir.exists():
            return []
        return [json.loads(p.read_text()) for p in sorted(self.dir.glob("snap-*.json"))]

    def verify_integrity(self, snapshot_id: str) -> list:
        """Re-hash the stored bodies against the pinned hashes. Returns an
        empty list if intact; one line per problem otherwise."""
        problems: list = []
        snap = self.get(snapshot_id)
        import base64
        if _sha256(base64.b64decode(snap["req_body_b64"])) != snap["req_hash"]:
            problems.append(f"{snapshot_id}: request body hash mismatch")
        if _sha256(base64.b64decode(snap["resp_body_b64"])) != snap["resp_hash"]:
            problems.append(f"{snapshot_id}: response body hash mismatch")
        return problems
