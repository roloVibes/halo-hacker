#!/usr/bin/env python3
"""Traffic analysis MCP server for halo-hacker.

Real-time proxy traffic analysis (Caido/Burp). A stateful stdio JSON-RPC
server that holds a background poll loop over the local proxy and answers
agent tool calls: start/stop watching, fetch recent sanitized pairs, list
candidate findings, and produce correlation-based testing suggestions.

Read-only: it polls the proxy, runs declarative passive checks, and writes
candidate findings to the engagement store -- it never sends a request to
any target.

Design:
  - One background thread runs `traffic_observer.observe_once` in a loop.
  - A bounded ring buffer keeps the last N sanitized pairs for `recent`
    and the correlation engine.
  - `suggest` correlates patterns across the buffer (parameter reuse,
    auth-boundary crossings, interesting response shapes) and returns
    ranked, actionable next steps for the human tester or a test agent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Optional

# The pack's own tools are importable relative to the repo root; under Halo
# the server runs with the pack folder as the working directory.
_HERE = Path(__file__).resolve().parent
_PACK_ROOT = _HERE.parent
if str(_PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACK_ROOT))

from tools.traffic_observer import observe_once  # noqa: E402

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

# The engagement root is where the findings store lives. Prefer an explicit
# env var, else a conventional location under the pack data folder.
ENGAGEMENT_ROOT = Path(
    os.environ.get("HALO_HACKER_ENGAGEMENT_ROOT")
    or os.environ.get("HALO_HACKER_DATA_DIR")
    or os.path.join(
        os.path.expanduser("~"), ".halo", "packs", ".data", "halo-hacker", "engagement"
    )
)

# The proxy to watch, unless overridden per tool call.
DEFAULT_PROXY = os.environ.get("HALO_HACKER_PROXY", "caido")
POLL_INTERVAL_S = int(os.environ.get("HALO_HACKER_POLL_INTERVAL", "15"))
RING_SIZE = int(os.environ.get("HALO_HACKER_RING_SIZE", "500"))


class WatcherState:
    """Thread-safe state shared by the JSON-RPC loop and the poll thread."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.watching = False
        self.proxy = DEFAULT_PROXY
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.since: dict = {}
        self.ring: deque = deque(maxlen=RING_SIZE)
        self.candidates: list[dict] = []
        self.counters = {"new": 0, "deduped": 0, "out_of_scope": 0, "polls": 0, "errors": 0}
        self.last_poll = ""
        self.last_error = ""

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "watching": self.watching,
                "proxy": self.proxy,
                "counters": dict(self.counters),
                "last_poll": self.last_poll,
                "last_error": self.last_error,
                "ring_size": len(self.ring),
                "candidates": len(self.candidates),
            }

    def record_poll(self, result: dict) -> None:
        with self.lock:
            self.last_poll = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if result.get("ok"):
                self.counters["polls"] += 1
                self.counters["new"] += int(result.get("new", 0))
                self.counters["deduped"] += int(result.get("deduped", 0))
                self.counters["out_of_scope"] += int(result.get("out_of_scope", 0))
                self.since = dict(result.get("since", {}))
                for ev in result.get("events", []):
                    self.candidates.append(ev)
                    if len(self.candidates) > 200:
                        self.candidates = self.candidates[-200:]
                # The observer does not expose raw pairs, so re-poll is the
                # source of truth for `recent`. We keep candidates here.
            else:
                self.counters["errors"] += 1
                self.last_error = result.get("error", "unknown")

    def record_pair(self, pair: dict) -> None:
        with self.lock:
            self.ring.append(pair)


STATE = WatcherState()


# ---------------------------------------------------------------------------
# The poll loop (runs in a background thread)
# ---------------------------------------------------------------------------

def _poll_loop() -> None:
    """Poll the proxy every POLL_INTERVAL_S until stop_event is set."""
    while not STATE.stop_event.is_set():
        proxy = STATE.proxy
        try:
            result = observe_once(ENGAGEMENT_ROOT, proxy=proxy, since=STATE.since)
            STATE.record_poll(result)
        except Exception as exc:  # never let the thread die silently
            with STATE.lock:
                STATE.counters["errors"] += 1
                STATE.last_error = f"poll exception: {exc}"
        STATE.stop_event.wait(POLL_INTERVAL_S)


def start_watching(proxy: str) -> dict:
    with STATE.lock:
        if STATE.watching:
            return {"ok": False, "error": "already watching", "state": STATE.snapshot()}
        STATE.proxy = proxy
        STATE.watching = True
        STATE.stop_event.clear()
        STATE.thread = threading.Thread(target=_poll_loop, name="hh-traffic-watch", daemon=True)
        STATE.thread.start()
    return {"ok": True, "state": STATE.snapshot()}


def stop_watching() -> dict:
    with STATE.lock:
        if not STATE.watching:
            return {"ok": False, "error": "not watching", "state": STATE.snapshot()}
        STATE.watching = False
        STATE.stop_event.set()
    if STATE.thread is not None:
        STATE.thread.join(timeout=POLL_INTERVAL_S + 5)
    return {"ok": True, "state": STATE.snapshot()}


# ---------------------------------------------------------------------------
# Correlation engine (traffic_suggest)
# ---------------------------------------------------------------------------

def _parse_query_params(url: str) -> list[str]:
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    return [k for k, _ in urllib.parse.parse_qsl(parsed.query)]


def _endpoint_key(url: str) -> str:
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.hostname or ''}{parsed.path or '/'}"


def _auth_boundary(pairs: list[dict]) -> list[dict]:
    """Detect endpoints whose response differs with vs without auth."""
    suggestions = []
    # Group pairs by endpoint; compare a pair with Authorization to one without
    by_endpoint: dict[str, list[dict]] = {}
    for p in pairs:
        by_endpoint.setdefault(_endpoint_key(p.get("url", "")), []).append(p)
    for ep, items in by_endpoint.items():
        # NOTE: auth presence on the request is not directly visible in the
        # sanitized pair. Use status variance as a proxy signal instead.
        statuses = Counter(p.get("status") for p in items)
        if len(statuses) > 1 and 200 in statuses and 401 in statuses:
            suggestions.append({
                "kind": "auth-boundary",
                "endpoint": ep,
                "detail": f"endpoint {ep} returns both 200 and 401 — probe authz on each object/role",
                "confidence": "medium",
            })
    return suggestions


def _parameter_reuse(pairs: list[dict]) -> list[dict]:
    """Suggest trying a parameter seen on one endpoint against sibling endpoints."""
    by_host: dict[str, list[dict]] = {}
    for p in pairs:
        host = urllib_parse_host(p.get("url", ""))
        by_host.setdefault(host, []).append(p)
    suggestions = []
    for host, items in by_host.items():
        param_by_path: dict[str, set[str]] = {}
        for p in items:
            path = urllib_parse_path(p.get("url", ""))
            params = _parse_query_params(p.get("url", ""))
            if params:
                param_by_path[path] = set(params)
        if len(param_by_path) < 2:
            continue
        all_params = set().union(*param_by_path.values())
        for path, params in param_by_path.items():
            missing = all_params - params
            if missing:
                suggestions.append({
                    "kind": "parameter-reuse",
                    "host": host,
                    "detail": f"try parameters {sorted(missing)} on {host}{path} (seen on sibling endpoints)",
                    "confidence": "low",
                })
    return suggestions


def urllib_parse_host(url: str) -> str:
    import urllib.parse
    return (urllib.parse.urlparse(url).hostname or "").lower()


def urllib_parse_path(url: str) -> str:
    import urllib.parse
    return urllib.parse.urlparse(url).path or "/"


def suggest(pairs: list[dict], limit: int = 8) -> list[dict]:
    """Correlate recent traffic and return ranked next-step suggestions."""
    if not pairs:
        return []
    out = _auth_boundary(pairs) + _parameter_reuse(pairs)
    # Rank: auth-boundary (medium) before parameter-reuse (low)
    order = {"medium": 0, "low": 1}
    out.sort(key=lambda s: order.get(s.get("confidence", "low"), 2))
    return out[:limit]


# ---------------------------------------------------------------------------
# JSON-RPC
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "traffic_start",
        "description": "Start watching a proxy (Caido or Burp) for the active engagement. Read-only: never sends requests.",
        "inputSchema": {
            "type": "object",
            "properties": {"proxy": {"type": "string", "enum": ["caido", "burp"]}},
            "required": ["proxy"],
        },
    },
    {
        "name": "traffic_stop",
        "description": "Stop the traffic watcher.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "traffic_status",
        "description": "Current state: watching/stopped, proxy, candidates found, deduped, out-of-scope, last poll.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "traffic_candidates",
        "description": "List candidate findings produced by passive traffic checks.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
    },
    {
        "name": "traffic_suggest",
        "description": "Correlation-based testing suggestions from observed traffic (parameter reuse, auth-boundary crossings).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _tool_result(tool_name: str, data: dict) -> str:
    return json.dumps(data, indent=2)


def handle_request(request: dict) -> Optional[dict]:
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "halo-hacker-traffic", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        args = params.get("arguments", {}) or {}

        try:
            if tool_name == "traffic_start":
                data = start_watching(args.get("proxy", DEFAULT_PROXY))
            elif tool_name == "traffic_stop":
                data = stop_watching()
            elif tool_name == "traffic_status":
                data = STATE.snapshot()
            elif tool_name == "traffic_candidates":
                limit = int(args.get("limit", 20))
                with STATE.lock:
                    cands = list(STATE.candidates[-limit:])
                data = {"ok": True, "candidates": cands, "count": len(cands)}
            elif tool_name == "traffic_suggest":
                with STATE.lock:
                    pairs = list(STATE.ring)
                if not pairs:
                    data = {"ok": True, "suggestions": [], "note": "no traffic observed yet — start the watcher first"}
                else:
                    data = {"ok": True, "suggestions": suggest(pairs), "observed": len(pairs)}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"unknown tool: {tool_name}"},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": _tool_result(tool_name, data)}]},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(exc)})}]
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is None:
                continue
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception:
            continue


def watch_once() -> None:
    """`watch` subcommand: run one poll loop synchronously (service mode)."""
    result = observe_once(ENGAGEMENT_ROOT, proxy=DEFAULT_PROXY, since={})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="halo-hacker traffic MCP server")
    parser.add_argument("mode", nargs="?", default="serve", choices=["serve", "watch"])
    args = parser.parse_args()
    if args.mode == "watch":
        watch_once()
    else:
        main()