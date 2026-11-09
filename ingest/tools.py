"""The five ingestion tools — shared by the MCP server and the CLI.

No policy of its own: the library's guards (privacy filter, trust tiers,
no-delete store, refusal-biased upserts) are the policy. Launched inside a
halo session the server inherits the harness's lanes/governor; standalone
it still works but must be pointed at a local model.
"""

from __future__ import annotations

import os

from ingest import adapters, pipeline
from ingest.model_client import OllamaClient, OpenRouterClient
from ingest.store import Store


def _config_str(key: str, default: str = "") -> str:
    """Read a pack setting through Halo's extension API when available.

    The server normally runs under Halo (PYTHONPATH carries halo_harness);
    standalone (tests, manual runs) falls back to the default.
    """
    try:
        from halo_harness.ext import get_config  # type: ignore

        value = get_config("halo-hacker", key, default)
        return str(value) if value else default
    except Exception:
        return default


def _client():
    """Local lane by default. Hosted = explicit opt-in via HALO_HACKER_HOSTED=1
    (privacy: user content leaves the machine)."""
    if os.environ.get("HALO_HACKER_HOSTED") == "1":
        return OpenRouterClient()
    return OllamaClient()


def _vault_root() -> str:
    """Where the knowledge base lives: env var first (explicit per-launch
    override), then the pack's `vault` config key (halo config set
    packs.settings.halo-hacker.vault <path>), else empty = refuse."""
    return os.environ.get("HALO_HACKER_VAULT") or _config_str("vault")


def _store():
    vault = _vault_root()
    if not vault:
        return {"ok": False, "error": "no vault set — set HALO_HACKER_VAULT or `halo config set packs.settings.halo-hacker.vault <path>`"}
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
