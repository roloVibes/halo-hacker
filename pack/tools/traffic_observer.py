#!/usr/bin/env python3
"""Passive traffic observer for halo-hacker.

Watches a human tester's proxy traffic (Caido or Burp) and surfaces
read-only candidate findings. The observer never sends a request to any
target; it only polls the local proxy API and writes findings to the
engagement store.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from caido_adapter import SanitizationPolicy, sanitize_headers
from engage import _host_in_targets, load_engagement
from findings_store import FindingStore, FindingStoreError
from findings_view import data_dir, finding_event
from passive_checks import run_checks


CAIDO_GRAPHQL_URL = "http://127.0.0.1:8080/graphql"
BURP_URL = os.environ.get("BURP_URL", "http://127.0.0.1:1337")
BURP_API_KEY = os.environ.get("BURP_API_KEY")

_OBSERVER_STATE = "observer-state.json"


def _state_path() -> Path:
    return data_dir() / _OBSERVER_STATE


def _load_state() -> dict:
    p = _state_path()
    if not p.is_file():
        return {"seen": [], "cursors": {}}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"seen": [], "cursors": {}}


def _save_state(state: dict) -> None:
    _atomic_write(_state_path(), json.dumps(state, indent=2))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".obs-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _url_host(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return (parsed.hostname or "").lower()


def _url_path_without_query(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.path or "/"


def _dedup_key(check_id: str, host: str, path: str) -> str:
    return json.dumps([check_id, host.lower(), path], sort_keys=True)


def _load_targets(engagement_root: Path) -> list[dict]:
    eng = load_engagement(engagement_root)
    targets_file = eng.get("targets_file", "scope/targets.json")
    path = engagement_root / targets_file
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    return list(data.get("includes", []))


def _fetch_caido(since: dict) -> tuple[list[dict], dict]:
    """Minimal read-only GraphQL poll for Caido HTTP events.

    NOTE: this query shape is UNVERIFIED against a live Caido instance.
    Caido's GraphQL schema may use different field names; the adapter is
    draft and this transport layer must be verified live before any
    non-draft use (see caido_adapter.py and docs/INTEGRATION_STATUS.md).
    """
    offset = int(since.get("offset", 0))
    query = {
        "query": (
            "query RequestsEvents($offset: Int!) {"
            "  requestsEvents(offset: $offset) {"
            "    id"
            "    request { method path host headers body scheme }"
            "    response { status headers body }"
            "  }"
            "}"
        ),
        "variables": {"offset": offset},
    }
    body = json.dumps(query).encode()
    req = urllib.request.Request(
        CAIDO_GRAPHQL_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    events = []
    if data.get("data") and isinstance(data["data"].get("requestsEvents"), list):
        for ex in data["data"]["requestsEvents"]:
            req = ex.get("request") or {}
            resp = ex.get("response") or {}
            scheme = req.get("scheme") or "https"
            host = req.get("host") or ""
            path = req.get("path") or "/"
            url = f"{scheme}://{host}{path}"
            events.append({
                "method": req.get("method", "GET"),
                "url": url,
                "host": host,
                "status": resp.get("status") or resp.get("statusCode"),
                "response_headers": resp.get("headers") or {},
                "response_body": resp.get("body") or "",
            })
    # Advance cursor by count; Caido may expose a real nextOffset in future.
    next_since = {"offset": offset + len(events)}
    return events, next_since


def _parse_raw_response(raw: bytes) -> tuple[int, dict, str]:
    """Parse a raw HTTP response into status, headers, body. Best-effort."""
    # Split header block from body using the first double CRLF.
    parts = raw.split(b"\r\n\r\n", 1)
    if len(parts) < 2:
        parts = raw.split(b"\n\n", 1)
    head = parts[0].decode("utf-8", errors="replace")
    body = parts[1].decode("utf-8", errors="replace") if len(parts) > 1 else ""
    lines = head.splitlines()
    status = 0
    headers: dict = {}
    if lines:
        m = re.match(r"HTTP/\d\.\d\s+(\d+)", lines[0])
        if m:
            status = int(m.group(1))
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return status, headers, body


def _fetch_burp(since: dict) -> tuple[list[dict], dict]:
    """Poll Burp's REST API proxy history. Responses are raw HTTP base64."""
    offset = int(since.get("offset", 0))
    url = f"{BURP_URL.rstrip('/')}/v0.1/proxy/history?limit=100&offset={offset}"
    req = urllib.request.Request(url, method="GET")
    if BURP_API_KEY:
        req.add_header("Authorization", f"Bearer {BURP_API_KEY}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read().decode("utf-8", errors="replace"))
    events = []
    for item in items or []:
        raw_resp = base64.b64decode(item.get("response") or "")
        status, headers, body = _parse_raw_response(raw_resp)
        scheme = "https" if item.get("protocol") == "https" else "http"
        host = item.get("host") or ""
        port = item.get("port")
        path = "/"
        raw_req = base64.b64decode(item.get("request") or "")
        req_head = raw_req.split(b"\r\n", 1)[0].decode("utf-8", errors="replace")
        m = re.match(r"([A-Z]+)\s+(\S+)\s+HTTP", req_head)
        method = m.group(1) if m else "GET"
        path = m.group(2) if m else "/"
        if port and ((scheme == "http" and port != 80) or (scheme == "https" and port != 443)):
            host = f"{host}:{port}"
        url = f"{scheme}://{host}{path}"
        events.append({
            "method": method,
            "url": url,
            "host": urllib.parse.urlparse(url).hostname or host,
            "status": status or item.get("statusCode"),
            "response_headers": headers,
            "response_body": body,
        })
    next_since = {"offset": offset + len(events)}
    return events, next_since


def _redact_pair(pair: dict) -> dict:
    """Apply the pack's redaction rules to a traffic pair."""
    policy = SanitizationPolicy()
    headers, _ = sanitize_headers(pair.get("response_headers") or {})
    body, _ = policy.sanitize_body(pair.get("response_body") or "")
    return {
        "method": pair.get("method", "GET"),
        "url": pair.get("url", ""),
        "host": pair.get("host", ""),
        "status": pair.get("status", 0),
        "response_headers": headers,
        "response_body": body,
    }


def _make_slug(check_id: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", check_id.lower()).strip("-")


def _unique_finding_id(store: FindingStore, base_id: str) -> str:
    """Collision-safe finding_id: append a counter if one already exists."""
    def _exists(fid: str) -> bool:
        try:
            store.get_finding(fid)
            return True
        except FindingStoreError:
            return False

    if not _exists(base_id):
        return base_id
    for n in range(2, 1000):
        cand = f"{base_id}-{n}"
        if not _exists(cand):
            return cand
    raise RuntimeError("could not allocate a unique finding_id")


def _create_candidate(store: FindingStore, hit: dict, pair: dict,
                      engagement_id: str) -> dict:
    """Store one real ledger row and a candidate finding for a passive hit."""
    host = pair.get("host", "")
    path = _url_path_without_query(pair.get("url", ""))
    target_ref = f"{host}{path}"
    slug = _make_slug(hit["check_id"])
    base_id = f"pas-01-{slug}"
    finding_id = _unique_finding_id(store, base_id)

    evidence_text = json.dumps({
        "check_id": hit["check_id"],
        "host": host,
        "path": path,
        "status": pair.get("status"),
        "note": hit["evidence_note"],
        "response_headers": pair.get("response_headers", {}),
    }, sort_keys=True)
    row = store.add_evidence(
        evidence_text.encode(),
        actor="hh-traffic-observer",
        action="passive-hit",
        finding_id=finding_id,
        meta={
            "check_id": hit["check_id"],
            "host": host,
            "path": path,
            "url": pair.get("url", ""),
        },
    )

    finding = {
        "finding_id": finding_id,
        "engagement_id": engagement_id,
        "target_ref": target_ref,
        "title": hit["title"],
        "category": "passive-traffic:information-disclosure",
        "description": hit["description"],
        "status": "candidate",
        "source": "passive-traffic",
        "severity": hit["severity_hint"],
        "evidence": [{
            "ledger_ref": f"evidence/ledger.jsonl#{row['seq']:04d}",
            "artifact_sha256": row["artifact_sha256"],
            "kind": "request-response",
            "sanitized": True,
        }],
        "audit_history": [{
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "actor": "hh-traffic-observer",
            "action": "candidate-created",
            "detail": f"{hit['check_id']} on {target_ref}",
        }],
    }
    store.put_finding(finding)
    return finding


def observe_once(engagement_root, *, proxy: str, since: dict) -> dict:
    """Poll a proxy once, analyze new in-scope traffic, return candidates.

    Returns:
      {"ok": true, "events": [...], "new": N, "deduped": M, "out_of_scope": O,
       "since": {...}} on success.
      {"ok": false, "error": "network"} on proxy API failure.
      {"ok": false, "error": "..."} on other failures (never raises).
    """
    engagement_root = Path(engagement_root)
    result = {
        "ok": True,
        "events": [],
        "new": 0,
        "deduped": 0,
        "out_of_scope": 0,
        "since": dict(since),
    }
    try:
        store = FindingStore(engagement_root)
        engagement_id = store.engagement().get("engagement_id") or "unknown"
        targets = _load_targets(engagement_root)
        state = _load_state()
        seen = set(state.get("seen", []))

        if proxy == "caido":
            events, next_since = _fetch_caido(since)
        elif proxy == "burp":
            events, next_since = _fetch_burp(since)
        else:
            return {"ok": False, "error": f"unsupported proxy: {proxy}"}

        for pair in events:
            host = pair.get("host", "").lower()
            if not host or not _host_in_targets(host, targets):
                result["out_of_scope"] += 1
                continue

            redacted = _redact_pair(pair)
            path = _url_path_without_query(redacted["url"])
            hits = run_checks(redacted)

            for hit in hits:
                key = _dedup_key(hit["check_id"], host, path)
                if key in seen:
                    result["deduped"] += 1
                    continue
                seen.add(key)
                finding = _create_candidate(store, hit, redacted, engagement_id)
                result["events"].append(finding_event(finding, actor="hh-traffic-observer"))
                result["new"] += 1

        state["seen"] = sorted(seen)
        state["cursors"] = state.get("cursors", {})
        state["cursors"][proxy] = next_since
        _save_state(state)
        result["since"] = next_since
        return result

    except urllib.error.URLError as e:
        return {"ok": False, "error": "network", "detail": str(e)}
    except FindingStoreError as e:
        return {"ok": False, "error": f"store: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"observer: {e}"}


def _poll_loop(engagement_root: Path, proxy: str, interval: int) -> None:
    since: dict = {}
    while True:
        result = observe_once(engagement_root, proxy=proxy, since=since)
        if not result.get("ok"):
            print(f"[error] {result.get('error')} — {result.get('detail', '')}", file=sys.stderr)
        else:
            print(
                f"{result['new']} new passive candidates "
                f"({result['deduped']} deduped, {result['out_of_scope']} out-of-scope)"
            )
            since = result.get("since", {})
        time.sleep(interval)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Passive traffic observer for halo-hacker")
    parser.add_argument("engagement_root", help="Path to the engagement tree")
    parser.add_argument("--proxy", choices=["caido", "burp"], required=True)
    parser.add_argument("--once", action="store_true", help="Run one poll and exit")
    parser.add_argument("--interval", type=int, default=15, help="Poll interval in seconds")
    args = parser.parse_args()

    state = _load_state()
    since = state.get("cursors", {}).get(args.proxy, {})

    if args.once:
        result = observe_once(Path(args.engagement_root), proxy=args.proxy, since=since)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("ok") else 1)

    _poll_loop(Path(args.engagement_root), args.proxy, args.interval)


if __name__ == "__main__":
    _main()
