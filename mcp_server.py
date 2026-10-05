"""halo-hacker MCP server — the in-session surface (primary mode).

Tools: ingest_notes, ingest_pdf, ingest_github, ingest_youtube, ingest_status.
Runs the same library the CLI uses; no policy of its own. Launched inside a halo
session it inherits the harness's lanes/governor; standalone it still works but
must be pointed at a local model.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest import adapters, pipeline
from ingest.model_client import OllamaClient, OpenRouterClient, ModelError
from ingest.store import Store


def _client():
    """Local lane by default. Hosted = explicit opt-in via HALO_HACKER_HOSTED=1
    (privacy: user content leaves the machine)."""
    if os.environ.get("HALO_HACKER_HOSTED") == "1":
        return OpenRouterClient()
    return OllamaClient()


def _store() -> Store:
    vault = os.environ.get("HALO_HACKER_VAULT")
    if not vault:
        return {"ok": False, "error": "HALO_HACKER_VAULT not set — point it at your vault root"}
    return Store(vault)


def ingest_notes(root: str, dry_run: bool = False) -> dict:
    """Ingest a directory tree of cyber notes (markdown/txt). First-party tier.
    Returns the full report: n_in/n_kept/n_dropped + filed/duplicates/refused/errors.
    A high refusal rate is correct behaviour, not a failure."""
    docs, skipped = adapters.scan_tree(root)
    store = _store()
    if isinstance(store, dict):
        return store
    report = pipeline.run(docs, store,
                          lambda d: pipeline.model_classify(_client(), d),
                          lambda d: pipeline.model_distill(_client(), d),
                          dry_run=dry_run)
    report["skipped_unreadable"] = [{"path": p, "reason": r} for p, r in skipped]
    report["ok"] = True
    return report


def ingest_pdf(path: str) -> dict:
    """Ingest ONE PDF (report/whitepaper). First-party tier. Fails loudly on
    encrypted or scanned (no-text) PDFs — run ocrmypdf first for scans."""
    store = _store()
    if isinstance(store, dict):
        return store
    doc = adapters.read_pdf(path)
    report = pipeline.run([doc], store,
                          lambda d: pipeline.model_classify(_client(), d),
                          lambda d: pipeline.model_distill(_client(), d))
    report["ok"] = True
    return report


def ingest_github(url: str) -> dict:
    """Ingest ONE file from a public GitHub repo (blob or raw URL). Third-party
    tier: filed as a lead requiring corroboration."""
    store = _store()
    if isinstance(store, dict):
        return store
    doc = adapters.fetch_github(url)
    report = pipeline.run([doc], store,
                          lambda d: pipeline.model_classify(_client(), d),
                          lambda d: pipeline.model_distill(_client(), d))
    report["ok"] = True
    return report


def ingest_youtube(url: str) -> dict:
    """Ingest ONE YouTube video via its subtitles (yt-dlp). Third-party tier."""
    store = _store()
    if isinstance(store, dict):
        return store
    doc = adapters.fetch_youtube(url)
    report = pipeline.run([doc], store,
                          lambda d: pipeline.model_classify(_client(), d),
                          lambda d: pipeline.model_distill(_client(), d))
    report["ok"] = True
    return report


def ingest_status() -> dict:
    """Ledger summary: rows, per-domain counts, per-trust-tier counts."""
    store = _store()
    if isinstance(store, dict):
        return store
    rows = store.rows()
    by_domain, by_tier = {}, {}
    for r in rows:
        dom = r["dest"].split(os.sep)[-2] if os.sep in r["dest"] else "?"
        by_domain[dom] = by_domain.get(dom, 0) + 1
        by_tier[r["trust_tier"]] = by_tier.get(r["trust_tier"], 0) + 1
    return {"ok": True, "rows": len(rows), "by_domain": by_domain, "by_tier": by_tier}


TOOLS = (ingest_notes, ingest_pdf, ingest_github, ingest_youtube, ingest_status)


def main() -> int:
    if "--selftest" in sys.argv:
        # No-network sanity: imports resolve and the VAULT GUARD fires on every
        # tool when HALO_HACKER_VAULT is unset (refuse-before-touching-anything).
        for fn, arg in [(ingest_notes, "/nonexistent"), (ingest_pdf, "/nonexistent.pdf"),
                        (ingest_github, "https://github.com/x/y/blob/main/z.md"),
                        (ingest_youtube, "https://youtu.be/x"), (ingest_status, None)]:
            r = fn(arg) if arg is not None else fn()
            assert r.get("ok") is False and "HALO_HACKER_VAULT" in r.get("error", ""), (fn, r)
        print("halo-hacker selftest OK — 5 tools, vault guard fires on all of them")
        return 0
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("MCP SDK not installed: uv pip install 'mcp>=1,<2'", file=sys.stderr)
        return 1
    mcp = FastMCP("halo-hacker")
    for fn in TOOLS:
        mcp.tool()(fn)
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
