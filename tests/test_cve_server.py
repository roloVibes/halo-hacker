"""Unit tests for CVE server."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Loaded by file path: the pack's own `mcp/` folder is a namespace package, so a
# plain `import mcp...` would resolve to the installed MCP SDK instead of the pack.
_PACK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("hh_cve_server", _PACK / "mcp" / "cve_server.py")
cve_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cve_server)

cve_lookup, kev_check, epss_score, answer = (
    cve_server.cve_lookup, cve_server.kev_check, cve_server.epss_score, cve_server.answer)


def test_cve_lookup_offline():
    """Test CVE lookup with mocked responses."""
    # Mock the urllib request to simulate network failure
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Test case 1: Network error
        mock_urlopen.side_effect = Exception("Network error")
        
        result = cve_lookup("CVE-2023-12345")
        assert not result["ok"]
        assert result["error"] == "network"


def test_kev_check_offline(monkeypatch, tmp_path):
    """Test KEV check with mocked responses."""
    # Isolate module-level KEV cache state and the on-disk cache: a prior test
    # (or a real run) may have populated either, and a warm cache would make a
    # "network failure" silently succeed.
    # Patch the module object `kev_check` was bound from (the importlib copy at
    # the top of this file, registered as "hh_cve_server"), NOT a fresh
    # `import cve_server` -- the sys.path insert makes that a distinct module
    # object and the patch would miss.
    # `kev_check` was bound from the importlib-loaded module at the top of this
    # file; its __globals__ is that module's namespace, so patch it there.
    g = kev_check.__globals__
    monkeypatch.setitem(g, "_KEV_DATA", None)
    monkeypatch.setitem(g, "_KEV_CACHE_TIME", None)
    monkeypatch.setitem(g, "_get_cache_dir", lambda: str(tmp_path))

    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = Exception("Network error")
        result = kev_check(["CVE-2023-12345"])
        assert not result["ok"]
        assert result["error"] == "network"


def test_epss_score_offline():
    """Test EPSS score with mocked responses."""
    # Mock the urllib request to simulate network failure
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Test case 1: Network error
        mock_urlopen.side_effect = Exception("Network error")
        
        result = epss_score("CVE-2023-12345")
        assert not result["ok"]
        assert result["error"] == "network"


def test_jsonrpc_initialize():
    """Test JSON-RPC initialize response."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    
    response = answer(msg)
    assert response["result"]["serverInfo"]["name"] == "halo-hacker-cve"
    assert "tools" in response["result"]["capabilities"]


def test_jsonrpc_tools_list():
    """Test JSON-RPC tools/list response."""
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    response = answer(msg)
    tools = response["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    assert "cve_lookup" in tool_names
    assert "kev_check" in tool_names
    assert "epss_score" in tool_names


def test_jsonrpc_tools_call():
    """Test JSON-RPC tools/call response."""
    # Test cve_lookup tool call
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "cve_lookup",
            "arguments": {"cve_id": "CVE-2023-12345"}
        }
    }
    
    response = answer(msg)
    # Should return unknown cve error since we're not mocking the network
    result = json.loads(response["result"]["content"][0]["text"])
    assert not result["ok"]
    # Note: This will return "unknown cve" because of how our implementation handles network errors
    # but it's still an error response, which is what we want to test for


def test_tool_descriptions():
    """Test that tool descriptions are properly set."""
    TOOLS = cve_server.TOOLS
    
    tool_names = [tool["name"] for tool in TOOLS]
    assert "cve_lookup" in tool_names
    assert "kev_check" in tool_names
    assert "epss_score" in tool_names
    
    # Check that descriptions are not empty
    for tool in TOOLS:
        assert tool["description"] is not None and len(tool["description"]) > 0


if __name__ == "__main__":
    # Only the no-fixture tests run here: `halo pack test` execs this block
    # bare, so anything taking monkeypatch/tmp_path (the KEV regression pair)
    # is pytest-only.
    test_cve_lookup_offline()
    test_epss_score_offline()
    test_jsonrpc_initialize()
    test_jsonrpc_tools_list()
    test_jsonrpc_tools_call()
    test_tool_descriptions()
    print("All tests passed!")

def test_kev_check_marks_known_and_unknown(monkeypatch, tmp_path):
    """Regression: kev_check must return per-CVE verdicts, never NameError-as-network.

    The pre-fix version referenced the any(...) generator's loop variable
    (`found_item`) outside its scope; every online call raised NameError and the
    blanket except masked it as {"ok": false, "error": "network"} -- a 100%
    silent failure that the offline-only tests could not see.
    """
    fake_catalog = {
        "vulnerabilities": [
            {"cveID": "CVE-2021-44228", "dateAdded": "2021-12-10",
             "requiredAction": "Apply updates", "rationalForExploitation": ""},
        ]
    }
    monkeypatch.setitem(kev_check.__globals__, "_fetch_kev", lambda: fake_catalog)

    out = kev_check(["CVE-2021-44228", "CVE-1900-0001"])
    assert out["ok"], f"kev_check must succeed online, got {out}"
    by_id = {r["cve_id"]: r for r in out["results"]}
    assert by_id["CVE-2021-44228"]["known_exploited"] is True
    assert by_id["CVE-2021-44228"]["date_added"] == "2021-12-10"
    assert by_id["CVE-1900-0001"]["known_exploited"] is False


def test_nvd_pacer_enforces_unauthenticated_limit(monkeypatch):
    """6 unauthenticated NVD calls inside 30s must sleep; with a key, never."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))
    import cve_server

    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    monkeypatch.delenv("NVD_API_KEY", raising=False)
    cve_server._NVD_CALL_TIMES.clear()

    for _ in range(5):
        cve_server._nvd_pace()
    assert sleeps == [], "first 5 unauthenticated calls must not wait"

    cve_server._nvd_pace()  # 6th inside the window
    assert sleeps and sleeps[0] > 0, "6th call inside 30s must pace"

    # with a key: no pacing ever
    monkeypatch.setenv("NVD_API_KEY", "test-key")
    cve_server._NVD_CALL_TIMES.clear()
    sleeps.clear()
    for _ in range(10):
        cve_server._nvd_pace()
    assert sleeps == [], "keyed calls must never wait"
