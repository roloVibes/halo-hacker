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
docs/INTEGRATION_STATUS.md). The offline fixtures in tests/ pin the
normalization; the transport layer must be verified live before any
non-draft use. Prefers a documented MCP interface when one exists
(docs/CORE_REQUESTS.md CR-6 notes the gap).
"""
from __future__ import annotations

import json
from typing import Optional

REDACT_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key",
                  "proxy-authorization", "x-csrf-token"}


def sanitize_headers(headers: dict) -> "tuple[dict, list[str]]":
    """Credential-bearing headers never enter evidence as-is.
    Returns (sanitized_headers, rules_fired)."""
    out, fired = {}, []
    for k, v in (headers or {}).items():
        if k.lower() in REDACT_HEADERS:
            out[k] = "[REDACTED]"
            fired.append(f"header:{k.lower()}")
        else:
            out[k] = v
    return out, fired


# Structured body redaction (2026-10-21 review: bodies carry tokens, PII,
# passwords and session secrets — header redaction alone is not
# "sanitized"). Each rule is (name, compiled_regex, replacement). The
# default set is conservative; users extend it via SanitizationPolicy.
import re as _re

DEFAULT_BODY_RULES: "list[tuple[str, _re.Pattern, str]]" = [
    ("bearer-token", _re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+=*"), "[REDACTED-BEARER]"),
    ("jwt", _re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED-JWT]"),
    ("credential", _re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd)['\"]?\s*[:=]\s*['\"]?[^\s'\",}]{8,}"), "[REDACTED-SECRET]"),
    ("openai-key", _re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED-KEY]"),
    ("private-key-block", _re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED-PRIVATE-KEY]"),
    ("credit-card", _re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[REDACTED-PAN]"),
    ("ssn", _re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED-SSN]"),
]


class SanitizationPolicy:
    """Configurable redaction rules for exchange bodies. extend() adds
    rules; a malformed rule raises at construction (fail loud, fail safe)."""

    def __init__(self, rules=None, max_body_chars: int = 2000):
        self.rules = list(rules) if rules is not None else list(DEFAULT_BODY_RULES)
        self.max_body_chars = max_body_chars
        for name, pat, _ in self.rules:
            if not isinstance(pat, _re.Pattern):
                raise CaidoUnavailable(f"body rule {name!r} is not a compiled pattern")

    def extend(self, name: str, pattern: str, replacement: str) -> "SanitizationPolicy":
        self.rules.append((name, _re.compile(pattern), replacement))
        return self

    def sanitize_body(self, body: str) -> "tuple[str, list[str]]":
        """Apply every rule; returns (sanitized, rules_fired)."""
        text = body or ""
        fired = []
        for name, pat, repl in self.rules:
            new, n = pat.subn(repl, text)
            if n:
                fired.append(name)
            text = new
        return text[: self.max_body_chars], fired


def normalize_exchange(exchange: dict,
                       policy: "SanitizationPolicy | None" = None) -> dict:
    """A Caido interception (request+response) -> sanitized observation.

    Expected input shape (fixture-pinned; verify against live API):
      {"id": "...", "request": {"method", "path", "host", "headers", "body"},
       "response": {"status", "headers", "body"}}

    The sanitized flag is set ONLY after the full exchange passes both
    header and body redaction (any exception means no flag) — and the
    output carries the redaction log so a reviewer can see what fired.
    """
    pol = policy or SanitizationPolicy()
    req = exchange.get("request") or {}
    resp = exchange.get("response") or {}
    req_h, fired_h1 = sanitize_headers(req.get("headers"))
    resp_h, fired_h2 = sanitize_headers(resp.get("headers"))
    req_b, fired_b1 = pol.sanitize_body(req.get("body") or "")
    resp_b, fired_b2 = pol.sanitize_body(resp.get("body") or "")
    fired = sorted(set(fired_h1 + fired_h2 + fired_b1 + fired_b2))
    # 'sanitized: True' is earned by completing the full pass above.
    return {
        "kind": "request-response",
        "sanitized": True,
        "redactions": fired,
        "request": {
            "method": req.get("method"),
            "url": f"{req.get('scheme', 'https')}://{req.get('host')}{req.get('path', '')}",
            "headers": req_h,
            "body_len": len(req.get("body") or ""),
            "body": req_b,
        },
        "response": {
            "status": resp.get("status"),
            "headers": resp_h,
            "body_len": len(resp.get("body") or ""),
            "body": resp_b,
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
