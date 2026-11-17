"""Unit tests for the HackerOne MCP server.

All HTTP is mocked; these tests never call the live HackerOne API.
"""
from __future__ import annotations

import base64
import io
import importlib.util
import json
from pathlib import Path
import urllib.error


# Loaded by file path: the pack's own `mcp/` folder is a namespace package, so a
# plain `import mcp...` could resolve to another installed package.
_PACK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("hh_h1_server", _PACK / "mcp" / "h1_server.py")
h1_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h1_server)


class FakeHTTPResponse:
    def __init__(self, status=200, body=b"{}"):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return self.body


def _http_error(url, code, msg, body=b"", headers=None):
    return urllib.error.HTTPError(url, code, msg, headers or {}, io.BytesIO(body))


def _mock_urlopen(monkeypatch, responses):
    calls = []
    queue = list(responses)

    def fake_urlopen(req, timeout=15):
        calls.append(req)
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(h1_server.urllib.request, "urlopen", fake_urlopen)
    return calls


def _enable_env_auth(monkeypatch, user="api-user", token="api-token"):
    monkeypatch.setattr(h1_server, "config_get", None)
    monkeypatch.setenv("H1_API_USER", user)
    monkeypatch.setenv("H1_API_TOKEN", token)
    monkeypatch.setattr(h1_server, "_pace", lambda: None)


def _disable_auth(monkeypatch):
    monkeypatch.setattr(h1_server, "config_get", None)
    monkeypatch.delenv("H1_API_USER", raising=False)
    monkeypatch.delenv("H1_API_TOKEN", raising=False)


def test_auth_resolution_no_credentials_all_tools(monkeypatch):
    _disable_auth(monkeypatch)
    args_by_tool = {
        "h1_balance": {},
        "h1_me_reports": {},
        "h1_report": {"report_id": "123"},
        "h1_programs": {},
        "h1_program": {"handle": "ukg_inc"},
        "h1_program_scopes": {"handle": "ukg_inc"},
        "h1_program_exclusions": {"handle": "ukg_inc"},
        "h1_program_weaknesses": {"handle": "ukg_inc"},
        "h1_earnings": {},
        "h1_payouts": {},
        "h1_hacktivity": {},
        "h1_report_intents": {},
        "h1_report_intent": {"intent_id": "intent-1"},
        "h1_report_create": {
            "team_handle": "ukg_inc",
            "title": "Title",
            "vulnerability_information": "Steps",
            "impact": "Impact",
        },
        "h1_intent_create": {"team_handle": "ukg_inc", "description": "Intent"},
        "h1_intent_update": {"intent_id": "intent-1", "description": "Updated"},
        "h1_intent_delete": {"intent_id": "intent-1"},
        "h1_intent_submit": {"intent_id": "intent-1"},
    }

    assert set(args_by_tool) == set(h1_server._TOOLS)
    for name, args in args_by_tool.items():
        result = h1_server._TOOLS[name](**args)
        assert result["ok"] is False, name
        assert result["error"] == "no_credentials", name


def test_auth_resolution_env_credentials_add_basic_header(monkeypatch):
    _enable_env_auth(monkeypatch, user="user@example.com", token="secret-token")
    calls = _mock_urlopen(monkeypatch, [FakeHTTPResponse(body=b'{"data": {"balance": 0}}')])

    result = h1_server.h1_balance()

    assert result["ok"] is True
    expected = base64.b64encode(b"user@example.com:secret-token").decode("ascii")
    assert calls[0].get_header("Authorization") == "Basic " + expected


def test_url_construction_page_params_quote_and_paths(monkeypatch):
    assert h1_server._page_params(0, 500) == [("page[number]", 1), ("page[size]", 100)]
    assert h1_server._page_params(3, 0) == [("page[number]", 3), ("page[size]", 1)]
    assert h1_server._quote("page[number]") == "page%5Bnumber%5D"

    _enable_env_auth(monkeypatch)
    calls = _mock_urlopen(
        monkeypatch,
        [FakeHTTPResponse(body=b'{"data": {}}'), FakeHTTPResponse(body=b'{"data": {}}')],
    )

    assert h1_server.h1_program("ukg_inc")["ok"] is True
    assert h1_server.h1_report("123")["ok"] is True
    assert calls[0].full_url == "https://api.hackerone.com/v1/hackers/programs/ukg_inc"
    assert calls[1].full_url == "https://api.hackerone.com/v1/hackers/reports/123"


def test_success_parsing_returns_parsed_json(monkeypatch):
    _enable_env_auth(monkeypatch)
    body = {"data": {"balance": 12.34}}
    _mock_urlopen(monkeypatch, [FakeHTTPResponse(body=json.dumps(body).encode())])

    assert h1_server.h1_balance() == {"ok": True, "data": body}


def test_http_401_error_path(monkeypatch):
    _enable_env_auth(monkeypatch)
    _mock_urlopen(
        monkeypatch,
        [_http_error("https://api.hackerone.com/v1/hackers/payments/balance", 401, "Unauthorized", b"nope")],
    )

    result = h1_server.h1_balance()

    assert result == {"ok": False, "error": "http_401", "detail": "nope"}


def test_http_429_retries_once_then_rate_limited(monkeypatch):
    _enable_env_auth(monkeypatch)
    sleeps = []
    monkeypatch.setattr(h1_server.time, "sleep", lambda seconds: sleeps.append(seconds))
    calls = _mock_urlopen(
        monkeypatch,
        [
            _http_error("https://api.hackerone.com/v1/hackers/payments/balance", 429, "Too Many", b"slow", {"Retry-After": "0"}),
            _http_error("https://api.hackerone.com/v1/hackers/payments/balance", 429, "Too Many", b"still slow", {"Retry-After": "0"}),
        ],
    )

    result = h1_server.h1_balance()

    assert len(calls) == 2
    assert sleeps == [0.0]
    assert result == {"ok": False, "error": "rate_limited", "detail": "still slow"}


def test_network_errors_cover_urlerror_and_timeout(monkeypatch):
    for exc in (urllib.error.URLError("down"), TimeoutError("timed out")):
        _enable_env_auth(monkeypatch)
        _mock_urlopen(monkeypatch, [exc])

        result = h1_server.h1_balance()

        assert result == {"ok": False, "error": "network"}


def test_invalid_json_returns_bad_json(monkeypatch):
    _enable_env_auth(monkeypatch)
    _mock_urlopen(monkeypatch, [FakeHTTPResponse(body=b"not-json")])

    result = h1_server.h1_balance()

    assert result["ok"] is False
    assert result["error"] == "bad_json"
    assert result["detail"] == "not-json"


def test_write_payload_shapes_strip_none_and_promote_ids(monkeypatch):
    _enable_env_auth(monkeypatch)
    calls = _mock_urlopen(
        monkeypatch,
        [
            FakeHTTPResponse(body=b'{"data": {"id": "999", "type": "report"}}'),
            FakeHTTPResponse(body=b'{"id": "intent-1", "type": "report_intent"}'),
        ],
    )

    report_result = h1_server.h1_report_create(
        team_handle="ukg_inc",
        title="Title",
        vulnerability_information="Steps",
        impact="Impact",
        severity_rating=None,
        weakness_id="weak-1",
        structured_scope_id=None,
    )
    intent_result = h1_server.h1_intent_create("ukg_inc", "Intent description", title=None)

    assert report_result["id"] == "999"
    report_payload = json.loads(calls[0].data.decode())
    assert report_payload == {
        "data": {
            "type": "report",
            "attributes": {
                "team_handle": "ukg_inc",
                "title": "Title",
                "vulnerability_information": "Steps",
                "impact": "Impact",
                "weakness_id": "weak-1",
            },
        }
    }

    assert intent_result["id"] == "intent-1"
    intent_payload = json.loads(calls[1].data.decode())
    assert intent_payload == {
        "data": {
            "type": "report-intent",
            "attributes": {"team_handle": "ukg_inc", "description": "Intent description"},
        }
    }


def test_mcp_protocol_loop_initialize_list_call_and_unknown(monkeypatch):
    _enable_env_auth(monkeypatch)
    _mock_urlopen(monkeypatch, [FakeHTTPResponse(body=b'{"data": {"balance": 0.0}}')])

    init = h1_server.answer({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    listed = h1_server.answer({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    called = h1_server.answer(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "h1_balance", "arguments": {}},
        }
    )
    unknown = h1_server.answer({"jsonrpc": "2.0", "id": 4, "method": "bogus", "params": {}})

    assert init["result"]["serverInfo"]["name"] == "halo-hacker-h1"
    assert len(listed["result"]["tools"]) == 18
    call_payload = json.loads(called["result"]["content"][0]["text"])
    assert call_payload == {"ok": True, "data": {"data": {"balance": 0.0}}}
    assert unknown["error"]["code"] == -32601
