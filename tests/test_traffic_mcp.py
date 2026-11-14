"""Tests for the traffic MCP server's correlation engine and RPC handlers.

The engine is pure Python (no proxy, no network): it takes a list of
sanitized pairs and returns ranked suggestions. These tests pin that
behavior so the correlation logic can't silently break.
"""
from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

_PACK = Path(__file__).resolve().parent.parent
if str(_PACK) not in sys.path:
    sys.path.insert(0, str(_PACK))

# The mcp/ directory is not a package (it collides with the real `mcp`
# SDK module); load the traffic server by path.
def _load_traffic_server():
    spec = importlib.util.spec_from_file_location(
        "hh_traffic_server", str(_PACK / "mcp" / "traffic_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ts = _load_traffic_server()


def _pair(url, status=200, headers=None, body=""):
    return {"method": "GET", "url": url, "host": "target.example",
            "status": status, "response_headers": headers or {}, "response_body": body}


def test_parameter_reuse_suggestion():
    """A param seen on one endpoint suggests trying it on a sibling endpoint."""
    pairs = [
        _pair("https://target.example/api/users?id=1&role=admin"),
        _pair("https://target.example/api/orders?limit=10"),
    ]
    out = ts.suggest(pairs)
    kinds = {s["kind"] for s in out}
    assert "parameter-reuse" in kinds, out
    pr = [s for s in out if s["kind"] == "parameter-reuse"][0]
    assert "role" in pr["detail"] or "id" in pr["detail"] or "limit" in pr["detail"]


def test_auth_boundary_suggestion():
    """An endpoint returning both 200 and 401 flags an authz probe."""
    pairs = [
        _pair("https://target.example/api/me", status=200),
        _pair("https://target.example/api/me", status=401),
    ]
    out = ts.suggest(pairs)
    assert any(s["kind"] == "auth-boundary" for s in out), out


def test_no_traffic_returns_empty():
    assert ts.suggest([]) == []


def test_rpc_initialize_and_tools_list():
    init = ts.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "halo-hacker-traffic"

    listing = ts.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in listing["result"]["tools"]}
    assert {"traffic_start", "traffic_stop", "traffic_status",
            "traffic_candidates", "traffic_suggest"} <= names


def test_rpc_unknown_tool_is_clean_error():
    resp = ts.handle_request({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    # Unknown tool is an MCP error response, not a result.
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_status_snapshot_shape():
    snap = ts.STATE.snapshot()
    assert set(snap.keys()) == {
        "watching", "proxy", "counters", "last_poll", "last_error",
        "ring_size", "candidates",
    }
    assert snap["proxy"] in ("caido", "burp")
