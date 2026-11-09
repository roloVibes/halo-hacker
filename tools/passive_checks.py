#!/usr/bin/env python3
"""Declarative passive traffic checks for the halo-hacker pack.

Each check is a dict in CHECKS with metadata and a matcher callable.
A matcher receives the sanitized request/response pair and returns either
None (no hit) or a dict of template variables used to render title,
description, and evidence_note.

Scope: response-side, read-only, no outbound traffic.
"""
from __future__ import annotations

import ipaddress
import re
import urllib.parse
from typing import Callable, Optional


SEVERITIES = {"critical", "high", "medium", "low", "info"}


def _is_html_or_js(ct: str) -> bool:
    ct = (ct or "").lower().split(";")[0].strip()
    return ct in {
        "text/html",
        "application/xhtml+xml",
        "application/javascript",
        "text/javascript",
        "application/ecmascript",
    }


def _header_value(headers: dict, name: str) -> str:
    for k, v in (headers or {}).items():
        if k.lower() == name.lower():
            return str(v).split(",")[0].strip()
    return ""


def _missing_security_headers(pair: dict) -> Optional[dict]:
    """HSTS / CSP / X-Content-Type-Options missing on HTML/JS responses."""
    if pair.get("status") != 200:
        return None
    ct = _header_value(pair.get("response_headers") or {}, "content-type")
    if not _is_html_or_js(ct):
        return None
    required = ["strict-transport-security", "content-security-policy", "x-content-type-options"]
    present = {k.lower() for k in (pair.get("response_headers") or {}).keys()}
    missing = [h for h in required if h not in present]
    if not missing:
        return None
    return {"missing": ", ".join(missing)}


def _verbose_banner(pair: dict) -> Optional[dict]:
    """Server or X-Powered-By header discloses a version string."""
    banner_headers = ["server", "x-powered-by", "x-aspnet-version"]
    for h in banner_headers:
        val = _header_value(pair.get("response_headers") or {}, h)
        if not val:
            continue
        # Version-like digits (e.g., nginx/1.18.0, ASP.NET 4.0.30319)
        if re.search(r"\d+\.\d+", val):
            return {"header": h, "value": val[:120]}
    return None


def _stack_trace(pair: dict) -> Optional[dict]:
    """Recognized stack-trace / error patterns in response body."""
    body = pair.get("response_body") or ""
    patterns = [
        ("python", r"Traceback \(most recent call last\)"),
        ("java", r"\sat\s+[a-z][a-z0-9_.]*\.[A-Z][A-Za-z0-9_]*\.[A-Za-z0-9_]+\("),
        ("dotnet", r"System\.[A-Za-z0-9_]+Exception"),
        ("php", r"Fatal error.*in\s+/.+\s+on\s+line\s+\d+"),
    ]
    for lang, pat in patterns:
        if re.search(pat, body, re.IGNORECASE):
            return {"language": lang}
    return None


def _internal_ip(pair: dict) -> Optional[dict]:
    """RFC1918 / loopback IPv4 addresses disclosed in response body."""
    body = pair.get("response_body") or ""
    for m in re.finditer(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", body):
        try:
            ip = ipaddress.ip_address(m.group(1))
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback:
            return {"ip": str(ip)}
    return None


def _insecure_cookie(pair: dict) -> Optional[dict]:
    """Set-Cookie header missing Secure or HttpOnly flags."""
    raw = pair.get("response_headers") or {}
    cookies = []
    for k, v in raw.items():
        if k.lower() == "set-cookie":
            cookies.append(str(v))
    if not cookies:
        return None
    for c in cookies:
        flags = {f.strip().lower() for f in re.split(r"[;,]", c)}
        missing = []
        if "secure" not in flags:
            missing.append("Secure")
        if "httponly" not in flags:
            missing.append("HttpOnly")
        if missing:
            # Report only the cookie name for the evidence note.
            name = c.split(";")[0].split("=")[0].strip() or "unknown"
            return {"cookie_name": name, "missing": ", ".join(missing)}
    return None


def _reflected_value(pair: dict) -> Optional[dict]:
    """A URL query value (>= 8 chars) appears verbatim in the response body."""
    url = pair.get("url") or ""
    body = pair.get("response_body") or ""
    if not body or len(body) > 200_000:
        return None
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qsl(parsed.query)
    seen = set()
    for _name, value in qs:
        if len(value) < 8:
            continue
        if value in seen:
            continue
        seen.add(value)
        if value in body:
            return {"parameter": _name, "value": value[:80]}
    return None


# Declarative, extensible check catalog. Matchers are pure callables.
CHECKS: "list[dict]" = [
    {
        "check_id": "missing-security-headers",
        "severity_hint": "medium",
        "title": "Missing security headers on {host}",
        "description": (
            "The response for {method} {url} is missing the following "
            "security headers: {missing}. Missing headers weaken the browser-side "
            "security posture of the application."
        ),
        "evidence_note": "Missing headers: {missing}",
        "matcher": _missing_security_headers,
    },
    {
        "check_id": "verbose-server-banner",
        "severity_hint": "low",
        "title": "Verbose server banner on {host}",
        "description": (
            "The {header} response header on {host} discloses a version "
            "string ('{value}'), which may assist an attacker in selecting "
            "targeted exploits."
        ),
        "evidence_note": "Header {header}: {value}",
        "matcher": _verbose_banner,
    },
    {
        "check_id": "stack-trace-disclosure",
        "severity_hint": "medium",
        "title": "{language} stack trace disclosed on {host}",
        "description": (
            "The response body for {method} {url} contains a {language} "
            "stack trace or runtime error message, revealing implementation "
            "details and potentially paths or internal identifiers."
        ),
        "evidence_note": "Detected {language} stack-trace pattern in body",
        "matcher": _stack_trace,
    },
    {
        "check_id": "internal-ip-disclosure",
        "severity_hint": "low",
        "title": "Internal IP address disclosed on {host}",
        "description": (
            "The response body for {method} {url} contains the internal or "
            "loopback IP address {ip}, which may reveal internal network "
            "topology."
        ),
        "evidence_note": "Internal IP found in body: {ip}",
        "matcher": _internal_ip,
    },
    {
        "check_id": "insecure-set-cookie",
        "severity_hint": "medium",
        "title": "Session cookie missing Secure/HttpOnly on {host}",
        "description": (
            "The Set-Cookie header for '{cookie_name}' on {host} is missing "
            "the {missing} flag(s), increasing the risk of cookie leakage or "
            "client-side script access."
        ),
        "evidence_note": "Cookie '{cookie_name}' missing {missing}",
        "matcher": _insecure_cookie,
    },
    {
        "check_id": "reflected-query-value",
        "severity_hint": "info",
        "title": "Reflected query value on {host}",
        "description": (
            "The value of query parameter '{parameter}' in {method} {url} is "
            "reflected verbatim in the response body. If user input is echoed "
            "without encoding, it may support cross-site scripting or other "
            "injection issues."
        ),
        "evidence_note": "Parameter '{parameter}' value reflected in body",
        "matcher": _reflected_value,
    },
]


def _render(template: str, vars: dict) -> str:
    """Simple brace substitution with missing-key protection."""
    return template.format(**vars)


def run_checks(pair: dict) -> list[dict]:
    """Run every passive check against a sanitized request/response pair.

    Pair shape:
      {"method", "url", "host", "status", "response_headers": {...},
       "response_body": str}

    Returns a list of hits:
      {"check_id", "title", "severity_hint", "evidence_note", "description"}
    """
    hits = []
    base_vars = {
        "method": str(pair.get("method", "")),
        "url": str(pair.get("url", "")),
        "host": str(pair.get("host", "")),
        "status": str(pair.get("status", "")),
    }
    for check in CHECKS:
        match = check["matcher"](pair)
        if match is None:
            continue
        vars = {**base_vars, **match}
        hits.append({
            "check_id": check["check_id"],
            "title": _render(check["title"], vars),
            "severity_hint": check["severity_hint"],
            "evidence_note": _render(check["evidence_note"], vars),
            "description": _render(check["description"], vars),
        })
    return hits
