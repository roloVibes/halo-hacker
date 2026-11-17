"""HackerOne Hacker API v1 MCP server for halo-hacker, stdlib-only.

Tools:
- h1_balance() — GET /v1/hackers/payments/balance
- h1_me_reports(page=1, page_size=100) — GET /v1/hackers/me/reports
- h1_report(report_id) — GET /v1/hackers/reports/{id}
- h1_programs(page=1, page_size=100) — GET /v1/hackers/programs
- h1_program(handle) — GET /v1/hackers/programs/{handle}
- h1_program_scopes(handle, page=1, page_size=100) — GET /v1/hackers/programs/{handle}/structured_scopes
- h1_program_exclusions(handle) — GET /v1/hackers/programs/{handle}/scope_exclusions
- h1_program_weaknesses(handle, page=1, page_size=100) — GET /v1/hackers/programs/{handle}/weaknesses
- h1_earnings(page=1, page_size=100) — GET /v1/hackers/payments/earnings
- h1_payouts(page=1, page_size=100) — GET /v1/hackers/payments/payouts
- h1_hacktivity(query=None, sort=None, page=1, page_size=25) — GET /v1/hackers/hacktivity
- h1_report_intents() — GET /v1/hackers/report_intents
- h1_report_intent(intent_id) — GET /v1/hackers/report_intents/{id}
- h1_report_create(team_handle, title, vulnerability_information, impact,
  severity_rating=None, weakness_id=None, structured_scope_id=None) — POST /v1/hackers/reports
- h1_intent_create(team_handle, description, title=None) — POST /v1/hackers/report_intents
- h1_intent_update(intent_id, description) — PATCH /v1/hackers/report_intents/{id}
- h1_intent_delete(intent_id) — DELETE /v1/hackers/report_intents/{id}
- h1_intent_submit(intent_id) — POST /v1/hackers/report_intents/{id}/submit

Auth resolution order: first halo_harness.ext.config_get("halo-hacker", "h1_api_user")
and config_get("halo-hacker", "h1_api_token") when the Halo harness is importable;
then environment variables H1_API_USER and H1_API_TOKEN. If neither source provides
both values, every tool returns {"ok": false, "error": "no_credentials"} with a setup note.

HackerOne quirk: nonexistent API paths may return 401, so this server never treats 401
as proof of bad credentials by itself; it returns the HTTP status and response body detail.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from halo_harness.ext import API_VERSION, config_get
except ImportError:  # the `python` on PATH is not the one Halo runs in
    API_VERSION = "1.0"
    config_get = None

_BASE_URL = "https://api.hackerone.com"
_USER_AGENT = "halo-hacker-h1-server/1.0"
_MIN_REQUEST_INTERVAL = 0.5
_LAST_REQUEST_AT = 0.0
_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def _get_data_dir() -> str:
    """Get the pack data directory, using HALO_HACKER_DATA_DIR env var or default."""
    data_dir = os.environ.get("HALO_HACKER_DATA_DIR")
    if not data_dir:
        data_dir = os.path.expanduser("~/.halo/halo-hacker-data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _config_value(key: str) -> Optional[str]:
    if config_get is None:
        return None
    try:
        value = config_get("halo-hacker", key)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _credentials() -> Optional[Tuple[str, str]]:
    user = _config_value("h1_api_user")
    token = _config_value("h1_api_token")
    if not user or not token:
        user = os.environ.get("H1_API_USER") or ""
        token = os.environ.get("H1_API_TOKEN") or ""
    user = user.strip()
    token = token.strip()
    if user and token:
        return user, token
    return None


def _no_credentials() -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "no_credentials",
        "note": (
            "Set halo-hacker config keys h1_api_user and h1_api_token, or set "
            "environment variables H1_API_USER and H1_API_TOKEN."
        ),
    }


def _quote(value: Any) -> str:
    out = []
    for byte in str(value).encode("utf-8"):
        char = chr(byte)
        if char in _UNRESERVED:
            out.append(char)
        else:
            out.append("%{:02X}".format(byte))
    return "".join(out)


def _encode_query(params: List[Tuple[str, Any]]) -> str:
    parts = []
    for key, value in params:
        if value is None:
            continue
        parts.append("{}={}".format(_quote(key), _quote(value)))
    return "&".join(parts)


def _path_segment(value: Any) -> str:
    return _quote(value)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _page_params(page: Any, page_size: Any) -> List[Tuple[str, Any]]:
    page_number = _as_int(page, 1)
    if page_number < 1:
        page_number = 1
    size = _as_int(page_size, 100)
    if size < 1:
        size = 1
    if size > 100:
        size = 100
    return [("page[number]", page_number), ("page[size]", size)]


def _pace() -> None:
    global _LAST_REQUEST_AT
    now = time.monotonic()
    if _LAST_REQUEST_AT:
        wait = _MIN_REQUEST_INTERVAL - (now - _LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


def _decode_body(raw: bytes) -> str:
    return raw.decode("utf-8", "replace")


def _truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _retry_after_seconds(headers: Any) -> float:
    try:
        value = headers.get("Retry-After")
    except Exception:
        value = None
    if value is None:
        return 5.0
    try:
        seconds = float(str(value).strip())
    except Exception:
        return 5.0
    if seconds < 0:
        return 0.0
    return seconds


def _parse_success(raw: bytes) -> Dict[str, Any]:
    if not raw:
        return {"ok": True, "data": {}}
    text = _decode_body(raw)
    try:
        data = json.loads(text)
    except ValueError:
        return {"ok": False, "error": "bad_json", "detail": _truncate(text)}
    return {"ok": True, "data": data}


def _open_once(req: urllib.request.Request) -> Tuple[Dict[str, Any], Optional[float]]:
    try:
        _pace()
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.getcode()
            raw = response.read()
            if status < 200 or status >= 300:
                detail = _truncate(_decode_body(raw))
                if status == 429:
                    return {"ok": False, "error": "rate_limited", "detail": detail}, 5.0
                return {"ok": False, "error": "http_{}".format(status), "detail": detail}, None
            return _parse_success(raw), None
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:
            raw = b""
        detail = _truncate(_decode_body(raw))
        if e.code == 429:
            return {"ok": False, "error": "rate_limited", "detail": detail}, _retry_after_seconds(e.headers)
        return {"ok": False, "error": "http_{}".format(e.code), "detail": detail}, None
    except Exception:
        return {"ok": False, "error": "network"}, None


def _request(method: str, path: str, query: Optional[List[Tuple[str, Any]]] = None,
             payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    creds = _credentials()
    if creds is None:
        return _no_credentials()

    url = _BASE_URL + path
    if query:
        encoded = _encode_query(query)
        if encoded:
            url += "?" + encoded

    user, token = creds
    basic = base64.b64encode((user + ":" + token).encode("utf-8")).decode("ascii")
    headers = {
        "Accept": "application/json",
        "Authorization": "Basic " + basic,
        "User-Agent": _USER_AGENT,
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    for attempt in range(2):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        result, retry_after = _open_once(req)
        if retry_after is not None and attempt == 0:
            time.sleep(retry_after)
            continue
        return result
    return {"ok": False, "error": "rate_limited"}


def _clean_attrs(attrs: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in attrs.items() if value is not None}


def _json_api_payload(resource_type: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
    return {"data": {"type": resource_type, "attributes": _clean_attrs(attrs)}}


def _with_top_level_id(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result.get("ok"):
        return result
    data = result.get("data")
    found = None
    if isinstance(data, dict):
        item = data.get("data")
        if isinstance(item, dict) and item.get("id") is not None:
            found = item.get("id")
        elif data.get("id") is not None:
            found = data.get("id")
    if found is not None:
        result = dict(result)
        result["id"] = str(found)
    return result


def h1_balance() -> Dict[str, Any]:
    """Get the hacker payments balance."""
    return _request("GET", "/v1/hackers/payments/balance")


def h1_me_reports(page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List the authenticated hacker's reports."""
    return _request("GET", "/v1/hackers/me/reports", _page_params(page, page_size))


def h1_report(report_id: Any) -> Dict[str, Any]:
    """Get one hacker report by id."""
    return _request("GET", "/v1/hackers/reports/{}".format(_path_segment(report_id)))


def h1_programs(page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List hacker-visible programs."""
    return _request("GET", "/v1/hackers/programs", _page_params(page, page_size))


def h1_program(handle: Any) -> Dict[str, Any]:
    """Get one program by handle."""
    return _request("GET", "/v1/hackers/programs/{}".format(_path_segment(handle)))


def h1_program_scopes(handle: Any, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List structured scopes for a program handle."""
    path = "/v1/hackers/programs/{}/structured_scopes".format(_path_segment(handle))
    return _request("GET", path, _page_params(page, page_size))


def h1_program_exclusions(handle: Any) -> Dict[str, Any]:
    """List scope exclusions for a program handle."""
    path = "/v1/hackers/programs/{}/scope_exclusions".format(_path_segment(handle))
    return _request("GET", path)


def h1_program_weaknesses(handle: Any, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List weaknesses for a program handle."""
    path = "/v1/hackers/programs/{}/weaknesses".format(_path_segment(handle))
    return _request("GET", path, _page_params(page, page_size))


def h1_earnings(page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List hacker payment earnings."""
    return _request("GET", "/v1/hackers/payments/earnings", _page_params(page, page_size))


def h1_payouts(page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """List hacker payment payouts."""
    return _request("GET", "/v1/hackers/payments/payouts", _page_params(page, page_size))


def h1_hacktivity(query: Optional[str] = None, sort: Optional[str] = None,
                  page: int = 1, page_size: int = 25) -> Dict[str, Any]:
    """Search HackerOne hacktivity."""
    params = []
    if query is not None:
        params.append(("queryString", query))
    if sort is not None:
        params.append(("sort", sort))
    params.extend(_page_params(page, page_size))
    return _request("GET", "/v1/hackers/hacktivity", params)


def h1_report_intents() -> Dict[str, Any]:
    """List report intents."""
    return _request("GET", "/v1/hackers/report_intents")


def h1_report_intent(intent_id: Any) -> Dict[str, Any]:
    """Get one report intent by id."""
    return _request("GET", "/v1/hackers/report_intents/{}".format(_path_segment(intent_id)))


def h1_report_create(team_handle: str, title: str, vulnerability_information: str,
                     impact: str, severity_rating: Optional[str] = None,
                     weakness_id: Optional[str] = None,
                     structured_scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a HackerOne report."""
    payload = _json_api_payload("report", {
        "team_handle": team_handle,
        "title": title,
        "vulnerability_information": vulnerability_information,
        "impact": impact,
        "severity_rating": severity_rating,
        "weakness_id": weakness_id,
        "structured_scope_id": structured_scope_id,
    })
    return _with_top_level_id(_request("POST", "/v1/hackers/reports", payload=payload))


def h1_intent_create(team_handle: str, description: str,
                     title: Optional[str] = None) -> Dict[str, Any]:
    """Create a report intent."""
    payload = _json_api_payload("report-intent", {
        "team_handle": team_handle,
        "description": description,
        "title": title,
    })
    return _with_top_level_id(_request("POST", "/v1/hackers/report_intents", payload=payload))


def h1_intent_update(intent_id: Any, description: str) -> Dict[str, Any]:
    """Update a report intent description."""
    payload = _json_api_payload("report-intent", {"description": description})
    path = "/v1/hackers/report_intents/{}".format(_path_segment(intent_id))
    return _with_top_level_id(_request("PATCH", path, payload=payload))


def h1_intent_delete(intent_id: Any) -> Dict[str, Any]:
    """Delete a report intent."""
    path = "/v1/hackers/report_intents/{}".format(_path_segment(intent_id))
    return _with_top_level_id(_request("DELETE", path))


def h1_intent_submit(intent_id: Any) -> Dict[str, Any]:
    """Submit a report intent."""
    path = "/v1/hackers/report_intents/{}/submit".format(_path_segment(intent_id))
    return _with_top_level_id(_request("POST", path))


_TOOLS = {
    "h1_balance": h1_balance,
    "h1_me_reports": h1_me_reports,
    "h1_report": h1_report,
    "h1_programs": h1_programs,
    "h1_program": h1_program,
    "h1_program_scopes": h1_program_scopes,
    "h1_program_exclusions": h1_program_exclusions,
    "h1_program_weaknesses": h1_program_weaknesses,
    "h1_earnings": h1_earnings,
    "h1_payouts": h1_payouts,
    "h1_hacktivity": h1_hacktivity,
    "h1_report_intents": h1_report_intents,
    "h1_report_intent": h1_report_intent,
    "h1_report_create": h1_report_create,
    "h1_intent_create": h1_intent_create,
    "h1_intent_update": h1_intent_update,
    "h1_intent_delete": h1_intent_delete,
    "h1_intent_submit": h1_intent_submit,
}

TOOLS = [
    {"name": "h1_balance", "description": h1_balance.__doc__.strip(),
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "h1_me_reports", "description": h1_me_reports.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}}}},
    {"name": "h1_report", "description": h1_report.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"report_id": {"type": "string"}},
                     "required": ["report_id"]}},
    {"name": "h1_programs", "description": h1_programs.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}}}},
    {"name": "h1_program", "description": h1_program.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"handle": {"type": "string"}},
                     "required": ["handle"]}},
    {"name": "h1_program_scopes", "description": h1_program_scopes.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"handle": {"type": "string"},
                                    "page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}},
                     "required": ["handle"]}},
    {"name": "h1_program_exclusions", "description": h1_program_exclusions.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"handle": {"type": "string"}},
                     "required": ["handle"]}},
    {"name": "h1_program_weaknesses", "description": h1_program_weaknesses.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"handle": {"type": "string"},
                                    "page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}},
                     "required": ["handle"]}},
    {"name": "h1_earnings", "description": h1_earnings.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}}}},
    {"name": "h1_payouts", "description": h1_payouts.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 100}}}},
    {"name": "h1_hacktivity", "description": h1_hacktivity.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"},
                                    "sort": {"type": "string"},
                                    "page": {"type": "integer", "default": 1},
                                    "page_size": {"type": "integer", "default": 25}}}},
    {"name": "h1_report_intents", "description": h1_report_intents.__doc__.strip(),
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "h1_report_intent", "description": h1_report_intent.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"intent_id": {"type": "string"}},
                     "required": ["intent_id"]}},
    {"name": "h1_report_create", "description": h1_report_create.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"team_handle": {"type": "string"},
                                    "title": {"type": "string"},
                                    "vulnerability_information": {"type": "string"},
                                    "impact": {"type": "string"},
                                    "severity_rating": {"type": "string"},
                                    "weakness_id": {"type": "string"},
                                    "structured_scope_id": {"type": "string"}},
                     "required": ["team_handle", "title", "vulnerability_information", "impact"]}},
    {"name": "h1_intent_create", "description": h1_intent_create.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"team_handle": {"type": "string"},
                                    "description": {"type": "string"},
                                    "title": {"type": "string"}},
                     "required": ["team_handle", "description"]}},
    {"name": "h1_intent_update", "description": h1_intent_update.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"intent_id": {"type": "string"},
                                    "description": {"type": "string"}},
                     "required": ["intent_id", "description"]}},
    {"name": "h1_intent_delete", "description": h1_intent_delete.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"intent_id": {"type": "string"}},
                     "required": ["intent_id"]}},
    {"name": "h1_intent_submit", "description": h1_intent_submit.__doc__.strip(),
     "inputSchema": {"type": "object",
                     "properties": {"intent_id": {"type": "string"}},
                     "required": ["intent_id"]}},
]


def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    fn = _TOOLS.get(name)
    if fn is None:
        return {"content": [{"type": "text", "text": "no tool {}".format(name)}], "isError": True}
    try:
        result = fn(**(args or {}))
    except TypeError as bad_args:
        return {"content": [{"type": "text", "text": "{}: {}".format(name, bad_args)}], "isError": True}
    except Exception:
        result = {"ok": False, "error": "network"}
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}], "isError": False}


def answer(msg: Dict[str, Any]):
    """The reply to one request (None for a notification)."""
    method, params = msg.get("method"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion") or "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "halo-hacker-h1", "version": "1.0.0", "extensionApi": API_VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(str(params.get("name") or ""), params.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "no method {}".format(method)}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


def main() -> int:
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
