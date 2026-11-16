#!/usr/bin/env python3
"""Halo Hacker evidence-quote verification (G2, from _research/ARTEX-REVIEW.md).

A finding's evidence quotes must VERBATIM appear in the captured response —
mechanically checked, never trusted to the model's assertion. This is the
gate ARTEX applies before a finding can reach 'verified' (design-only
lineage; independent implementation), mapped onto the pack's validator role.

The check is deliberately a TOOL, not a prompt instruction: doctrine never
relies on the model's good behavior (the standing boundary rule). The
validator calls verify_quotes() with the candidate quotes and the snapshot
id; confirmation is impossible when a quote does not resolve.

Encoding handling mirrors ARTEX: gzip/deflate bodies are decoded before the
quote check (a compressed capture must not false-negative a real quote).
"""
from __future__ import annotations

import gzip
import zlib
from pathlib import Path
from typing import Optional

from traffic_snapshot import SnapshotStore, SnapshotError


class QuoteVerificationError(Exception):
    pass


def _decode_body(body_b64: str, content_encoding: Optional[str]) -> bytes:
    """Return the body as bytes: base64-decode the stored form, then gunzip /
    inflate when the capture's Content-Encoding says so. A body that fails to
    decode is returned raw — the quote check runs against what was captured."""
    import base64
    try:
        raw = base64.b64decode(body_b64 or "")
    except Exception:
        raw = (body_b64 or "").encode("utf-8", errors="replace")
    enc = (content_encoding or "").lower().strip()
    try:
        if enc == "gzip":
            return gzip.decompress(raw)
        if enc in ("deflate", "zlib"):
            return zlib.decompress(raw)
    except Exception:
        return raw
    return raw


def _content_encoding_from_head(resp_head: str) -> Optional[str]:
    """resp_head is the JSON-serialized sanitized headers dict."""
    import json
    try:
        headers = json.loads(resp_head or "{}")
    except Exception:
        return None
    for k, v in headers.items():
        if k.lower() == "content-encoding":
            return str(v)
    return None


def verify_quotes(engagement_root: Path, snapshot_id: str,
                  quotes: "list[str]") -> dict:
    """Check each quote appears verbatim in the snapshot's (decoded) response
    body. Returns a report; raises nothing on ordinary misses — a miss is a
    RESULT, not an error, so the caller can report it as a finding-quality
    problem. Structural problems (no such snapshot) raise."""
    store = SnapshotStore(Path(engagement_root))
    snap = store.get(snapshot_id)  # raises SnapshotError if absent
    integrity = store.verify_integrity(snapshot_id)
    if integrity:
        raise QuoteVerificationError(
            "snapshot integrity check failed: " + "; ".join(integrity))

    enc = _content_encoding_from_head(snap.get("resp_head", ""))
    body = _decode_body(snap.get("resp_body_b64", ""), enc)

    results = []
    for q in quotes:
        needle = (q or "").encode("utf-8", errors="replace")
        results.append({
            "quote": q,
            "present": bool(needle) and needle in body,
        })
    return {
        "snapshot_id": snapshot_id,
        "content_encoding": enc or "identity",
        "quote_count": len(quotes),
        "verified_count": sum(1 for r in results if r["present"]),
        "all_verified": all(r["present"] for r in results) and bool(results),
        "results": results,
    }
