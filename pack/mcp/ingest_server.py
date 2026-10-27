"""halo-hacker ingestion MCP server — the in-session surface (primary mode).

Tools: ingest_notes, ingest_pdf, ingest_github, ingest_youtube, ingest_status.
The implementations live in pack/ingest/tools.py (shared with pack/cli.py);
this file is only the stdio JSON-RPC wire — standard library only, no MCP
SDK dependency (the SDK renamed FastMCP between 1.x and 2.x; a hand-rolled
server, like the one in Halo's own doc-review template pack, works under
any Halo). One JSON message per line.

Launched inside a halo session it inherits the harness's lanes/governor;
standalone it still works but must be pointed at a local model.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest.tools import (  # noqa: E402
    ingest_github,
    ingest_notes,
    ingest_pdf,
    ingest_status,
    ingest_youtube,
)

try:
    from halo_harness.ext import API_VERSION
except ImportError:  # the `python` on PATH is not the one Halo runs in
    API_VERSION = "1.0"

_TOOL_FNS = {
    "ingest_notes": ingest_notes,
    "ingest_pdf": ingest_pdf,
    "ingest_github": ingest_github,
    "ingest_youtube": ingest_youtube,
    "ingest_status": ingest_status,
}

TOOLS = [
    {"name": "ingest_notes", "description": ingest_notes.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"root": {"type": "string", "description": "directory tree of notes (markdown/txt)"},
                                    "dry_run": {"type": "boolean", "description": "run the filters, write nothing"}},
                     "required": ["root"]}},
    {"name": "ingest_pdf", "description": ingest_pdf.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string", "description": "one PDF (report/whitepaper)"}},
                     "required": ["path"]}},
    {"name": "ingest_github", "description": ingest_github.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"url": {"type": "string", "description": "one public GitHub file (blob or raw URL)"}},
                     "required": ["url"]}},
    {"name": "ingest_youtube", "description": ingest_youtube.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"url": {"type": "string", "description": "one YouTube video (subtitles via yt-dlp)"}},
                     "required": ["url"]}},
    {"name": "ingest_status", "description": ingest_status.__doc__.strip(),
     "inputSchema": {"type": "object", "properties": {}}},
]


def call_tool(name: str, args: dict) -> dict:
    fn = _TOOL_FNS.get(name)
    if fn is None:
        return {"content": [{"type": "text", "text": f"no tool {name}"}], "isError": True}
    try:
        result = fn(**(args or {}))
    except TypeError as bad_args:
        return {"content": [{"type": "text", "text": f"{name}: {bad_args}"}], "isError": True}
    except Exception as e:  # a refused/failed ingestion is data, not a crash
        return {"content": [{"type": "text", "text": json.dumps({"ok": False, "error": str(e)})}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": False}


def answer(msg: dict):
    """The reply to one request (None for a notification)."""
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "halo-hacker-ingest", "version": "1.0.0", "extensionApi": API_VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def main() -> int:
    if "--selftest" in sys.argv:
        # No-network sanity: imports resolve and the vault guard fires on every
        # tool when no vault is configured (refuse-before-touching-anything).
        for name, fn in _TOOL_FNS.items():
            arg = None if name == "ingest_status" else "/nonexistent"
            r = fn(arg) if arg is not None else fn()
            assert r.get("ok") is False and "vault" in r.get("error", "").lower(), (name, r)
        print("halo-hacker selftest OK — 5 tools, vault guard fires on all of them")
        return 0
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        reply = answer(msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
