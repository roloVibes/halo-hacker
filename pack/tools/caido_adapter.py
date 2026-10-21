#!/usr/bin/env python3
"""Halo Hacker Caido adapter (Milestone 3, DRAFT — read-only).

Caido (https://caido.io) is the HTTP proxy this pack targets for traffic
analysis: permitted HTTP history, site map, request/response inspection,
and controlled replay PREPARATION (a prepared replay still goes through
the engagement's approval gate — this adapter never sends on its own).

Scope of this module (deliberately narrow):
- A read-only client over Caido's local API, endpoint configurable.
- Normalization of intercepted requests/responses into the pack's
  sanitized observation shape for the recon pipeline.

STATUS: DRAFT. The request/response shapes against a LIVE Caido instance
are NOT yet verified (no instance reachable at build time — see
INTEGRATION_STATUS.md). The offline fixtures in tests/ pin the
normalization; the transport layer must be verified live before any
non-draft use. Prefers a documented MCP interface when one exists
(CORE_REQUESTS.md CR-6 notes the gap).
"""
from __future__ import annotations

import json
from typing import Optional

REDACT_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key",
                  "proxy-authorization", "x-csrf-token"}


def sanitize_headers(headers: dict) -> dict:
    """Credential-bearing headers never enter evidence as-is."""
    out = {}
    for k, v in (headers or {}).items():
        out[k] = "[REDACTED]" if k.lower() in REDACT_HEADERS else v
    return out


def normalize_exchange(exchange: dict) -> dict:
    """A Caido interception (request+response) -> sanitized observation.

    Expected input shape (fixture-pinned; verify against live API):
      {"id": "...", "request": {"method", "path", "host", "headers", "body"},
       "response": {"status", "headers", "body"}}
    """
    req = exchange.get("request") or {}
    resp = exchange.get("response") or {}
    return {
        "kind": "request-response",
        "sanitized": True,
        "request": {
            "method": req.get("method"),
            "url": f"{req.get('scheme', 'https')}://{req.get('host')}{req.get('path', '')}",
            "headers": sanitize_headers(req.get("headers")),
            "body_len": len(req.get("body") or ""),
            "body": (req.get("body") or "")[:2000],  # truncated, sanitized upstream
        },
        "response": {
            "status": resp.get("status"),
            "headers": sanitize_headers(resp.get("headers")),
            "body_len": len(resp.get("body") or ""),
            "body": (resp.get("body") or "")[:2000],
        },
        "source_exchange_id": exchange.get("id"),
    }


class CaidoClient:
    """Read-only transport. Only list/get operations; no send, no modify.

    The base URL and credentials come from the user's Caido configuration
    (never stored here). All methods raise CaidoUnavailable rather than
    guessing when the API shape doesn't match — fail loud, fail safe.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:7230",
                 api_token: Optional[str] = None, session=None):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._session = session  # injectable for tests; None = unverified

    def _get(self, path: str):
        if self._session is None:
            raise CaidoUnavailable(
                "live Caido transport not verified yet (draft adapter); "
                "see INTEGRATION_STATUS.md before use")
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        r = self._session.get(self.base_url + path, headers=headers, timeout=10)
        if r.status_code != 200:
            raise CaidoUnavailable(f"Caido API {path} returned {r.status_code}")
        return r.json()

    def list_exchanges(self, limit: int = 50):
        return self._get(f"/api/exchanges?limit={limit}")

    def get_exchange(self, exchange_id: str):
        return self._get(f"/api/exchanges/{exchange_id}")


class CaidoUnavailable(Exception):
    pass
